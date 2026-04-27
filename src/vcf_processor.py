"""
VCF Processor Module

Handles parsing of VCF files from 1000 Genomes Project to extract genetic variants.
Focuses on CYP genes (CYP2D6 on chromosome 22, CYP2C19 on chr10, CYP3A4 on chr7).
Supports both local file access and S3 cloud storage integration.

Database Backend Integration (Day 1 Afternoon):
- Uses database backend (variant_db_v2.py) for gene locations when available
- Falls back to hardcoded GENE_LOCATIONS if database unavailable
- Maintains backward compatibility with existing workflow
"""

import gzip
import logging
import os
import subprocess  # nosec B404 - tabix for region-indexed VCF; args from config/paths
import tempfile
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

try:
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config as BotoConfig
except Exception:  # pragma: no cover
    boto3 = None
    UNSIGNED = None  # type: ignore[assignment]
    BotoConfig = None  # type: ignore[assignment]

from .allele_caller import _genotype_to_alleles, call_gene_from_variants
from .cyp1a2_caller import interpret_cyp1a2_from_vcf
from .cyp2b6_caller import interpret_cyp2b6_from_vcf
from .cyp3a_caller import interpret_cyp3a4_from_vcf, interpret_cyp3a5_from_vcf
from .dpyd_caller import interpret_dpyd_from_vcf
from .exceptions import VCFProcessingError
from .gst_caller import interpret_gst_from_vcf
from .nat2_caller import interpret_nat2_from_vcf
from .pgx_triggers import DRUG_GENE_TRIGGERS
from .slco1b1_caller import interpret_slco1b1, interpret_slco1b1_from_vcf
from .tpmt_caller import interpret_tpmt_from_vcf
from .variant_db import (
    VARIANT_DB,
    get_allele_interpretation,
    get_phenotype_prediction,
    get_variant_info,
)
from .warfarin_caller import interpret_warfarin_from_vcf

# Database backend (NEW - Day 1 Afternoon)
try:
    from .variant_db_v2 import get_gene_location, list_supported_genes

    DB_BACKEND_AVAILABLE = True
except ImportError:
    DB_BACKEND_AVAILABLE = False

# AWS S3 integration (optional)
try:
    from .aws.s3_genomic_manager import S3GenomicDataManager

    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False

# Set up logging
logger = logging.getLogger(__name__)

# Gene locations by genome build
# GRCh37/hg19 coordinates (1000 Genomes Phase 3)
# NOTE: These are fallback values. Database backend (variant_db_v2.py) is preferred.
GENE_LOCATIONS_GRCH37 = {
    "CYP2D6": {"chrom": "22", "start": 42522500, "end": 42530900},
    "CYP2C19": {"chrom": "10", "start": 96535040, "end": 96625463},
    "CYP2C9": {"chrom": "10", "start": 96698415, "end": 96749147},
    "CYP3A4": {"chrom": "7", "start": 99376140, "end": 99391055},
    "CYP3A5": {"chrom": "7", "start": 99245000, "end": 99277000},
    "CYP1A2": {"chrom": "15", "start": 75041187, "end": 75048941},
    "CYP2B6": {"chrom": "19", "start": 41354432, "end": 41395879},
    "NAT2": {"chrom": "8", "start": 18257854, "end": 18267997},
    "GSTM1": {"chrom": "1", "start": 110230233, "end": 110264979},
    "GSTT1": {"chrom": "22", "start": 24376182, "end": 24384491},
    "UGT1A1": {"chrom": "2", "start": 234668875, "end": 234689625},
    "SLCO1B1": {"chrom": "12", "start": 21288593, "end": 21397223},
    "VKORC1": {"chrom": "16", "start": 31102163, "end": 31107800},
    "TPMT": {"chrom": "6", "start": 18128542, "end": 18155374},
    "DPYD": {"chrom": "1", "start": 97543299, "end": 97883432},
    # Proxy marker for HLA-B*57:01 (rs2395029; HCP5 region). Used for abacavir safety flag.
    "HLA_B5701": {"chrom": "6", "start": 31365000, "end": 31369000},
    # Proxy region for HLA-B*15:02 tag SNP rs3909184 (carbamazepine / phenytoin / oxcarbazepine SJS/TEN).
    "HLA_B1502": {"chrom": "6", "start": 31356200, "end": 31357200},
}

# GRCh38/hg38 coordinates (required for PharmCAT compatibility)
GENE_LOCATIONS_GRCH38 = {
    "CYP2D6": {"chrom": "chr22", "start": 42126499, "end": 42135000},
    "CYP2C19": {"chrom": "chr10", "start": 94762681, "end": 94855547},
    "CYP2C9": {"chrom": "chr10", "start": 94938683, "end": 94990091},
    "CYP3A4": {"chrom": "chr7", "start": 99756960, "end": 99784247},
    "CYP3A5": {"chrom": "chr7", "start": 99660464, "end": 99700494},
    "CYP1A2": {"chrom": "chr15", "start": 74749056, "end": 74763903},
    "CYP2B6": {"chrom": "chr19", "start": 40993483, "end": 41043478},
    "NAT2": {"chrom": "chr8", "start": 18389455, "end": 18405702},
    "GSTM1": {"chrom": "chr1", "start": 110183534, "end": 110218195},
    "GSTT1": {"chrom": "chr22", "start": 24359079, "end": 24367533},
    "UGT1A1": {"chrom": "chr2", "start": 233757687, "end": 233773299},
    "SLCO1B1": {"chrom": "chr12", "start": 21130388, "end": 21241481},
    "VKORC1": {"chrom": "chr16", "start": 31096368, "end": 31101932},
    "TPMT": {"chrom": "chr6", "start": 18128542, "end": 18155372},
    "DPYD": {"chrom": "chr1", "start": 97078528, "end": 97921547},
    "HLA_B5701": {"chrom": "chr6", "start": 31265000, "end": 31269000},
    "HLA_B1502": {"chrom": "chr6", "start": 31236000, "end": 31237000},
}

# Default: GRCh37 (backward-compatible alias)
CYP_GENE_LOCATIONS = GENE_LOCATIONS_GRCH37


def get_gene_locations(build: str = "GRCh37") -> Dict:
    """
    Return gene location dict for the specified genome build.

    Database Backend Integration (Day 1 Afternoon):
    - Tries database backend first (variant_db_v2.py) for scalable 100+ gene support
    - Falls back to hardcoded GENE_LOCATIONS if database unavailable
    - Maintains backward compatibility with existing workflow
    """
    # Try database backend first (NEW - Day 1 Afternoon)
    if DB_BACKEND_AVAILABLE:
        try:
            genes = list_supported_genes()
            if genes:
                locations = {}
                for gene in genes:
                    loc = get_gene_location(gene, build)
                    if loc:
                        locations[gene] = {
                            "chrom": loc["chrom"],
                            "start": loc["start"],
                            "end": loc["end"],
                        }
                if locations:
                    logger.info(
                        f"Loaded {len(locations)} gene locations from database backend (build: {build})"
                    )
                    return locations
        except Exception as e:
            logger.debug(
                f"Database backend unavailable for gene locations, using hardcoded: {e}"
            )

    # Fallback to hardcoded locations (backward compatibility)
    if build.upper() in ("GRCH38", "HG38"):
        return GENE_LOCATIONS_GRCH38
    return GENE_LOCATIONS_GRCH37


# Genes included in patient profile (must have CYP_GENE_LOCATIONS; VARIANT_DB used as fallback where applicable).
# Order: Big 3 CYPs first, then Phase II / transporters, then Warfarin (VKORC1).
# Database Backend Integration (Day 1 Afternoon): Dynamically loaded from database when available
if DB_BACKEND_AVAILABLE:
    try:
        PROFILE_GENES = list_supported_genes(tier=1)
        if PROFILE_GENES:
            logger.info(
                f"Loaded {len(PROFILE_GENES)} profile genes from database backend"
            )
        else:
            # Fallback to hardcoded list (all 15 Tier-1 genes)
            PROFILE_GENES = [
                "CYP2D6",
                "CYP2C19",
                "CYP2C9",
                "CYP3A4",
                "CYP3A5",
                "CYP1A2",
                "CYP2B6",
                "NAT2",
                "UGT1A1",
                "SLCO1B1",
                "VKORC1",
                "TPMT",
                "DPYD",
                "GSTM1",
                "GSTT1",
                "HLA_B5701",
                "HLA_B1502",
            ]
    except Exception as e:
        logger.debug(
            f"Database backend unavailable for profile genes, using hardcoded: {e}"
        )
        PROFILE_GENES = [
            "CYP2D6",
            "CYP2C19",
            "CYP2C9",
            "CYP3A4",
            "CYP3A5",
            "CYP1A2",
            "CYP2B6",
            "NAT2",
            "UGT1A1",
            "SLCO1B1",
            "VKORC1",
            "TPMT",
            "DPYD",
            "GSTM1",
            "GSTT1",
            "HLA_B5701",
            "HLA_B1502",
        ]
else:
    PROFILE_GENES = [
        "CYP2D6",
        "CYP2C19",
        "CYP2C9",
        "CYP3A4",
        "CYP3A5",
        "CYP1A2",
        "CYP2B6",
        "NAT2",
        "UGT1A1",
        "SLCO1B1",
        "VKORC1",
        "TPMT",
        "DPYD",
        "GSTM1",
        "GSTT1",
        "HLA_B5701",
        "HLA_B1502",
    ]

# Warfarin PGx: rsIDs used for deterministic CYP2C9 + VKORC1 interpretation.
WARFARIN_RSIDS = {"rs1799853", "rs1057910", "rs9923231"}
# SLCO1B1 (statin myopathy): CPIC marker rs4149056.
SLCO1B1_RSIDS = {"rs4149056"}
# Drugs that trigger SLCO1B1 statin PGx recommendation (CPIC-style).
STATIN_DRUGS = {
    "simvastatin",
    "atorvastatin",
    "rosuvastatin",
    "pravastatin",
    "lovastatin",
    "fluvastatin",
    "pitavastatin",
}

# Star Allele to Activity Score Mapping
# Based on CPIC/PharmVar guidelines
# Activity Score (AS) determines metabolizer status:
# - AS = 0: Poor Metabolizer
# - AS = 0.5-1.0: Intermediate Metabolizer
# - AS = 1.5-2.0: Extensive Metabolizer (Normal)
# - AS > 2.0: Ultra-Rapid Metabolizer (requires duplication)

CYP2D6_ACTIVITY_SCORES = {
    "*1": 1.0,  # Wild type (normal function)
    "*2": 1.0,  # Normal function
    "*3": 0.0,  # No function (nonsense mutation)
    "*4": 0.0,  # No function (splicing defect)
    "*5": 0.0,  # No function (gene deletion)
    "*6": 0.0,  # No function (frameshift)
    "*9": 0.5,  # Reduced function
    "*10": 0.5,  # Reduced function
    "*17": 0.5,  # Reduced function
    "*29": 0.5,  # Reduced function
    "*41": 0.5,  # Reduced function
    "*1xN": 1.0,  # Normal function, duplicated (AS multiplied by copy number)
    "*2xN": 1.0,  # Normal function, duplicated
}

CYP2C19_ACTIVITY_SCORES = {
    "*1": 1.0,  # Wild type (normal function)
    "*2": 0.0,  # No function
    "*3": 0.0,  # No function
    "*4": 0.0,  # No function
    "*5": 0.0,  # No function
    "*6": 0.0,  # No function
    "*7": 0.0,  # No function
    "*8": 0.0,  # No function
    "*9": 0.5,  # Reduced function
    "*10": 0.5,  # Reduced function
    "*17": 1.5,  # Increased function (gain-of-function)
    "*1xN": 1.0,  # Normal function, duplicated
    "*17xN": 1.5,  # Increased function, duplicated (ultra-rapid)
}

CYP2C9_ACTIVITY_SCORES = {
    "*1": 1.0,  # Wild type (normal function)
    "*2": 0.5,  # Reduced function
    "*3": 0.0,  # No function
    "*4": 0.0,  # No function
    "*5": 0.0,  # No function
    "*6": 0.0,  # No function
    "*8": 0.0,  # No function
    "*11": 0.0,  # No function
    "*13": 0.5,  # Reduced function
    "*14": 0.5,  # Reduced function
}

# Gene-specific activity score mappings
CYP_ACTIVITY_SCORES = {
    "CYP2D6": CYP2D6_ACTIVITY_SCORES,
    "CYP2C19": CYP2C19_ACTIVITY_SCORES,
    "CYP2C9": CYP2C9_ACTIVITY_SCORES,
}


def alt_dosage(gt: str):
    """
    Convert VCF genotype into ALT allele dosage.

    Examples:
        0/0 → 0 copies ALT
        0/1 → 1 copy ALT
        1/1 → 2 copies ALT
    """
    if gt in ("0/0", "0|0"):
        return 0
    if gt in ("0/1", "1/0", "0|1", "1|0"):
        return 1
    if gt in ("1/1", "1|1"):
        return 2
    return None


def validate_vcf(file_content: str) -> Tuple[bool, str]:
    """
    Validate VCF file content.

    Args:
        file_content: Content of the VCF file as string

    Returns:
        Tuple of (is_valid, error_message)
    """
    lines = file_content.strip().split("\n")
    if not lines:
        return False, "Empty file"

    # Check for VCF header
    if not lines[0].startswith("##fileformat=VCF"):
        return False, "Missing VCF fileformat header (##fileformat=VCF...)"

    # Check for column header
    has_header = False
    for line in lines:
        if line.startswith("#CHROM"):
            has_header = True
            fields = line.strip().split("\t")
            required = ["#CHROM", "POS", "ID", "REF", "ALT", "QUAL", "FILTER", "INFO"]
            if not all(field in fields for field in required):
                return False, f"Missing required columns. Found: {fields}"
            break

    if not has_header:
        return False, "Missing column header line starting with #CHROM"

    return True, "Valid VCF"


def parse_vcf_line(line: str) -> Optional[Dict]:
    """
    Parse a single VCF line (non-header).

    Returns:
        Dictionary with variant information or None if invalid
    """
    if line.startswith("#"):
        return None

    fields = line.strip().split("\t")
    if len(fields) < 10:
        return None

    try:
        chrom = fields[0]
        pos = int(fields[1])
        var_id = fields[2]
        ref = fields[3]
        alt = fields[4]
        qual = fields[5]
        filter_status = fields[6]
        info = fields[7]
        format_field = fields[8]
        genotypes = fields[9:]

        return {
            "chrom": chrom,
            "pos": pos,
            "id": var_id,
            "ref": ref,
            "alt": alt,
            "qual": qual,
            "filter": filter_status,
            "info": info,
            "format": format_field,
            "genotypes": genotypes,
        }
    except (ValueError, IndexError):
        return None


def extract_cyp_variants(
    vcf_path: str, gene: str = "CYP2D6", sample_limit: Optional[int] = None
) -> List[Dict]:
    """
    Extract variants in CYP gene regions from VCF file.

    Args:
        vcf_path: Path to VCF file (can be .gz compressed)
        gene: Gene name (CYP2D6, CYP2C19, CYP3A4)
        sample_limit: Limit number of samples to process (None = all)

    Returns:
        List of variant dictionaries with sample genotypes
    """
    if gene not in CYP_GENE_LOCATIONS:
        raise VCFProcessingError(
            f"Unknown gene: {gene}. Supported: {list(CYP_GENE_LOCATIONS.keys())}",
            vcf_path=vcf_path,
        )

    gene_loc = CYP_GENE_LOCATIONS[gene]
    target_chrom = gene_loc["chrom"]
    start_pos = gene_loc["start"]
    end_pos = gene_loc["end"]

    variants = []

    # Open VCF file (handle gzip)
    open_func = cast(
        Callable[..., Any],
        gzip.open if vcf_path.endswith(".gz") else open,
    )
    mode = "rt" if vcf_path.endswith(".gz") else "r"

    try:
        with open_func(vcf_path, mode) as f:
            sample_names = None

            for line_num, line in enumerate(f):
                # Parse header to get sample names
                if line.startswith("#CHROM"):
                    header_fields = line.strip().split("\t")
                    if len(header_fields) > 9:
                        sample_names = header_fields[9:]
                        if sample_limit:
                            sample_names = sample_names[:sample_limit]
                    continue

                # Skip other header lines
                if line.startswith("#"):
                    continue

                # Parse variant line
                variant = parse_vcf_line(line)
                if not variant:
                    continue

                # Check if variant is in target region
                if (
                    variant["chrom"] == target_chrom
                    and start_pos <= variant["pos"] <= end_pos
                ):
                    # Add sample information
                    variant["gene"] = gene
                    variant["samples"] = {}

                    if sample_names:
                        for i, sample_name in enumerate(sample_names):
                            if i < len(variant["genotypes"]):
                                variant["samples"][sample_name] = variant["genotypes"][
                                    i
                                ]

                    variants.append(variant)

                    # Progress indicator for large files
                    if len(variants) % 100 == 0:
                        logger.debug(
                            f"Found {len(variants)} variants in {gene} region..."
                        )

        logger.info(f"Total variants found in {gene} region: {len(variants)}")
        return variants

    except FileNotFoundError:
        raise VCFProcessingError(f"VCF file not found: {vcf_path}", vcf_path=vcf_path)
    except Exception as e:
        logger.error(f"Error parsing VCF file: {e}", exc_info=True)
        raise VCFProcessingError(
            f"Error parsing VCF file: {str(e)}", vcf_path=vcf_path
        ) from e


def extract_variants_with_tabix(vcf_path: str, gene: str) -> List[Dict]:
    """
    Extract variants using tabix region query instead of full file scan.
    Requires .tbi index file. Falls back to full-file scan on tabix failure.
    """
    if gene not in CYP_GENE_LOCATIONS:
        return []

    gene_loc = CYP_GENE_LOCATIONS[gene]
    chrom = gene_loc["chrom"]
    start = gene_loc["start"]
    end = gene_loc["end"]
    region = f"{chrom}:{start}-{end}"

    try:
        # -h: include header so we can build variant["samples"] for sample_id lookup
        result = subprocess.run(  # nosec B603 B607 - tabix fixed cmd; vcf_path/region from config
            ["tabix", "-h", vcf_path, region],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        lines = result.stdout.strip().split("\n")
        sample_names: Optional[List[str]] = None
        variants: List[Dict] = []

        for line in lines:
            if not line:
                continue
            if line.startswith("#CHROM"):
                parts = line.strip().split("\t")
                if len(parts) > 9:
                    sample_names = parts[9:]
                continue
            if line.startswith("#"):
                continue

            variant = parse_vcf_line(line)
            if not variant:
                continue
            variant["gene"] = gene
            variant["samples"] = {}
            if sample_names and variant.get("genotypes"):
                for i, name in enumerate(sample_names):
                    if i < len(variant["genotypes"]):
                        variant["samples"][name] = variant["genotypes"][i]
            variants.append(variant)

        if variants:
            logger.info(
                f"Tabix: found {len(variants)} variants in {gene} region (query {region})"
            )
        return variants

    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ) as e:
        logger.warning(
            f"Tabix region query failed ({e}), falling back to full-file scan for {gene}"
        )
        return extract_cyp_variants(vcf_path, gene, sample_limit=1)


def _parse_svtype(info: str) -> Optional[str]:
    """
    Parse INFO field for SVTYPE (structural variant type).
    Returns 'DEL', 'DUP', or None.
    Standard VCF: SVTYPE=DEL, SVTYPE=DUP, SVTYPE=DUP:TANDEM, SVTYPE=CNV.
    """
    if not info:
        return None
    info_upper = info.upper()
    for part in info.replace(";", " ").split():
        if "=" in part:
            k, v = part.split("=", 1)
            if k.upper() == "SVTYPE":
                v = v.upper()
                if v == "DEL" or v.startswith("DEL"):
                    return "DEL"
                if v == "DUP" or v.startswith("DUP") or v == "CNV":
                    return "DUP"  # CNV can be gain; treat as DUP for CYP2D6
                return None
    return None


def _parse_cnv_copy_number(info: str) -> Optional[int]:
    """
    Best-effort extraction of copy number from VCF INFO.
    Common patterns include CN=0/1/2/3... on CNV/SV records.
    """
    import re

    if not info:
        return None
    m = re.search(r"(?:^|;)CN=([0-9]+)(?:;|$)", info)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _cnv_allele_to_star(
    gene: str,
    cnv_type: str,
    other_alleles: List[str],
    copy_number: Optional[int] = None,
) -> str:
    """
    Map CNV marker to PharmVar-style star allele for CYP2D6.

    Resolution logic (v1 heuristic — not Cyrius/Stargazer level):
    - DEL: gene deletion, star allele *5
      - CN=0: both copies deleted → *5/*5 diplotype
      - CN=1: one copy deleted → *5/[SNP allele]
    - DUP: gene duplication, expressed as allele×copy_count
      - CN=3: one extra copy → [allele]x2 (e.g. *1x2 or *2x2)
      - CN=4: two extra copies → [allele]x3
      - CN≥5: ultrarapid pattern → [allele]xN

    SNP allele integration: if *2 is among detected SNP alleles, the
    duplicated allele is annotated as *2xN rather than *1xN.
    """
    dominant_snp = "*1"
    for candidate in ("*2", "*4", "*10", "*17", "*41"):
        if candidate in other_alleles:
            dominant_snp = candidate
            break

    if cnv_type == "DEL":
        cn = copy_number if copy_number is not None else 0
        if cn == 0:
            return "*5"
        return "*5"

    if cnv_type in ("DUP", "CNV"):
        cn = copy_number if copy_number is not None else 3
        if cn <= 2:
            return dominant_snp
        extra_copies = cn - 1
        if extra_copies == 2:
            return f"{dominant_snp}x2"
        if extra_copies == 3:
            return f"{dominant_snp}x3"
        return f"{dominant_snp}xN"

    return f"{dominant_snp}xN"


def _resolve_cyp2d6_diplotype(
    snp_alleles: List[str],
    cnv_type: Optional[str],
    copy_number: int,
) -> str:
    """
    Build a PharmVar-style diplotype string for CYP2D6 integrating SNP + CNV data.

    Rules:
    - No CNV, no SNP variants: *1/*1
    - No CNV, SNP variants: sorted diplotype from SNP alleles
    - DEL (CN=0): *5/*5 (ultra-poor)
    - DEL (CN=1): *5/[dominant SNP allele or *1]
    - DUP (CN=3): *1/*[dominant]x2 or *[dom]x2/*1
    - DUP (CN≥4): *[dom]x[N]/*[secondary]
    """
    dominant = next(
        (a for a in ("*2", "*4", "*10", "*17", "*41") if a in snp_alleles),
        "*1",
    )

    if cnv_type is None:
        if not snp_alleles:
            return "*1/*1"
        alleles = sorted(snp_alleles)[:2]
        if len(alleles) == 1:
            return f"*1/{alleles[0]}"
        return "/".join(alleles)

    if cnv_type == "DEL":
        cn = copy_number
        if cn == 0:
            return "*5/*5"
        snp_part = dominant if snp_alleles else "*1"
        return f"*5/{snp_part}"

    if cnv_type in ("DUP", "CNV"):
        cn = copy_number
        dup_allele = _cnv_allele_to_star("CYP2D6", "DUP", snp_alleles, cn)
        other = (
            dominant if snp_alleles and dominant != dup_allele.split("x")[0] else "*1"
        )
        return f"{other}/{dup_allele}"

    return "*1/*1"


def infer_metabolizer_status(
    variants: List[Dict], sample_id: str, gene: str = "CYP2D6"
) -> str:
    """
    Infer CYP metabolizer status using Targeted Variant Lookup (Dictionary-Based Genotyping).

    This method replaces naive variant counting with targeted lookup of Tier 1 Clinical Variants
    (CPIC Level A) based on specific rsIDs. Only variants known to affect enzyme function are
    considered, filtering out synonymous mutations and intronic variants.

    Based on CPIC/PharmVar guidelines:
    - AS = 0: Poor Metabolizer
    - AS = 0.5-1.0: Intermediate Metabolizer
    - AS = 1.5-2.0: Extensive Metabolizer (Normal)
    - AS > 2.0: Ultra-Rapid Metabolizer

    Args:
        variants: List of variant dictionaries from VCF
        sample_id: Sample ID to analyze
        gene: Gene name (CYP2D6, CYP2C19, CYP2C9)

    Returns:
        Metabolizer status: 'extensive_metabolizer', 'intermediate_metabolizer',
                           'poor_metabolizer', or 'ultra_rapid_metabolizer'
    """
    if not variants:
        return "extensive_metabolizer"  # Default: wild-type (*1/*1)

    # Get critical variants database for this gene
    gene_db = VARIANT_DB.get(gene, {})
    if not gene_db:
        # Fallback: if gene not in database, assume normal
        return "extensive_metabolizer"

    # Track found alleles and structural variants
    found_alleles = []
    copy_number = 2  # Default diploid
    has_deletion = False

    # Scan variants for critical rsIDs
    for variant in variants:
        if sample_id not in variant.get("samples", {}):
            continue

        genotype = variant["samples"][sample_id]
        rsid = variant.get("id", "")

        # Skip if genotype is homozygous reference (0/0) or missing
        if genotype in ["0/0", "0|0", ".", "./.", ".|."]:
            continue

        # Check for structural variants (deletions/duplications)
        # CNV detection restricted to CYP2D6 — the only gene where CNVs
        # are clinically actionable in the current panel
        alt = str(variant.get("alt", ""))
        info = str(variant.get("info", ""))
        svtype = _parse_svtype(info)
        cn = _parse_cnv_copy_number(info)

        if gene == "CYP2D6":
            if "<DEL>" in alt or svtype == "DEL":
                has_deletion = True
                found_alleles.append(f"{gene}_DEL")
                copy_number = 0 if cn is None else cn
                continue
            if "<DUP>" in alt or svtype == "DUP" or svtype == "CNV":
                # Prefer explicit CN if available; otherwise assume single duplication (3 copies total)
                copy_number = 3 if cn is None else cn
                found_alleles.append(f"{gene}_DUP")
                continue

        # Check if this variant is in our critical variants database
        if rsid in gene_db:
            variant_info = gene_db[rsid]
            allele = variant_info["allele"]

            # Check if patient actually has this variant (not homozygous reference)
            # Parse genotype to determine zygosity
            is_variant = False
            is_homozygous = False

            if "/" in genotype:
                alleles = genotype.split("/")
                if len(alleles) == 2:
                    if alleles[0] != "0" and alleles[1] != "0":
                        is_variant = True
                        is_homozygous = alleles[0] == alleles[1]
                    elif alleles[0] != "0" or alleles[1] != "0":
                        is_variant = True
            elif "|" in genotype:
                alleles = genotype.split("|")
                if len(alleles) == 2:
                    if alleles[0] != "0" and alleles[1] != "0":
                        is_variant = True
                        is_homozygous = alleles[0] == alleles[1]
                    elif alleles[0] != "0" or alleles[1] != "0":
                        is_variant = True

            if is_variant:
                found_alleles.append(str(allele))
                logger.debug(
                    f"Found Critical Variant: {rsid} ({allele}) - {variant_info['impact']} - {variant_info['name']}"
                )

    # Use variant_db function to predict phenotype based on found alleles
    phenotype = get_phenotype_prediction(gene, found_alleles, copy_number)

    return phenotype


def infer_metabolizer_status_with_alleles(
    variants: List[Dict], sample_id: str, gene: str = "CYP2D6"
) -> Dict:
    """
    Infer metabolizer status and return allele-level interpretation for transparency.
    Returns phenotype, called alleles, allele call string (e.g. *1/*4), and PharmVar-style interpretations.
    """
    result = {
        "phenotype": "extensive_metabolizer",
        "alleles": [],
        "allele_call": "",
        "interpretation": [],
        "copy_number": 2,
    }
    if not variants:
        result["allele_call"] = "*1/*1"
        result["interpretation"] = [f"{gene}*1: Normal function (wild-type)"]
        return result

    gene_db = VARIANT_DB.get(gene, {})
    if not gene_db:
        return result

    found_alleles: List[str] = []
    copy_number = 2
    has_deletion = False

    for variant in variants:
        if sample_id not in variant.get("samples", {}):
            continue
        genotype = variant["samples"][sample_id]
        rsid = variant.get("id", "")
        if genotype in ["0/0", "0|0", ".", "./.", ".|."]:
            continue
        alt = str(variant.get("alt", ""))
        info = str(variant.get("info", ""))
        svtype = _parse_svtype(info)
        cn = _parse_cnv_copy_number(info)
        # CNV detection restricted to CYP2D6
        if gene == "CYP2D6":
            if "<DEL>" in alt or svtype == "DEL":
                has_deletion = True
                found_alleles.append(f"{gene}_DEL")
                copy_number = 0 if cn is None else cn
                continue
            if "<DUP>" in alt or svtype == "DUP" or svtype == "CNV":
                copy_number = 3 if cn is None else cn
                found_alleles.append(f"{gene}_DUP")
                continue
        if rsid in gene_db:
            variant_info = gene_db[rsid]
            allele = variant_info["allele"]
            is_variant = False
            if "/" in genotype:
                alleles = genotype.split("/")
                if len(alleles) == 2 and (alleles[0] != "0" or alleles[1] != "0"):
                    is_variant = True
            elif "|" in genotype:
                alleles = genotype.split("|")
                if len(alleles) == 2 and (alleles[0] != "0" or alleles[1] != "0"):
                    is_variant = True
            if is_variant:
                found_alleles.append(str(allele))

    result["phenotype"] = get_phenotype_prediction(gene, found_alleles, copy_number)
    result["alleles"] = found_alleles
    result["copy_number"] = copy_number

    if not found_alleles:
        result["allele_call"] = "*1/*1"
        result["interpretation"] = [f"{gene}*1: Normal function (wild-type)"]
    else:
        snp_alleles = [a for a in found_alleles if "_DEL" not in a and "_DUP" not in a]
        has_del = any(f"{gene}_DEL" in str(a) for a in found_alleles)
        has_dup = any(f"{gene}_DUP" in str(a) for a in found_alleles)

        if gene == "CYP2D6" and (has_del or has_dup):
            cnv_type: Optional[str] = "DEL" if has_del else "DUP"
            result["allele_call"] = _resolve_cyp2d6_diplotype(
                snp_alleles, cnv_type, copy_number
            )
            cnv_star = _cnv_allele_to_star(gene, cnv_type, snp_alleles, copy_number)
            cn_note = (
                f"CYP2D6 copy number CN={copy_number}: {result['allele_call']} "
                f"({'Homozygous deletion (ultra-poor)' if cnv_type == 'DEL' and copy_number == 0 else cnv_star}). "
                "Resolution: v1 heuristic (SNP+CNV integration). "
                "For clinical use, confirm with Cyrius or Stargazer CNV caller."
            )
        else:
            display_alleles: List[str] = []
            for a in found_alleles:
                if f"{gene}_DEL" in str(a):
                    display_alleles.append("*5")
                elif f"{gene}_DUP" in str(a):
                    display_alleles.append(
                        _cnv_allele_to_star(gene, "DUP", snp_alleles, copy_number)
                    )
                else:
                    display_alleles.append(a)
            result["allele_call"] = "/".join(sorted(set(display_alleles)))
            cn_note = None

        result["interpretation"] = get_allele_interpretation(gene, found_alleles)
        if gene == "CYP2D6" and copy_number != 2:
            interp_obj = result.get("interpretation") or []
            base_interp = (
                [str(x) for x in interp_obj] if isinstance(interp_obj, list) else []
            )
            notes = [
                f"CYP2D6 copy number inferred from SV/CNV record: CN={copy_number}"
            ]
            if "cn_note" in dir() and cn_note:
                notes.append(cn_note)
            result["interpretation"] = base_interp + notes
    return result


def _variants_to_genotype_map(
    variants: List[Dict], sample_id: str
) -> Dict[str, Tuple[str, str, str]]:
    """Build rsid -> (ref, alt, gt) from VCF variant list for one sample."""
    out: Dict[str, Tuple[str, str, str]] = {}
    for v in variants:
        rsid = v.get("id") or v.get("rsid", "")
        if (
            not rsid
            or rsid.startswith("CYP")
            or "DEL" in str(rsid)
            or "DUP" in str(rsid)
        ):
            continue
        ref = str(v.get("ref", ""))
        alt = str(v.get("alt", ""))
        if not ref:
            continue
        if "," in alt:
            alt = alt.split(",")[0]
        samples = v.get("samples", {})
        gt = samples.get(sample_id, "0/0")
        if not gt or gt in (".", "./.", ".|."):
            continue
        out[rsid] = (ref, alt, gt)
    return out


def _has_alt_allele(var_map: Dict[str, Tuple[str, str, str]], rsid: str) -> bool:
    """Return True if genotype indicates >=1 ALT allele for the rsid."""
    if rsid not in var_map:
        return False
    _ref, _alt, gt = var_map.get(rsid, ("", "", "0/0"))
    try:
        dosage = int(alt_dosage(str(gt)))
        return dosage > 0
    except Exception:
        return False


def _chrom_key_for_gene(gene: str) -> Optional[str]:
    """Return VCF chromosome key for a gene (e.g. CYP2D6 -> chr22)."""
    loc = CYP_GENE_LOCATIONS.get(gene)
    if not loc:
        return None
    c = str(loc["chrom"]).upper()
    if c == "X" or c == "Y":
        return f"chr{c}"
    try:
        return f"chr{int(c)}"
    except (TypeError, ValueError):
        return None


def _is_valid_vcf_path(path: Optional[str]) -> bool:
    """Return True if path is a valid VCF path (local file exists, S3 URL, or HTTPS URL)."""
    if not path:
        return False
    if path.startswith("s3://"):
        return True
    if path.startswith("https://") or path.startswith("http://"):
        return True
    return os.path.exists(path)


# ---------------------------------------------------------------------------
# 1000 Genomes AWS Open Data HTTPS streaming helpers
# ---------------------------------------------------------------------------

_1000G_HTTPS_BASE = "https://1000genomes.s3.amazonaws.com"
_1000G_PHASE3_PREFIX = "release/20130502"


def get_1000genomes_streaming_url(chrom: str) -> str:
    """
    Return the HTTPS streaming URL for a 1000 Genomes Phase 3 VCF chromosome.
    No download required — tabix streams via HTTP range requests.
    This dataset is part of the AWS Open Data Program (zero egress cost in us-east-1).
    """
    c = chrom.lower().replace("chr", "")
    key = f"{_1000G_PHASE3_PREFIX}/ALL.chr{c}.phase3_shapeit2_mvncall_integrated_v5a.20130502.genotypes.vcf.gz"
    return f"{_1000G_HTTPS_BASE}/{key}"


def get_1000genomes_streaming_paths(
    chromosomes: Optional[List[str]] = None,
) -> Dict[str, str]:
    """
    Return a chromosome -> HTTPS streaming URL map for 1000 Genomes.
    Default chromosomes cover all 15 Tier-1 pharmacogenomic genes:
      chr22: CYP2D6, GSTT1
      chr10: CYP2C19, CYP2C9
      chr7:  CYP3A4, CYP3A5
      chr15: CYP1A2
      chr19: CYP2B6
      chr8:  NAT2
      chr2:  UGT1A1
      chr12: SLCO1B1
      chr16: VKORC1
      chr6:  TPMT, HLA_B5701, HLA_B1502
      chr1:  DPYD, GSTM1
    Streaming is via HTTPS tabix range requests — no local download required.
    This dataset is part of the AWS Open Data Program (zero egress cost in us-east-1).
    """
    default_chroms = [
        "chr22",
        "chr10",
        "chr7",
        "chr15",
        "chr19",
        "chr8",
        "chr2",
        "chr12",
        "chr16",
        "chr6",
        "chr1",
    ]
    chroms = chromosomes or default_chroms
    return {c: get_1000genomes_streaming_url(c) for c in chroms}


def extract_variants_with_tabix_retry(
    vcf_path: str, gene: str, max_retries: int = 3, backoff_base: float = 1.5
) -> List[Dict]:
    """
    Wrapper around extract_variants_with_tabix with exponential backoff retry.
    Needed for HTTPS range-request paths that may experience transient failures.
    """
    import time as _time

    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            return extract_variants_with_tabix(vcf_path, gene)
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                sleep_s = backoff_base**attempt
                logger.warning(
                    f"tabix attempt {attempt + 1}/{max_retries} failed for {gene} "
                    f"({vcf_path}): {exc}. Retrying in {sleep_s:.1f}s…"
                )
                _time.sleep(sleep_s)
    logger.error(f"All {max_retries} tabix attempts failed for {gene}: {last_exc}")
    return []


def probe_1000genomes_streaming(timeout: int = 8) -> Dict[str, object]:
    """
    Probe the 1000 Genomes HTTPS endpoint with a HEAD request.
    Returns latency (ms), availability, and the tested URL.
    Used by /vcf-datasets/streaming-status API endpoint.
    """
    import time as _time

    probe_url = get_1000genomes_streaming_url("chr22")
    result: Dict[str, object] = {
        "available": False,
        "latency_ms": None,
        "url": probe_url,
        "source": "AWS Open Data Program (1000 Genomes Phase 3)",
        "streaming_mode": "HTTPS tabix range requests (no local download)",
        "cost": "$0 — AWS Open Data Program eliminates egress charges",
    }
    try:
        import urllib.request

        t0 = _time.monotonic()
        req = urllib.request.Request(probe_url, method="HEAD")
        req.add_header("User-Agent", "SynthaTrial/1.0 streaming-probe")
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            latency = int((_time.monotonic() - t0) * 1000)
            result["available"] = resp.status == 200
            result["latency_ms"] = latency
            result["http_status"] = resp.status
    except Exception as exc:
        result["error"] = str(exc)
    return result


def generate_patient_profile_from_vcf(
    vcf_path: str,
    sample_id: str,
    drug_name: Optional[str] = None,
    age: Optional[int] = None,
    conditions: Optional[List[str]] = None,
    lifestyle: Optional[Dict[str, str]] = None,
    vcf_path_chr10: Optional[str] = None,
    vcf_paths_by_chrom: Optional[Dict[str, str]] = None,
) -> str:
    """
    Generate a synthetic patient profile from VCF data.
    Uses chr22 (CYP2D6), chr10 (CYP2C19, CYP2C9), chr2 (UGT1A1), chr12 (SLCO1B1)
    when the corresponding VCF files are provided via vcf_paths_by_chrom or legacy args.
    When drug_name is a statin, appends deterministic Statin PGx (SLCO1B1) line (CPIC-style).

    Args:
        vcf_path: Path to primary VCF (chr22 for CYP2D6); used if vcf_paths_by_chrom not set.
        sample_id: Sample ID from VCF file
        age: Patient age (random if not provided)
        conditions: List of medical conditions
        lifestyle: Dictionary with 'alcohol' and 'smoking' keys
        vcf_path_chr10: Optional path to chr10 (CYP2C9/CYP2C19); used if vcf_paths_by_chrom not set.
        vcf_paths_by_chrom: Optional dict chromosome -> path.
        drug_name: Optional drug name; if a statin, Statin PGx (SLCO1B1) line is appended.
    Returns:
        Formatted patient profile string
    """
    import random

    # Build chromosome -> path map: prefer vcf_paths_by_chrom, else legacy args
    # Accept both local paths (os.path.exists) and S3 URLs (s3://)
    if vcf_paths_by_chrom:
        paths = {k: p for k, p in vcf_paths_by_chrom.items() if _is_valid_vcf_path(p)}
    else:
        paths = {}
        if _is_valid_vcf_path(vcf_path):
            paths["chr22"] = vcf_path
        if _is_valid_vcf_path(vcf_path_chr10):
            paths["chr10"] = vcf_path_chr10

    # --------------------------------------------
    # Drug-aware PGx triggering (CPIC-style)
    # --------------------------------------------
    triggered_genes: set = set()
    if drug_name and drug_name.strip():
        triggered_genes = set(DRUG_GENE_TRIGGERS.get(drug_name.strip().lower(), []))
    logger.info(f"Drug: {drug_name} → Triggered PGx genes: {triggered_genes}")

    # Extract variants and infer status for each profile gene from the correct chromosome VCF
    # S3 paths are downloaded to temp local file before tabix (which requires local path)
    gene_variants: Dict[str, List] = {g: [] for g in PROFILE_GENES}
    for gene in PROFILE_GENES:
        chr_key = _chrom_key_for_gene(gene)
        if not chr_key:
            continue
        vcf_file = paths.get(chr_key)
        if not vcf_file:
            continue
        try:
            local_vcf = (
                download_s3_vcf_if_needed(vcf_file)
                if vcf_file.startswith("s3://")
                else vcf_file
            )
            gene_variants[gene] = extract_variants_with_tabix(local_vcf, gene)
            if gene_variants[gene]:
                logger.info(
                    f"Extracted {len(gene_variants[gene])} {gene} variants from {chr_key}"
                )
        except Exception as e:
            logger.warning(f"Could not extract {gene} variants from {chr_key}: {e}")

    # Infer status and allele-level interpretation per gene (for transparency)
    # CYP2C19: use curated PharmVar/CPIC data when present (deterministic, guideline-derived)
    def _status_and_alleles(
        gene: str, default: str = "extensive_metabolizer"
    ) -> Tuple[str, Optional[str], List[str]]:
        if gene == "SLCO1B1":
            default = "average_function"
        if not gene_variants[gene]:
            return default, None, []
        var_map = _variants_to_genotype_map(gene_variants[gene], sample_id)
        # HLA-B*57:01 proxy (rs2395029). This is a safety flag used for abacavir only.
        if gene == "HLA_B5701":
            if not var_map:
                return "negative", None, []
            pos = _has_alt_allele(var_map, "rs2395029")
            if pos:
                return (
                    "positive",
                    "POS",
                    [
                        "HLA-B*57:01 proxy (rs2395029): POSITIVE (abacavir hypersensitivity risk)"
                    ],
                )
            return ("negative", "NEG", ["HLA-B*57:01 proxy (rs2395029): negative"])
        # HLA-B*15:02 proxy (rs3909184). SJS/TEN risk flag for carbamazepine class.
        if gene == "HLA_B1502":
            if not var_map:
                return "negative", None, []
            pos = _has_alt_allele(var_map, "rs3909184")
            if pos:
                return (
                    "positive",
                    "POS",
                    [
                        "HLA-B*15:02 proxy (rs3909184): POSITIVE (carbamazepine-class SJS/TEN risk)"
                    ],
                )
            return ("negative", "NEG", ["HLA-B*15:02 proxy (rs3909184): negative"])
        # VKORC1: genotype at rs9923231 (GG/GA/AA), diploid-correct from GT
        if gene == "VKORC1" and var_map:
            ref, alt, gt = var_map.get("rs9923231", (None, None, None))
            if ref and alt and gt:
                dosage = alt_dosage(gt)
                if dosage == 0:
                    geno = f"{ref}{ref}"
                elif dosage == 1:
                    geno = f"{ref}{alt}"
                elif dosage == 2:
                    geno = f"{alt}{alt}"
                else:
                    geno = "Unknown"
                return (
                    f"vkorc1_{geno.lower()}",
                    geno,
                    [f"VKORC1 rs9923231 genotype={gt} → {geno}"],
                )
            return default, None, []
        # SLCO1B1: deterministic rs4149056 (c.521T>C) → TT/TC/CC, phenotype.
        # Do not attempt generic star-allele calling for SLCO1B1.
        if gene == "SLCO1B1":
            if not var_map or "rs4149056" not in var_map:
                return default, None, []
            try:
                slco_result = interpret_slco1b1_from_vcf(var_map)
                if slco_result:
                    phen_raw = slco_result["phenotype"]
                    if "Normal" in phen_raw or "low" in phen_raw.lower():
                        phen_norm = "average_function"
                    elif "Decreased" in phen_raw or "moderate" in phen_raw.lower():
                        phen_norm = "decreased_function"
                    elif "Poor" in phen_raw or "high" in phen_raw.lower():
                        phen_norm = "poor_function"
                    else:
                        phen_norm = "average_function"
                    return (
                        phen_norm,
                        slco_result["genotype"],
                        [f"SLCO1B1 rs4149056 {slco_result['genotype']} → {phen_raw}"],
                    )
            except Exception as e:
                logger.debug(f"SLCO1B1 interpretation skipped: {e}")
            return default, None, []
        # Try CPIC/PharmVar path first for genes with data/pgx files (e.g. CYP2C19)
        try:
            if var_map:
                cpic_result = call_gene_from_variants(gene, var_map)
                if cpic_result:
                    phen = cpic_result["phenotype_normalized"]
                    diplo = cpic_result["diplotype"]
                    vtag = cpic_result.get("verification_status", "")
                    interp = [
                        f"{gene} {diplo} → {cpic_result['phenotype_display']} (CPIC)"
                        + (f" [{vtag}]" if vtag else "")
                    ]
                    return phen, diplo, interp
        except Exception as e:
            logger.debug(f"CPIC/PharmVar path skipped for {gene}: {e}")
        info = infer_metabolizer_status_with_alleles(
            gene_variants[gene], sample_id, gene=gene
        )
        return (
            info["phenotype"],
            info.get("allele_call"),
            info.get("interpretation", []),
        )

    genetics_parts = []
    for gene in PROFILE_GENES:
        status, allele_call, interpretation = _status_and_alleles(gene)

        # --------------------------------------------
        # CPIC-style gating: only show drug-relevant genes
        # --------------------------------------------
        if gene == "SLCO1B1" and gene not in triggered_genes:
            continue
        if gene in ("CYP2C9", "VKORC1") and gene not in triggered_genes:
            continue
        if gene == "CYP2C19" and drug_name and gene not in triggered_genes:
            continue
        if gene in ("TPMT", "DPYD") and drug_name and gene not in triggered_genes:
            continue
        if gene == "HLA_B5701" and drug_name and gene not in triggered_genes:
            continue
        if gene == "HLA_B1502" and drug_name and gene not in triggered_genes:
            continue

        s = status
        if gene == "VKORC1" and allele_call:
            genetics_parts.append(f"VKORC1 {allele_call}")
            continue
        if s == "extensive_metabolizer" and gene != "SLCO1B1":
            continue
        if gene == "SLCO1B1" and s == "average_function":
            continue
        term = s.replace("_", " ").title()
        if gene == "SLCO1B1":
            term = term.replace("Metabolizer", "Function")
        if gene == "HLA_B5701":
            label = "HLA-B*57:01"
            if s == "positive":
                genetics_parts.append(
                    f"{label} Positive (Abacavir hypersensitivity risk)"
                )
            else:
                genetics_parts.append(f"{label} Negative")
            continue
        if gene == "HLA_B1502":
            label = "HLA-B*15:02"
            if s == "positive":
                genetics_parts.append(
                    f"{label} Positive (Carbamazepine-class SJS/TEN risk — proxy)"
                )
            else:
                genetics_parts.append(f"{label} Negative (proxy)")
            continue
        # Include allele call when available (e.g. "CYP2D6 *1/*4 (Poor Metabolizer)")
        if allele_call and allele_call != "*1/*1":
            genetics_parts.append(f"{gene} {allele_call} ({term})")
        else:
            genetics_parts.append(f"{gene} {term}")

    # Warfarin PGx: merge CYP2C9 (chr10) + VKORC1 (chr16) variants and add deterministic interpretation
    warfarin_var_map: Dict[str, Tuple[str, str, str]] = {}
    for g in ("CYP2C9", "VKORC1"):
        if gene_variants.get(g):
            warfarin_var_map.update(
                _variants_to_genotype_map(gene_variants[g], sample_id)
            )
    if (
        "VKORC1" in triggered_genes
        and warfarin_var_map
        and any(rsid in warfarin_var_map for rsid in WARFARIN_RSIDS)
    ):
        try:
            warfarin_result = interpret_warfarin_from_vcf(warfarin_var_map)
            if warfarin_result:
                genetics_parts.append(
                    f"Warfarin PGx: CYP2C9 {warfarin_result['CYP2C9']} + VKORC1 {warfarin_result['VKORC1']} → {warfarin_result['recommendation']}"
                )
        except Exception as e:
            logger.debug(f"Warfarin interpretation skipped: {e}")

    # --------------------------------------------
    # CPIC-grade Statin PGx: SLCO1B1
    # --------------------------------------------
    if "SLCO1B1" in triggered_genes and drug_name:
        slco_var_map: Dict[str, Tuple[str, str, str]] = {}
        if gene_variants.get("SLCO1B1"):
            slco_var_map.update(
                _variants_to_genotype_map(gene_variants["SLCO1B1"], sample_id)
            )
        if slco_var_map and "rs4149056" in slco_var_map:
            try:
                ref, alt, gt = slco_var_map["rs4149056"]
                alleles = _genotype_to_alleles(ref, alt, gt)
                genotype = "".join(sorted(alleles))
                slco_result = interpret_slco1b1(genotype, drug_name)
                if slco_result:
                    genetics_parts.append(
                        f"Statin PGx (CPIC): SLCO1B1 {genotype} → "
                        f"{slco_result['phenotype']} ({slco_result['risk']}) | "
                        f"{slco_result['recommendation']}"
                    )
            except Exception as e:
                logger.debug(f"SLCO1B1 interpretation skipped: {e}")

    # --------------------------------------------
    # CPIC-grade TPMT PGx: Thiopurines
    # --------------------------------------------
    if "TPMT" in triggered_genes and drug_name:
        tpmt_var_map: Dict[str, Tuple[str, str, str]] = {}
        if gene_variants.get("TPMT"):
            tpmt_var_map.update(
                _variants_to_genotype_map(gene_variants["TPMT"], sample_id)
            )
        if tpmt_var_map:
            try:
                tpmt_result = interpret_tpmt_from_vcf(tpmt_var_map)
                if tpmt_result:
                    genetics_parts.append(
                        f"TPMT PGx: {tpmt_result['diplotype']} → {tpmt_result['phenotype']}"
                    )
            except Exception as e:
                logger.debug(f"TPMT interpretation skipped: {e}")

    # --------------------------------------------
    # CPIC-grade DPYD PGx: Fluoropyrimidines
    # --------------------------------------------
    if "DPYD" in triggered_genes and drug_name:
        dpyd_var_map: Dict[str, Tuple[str, str, str]] = {}
        if gene_variants.get("DPYD"):
            dpyd_var_map.update(
                _variants_to_genotype_map(gene_variants["DPYD"], sample_id)
            )
        if dpyd_var_map:
            try:
                dpyd_result = interpret_dpyd_from_vcf(dpyd_var_map)
                if dpyd_result:
                    genetics_parts.append(
                        f"DPYD PGx: {dpyd_result['diplotype']} → {dpyd_result['phenotype']}"
                    )
            except Exception as e:
                logger.debug(f"DPYD interpretation skipped: {e}")

    # --------------------------------------------
    # CPIC-grade CYP2B6 PGx: Efavirenz, Bupropion
    # --------------------------------------------
    if "CYP2B6" in triggered_genes and drug_name:
        cyp2b6_var_map: Dict[str, Tuple[str, str, str]] = {}
        if gene_variants.get("CYP2B6"):
            cyp2b6_var_map.update(
                _variants_to_genotype_map(gene_variants["CYP2B6"], sample_id)
            )
        if cyp2b6_var_map:
            try:
                cyp2b6_result = interpret_cyp2b6_from_vcf(cyp2b6_var_map)
                if (
                    cyp2b6_result
                    and cyp2b6_result.get("phenotype") != "Normal Metabolizer"
                ):
                    genetics_parts.append(
                        f"CYP2B6 PGx: {cyp2b6_result['diplotype']} → {cyp2b6_result['phenotype']} "
                        f"[CPIC Level A — {drug_name}]"
                    )
            except Exception as e:
                logger.debug(f"CYP2B6 interpretation skipped: {e}")

    # --------------------------------------------
    # CYP1A2 PGx: Clozapine, Theophylline
    # --------------------------------------------
    if "CYP1A2" in triggered_genes and drug_name:
        cyp1a2_var_map: Dict[str, Tuple[str, str, str]] = {}
        if gene_variants.get("CYP1A2"):
            cyp1a2_var_map.update(
                _variants_to_genotype_map(gene_variants["CYP1A2"], sample_id)
            )
        smoking_status = (lifestyle or {}).get("smoking", "unknown")
        if cyp1a2_var_map:
            try:
                cyp1a2_result = interpret_cyp1a2_from_vcf(
                    cyp1a2_var_map, smoking_status=smoking_status
                )
                if cyp1a2_result and cyp1a2_result.get("phenotype") not in (
                    "Normal Metabolizer",
                    None,
                ):
                    genetics_parts.append(
                        f"CYP1A2 PGx: {cyp1a2_result['diplotype']} → {cyp1a2_result['phenotype']}"
                    )
            except Exception as e:
                logger.debug(f"CYP1A2 interpretation skipped: {e}")

    # --------------------------------------------
    # CYP3A5 PGx: Tacrolimus (Transplant)
    # --------------------------------------------
    if "CYP3A5" in triggered_genes and drug_name:
        cyp3a5_var_map: Dict[str, Tuple[str, str, str]] = {}
        if gene_variants.get("CYP3A5"):
            cyp3a5_var_map.update(
                _variants_to_genotype_map(gene_variants["CYP3A5"], sample_id)
            )
        if cyp3a5_var_map:
            try:
                cyp3a5_result = interpret_cyp3a5_from_vcf(cyp3a5_var_map)
                if cyp3a5_result:
                    genetics_parts.append(
                        f"CYP3A5 PGx: {cyp3a5_result['diplotype']} → {cyp3a5_result['phenotype']} "
                        f"[CPIC Level A]"
                    )
            except Exception as e:
                logger.debug(f"CYP3A5 interpretation skipped: {e}")

    # --------------------------------------------
    # NAT2 PGx: Isoniazid (TB), Hydralazine
    # --------------------------------------------
    if "NAT2" in triggered_genes and drug_name:
        nat2_var_map: Dict[str, Tuple[str, str, str]] = {}
        if gene_variants.get("NAT2"):
            nat2_var_map.update(
                _variants_to_genotype_map(gene_variants["NAT2"], sample_id)
            )
        if nat2_var_map:
            try:
                nat2_result = interpret_nat2_from_vcf(nat2_var_map)
                if nat2_result and nat2_result.get("phenotype") != "Rapid Acetylator":
                    genetics_parts.append(
                        f"NAT2 PGx: {nat2_result['diplotype']} → {nat2_result['phenotype']} "
                        f"[CPIC Level A — {drug_name}]"
                    )
            except Exception as e:
                logger.debug(f"NAT2 interpretation skipped: {e}")

    # --------------------------------------------
    # GSTM1/GSTT1 PGx: Platinum chemotherapy, Busulfan
    # --------------------------------------------
    if any(g in triggered_genes for g in ("GSTM1", "GSTT1")) and drug_name:
        gst_var_map: Dict[str, Tuple[str, str, str]] = {}
        for gst_gene in ("GSTM1", "GSTT1"):
            if gene_variants.get(gst_gene):
                gst_var_map.update(
                    _variants_to_genotype_map(gene_variants[gst_gene], sample_id)
                )
        if gst_var_map:
            try:
                gst_results = interpret_gst_from_vcf(gst_var_map, drug_name=drug_name)
                for gst_gene in ("GSTM1", "GSTT1"):
                    r = gst_results.get(gst_gene, {})
                    if r and r.get("phenotype") not in ("Normal Function", None):
                        genetics_parts.append(
                            f"{gst_gene} PGx: {r['genotype']} → {r['phenotype']}"
                        )
            except Exception as e:
                logger.debug(f"GST interpretation skipped: {e}")

    if not genetics_parts:
        genetics_text = "No variant metabolizer status detected"
    else:
        genetics_text = ", ".join(genetics_parts)

    # Add structured gene phenotype lines for downstream PGx parsing (e.g., api.py /analyze).
    # Keep the single-line Genetics summary for readability in the UI.
    structured_lines: List[str] = []
    if drug_name:
        triggered = set(DRUG_GENE_TRIGGERS.get(drug_name.strip().lower(), []))
    else:
        triggered = set()
    for gene in ("TPMT", "DPYD"):
        if triggered and gene not in triggered:
            continue
        status, _allele_call, _interp = _status_and_alleles(gene)
        if status == "extensive_metabolizer":
            continue
        structured_lines.append(f"- {gene}: {status.replace('_', ' ').title()}")

    # HLA proxy lines: emit when the drug triggers them AND variant data was loaded,
    # so api.py _extract_gene_pheno can find "HLA_B5701:" / "HLA_B1502:" in the profile.
    for hla_gene in ("HLA_B5701", "HLA_B1502"):
        if triggered and hla_gene not in triggered:
            continue
        if hla_gene not in gene_variants:
            structured_lines.append(
                f"- {hla_gene}: Unknown (no VCF data for this locus)"
            )
            continue
        hla_status, _hla_allele, _hla_interp = _status_and_alleles(hla_gene)
        structured_lines.append(f"- {hla_gene}: {hla_status.replace('_', ' ').title()}")

    # Default values
    if age is None:
        age = random.randint(25, 75)  # nosec B311 - synthetic demo only
    if conditions is None:
        conditions = []
    if lifestyle is None:
        lifestyle = {"alcohol": "Moderate", "smoking": "Non-smoker"}

    conditions_text = ", ".join(conditions) if conditions else "None"
    lifestyle_text = f"Alcohol: {lifestyle.get('alcohol', 'Moderate')}, Smoking: {lifestyle.get('smoking', 'Non-smoker')}"

    profile = f"""ID: {sample_id}
Age: {age}
Genetics: {genetics_text}
{chr(10).join(structured_lines) if structured_lines else ""}
Conditions: {conditions_text}
Lifestyle: {lifestyle_text}
Source: 1000 Genomes Project VCF"""

    return profile


def generate_patient_profile_multi_chromosome(
    vcf_path_chr22: str,
    vcf_path_chr10: Optional[str],
    sample_id: str,
    age: Optional[int] = None,
    conditions: Optional[List[str]] = None,
    lifestyle: Optional[Dict[str, str]] = None,
    vcf_paths_by_chrom: Optional[Dict[str, str]] = None,
) -> str:
    """
    Generate patient profile from multiple VCF files.
    When vcf_paths_by_chrom is provided, uses it for all chromosomes (chr2, chr10, chr12, chr22, etc.).
    """
    return generate_patient_profile_from_vcf(
        vcf_path_chr22,
        sample_id,
        age=age,
        conditions=conditions,
        lifestyle=lifestyle,
        vcf_path_chr10=vcf_path_chr10,
        vcf_paths_by_chrom=vcf_paths_by_chrom,
    )


def get_sample_ids_from_vcf(vcf_path: str, limit: Optional[int] = 10) -> List[str]:
    """
    Get list of sample IDs from VCF file header.
    Supports both local paths and S3 URLs (downloads to temp when needed).
    """
    if not vcf_path:
        return []
    # Remote HTTP(S) VCFs: use tabix header read (supports range requests).
    if vcf_path.startswith("http://") or vcf_path.startswith("https://"):
        try:
            result = subprocess.run(  # nosec B603 B607
                ["tabix", "-H", vcf_path],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            for line in result.stdout.splitlines():
                if line.startswith("#CHROM"):
                    header_fields = line.strip().split("\t")
                    if len(header_fields) > 9:
                        remote_samples: List[str] = header_fields[9:]
                        return remote_samples[:limit] if limit else remote_samples
            return []
        except Exception as e:
            logger.warning(f"Error reading remote VCF header via tabix: {e}")
            return []
    local_path = (
        download_s3_vcf_if_needed(vcf_path)
        if vcf_path.startswith("s3://")
        else vcf_path
    )
    open_func = cast(
        Callable[..., Any],
        gzip.open if local_path.endswith(".gz") else open,
    )
    mode = "rt" if local_path.endswith(".gz") else "r"

    try:
        with open_func(local_path, mode) as f:
            for line in f:
                if line.startswith("#CHROM"):
                    header_fields = line.strip().split("\t")
                    if len(header_fields) > 9:
                        samples: List[str] = header_fields[9:]
                        if limit:
                            return samples[:limit]
                        return samples
        return []
    except Exception as e:
        print(f"Error reading VCF header: {e}")
        return []


# Chromosomes supported for discovery (autosomes 1-22, X, Y).
# Order: longest token first so "chr22" matches before "chr2".
SUPPORTED_CHROMOSOMES_ORDER: Tuple[str, ...] = tuple(
    sorted(
        [f"chr{i}" for i in range(1, 23)] + ["chrX", "chrY"],
        key=lambda x: -len(x),
    )
)


def discover_vcf_paths(genomes_dir: str = "data/genomes") -> Dict[str, str]:
    """
    Discover VCF files in data/genomes and map them to chromosomes.
    Now supports both local files and S3 cloud storage.

    Accepts both short names (chr22.vcf.gz, chr10.vcf.gz) and long 1000 Genomes
    names (e.g. ALL.chr22.phase3_shapeit2_mvncall_integrated_v5a.20130502.genotypes.vcf.gz).
    Returns a dict mapping chromosome key to absolute path, e.g. {"chr22": path, "chr10": path}.
    Any chr1–chr22, chrX, chrY present in the filename is detected.
    """
    found: Dict[str, str] = {}
    vcf_source_mode = os.getenv("VCF_SOURCE_MODE", "auto").strip().lower()
    if vcf_source_mode not in ("auto", "local", "s3"):
        vcf_source_mode = "auto"

    # First try S3 if available and configured (unless forced local mode).
    if vcf_source_mode != "local" and S3_AVAILABLE:
        bucket_name = os.getenv("AWS_S3_BUCKET_GENOMIC", "synthatrial-genomic-data")
        if bucket_name and os.getenv("AWS_ACCESS_KEY_ID"):
            try:
                s3_manager = S3GenomicDataManager(bucket_name)
                if s3_manager.s3_client:
                    s3_files = s3_manager.list_vcf_files()
                    logger.info(
                        f"Found {len(s3_files)} VCF files in S3 bucket {bucket_name}"
                    )

                    for file_info in s3_files:
                        key = file_info["key"]
                        # Extract chromosome from S3 key
                        for c in SUPPORTED_CHROMOSOMES_ORDER:
                            if c in key:
                                idx = key.find(c)
                                next_char = key[idx + len(c) : idx + len(c) + 1]
                                if next_char and next_char.isdigit():
                                    continue
                                if c not in found:
                                    # Use S3 URL format for cloud access
                                    found[c] = f"s3://{bucket_name}/{key}"
                                    logger.info(f"Mapped {c} to S3: {key}")
                                break

                    if found:
                        logger.info(f"Using S3 VCF files: {list(found.keys())}")
                        return found
            except Exception as e:
                logger.warning(f"S3 VCF discovery failed, falling back to local: {e}")

    if vcf_source_mode == "s3":
        # Explicitly S3-only mode; skip local fallback.
        return {}

    # Fallback to local file discovery
    if not os.path.isdir(genomes_dir):
        return {}

    try:
        for name in os.listdir(genomes_dir):
            if not name.endswith(".vcf.gz"):
                continue
            path = os.path.join(genomes_dir, name)
            if not os.path.isfile(path):
                continue
            # Match all chrN/chrX/chrY in filename; take first that we support (longest-first)
            for c in SUPPORTED_CHROMOSOMES_ORDER:
                if c not in name:
                    continue
                idx = name.find(c)
                next_char = name[idx + len(c) : idx + len(c) + 1]
                if next_char and next_char.isdigit():
                    continue
                if c not in found:
                    found[c] = os.path.abspath(path)
                break
    except OSError as e:
        logger.warning(f"Could not list genomes dir {genomes_dir}: {e}")

    if found:
        logger.info(f"Using local VCF files: {list(found.keys())}")
        return found

    # Auto-mode: no local files found → fall back to 1000 Genomes HTTPS streaming.
    # This is zero-cost (AWS Open Data Program) and requires no local storage.
    if vcf_source_mode == "auto":
        logger.info(
            "No local VCF files found — defaulting to 1000 Genomes HTTPS streaming "
            "(AWS Open Data Program, no egress charges, tabix range requests only)."
        )
        return get_1000genomes_streaming_paths()

    return found


def discover_local_vcf_paths(genomes_dir: str = "data/genomes") -> Dict[str, str]:
    """
    Discover VCF files from local filesystem only (no S3).
    Use this for fast operations that cannot wait for S3 downloads.
    """
    found: Dict[str, str] = {}
    if not os.path.isdir(genomes_dir):
        return found
    try:
        for name in os.listdir(genomes_dir):
            if not name.endswith(".vcf.gz"):
                continue
            path = os.path.join(genomes_dir, name)
            if not os.path.isfile(path):
                continue
            for c in SUPPORTED_CHROMOSOMES_ORDER:
                if c not in name:
                    continue
                idx = name.find(c)
                next_char = name[idx + len(c) : idx + len(c) + 1]
                if next_char and next_char.isdigit():
                    continue
                if c not in found:
                    found[c] = os.path.abspath(path)
                break
    except OSError as e:
        logger.warning(f"Could not list genomes dir {genomes_dir}: {e}")
    if found:
        logger.info(f"Using local VCF files (no S3): {list(found.keys())}")
    return found


def download_s3_vcf_if_needed(s3_path: str) -> str:
    """
    Download VCF file from S3 to temporary location if needed.
    Returns local path for processing.
    """
    if not s3_path.startswith("s3://"):
        return s3_path  # Already local path

    if not S3_AVAILABLE:
        raise VCFProcessingError("S3 integration not available", vcf_path=s3_path)

    # Parse S3 URL: s3://bucket/key
    parts = s3_path[5:].split("/", 1)  # Remove s3:// prefix
    if len(parts) != 2:
        raise VCFProcessingError(f"Invalid S3 path format: {s3_path}", vcf_path=s3_path)

    bucket_name, key = parts

    try:
        # Some public buckets (e.g. AWS Open Data) require unsigned access.
        public_buckets = set(
            b.strip()
            for b in os.getenv("S3_PUBLIC_BUCKETS", "1000genomes").split(",")
            if b.strip()
        )
        if bucket_name in public_buckets:
            s3_client = boto3.client(
                "s3",
                region_name=os.getenv("AWS_REGION", "us-east-1"),
                config=BotoConfig(signature_version=UNSIGNED),
            )
        else:
            s3_manager = S3GenomicDataManager(bucket_name)
            if not s3_manager.s3_client:
                raise VCFProcessingError("S3 client not available", vcf_path=s3_path)
            s3_client = s3_manager.s3_client

        # Create temporary file
        temp_dir = tempfile.gettempdir()
        local_filename = os.path.basename(key)
        local_path = os.path.join(temp_dir, f"anukriti_{local_filename}")

        # Download from S3
        s3_client.download_file(bucket_name, key, local_path)

        if os.path.exists(local_path):
            logger.info(f"Downloaded S3 VCF to temporary location: {local_path}")
            return local_path
        else:
            raise VCFProcessingError(
                f"Failed to download S3 file: {s3_path}", vcf_path=s3_path
            )

    except Exception as e:
        logger.error(f"Error downloading S3 VCF file: {e}")
        raise VCFProcessingError(
            f"S3 download failed: {str(e)}", vcf_path=s3_path
        ) from e
