"""
CPIC-grade G6PD PGx: Glucose-6-phosphate dehydrogenase.

G6PD deficiency is the most common enzymopathy worldwide, affecting >400 million
people. It is X-linked, with highest prevalence in malaria-endemic regions
(sub-Saharan Africa, Mediterranean, Middle East, Southeast Asia).

Key variants:
  - rs1050828 (G6PD A-): ~20-25% in sub-Saharan Africa
  - rs5030868 (G6PD Mediterranean): ~5-20% in Mediterranean / Middle Eastern
  - rs72554665 (G6PD Canton): ~5% in Southeast Asia
  - rs5030869 (G6PD Chatham): ~2-5% in South Asia / Middle East
  - rs72554664 (G6PD Kaiping): ~3-5% in Southeast Asia

Drives dosing recommendations for primaquine, rasburicase, and dapsone.

Data files:
  data/pgx/pharmvar/g6pd_alleles.tsv
  data/pgx/cpic/g6pd_phenotypes.json
  data/pgx/cpic/g6pd_guidelines.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, Tuple

from .allele_caller import (
    build_diplotype_simple,
    call_star_alleles_simple,
    load_pharmvar_table,
)

DEFAULT_PGX_DIR = Path(__file__).resolve().parent.parent / "data" / "pgx"

_WILDTYPE = "B"


def _pgx_path(*parts: str, base_dir: Optional[Path] = None) -> Path:
    base = base_dir or DEFAULT_PGX_DIR
    return base.joinpath(*parts)


def call_g6pd(patient_variants: Dict[str, str], base_dir: Optional[Path] = None) -> str:
    """
    Detect G6PD variant alleles from rsIDs.
    Default (wildtype) = B. Returns diplotype string using G6PD nomenclature
    (e.g. "B/A-", "B/Mediterranean").
    """
    path = _pgx_path("pharmvar", "g6pd_alleles.tsv", base_dir=base_dir)
    if not path.is_file():
        return f"{_WILDTYPE}/{_WILDTYPE}"
    table = load_pharmvar_table(path)
    detected = call_star_alleles_simple(patient_variants, table)
    if detected == ["*1"]:
        detected = [_WILDTYPE]
    return _build_g6pd_diplotype(detected)


def _build_g6pd_diplotype(alleles: list[str]) -> str:
    """G6PD uses named alleles (B, A-, Mediterranean, etc.) instead of star notation."""
    cleaned = [a if a != "*1" else _WILDTYPE for a in alleles]
    if not cleaned:
        return f"{_WILDTYPE}/{_WILDTYPE}"
    if len(cleaned) == 1:
        return f"{_WILDTYPE}/{cleaned[0]}"
    return f"{cleaned[0]}/{cleaned[1]}"


def load_g6pd_phenotypes(base_dir: Optional[Path] = None) -> Dict[str, str]:
    """Load G6PD diplotype -> phenotype JSON."""
    path = _pgx_path("cpic", "g6pd_phenotypes.json", base_dir=base_dir)
    if not path.is_file():
        return {}
    with open(path, "r") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def load_g6pd_guidelines(base_dir: Optional[Path] = None) -> Dict:
    """Load G6PD drug-specific guidelines JSON."""
    path = _pgx_path("cpic", "g6pd_guidelines.json", base_dir=base_dir)
    if not path.is_file():
        return {}
    with open(path, "r") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def interpret_g6pd(
    patient_variants: Dict[str, str],
    drug_name: str = "",
    base_dir: Optional[Path] = None,
) -> Dict[str, str]:
    """
    Deterministic G6PD PGx interpretation.

    patient_variants: rsid -> alt allele.
    Returns dict with gene, diplotype, phenotype, recommendation.
    """
    diplotype = call_g6pd(patient_variants, base_dir=base_dir)
    phenotypes = load_g6pd_phenotypes(base_dir=base_dir)
    phenotype = phenotypes.get(diplotype, "Unknown G6PD Status")

    recommendation = "No specific guideline available"
    drug = (drug_name or "").strip().lower()
    if drug:
        guidelines = load_g6pd_guidelines(base_dir=base_dir)
        if drug in guidelines:
            recommendation = guidelines[drug].get(
                phenotype, "No guideline for this phenotype"
            )

    return {
        "gene": "G6PD",
        "diplotype": diplotype,
        "phenotype": phenotype,
        "recommendation": recommendation,
    }


def interpret_g6pd_from_vcf(
    var_map: Dict[str, Tuple[str, str, str]],
    base_dir: Optional[Path] = None,
) -> Optional[Dict[str, str]]:
    """
    Deterministic G6PD interpretation from VCF variant map.
    var_map: rsid -> (ref, alt, gt).
    """
    from .allele_caller import alt_dosage

    g6pd_rsids = {"rs1050828", "rs5030868", "rs72554665", "rs5030869", "rs72554664"}
    relevant = {k: v for k, v in var_map.items() if k in g6pd_rsids}
    if not relevant:
        return {
            "gene": "G6PD",
            "diplotype": f"{_WILDTYPE}/{_WILDTYPE}",
            "phenotype": "Normal",
        }

    simple_variants: Dict[str, str] = {}
    for rsid, (ref, alt, gt) in relevant.items():
        dosage = alt_dosage(gt)
        if dosage and dosage > 0:
            simple_variants[rsid] = alt

    return interpret_g6pd(simple_variants, base_dir=base_dir)
