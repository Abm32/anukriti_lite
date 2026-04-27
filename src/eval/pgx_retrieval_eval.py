from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from src.eval.retrieval_metrics import RetrievalScores, aggregate_scores, score_ranking
from src.rag.retriever import retrieve_docs


@dataclass(frozen=True)
class RetrievalEvalExample:
    query_preview: str
    relevant_doc_id: str
    ranked_doc_ids: List[str]
    hit: bool
    rr: float


@dataclass(frozen=True)
class RetrievalEvalResult:
    n_queries: int
    misses: int
    scores: RetrievalScores
    examples: List[RetrievalEvalExample]


def _load_queries_from_sft_jsonl(path: Path) -> List[Tuple[str, Set[str]]]:
    queries: List[Tuple[str, Set[str]]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            msgs = obj.get("messages") or []
            meta = obj.get("meta") or {}

            q = ""
            for m in msgs:
                if m.get("role") == "user":
                    q = m.get("content") or ""
                    break
            source = meta.get("source")
            key = meta.get("key")
            if not q or not source or not key:
                continue
            queries.append((q, {f"{source}::{key}"}))
    return queries


def evaluate_pgx_retrieval(
    queries_path: Path = Path("data/training/pgx_sft.jsonl"),
    *,
    top_k: int = 10,
    ks: Iterable[int] = (1, 3, 5, 10),
    limit: int = 50,
    examples: int = 10,
) -> RetrievalEvalResult:
    """
    Run retrieval quality evaluation for the PGx retriever.

    Relevance labels are taken from the SFT export JSONL's `meta.source` + `meta.key`.
    This answers: "When the query mentions a specific CPIC row, do we retrieve that row?"
    """
    ks = tuple(int(k) for k in ks)
    if top_k <= 0:
        raise ValueError("top_k must be > 0")

    qs = _load_queries_from_sft_jsonl(queries_path)
    if limit and limit > 0:
        qs = qs[:limit]
    if not qs:
        raise ValueError(f"No labeled queries found in {queries_path}")

    per_query = []
    ex_rows: List[RetrievalEvalExample] = []
    misses = 0

    for q, relevant in qs:
        docs = retrieve_docs(q, top_k=top_k)
        ranked = [d.doc_id for d in docs]
        p_at, r_at, rr, ndcg_at = score_ranking(ranked, relevant, ks=ks)
        per_query.append((p_at, r_at, rr, ndcg_at))
        hit = rr > 0.0
        if not hit:
            misses += 1

        if len(ex_rows) < examples:
            preview = (q or "").replace("\n", " ").strip()
            if len(preview) > 140:
                preview = preview[:137] + "..."
            ex_rows.append(
                RetrievalEvalExample(
                    query_preview=preview,
                    relevant_doc_id=next(iter(relevant)),
                    ranked_doc_ids=ranked[: min(len(ranked), max(ks))],
                    hit=hit,
                    rr=rr,
                )
            )

    scores = aggregate_scores(per_query)
    return RetrievalEvalResult(
        n_queries=len(per_query),
        misses=misses,
        scores=scores,
        examples=ex_rows,
    )


def as_dict(result: RetrievalEvalResult) -> Dict:
    return {
        "n_queries": result.n_queries,
        "misses": result.misses,
        "scores": asdict(result.scores),
        "examples": [asdict(e) for e in result.examples],
    }
