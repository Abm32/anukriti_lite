"""
Statistical concordance metrics for PGx tool benchmarking.

Implements standard pharmacogenomics benchmarking metrics from:
- Halman et al. 2024 (PMC11315677)
- Twesigomwe et al. 2020 (Nature npj Genomic Medicine)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class ConcordanceMetrics:
    """Full concordance report for a gene or tool comparison."""

    gene: str
    tool: str
    total_samples: int = 0
    concordant: int = 0
    discordant: int = 0
    no_call_truth: int = 0
    no_call_test: int = 0

    # Per-phenotype metrics
    phenotype_concordant: int = 0
    phenotype_discordant: int = 0

    # Detailed mismatches for reporting
    mismatches: List[Dict] = field(default_factory=list)

    @property
    def call_rate(self) -> float:
        """Fraction of samples receiving a genotype call."""
        callable = self.total_samples - self.no_call_test
        return callable / self.total_samples if self.total_samples > 0 else 0.0

    @property
    def diplotype_concordance(self) -> float:
        """Fraction of called samples matching truth set diplotype."""
        called = self.concordant + self.discordant
        return self.concordant / called if called > 0 else 0.0

    @property
    def phenotype_concordance(self) -> float:
        """Fraction of called samples matching truth set phenotype."""
        called = self.phenotype_concordant + self.phenotype_discordant
        return self.phenotype_concordant / called if called > 0 else 0.0

    @property
    def sensitivity(self) -> Optional[float]:
        """True positive rate for actionable phenotypes (non-Normal)."""
        # Computed from mismatches; returns None if not enough data
        return None  # Calculated in compute_concordance with full confusion matrix

    def wilson_ci(self, confidence: float = 0.95) -> Tuple[float, float]:
        """Wilson score 95% confidence interval for diplotype concordance."""
        n = self.concordant + self.discordant
        if n == 0:
            return (0.0, 0.0)
        p = self.diplotype_concordance
        z = 1.96 if confidence == 0.95 else 2.576  # 95% or 99%
        denom = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denom
        spread = z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
        return (max(0.0, center - spread), min(1.0, center + spread))

    def to_dict(self) -> Dict:
        ci_low, ci_high = self.wilson_ci()
        return {
            "gene": self.gene,
            "tool": self.tool,
            "total_samples": self.total_samples,
            "concordant": self.concordant,
            "discordant": self.discordant,
            "no_call_test": self.no_call_test,
            "call_rate": round(self.call_rate, 4),
            "diplotype_concordance": round(self.diplotype_concordance, 4),
            "phenotype_concordance": round(self.phenotype_concordance, 4),
            "ci_95_low": round(ci_low, 4),
            "ci_95_high": round(ci_high, 4),
            "mismatches": self.mismatches,
        }


def normalize_diplotype(diplotype: str) -> str:
    """
    Normalize diplotype for comparison.

    Handles:
    - Allele ordering (*2/*1 → *1/*2)
    - Whitespace
    - Bracket notation ([*6+*14] treated as single allele)
    """
    if not diplotype or diplotype.lower() in ("unknown", "no call", "n/a", ""):
        return ""
    d = diplotype.strip()
    # Split on / but preserve bracket notation
    parts = []
    current = ""
    depth = 0
    for ch in d:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if ch == "/" and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current.strip())
    # Sort alleles lexicographically for consistent comparison
    parts.sort()
    return "/".join(parts)


def normalize_phenotype(phenotype: str) -> str:
    """Normalize phenotype strings for comparison across tools."""
    p = phenotype.strip().lower()
    # Map common variations to canonical forms
    mappings = {
        "ultrarapid metabolizer": "ultrarapid_metabolizer",
        "ultra-rapid metabolizer": "ultrarapid_metabolizer",
        "normal metabolizer": "normal_metabolizer",
        "extensive metabolizer": "normal_metabolizer",
        "normal function": "normal_function",
        "intermediate metabolizer": "intermediate_metabolizer",
        "poor metabolizer": "poor_metabolizer",
        "rapid metabolizer": "rapid_metabolizer",
        "decreased function": "decreased_function",
        "increased function": "increased_function",
        "poor function": "poor_function",
        "normal sensitivity": "normal_sensitivity",
        "intermediate sensitivity": "intermediate_sensitivity",
        "high sensitivity": "high_sensitivity",
        "possible intermediate metabolizer": "intermediate_metabolizer",
        "likely intermediate metabolizer": "intermediate_metabolizer",
        "likely poor metabolizer": "poor_metabolizer",
    }
    for key, val in mappings.items():
        if key in p:
            return val
    return p.replace(" ", "_").replace("-", "_")


def compute_concordance(
    truth: List[Dict],
    predictions: List[Dict],
    gene: str,
    tool: str = "Anukriti",
) -> ConcordanceMetrics:
    """
    Compute concordance between truth set and tool predictions.

    truth: list of {sample_id, diplotype, phenotype}
    predictions: list of {sample_id, diplotype, phenotype}

    Returns ConcordanceMetrics with full statistics.
    """
    metrics = ConcordanceMetrics(gene=gene, tool=tool)

    # Index predictions by sample_id
    pred_by_sample = {p["sample_id"]: p for p in predictions}

    for t in truth:
        sid = t["sample_id"]
        metrics.total_samples += 1

        truth_dip = normalize_diplotype(t.get("diplotype", ""))
        truth_pheno = normalize_phenotype(t.get("phenotype", ""))

        if not truth_dip:
            metrics.no_call_truth += 1
            continue

        if sid not in pred_by_sample:
            metrics.no_call_test += 1
            continue

        pred = pred_by_sample[sid]
        pred_dip = normalize_diplotype(pred.get("diplotype", ""))
        pred_pheno = normalize_phenotype(pred.get("phenotype", ""))

        if not pred_dip:
            metrics.no_call_test += 1
            continue

        # Diplotype concordance
        if truth_dip == pred_dip:
            metrics.concordant += 1
        else:
            metrics.discordant += 1
            metrics.mismatches.append(
                {
                    "sample_id": sid,
                    "truth_diplotype": t.get("diplotype", ""),
                    "pred_diplotype": pred.get("diplotype", ""),
                    "truth_phenotype": t.get("phenotype", ""),
                    "pred_phenotype": pred.get("phenotype", ""),
                }
            )

        # Phenotype concordance (more lenient — different diplotypes can yield same phenotype)
        if truth_pheno and pred_pheno:
            if truth_pheno == pred_pheno:
                metrics.phenotype_concordant += 1
            else:
                metrics.phenotype_discordant += 1

    return metrics


def compute_confusion_matrix(
    truth_labels: List[str],
    pred_labels: List[str],
) -> Dict[str, Dict[str, int]]:
    """
    Build confusion matrix for phenotype classification.

    Returns nested dict: {true_label: {pred_label: count}}
    """
    labels = sorted(set(truth_labels + pred_labels))
    matrix: Dict[str, Dict[str, int]] = {
        lb: {lb2: 0 for lb2 in labels} for lb in labels
    }
    for t, p in zip(truth_labels, pred_labels):
        matrix[t][p] += 1
    return matrix


def compute_actionability_metrics(
    truth_labels: List[str],
    pred_labels: List[str],
) -> Dict[str, float]:
    """
    Compute sensitivity/specificity for actionable phenotypes.

    Actionable = any non-normal phenotype (intermediate, poor, ultrarapid).
    This is clinically important: missing a poor metabolizer is dangerous.
    """
    normal = {"normal_metabolizer", "normal_function", "extensive_metabolizer"}

    tp = fp = tn = fn = 0
    for t, p in zip(truth_labels, pred_labels):
        t_act = t not in normal
        p_act = p not in normal
        if t_act and p_act:
            tp += 1
        elif t_act and not p_act:
            fn += 1
        elif not t_act and p_act:
            fp += 1
        else:
            tn += 1

    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    ppv = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    npv = tn / (tn + fn) if (tn + fn) > 0 else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) > 0 else 0.0

    return {
        "sensitivity": round(sensitivity, 4),
        "specificity": round(specificity, 4),
        "ppv": round(ppv, 4),
        "npv": round(npv, 4),
        "f1_score": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }
