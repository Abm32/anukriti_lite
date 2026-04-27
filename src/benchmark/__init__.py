"""
Benchmarking framework for comparing Anukriti against established PGx tools.

Compares allele calling concordance against:
- PharmCAT (CPIC Named Allele Matcher)
- Aldy (ILP-based star allele caller)
- Stargazer (haplotype-based caller)

Uses GeT-RM consensus genotypes as ground truth.
"""

from .ablation_study import AblationResult, run_ablation_study
from .clinical_cases import (
    ClinicalCase,
    ClinicalValidationResult,
    load_clinical_cases,
    validate_clinical_cases,
)
from .concordance import ConcordanceMetrics, compute_concordance
from .getrm_truth import GETRM_TRUTH_SETS, get_truth_for_gene
from .tool_comparison import BenchmarkRunner, ToolComparisonResult

__all__ = [
    "AblationResult",
    "run_ablation_study",
    "ClinicalCase",
    "ClinicalValidationResult",
    "load_clinical_cases",
    "validate_clinical_cases",
    "ConcordanceMetrics",
    "compute_concordance",
    "GETRM_TRUTH_SETS",
    "get_truth_for_gene",
    "BenchmarkRunner",
    "ToolComparisonResult",
]
