"""
Learned re-ranking for similar-drug retrieval (local ChEMBL fingerprints only).

Trained on weak labels from Tanimoto similarity on Morgan bit vectors; at inference
re-orders cosine top-pool candidates. Does not affect PGx allele calling or CPIC tables.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def pair_feature_matrix(query: np.ndarray, candidates: np.ndarray) -> np.ndarray:
    """
    query: (d,) float32/float64
    candidates: (n, d)
    Returns (n, 3): cosine, Tanimoto (bit), mean |q-c| (Hamming-like for 0/1).
    """
    q = query.astype(np.float64)
    C = candidates.astype(np.float64)
    dot = C @ q
    nq = float(np.sum(q))
    nc = np.sum(C, axis=1)
    qn = float(np.linalg.norm(q)) + 1e-12
    cn = np.linalg.norm(C, axis=1) + 1e-12
    cos = dot / (cn * qn)
    tani = dot / (nq + nc - dot + 1e-12)
    ham = np.mean(np.abs(C - q), axis=1)
    return np.column_stack([cos, tani, ham])


def tanimoto(q: np.ndarray, c: np.ndarray) -> float:
    q = q.astype(np.float64)
    c = c.astype(np.float64)
    dot = float(np.dot(q, c))
    nq = float(np.sum(q))
    nc = float(np.sum(c))
    return float(dot / (nq + nc - dot + 1e-12))


def load_reranker_bundle(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        import joblib
    except ImportError:  # pragma: no cover
        logger.warning("joblib not available; install scikit-learn")
        return None
    try:
        bundle = joblib.load(path)
        if not isinstance(bundle, dict) or "model" not in bundle:
            logger.warning("Invalid reranker bundle (expected dict with 'model')")
            return None
        return bundle
    except Exception as e:
        logger.warning(f"Failed to load drug reranker: {e}")
        return None


def rerank_top_indices(
    query_vec: np.ndarray,
    candidate_indices: np.ndarray,
    vectors: np.ndarray,
    bundle_path: Path,
    final_k: int,
) -> Tuple[np.ndarray, bool]:
    """
    Re-order candidate_indices by learned score; return first final_k indices.
    Returns (indices, used_reranker).
    """
    bundle = load_reranker_bundle(bundle_path)
    if bundle is None:
        return candidate_indices[:final_k], False

    model = bundle["model"]
    if candidate_indices.size == 0:
        return candidate_indices, True

    C = vectors[candidate_indices]
    X = pair_feature_matrix(query_vec, C)
    try:
        if hasattr(model, "predict_proba"):
            scores = model.predict_proba(X)[:, 1]
        else:
            scores = model.decision_function(X)
    except Exception as e:
        logger.warning(f"Reranker predict failed: {e}")
        return candidate_indices[:final_k], False

    order = np.argsort(-scores)
    ranked = candidate_indices[order]
    return ranked[:final_k], True
