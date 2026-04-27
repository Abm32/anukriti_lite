#!/usr/bin/env python3
"""
Run head-to-head comparison of Anukriti vs PharmCAT on 1000 Genomes VCFs.

Usage:
    python scripts/run_pharmcat_comparison.py --samples 5
    python scripts/run_pharmcat_comparison.py --samples 10 --output results.json --latex
    python scripts/run_pharmcat_comparison.py --sample-ids HG00096,HG00097,NA12878
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.benchmark.pharmcat_comparison import (
    PharmCATComparisonResult,
    compare_results,
    create_grch38_vcf,
    extract_sample_variants,
    find_vcf_for_gene,
    parse_pharmcat_phenotypes,
    run_anukriti_on_variants,
    run_pharmcat_docker,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

GENOMES_DIR = Path(__file__).resolve().parent.parent / "data" / "genomes"

# Well-characterized 1000 Genomes samples from GeT-RM
DEFAULT_SAMPLES = [
    "HG00096",  # EUR
    "HG00097",  # EUR
    "HG00099",  # EUR
    "NA12878",  # EUR (reference)
    "NA18519",  # AFR
    "NA18861",  # EAS
    "NA19785",  # AFR
    "HG00436",  # SAS
    "NA18526",  # EAS
    "NA19920",  # AFR
]

# Genes to compare (PharmCAT can call these directly)
COMPARISON_GENES = ["CYP2C19", "CYP2C9", "TPMT", "DPYD", "SLCO1B1", "VKORC1", "UGT1A1"]


def run_comparison(
    sample_ids: list[str],
    genomes_dir: Path,
    output_path: str | None = None,
    latex: bool = False,
) -> PharmCATComparisonResult:
    """Run full Anukriti vs PharmCAT comparison."""
    result = PharmCATComparisonResult(genes_compared=COMPARISON_GENES)

    for sample_id in sample_ids:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing sample: {sample_id}")
        logger.info(f"{'='*60}")

        # Step 1: Extract variants for all genes
        all_variants: dict[str, dict] = {}
        for gene in COMPARISON_GENES:
            vcf_path = find_vcf_for_gene(gene, genomes_dir)
            if vcf_path is None:
                logger.warning(f"No VCF found for {gene} (chr{gene})")
                continue

            logger.info(f"  Extracting {gene} variants from {vcf_path.name}...")
            variants = extract_sample_variants(str(vcf_path), sample_id, gene)
            if variants:
                all_variants[gene] = variants
                logger.info(f"    Found {len(variants)} PGx variants")
            else:
                logger.info(f"    No PGx variants found (wildtype)")

        if not all_variants:
            logger.warning(f"No variants found for {sample_id}, skipping")
            continue

        # Step 2: Run Anukriti
        logger.info(f"  Running Anukriti allele caller...")
        anukriti_results = run_anukriti_on_variants(all_variants)
        for gene, res in anukriti_results.items():
            logger.info(f"    {gene}: {res['diplotype']} → {res['phenotype']}")

        # Step 3: Create GRCh38 VCF and run PharmCAT
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            vcf_38 = tmpdir_path / f"{sample_id}.vcf"
            output_dir = tmpdir_path / "output"

            logger.info(f"  Creating GRCh38 VCF for PharmCAT...")
            if create_grch38_vcf(all_variants, sample_id, vcf_38):
                logger.info(f"  Running PharmCAT via Docker...")
                pharmcat_raw = run_pharmcat_docker(vcf_38, output_dir)

                if pharmcat_raw:
                    pharmcat_results = parse_pharmcat_phenotypes(pharmcat_raw)
                    for gene, res in pharmcat_results.items():
                        if gene in COMPARISON_GENES:
                            logger.info(
                                f"    PharmCAT {gene}: {res['diplotype']} → {res['phenotype']}"
                            )
                else:
                    logger.warning("  PharmCAT returned no results")
                    pharmcat_results = {}
            else:
                logger.warning("  Failed to create GRCh38 VCF")
                pharmcat_results = {}

        # Step 4: Compare
        comparison = compare_results(anukriti_results, pharmcat_results, sample_id)
        result.samples.append(comparison)
        logger.info(
            f"  Result: {comparison.concordant_genes}/{comparison.total_genes} concordant"
        )

    # Print results
    print(result.summary_table())

    if latex:
        print("\nLaTeX Table:")
        print(result.generate_latex_table())

    if output_path:
        with open(output_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        logger.info(f"Results saved to {output_path}")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Anukriti vs PharmCAT head-to-head comparison"
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=5,
        help="Number of samples to compare (default: 5)",
    )
    parser.add_argument(
        "--sample-ids",
        type=str,
        default=None,
        help="Comma-separated sample IDs (overrides --samples)",
    )
    parser.add_argument(
        "--genomes-dir",
        type=str,
        default=str(GENOMES_DIR),
        help="Path to directory with 1000 Genomes VCFs",
    )
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    parser.add_argument("--latex", action="store_true", help="Generate LaTeX table")
    args = parser.parse_args()

    if args.sample_ids:
        sample_ids = [s.strip() for s in args.sample_ids.split(",")]
    else:
        sample_ids = DEFAULT_SAMPLES[: args.samples]

    genomes_dir = Path(args.genomes_dir)
    if not genomes_dir.exists():
        logger.error(f"Genomes directory not found: {genomes_dir}")
        sys.exit(1)

    run_comparison(sample_ids, genomes_dir, args.output, args.latex)


if __name__ == "__main__":
    main()
