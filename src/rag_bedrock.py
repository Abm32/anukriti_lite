"""
Bedrock RAG Pipeline

Connects Titan embeddings + domain retrieval + Claude reasoning into
one pharmacogenomics-oriented pipeline.
"""

from typing import Any, Dict, List, Optional

from src.config import config, resolve_nova_model_id
from src.exceptions import LLMError
from src.llm_bedrock import generate_pgx_response, generate_pgx_response_nova
from src.rag.retriever import retrieve


def build_query(
    drug_name: str,
    patient_profile: str,
    drug_smiles: Optional[str] = None,
    similar_drugs: Optional[List[str]] = None,
) -> str:
    """
    Build a compact textual query that describes the case.
    """
    parts = [
        f"Drug: {drug_name}",
        f"SMILES: {drug_smiles or 'not provided'}",
        "",
        "Patient profile:",
        patient_profile or "N/A",
    ]
    if similar_drugs:
        parts.append("")
        parts.append("Similar drugs (from vector search):")
        parts.extend(f"- {d}" for d in similar_drugs[:5])
    return "\n".join(parts)


def retrieve_context(embedding: list[float], drug_name: str) -> str:
    """
    TEMPORARY: simple PGx context stub.

    This should later be replaced by:
    - direct lookups into curated CPIC/PharmVar JSON,
    - or a vector DB (Pinecone / OpenSearch) populated from ChEMBL + PGx packs.
    """
    # The embedding is currently unused but included so the signature is ready
    # for vector DB integration.
    _ = embedding
    return f"""
Example PGx background knowledge (stub; do not treat as clinical guidance):

- SLCO1B1 reduced-function variants increase statin myopathy risk,
  especially with simvastatin; lower doses or alternative agents are often
  considered in guidelines.
- CYP2C19 poor metabolizers have reduced activation of clopidogrel, which
  can blunt antiplatelet effect; alternative agents may be preferred.
- CYP2C9 and VKORC1 variants alter warfarin sensitivity; guideline dosing
  algorithms adjust starting and maintenance doses accordingly.
- HLA-B*57:01 carriers are at high risk of severe abacavir hypersensitivity
  (immune-mediated, not metabolic). Abacavir is contraindicated in HLA-B*57:01
  positive patients. This is NOT a CYP-mediated interaction.
- HLA-B*15:02 carriers are at high risk of Stevens-Johnson syndrome / TEN
  with carbamazepine, oxcarbazepine, and phenytoin (immune-mediated).

Current query drug: {drug_name}
Only use background that is relevant; clearly state uncertainty when data
are extrapolated or limited.
"""


def run_bedrock_rag(
    drug_name: str,
    patient_profile: str,
    drug_smiles: Optional[str] = None,
    similar_drugs: Optional[List[str]] = None,
) -> str:
    """
    Run the Bedrock-backed RAG pipeline for a single drug + patient profile.
    """
    if not drug_name:
        raise ValueError("drug_name is required for Bedrock RAG pipeline")

    query = build_query(
        drug_name=drug_name,
        patient_profile=patient_profile,
        drug_smiles=drug_smiles,
        similar_drugs=similar_drugs,
    )

    # Retrieval over local PGx JSON (CPIC-style). If this fails or no docs
    # are found, fall back to a generic background stub.
    try:
        docs = retrieve(query, top_k=3)
    except Exception:
        docs = []

    if docs:
        context = "\n\n".join(docs)
    else:
        # Fallback context
        context = (
            "PGx background: SLCO1B1 for statin myopathy, CYP2C9+VKORC1 for "
            "warfarin dose sensitivity, CYP2C19 for clopidogrel activation, "
            "HLA-B*57:01 for abacavir hypersensitivity (immune-mediated, not CYP), "
            "HLA-B*15:02 for carbamazepine-class SJS/TEN (immune-mediated, not CYP). "
            "Use only conservative, guideline-aligned reasoning."
        )

    try:
        answer = generate_pgx_response(context=context, query=query, pgx_data=None)
        return answer
    except LLMError:
        raise
    except Exception as exc:  # pragma: no cover
        raise LLMError(
            f"Failed to generate Bedrock PGx response: {exc}",
            model=config.CLAUDE_MODEL,
        ) from exc


def run_nova_rag(
    drug_name: str,
    patient_profile: str,
    drug_smiles: Optional[str] = None,
    similar_drugs: Optional[List[str]] = None,
    nova_variant: Optional[str] = None,
) -> str:
    """
    Run the RAG pipeline using Amazon Nova Lite or Pro via Bedrock for explanation.
    Same flow as run_bedrock_rag but calls Nova instead of Claude.
    """
    if not drug_name:
        raise ValueError("drug_name is required for Nova RAG pipeline")

    query = build_query(
        drug_name=drug_name,
        patient_profile=patient_profile,
        drug_smiles=drug_smiles,
        similar_drugs=similar_drugs,
    )

    try:
        docs = retrieve(query, top_k=3)
    except Exception:
        docs = []

    if docs:
        context = "\n\n".join(docs)
    else:
        context = (
            "PGx background: SLCO1B1 for statin myopathy, CYP2C9+VKORC1 for "
            "warfarin dose sensitivity, CYP2C19 for clopidogrel activation, "
            "HLA-B*57:01 for abacavir hypersensitivity (immune-mediated, not CYP), "
            "HLA-B*15:02 for carbamazepine-class SJS/TEN (immune-mediated, not CYP). "
            "Use only conservative, guideline-aligned reasoning."
        )

    try:
        answer = generate_pgx_response_nova(
            context=context, query=query, pgx_data=None, nova_variant=nova_variant
        )
        return answer
    except LLMError:
        raise
    except Exception as exc:  # pragma: no cover
        raise LLMError(
            f"Failed to generate Nova PGx response: {exc}",
            model=resolve_nova_model_id(nova_variant),
        ) from exc
