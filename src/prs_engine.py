"""
Polygenic Risk Score (PRS) Engine.

Computes simplified polygenic risk scores for cardiovascular disease (CVD)
and Type 2 diabetes (T2D) from a patient's variant profile.

WHY THIS MATTERS FOR EQUITY:
- Most published PRS were developed using predominantly European-ancestry GWAS data
- The same PRS weights applied to non-European populations significantly underestimate
  or overestimate risk (sometimes by >2-fold)
- This is a direct analogue to the PGx equity story: algorithmic bias from training
  data homogeneity affects clinical predictions for underrepresented populations
- SynthaTrial uses the 1000 Genomes multi-ancestry dataset to make this gap visible

LOCI IMPLEMENTED:
1. Cardiovascular (CAD): CARDIoGRAM+C4D GWAS top loci (simplified subset)
   - rs4977574 (ANRIL), rs10757274 (CDKN2A/B), rs1333049 (CDKN2B-AS1)
   - rs3798220 (LPA), rs11206510 (PCSK9), rs2943634 (2q36.3)
   Source: Nikpay et al., Nature Genetics 2015 (PMID 26343387)

2. Type 2 Diabetes (T2D): DIAGRAM GWAS top loci (simplified subset)
   - rs7903146 (TCF7L2), rs8050136 (FTO), rs1801282 (PPARG)
   - rs5219 (KCNJ11), rs10811661 (CDKN2A/B)
   Source: Morris et al., Nature Genetics 2012; Mahajan et al., Nature Genetics 2018

IMPORTANT LIMITATIONS:
- These are simplified, didactic PRS implementations using a handful of loci.
  Clinical-grade PRS uses thousands to millions of variants.
- EUR-trained weights are used here to demonstrate (not resolve) the equity gap.
- Results should NOT be used for clinical decision making.
- Full population-calibrated PRS requires ancestry-matched summary statistics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# CAD (Coronary Artery Disease) PRS loci — CARDIoGRAM+C4D
# Format: rsid -> (risk_allele, effect_size_log_OR, eur_risk_freq, equity_note)
# ---------------------------------------------------------------------------

CAD_LOCI: Dict[str, Tuple[str, float, float, str]] = {
    "rs4977574": ("G", 0.093, 0.56, "Similar frequency across EUR/AFR/EAS"),
    "rs10757274": ("G", 0.118, 0.50, "CDKN2B-AS1 region; EUR freq ~50%"),
    "rs1333049": ("C", 0.126, 0.50, "Same CDKN2B-AS1 locus; high LD with rs10757274"),
    "rs3798220": (
        "C",
        0.238,
        0.02,
        "LPA variant; effect large but rare; AFR freq ~0.5%",
    ),
    "rs11206510": ("T", 0.089, 0.80, "PCSK9; AFR freq substantially lower"),
    "rs2943634": ("A", 0.066, 0.57, "2q36 locus; validated across ancestries"),
}

# Population-specific frequency adjustments for equity demonstration
# (risk allele frequency by superpopulation from 1000G Phase 3)
CAD_LOCI_POP_FREQ: Dict[str, Dict[str, float]] = {
    "rs4977574": {"AFR": 0.50, "AMR": 0.55, "EAS": 0.45, "EUR": 0.56, "SAS": 0.54},
    "rs10757274": {"AFR": 0.20, "AMR": 0.45, "EAS": 0.35, "EUR": 0.50, "SAS": 0.48},
    "rs1333049": {"AFR": 0.22, "AMR": 0.46, "EAS": 0.34, "EUR": 0.50, "SAS": 0.47},
    "rs3798220": {"AFR": 0.005, "AMR": 0.01, "EAS": 0.01, "EUR": 0.02, "SAS": 0.015},
    "rs11206510": {"AFR": 0.40, "AMR": 0.75, "EAS": 0.90, "EUR": 0.80, "SAS": 0.78},
    "rs2943634": {"AFR": 0.60, "AMR": 0.58, "EAS": 0.52, "EUR": 0.57, "SAS": 0.55},
}

# ---------------------------------------------------------------------------
# T2D (Type 2 Diabetes) PRS loci — DIAGRAM GWAS
# ---------------------------------------------------------------------------

T2D_LOCI: Dict[str, Tuple[str, float, float, str]] = {
    "rs7903146": (
        "T",
        0.356,
        0.28,
        "TCF7L2 — strongest T2D signal. EUR freq ~28%; AFR ~20%",
    ),
    "rs8050136": (
        "A",
        0.119,
        0.40,
        "FTO obesity locus; higher effect in obesity context",
    ),
    "rs1801282": (
        "C",
        0.093,
        0.12,
        "PPARG Pro12Ala; protective C allele more common in EUR",
    ),
    "rs5219": ("T", 0.083, 0.35, "KCNJ11 (Kir6.2); EUR/EAS similar; AFR differs"),
    "rs10811661": (
        "T",
        0.152,
        0.80,
        "CDKN2A/B; risk allele common in EUR; lower in AFR",
    ),
}

T2D_LOCI_POP_FREQ: Dict[str, Dict[str, float]] = {
    "rs7903146": {"AFR": 0.20, "AMR": 0.25, "EAS": 0.04, "EUR": 0.28, "SAS": 0.29},
    "rs8050136": {"AFR": 0.42, "AMR": 0.38, "EAS": 0.12, "EUR": 0.40, "SAS": 0.22},
    "rs1801282": {"AFR": 0.08, "AMR": 0.10, "EAS": 0.10, "EUR": 0.12, "SAS": 0.13},
    "rs5219": {"AFR": 0.25, "AMR": 0.35, "EAS": 0.40, "EUR": 0.35, "SAS": 0.32},
    "rs10811661": {"AFR": 0.50, "AMR": 0.72, "EAS": 0.85, "EUR": 0.80, "SAS": 0.78},
}


def compute_prs(
    variant_dosages: Dict[str, int],
    loci: Dict[str, Tuple[str, float, float, str]],
    ancestry: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute a simplified weighted PRS for a given set of loci.

    Args:
        variant_dosages: Dict rsid → dosage (0, 1, or 2 copies of the risk allele).
        loci: The PRS loci dict with (risk_allele, effect_size, eur_freq, note).
        ancestry: Optional superpopulation for frequency context.

    Returns:
        Dict with raw_score, z_score (EUR-baseline), risk_percentile, per_locus details.
    """
    raw_score = 0.0
    per_locus = []
    mean_score = 0.0
    var_score = 0.0

    for rsid, (risk_allele, effect_size, eur_freq, note) in loci.items():
        dosage = variant_dosages.get(rsid, 0)
        contribution = effect_size * dosage
        raw_score += contribution

        # Expected mean under HWE for EUR population
        expected_dosage = 2 * eur_freq
        mean_score += effect_size * expected_dosage
        # Expected variance under HWE
        var_score += (effect_size**2) * 2 * eur_freq * (1 - eur_freq)

        per_locus.append(
            {
                "rsid": rsid,
                "risk_allele": risk_allele,
                "dosage": dosage,
                "effect_size": round(effect_size, 4),
                "contribution": round(contribution, 4),
                "eur_risk_freq": eur_freq,
                "note": note,
            }
        )

    # Z-score relative to EUR mean
    sd_score = var_score**0.5 if var_score > 0 else 1.0
    z_score = (raw_score - mean_score) / sd_score if sd_score > 0 else 0.0

    # Rough risk percentile from z-score (normal approximation)
    risk_percentile = _z_to_percentile(z_score)

    # Risk tier
    if risk_percentile >= 90:
        risk_tier = "High (top 10% of EUR population)"
    elif risk_percentile >= 75:
        risk_tier = "Above Average (top 25% of EUR population)"
    elif risk_percentile >= 25:
        risk_tier = "Average"
    else:
        risk_tier = "Below Average"

    return {
        "raw_score": round(raw_score, 4),
        "z_score_eur_baseline": round(z_score, 3),
        "risk_percentile_eur": round(risk_percentile, 1),
        "risk_tier": risk_tier,
        "per_locus": per_locus,
        "loci_count": len(loci),
        "loci_with_data": sum(1 for r in loci if r in variant_dosages),
    }


def _z_to_percentile(z: float) -> float:
    """Approximate normal CDF for percentile conversion."""
    import math

    return 100.0 * (1 + math.erf(z / math.sqrt(2))) / 2


def _extract_dosages(
    variants: Dict[str, str],
    loci: Dict[str, Tuple[str, float, float, str]],
) -> Dict[str, int]:
    """
    Convert a variant dict (rsid → alt_allele or 'ref/alt genotype') to dosage.
    Accepts both simple alt-allele dicts and GT-format strings.
    """
    dosages: Dict[str, int] = {}
    for rsid, (risk_allele, _, _, _) in loci.items():
        val = variants.get(rsid, "")
        if not val:
            dosages[rsid] = 0
            continue
        # Handle GT format e.g. "0/1", "1/1", "0|1"
        if "/" in val or "|" in val:
            sep = "/" if "/" in val else "|"
            alleles = val.split(sep)
            # Count non-reference alleles as risk (simplified: 0=ref, 1=alt=risk)
            dosages[rsid] = sum(1 for a in alleles if a not in ("0", ".", ""))
        else:
            # Simple alt allele string: presence = 1
            dosages[rsid] = 1 if val.strip() else 0
    return dosages


def run_prs_analysis(
    patient_variants: Dict[str, str],
    ancestry: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run PRS analysis for both CAD and T2D from a patient's variant dict.

    Args:
        patient_variants: Dict rsid → alt allele or GT string.
        ancestry: Optional superpopulation code (AFR, AMR, EAS, EUR, SAS).

    Returns:
        Dict with cad and t2d PRS results, equity analysis, and disclaimer.
    """
    cad_dosages = _extract_dosages(patient_variants, CAD_LOCI)
    t2d_dosages = _extract_dosages(patient_variants, T2D_LOCI)

    cad_result = compute_prs(cad_dosages, CAD_LOCI, ancestry)
    t2d_result = compute_prs(t2d_dosages, T2D_LOCI, ancestry)

    # Equity analysis: estimate expected score for patient ancestry vs EUR training set
    equity_notes = _build_equity_analysis(ancestry)

    return {
        "cardiovascular_prs": {
            "trait": "Coronary Artery Disease (CAD)",
            "gwas_source": "CARDIoGRAM+C4D (Nikpay et al., Nat Genet 2015, PMID 26343387)",
            "loci_used": len(CAD_LOCI),
            **cad_result,
        },
        "diabetes_prs": {
            "trait": "Type 2 Diabetes (T2D)",
            "gwas_source": "DIAGRAM consortium (Mahajan et al., Nat Genet 2018, PMID 30297969)",
            "loci_used": len(T2D_LOCI),
            **t2d_result,
        },
        "ancestry": ancestry or "Unknown",
        "equity_analysis": equity_notes,
        "disclaimer": (
            "This is a simplified, didactic PRS using a handful of GWAS loci. "
            "Clinical-grade PRS uses thousands to millions of variants and requires "
            "ancestry-matched training data. These scores use EUR-derived weights and "
            "may systematically under- or over-estimate risk in non-European individuals. "
            "NOT for clinical use. Results are for research and educational purposes only."
        ),
        "streaming_note": "Variant data can be sourced from 1000 Genomes HTTPS streaming (no local download required).",
    }


def _build_equity_analysis(ancestry: Optional[str]) -> Dict[str, Any]:
    """
    Build equity context for PRS bias when using EUR-trained weights on non-EUR ancestry.
    """
    if not ancestry:
        return {
            "note": "Ancestry not provided. PRS scores use EUR-baseline weights.",
            "bias_risk": "Unknown — provide ancestry for equity contextualization.",
        }

    anc = ancestry.upper()
    bias_notes: Dict[str, str] = {
        "AFR": (
            "EUR-trained PRS typically underestimates CAD risk in African-ancestry individuals "
            "due to greater genetic diversity and lower LD with tag SNPs. "
            "Several top CAD loci (e.g. LPA rs3798220) are very rare in AFR populations — "
            "their effect may be attributed to private AFR variants not included in EUR GWAS. "
            "T2D PRS: TCF7L2 rs7903146 risk allele frequency ~20% AFR vs 28% EUR; "
            "FTO rs8050136 has similar frequencies. Overall T2D PRS less biased than CAD PRS."
        ),
        "EAS": (
            "EUR-trained CAD PRS shows reduced accuracy in East Asian populations. "
            "Key CAD loci frequencies differ substantially: rs10757274 (CDKN2B) ~35% EAS vs 50% EUR. "
            "T2D PRS: TCF7L2 rs7903146 is much rarer in EAS (~4% vs 28% EUR) — "
            "EAS T2D risk is driven by different loci (e.g. KCNQ1, CDC123) not captured here. "
            "EAS T2D PRS from EUR weights is particularly unreliable."
        ),
        "SAS": (
            "South Asian populations have the highest absolute T2D burden globally but "
            "EUR-trained T2D PRS performs moderately (some loci are shared). "
            "CAD risk in SAS is underestimated by EUR PRS — South Asian-specific risk loci "
            "(e.g. LIPA, SLC22A5) are not captured in standard EUR GWAS panels."
        ),
        "AMR": (
            "Admixed American populations show variable PRS performance depending on "
            "European admixture fraction. EUR-trained PRS may be better calibrated for "
            "individuals with higher EUR ancestry, and poorly calibrated for indigenous ancestry components."
        ),
        "EUR": (
            "EUR-trained PRS weights are calibrated for this population. "
            "Performance should be most accurate for EUR-ancestry individuals, "
            "though still limited by small loci count in this simplified implementation."
        ),
    }

    note = bias_notes.get(
        anc, f"Ancestry '{ancestry}' not in standard 1000G superpopulations."
    )

    return {
        "ancestry_code": anc,
        "eur_training_bias": note,
        "recommendation": (
            "For clinical risk assessment in non-EUR individuals, use ancestry-matched "
            "or multi-ancestry PRS (e.g. PGS Catalog multi-ancestry scores). "
            "See: https://www.pgscatalog.org"
        ),
        "equity_gap_severity": (
            "HIGH"
            if anc in ("AFR", "EAS")
            else "MODERATE" if anc in ("SAS", "AMR") else "LOW"
        ),
    }
