"""
CPIC-grade SLCO1B1 (statin myopathy) PGx: rs4149056 c.521T>C.

Variant → Genotype → Phenotype → Recommendation using CPIC terminology.
Data: data/pgx/cpic/slco1b1_phenotypes.json, statin_guidelines.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, cast

DEFAULT_PGX_DIR = Path(__file__).resolve().parent.parent / "data" / "pgx"


def _pgx_path(*parts: str, base_dir: Optional[Path] = None) -> Path:
    base = base_dir or DEFAULT_PGX_DIR
    return base.joinpath(*parts)


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    """Load JSON file into a typed dict for mypy."""
    if not path.is_file():
        return None
    with open(path, "r") as f:
        data = json.load(f)
    return cast(Dict[str, Any], data)


def alt_dosage(gt: str) -> Optional[int]:
    """VCF genotype → ALT allele dosage (0, 1, or 2)."""
    if gt in ("0/0", "0|0"):
        return 0
    if gt in ("0/1", "1/0", "0|1", "1|0"):
        return 1
    if gt in ("1/1", "1|1"):
        return 2
    return None


def interpret_slco1b1(rs4149056_genotype: str, drug_name: str) -> Dict:
    """
    CPIC-grade SLCO1B1 interpretation for statins.

    Input:
      rs4149056_genotype: TT / TC / CC
      drug_name: simvastatin / atorvastatin / rosuvastatin

    Output:
      phenotype, risk, recommendation (drug-specific).
    """
    slco_path = _pgx_path("cpic", "slco1b1_phenotypes.json")
    statin_path = _pgx_path("cpic", "statin_guidelines.json")

    slco_data = _load_json(slco_path)
    statin_guides = _load_json(statin_path)

    if not slco_data or "rs4149056" not in slco_data:
        return {}

    genotype = rs4149056_genotype.upper().strip()
    if genotype not in slco_data["rs4149056"]:
        return {}

    phenotype_info = slco_data["rs4149056"][genotype]
    phenotype = phenotype_info.get("phenotype", "")
    risk = phenotype_info.get("risk", "")

    drug = (drug_name or "").strip().lower()
    recommendation: Optional[str] = None
    if drug and statin_guides and drug in statin_guides:
        recommendation = statin_guides[drug].get(phenotype)

    return {
        "gene": "SLCO1B1",
        "variant": "rs4149056",
        "genotype": genotype,
        "phenotype": phenotype,
        "risk": risk,
        "recommendation": recommendation or "No guideline available",
    }


def load_slco1b1_phenotypes(base_dir: Optional[Path] = None) -> Dict[str, str]:
    """Load SLCO1B1 genotype → phenotype string (TT/TC/CC → description). Backward compat."""
    path = _pgx_path("cpic", "slco1b1_phenotypes.json", base_dir=base_dir)
    data = _load_json(path)
    if not data or "rs4149056" not in data:
        return {}
    out = {}
    for geno, info in data["rs4149056"].items():
        if isinstance(info, dict):
            out[geno] = info.get("phenotype", "") or info.get("risk", "")
        else:
            out[geno] = str(info)
    return out


def interpret_slco1b1_from_vcf(
    var_map: Dict[str, Tuple[str, str, str]],
    base_dir: Optional[Path] = None,
) -> Optional[Dict[str, str]]:
    """
    Deterministic SLCO1B1 interpretation from VCF variant map (no drug).
    var_map: rsid -> (ref, alt, gt). Returns genotype (TT/TC/CC) and phenotype.
    For drug-specific recommendation use interpret_slco1b1(genotype, drug_name).
    """
    if "rs4149056" not in var_map:
        return None
    ref, alt, gt = var_map["rs4149056"]
    dosage = alt_dosage(gt)
    if dosage == 0:
        geno = f"{ref}{ref}"
    elif dosage == 1:
        geno = f"{ref}{alt}"
    elif dosage == 2:
        geno = f"{alt}{alt}"
    else:
        geno = "Unknown"
    table = load_slco1b1_phenotypes(base_dir=base_dir)
    phenotype = table.get(geno, "Unknown function")
    return {
        "gene": "SLCO1B1",
        "rsid": "rs4149056",
        "genotype": geno,
        "phenotype": phenotype,
    }
