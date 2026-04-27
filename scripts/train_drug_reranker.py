#!/usr/bin/env python3
"""
Train a small sklearn reranker for similar-drug retrieval.

Weak supervision: label pairs by Tanimoto similarity on Morgan fingerprints
(same representation as production). Positive if Tanimoto >= hi, negative if <= lo.

Usage (from repo root):
  python scripts/train_drug_reranker.py --output data/models/drug_reranker.joblib

Requires ChEMBL SQLite (or existing local vector .npz cache).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

from src.chembl_processor import batch_extract_drugs, find_chembl_db_path
from src.config import config
from src.ml.drug_reranker import pair_feature_matrix, tanimoto


def load_vectors() -> tuple[np.ndarray, np.ndarray]:
    """Load (vectors, norms) from local cache or build from ChEMBL."""
    cache = (
        Path(config.LOCAL_VECTOR_CACHE_DIR)
        / f"chembl_local_vectors_bits{config.FINGERPRINT_BITS}_limit{config.CHEMBL_LIMIT}.npz"
    )
    if cache.is_file():
        data = np.load(cache, allow_pickle=False)
        v = data["vectors"].astype(np.float32)
        n = data["norms"].astype(np.float32)
        return v, n

    db_path = config.CHEMBL_DB_PATH or find_chembl_db_path()
    if not db_path:
        raise SystemExit(
            "ChEMBL DB not found; set CHEMBL_DB_PATH or build local cache first."
        )
    records = batch_extract_drugs(
        str(db_path), limit=config.CHEMBL_LIMIT, batch_size=200
    )
    if not records:
        raise SystemExit("No ChEMBL records extracted.")
    v = np.array([rec["vector"] for rec in records], dtype=np.float32)
    n = np.linalg.norm(v, axis=1).astype(np.float32)
    return v, n


def sample_pairs(
    vectors: np.ndarray,
    n_pos: int,
    n_neg: int,
    hi: float,
    lo: float,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    m = vectors.shape[0]
    Xp: list[np.ndarray] = []
    Xn: list[np.ndarray] = []

    tries = 0
    max_tries = max(n_pos, n_neg) * 100
    while len(Xp) < n_pos and tries < max_tries:
        tries += 1
        i, j = int(rng.integers(0, m)), int(rng.integers(0, m))
        if i == j:
            continue
        t = tanimoto(vectors[i], vectors[j])
        if t >= hi:
            Xp.append(pair_feature_matrix(vectors[i], vectors[j : j + 1])[0])

    tries = 0
    while len(Xn) < n_neg and tries < max_tries:
        tries += 1
        i, j = int(rng.integers(0, m)), int(rng.integers(0, m))
        if i == j:
            continue
        t = tanimoto(vectors[i], vectors[j])
        if t <= lo:
            Xn.append(pair_feature_matrix(vectors[i], vectors[j : j + 1])[0])

    if len(Xp) < n_pos or len(Xn) < n_neg:
        raise SystemExit(
            f"Not enough pairs (pos={len(Xp)}/{n_pos}, neg={len(Xn)}/{n_neg}). "
            "Increase CHEMBL_LIMIT or relax --hi / --lo."
        )

    X = np.vstack(Xp + Xn)
    y = np.array([1] * len(Xp) + [0] * len(Xn), dtype=np.int32)
    return X, y


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "data" / "models" / "drug_reranker.joblib",
    )
    ap.add_argument("--n-pos", type=int, default=8000)
    ap.add_argument("--n-neg", type=int, default=8000)
    ap.add_argument(
        "--hi", type=float, default=0.45, help="Tanimoto threshold for positive"
    )
    ap.add_argument(
        "--lo", type=float, default=0.12, help="Tanimoto threshold for negative"
    )
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    vectors, _ = load_vectors()
    print(f"Loaded {vectors.shape[0]} fingerprints, dim={vectors.shape[1]}")

    X, y = sample_pairs(vectors, args.n_pos, args.n_neg, args.hi, args.lo, args.seed)
    print(f"Training samples: {X.shape[0]} pos={int(y.sum())} neg={int((1 - y).sum())}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=args.seed, stratify=y
    )
    model = LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        random_state=args.seed,
    )
    model.fit(X_train, y_train)
    proba = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, proba)
    print(f"Holdout ROC-AUC: {auc:.4f}")

    import joblib

    bundle = {
        "model": model,
        "feature": "cosine_tanimoto_hamming_mean_abs",
        "hi": args.hi,
        "lo": args.lo,
        "chembl_limit": config.CHEMBL_LIMIT,
        "fingerprint_bits": config.FINGERPRINT_BITS,
    }
    joblib.dump(bundle, args.output)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
