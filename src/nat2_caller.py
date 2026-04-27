"""
CPIC-grade NAT2 PGx caller.

NAT2 (N-acetyltransferase 2) determines acetylator phenotype:
- Rapid Acetylator: two functional alleles
- Intermediate Acetylator: one functional + one slow allele
- Slow Acetylator: two slow alleles (no functional alleles)

Primary drug: isoniazid (TB treatment) — CPIC Level A.
Also relevant for: hydralazine, procainamide, sulfamethoxazole.

Equity significance — NAT2 slow acetylator frequency by ancestry:
- Middle Eastern: ~90% slow acetylator
- European: ~55-60% slow acetylator
- South Asian: ~50% slow acetylator
- East Asian: ~30-40% slow acetylator
- Sub-Saharan African: ~20-30% slow acetylator

TB disproportionately affects low-income populations in the Global South.
NAT2-guided isoniazid dosing is critical for equitable TB treatment and
reducing isoniazid-induced peripheral neuropathy and hepatotoxicity.

Data: data/pgx/pharmvar/nat2_alleles.tsv
      data/pgx/cpic/nat2_phenotypes.json
      data/pgx/cpic/isoniazid_guidelines.json
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

_SLOW_ALLELE_RSIDS = {
    "rs1801280",  # *5 series
    "rs1799930",  # *6 series
    "rs1799931",  # *7
    "rs1801279",  # *14 series
}


def _pgx_path(*parts: str, base_dir: Optional[Path] = None) -> Path:
    base = base_dir or DEFAULT_PGX_DIR
    return base.joinpath(*parts)


def call_nat2(patient_variants: Dict[str, str], base_dir: Optional[Path] = None) -> str:
    """
    Detect NAT2 alleles from rsIDs. Default = *4 (rapid). Returns diplotype string.
    """
    path = _pgx_path("pharmvar", "nat2_alleles.tsv", base_dir=base_dir)
    if not path.is_file():
        return "*4/*4"
    table = load_pharmvar_table(path)
    detected = call_star_alleles_simple(patient_variants, table)
    if not detected:
        return "*4/*4"
    return build_diplotype_simple(detected)


def infer_nat2_phenotype_from_rsids(patient_variants: Dict[str, str]) -> str:
    """
    Heuristic acetylator phenotype from key NAT2 slow-allele rsIDs.
    Counts slow-allele variant dosages across the four key SNPs.
    - 0 slow alleles across all SNPs: Rapid Acetylator
    - 1-2 slow alleles (heterozygous): Intermediate Acetylator
    - 3+ slow alleles (homozygous or compound): Slow Acetylator
    """
    slow_allele_count = 0
    for rsid in _SLOW_ALLELE_RSIDS:
        if rsid in patient_variants:
            slow_allele_count += 1

    if slow_allele_count == 0:
        return "Rapid Acetylator"
    elif slow_allele_count == 1:
        return "Intermediate Acetylator"
    else:
        return "Slow Acetylator"


def load_nat2_phenotypes(base_dir: Optional[Path] = None) -> Dict[str, str]:
    path = _pgx_path("cpic", "nat2_phenotypes.json", base_dir=base_dir)
    if not path.is_file():
        return {}
    with open(path) as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def interpret_nat2(
    patient_variants: Dict[str, str],
    drug_name: str = "",
    base_dir: Optional[Path] = None,
) -> Dict[str, str]:
    """
    Deterministic NAT2 PGx interpretation.
    patient_variants: rsid -> alt.
    Returns dict with gene, diplotype, phenotype, recommendation, equity_note.
    """
    diplotype = call_nat2(patient_variants, base_dir=base_dir)
    phenotypes = load_nat2_phenotypes(base_dir=base_dir)
    phenotype = phenotypes.get(diplotype)

    if phenotype is None:
        phenotype = infer_nat2_phenotype_from_rsids(patient_variants)

    recommendation = "No specific guideline available"
    drug = (drug_name or "").strip().lower()
    if drug:
        guidelines_path = _pgx_path(
            "cpic", "isoniazid_guidelines.json", base_dir=base_dir
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
        "gene": "NAT2",
        "diplotype": diplotype,
        "phenotype": phenotype,
        "recommendation": recommendation,
        "cpic_level": "A",
        "equity_note": (
            "NAT2 slow acetylator prevalence varies dramatically by ancestry "
            "(90% Middle Eastern, 60% European, 30% sub-Saharan African). "
            "Isoniazid toxicity (peripheral neuropathy, hepatitis) primarily affects "
            "slow acetylators. Pyridoxine (B6) supplementation and dose adjustment "
            "are critical for equitable TB treatment globally."
        ),
    }


def interpret_nat2_from_vcf(
    var_map: Dict[str, Tuple[str, str, str]],
    base_dir: Optional[Path] = None,
) -> Optional[Dict[str, str]]:
    from .allele_caller import alt_dosage

    nat2_rsids = {"rs1801280", "rs1799930", "rs1799931", "rs1801279"}
    relevant = {k: v for k, v in var_map.items() if k in nat2_rsids}
    if not relevant:
        return {
            "gene": "NAT2",
            "diplotype": "*4/*4",
            "phenotype": "Rapid Acetylator",
        }

    simple_variants: Dict[str, str] = {}
    for rsid, (ref, alt, gt) in relevant.items():
        dosage = alt_dosage(gt)
        if dosage and dosage > 0:
            simple_variants[rsid] = alt

    return interpret_nat2(simple_variants, base_dir=base_dir)
