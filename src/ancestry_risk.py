"""
Ancestry-aware risk scoring for pharmacogenomic predictions.

Adjusts confidence scores based on how well-represented a patient's ancestry
is in the evidence base for a given gene-drug pair. Uses population-specific
allele frequencies from 1000 Genomes / gnomAD-style data.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# Population-specific allele frequencies for key PGx variants
# Source: 1000 Genomes Phase 3, gnomAD v3.1 (simplified)
POPULATION_VARIANT_FREQUENCIES = {
    "CYP2D6": {
        "*4": {"AFR": 0.07, "EUR": 0.20, "EAS": 0.01, "SAS": 0.10, "AMR": 0.12},
        "*10": {"AFR": 0.04, "EUR": 0.02, "EAS": 0.40, "SAS": 0.15, "AMR": 0.05},
        "*17": {"AFR": 0.20, "EUR": 0.01, "EAS": 0.01, "SAS": 0.03, "AMR": 0.05},
        "*41": {"AFR": 0.08, "EUR": 0.08, "EAS": 0.03, "SAS": 0.12, "AMR": 0.06},
    },
    "CYP2C19": {
        "*2": {"AFR": 0.15, "EUR": 0.15, "EAS": 0.30, "SAS": 0.35, "AMR": 0.12},
        "*3": {"AFR": 0.01, "EUR": 0.01, "EAS": 0.05, "SAS": 0.02, "AMR": 0.01},
        "*17": {"AFR": 0.24, "EUR": 0.21, "EAS": 0.03, "SAS": 0.15, "AMR": 0.16},
    },
    "CYP2C9": {
        "*2": {"AFR": 0.02, "EUR": 0.13, "EAS": 0.00, "SAS": 0.08, "AMR": 0.08},
        "*3": {"AFR": 0.01, "EUR": 0.07, "EAS": 0.04, "SAS": 0.10, "AMR": 0.05},
    },
    "TPMT": {
        "*2": {"AFR": 0.005, "EUR": 0.02, "EAS": 0.005, "SAS": 0.01, "AMR": 0.02},
        "*3A": {"AFR": 0.005, "EUR": 0.04, "EAS": 0.005, "SAS": 0.02, "AMR": 0.03},
        "*3C": {"AFR": 0.06, "EUR": 0.003, "EAS": 0.02, "SAS": 0.01, "AMR": 0.01},
    },
    "DPYD": {
        "*2A": {"AFR": 0.005, "EUR": 0.01, "EAS": 0.001, "SAS": 0.008, "AMR": 0.008},
        "c.2846A>T": {
            "AFR": 0.005,
            "EUR": 0.01,
            "EAS": 0.002,
            "SAS": 0.008,
            "AMR": 0.008,
        },
        "HapB3": {"AFR": 0.005, "EUR": 0.04, "EAS": 0.001, "SAS": 0.01, "AMR": 0.02},
    },
    "SLCO1B1": {
        "*5": {"AFR": 0.02, "EUR": 0.15, "EAS": 0.10, "SAS": 0.08, "AMR": 0.10},
    },
    "G6PD": {
        "A-": {"AFR": 0.22, "EUR": 0.005, "EAS": 0.005, "SAS": 0.05, "AMR": 0.05},
        "Mediterranean": {
            "AFR": 0.005,
            "EUR": 0.03,
            "EAS": 0.005,
            "SAS": 0.10,
            "AMR": 0.02,
        },
        "Canton": {"AFR": 0.001, "EUR": 0.001, "EAS": 0.05, "SAS": 0.01, "AMR": 0.005},
        "Kaiping": {
            "AFR": 0.001,
            "EUR": 0.001,
            "EAS": 0.03,
            "SAS": 0.005,
            "AMR": 0.003,
        },
    },
}

# Evidence strength per gene (how well-studied it is in each population)
# Scale: 0.0 (no evidence) to 1.0 (strong CPIC Level A evidence)
EVIDENCE_STRENGTH = {
    "CYP2D6": {"AFR": 0.7, "EUR": 1.0, "EAS": 0.9, "SAS": 0.6, "AMR": 0.7},
    "CYP2C19": {"AFR": 0.7, "EUR": 1.0, "EAS": 0.9, "SAS": 0.7, "AMR": 0.7},
    "CYP2C9": {"AFR": 0.5, "EUR": 1.0, "EAS": 0.7, "SAS": 0.6, "AMR": 0.6},
    "TPMT": {"AFR": 0.6, "EUR": 1.0, "EAS": 0.7, "SAS": 0.5, "AMR": 0.6},
    "DPYD": {"AFR": 0.4, "EUR": 0.9, "EAS": 0.5, "SAS": 0.4, "AMR": 0.5},
    "SLCO1B1": {"AFR": 0.6, "EUR": 1.0, "EAS": 0.8, "SAS": 0.6, "AMR": 0.6},
    "UGT1A1": {"AFR": 0.6, "EUR": 0.9, "EAS": 0.8, "SAS": 0.5, "AMR": 0.6},
    "G6PD": {"AFR": 0.8, "EUR": 0.7, "EAS": 0.7, "SAS": 0.6, "AMR": 0.6},
}

VALID_POPULATIONS = {"AFR", "EUR", "EAS", "SAS", "AMR"}


def compute_ancestry_confidence(
    gene: str,
    population: str,
    phenotype: str = "",
) -> Dict[str, object]:
    """
    Compute ancestry-adjusted confidence score for a PGx prediction.

    Args:
        gene: Pharmacogene name (e.g. "CYP2D6")
        population: Patient ancestry (AFR, EUR, EAS, SAS, AMR)
        phenotype: Predicted phenotype (e.g. "Poor Metabolizer")

    Returns:
        Dict with confidence score (0-1), evidence level, and notes.
    """
    pop = population.upper().strip()
    if pop not in VALID_POPULATIONS:
        return {
            "confidence": 0.5,
            "evidence_level": "unknown",
            "population": pop,
            "note": f"Ancestry '{pop}' not recognized. Using default confidence.",
        }

    evidence = EVIDENCE_STRENGTH.get(gene, {}).get(pop, 0.5)

    # Adjust confidence based on phenotype rarity in this population
    phenotype_penalty = 0.0
    pheno_lower = phenotype.lower()
    variant_freqs = POPULATION_VARIANT_FREQUENCIES.get(gene, {})
    if "poor" in pheno_lower and variant_freqs:
        # Poor metabolizers involve rare alleles — check frequency
        max_freq = max(
            (f.get(pop, 0.0) for f in variant_freqs.values()),
            default=0.0,
        )
        if max_freq < 0.01:
            phenotype_penalty = 0.15  # Rare in this population
        elif max_freq < 0.05:
            phenotype_penalty = 0.05

    confidence = max(0.1, min(1.0, evidence - phenotype_penalty))

    if evidence >= 0.9:
        level = "strong"
    elif evidence >= 0.7:
        level = "moderate"
    elif evidence >= 0.5:
        level = "limited"
    else:
        level = "insufficient"

    notes = []
    if evidence < 0.7:
        notes.append(
            f"{gene} evidence in {pop} population is limited. "
            "Guideline recommendations may not fully apply."
        )
    if phenotype_penalty > 0:
        notes.append(
            f"The predicted phenotype is rare in {pop} population. "
            "Consider confirmatory testing."
        )

    return {
        "confidence": round(confidence, 2),
        "evidence_level": level,
        "population": pop,
        "gene": gene,
        "note": " ".join(notes) if notes else "Well-characterized in this population.",
    }


def get_population_risk_summary(
    genes: List[str],
    population: str,
) -> List[Dict[str, object]]:
    """
    Get risk summary for multiple genes in a given population.

    Returns list of confidence scores and evidence levels.
    """
    results = []
    for gene in genes:
        result = compute_ancestry_confidence(gene, population)
        results.append(result)
    return results


def compute_ancestry_confidence_auto(
    gene: str,
    patient_genotypes: dict,
    phenotype: str = "",
) -> dict:
    """
    Like compute_ancestry_confidence but infers ancestry from genotype
    automatically using PCA on AIMs, then delegates to the standard scorer.
    """
    try:
        from .ancestry_inference import infer_ancestry

        inference = infer_ancestry(patient_genotypes)
        population = inference.get("inferred_population", "")
        result = compute_ancestry_confidence(gene, population, phenotype)
        result["ancestry_inferred"] = True
        result["ancestry_inference"] = inference
        return result
    except Exception:
        return compute_ancestry_confidence(gene, "UNKNOWN", phenotype)


def get_variant_frequency(
    gene: str,
    allele: str,
    population: str,
) -> Optional[float]:
    """
    Look up variant frequency for a specific allele in a population.

    Returns frequency (0.0-1.0) or None if not available.
    """
    pop = population.upper().strip()
    freqs = POPULATION_VARIANT_FREQUENCIES.get(gene, {}).get(allele, {})
    return freqs.get(pop)
