import json
import os
from typing import Dict

CPIC_SLCO1B1_PATH = "data/pgx/cpic/slco1b1_phenotypes.json"
CPIC_STATIN_GUIDE_PATH = "data/pgx/cpic/statin_guidelines.json"


def _load_json(path: str):
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def interpret_slco1b1(rs4149056_genotype: str, drug_name: str) -> Dict:
    """CPIC-grade SLCO1B1 interpretation for statins."""

    slco_data = _load_json(CPIC_SLCO1B1_PATH)
    statin_guides = _load_json(CPIC_STATIN_GUIDE_PATH)

    if not slco_data:
        return {}

    genotype = rs4149056_genotype.upper()
    if genotype not in slco_data["rs4149056"]:
        return {}

    phenotype_info = slco_data["rs4149056"][genotype]
    phenotype = phenotype_info["phenotype"]
    risk = phenotype_info["risk"]

    drug = drug_name.lower()
    recommendation = None

    if statin_guides and drug in statin_guides:
        recommendation = statin_guides[drug].get(phenotype)

    return {
        "gene": "SLCO1B1",
        "variant": "rs4149056",
        "genotype": genotype,
        "phenotype": phenotype,
        "risk": risk,
        "recommendation": recommendation or "No guideline available",
    }
