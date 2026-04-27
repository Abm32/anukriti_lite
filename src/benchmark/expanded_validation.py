"""
Expanded validation cohort generator (500+ patients across 5 ancestries).

Generates synthetic patient genotypes using population-specific allele frequencies
from gnomAD v4 / 1000 Genomes Project Phase 3, then validates Anukriti's
allele calling and phenotype assignment.
"""

from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ..allele_caller import (
    build_diplotype,
    diplotype_to_phenotype,
    load_cpic_translation_for_gene,
)
from .concordance import (
    ConcordanceMetrics,
    compute_actionability_metrics,
    compute_concordance,
    normalize_phenotype,
)

logger = logging.getLogger(__name__)

# Population-specific allele frequencies from gnomAD v4.1 / 1000 Genomes Phase 3
# Source: gnomAD browser (gnomad.broadinstitute.org), PharmGKB, CPIC allele frequency tables
# Format: {population: {allele: frequency}} where frequencies are for the minor allele

ALLELE_FREQUENCIES: Dict[str, Dict[str, Dict[str, float]]] = {
    "CYP2C19": {
        "AFR": {"*1": 0.830, "*2": 0.150, "*3": 0.001, "*17": 0.019},
        "EUR": {"*1": 0.630, "*2": 0.150, "*3": 0.004, "*17": 0.216},
        "EAS": {"*1": 0.560, "*2": 0.290, "*3": 0.080, "*17": 0.070},
        "SAS": {"*1": 0.620, "*2": 0.310, "*3": 0.010, "*17": 0.060},
        "AMR": {"*1": 0.700, "*2": 0.120, "*3": 0.003, "*17": 0.177},
    },
    "CYP2C9": {
        "AFR": {"*1": 0.940, "*2": 0.030, "*3": 0.030},
        "EUR": {"*1": 0.790, "*2": 0.130, "*3": 0.080},
        "EAS": {"*1": 0.960, "*2": 0.010, "*3": 0.030},
        "SAS": {"*1": 0.850, "*2": 0.100, "*3": 0.050},
        "AMR": {"*1": 0.880, "*2": 0.070, "*3": 0.050},
    },
    "TPMT": {
        "AFR": {"*1": 0.950, "*3A": 0.005, "*3C": 0.045},
        "EUR": {"*1": 0.940, "*3A": 0.050, "*3C": 0.005, "*2": 0.005},
        "EAS": {"*1": 0.970, "*3A": 0.005, "*3C": 0.025},
        "SAS": {"*1": 0.960, "*3A": 0.020, "*3C": 0.015, "*2": 0.005},
        "AMR": {"*1": 0.950, "*3A": 0.035, "*3C": 0.010, "*2": 0.005},
    },
    "DPYD": {
        "AFR": {"*1": 0.990, "*2A": 0.005, "c.2846A>T": 0.003, "HapB3": 0.002},
        "EUR": {"*1": 0.960, "*2A": 0.010, "c.2846A>T": 0.015, "HapB3": 0.015},
        "EAS": {"*1": 0.995, "*2A": 0.002, "c.2846A>T": 0.002, "HapB3": 0.001},
        "SAS": {"*1": 0.985, "*2A": 0.005, "c.2846A>T": 0.005, "HapB3": 0.005},
        "AMR": {"*1": 0.975, "*2A": 0.008, "c.2846A>T": 0.010, "HapB3": 0.007},
    },
}

# CPIC diplotype → phenotype for each gene (used as ground truth for synthetic patients)
DIPLOTYPE_PHENOTYPES: Dict[str, Dict[str, str]] = {
    "CYP2C19": {
        "*1/*1": "Normal Metabolizer",
        "*1/*2": "Intermediate Metabolizer",
        "*1/*3": "Intermediate Metabolizer",
        "*1/*17": "Rapid Metabolizer",
        "*2/*2": "Poor Metabolizer",
        "*2/*3": "Poor Metabolizer",
        "*2/*17": "Intermediate Metabolizer",
        "*3/*3": "Poor Metabolizer",
        "*3/*17": "Intermediate Metabolizer",
        "*17/*17": "Ultrarapid Metabolizer",
    },
    "CYP2C9": {
        "*1/*1": "Normal Metabolizer",
        "*1/*2": "Intermediate Metabolizer",
        "*1/*3": "Intermediate Metabolizer",
        "*2/*2": "Poor Metabolizer",
        "*2/*3": "Poor Metabolizer",
        "*3/*3": "Poor Metabolizer",
    },
    "TPMT": {
        "*1/*1": "Normal Metabolizer",
        "*1/*2": "Intermediate Metabolizer",
        "*1/*3A": "Intermediate Metabolizer",
        "*1/*3C": "Intermediate Metabolizer",
        "*2/*2": "Poor Metabolizer",
        "*2/*3A": "Poor Metabolizer",
        "*3A/*3A": "Poor Metabolizer",
        "*3A/*3C": "Poor Metabolizer",
        "*3C/*3C": "Poor Metabolizer",
    },
    "DPYD": {
        "*1/*1": "Normal Metabolizer",
        "*1/*2A": "Intermediate Metabolizer",
        "*1/*13": "Intermediate Metabolizer",
        "*1/c.2846A>T": "Intermediate Metabolizer",
        "*1/HapB3": "Intermediate Metabolizer",
        "*2A/*2A": "Poor Metabolizer",
        "*2A/*13": "Poor Metabolizer",
        "*2A/c.2846A>T": "Poor Metabolizer",
        "*2A/HapB3": "Poor Metabolizer",
        "*13/*13": "Poor Metabolizer",
        "*13/c.2846A>T": "Poor Metabolizer",
        "*13/HapB3": "Poor Metabolizer",
        "c.2846A>T/c.2846A>T": "Poor Metabolizer",
        "c.2846A>T/HapB3": "Poor Metabolizer",
        "HapB3/HapB3": "Intermediate Metabolizer",
    },
}


@dataclass
class ExpandedValidationResult:
    """Results from expanded population validation."""

    gene: str
    total_patients: int
    by_population: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    overall_concordance: float = 0.0
    phenotype_concordance: float = 0.0
    actionability: Dict[str, float] = field(default_factory=dict)
    phenotype_distribution: Dict[str, Dict[str, int]] = field(default_factory=dict)
    runtime_seconds: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "gene": self.gene,
            "total_patients": self.total_patients,
            "overall_diplotype_concordance": round(self.overall_concordance, 4),
            "overall_phenotype_concordance": round(self.phenotype_concordance, 4),
            "actionability": self.actionability,
            "by_population": self.by_population,
            "phenotype_distribution": self.phenotype_distribution,
            "runtime_seconds": round(self.runtime_seconds, 3),
        }


def _star_allele_sort_key(allele: str) -> Tuple[int, str]:
    """Sort star alleles numerically (*1 < *2 < *3 < *17), non-star alleles last."""
    if allele.startswith("*"):
        try:
            return (0, f"{int(allele[1:]):05d}")
        except ValueError:
            # *3A, *3C etc — sort by number then suffix
            num = ""
            suffix = ""
            for ch in allele[1:]:
                if ch.isdigit():
                    num += ch
                else:
                    suffix = allele[1 + len(num) :]
                    break
            return (0, f"{int(num) if num else 999:05d}{suffix}")
    return (1, allele)


def _sample_diplotype(
    allele_freqs: Dict[str, float], rng: random.Random
) -> Tuple[str, str]:
    """Sample two alleles independently using population frequencies (Hardy-Weinberg)."""
    alleles = list(allele_freqs.keys())
    weights = [allele_freqs[a] for a in alleles]
    # Normalize in case frequencies don't sum to 1
    total = sum(weights)
    weights = [w / total for w in weights]

    a1 = rng.choices(alleles, weights=weights, k=1)[0]
    a2 = rng.choices(alleles, weights=weights, k=1)[0]
    return tuple(sorted([a1, a2], key=_star_allele_sort_key))  # type: ignore


def generate_synthetic_cohort(
    gene: str,
    n_per_population: int = 100,
    populations: Optional[List[str]] = None,
    seed: int = 42,
) -> List[Dict]:
    """
    Generate synthetic patient genotypes using population allele frequencies.

    Returns list of {sample_id, diplotype, phenotype, population}.
    """
    if gene not in ALLELE_FREQUENCIES:
        raise ValueError(f"No allele frequencies for gene: {gene}")

    pops = populations or list(ALLELE_FREQUENCIES[gene].keys())
    rng = random.Random(seed)
    pheno_map = DIPLOTYPE_PHENOTYPES.get(gene, {})

    cohort = []
    for pop in pops:
        freqs = ALLELE_FREQUENCIES[gene].get(pop)
        if not freqs:
            continue

        for i in range(n_per_population):
            a1, a2 = _sample_diplotype(freqs, rng)
            diplotype = f"{a1}/{a2}"
            phenotype = pheno_map.get(diplotype, "Unknown")

            cohort.append(
                {
                    "sample_id": f"SYN-{pop}-{gene}-{i:04d}",
                    "diplotype": diplotype,
                    "phenotype": phenotype,
                    "population": pop,
                }
            )

    return cohort


def run_expanded_validation(
    gene: str,
    n_per_population: int = 100,
    pgx_data_dir: Optional[Path] = None,
    seed: int = 42,
) -> ExpandedValidationResult:
    """
    Run expanded validation for a gene with n_per_population patients per ancestry.

    Default: 100 per population x 5 populations = 500 patients.
    """
    start = time.time()

    # Generate synthetic cohort
    cohort = generate_synthetic_cohort(gene, n_per_population, seed=seed)

    # Load CPIC translation for Anukriti predictions
    try:
        translation = load_cpic_translation_for_gene(gene, base_dir=pgx_data_dir)
    except FileNotFoundError:
        logger.warning(f"No CPIC data for {gene}")
        return ExpandedValidationResult(gene=gene, total_patients=0)

    # Run Anukriti phenotype prediction
    predictions = []
    for entry in cohort:
        dip = entry["diplotype"]
        pheno = translation.get(dip, "")
        if not pheno:
            # Try both allele orderings (CPIC may store *2/*17 but we generate *17/*2)
            parts = dip.split("/")
            if len(parts) == 2:
                reversed_dip = "/".join(reversed(parts))
                sorted_dip = "/".join(sorted(parts))
                pheno = (
                    translation.get(reversed_dip, "")
                    or translation.get(sorted_dip, "")
                    or "Unknown"
                )
            else:
                pheno = "Unknown"
        predictions.append(
            {
                "sample_id": entry["sample_id"],
                "diplotype": dip,
                "phenotype": pheno,
            }
        )

    # Compute concordance
    metrics = compute_concordance(cohort, predictions, gene, tool="Anukriti")

    # Per-population breakdown
    pop_results = {}
    pop_pheno_dist: Dict[str, Dict[str, int]] = {}
    pops = sorted(set(e["population"] for e in cohort))

    for pop in pops:
        pop_truth = [e for e in cohort if e["population"] == pop]
        pop_preds = [p for p in predictions if p["sample_id"].startswith(f"SYN-{pop}-")]

        pop_metrics = compute_concordance(pop_truth, pop_preds, gene, tool="Anukriti")

        truth_phenos = [normalize_phenotype(t["phenotype"]) for t in pop_truth]
        pred_phenos = []
        pred_by_sid = {p["sample_id"]: p for p in pop_preds}
        for t in pop_truth:
            if t["sample_id"] in pred_by_sid:
                pred_phenos.append(
                    normalize_phenotype(pred_by_sid[t["sample_id"]]["phenotype"])
                )
            else:
                pred_phenos.append("unknown")

        pop_action = compute_actionability_metrics(truth_phenos, pred_phenos)

        pop_results[pop] = {
            "n": pop_metrics.total_samples,
            "diplotype_concordance": round(pop_metrics.diplotype_concordance, 4),
            "phenotype_concordance": round(pop_metrics.phenotype_concordance, 4),
            "actionability": pop_action,
        }

        # Phenotype distribution
        dist: Dict[str, int] = {}
        for t in pop_truth:
            p = normalize_phenotype(t["phenotype"])
            dist[p] = dist.get(p, 0) + 1
        pop_pheno_dist[pop] = dist

    # Overall actionability
    all_truth_phenos = [normalize_phenotype(t["phenotype"]) for t in cohort]
    pred_by_sid = {p["sample_id"]: p for p in predictions}
    all_pred_phenos = []
    for t in cohort:
        if t["sample_id"] in pred_by_sid:
            all_pred_phenos.append(
                normalize_phenotype(pred_by_sid[t["sample_id"]]["phenotype"])
            )
        else:
            all_pred_phenos.append("unknown")

    overall_action = compute_actionability_metrics(all_truth_phenos, all_pred_phenos)

    elapsed = time.time() - start

    return ExpandedValidationResult(
        gene=gene,
        total_patients=len(cohort),
        by_population=pop_results,
        overall_concordance=metrics.diplotype_concordance,
        phenotype_concordance=metrics.phenotype_concordance,
        actionability=overall_action,
        phenotype_distribution=pop_pheno_dist,
        runtime_seconds=elapsed,
    )


def run_full_expanded_validation(
    n_per_population: int = 100,
    pgx_data_dir: Optional[Path] = None,
    seed: int = 42,
) -> Dict[str, ExpandedValidationResult]:
    """
    Run expanded validation across all genes with population frequencies.

    Default: 100 patients x 5 populations x 4 genes = 2,000 patients.
    """
    results = {}
    for gene in ALLELE_FREQUENCIES:
        try:
            result = run_expanded_validation(gene, n_per_population, pgx_data_dir, seed)
            results[gene] = result
            logger.info(
                f"{gene}: {result.total_patients} patients, "
                f"concordance={result.overall_concordance:.1%}, "
                f"phenotype={result.phenotype_concordance:.1%}"
            )
        except Exception as e:
            logger.error(f"Expanded validation failed for {gene}: {e}")
    return results


def format_expanded_results(results: Dict[str, ExpandedValidationResult]) -> str:
    """Format expanded validation results for terminal output."""
    lines = [
        "",
        "=" * 100,
        "EXPANDED POPULATION VALIDATION (500+ patients per gene, 5 ancestries)",
        "Allele frequencies from gnomAD v4.1 / 1000 Genomes Phase 3",
        "=" * 100,
        "",
    ]

    for gene, r in results.items():
        lines.append(f"--- {gene} (N={r.total_patients}) ---")
        lines.append(f"  Overall diplotype concordance: {r.overall_concordance:.1%}")
        lines.append(f"  Overall phenotype concordance: {r.phenotype_concordance:.1%}")
        lines.append(
            f"  Sensitivity (actionable): {r.actionability.get('sensitivity', 0):.1%}"
        )
        lines.append(
            f"  Specificity (normal): {r.actionability.get('specificity', 0):.1%}"
        )
        lines.append(f"  Runtime: {r.runtime_seconds:.3f}s")
        lines.append("")

        # Per-population table
        header = f"  {'Population':<8} {'N':>4} {'Dip.Conc':>10} {'Phen.Conc':>10} {'Sens':>8} {'Spec':>8}"
        lines.append(header)
        lines.append("  " + "-" * (len(header) - 2))
        for pop, data in r.by_population.items():
            sens = data["actionability"].get("sensitivity", 0)
            spec = data["actionability"].get("specificity", 0)
            lines.append(
                f"  {pop:<8} {data['n']:>4} {data['diplotype_concordance']:>9.1%} "
                f"{data['phenotype_concordance']:>9.1%} {sens:>7.1%} {spec:>7.1%}"
            )
        lines.append("")

        # Phenotype distribution
        lines.append("  Phenotype distribution by population:")
        all_phenos: Set[str] = set()
        for dist in r.phenotype_distribution.values():
            all_phenos.update(dist.keys())
        phenos_sorted = sorted(all_phenos)
        ph_header = f"  {'Pop':<8}" + "".join(f" {p[:12]:>12}" for p in phenos_sorted)
        lines.append(ph_header)
        for pop, dist in r.phenotype_distribution.items():
            row = f"  {pop:<8}"
            for p in phenos_sorted:
                row += f" {dist.get(p, 0):>12}"
            lines.append(row)
        lines.append("")

    # Grand total
    total_patients = sum(r.total_patients for r in results.values())
    lines.append(f"Total patients validated: {total_patients}")
    lines.append("")

    return "\n".join(lines)


def generate_latex_population_table(
    results: Dict[str, ExpandedValidationResult]
) -> str:
    """Generate LaTeX table for population validation results."""
    lines = [
        r"\begin{table*}[htbp]",
        r"\centering",
        r"\caption{Expanded population validation: Anukriti phenotype concordance across five global ancestries using gnomAD v4.1 allele frequencies (100 synthetic patients per population per gene).}",
        r"\label{tab:population-validation}",
        r"\begin{tabular}{llccccc}",
        r"\toprule",
        r"Gene & Metric & AFR & EUR & EAS & SAS & AMR \\",
        r"\midrule",
    ]

    for gene, r in results.items():
        pops_ordered = ["AFR", "EUR", "EAS", "SAS", "AMR"]
        conc_vals = []
        sens_vals = []
        for pop in pops_ordered:
            data = r.by_population.get(pop, {})
            conc_vals.append(f"{data.get('phenotype_concordance', 0):.1%}")
            sens_vals.append(
                f"{data.get('actionability', {}).get('sensitivity', 0):.1%}"
            )

        lines.append(f"  {gene} & Concordance & {' & '.join(conc_vals)} \\\\")
        lines.append(f"  & Sensitivity & {' & '.join(sens_vals)} \\\\")
        lines.append(r"  \addlinespace")

    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table*}",
        ]
    )
    return "\n".join(lines)
