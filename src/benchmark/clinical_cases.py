"""
Clinical case validation using published pharmacogenomics case reports.

Validates Anukriti's phenotype predictions against real-world adverse drug
reaction cases from peer-reviewed literature. Each case has a known genotype,
expected phenotype, drug involved, and documented clinical outcome.

References:
- Gasche et al. 2004 (NEJM) — CYP2D6 codeine toxicity
- Kang & Hwang 2016 (Int J Cardiol) — CYP2C19 clopidogrel resistance
- Johnson & Cavallari 2014 (Case Rep Genet) — CYP2C9/VKORC1 warfarin
- Fidai et al. 2019 (Autops Case Rep) — DPYD 5-FU fatal toxicity
- SEARCH Collaborative Group 2008 (NEJM) — SLCO1B1 statin myopathy
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .concordance import normalize_phenotype

logger = logging.getLogger(__name__)

# Default path to published cases JSON
_DEFAULT_CASES_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "clinical_cases"
    / "published_cases.json"
)


@dataclass
class ClinicalCase:
    """A single published clinical case report."""

    case_id: str
    gene: str
    diplotype: str
    phenotype: str
    drug: str
    clinical_outcome: str
    expected_risk: str
    patient_summary: str
    reference: str
    pmid: Optional[str] = None


@dataclass
class ClinicalValidationResult:
    """Results from validating Anukriti against published clinical cases."""

    total_cases: int = 0
    phenotype_concordant: int = 0
    phenotype_discordant: int = 0
    genes_tested: List[str] = field(default_factory=list)
    cases: List[Dict[str, Any]] = field(default_factory=list)
    mismatches: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def concordance(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return self.phenotype_concordant / self.total_cases

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_cases": self.total_cases,
            "phenotype_concordant": self.phenotype_concordant,
            "phenotype_discordant": self.phenotype_discordant,
            "concordance": round(self.concordance, 4),
            "genes_tested": self.genes_tested,
            "cases": self.cases,
            "mismatches": self.mismatches,
        }

    def summary_table(self) -> str:
        """Generate formatted summary table."""
        lines = [
            "",
            "=" * 90,
            "CLINICAL CASE VALIDATION — Published Case Reports",
            "=" * 90,
            "",
            f"{'Case ID':<10} {'Gene':<10} {'Diplotype':<12} "
            f"{'Expected':<22} {'Predicted':<22} {'Match':>5}",
            "-" * 90,
        ]
        for case in self.cases:
            match = "Y" if case["match"] else "N"
            lines.append(
                f"{case['case_id']:<10} {case['gene']:<10} "
                f"{case['diplotype']:<12} {case['expected_phenotype']:<22} "
                f"{case['predicted_phenotype']:<22} {match:>5}"
            )
        lines.append("-" * 90)
        lines.append(
            f"Overall: {self.phenotype_concordant}/{self.total_cases} "
            f"({self.concordance:.1%}) concordance"
        )
        lines.append("")
        return "\n".join(lines)


def load_clinical_cases(
    cases_path: Optional[Path] = None,
    gene_filter: Optional[str] = None,
) -> List[ClinicalCase]:
    """Load published clinical cases from JSON file."""
    path = cases_path or _DEFAULT_CASES_PATH
    if not path.exists():
        logger.warning(f"Clinical cases file not found: {path}")
        return []

    with open(path) as f:
        data = json.load(f)

    cases = []
    for entry in data.get("cases", []):
        case = ClinicalCase(
            case_id=entry["case_id"],
            gene=entry["gene"],
            diplotype=entry["diplotype"],
            phenotype=entry["phenotype"],
            drug=entry["drug"],
            clinical_outcome=entry["clinical_outcome"],
            expected_risk=entry["expected_risk"],
            patient_summary=entry.get("patient_summary", ""),
            reference=entry.get("reference", ""),
            pmid=entry.get("pmid"),
        )
        if gene_filter and case.gene.upper() != gene_filter.upper():
            continue
        cases.append(case)

    return cases


def validate_clinical_cases(
    cases: List[ClinicalCase],
    phenotype_lookup: Dict[str, Dict[str, str]],
) -> ClinicalValidationResult:
    """
    Validate Anukriti phenotype predictions against published clinical cases.

    phenotype_lookup: {gene: {diplotype: phenotype}} from CPIC translation tables.
    """
    result = ClinicalValidationResult()
    genes_seen: set = set()

    for case in cases:
        gene = case.gene.upper()
        genes_seen.add(gene)

        # Look up Anukriti's predicted phenotype
        gene_table = phenotype_lookup.get(gene, {})
        predicted = gene_table.get(case.diplotype, "")

        # Try reversed diplotype ordering
        if not predicted and "/" in case.diplotype:
            parts = case.diplotype.split("/")
            if len(parts) == 2:
                reversed_dip = "/".join(reversed(parts))
                sorted_dip = "/".join(sorted(parts))
                predicted = gene_table.get(reversed_dip, "") or gene_table.get(
                    sorted_dip, ""
                )

        if not predicted:
            predicted = "Unknown"

        # Compare normalized phenotypes
        expected_norm = normalize_phenotype(case.phenotype)
        predicted_norm = normalize_phenotype(predicted)
        match = expected_norm == predicted_norm

        case_result = {
            "case_id": case.case_id,
            "gene": case.gene,
            "diplotype": case.diplotype,
            "drug": case.drug,
            "expected_phenotype": case.phenotype,
            "predicted_phenotype": predicted,
            "match": match,
            "clinical_outcome": case.clinical_outcome,
            "reference": case.reference,
            "pmid": case.pmid,
        }

        result.cases.append(case_result)
        result.total_cases += 1

        if match:
            result.phenotype_concordant += 1
        else:
            result.phenotype_discordant += 1
            result.mismatches.append(case_result)

    result.genes_tested = sorted(genes_seen)
    return result


def generate_latex_table(result: ClinicalValidationResult) -> str:
    """Generate LaTeX table for published clinical case validation."""
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Validation against published clinical case reports. "
        r"Each case represents a documented adverse drug reaction with confirmed "
        r"pharmacogenomic genotype from peer-reviewed literature.}",
        r"\label{tab:clinical-cases}",
        r"\renewcommand{\arraystretch}{1.2}",
        r"\small",
        r"\begin{tabular}{@{}llllc@{}}",
        r"\toprule",
        r"\textbf{Gene} & \textbf{Diplotype} & \textbf{Drug} & "
        r"\textbf{Phenotype} & \textbf{Concordant} \\",
        r"\midrule",
    ]

    for case in result.cases:
        check = r"\checkmark" if case["match"] else r"$\times$"
        diplotype = case["diplotype"].replace("*", r"\ast ")
        lines.append(
            f"  {case['gene']} & {diplotype} & {case['drug']} "
            f"& {case['predicted_phenotype']} & {check} \\\\"
        )

    lines.append(r"\midrule")
    lines.append(
        f"  \\textbf{{Overall}} & & & "
        f"& \\textbf{{{result.phenotype_concordant}/{result.total_cases}}} \\\\"
    )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines)
