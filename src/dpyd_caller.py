"""
CPIC-grade DPYD PGx: Dihydropyrimidine dehydrogenase.

Determines DPYD metabolizer status from key variants (rs3918290, rs55886062,
rs67376798, rs56038477). Drives fluoropyrimidine dosing recommendations
(5-fluorouracil, capecitabine, tegafur).
Data: data/pgx/pharmvar/dpyd_alleles.tsv, data/pgx/cpic/dpyd_phenotypes.json,
      data/pgx/cpic/fluoropyrimidine_guidelines.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .allele_caller import (
    build_diplotype_simple,
    call_star_alleles_simple,
    load_pharmvar_table,
)

DEFAULT_PGX_DIR = Path(__file__).resolve().parent.parent / "data" / "pgx"


def _pgx_path(*parts: str, base_dir: Optional[Path] = None) -> Path:
    base = base_dir or DEFAULT_PGX_DIR
    return base.joinpath(*parts)


def call_dpyd(patient_variants: Dict[str, str], base_dir: Optional[Path] = None) -> str:
    """
    Detect DPYD alleles from rsIDs (simple variant dict: rsid -> alt).
    Default = *1. Returns diplotype string.
    """
    path = _pgx_path("pharmvar", "dpyd_alleles.tsv", base_dir=base_dir)
    if not path.is_file():
        return "*1/*1"
    table = load_pharmvar_table(path)
    detected = call_star_alleles_simple(patient_variants, table)
    return build_diplotype_simple(detected)


def load_dpyd_phenotypes(base_dir: Optional[Path] = None) -> Dict[str, str]:
    """Load DPYD diplotype -> phenotype JSON."""
    path = _pgx_path("cpic", "dpyd_phenotypes.json", base_dir=base_dir)
    if not path.is_file():
        return {}
    with open(path, "r") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def load_fluoropyrimidine_guidelines(base_dir: Optional[Path] = None) -> Dict:
    """Load fluoropyrimidine drug-specific guidelines JSON."""
    path = _pgx_path("cpic", "fluoropyrimidine_guidelines.json", base_dir=base_dir)
    if not path.is_file():
        return {}
    with open(path, "r") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def interpret_dpyd(
    patient_variants: Dict[str, str],
    drug_name: str = "",
    base_dir: Optional[Path] = None,
) -> Dict[str, str]:
    """
    Deterministic DPYD PGx interpretation.
    patient_variants: rsid -> alt.
    Returns dict with gene, diplotype, phenotype, recommendation.
    """
    diplotype = call_dpyd(patient_variants, base_dir=base_dir)
    phenotypes = load_dpyd_phenotypes(base_dir=base_dir)
    phenotype = phenotypes.get(diplotype, "Unknown Metabolizer Status")

    recommendation = "No specific guideline available"
    drug = (drug_name or "").strip().lower()
    if drug:
        guidelines = load_fluoropyrimidine_guidelines(base_dir=base_dir)
        if drug in guidelines:
            recommendation = guidelines[drug].get(
                phenotype, "No guideline for this phenotype"
            )

    return {
        "gene": "DPYD",
        "diplotype": diplotype,
        "phenotype": phenotype,
        "recommendation": recommendation,
    }


def interpret_dpyd_from_vcf(
    var_map: Dict[str, Tuple[str, str, str]],
    base_dir: Optional[Path] = None,
) -> Optional[Dict[str, str]]:
    """
    Deterministic DPYD interpretation from VCF variant map.
    var_map: rsid -> (ref, alt, gt).
    """
    from .allele_caller import alt_dosage

    dpyd_rsids = {"rs3918290", "rs55886062", "rs67376798", "rs56038477"}
    relevant = {k: v for k, v in var_map.items() if k in dpyd_rsids}
    if not relevant:
        return {
            "gene": "DPYD",
            "diplotype": "*1/*1",
            "phenotype": "Normal Metabolizer",
        }

    # Convert VCF format to simple variant dict
    simple_variants: Dict[str, str] = {}
    for rsid, (ref, alt, gt) in relevant.items():
        dosage = alt_dosage(gt)
        if dosage and dosage > 0:
            simple_variants[rsid] = alt

    result = interpret_dpyd(simple_variants, base_dir=base_dir)
    return result
