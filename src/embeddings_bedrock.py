"""
Bedrock Embeddings Wrapper

Provides a thin wrapper around Amazon Titan text embedding model.
"""

import json
from typing import List

try:
    import boto3
except Exception:  # pragma: no cover
    boto3 = None

from src.config import config
from src.exceptions import LLMError

_client = (
    boto3.client("bedrock-runtime", region_name=config.BEDROCK_REGION)
    if boto3 is not None
    else None
)


def get_embedding(text: str) -> List[float]:
    """
    Generate a text embedding using Amazon Titan.

    Args:
        text: Input text to embed.

    Returns:
        List of floats representing the embedding vector.
    """
    if _client is None:
        raise LLMError(
            "boto3 (AWS SDK) is not installed; cannot call Bedrock Titan embeddings",
            model=config.TITAN_EMBED_MODEL,
        )
    try:
        body = json.dumps({"inputText": text})
        response = _client.invoke_model(
            modelId=config.TITAN_EMBED_MODEL,
            body=body,
        )
        payload = json.loads(response["body"].read())
        embedding = payload.get("embedding")
        if embedding is None:
            raise LLMError(
                "Titan embedding response missing 'embedding' field",
                model=config.TITAN_EMBED_MODEL,
            )
        # Ensure we always return a list[float] for type safety.
        return [float(x) for x in embedding]
    except Exception as exc:  # pragma: no cover - network / AWS errors
        raise LLMError(
            f"Failed to generate Titan embedding: {exc}",
            model=config.TITAN_EMBED_MODEL,
        ) from exc
