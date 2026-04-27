"""
PCA-based genetic ancestry inference from Ancestry-Informative Markers (AIMs).

Infers a patient's superpopulation (AFR, EUR, EAS, SAS, AMR) from their
genotype at ~30 high-Fst SNPs, using principal component analysis on a
pre-computed reference matrix derived from 1000 Genomes Phase 3.

This replaces the requirement for user-provided ancestry and enables
automatic ancestry-aware risk adjustment in the PGx pipeline.

IMPORTANT LIMITATIONS:
  - This is a simplified classifier using a small AIM panel.
  - Clinical-grade ancestry inference uses thousands of markers.
  - Admixed individuals may be classified with low confidence.
  - Results should be used to contextualise PGx predictions, NOT for
    race-based clinical decisions.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

SUPERPOPULATIONS = ["AFR", "EUR", "EAS", "SAS", "AMR"]

_REFERENCE_DATA: Optional[dict] = None

DEFAULT_PGX_DIR = Path(__file__).resolve().parent.parent / "data" / "pgx"


def _load_reference(base_dir: Optional[Path] = None) -> dict:
    """Load AIM reference panel and build the reference frequency matrix."""
    global _REFERENCE_DATA
    if _REFERENCE_DATA is not None:
        return _REFERENCE_DATA

    base = base_dir or DEFAULT_PGX_DIR
    path = base / "aims_reference.json"
    if not path.is_file():
        raise FileNotFoundError(f"AIMs reference not found: {path}")

    with open(path, "r") as f:
        raw = json.load(f)

    markers = raw["markers"]
    rsids = [m["rsid"] for m in markers]

    freq_matrix = np.zeros((len(markers), len(SUPERPOPULATIONS)), dtype=np.float64)
    for i, marker in enumerate(markers):
        for j, pop in enumerate(SUPERPOPULATIONS):
            freq_matrix[i, j] = marker["freqs"].get(pop, 0.0)

    mean = freq_matrix.mean(axis=1, keepdims=True)
    centered = freq_matrix - mean

    try:
        from sklearn.decomposition import PCA

        pca = PCA(n_components=min(5, len(SUPERPOPULATIONS)))
        ref_projected = pca.fit_transform(centered.T)
    except ImportError:
        U, S, Vt = np.linalg.svd(centered.T, full_matrices=False)
        ref_projected = U[:, :5] * S[:5]
        pca = None

    centroids = {}
    for j, pop in enumerate(SUPERPOPULATIONS):
        centroids[pop] = ref_projected[j]

    _REFERENCE_DATA = {
        "rsids": rsids,
        "markers": markers,
        "freq_matrix": freq_matrix,
        "mean": mean,
        "pca": pca,
        "ref_projected": ref_projected,
        "centroids": centroids,
    }
    return _REFERENCE_DATA


def infer_ancestry(
    patient_genotypes: Dict[str, Tuple[str, str, str]],
    base_dir: Optional[Path] = None,
) -> Dict[str, object]:
    """
    Infer superpopulation from a patient's genotype at AIM loci.

    Args:
        patient_genotypes: rsid -> (ref, alt, gt) from VCF
        base_dir: override for PGx data directory

    Returns:
        Dict with:
          - inferred_population: best-matching superpopulation code
          - ancestry_confidence: 0.0-1.0 (low = potentially admixed)
          - population_probabilities: dict of pop -> probability
          - markers_found: number of AIMs genotyped in this patient
          - markers_total: total AIMs in the panel
    """
    ref = _load_reference(base_dir)
    rsids = ref["rsids"]
    markers = ref["markers"]
    mean = ref["mean"]
    centroids = ref["centroids"]

    alt_freqs = np.full(len(rsids), 0.5, dtype=np.float64)
    found_count = 0

    for i, marker in enumerate(markers):
        rsid = marker["rsid"]
        if rsid in patient_genotypes:
            _, alt_allele, gt = patient_genotypes[rsid]
            dosage = _gt_to_dosage(gt)
            if dosage is not None:
                alt_freqs[i] = dosage / 2.0
                found_count += 1

    if found_count < 3:
        return {
            "inferred_population": "UNKNOWN",
            "ancestry_confidence": 0.0,
            "population_probabilities": {
                p: 1.0 / len(SUPERPOPULATIONS) for p in SUPERPOPULATIONS
            },
            "markers_found": found_count,
            "markers_total": len(rsids),
            "note": "Too few AIMs genotyped for reliable ancestry inference.",
        }

    patient_centered = alt_freqs - mean.flatten()

    pca = ref["pca"]
    if pca is not None:
        patient_projected = pca.transform(patient_centered.reshape(1, -1))[0]
    else:
        freq_matrix = ref["freq_matrix"]
        centered_ref = freq_matrix - mean
        U, S, Vt = np.linalg.svd(centered_ref.T, full_matrices=False)
        components = Vt[:5]
        patient_projected = patient_centered @ components.T

    distances = {}
    for pop, centroid in centroids.items():
        n_dims = min(len(patient_projected), len(centroid))
        distances[pop] = float(
            np.linalg.norm(patient_projected[:n_dims] - centroid[:n_dims])
        )

    inv_distances = {p: 1.0 / (d + 1e-8) for p, d in distances.items()}
    total_inv = sum(inv_distances.values())
    probabilities = {p: round(v / total_inv, 4) for p, v in inv_distances.items()}

    best_pop = min(distances, key=distances.get)
    sorted_dists = sorted(distances.values())

    if len(sorted_dists) >= 2 and sorted_dists[0] > 0:
        separation_ratio = sorted_dists[1] / (sorted_dists[0] + 1e-8)
        confidence = min(1.0, max(0.0, (separation_ratio - 1.0) / 2.0))
    else:
        confidence = 1.0

    markers_weight = min(1.0, found_count / (len(rsids) * 0.5))
    confidence = round(confidence * markers_weight, 3)

    note = ""
    if confidence < 0.3:
        note = (
            "Low confidence: patient may be admixed or have ancestry "
            "not well-represented by the 5-superpopulation model."
        )
    elif confidence < 0.6:
        note = "Moderate confidence. Consider confirmatory ancestry assessment."

    return {
        "inferred_population": best_pop,
        "ancestry_confidence": confidence,
        "population_probabilities": probabilities,
        "markers_found": found_count,
        "markers_total": len(rsids),
        "note": note,
    }


def _gt_to_dosage(gt: str) -> Optional[int]:
    """Convert VCF genotype to ALT dosage (0, 1, 2)."""
    if not gt:
        return None
    g = gt.replace("|", "/").strip()
    if g in ("0/0",):
        return 0
    if g in ("0/1", "1/0"):
        return 1
    if g in ("1/1",):
        return 2
    return None


def infer_ancestry_simple(
    patient_variants: Dict[str, str],
    base_dir: Optional[Path] = None,
) -> Dict[str, object]:
    """
    Simplified interface: rsid -> alt allele (no full VCF tuple).
    Constructs synthetic genotype tuples assuming heterozygous carrier.
    """
    genotypes = {}
    for rsid, alt in patient_variants.items():
        genotypes[rsid] = ("REF", alt, "0/1")
    return infer_ancestry(genotypes, base_dir=base_dir)
