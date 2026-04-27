"""
Bedrock LLM Wrapper (Claude + Amazon Nova)

Provides a focused interface for pharmacogenomics-style responses via Claude
or Amazon Nova Lite / Nova Pro via Bedrock Converse API.
"""

import os
from typing import Any, Dict, List, Optional

try:
    import boto3
    from botocore.config import Config as BotocoreConfig
except Exception:  # pragma: no cover
    boto3 = None
    BotocoreConfig = None  # type: ignore[assignment]

from src import metrics as _metrics
from src.config import config, resolve_nova_model_id
from src.exceptions import LLMError
from src.rate_limiter import get_rate_limiter

# Hard timeout on Bedrock calls: connect + read.
# Prevents a slow/hung Bedrock response from blocking the request thread.
_LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_CALL_TIMEOUT_SECONDS", "60"))

_client = (
    boto3.client(
        "bedrock-runtime",
        region_name=config.BEDROCK_REGION,
        config=BotocoreConfig(
            connect_timeout=10,
            read_timeout=_LLM_TIMEOUT_SECONDS,
            retries={"max_attempts": 0},  # tenacity handles retries; don't double-retry
        ),
    )
    if boto3 is not None and BotocoreConfig is not None
    else None
)


def _extract_converse_output_text(response: Dict[str, Any]) -> str:
    """
    Collect assistant text from Bedrock Converse responses.
    Nova and Claude both return output.message.content blocks; some models emit
    multiple blocks or omit text if misconfigured—handle defensively.
    """
    msg = (response.get("output") or {}).get("message") or {}
    blocks: List[Dict[str, Any]] = msg.get("content") or []
    parts: List[str] = []
    for block in blocks:
        if isinstance(block, dict) and block.get("text") is not None:
            parts.append(str(block["text"]))
    if not parts:
        raise ValueError(
            "No text in Converse response content blocks: "
            f"stopReason={response.get('stopReason')!r}"
        )
    return "\n".join(parts)


def _build_prompts(context: str, query: str, pgx_data: Optional[Dict[str, Any]]):
    """
    Build system + user prompts. If pgx_data is provided, we use the stricter
    schema where deterministic PGx results are the truth source.
    """
    if pgx_data:
        system_prompt = """
You are a clinical pharmacogenomics assistant.

STRICT RULES:
- Do NOT invent medical recommendations
- Use ONLY provided PGx data for decisions
- Your job is to EXPLAIN, not decide
"""

        user_prompt = f"""
PGx Result:
Gene: {pgx_data.get('gene', '')}
Genotype: {pgx_data.get('genotype', '')}
Phenotype: {pgx_data.get('phenotype', '')}
Risk: {pgx_data.get('risk', '')}
Recommendation: {pgx_data.get('recommendation', '')}

Additional Context:
{context}

Explain:
- Why this risk occurs
- What it means biologically
- Why the recommendation is given
"""
    else:
        system_prompt = (
            "You are a pharmacogenomics expert. Explain drug–gene interactions "
            "clearly, conservatively, and safely. Never give dosing instructions "
            "as if you were a prescriber; always frame outputs as research or "
            "educational insights, not clinical directives."
        )

        user_prompt = f"""
Context:
{context}

Question:
{query}

Provide, in order:
1. Risk level (Low / Medium / High) for this drug–patient combination.
2. Clinical meaning (1–2 short paragraphs).
3. Recommendation in non-prescriptive language (what a clinician should
   think about, not what to do).
"""

    return system_prompt, user_prompt


def generate_pgx_response(
    context: str, query: str, pgx_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate a pharmacogenomics explanation using Claude via Bedrock.

    Args:
        context: Retrieved domain knowledge / RAG context.
        query: User-specific question (drug + genetics / variant description).
        pgx_data: Optional deterministic PGx result (gene/genotype/phenotype/risk/recommendation).

    Returns:
        Model text response.
    """
    system_prompt, user_text = _build_prompts(context, query, pgx_data)

    if _client is None:
        raise LLMError(
            "boto3 (AWS SDK) is not installed; cannot call Bedrock Converse API",
            model=config.CLAUDE_MODEL,
        )

    # Apply rate limiting before API call
    rate_limiter = get_rate_limiter("claude")
    rate_limiter.throttle()

    try:
        response = _client.converse(
            modelId=config.CLAUDE_MODEL,
            system=[{"text": system_prompt}],
            messages=[
                {
                    "role": "user",
                    "content": [{"text": user_text}],
                }
            ],
            inferenceConfig={"maxTokens": 500, "temperature": 0.4},
        )
        _metrics.record_llm_call("bedrock_claude")
        return _extract_converse_output_text(response)
    except Exception as exc:  # pragma: no cover - network / AWS errors
        is_timeout = (
            "timeout" in str(exc).lower() or "ReadTimeout" in type(exc).__name__
        )
        _metrics.record_llm_call("bedrock_claude", timeout=is_timeout, error=True)
        raise LLMError(
            f"Failed to call Claude via Bedrock: {exc}",
            model=config.CLAUDE_MODEL,
        ) from exc


def generate_pgx_response_nova(
    context: str,
    query: str,
    pgx_data: Optional[Dict[str, Any]] = None,
    nova_variant: Optional[str] = None,
) -> str:
    """
    Generate a pharmacogenomics explanation using Amazon Nova via Bedrock.

    Calls Amazon Nova Lite or Nova Pro via the Bedrock Converse API for PGx
    explanations. Same prompt contract as Claude path.

    Args:
        context: Retrieved domain knowledge / RAG context.
        query: User-specific question (drug + genetics / variant description).
        pgx_data: Optional deterministic PGx result (gene/genotype/phenotype/risk/recommendation).
        nova_variant: ``lite`` or ``pro``; defaults to config NOVA_DEFAULT_VARIANT.

    Returns:
        Model text response.
    """
    system_prompt, user_text = _build_prompts(context, query, pgx_data)
    model_id = resolve_nova_model_id(nova_variant)

    if _client is None:
        raise LLMError(
            "boto3 (AWS SDK) is not installed; cannot call Bedrock Converse API",
            model=model_id,
        )

    # Apply rate limiting before API call
    rate_limiter = get_rate_limiter("nova")
    rate_limiter.throttle()

    try:
        response = _client.converse(
            modelId=model_id,
            system=[{"text": system_prompt}],
            messages=[
                {
                    "role": "user",
                    "content": [{"text": user_text}],
                }
            ],
            inferenceConfig={"maxTokens": 500, "temperature": 0.4},
        )
        _metrics.record_llm_call(
            f"bedrock_nova_{nova_variant or config.NOVA_DEFAULT_VARIANT}"
        )
        return _extract_converse_output_text(response)
    except Exception as exc:  # pragma: no cover - network / AWS errors
        is_timeout = (
            "timeout" in str(exc).lower() or "ReadTimeout" in type(exc).__name__
        )
        _metrics.record_llm_call(
            f"bedrock_nova_{nova_variant or config.NOVA_DEFAULT_VARIANT}",
            timeout=is_timeout,
            error=True,
        )
        raise LLMError(
            f"Failed to call Amazon Nova via Bedrock: {exc}",
            model=model_id,
        ) from exc
