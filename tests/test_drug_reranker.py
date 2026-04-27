"""Tests for optional drug similarity reranker features."""
import numpy as np

from src.ml.drug_reranker import pair_feature_matrix, tanimoto


def test_tanimoto_identical():
    q = np.array([1, 1, 0, 0], dtype=np.float32)
    assert abs(tanimoto(q, q) - 1.0) < 1e-6


def test_pair_feature_matrix_shape():
    q = np.random.randint(0, 2, size=128).astype(np.float32)
    C = np.random.randint(0, 2, size=(5, 128)).astype(np.float32)
    X = pair_feature_matrix(q, C)
    assert X.shape == (5, 3)
