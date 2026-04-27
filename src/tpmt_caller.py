"""
CPIC-grade TPMT PGx: Thiopurine S-methyltransferase.

Determines TPMT metabolizer status from key variants (rs1800462, rs1800460, rs1142345).
Drives thiopurine dosing recommendations (azathioprine, mercaptopurine, thioguanine).
Data: data/pgx/pharmvar/tpmt_alleles.tsv, data/pgx/cpic/tpmt_phenotypes.json,
      data/pgx/cpic/thiopurine_guidelines.json
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


def call_tpmt(patient_variants: Dict[str, str], base_dir: Optional[Path] = None) -> str:
    """
    Detect TPMT alleles from rsIDs (simple variant dict: rsid -> alt).
    Default = *1. Returns diplotype string (e.g. *1/*3A).
    """
    path = _pgx_path("pharmvar", "tpmt_alleles.tsv", base_dir=base_dir)
    if not path.is_file():
        return "*1/*1"
    table = load_pharmvar_table(path)
    detected = call_star_alleles_simple(patient_variants, table)
    return build_diplotype_simple(detected)


def load_tpmt_phenotypes(base_dir: Optional[Path] = None) -> Dict[str, str]:
    """Load TPMT diplotype -> phenotype JSON."""
    path = _pgx_path("cpic", "tpmt_phenotypes.json", base_dir=base_dir)
    if not path.is_file():
        return {}
    with open(path, "r") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def load_thiopurine_guidelines(base_dir: Optional[Path] = None) -> Dict:
    """Load thiopurine drug-specific guidelines JSON."""
    path = _pgx_path("cpic", "thiopurine_guidelines.json", base_dir=base_dir)
    if not path.is_file():
        return {}
    with open(path, "r") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def interpret_tpmt(
    patient_variants: Dict[str, str],
    drug_name: str = "",
    base_dir: Optional[Path] = None,
) -> Dict[str, str]:
    """
    Deterministic TPMT PGx interpretation.
    patient_variants: rsid -> alt.
    Returns dict with gene, diplotype, phenotype, recommendation.
    """
    diplotype = call_tpmt(patient_variants, base_dir=base_dir)
    phenotypes = load_tpmt_phenotypes(base_dir=base_dir)
    phenotype = phenotypes.get(diplotype, "Unknown Metabolizer Status")

    recommendation = "No specific guideline available"
    drug = (drug_name or "").strip().lower()
    if drug:
        guidelines = load_thiopurine_guidelines(base_dir=base_dir)
        if drug in guidelines:
            recommendation = guidelines[drug].get(
                phenotype, "No guideline for this phenotype"
            )

    return {
        "gene": "TPMT",
        "diplotype": diplotype,
        "phenotype": phenotype,
        "recommendation": recommendation,
    }


def interpret_tpmt_from_vcf(
    var_map: Dict[str, Tuple[str, str, str]],
    base_dir: Optional[Path] = None,
) -> Optional[Dict[str, str]]:
    """
    Deterministic TPMT interpretation from VCF variant map.
    var_map: rsid -> (ref, alt, gt).
    """
    from .allele_caller import alt_dosage

    tpmt_rsids = {"rs1800462", "rs1800460", "rs1142345", "rs1800584"}
    relevant = {k: v for k, v in var_map.items() if k in tpmt_rsids}
    if not relevant:
        return {
            "gene": "TPMT",
            "diplotype": "*1/*1",
            "phenotype": "Normal Metabolizer",
        }

    # Convert VCF format to simple variant dict
    simple_variants: Dict[str, str] = {}
    for rsid, (ref, alt, gt) in relevant.items():
        dosage = alt_dosage(gt)
        if dosage and dosage > 0:
            simple_variants[rsid] = alt

    result = interpret_tpmt(simple_variants, base_dir=base_dir)
    return result
