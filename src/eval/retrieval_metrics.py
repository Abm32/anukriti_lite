from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Set, Tuple


@dataclass(frozen=True)
class RetrievalScores:
    precision_at_k: Dict[int, float]
    recall_at_k: Dict[int, float]
    mrr: float
    ndcg_at_k: Dict[int, float]


def _dcg(rels: Sequence[int]) -> float:
    # rels: relevance labels (0/1) in ranked order
    s = 0.0
    for i, rel in enumerate(rels, start=1):
        if rel <= 0:
            continue
        s += (2**rel - 1) / math.log2(i + 1)
    return s


def score_ranking(
    ranked_doc_ids: Sequence[str],
    relevant_doc_ids: Set[str],
    ks: Iterable[int] = (1, 3, 5, 10),
) -> Tuple[Dict[int, float], Dict[int, float], float, Dict[int, float]]:
    """
    Compute per-query metrics given ranked doc ids and a set of relevant doc ids.
    - precision@k, recall@k
    - MRR (first relevant)
    - nDCG@k (binary relevance)
    """
    ks = sorted(set(int(k) for k in ks if int(k) > 0))
    if not ks:
        raise ValueError("ks must contain at least one positive integer")

    rel_list = [1 if d in relevant_doc_ids else 0 for d in ranked_doc_ids]
    n_rel = len(relevant_doc_ids)

    precision_at: Dict[int, float] = {}
    recall_at: Dict[int, float] = {}
    ndcg_at: Dict[int, float] = {}

    for k in ks:
        top = rel_list[:k]
        tp = sum(top)
        precision_at[k] = tp / k
        recall_at[k] = tp / n_rel if n_rel > 0 else 0.0

        dcg = _dcg(top)
        ideal = _dcg([1] * min(n_rel, k))
        ndcg_at[k] = (dcg / ideal) if ideal > 0 else 0.0

    # MRR
    rr = 0.0
    for i, d in enumerate(ranked_doc_ids, start=1):
        if d in relevant_doc_ids:
            rr = 1.0 / i
            break

    return precision_at, recall_at, rr, ndcg_at


def aggregate_scores(
    per_query: List[Tuple[Dict[int, float], Dict[int, float], float, Dict[int, float]]]
) -> RetrievalScores:
    if not per_query:
        raise ValueError("No per-query scores to aggregate")

    ks = sorted(per_query[0][0].keys())
    p = {k: 0.0 for k in ks}
    r = {k: 0.0 for k in ks}
    n = {k: 0.0 for k in ks}
    mrr = 0.0

    for p_at, r_at, rr, ndcg_at in per_query:
        for k in ks:
            p[k] += p_at[k]
            r[k] += r_at[k]
            n[k] += ndcg_at[k]
        mrr += rr

    denom = float(len(per_query))
    return RetrievalScores(
        precision_at_k={k: p[k] / denom for k in ks},
        recall_at_k={k: r[k] / denom for k in ks},
        mrr=mrr / denom,
        ndcg_at_k={k: n[k] / denom for k in ks},
    )
