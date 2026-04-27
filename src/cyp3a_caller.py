"""
CPIC-grade CYP3A4/CYP3A5 PGx callers.

CYP3A5: Key actionable gene for tacrolimus dosing (CPIC Level A).
  *3 (rs776746) is the most common No Function allele across all populations.
  ~90% of Europeans and East Asians are *3/*3 (Poor Metabolizers).
  ~50-75% of Africans carry at least one *1 allele (Intermediate/Rapid Metabolizers).
  This ancestry gap directly impacts tacrolimus dosing in transplant medicine.

CYP3A4: Contributes to metabolism of >50% of all drugs. *22 (rs35599367) is
  the main clinically actionable variant for reduced function.

Data: data/pgx/pharmvar/cyp3a5_alleles.tsv, cyp3a4_alleles.tsv
      data/pgx/cpic/cyp3a5_phenotypes.json, cyp3a4_phenotypes.json
      data/pgx/cpic/tacrolimus_guidelines.json
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


# ---------------------------------------------------------------------------
# CYP3A5
# ---------------------------------------------------------------------------


def call_cyp3a5(
    patient_variants: Dict[str, str], base_dir: Optional[Path] = None
) -> str:
    """
    Detect CYP3A5 alleles from rsIDs. Default = *1 (expressors).
    Returns diplotype string (e.g. *1/*3).
    """
    path = _pgx_path("pharmvar", "cyp3a5_alleles.tsv", base_dir=base_dir)
    if not path.is_file():
        return "*1/*1"
    table = load_pharmvar_table(path)
    detected = call_star_alleles_simple(patient_variants, table)
    return build_diplotype_simple(detected)


def load_cyp3a5_phenotypes(base_dir: Optional[Path] = None) -> Dict[str, str]:
    path = _pgx_path("cpic", "cyp3a5_phenotypes.json", base_dir=base_dir)
    if not path.is_file():
        return {}
    with open(path) as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def interpret_cyp3a5(
    patient_variants: Dict[str, str],
    drug_name: str = "",
    base_dir: Optional[Path] = None,
) -> Dict[str, str]:
    """
    Deterministic CYP3A5 PGx interpretation.
    patient_variants: rsid -> alt.
    Returns dict with gene, diplotype, phenotype, recommendation, equity_note.
    """
    diplotype = call_cyp3a5(patient_variants, base_dir=base_dir)
    phenotypes = load_cyp3a5_phenotypes(base_dir=base_dir)
    phenotype = phenotypes.get(diplotype, "Unknown Metabolizer Status")

    recommendation = "No specific guideline available"
    drug = (drug_name or "").strip().lower()
    if drug:
        guidelines_path = _pgx_path(
            "cpic", "tacrolimus_guidelines.json", base_dir=base_dir
        )
        if guidelines_path.is_file():
            with open(guidelines_path) as f:
                guidelines = json.load(f)
            drug_map = {k: v for k, v in guidelines.items() if not k.startswith("_")}
            if drug in drug_map:
                recommendation = drug_map[drug].get(
                    phenotype, "No guideline for this phenotype"
                )

    return {
        "gene": "CYP3A5",
        "diplotype": diplotype,
        "phenotype": phenotype,
        "recommendation": recommendation,
        "cpic_level": "A",
        "equity_note": (
            "CYP3A5 expressors (*1 carriers) are ~75% of African-descent patients "
            "vs ~10% of European-descent patients. Standard tacrolimus doses are "
            "systematically under-dosed for African transplant recipients without genotyping."
        ),
    }


def interpret_cyp3a5_from_vcf(
    var_map: Dict[str, Tuple[str, str, str]],
    base_dir: Optional[Path] = None,
) -> Optional[Dict[str, str]]:
    from .allele_caller import alt_dosage

    cyp3a5_rsids = {"rs776746", "rs10264272", "rs41303343", "rs41279854", "rs28383479"}
    relevant = {k: v for k, v in var_map.items() if k in cyp3a5_rsids}
    if not relevant:
        return {
            "gene": "CYP3A5",
            "diplotype": "*3/*3",
            "phenotype": "Poor Metabolizer",
            "equity_note": "No CYP3A5 variants detected — assumed *3/*3 (most common in non-African populations).",
        }

    simple_variants: Dict[str, str] = {}
    for rsid, (ref, alt, gt) in relevant.items():
        dosage = alt_dosage(gt)
        if dosage and dosage > 0:
            simple_variants[rsid] = alt

    return interpret_cyp3a5(simple_variants, base_dir=base_dir)


# ---------------------------------------------------------------------------
# CYP3A4
# ---------------------------------------------------------------------------


def call_cyp3a4(
    patient_variants: Dict[str, str], base_dir: Optional[Path] = None
) -> str:
    """
    Detect CYP3A4 alleles from rsIDs. Default = *1. Returns diplotype string.
    """
    path = _pgx_path("pharmvar", "cyp3a4_alleles.tsv", base_dir=base_dir)
    if not path.is_file():
        return "*1/*1"
    table = load_pharmvar_table(path)
    detected = call_star_alleles_simple(patient_variants, table)
    return build_diplotype_simple(detected)


def interpret_cyp3a4(
    patient_variants: Dict[str, str],
    drug_name: str = "",
    base_dir: Optional[Path] = None,
) -> Dict[str, str]:
    diplotype = call_cyp3a4(patient_variants, base_dir=base_dir)
    phenotypes_path = _pgx_path("cpic", "cyp3a4_phenotypes.json", base_dir=base_dir)
    phenotypes: Dict[str, str] = {}
    if phenotypes_path.is_file():
        with open(phenotypes_path) as f:
            data = json.load(f)
        phenotypes = {k: v for k, v in data.items() if not k.startswith("_")}
    phenotype = phenotypes.get(diplotype, "Normal Metabolizer")

    return {
        "gene": "CYP3A4",
        "diplotype": diplotype,
        "phenotype": phenotype,
        "recommendation": (
            "CYP3A4 metabolizes >50% of all drugs. Variants may significantly alter "
            "exposure for tacrolimus, midazolam, statins, antiretrovirals, and many "
            "other drugs. Interpret in combination with CYP3A5 genotype."
        ),
        "cpic_level": "A/B",
    }


def interpret_cyp3a4_from_vcf(
    var_map: Dict[str, Tuple[str, str, str]],
    base_dir: Optional[Path] = None,
) -> Optional[Dict[str, str]]:
    from .allele_caller import alt_dosage

    cyp3a4_rsids = {
        "rs35599367",
        "rs55902638",
        "rs55901263",
        "rs56324128",
        "rs138105638",
        "rs4987161",
        "rs4986910",
        "rs4986907",
        "rs67666821",
    }
    relevant = {k: v for k, v in var_map.items() if k in cyp3a4_rsids}
    if not relevant:
        return {
            "gene": "CYP3A4",
            "diplotype": "*1/*1",
            "phenotype": "Normal Metabolizer",
        }

    simple_variants: Dict[str, str] = {}
    for rsid, (ref, alt, gt) in relevant.items():
        dosage = alt_dosage(gt)
        if dosage and dosage > 0:
            simple_variants[rsid] = alt

    return interpret_cyp3a4(simple_variants, base_dir=base_dir)
