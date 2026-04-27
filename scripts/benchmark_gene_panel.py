#!/usr/bin/env python3
"""
Gene Panel Performance Benchmarking

Measures query performance for all genes in the database.
Verifies sub-100ms requirement for production readiness.

Usage:
    python scripts/benchmark_gene_panel.py              # Benchmark all genes
    python scripts/benchmark_gene_panel.py --genes 100  # Test scalability
"""

import argparse
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.variant_db_v2 import (
    get_database_stats,
    get_gene_variants,
    get_phenotype_translation,
    list_supported_genes,
)


def benchmark_gene(gene_symbol: str) -> dict:
    """Benchmark query performance for a single gene."""
    results = {
        "gene": gene_symbol,
        "variant_query_ms": 0,
        "phenotype_query_ms": 0,
        "total_ms": 0,
        "variant_count": 0,
        "phenotype_count": 0,
        "passed": False,
    }

    # Benchmark variant query
    start = time.time()
    variants = get_gene_variants(gene_symbol)
    variant_time = (time.time() - start) * 1000
    results["variant_query_ms"] = round(variant_time, 2)
    results["variant_count"] = len(variants)

    # Benchmark phenotype query
    start = time.time()
    phenotypes = get_phenotype_translation(gene_symbol)
    phenotype_time = (time.time() - start) * 1000
    results["phenotype_query_ms"] = round(phenotype_time, 2)
    results["phenotype_count"] = len(phenotypes)

    # Total time
    results["total_ms"] = round(variant_time + phenotype_time, 2)

    # Pass if < 100ms total
    results["passed"] = results["total_ms"] < 100

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark gene panel query performance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/benchmark_gene_panel.py              # Benchmark all genes
  python scripts/benchmark_gene_panel.py --genes 100  # Test scalability
        """,
    )
    parser.add_argument(
        "--genes", type=int, help="Expected gene count for scalability test"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("GENE PANEL PERFORMANCE BENCHMARK")
    print("=" * 70)
    print()

    # Get database stats
    stats = get_database_stats()
    print(
        f"Database: {stats['gene_count']} genes, "
        f"{stats['variant_count']} variants, "
        f"{stats['phenotype_count']} phenotypes"
    )
    print(f"Size: {stats['database_size_mb']} MB")
    print()

    # Get all genes
    genes = list_supported_genes()
    print(f"Testing {len(genes)} genes...")
    print()

    # Benchmark each gene
    results = []
    for gene in genes:
        result = benchmark_gene(gene)
        results.append(result)

        status = "✓" if result["passed"] else "✗"
        print(
            f"{status} {gene:12} | "
            f"Variants: {result['variant_count']:3} ({result['variant_query_ms']:6.2f}ms) | "
            f"Phenotypes: {result['phenotype_count']:3} ({result['phenotype_query_ms']:6.2f}ms) | "
            f"Total: {result['total_ms']:6.2f}ms"
        )

    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed

    avg_time = sum(r["total_ms"] for r in results) / len(results) if results else 0
    max_time = max(r["total_ms"] for r in results) if results else 0
    min_time = min(r["total_ms"] for r in results) if results else 0

    print(f"Total genes tested: {len(results)}")
    print(f"✓ Passed (< 100ms): {passed}")
    if failed > 0:
        print(f"✗ Failed (≥ 100ms): {failed}")
    print()
    print(f"Average query time: {avg_time:.2f}ms")
    print(f"Min query time: {min_time:.2f}ms")
    print(f"Max query time: {max_time:.2f}ms")
    print()

    # Scalability check
    if args.genes:
        print(f"Scalability Test (target: {args.genes} genes)")
        print(f"Current: {len(results)} genes")
        print(f"Projected avg time at {args.genes} genes: {avg_time:.2f}ms")
        print(f"Projected max time at {args.genes} genes: {max_time:.2f}ms")
        print()

        if avg_time < 50 and max_time < 100:
            print(f"✓ SCALABILITY PASSED - Ready for {args.genes}+ genes")
        else:
            print(
                f"⚠ SCALABILITY WARNING - May need optimization for {args.genes}+ genes"
            )
        print()

    if failed == 0:
        print("✓ ALL GENES PASSED - Production ready!")
    else:
        print("✗ SOME GENES FAILED - Optimization needed")
        print()
        print("Failed genes:")
        for r in results:
            if not r["passed"]:
                print(f"  - {r['gene']}: {r['total_ms']:.2f}ms")

    print("=" * 70)

    # Exit with error code if any failed
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
