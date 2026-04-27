#!/usr/bin/env python3
"""
Evaluate PGx retrieval when queries do NOT include explicit `source` / `key` hints.

This is closer to real user behavior: the user asks about a drug + phenotype
without naming the exact CPIC row id.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, os.fspath(REPO_ROOT))

from src.eval.retrieval_metrics import aggregate_scores, score_ranking  # noqa: E402
from src.rag.retriever import retrieve_docs  # noqa: E402


def _strip_hints(user_text: str) -> str:
    t = user_text or ""
    # Remove the explicit labeling lines and any "from X; key `Y`" patterns.
    t = re.sub(r"^Context.*\n", "", t, flags=re.IGNORECASE | re.MULTILINE)
    t = re.sub(r"\bfrom\s+[a-z0-9_.-]+\.json\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\bkey\s*[`'\"][^`'\"]+[`'\"]", "", t, flags=re.IGNORECASE)
    # Remove the literal context excerpt block that follows "Context..."
    t = re.sub(
        r"Context\s*\(.*?\):\s*\n.*?\n\n", "", t, flags=re.IGNORECASE | re.DOTALL
    )
    return t.strip()


def load_hintless_queries(path: Path) -> List[Tuple[str, Set[str]]]:
    out: List[Tuple[str, Set[str]]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            msgs = obj.get("messages") or []
            meta = obj.get("meta") or {}
            source = meta.get("source")
            key = meta.get("key")
            if not source or not key:
                continue
            user = ""
            for m in msgs:
                if m.get("role") == "user":
                    user = m.get("content") or ""
                    break
            q = _strip_hints(user)
            if not q:
                continue
            out.append((q, {f"{source}::{key}"}))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--queries",
        type=Path,
        default=Path("data/training/pgx_sft.jsonl"),
    )
    ap.add_argument("--top_k", type=int, default=10)
    ap.add_argument("--ks", type=str, default="1,3,5,10")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT
        / "zervehack"
        / "artifacts"
        / "pgx_retrieval_eval_hintless.json",
    )
    args = ap.parse_args()

    ks = [int(x) for x in args.ks.split(",") if x.strip()]
    qs = load_hintless_queries(args.queries)
    if args.limit and args.limit > 0:
        qs = qs[: args.limit]
    if not qs:
        raise SystemExit(f"No hintless queries found in {args.queries}")

    per_query = []
    misses = 0
    for q, relevant in qs:
        docs = retrieve_docs(q, top_k=args.top_k)
        ranked = [d.doc_id for d in docs]
        p_at, r_at, rr, ndcg_at = score_ranking(ranked, relevant, ks=ks)
        per_query.append((p_at, r_at, rr, ndcg_at))
        if rr == 0.0:
            misses += 1

    scores = aggregate_scores(per_query)
    payload: Dict = {
        "n_queries": len(per_query),
        "misses": misses,
        "scores": {
            "precision_at_k": scores.precision_at_k,
            "recall_at_k": scores.recall_at_k,
            "mrr": scores.mrr,
            "ndcg_at_k": scores.ndcg_at_k,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote: {args.out}")


if __name__ == "__main__":
    main()
