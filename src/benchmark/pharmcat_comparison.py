"""
Head-to-head comparison of Anukriti vs PharmCAT on identical VCF inputs.

Extracts PGx variants from 1000 Genomes Phase 3 VCFs (GRCh37),
lifts over to GRCh38 for PharmCAT, runs both tools, and compares results.

Requires:
- Docker (for PharmCAT: pgkb/pharmcat)
- pyliftover (pip install pyliftover)
- Local 1000 Genomes VCF files in data/genomes/
"""

from __future__ import annotations

import gzip
import json
import logging
import subprocess  # nosec B404
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# GRCh37 coordinates for PGx genes (matching vcf_processor.py)
GENE_REGIONS_GRCH37: Dict[str, Dict[str, Any]] = {
    "CYP2C19": {"chrom": "10", "start": 96522463, "end": 96612671},
    "CYP2C9": {"chrom": "10", "start": 96698415, "end": 96749148},
    "CYP2D6": {"chrom": "22", "start": 42522501, "end": 42526883},
    "UGT1A1": {"chrom": "2", "start": 234668879, "end": 234681945},
    "SLCO1B1": {"chrom": "12", "start": 21282127, "end": 21392730},
    "VKORC1": {"chrom": "16", "start": 31102163, "end": 31106946},
    "TPMT": {"chrom": "6", "start": 18128542, "end": 18155374},
    "DPYD": {"chrom": "1", "start": 97543299, "end": 97883432},
}

# Map chromosome to VCF filename pattern
CHROM_VCF_PATTERN = "ALL.chr{chrom}.phase3_shapeit2_mvncall_integrated_v5{suffix}.20130502.genotypes.vcf.gz"

# PGx rsIDs we care about (from variant_db.py)
PGX_RSIDS: Dict[str, List[str]] = {
    "CYP2C19": ["rs4244285", "rs4986893", "rs12248560", "rs28399504"],
    "CYP2C9": ["rs1799853", "rs1057910"],
    "TPMT": ["rs1800462", "rs1800460", "rs1142345"],
    "DPYD": ["rs3918290", "rs55886062", "rs67376798", "rs75017182"],
    "SLCO1B1": ["rs4149056"],
    "VKORC1": ["rs9923231"],
    "UGT1A1": ["rs8175347", "rs4148323"],
}


@dataclass
class SampleComparison:
    """Comparison result for a single sample across all genes."""

    sample_id: str
    genes: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @property
    def concordant_genes(self) -> int:
        return sum(1 for g in self.genes.values() if g.get("concordant", False))

    @property
    def total_genes(self) -> int:
        return len(self.genes)


@dataclass
class PharmCATComparisonResult:
    """Full comparison results across multiple samples."""

    samples: List[SampleComparison] = field(default_factory=list)
    pharmcat_version: str = ""
    genes_compared: List[str] = field(default_factory=list)

    @property
    def total_comparisons(self) -> int:
        return sum(s.total_genes for s in self.samples)

    @property
    def total_concordant(self) -> int:
        return sum(s.concordant_genes for s in self.samples)

    @property
    def concordance(self) -> float:
        if self.total_comparisons == 0:
            return 0.0
        return self.total_concordant / self.total_comparisons

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pharmcat_version": self.pharmcat_version,
            "genes_compared": self.genes_compared,
            "total_samples": len(self.samples),
            "total_comparisons": self.total_comparisons,
            "total_concordant": self.total_concordant,
            "concordance": round(self.concordance, 4),
            "samples": [
                {
                    "sample_id": s.sample_id,
                    "concordant": s.concordant_genes,
                    "total": s.total_genes,
                    "genes": s.genes,
                }
                for s in self.samples
            ],
        }

    def summary_table(self) -> str:
        """Generate formatted comparison table."""
        lines = [
            "",
            "=" * 95,
            "ANUKRITI vs PHARMCAT — Head-to-Head VCF Comparison",
            "=" * 95,
            "",
            f"{'Sample':<12} ",
        ]

        # Build per-gene header
        genes = self.genes_compared
        header = f"{'Sample':<12} " + " ".join(f"{g:>10}" for g in genes) + "  Overall"
        sep = "-" * len(header)
        lines = lines[:5]  # Reset
        lines.extend(["", header, sep])

        for s in self.samples:
            row = f"{s.sample_id:<12} "
            for g in genes:
                if g in s.genes:
                    match = "Y" if s.genes[g].get("concordant") else "N"
                    row += f"{'  ' + match:>10} "
                else:
                    row += f"{'---':>10} "
            row += f"  {s.concordant_genes}/{s.total_genes}"
            lines.append(row)

        lines.append(sep)
        lines.append(
            f"Overall concordance: {self.total_concordant}/{self.total_comparisons} "
            f"({self.concordance:.1%})"
        )
        lines.append("")
        return "\n".join(lines)

    def generate_latex_table(self) -> str:
        """Generate LaTeX table for the paper."""
        genes = self.genes_compared
        ncols = len(genes) + 2  # sample + genes + overall
        col_spec = "l" + "c" * (len(genes) + 1)

        lines = [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\caption{Head-to-head comparison: Anukriti vs.\ PharmCAT on identical "
            r"1000 Genomes VCF inputs. \checkmark\ indicates phenotype concordance.}",
            r"\label{tab:pharmcat-comparison}",
            r"\renewcommand{\arraystretch}{1.2}",
            r"\small",
            f"\\begin{{tabular}}{{@{{}}{col_spec}@{{}}}}",
            r"\toprule",
            r"\textbf{Sample} & "
            + " & ".join(f"\\textbf{{{g}}}" for g in genes)
            + r" & \textbf{Overall} \\",
            r"\midrule",
        ]

        for s in self.samples:
            row = s.sample_id
            for g in genes:
                if g in s.genes and s.genes[g].get("concordant"):
                    row += r" & \checkmark"
                elif g in s.genes:
                    row += r" & $\times$"
                else:
                    row += " & ---"
            row += f" & {s.concordant_genes}/{s.total_genes} \\\\"
            lines.append(f"  {row}")

        lines.append(r"\midrule")
        lines.append(
            f"  \\textbf{{Overall}} & "
            + " & ".join([""] * len(genes))
            + f" & \\textbf{{{self.total_concordant}/{self.total_comparisons}}} \\\\"
        )
        lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
        return "\n".join(lines)


def extract_sample_variants(
    vcf_path: str,
    sample_id: str,
    gene: str,
) -> Dict[str, Tuple[str, str, str]]:
    """
    Extract PGx variants for a single sample from a 1000 Genomes VCF.

    Returns: {rsid: (ref, alt, genotype_string)}
    """
    if gene not in GENE_REGIONS_GRCH37:
        return {}

    region = GENE_REGIONS_GRCH37[gene]
    target_chrom = region["chrom"]
    start = region["start"]
    end = region["end"]
    target_rsids = set(PGX_RSIDS.get(gene, []))

    variants: Dict[str, Tuple[str, str, str]] = {}
    sample_idx: Optional[int] = None

    # Build position-to-rsid lookup for fallback matching
    pos_to_rsid: Dict[int, str] = {}
    for rsid in target_rsids:
        pos = _RSID_POSITIONS_GRCH37.get(rsid)
        if pos:
            pos_to_rsid[pos] = rsid

    open_func: Any = gzip.open if vcf_path.endswith(".gz") else open
    mode = "rt" if vcf_path.endswith(".gz") else "r"

    with open_func(vcf_path, mode) as f:
        for line in f:
            if line.startswith("#CHROM"):
                fields = line.strip().split("\t")
                samples = fields[9:]
                if sample_id in samples:
                    sample_idx = samples.index(sample_id)
                else:
                    logger.warning(f"Sample {sample_id} not found in VCF")
                    return {}
                continue

            if line.startswith("#"):
                continue

            # Quick parse of first 3 fields only (avoid splitting 2504 columns)
            tab1 = line.index("\t")
            chrom = line[:tab1]

            if chrom != target_chrom:
                continue

            tab2 = line.index("\t", tab1 + 1)
            pos = int(line[tab1 + 1 : tab2])

            if pos < start:
                continue
            if pos > end:
                break  # VCFs are sorted by position

            tab3 = line.index("\t", tab2 + 1)
            rsid_field = line[tab2 + 1 : tab3]

            # Match by rsID or by position (some VCFs use "." for ID)
            matched_rsid = None
            if rsid_field in target_rsids:
                matched_rsid = rsid_field
            elif pos in pos_to_rsid:
                matched_rsid = pos_to_rsid[pos]

            if matched_rsid is None or sample_idx is None:
                continue

            # Only do full split for matching variants
            all_fields = line.strip().split("\t")
            ref = all_fields[3]
            alt = all_fields[4]

            col = 9 + sample_idx
            if col < len(all_fields):
                gt = all_fields[col].split(":")[0]
                variants[matched_rsid] = (ref, alt, gt)

    return variants


def find_vcf_for_gene(gene: str, genomes_dir: Path) -> Optional[Path]:
    """Find the VCF file containing a gene's chromosome."""
    if gene not in GENE_REGIONS_GRCH37:
        return None

    chrom = GENE_REGIONS_GRCH37[gene]["chrom"]

    # Try both v5a and v5b suffixes
    for suffix in ["a", "b"]:
        pattern = f"ALL.chr{chrom}.phase3_shapeit2_mvncall_integrated_v5{suffix}.20130502.genotypes.vcf.gz"
        path = genomes_dir / pattern
        if path.exists():
            return path

    return None


def create_grch38_vcf(
    variants: Dict[str, Dict[str, Tuple[str, str, str]]],
    sample_id: str,
    output_path: Path,
) -> bool:
    """
    Create a GRCh38 VCF file for PharmCAT from extracted variants.

    PharmCAT requires a genotype call at every allele-definition position —
    missing positions are treated as "no data", not as reference.  This
    function lifts the sample's actual variant calls from GRCh37 to GRCh38,
    then backfills **reference calls (0/0)** at all remaining PharmCAT
    definition positions so that PharmCAT can make a proper allele call.

    Uses pyliftover for coordinate conversion of sample variants.

    Args:
        variants: {gene: {rsid: (ref, alt, gt)}}
        sample_id: Identifier written into the VCF header/sample column.
        output_path: Where to write the VCF.

    Returns:
        True if the VCF was written with at least one data line.
    """
    try:
        from pyliftover import LiftOver

        lo = LiftOver("hg19", "hg38")
    except Exception as e:
        logger.error(f"pyliftover not available: {e}")
        return False

    vcf_lines = [
        "##fileformat=VCFv4.2",
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
        f"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t{sample_id}",
    ]

    # Track which GRCh38 positions already have a call from the sample so
    # we don't emit duplicates when backfilling.
    covered_positions: set = set()  # {(chrom, pos)}

    # --- Step 1: Lift over the sample's actual variant calls ---------------
    for gene, gene_variants in sorted(variants.items()):
        if gene not in GENE_REGIONS_GRCH37:
            continue
        chrom_37 = GENE_REGIONS_GRCH37[gene]["chrom"]

        for rsid, (ref, alt, gt) in sorted(gene_variants.items()):
            grch37_pos = _get_rsid_position_grch37(rsid, gene)
            if grch37_pos is None:
                continue

            result = lo.convert_coordinate(f"chr{chrom_37}", grch37_pos - 1)
            if not result:
                logger.warning(
                    f"Liftover failed for {rsid} at chr{chrom_37}:{grch37_pos}"
                )
                continue

            grch38_chrom, grch38_pos_0based, strand, score = result[0]
            grch38_pos = grch38_pos_0based + 1

            covered_positions.add((grch38_chrom, grch38_pos))
            vcf_lines.append(
                f"{grch38_chrom}\t{grch38_pos}\t{rsid}\t{ref}\t{alt}"
                f"\t.\tPASS\t.\tGT\t{gt}"
            )

    # --- Step 2: Backfill reference calls at all PharmCAT definition -------
    #     positions that the sample did not already cover.
    ref_backfill_count = 0
    for gene in sorted(PHARMCAT_DEFINITION_POSITIONS_GRCH38):
        # Only backfill genes we are actually comparing
        if gene not in GENE_REGIONS_GRCH37:
            continue

        for chrom, pos, rsid, ref in PHARMCAT_DEFINITION_POSITIONS_GRCH38[gene]:
            if (chrom, pos) in covered_positions:
                continue
            # Emit a homozygous-reference call.  ALT is "." (no alternate).
            vcf_lines.append(f"{chrom}\t{pos}\t{rsid}\t{ref}\t.\t.\tPASS\t.\tGT\t0/0")
            covered_positions.add((chrom, pos))
            ref_backfill_count += 1

    logger.info(
        f"GRCh38 VCF for {sample_id}: "
        f"{len(vcf_lines) - 3} total lines "
        f"({ref_backfill_count} reference backfill)"
    )

    # Sort variant lines by chromosome then position
    header_lines = vcf_lines[:3]
    variant_lines = vcf_lines[3:]
    variant_lines.sort(key=lambda x: (x.split("\t")[0], int(x.split("\t")[1])))

    with open(output_path, "w") as f:
        f.write("\n".join(header_lines + variant_lines) + "\n")

    return len(variant_lines) > 0


# Known GRCh37 positions for key PGx rsIDs
_RSID_POSITIONS_GRCH37: Dict[str, int] = {
    # CYP2C19
    "rs4244285": 96541616,
    "rs4986893": 96540410,
    "rs12248560": 96521657,
    "rs28399504": 96535210,
    # CYP2C9
    "rs1799853": 96702047,
    "rs1057910": 96741053,
    # TPMT
    "rs1800462": 18143955,
    "rs1800460": 18130918,
    "rs1142345": 18143724,
    # DPYD
    "rs3918290": 97915614,
    "rs55886062": 97981395,
    "rs67376798": 97847693,
    "rs75017182": 97573863,
    # SLCO1B1
    "rs4149056": 21331549,
    # VKORC1
    "rs9923231": 31104878,
    # UGT1A1
    "rs8175347": 234668879,
    "rs4148323": 234669144,
}


def _get_rsid_position_grch37(rsid: str, gene: str) -> Optional[int]:
    """Get known GRCh37 position for a PGx rsID."""
    return _RSID_POSITIONS_GRCH37.get(rsid)


# ---------------------------------------------------------------------------
# PharmCAT allele-definition positions (GRCh38).
#
# PharmCAT requires a genotype call at *every* position used in its allele
# definitions — if a position is absent from the VCF it is treated as "no
# data", NOT as homozygous-reference.  This table was extracted from the
# PharmCAT preprocessor's `*.missing_pgx_var.vcf` output and lists every
# definition position for the seven genes Anukriti covers.
#
# Each entry is (chrom, pos, rsid_or_dot, ref_allele).
# ---------------------------------------------------------------------------
PHARMCAT_DEFINITION_POSITIONS_GRCH38: Dict[str, List[Tuple[str, int, str, str]]] = {
    "CYP2C19": [
        ("chr10", 94761900, "rs12248560", "C"),
        ("chr10", 94762706, "rs28399504", "A"),
        ("chr10", 94762712, "rs367543002", "C"),
        ("chr10", 94762715, "rs367543003", "T"),
        ("chr10", 94762755, "rs55752064", "T"),
        ("chr10", 94762760, "rs17882687", "A"),
        ("chr10", 94762788, "rs1564656981", "A"),
        ("chr10", 94762856, "rs1564657013", "A"),
        ("chr10", 94775106, "rs145328984", "C"),
        ("chr10", 94775121, "rs1564660997", "C"),
        ("chr10", 94775160, "rs118203756", "G"),
        ("chr10", 94775185, "rs1288601658", "A"),
        ("chr10", 94775367, "rs12769205", "A"),
        ("chr10", 94775416, "rs41291556", "T"),
        ("chr10", 94775423, "rs17885179", "A"),
        ("chr10", 94775489, "rs17884712", "G"),
        ("chr10", 94775507, "rs58973490", "G"),
        ("chr10", 94780544, "rs57700608", "A"),
        ("chr10", 94780574, "rs140278421", "G"),
        ("chr10", 94780579, "rs370803989", "G"),
        ("chr10", 94781858, "rs6413438", "C"),
        ("chr10", 94781944, "rs375781227", "G"),
        ("chr10", 94781999, "rs72558186", "T"),
        ("chr10", 94842861, "rs138142612", "G"),
        ("chr10", 94842866, "rs3758581", "A"),
        ("chr10", 94842879, "rs118203757", "G"),
        ("chr10", 94842995, "rs113934938", "G"),
        ("chr10", 94849995, "rs17879685", "C"),
        ("chr10", 94852738, "rs56337013", "C"),
        ("chr10", 94852765, "rs192154563", "C"),
        ("chr10", 94852785, "rs118203759", "C"),
        ("chr10", 94852914, "rs55640102", "A"),
    ],
    "CYP2C9": [
        ("chr10", 94938683, "rs114071557", "A"),
        ("chr10", 94938719, ".", "T"),
        ("chr10", 94938737, "rs67807361", "C"),
        ("chr10", 94938771, "rs142240658", "C"),
        ("chr10", 94938788, ".", "C"),
        ("chr10", 94938800, "rs1364419386", "G"),
        ("chr10", 94938803, "rs2031308986", "A"),
        ("chr10", 94938828, "rs564813580", "A"),
        ("chr10", 94941897, "rs371055887", "G"),
        ("chr10", 94941915, "rs1216169538", "G"),
        ("chr10", 94941958, "rs72558187", "T"),
        ("chr10", 94941975, "rs2493006942", "G"),
        ("chr10", 94941976, "rs761033063", "G"),
        ("chr10", 94941982, "rs762239445", "G"),
        ("chr10", 94942018, ".", "T"),
        ("chr10", 94942205, "rs1304490498", "CAATGGAAAGA"),
        ("chr10", 94942216, "rs774607211", "A"),
        ("chr10", 94942230, "rs767576260", "C"),
        ("chr10", 94942231, "rs12414460", "G"),
        ("chr10", 94942233, "rs375805362", "C"),
        ("chr10", 94942234, "rs72558189", "G"),
        ("chr10", 94942240, "rs530507053", "C"),
        ("chr10", 94942243, "rs1375956433", "T"),
        ("chr10", 94942249, "rs200965026", "C"),
        ("chr10", 94942254, "rs199523631", "C"),
        ("chr10", 94942255, "rs200183364", "G"),
        ("chr10", 94942291, "rs141489852", "G"),
        ("chr10", 94942305, "rs754487195", "G"),
        ("chr10", 94942306, "rs1289704600", "C"),
        ("chr10", 94942308, "rs17847037", "C"),
        ("chr10", 94942309, "rs7900194", "G"),
        ("chr10", 94947782, "rs72558190", "C"),
        ("chr10", 94947785, "rs774550549", "C"),
        ("chr10", 94947869, "rs2492587526", "A"),
        ("chr10", 94947907, ".", "A"),
        ("chr10", 94947917, "rs1326630788", "T"),
        ("chr10", 94947938, "rs2031531005", "A"),
        ("chr10", 94947939, "rs370100007", "G"),
        ("chr10", 94949129, ".", "A"),
        ("chr10", 94949144, "rs2492591692", "C"),
        ("chr10", 94949145, "rs772782449", "C"),
        ("chr10", 94949161, ".", "AT"),
        ("chr10", 94949184, "rs369745682", "T"),
        ("chr10", 94949217, "rs2256871", "A"),
        ("chr10", 94949280, "rs9332130", "A"),
        ("chr10", 94949281, "rs9332131", "GA"),
        ("chr10", 94972119, "rs182132442", "C"),
        ("chr10", 94972123, ".", "C"),
        ("chr10", 94972134, "rs2492634549", "A"),
        ("chr10", 94972179, "rs72558192", "A"),
        ("chr10", 94972180, "rs988617574", "C"),
        ("chr10", 94972183, ".", "A"),
        ("chr10", 94972194, "rs546318684", "A"),
        ("chr10", 94972233, "rs1237225311", "C"),
        ("chr10", 94981199, ".", "G"),
        ("chr10", 94981201, "rs57505750", "T"),
        ("chr10", 94981224, "rs28371685", "C"),
        ("chr10", 94981225, "rs367826293", "G"),
        ("chr10", 94981230, "rs1274535931", "C"),
        ("chr10", 94981250, "rs750820937", "C"),
        ("chr10", 94981258, "rs1297714792", "C"),
        ("chr10", 94981281, "rs749060448", "G"),
        ("chr10", 94981297, "rs56165452", "T"),
        ("chr10", 94981301, "rs28371686", "C"),
        ("chr10", 94981302, "rs1250577724", "C"),
        ("chr10", 94981305, "rs578144976", "C"),
        ("chr10", 94981365, "rs2492650213", "C"),
        ("chr10", 94981371, "rs542577750", "G"),
        ("chr10", 94986042, "rs764211126", "A"),
        ("chr10", 94986073, "rs72558193", "A"),
        ("chr10", 94986136, "rs1254213342", "A"),
        ("chr10", 94986174, "rs1441296358", "G"),
        ("chr10", 94988852, "rs776908257", "C"),
        ("chr10", 94988855, "rs2492662738", "A"),
        ("chr10", 94988880, "rs2492662839", "G"),
        ("chr10", 94988917, "rs769942899", "G"),
        ("chr10", 94988925, "rs202201137", "A"),
        ("chr10", 94988955, "rs767284820", "T"),
        ("chr10", 94988984, "rs781583846", "G"),
        ("chr10", 94989020, "rs9332239", "C"),
        ("chr10", 94989023, "rs868182778", "G"),
    ],
    "DPYD": [
        ("chr1", 97078987, "rs114096998", "G"),
        ("chr1", 97078993, "rs148799944", "C"),
        ("chr1", 97079005, "rs140114515", "C"),
        ("chr1", 97079071, "rs1801268", "C"),
        ("chr1", 97079076, "rs139459586", "A"),
        ("chr1", 97079077, "rs202144771", "G"),
        ("chr1", 97079121, "rs72547601", "T"),
        ("chr1", 97079133, "rs72547602", "T"),
        ("chr1", 97079139, "rs145529148", "T"),
        ("chr1", 97082365, "rs141044036", "T"),
        ("chr1", 97082391, "rs67376798", "T"),
        ("chr1", 97098598, "rs1801267", "C"),
        ("chr1", 97098599, "rs147545709", "G"),
        ("chr1", 97098616, "rs55674432", "C"),
        ("chr1", 97098632, "rs201035051", "T"),
        ("chr1", 97193109, "rs60139309", "T"),
        ("chr1", 97193209, "rs200687447", "C"),
        ("chr1", 97234958, "rs199634007", "G"),
        ("chr1", 97234991, "rs56005131", "G"),
        ("chr1", 97305279, "rs112766203", "G"),
        ("chr1", 97305363, "rs60511679", "A"),
        ("chr1", 97305364, "rs1801160", "C"),
        ("chr1", 97305372, "rs146529561", "G"),
        ("chr1", 97306195, "rs145548112", "C"),
        ("chr1", 97373598, "rs137999090", "C"),
        ("chr1", 97373629, "rs138545885", "C"),
        ("chr1", 97382461, "rs55971861", "T"),
        ("chr1", 97450058, "rs3918290", "C"),
        ("chr1", 97450059, "rs3918289", "G"),
        ("chr1", 97450065, "rs72549303", "TG"),
        ("chr1", 97450068, "rs17376848", "A"),
        ("chr1", 97450168, "rs147601618", "A"),
        ("chr1", 97450187, "rs145773863", "C"),
        ("chr1", 97450189, "rs138616379", "C"),
        ("chr1", 97450190, "rs59086055", "G"),
        ("chr1", 97515784, "rs201615754", "C"),
        ("chr1", 97515787, "rs55886062", "A"),
        ("chr1", 97515839, "rs1801159", "T"),
        ("chr1", 97515851, "rs142619737", "C"),
        ("chr1", 97515865, "rs1801158", "C"),
        ("chr1", 97515889, "rs190951787", "G"),
        ("chr1", 97515923, "rs148994843", "C"),
        ("chr1", 97549565, "rs138391898", "C"),
        ("chr1", 97549600, "rs111858276", "T"),
        ("chr1", 97549609, "rs72549304", "G"),
        ("chr1", 97549681, "rs199549923", "G"),
        ("chr1", 97549713, "rs57918000", "G"),
        ("chr1", 97549726, "rs144395748", "G"),
        ("chr1", 97549735, "rs72975710", "G"),
        ("chr1", 97573785, "rs186169810", "A"),
        ("chr1", 97573805, "rs142512579", "C"),
        ("chr1", 97573821, "rs764666241", "C"),
        ("chr1", 97573839, "rs200064537", "A"),
        ("chr1", 97573863, "rs56038477", "C"),
        ("chr1", 97573881, "rs61622928", "C"),
        ("chr1", 97573918, "rs143815742", "C"),
        ("chr1", 97573919, "rs140602333", "G"),
        ("chr1", 97573943, "rs78060119", "C"),
        ("chr1", 97579893, "rs75017182", "G"),
        ("chr1", 97593238, "rs72549305", "T"),
        ("chr1", 97593289, "rs143154602", "G"),
        ("chr1", 97593322, "rs183385770", "C"),
        ("chr1", 97593343, "rs72549306", "C"),
        ("chr1", 97593379, "rs201018345", "C"),
        ("chr1", 97595083, "rs145112791", "G"),
        ("chr1", 97595088, "rs150437414", "A"),
        ("chr1", 97595149, "rs146356975", "T"),
        ("chr1", 97679170, "rs45589337", "T"),
        ("chr1", 97691776, "rs1801266", "G"),
        ("chr1", 97699399, "rs72549307", "T"),
        ("chr1", 97699430, "rs72549308", "T"),
        ("chr1", 97699474, "rs115232898", "T"),
        ("chr1", 97699506, "rs6670886", "C"),
        ("chr1", 97699533, "rs139834141", "C"),
        ("chr1", 97699535, "rs2297595", "T"),
        ("chr1", 97721542, "rs200562975", "T"),
        ("chr1", 97721650, "rs141462178", "T"),
        ("chr1", 97740400, "rs150385342", "C"),
        ("chr1", 97740410, "rs72549309", "GATGA"),
        ("chr1", 97883329, "rs1801265", "A"),
        ("chr1", 97883352, "rs80081766", "C"),
        ("chr1", 97883353, "rs72549310", "G"),
        ("chr1", 97883368, "rs150036960", "G"),
    ],
    "SLCO1B1": [
        ("chr12", 21141575, "rs185905373", "A"),
        ("chr12", 21172675, "rs556524705", "G"),
        ("chr12", 21172734, "rs139257324", "C"),
        ("chr12", 21172735, "rs61760182", "G"),
        ("chr12", 21172776, "rs373327528", "G"),
        ("chr12", 21172782, "rs56101265", "T"),
        ("chr12", 21176804, "rs2306283", "A"),
        ("chr12", 21176868, "rs2306282", "A"),
        ("chr12", 21176871, "rs145144129", "G"),
        ("chr12", 21176879, "rs11045819", "C"),
        ("chr12", 21176898, "rs77271279", "G"),
        ("chr12", 21178612, "rs141467543", "A"),
        ("chr12", 21178653, "rs200331427", "C"),
        ("chr12", 21178926, "rs201722521", "A"),
        ("chr12", 21178957, "rs79135870", "A"),
        ("chr12", 21196951, "rs11045852", "A"),
        ("chr12", 21196975, "rs183501729", "C"),
        ("chr12", 21196976, "rs11045853", "G"),
        ("chr12", 21200544, "rs72559747", "C"),
        ("chr12", 21200595, "rs55901008", "T"),
        ("chr12", 21200673, "rs756393362", "G"),
        ("chr12", 21202553, "rs1228465562", "T"),
        ("chr12", 21202555, "rs59113707", "C"),
        ("chr12", 21202664, "rs142965323", "G"),
        ("chr12", 21205921, "rs72559748", "A"),
        ("chr12", 21205999, "rs59502379", "G"),
        ("chr12", 21206031, "rs74064213", "A"),
        ("chr12", 21222355, "rs71581941", "C"),
        ("chr12", 21224840, "rs200994482", "G"),
        ("chr12", 21239042, "rs34671512", "A"),
        ("chr12", 21239077, "rs56199088", "A"),
        ("chr12", 21239113, "rs55737008", "A"),
        ("chr12", 21239145, "rs200995543", "C"),
        ("chr12", 21239158, "rs140790673", "C"),
    ],
    "TPMT": [
        ("chr6", 18130687, "rs1142345", "T"),
        ("chr6", 18130694, "rs150900439", "T"),
        ("chr6", 18130725, "rs72552736", "A"),
        ("chr6", 18130729, "rs139392616", "C"),
        ("chr6", 18130730, "rs761990479", "G"),
        ("chr6", 18130758, "rs398122996", "A"),
        ("chr6", 18130762, "rs56161402", "C"),
        ("chr6", 18130772, "rs377085266", "A"),
        ("chr6", 18130781, "rs1800584", "C"),
        ("chr6", 18132136, "rs72556347", "A"),
        ("chr6", 18132147, "rs79901429", "A"),
        ("chr6", 18132163, ".", "C"),
        ("chr6", 18133845, "rs75543815", "T"),
        ("chr6", 18133847, "rs6921269", "C"),
        ("chr6", 18133870, "rs772832951", "A"),
        ("chr6", 18133884, "rs74423290", "G"),
        ("chr6", 18133887, "rs201695576", "T"),
        ("chr6", 18133890, "rs9333570", "C"),
        ("chr6", 18138969, "rs144041067", "C"),
        ("chr6", 18138970, "rs112339338", "G"),
        ("chr6", 18138997, "rs1800460", "C"),
        ("chr6", 18139027, "rs72552737", "C"),
        ("chr6", 18139689, "rs72552738", "C"),
        ("chr6", 18139710, "rs200220210", "G"),
        ("chr6", 18143597, ".", "T"),
        ("chr6", 18143606, "rs151149760", "T"),
        ("chr6", 18143613, ".", "C"),
        ("chr6", 18143622, "rs115106679", "C"),
        ("chr6", 18143643, ".", "A"),
        ("chr6", 18143700, "rs753545734", "C"),
        ("chr6", 18143718, "rs111901354", "G"),
        ("chr6", 18143724, "rs1800462", "C"),
        ("chr6", 18143728, "rs1256618794", "C"),
        ("chr6", 18147838, "rs281874771", "G"),
        ("chr6", 18147845, "rs777686348", "C"),
        ("chr6", 18147851, "rs200591577", "G"),
        ("chr6", 18147856, ".", "A"),
        ("chr6", 18147910, "rs72552740", "A"),
        ("chr6", 18149004, ".", "G"),
        ("chr6", 18149022, "rs750424422", "C"),
        ("chr6", 18149032, "rs759836180", "C"),
        ("chr6", 18149045, "rs72552742", "T"),
        ("chr6", 18149103, ".", "CAAGT"),
        ("chr6", 18149126, "rs267607275", "A"),
        ("chr6", 18149127, "rs9333569", "T"),
    ],
    "UGT1A1": [
        ("chr2", 233759924, "rs887829", "C"),
        ("chr2", 233760233, "rs3064744", "CAT"),
        ("chr2", 233760498, "rs4148323", "G"),
        ("chr2", 233760973, "rs35350960", "C"),
    ],
    "VKORC1": [
        ("chr16", 31096368, "rs9923231", "C"),
    ],
}


def run_pharmcat_docker(vcf_path: Path, output_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Run PharmCAT via Docker on a VCF file.

    Returns parsed phenotype results or None on failure.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(  # nosec B603 B607
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{vcf_path.parent}:/pharmcat/data",
                "-v",
                f"{output_dir}:/pharmcat/output",
                "pgkb/pharmcat",
                "pharmcat_pipeline",
                f"/pharmcat/data/{vcf_path.name}",
                "-o",
                "/pharmcat/output",
                "-reporterJson",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            logger.error(f"PharmCAT failed: {result.stderr}")
            return None

        # Find and parse phenotype JSON
        stem = vcf_path.stem.replace(".vcf", "")
        phenotype_file = output_dir / f"{stem}.phenotype.json"
        if not phenotype_file.exists():
            # Try alternate naming
            for match in output_dir.glob("*.phenotype.json"):
                phenotype_file = match
                break

        if phenotype_file.exists():
            with open(phenotype_file) as fh:
                parsed: Dict[str, Any] = json.load(fh)
                return parsed

        logger.warning(f"No phenotype JSON found in {output_dir}")
        return None

    except subprocess.TimeoutExpired:
        logger.error("PharmCAT timed out after 120 seconds")
        return None
    except FileNotFoundError:
        logger.error("Docker not found. Install Docker to run PharmCAT comparison.")
        return None


def parse_pharmcat_phenotypes(
    pharmcat_result: Dict[str, Any],
) -> Dict[str, Dict[str, str]]:
    """
    Parse PharmCAT phenotype JSON to extract gene -> diplotype/phenotype.

    Returns: {gene: {"diplotype": str, "phenotype": str}}
    """
    results: Dict[str, Dict[str, str]] = {}

    gene_reports = pharmcat_result.get("geneReports", {})
    for gene_name, gene_data in gene_reports.items():
        diplotypes = gene_data.get("sourceDiplotypes", [])
        if not diplotypes:
            continue

        d = diplotypes[0]
        label = d.get("label", "")
        phenotypes = d.get("phenotypes", [])
        phenotype = phenotypes[0] if phenotypes else "No Result"

        # Skip genes with no result
        if phenotype == "No Result" or label == "Unknown/Unknown":
            continue

        results[gene_name] = {
            "diplotype": label,
            "phenotype": phenotype,
        }

    return results


def run_anukriti_on_variants(
    variants: Dict[str, Dict[str, Tuple[str, str, str]]],
    pgx_data_dir: Optional[Path] = None,
) -> Dict[str, Dict[str, str]]:
    """
    Run Anukriti's allele caller on extracted variants.

    Returns: {gene: {"diplotype": str, "phenotype": str}}
    """
    from ..allele_caller import (
        alt_dosage,
        build_diplotype,
        call_star_alleles,
        diplotype_to_phenotype,
        load_cpic_translation_for_gene,
        load_pharmvar_alleles,
    )

    results: Dict[str, Dict[str, str]] = {}
    base_dir = (
        pgx_data_dir or Path(__file__).resolve().parent.parent.parent / "data" / "pgx"
    )

    for gene, gene_variants in variants.items():
        # SLCO1B1: single-locus genotype (TT/TC/CC at rs4149056)
        if gene.upper() == "SLCO1B1":
            rs_data = gene_variants.get("rs4149056")
            if rs_data:
                ref, alt_allele, gt = rs_data
                dosage = alt_dosage(gt)
                geno_map = {0: "TT", 1: "TC", 2: "CC"}
                genotype = geno_map.get(dosage, "TT")
                pheno_map = {
                    "TT": "Normal Function",
                    "TC": "Decreased Function",
                    "CC": "Poor Function",
                }
                results[gene] = {
                    "diplotype": genotype,
                    "phenotype": pheno_map.get(genotype, "Unknown"),
                }
            continue

        # VKORC1: single-locus genotype (GG/GA/AA at rs9923231)
        if gene.upper() == "VKORC1":
            rs_data = gene_variants.get("rs9923231")
            if rs_data:
                ref, alt_allele, gt = rs_data
                dosage = alt_dosage(gt)
                geno_map = {0: "GG", 1: "GA", 2: "AA"}
                genotype = geno_map.get(dosage, "GG")
                pheno_map = {
                    "GG": "Normal Sensitivity",
                    "GA": "Intermediate Sensitivity",
                    "AA": "High Sensitivity",
                }
                results[gene] = {
                    "diplotype": genotype,
                    "phenotype": pheno_map.get(genotype, "Unknown"),
                }
            continue

        # Standard star-allele-based genes
        try:
            allele_table = load_pharmvar_alleles(gene, base_dir=base_dir)
            translation = load_cpic_translation_for_gene(gene, base_dir=base_dir)
        except FileNotFoundError:
            logger.warning(f"Missing data files for {gene}")
            continue

        variant_tuples = {rsid: vals for rsid, vals in gene_variants.items()}

        allele_counts = call_star_alleles(variant_tuples, allele_table)
        diplotype = build_diplotype(allele_counts)
        phenotype = diplotype_to_phenotype(diplotype, translation)

        results[gene] = {
            "diplotype": diplotype,
            "phenotype": phenotype,
        }

    return results


def compare_results(
    anukriti: Dict[str, Dict[str, str]],
    pharmcat: Dict[str, Dict[str, str]],
    sample_id: str,
) -> SampleComparison:
    """Compare Anukriti and PharmCAT results for a single sample."""
    from .concordance import normalize_phenotype

    comparison = SampleComparison(sample_id=sample_id)

    # Compare genes present in both
    all_genes = set(anukriti.keys()) | set(pharmcat.keys())

    for gene in sorted(all_genes):
        anu = anukriti.get(gene, {})
        pcat = pharmcat.get(gene, {})

        anu_pheno = normalize_phenotype(anu.get("phenotype", "Unknown"))
        pcat_pheno = normalize_phenotype(pcat.get("phenotype", "Unknown"))

        comparison.genes[gene] = {
            "anukriti_diplotype": anu.get("diplotype", "N/A"),
            "anukriti_phenotype": anu.get("phenotype", "N/A"),
            "pharmcat_diplotype": pcat.get("diplotype", "N/A"),
            "pharmcat_phenotype": pcat.get("phenotype", "N/A"),
            "concordant": anu_pheno == pcat_pheno and anu_pheno != "unknown",
        }

    return comparison
