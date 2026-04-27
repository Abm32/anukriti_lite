"""
Local open-source embeddings using sentence-transformers.

Replaces proprietary Amazon Titan embeddings with a biomedical-tuned
transformer model that runs locally. Eliminates vendor lock-in and
per-request costs.

Supported models (configurable via EMBEDDING_LOCAL_MODEL env var):
  - NeuML/pubmedbert-base-embeddings (default, 768-d, PubMed-tuned)
  - pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-sst2 (768-d)
  - any sentence-transformers compatible model
"""

from __future__ import annotations

import logging
import os
from threading import Lock
from typing import List, Optional

logger = logging.getLogger(__name__)

_model = None
_model_lock = Lock()

DEFAULT_MODEL = "NeuML/pubmedbert-base-embeddings"


def _get_model_name() -> str:
    return os.getenv("EMBEDDING_LOCAL_MODEL", DEFAULT_MODEL)


def _get_model():
    global _model
    if _model is not None:
        return _model

    with _model_lock:
        if _model is not None:
            return _model

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is required for local embeddings. "
                "Install with: pip install sentence-transformers"
            ) from exc

        model_name = _get_model_name()
        logger.info("Loading local embedding model: %s", model_name)
        _model = SentenceTransformer(model_name)
        logger.info(
            "Loaded %s (dimension=%d)",
            model_name,
            _model.get_sentence_embedding_dimension(),
        )
        return _model


def get_embedding(text: str) -> List[float]:
    """
    Generate a text embedding using a local sentence-transformers model.

    Drop-in replacement for embeddings_bedrock.get_embedding().
    """
    model = _get_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def get_embeddings_batch(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """Embed multiple texts efficiently in a single batch."""
    model = _get_model()
    vecs = model.encode(texts, batch_size=batch_size, normalize_embeddings=True)
    return vecs.tolist()


def get_embedding_dimension() -> int:
    """Return the dimensionality of the current model's embeddings."""
    model = _get_model()
    return model.get_sentence_embedding_dimension()


def get_model_info() -> dict:
    """Return metadata about the active embedding model."""
    model_name = _get_model_name()
    try:
        dim = get_embedding_dimension()
    except Exception:
        dim = None
    return {
        "backend": "local",
        "model": model_name,
        "dimension": dim,
    }
