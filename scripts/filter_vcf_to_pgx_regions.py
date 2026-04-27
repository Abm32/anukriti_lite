#!/usr/bin/env python3
"""
Filter VCF to PGx gene regions only.

Extracts variants in pharmacogenomics gene regions (chr1, 2, 6, 10, 12, 16, 22)
using tabix. Reduces large VCFs (e.g., from DeepVariant with 4M+ variants) to
a small PGx-only subset for SynthaTrial ingestion.

Usage:
    python scripts/filter_vcf_to_pgx_regions.py input.vcf.gz output.vcf.gz
    python scripts/filter_vcf_to_pgx_regions.py input.vcf.gz output.vcf.gz --build GRCh38

Requires: tabix (htslib), bgzip for output compression.
"""

from __future__ import annotations

import argparse
import logging
import subprocess  # nosec B404 - tabix/bgzip from config
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# PGx gene regions (GRCh37/hg19). SynthaTrial vcf_processor.py GENE_LOCATIONS_GRCH37
PGX_REGIONS_GRCH37 = [
    ("1", 97543299, 97883432),   # DPYD
    ("2", 234668875, 234689625), # UGT1A1
    ("6", 18128542, 18155374),   # TPMT
    ("6", 31365000, 31369000),   # HLA-B*57:01 proxy (rs2395029)
    ("10", 96535040, 96625463),  # CYP2C19
    ("10", 96698415, 96749147),  # CYP2C9
    ("12", 21288593, 21397223),  # SLCO1B1
    ("16", 31102163, 31107800),  # VKORC1
    ("22", 42522500, 42530900),  # CYP2D6
]

# GRCh38/hg38 coordinates
PGX_REGIONS_GRCH38 = [
    ("1", 97078528, 97921547),   # DPYD
    ("2", 233757687, 233773299), # UGT1A1
    ("6", 18128542, 18155372),   # TPMT
    ("6", 31265000, 31269000),   # HLA-B*57:01 proxy
    ("10", 94762681, 94855547),  # CYP2C19
    ("10", 94938683, 94990091),  # CYP2C9
    ("12", 21130388, 21241481),  # SLCO1B1
    ("16", 31096368, 31101932),  # VKORC1
    ("22", 42126499, 42135000),  # CYP2D6
]


def _region_str(chrom: str, start: int, end: int, chr_prefix: bool) -> str:
    """Format region for tabix: chr:start-end or N:start-end."""
    c = f"chr{chrom}" if chr_prefix else chrom
    return f"{c}:{start}-{end}"


def run_tabix(
    vcf_path: str,
    output_path: str,
    regions: list[tuple[str, int, int]],
    chr_prefix: bool = False,
) -> int:
    """Extract regions with tabix, write to output. Returns 0 on success."""
    region_strs = [_region_str(c, s, e, chr_prefix) for c, s, e in regions]
    cmd = ["tabix", "-h", vcf_path] + region_strs
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
        out = result.stdout
    except subprocess.CalledProcessError as e:
        logger.error("tabix failed: %s", e.stderr)
        return 1
    except FileNotFoundError:
        logger.error("tabix not found. Install htslib (e.g. conda install -c conda-forge htslib)")
        return 1
    except subprocess.TimeoutExpired:
        logger.error("tabix timed out")
        return 1

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    wrote_gz = False
    if output_path.endswith(".gz"):
        # Pipe through bgzip
        try:
            with open(out_path, "wb") as f:
                proc = subprocess.Popen(
                    ["bgzip", "-c"],
                    stdin=subprocess.PIPE,
                    stdout=f,
                    stderr=subprocess.PIPE,
                )
                proc.stdin.write(out.encode())
                proc.stdin.close()
                proc.wait(timeout=60)
            if proc.returncode != 0:
                logger.error("bgzip failed")
                return 1
            wrote_gz = True
        except FileNotFoundError:
            # Fallback: write uncompressed
            fallback = out_path.with_suffix("") if out_path.suffix == ".gz" else out_path
            with open(fallback, "w") as f:
                f.write(out)
            logger.warning("bgzip not found; wrote uncompressed VCF to %s", fallback)
    else:
        with open(out_path, "w") as f:
            f.write(out)

    if wrote_gz:
        # Index output
        try:
            subprocess.run(
                ["tabix", "-p", "vcf", str(out_path)],
                check=True,
                capture_output=True,
                timeout=30,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass  # Index optional

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Filter VCF to PGx gene regions for SynthaTrial."
    )
    parser.add_argument("input_vcf", help="Input VCF (bgzipped, .tbi required)")
    parser.add_argument("output_vcf", help="Output VCF (.vcf or .vcf.gz)")
    parser.add_argument(
        "--build",
        choices=["GRCh37", "GRCh38"],
        default="GRCh37",
        help="Reference genome build (default: GRCh37)",
    )
    parser.add_argument(
        "--chr-prefix",
        action="store_true",
        help="Use chr-prefixed chromosomes (chr1, chr10, etc.)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not Path(args.input_vcf).exists():
        logger.error("Input VCF not found: %s", args.input_vcf)
        return 1

    tbi = f"{args.input_vcf}.tbi"
    if not Path(tbi).exists():
        logger.error("Tabix index not found: %s. Run: tabix -p vcf %s", tbi, args.input_vcf)
        return 1

    regions = PGX_REGIONS_GRCH38 if args.build == "GRCh38" else PGX_REGIONS_GRCH37
    logger.info("Extracting %d PGx regions (%s) from %s", len(regions), args.build, args.input_vcf)
    return run_tabix(
        args.input_vcf,
        args.output_vcf,
        regions,
        chr_prefix=args.chr_prefix,
    )


if __name__ == "__main__":
    sys.exit(main())
