#!/usr/bin/env python3
"""
PGx Tool Comparison Benchmark Runner

Compares Anukriti's allele calling against PharmCAT, Aldy, and Stargazer
using GeT-RM consensus truth sets and expanded synthetic cohorts.

Usage:
    python scripts/run_benchmark_comparison.py                    # Full benchmark
    python scripts/run_benchmark_comparison.py --gene CYP2C19     # Single gene
    python scripts/run_benchmark_comparison.py --expanded 200      # 200 patients/pop
    python scripts/run_benchmark_comparison.py --latex              # Output LaTeX tables
    python scripts/run_benchmark_comparison.py --output results.json
"""

import argparse
import json
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.benchmark.ablation_study import (
    format_ablation_results,
    generate_ablation_latex,
    run_ablation_study,
)
from src.benchmark.concordance import compute_actionability_metrics
from src.benchmark.expanded_validation import (
    format_expanded_results,
    generate_latex_population_table,
    run_expanded_validation,
    run_full_expanded_validation,
)
from src.benchmark.getrm_truth import (
    GETRM_TRUTH_SETS,
    get_all_sample_ids,
    get_population_distribution,
)
from src.benchmark.tool_comparison import BenchmarkRunner


def main():
    parser = argparse.ArgumentParser(
        description="Run PGx tool comparison benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--gene",
        help="Run benchmark for a specific gene only (e.g., CYP2C19)",
    )
    parser.add_argument(
        "--expanded",
        type=int,
        default=100,
        metavar="N",
        help="Number of synthetic patients per population for expanded validation (default: 100)",
    )
    parser.add_argument(
        "--latex",
        action="store_true",
        help="Output LaTeX tables for paper",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Save results to JSON file",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    args = parser.parse_args()

    print("=" * 80)
    print("ANUKRITI PGx TOOL COMPARISON BENCHMARK")
    print("=" * 80)

    # --- Part 1: GeT-RM Truth Set Benchmark ---
    print("\n[1/3] GeT-RM Reference Material Benchmark")
    print(f"  Samples: {len(get_all_sample_ids())} unique IDs")
    print(f"  Population distribution: {get_population_distribution()}")
    print(f"  Genes: {list(GETRM_TRUTH_SETS.keys())}")
    print()

    runner = BenchmarkRunner()
    start = time.time()

    if args.gene:
        runner.run_gene_benchmark(args.gene.upper())
    else:
        runner.run_all_genes()

    getrm_time = time.time() - start
    print(runner.generate_comparison_table())

    if args.latex:
        print("\n--- LaTeX Tool Comparison Table ---")
        print(runner.generate_latex_table())

    # --- Part 2: Expanded Population Validation ---
    print(
        f"\n[2/3] Expanded Population Validation ({args.expanded} patients/population)"
    )

    start = time.time()
    if args.gene:
        exp_results = {
            args.gene.upper(): run_expanded_validation(
                args.gene.upper(), args.expanded, seed=args.seed
            )
        }
    else:
        exp_results = run_full_expanded_validation(args.expanded, seed=args.seed)

    exp_time = time.time() - start
    print(format_expanded_results(exp_results))

    if args.latex:
        print("\n--- LaTeX Population Validation Table ---")
        print(generate_latex_population_table(exp_results))

    # --- Part 3: Ablation Study ---
    print(f"\n[3/4] Ablation Study (component contribution analysis)")
    ablation_result = run_ablation_study(seed=args.seed)
    print(format_ablation_results(ablation_result))

    if args.latex:
        print("\n--- LaTeX Ablation Table ---")
        print(generate_ablation_latex(ablation_result))

    # --- Part 4: Summary ---
    total_patients = sum(r.total_patients for r in exp_results.values())
    getrm_patients = sum(r.anukriti_metrics.total_samples for r in runner.results)

    print("\n[4/4] Summary")
    print(f"  GeT-RM benchmark: {getrm_patients} samples, {getrm_time:.2f}s")
    print(f"  Expanded validation: {total_patients} patients, {exp_time:.2f}s")
    print(f"  Total validated: {getrm_patients + total_patients}")
    print()

    # Key findings
    if runner.results:
        total_conc = sum(r.anukriti_metrics.concordant for r in runner.results)
        total_called = total_conc + sum(
            r.anukriti_metrics.discordant for r in runner.results
        )
        if total_called > 0:
            overall_getrm = total_conc / total_called
            print(f"  GeT-RM overall concordance: {overall_getrm:.1%}")

    for gene, r in exp_results.items():
        print(
            f"  {gene} expanded: {r.overall_concordance:.1%} diplotype, "
            f"{r.phenotype_concordance:.1%} phenotype"
        )

    # --- Save results ---
    if args.output:
        all_results = {
            "getrm_benchmark": {
                "results": [r.to_dict() for r in runner.results],
                "comparison_table": runner.generate_comparison_table(),
            },
            "expanded_validation": {
                gene: r.to_dict() for gene, r in exp_results.items()
            },
            "ablation_study": ablation_result.to_dict(),
            "summary": {
                "getrm_samples": getrm_patients,
                "expanded_patients": total_patients,
                "total_validated": getrm_patients + total_patients,
            },
        }
        if args.latex:
            all_results["latex"] = {
                "tool_comparison": runner.generate_latex_table(),
                "population_validation": generate_latex_population_table(exp_results),
            }
        with open(args.output, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\n  Results saved to: {args.output}")

    print()


if __name__ == "__main__":
    main()
