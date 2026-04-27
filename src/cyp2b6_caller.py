"""
CPIC-grade CYP2B6 PGx caller.

CYP2B6 is the primary enzyme metabolizing efavirenz (HIV/ARV) and bupropion (antidepressant).
CPIC Level A for efavirenz dosing.

Equity significance:
- CYP2B6*6 (rs3745274) frequency: ~50% in African populations vs ~25% in European
- CYP2B6*18 (rs28399499) frequency: ~10% in African, rare in European/Asian
- African patients on standard efavirenz (600mg/day) are disproportionately at risk
  for CNS toxicity (nightmares, dizziness, depression) and ART discontinuation
- This is a MAJOR equity gap in HIV pharmacogenomics

Data: data/pgx/pharmvar/cyp2b6_alleles.tsv
      data/pgx/cpic/cyp2b6_phenotypes.json
      data/pgx/cpic/cyp2b6_guidelines.json
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


def _pgx_path(*parts: str, base_dir: Optional[Path] = None) -> Path:
    base = base_dir or DEFAULT_PGX_DIR
    return base.joinpath(*parts)


def call_cyp2b6(
    patient_variants: Dict[str, str], base_dir: Optional[Path] = None
) -> str:
    """
    Detect CYP2B6 alleles from rsIDs. Default = *1. Returns diplotype string.
    """
    path = _pgx_path("pharmvar", "cyp2b6_alleles.tsv", base_dir=base_dir)
    if not path.is_file():
        return "*1/*1"
    table = load_pharmvar_table(path)
    detected = call_star_alleles_simple(patient_variants, table)
    return build_diplotype_simple(detected)


def load_cyp2b6_phenotypes(base_dir: Optional[Path] = None) -> Dict[str, str]:
    path = _pgx_path("cpic", "cyp2b6_phenotypes.json", base_dir=base_dir)
    if not path.is_file():
        return {}
    with open(path) as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def interpret_cyp2b6(
    patient_variants: Dict[str, str],
    drug_name: str = "",
    ancestry: str = "",
    base_dir: Optional[Path] = None,
) -> Dict[str, str]:
    """
    Deterministic CYP2B6 PGx interpretation.
    patient_variants: rsid -> alt.
    ancestry: optional population ancestry string for equity contextualization.
    Returns dict with gene, diplotype, phenotype, recommendation, equity_note.
    """
    diplotype = call_cyp2b6(patient_variants, base_dir=base_dir)
    phenotypes = load_cyp2b6_phenotypes(base_dir=base_dir)
    phenotype = phenotypes.get(diplotype, "Unknown Metabolizer Status")

    recommendation = "No specific guideline available"
    drug = (drug_name or "").strip().lower()
    if drug:
        guidelines_path = _pgx_path("cpic", "cyp2b6_guidelines.json", base_dir=base_dir)
        if guidelines_path.is_file():
            with open(guidelines_path) as f:
                guidelines = json.load(f)
            drug_map = {k: v for k, v in guidelines.items() if not k.startswith("_")}
            if drug in drug_map:
                recommendation = drug_map[drug].get(
                    phenotype, "No guideline for this phenotype"
                )

    equity_note = (
        "CYP2B6 poor metabolizer prevalence is significantly higher in African "
        "populations (*6/*6 ~25%, *6/*18 ~5%). Standard efavirenz 600mg/day causes "
        "CNS toxicity in CYP2B6 PMs, contributing to ARV treatment discontinuation "
        "in sub-Saharan Africa. Genotype-guided dosing can directly reduce this inequity."
    )

    return {
        "gene": "CYP2B6",
        "diplotype": diplotype,
        "phenotype": phenotype,
        "recommendation": recommendation,
        "cpic_level": "A",
        "equity_note": equity_note,
    }


def interpret_cyp2b6_from_vcf(
    var_map: Dict[str, Tuple[str, str, str]],
    ancestry: str = "",
    base_dir: Optional[Path] = None,
) -> Optional[Dict[str, str]]:
    from .allele_caller import alt_dosage

    cyp2b6_rsids = {
        "rs2279343",
        "rs3211371",
        "rs3745274",
        "rs4986776",
        "rs28399499",
        "rs34223104",
        "rs3826711",
        "rs36060847",
    }
    relevant = {k: v for k, v in var_map.items() if k in cyp2b6_rsids}
    if not relevant:
        return {
            "gene": "CYP2B6",
            "diplotype": "*1/*1",
            "phenotype": "Normal Metabolizer",
        }

    simple_variants: Dict[str, str] = {}
    for rsid, (ref, alt, gt) in relevant.items():
        dosage = alt_dosage(gt)
        if dosage and dosage > 0:
            simple_variants[rsid] = alt

    return interpret_cyp2b6(simple_variants, ancestry=ancestry, base_dir=base_dir)
