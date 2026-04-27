"""
Structured PGx Output Helpers

Utilities to normalize deterministic PGx results together with
LLM explanations into a consistent, API-friendly schema.
"""

from typing import Any, Dict, Optional


def get_confidence(gene: str) -> float:
    """
    Simple confidence heuristic per gene, roughly reflecting CPIC
    evidence strength for the currently supported loci.
    """
    cpic_levels = {
        "SLCO1B1": 0.92,
        "CYP2C19": 0.95,
        "CYP2C9": 0.93,
    }
    return cpic_levels.get((gene or "").upper(), 0.8)


def format_output(pgx: Dict[str, Any], explanation: str) -> Dict[str, Any]:
    """
    Build a normalized PGx result object.

    Expected pgx keys (from callers such as interpret_slco1b1):
      - gene
      - variant / rsid
      - genotype
      - phenotype
      - risk
      - recommendation
    """
    gene = pgx.get("gene", "")
    variant = pgx.get("variant") or pgx.get("rsid")
    out: Dict[str, Any] = {
        "gene": gene,
        "variant": variant,
        "genotype": pgx.get("genotype"),
        "phenotype": pgx.get("phenotype"),
        "risk_level": pgx.get("risk"),
        "clinical_recommendation": pgx.get("recommendation"),
        "explanation": explanation,
        "confidence": get_confidence(gene),
    }
    if pgx.get("verification_status"):
        out["verification_status"] = pgx.get("verification_status")
    if pgx.get("verification_detail"):
        out["verification_detail"] = pgx.get("verification_detail")
    return out


def format_novel_drug_output(
    *,
    base_pgx: Optional[Dict[str, Any]],
    explanation: str,
    novel_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build a structured output for novel-drug analysis while keeping deterministic PGx
    fields when available.
    """
    base = format_output(base_pgx or {}, explanation)
    base["novel_drug"] = novel_metadata
    return base
