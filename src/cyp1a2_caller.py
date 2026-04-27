"""
CPIC-grade CYP1A2 PGx caller.

CYP1A2 metabolizes clozapine, theophylline, caffeine, fluvoxamine, and other drugs.
Key clinical applications: antipsychotic dosing, asthma medications.

Critical note: CYP1A2 activity is strongly induced by:
- Tobacco smoking (1.5-3x increase via AhR-mediated induction)
- Omeprazole, cruciferous vegetables, chargrilled meat

Smoking status MUST be documented alongside genotype for accurate phenotype assignment.
This caller reports baseline (non-induced) phenotype and flags smoking interaction.

CPIC Level B (clinical evidence less robust than Level A genes).

Data: data/pgx/pharmvar/cyp1a2_alleles.tsv
      data/pgx/cpic/cyp1a2_phenotypes.json
      data/pgx/cpic/cyp1a2_guidelines.json
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


def call_cyp1a2(
    patient_variants: Dict[str, str], base_dir: Optional[Path] = None
) -> str:
    """
    Detect CYP1A2 alleles from rsIDs. Default = *1. Returns diplotype string.
    """
    path = _pgx_path("pharmvar", "cyp1a2_alleles.tsv", base_dir=base_dir)
    if not path.is_file():
        return "*1/*1"
    table = load_pharmvar_table(path)
    detected = call_star_alleles_simple(patient_variants, table)
    return build_diplotype_simple(detected)


def load_cyp1a2_phenotypes(base_dir: Optional[Path] = None) -> Dict[str, str]:
    path = _pgx_path("cpic", "cyp1a2_phenotypes.json", base_dir=base_dir)
    if not path.is_file():
        return {}
    with open(path) as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def interpret_cyp1a2(
    patient_variants: Dict[str, str],
    drug_name: str = "",
    smoking_status: str = "unknown",
    base_dir: Optional[Path] = None,
) -> Dict[str, str]:
    """
    Deterministic CYP1A2 PGx interpretation.
    patient_variants: rsid -> alt.
    smoking_status: 'smoker', 'non-smoker', or 'unknown'.
    Returns dict with gene, diplotype, phenotype, recommendation, smoking_interaction.
    """
    diplotype = call_cyp1a2(patient_variants, base_dir=base_dir)
    phenotypes = load_cyp1a2_phenotypes(base_dir=base_dir)
    phenotype = phenotypes.get(diplotype, "Normal Metabolizer")

    smoking_note = ""
    if smoking_status.lower() in ("smoker", "current smoker", "yes"):
        smoking_note = (
            "SMOKING INTERACTION: Patient is a smoker. CYP1A2 is strongly induced by "
            "tobacco smoke. Clozapine doses may need to be 1.5-2x higher. Abrupt "
            "smoking cessation can cause 50% increase in clozapine plasma levels — "
            "monitor closely and reduce dose upon cessation."
        )
    elif smoking_status.lower() in ("non-smoker", "never", "no"):
        smoking_note = "Non-smoker: CYP1A2 induction by tobacco is not a factor."
    else:
        smoking_note = (
            "Smoking status unknown. CYP1A2 activity is strongly modulated by tobacco "
            "smoking. Document smoking status for accurate phenotype assignment."
        )

    recommendation = "No specific guideline available"
    drug = (drug_name or "").strip().lower()
    if drug:
        guidelines_path = _pgx_path("cpic", "cyp1a2_guidelines.json", base_dir=base_dir)
        if guidelines_path.is_file():
            with open(guidelines_path) as f:
                guidelines = json.load(f)
            drug_map = {k: v for k, v in guidelines.items() if not k.startswith("_")}
            if drug in drug_map:
                recommendation = drug_map[drug].get(
                    phenotype, "No guideline for this phenotype"
                )

    return {
        "gene": "CYP1A2",
        "diplotype": diplotype,
        "phenotype": phenotype,
        "recommendation": recommendation,
        "smoking_interaction": smoking_note,
        "cpic_level": "B",
        "clinical_note": (
            "CYP1A2 activity is profoundly influenced by environmental inducers "
            "(smoking, omeprazole). Genotype alone is insufficient — always document "
            "smoking status and relevant drug interactions."
        ),
    }


def interpret_cyp1a2_from_vcf(
    var_map: Dict[str, Tuple[str, str, str]],
    smoking_status: str = "unknown",
    base_dir: Optional[Path] = None,
) -> Optional[Dict[str, str]]:
    from .allele_caller import alt_dosage

    cyp1a2_rsids = {
        "rs2069514",
        "rs762551",
        "rs12720461",
        "rs4986893",
        "rs72547510",
        "rs28399424",
        "rs28399426",
        "rs28399427",
        "rs62625009",
        "rs28399432",
        "rs28399434",
        "rs28399435",
    }
    relevant = {k: v for k, v in var_map.items() if k in cyp1a2_rsids}
    if not relevant:
        return {
            "gene": "CYP1A2",
            "diplotype": "*1/*1",
            "phenotype": "Normal Metabolizer",
            "smoking_interaction": f"Smoking status: {smoking_status}. CYP1A2 induction by tobacco may significantly alter drug exposure.",
        }

    simple_variants: Dict[str, str] = {}
    for rsid, (ref, alt, gt) in relevant.items():
        dosage = alt_dosage(gt)
        if dosage and dosage > 0:
            simple_variants[rsid] = alt

    return interpret_cyp1a2(
        simple_variants, smoking_status=smoking_status, base_dir=base_dir
    )
