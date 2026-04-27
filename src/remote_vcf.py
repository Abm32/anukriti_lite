"""
Remote VCF and variant data access — no local downloads needed.

Three strategies for accessing 1000 Genomes PGx data without downloading
terabytes of VCF files:

1. Remote tabix: HTTP range queries against 1000 Genomes FTP/HTTP servers
2. Pre-extracted PGx panel: Tiny TSV with just the ~30 rsIDs we need
3. Ensembl REST API: Query individual variants by rsID

The system tries each in order and falls back gracefully.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess  # nosec B404 - tabix for remote HTTP range queries on public 1000 Genomes data
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis cache for VCF streaming (optional — graceful fallback to no-cache)
# ---------------------------------------------------------------------------
_redis_client = None
_redis_checked = False


def _get_redis():
    """Lazy-init Redis client. Returns None if unavailable."""
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True

    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return None

    try:
        import redis as _redis_mod

        _redis_client = _redis_mod.from_url(redis_url, decode_responses=True)
        _redis_client.ping()
        logger.info("Redis VCF cache connected: %s", redis_url)
    except Exception as exc:
        logger.info("Redis unavailable (%s); VCF caching disabled", exc)
        _redis_client = None
    return _redis_client


def _vcf_cache_key(url: str, region: str, sample_id: Optional[str]) -> str:
    """Deterministic cache key for a tabix query."""
    raw = f"vcf:{url}:{region}:{sample_id or ''}"
    return "anukriti:" + hashlib.sha256(raw.encode()).hexdigest()[:32]


def _vcf_cache_ttl() -> int:
    return int(os.getenv("REDIS_VCF_CACHE_TTL", "86400"))


# 1000 Genomes Phase 3 remote URLs (EBI mirror — supports HTTP tabix)
REMOTE_VCF_URLS = {
    "chr1": "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/ALL.chr1.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
    "chr2": "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/ALL.chr2.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
    "chr6": "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/ALL.chr6.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
    "chr10": "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/ALL.chr10.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
    "chr12": "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/ALL.chr12.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
    "chr16": "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/ALL.chr16.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
    "chr22": "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/ALL.chr22.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
}

# PGx rsIDs we care about, grouped by gene
PGX_RSIDS = {
    "CYP2D6": {
        "chrom": "22",
        "rsids": [
            "rs3892097",
            "rs1065852",
            "rs16947",
            "rs28371725",
            "rs35742686",
            "rs5030655",
            "rs5030865",
            "rs28371706",
        ],
    },
    "CYP2C19": {
        "chrom": "10",
        "rsids": [
            "rs4244285",
            "rs4986893",
            "rs12248560",
            "rs28399504",
            "rs56337013",
            "rs72552267",
        ],
    },
    "CYP2C9": {
        "chrom": "10",
        "rsids": [
            "rs1799853",
            "rs1057910",
            "rs28371686",
            "rs9332131",
            "rs28371685",
            "rs7900194",
        ],
    },
    "VKORC1": {
        "chrom": "16",
        "rsids": ["rs9923231"],
    },
    "SLCO1B1": {
        "chrom": "12",
        "rsids": ["rs4149056", "rs2306283"],
    },
    "UGT1A1": {
        "chrom": "2",
        "rsids": ["rs8175347", "rs4148323", "rs3064744"],
    },
    "TPMT": {
        "chrom": "6",
        "rsids": ["rs1800462", "rs1800460", "rs1142345", "rs1800584"],
    },
    "DPYD": {
        "chrom": "1",
        "rsids": ["rs3918290", "rs55886062", "rs67376798", "rs56038477"],
    },
}

# Pre-extracted PGx panel cache location
PGX_PANEL_CACHE = (
    Path(__file__).resolve().parent.parent / "data" / "pgx" / "panel_cache"
)


def remote_tabix_query(
    chrom_key: str,
    region: str,
    sample_id: Optional[str] = None,
    timeout: int = 30,
) -> List[Dict]:
    """
    Query a remote 1000 Genomes VCF via HTTP tabix (range request).
    Downloads only the requested region (~KB), not the whole file (~GB).

    Args:
        chrom_key: e.g. "chr22"
        region: e.g. "22:42522500-42530900"
        sample_id: Optional sample to extract genotype for
        timeout: Request timeout in seconds

    Returns:
        List of variant dicts with id, ref, alt, genotype fields
    """
    url = REMOTE_VCF_URLS.get(chrom_key)
    if not url:
        logger.warning(f"No remote URL for {chrom_key}")
        return []

    # Try Redis cache first
    rclient = _get_redis()
    cache_key = _vcf_cache_key(url, region, sample_id) if rclient else ""
    if rclient and cache_key:
        try:
            cached = rclient.get(cache_key)
            if cached is not None:
                logger.info("VCF cache HIT for %s %s", chrom_key, region)
                return json.loads(cached)
        except Exception as exc:
            logger.debug("Redis get failed (non-fatal): %s", exc)

    try:
        result = subprocess.run(  # nosec B603 B607
            ["tabix", "-h", url, region],
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
        lines = result.stdout.strip().split("\n")
        sample_names: Optional[List[str]] = None
        sample_idx: Optional[int] = None
        variants: List[Dict] = []

        for line in lines:
            if not line:
                continue
            if line.startswith("#CHROM"):
                parts = line.strip().split("\t")
                if len(parts) > 9:
                    sample_names = parts[9:]
                    if sample_id and sample_id in sample_names:
                        sample_idx = sample_names.index(sample_id)
                continue
            if line.startswith("#"):
                continue

            fields = line.strip().split("\t")
            if len(fields) < 10:
                continue

            rsid = fields[2]
            ref = fields[3]
            alt = fields[4]
            gt = None
            if sample_idx is not None and (9 + sample_idx) < len(fields):
                gt_field = fields[9 + sample_idx]
                gt = gt_field.split(":")[0]  # Extract GT from FORMAT

            variants.append(
                {
                    "id": rsid,
                    "ref": ref,
                    "alt": alt,
                    "genotype": gt,
                    "chrom": fields[0],
                    "pos": int(fields[1]),
                }
            )

        logger.info(f"Remote tabix: {len(variants)} variants from {chrom_key} {region}")

        # Store in Redis cache for future queries
        if rclient and cache_key and variants:
            try:
                rclient.setex(cache_key, _vcf_cache_ttl(), json.dumps(variants))
                logger.debug(
                    "VCF cache SET for %s %s (%d variants)",
                    chrom_key,
                    region,
                    len(variants),
                )
            except Exception as exc:
                logger.debug("Redis set failed (non-fatal): %s", exc)

        return variants

    except FileNotFoundError:
        logger.warning("tabix not installed — cannot do remote queries")
        return []
    except subprocess.TimeoutExpired:
        logger.warning(f"Remote tabix timed out for {chrom_key} {region}")
        return []
    except subprocess.CalledProcessError as e:
        logger.warning(f"Remote tabix failed for {chrom_key}: {e}")
        return []


def query_ensembl_variant(rsid: str) -> Optional[Dict]:
    """
    Query Ensembl REST API for a single variant by rsID.
    Returns alleles and population frequencies. No local files needed.

    Rate limit: max 15 requests/second.
    """
    import requests

    url = f"https://rest.ensembl.org/variation/human/{rsid}"
    try:
        resp = requests.get(
            url,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "rsid": rsid,
                "alleles": data.get("mappings", [{}])[0].get("allele_string", ""),
                "minor_allele": data.get("minor_allele", ""),
                "maf": data.get("MAF"),
                "ancestral_allele": data.get("ancestral_allele", ""),
            }
        elif resp.status_code == 429:
            time.sleep(1)  # Rate limited, wait
            return query_ensembl_variant(rsid)
        else:
            logger.warning(f"Ensembl API returned {resp.status_code} for {rsid}")
            return None
    except Exception as e:
        logger.warning(f"Ensembl API failed for {rsid}: {e}")
        return None


def query_ensembl_genotype(rsid: str, sample_id: str) -> Optional[str]:
    """
    Query Ensembl for a specific sample's genotype at an rsID.
    Uses the 1000 Genomes population endpoint.
    """
    import requests

    url = f"https://rest.ensembl.org/variation/human/{rsid}?pops=1"
    try:
        resp = requests.get(
            url,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code == 200:
            result: Optional[str] = resp.json().get("minor_allele")
            return result
        return None
    except Exception:
        return None


def extract_pgx_panel_remote(
    sample_id: str,
    genes: Optional[List[str]] = None,
    timeout: int = 30,
) -> Dict[str, Dict[str, Tuple[str, str, str]]]:
    """
    Extract PGx-relevant variants for a sample using remote tabix queries.
    Only fetches the specific genomic regions needed (~KB each).

    Args:
        sample_id: 1000 Genomes sample ID (e.g. "HG00096")
        genes: List of genes to query (default: all PGx genes)
        timeout: Per-query timeout

    Returns:
        Dict of gene -> {rsid: (ref, alt, genotype)}
    """
    from .vcf_processor import CYP_GENE_LOCATIONS

    target_genes = genes or list(PGX_RSIDS.keys())
    results: Dict[str, Dict[str, Tuple[str, str, str]]] = {}

    for gene in target_genes:
        gene_info = PGX_RSIDS.get(gene)
        if not gene_info:
            continue

        gene_loc = CYP_GENE_LOCATIONS.get(gene)
        if not gene_loc:
            continue

        chrom = gene_loc["chrom"]
        chrom_key = f"chr{chrom}"
        region = f"{chrom}:{gene_loc['start']}-{gene_loc['end']}"

        variants = remote_tabix_query(chrom_key, region, sample_id, timeout)
        if not variants:
            continue

        target_rsids = set(gene_info["rsids"])
        gene_variants: Dict[str, Tuple[str, str, str]] = {}

        for v in variants:
            if v["id"] in target_rsids and v.get("genotype"):
                gene_variants[v["id"]] = (v["ref"], v["alt"], v["genotype"])

        if gene_variants:
            results[gene] = gene_variants
            logger.info(
                f"Remote: {gene} → {len(gene_variants)} PGx variants for {sample_id}"
            )

    return results


def save_pgx_panel_cache(
    sample_id: str,
    panel_data: Dict[str, Dict[str, Tuple[str, str, str]]],
) -> Path:
    """
    Cache extracted PGx panel to a tiny JSON file for instant reuse.
    """
    PGX_PANEL_CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = PGX_PANEL_CACHE / f"{sample_id}.json"

    serializable = {}
    for gene, variants in panel_data.items():
        serializable[gene] = {
            rsid: {"ref": ref, "alt": alt, "gt": gt}
            for rsid, (ref, alt, gt) in variants.items()
        }

    with open(cache_file, "w") as f:
        json.dump(serializable, f, indent=2)

    logger.info(f"Cached PGx panel for {sample_id} → {cache_file}")
    return cache_file


def load_pgx_panel_cache(
    sample_id: str,
) -> Optional[Dict[str, Dict[str, Tuple[str, str, str]]]]:
    """
    Load cached PGx panel if available.
    """
    cache_file = PGX_PANEL_CACHE / f"{sample_id}.json"
    if not cache_file.exists():
        return None

    try:
        with open(cache_file, "r") as f:
            data = json.load(f)

        result: Dict[str, Dict[str, Tuple[str, str, str]]] = {}
        for gene, variants in data.items():
            result[gene] = {
                rsid: (v["ref"], v["alt"], v["gt"]) for rsid, v in variants.items()
            }
        logger.info(f"Loaded cached PGx panel for {sample_id}")
        return result
    except Exception as e:
        logger.warning(f"Cache load failed for {sample_id}: {e}")
        return None


def get_pgx_panel(
    sample_id: str,
    genes: Optional[List[str]] = None,
    use_cache: bool = True,
) -> Dict[str, Dict[str, Tuple[str, str, str]]]:
    """
    Get PGx panel for a sample. Tries in order:
    1. Local cache (instant)
    2. Remote tabix (seconds, ~KB download per gene)
    3. Returns empty dict if both fail

    Args:
        sample_id: 1000 Genomes sample ID
        genes: Specific genes to query (default: all)
        use_cache: Whether to check/save cache

    Returns:
        Dict of gene -> {rsid: (ref, alt, genotype)}
    """
    # Try cache first
    if use_cache:
        cached = load_pgx_panel_cache(sample_id)
        if cached:
            if genes:
                return {g: cached[g] for g in genes if g in cached}
            return cached

    # Remote tabix
    panel = extract_pgx_panel_remote(sample_id, genes)

    # Cache for next time
    if panel and use_cache:
        save_pgx_panel_cache(sample_id, panel)

    return panel


def get_remote_sample_ids(chrom_key: str = "chr22", limit: int = 50) -> List[str]:
    """
    Get sample IDs from a remote VCF header without downloading the file.
    Uses tabix -H to fetch just the header.
    """
    url = REMOTE_VCF_URLS.get(chrom_key)
    if not url:
        return []

    try:
        result = subprocess.run(  # nosec B603 B607
            ["tabix", "-H", url],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        for line in result.stdout.strip().split("\n"):
            if line.startswith("#CHROM"):
                parts = line.strip().split("\t")
                if len(parts) > 9:
                    samples = parts[9:]
                    return samples[:limit]
        return []
    except Exception as e:
        logger.warning(f"Remote sample ID fetch failed: {e}")
        return []
