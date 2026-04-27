"""
Confidence tier contract for novel-drug PGx outputs.
"""

from __future__ import annotations

from typing import Any, Dict, List


def classify_confidence_tier(
    *,
    inference_confidence: float,
    candidate_genes: List[str],
    deterministic_callable_genes: List[str],
    evidence_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Tiering policy:
    - high: CPIC-backed deterministic mapping available for >=1 inferred gene
    - moderate: no deterministic coverage, but strong multi-source evidence
    - exploratory: sparse/similarity-only evidence
    """
    conf = float(inference_confidence or 0.0)
    evidence_sources = {str(item.get("source", "")) for item in evidence_items or []}
    source_count = len({s for s in evidence_sources if s})
    has_deterministic = len(deterministic_callable_genes or []) > 0

    if has_deterministic and conf >= 0.45:
        tier = "high"
        rationale = "At least one inferred gene is covered by deterministic CPIC/PharmVar pathways."
    elif conf >= 0.55 and source_count >= 2:
        tier = "moderate"
        rationale = (
            "Inference is supported by multiple evidence sources, but deterministic "
            "coverage for inferred genes is incomplete."
        )
    else:
        tier = "exploratory"
        rationale = "Evidence is limited and/or similarity-led. Use for hypothesis generation only."

    return {
        "confidence_tier": tier,
        "rationale": rationale,
        "inference_confidence": round(conf, 2),
        "candidate_genes": candidate_genes or [],
        "deterministic_callable_genes": deterministic_callable_genes or [],
        "evidence_source_count": source_count,
    }
