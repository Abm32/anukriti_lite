"""
Novel drug evidence aggregation and candidate-gene inference.

This module intentionally separates:
1) similarity retrieval evidence,
2) metadata-based biology evidence,
3) deterministic PGx coverage hints.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Set

from src.pgx_triggers import DRUG_GENE_TRIGGERS

PGX_GENE_SET: Set[str] = {
    # Tier 1 — CPIC Level A, highest clinical evidence
    "CYP2D6",
    "CYP2C19",
    "CYP2C9",
    "UGT1A1",
    "SLCO1B1",
    "VKORC1",
    "TPMT",
    "DPYD",
    "HLA_B5701",
    "HLA_B1502",
    # Tier 1 extended — CPIC Level A/B, newly activated callers
    "CYP3A4",
    "CYP3A5",
    "CYP1A2",
    "CYP2B6",
    "NAT2",
    "GSTM1",
    "GSTT1",
}


def _normalize_gene(text: str) -> Optional[str]:
    t = (text or "").strip().upper().replace("-", "_")
    if not t:
        return None
    if t in PGX_GENE_SET:
        return t
    if t == "HLA_B57_01":
        return "HLA_B5701"
    return None


def _extract_name(drug_entry: str) -> str:
    if "|" in (drug_entry or ""):
        return drug_entry.split("|", 1)[0].strip()
    return (drug_entry or "").strip()


def _genes_from_free_text(items: Sequence[str]) -> Set[str]:
    genes: Set[str] = set()
    for raw in items:
        upper = (raw or "").upper()
        for gene in PGX_GENE_SET:
            if gene in upper:
                genes.add(gene)
        if "HLA-B*57:01" in upper or "HLA_B5701" in upper:
            genes.add("HLA_B5701")
        if "HLA-B*15:02" in upper or "HLA_B1502" in upper:
            genes.add("HLA_B1502")
    return genes


def infer_novel_drug_hypothesis(
    *,
    drug_name: str,
    similar_drugs: Sequence[str],
    targets: Optional[Sequence[str]] = None,
    metabolism_enzymes: Optional[Sequence[str]] = None,
    transporters: Optional[Sequence[str]] = None,
    evidence_notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Infer candidate PGx genes and evidence for a novel drug.

    Returns a stable schema:
    {
      candidate_genes: [..],
      evidence_items: [{gene, source, weight, detail}],
      inference_confidence: float,
      reasoning_summary: str
    }
    """
    score_by_gene: Dict[str, float] = defaultdict(float)
    evidence_items: List[Dict[str, Any]] = []

    def add_evidence(gene: str, source: str, weight: float, detail: str) -> None:
        if gene not in PGX_GENE_SET:
            return
        score_by_gene[gene] += weight
        evidence_items.append(
            {
                "gene": gene,
                "source": source,
                "weight": round(weight, 3),
                "detail": detail,
            }
        )

    # 1) direct known trigger by drug name (if it happens to be known)
    known = DRUG_GENE_TRIGGERS.get((drug_name or "").strip().lower(), [])
    for gene in known:
        add_evidence(gene, "known_trigger_map", 1.0, f"Known trigger for {drug_name}")

    # 2) analog support via similar drug names
    for entry in similar_drugs or []:
        analog_name = _extract_name(entry)
        analog_genes = DRUG_GENE_TRIGGERS.get(analog_name.lower(), [])
        for gene in analog_genes:
            add_evidence(
                gene,
                "analog_trigger_map",
                0.6,
                f"Analog drug '{analog_name}' maps to {gene}",
            )

    # 3) explicit metadata support
    for raw in metabolism_enzymes or []:
        gene = _normalize_gene(raw)
        if gene:
            add_evidence(gene, "metabolism_enzymes", 0.9, f"Provided enzyme: {raw}")
    for raw in targets or []:
        gene = _normalize_gene(raw)
        if gene:
            add_evidence(gene, "targets", 0.7, f"Provided target: {raw}")
    for raw in transporters or []:
        gene = _normalize_gene(raw)
        if gene:
            add_evidence(gene, "transporters", 0.7, f"Provided transporter: {raw}")

    # 4) weak text-mined hints from freeform notes
    note_genes = _genes_from_free_text([evidence_notes or ""])
    for gene in note_genes:
        add_evidence(
            gene,
            "evidence_notes",
            0.3,
            "Gene keyword detected in evidence notes",
        )

    if not score_by_gene:
        return {
            "candidate_genes": [],
            "evidence_items": [],
            "inference_confidence": 0.0,
            "reasoning_summary": (
                "No gene-level evidence found from analogs or metadata. "
                "Inference remains exploratory."
            ),
        }

    ordered = sorted(score_by_gene.items(), key=lambda kv: kv[1], reverse=True)
    # candidate threshold keeps noise low, but always keep top-1 if any evidence exists
    candidates = [g for g, s in ordered if s >= 0.5] or [ordered[0][0]]

    top_score = ordered[0][1]
    total_signal = sum(score_by_gene.values())
    confidence = min(1.0, 0.2 + 0.2 * len(candidates) + 0.1 * top_score)
    confidence = max(0.1, min(confidence, 0.95))

    return {
        "candidate_genes": candidates,
        "evidence_items": evidence_items,
        "inference_confidence": round(confidence, 2),
        "reasoning_summary": (
            f"Inferred {len(candidates)} candidate gene(s) from "
            f"{len(evidence_items)} evidence item(s); total signal={total_signal:.2f}."
        ),
    }
