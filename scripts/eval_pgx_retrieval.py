#!/usr/bin/env python3
"""
Evaluate PGx guideline retrieval quality (precision@k / recall@k / MRR / nDCG).

This script uses the structured doc ids emitted by `src.rag.retriever.retrieve_docs()`,
which are stable identifiers of the form:  "<source_json>::<key>".

Default evaluation set:
  - derived from `data/training/pgx_sft.jsonl` produced by `export_pgx_sft_jsonl.py`
  - uses the JSONL's `meta.source` + `meta.key` as relevance labels (qrels)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Set

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

# Load repo .env before any code imports boto3 / Bedrock (embeddings client).
try:
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

from src.allele_caller import call_gene_from_variants
from src.citation_grounding import compute_explanation_grounding
from src.eval.retrieval_metrics import aggregate_scores, score_ranking
from src.rag.retriever import retrieve_docs


def load_queries_from_sft_jsonl(path: Path) -> List[Dict]:
    queries: List[Dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            msgs = obj.get("messages") or []
            meta = obj.get("meta") or {}
            # pick the user message as query text
            q = ""
            for m in msgs:
                if m.get("role") == "user":
                    q = m.get("content") or ""
                    break
            source = meta.get("source")
            key = meta.get("key")
            if not q or not source or not key:
                continue
            queries.append(
                {
                    "query": q,
                    "relevant_doc_ids": {f"{source}::{key}"},
                }
            )
    return queries


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--queries",
        type=Path,
        default=Path("data/training/pgx_sft.jsonl"),
        help="JSONL with messages+meta (default: exported SFT jsonl).",
    )
    ap.add_argument("--top_k", type=int, default=10)
    ap.add_argument("--ks", type=str, default="1,3,5,10")
    ap.add_argument("--limit", type=int, default=0, help="Optional limit on queries.")
    args = ap.parse_args()

    ks = [int(x) for x in args.ks.split(",") if x.strip()]
    try:
        queries = load_queries_from_sft_jsonl(args.queries)
    except FileNotFoundError:
        queries = []
    if args.limit and args.limit > 0:
        queries = queries[: args.limit]

    # --- Agent 2 / 5 reportable metrics (deterministic; no extra LLM calls) ---
    pgx_dir = _REPO_ROOT / "data" / "pgx"
    ctr: Counter[str] = Counter()
    scenarios = [
        ("cyp2c19", {}, "empty_variant_map"),
        ("cyp2c19", {"rs4244285": ("G", "A", "0/0")}, "hom_ref_observed"),
        ("cyp2c19", {"rs4244285": ("G", "A", "./.")}, "ambiguous_gt"),
    ]
    for gene, var_map, _label in scenarios:
        r = call_gene_from_variants(gene, var_map, base_dir=pgx_dir)
        if r:
            ctr[str(r.get("verification_status", ""))] += 1
    print("")
    print(
        "Deterministic call verification (PharmVar + CPIC table checks; sample scenarios)"
    )
    for k in sorted(ctr.keys()):
        print(f"  {k}: {ctr[k]}")

    passage = (
        "CYP2C19 poor metabolizers have reduced formation of the active clopidogrel metabolite "
        "and may exhibit higher platelet reactivity on standard doses."
    )
    aligned = (
        "Poor metabolizer status implies reduced active metabolite formation and higher "
        "platelet reactivity on clopidogrel standard doses."
    )
    g_aligned = compute_explanation_grounding(aligned, [passage])
    unrelated = "The moon is made of cheese and tastes excellent with crackers."
    g_unrelated = compute_explanation_grounding(unrelated, [passage])
    print("")
    print("Explanation grounding vs retrieved passages (synthetic sanity check)")
    al = g_aligned.get("grounded_sentence_fraction")
    ur = g_unrelated.get("grounded_sentence_fraction")
    print(f"  aligned explanation grounded_sentence_fraction: {al}")
    print(f"  unrelated text grounded_sentence_fraction: {ur}")

    if queries:
        q0 = queries[0]["query"]
        doc_texts = [d.text for d in retrieve_docs(q0, top_k=3)]
        pseudo_expl = (
            "This guidance reflects CPIC recommendations for the queried drug–gene pair; "
            "follow institutional protocol for dosing."
        )
        g_rag = compute_explanation_grounding(pseudo_expl, doc_texts)
        print("")
        print("Explanation grounding (first labeled retrieval query vs its top-3 docs)")
        print(
            f"  query[0] grounded_sentence_fraction: {g_rag.get('grounded_sentence_fraction')}"
        )
        print(f"  retrieval_passage_count: {g_rag.get('retrieval_passage_count')}")

    if not queries:
        print("")
        print(
            f"No labeled queries in {args.queries}; skipping retrieval ranking metrics."
        )
        return

    per_query = []
    misses = 0
    for item in queries:
        q: str = item["query"]
        relevant: Set[str] = set(item["relevant_doc_ids"])
        docs = retrieve_docs(q, top_k=args.top_k)
        ranked = [d.doc_id for d in docs]
        p_at, r_at, rr, ndcg_at = score_ranking(ranked, relevant, ks=ks)
        per_query.append((p_at, r_at, rr, ndcg_at))
        if rr == 0.0:
            misses += 1

    agg = aggregate_scores(per_query)
    print("")
    print("PGx retrieval evaluation")
    print(f"- queries: {len(per_query)}")
    print(f"- misses (no relevant in top_k): {misses}")
    print("")
    for k in sorted(agg.precision_at_k):
        print(
            f"precision@{k}: {agg.precision_at_k[k]:.3f}   recall@{k}: {agg.recall_at_k[k]:.3f}   ndcg@{k}: {agg.ndcg_at_k[k]:.3f}"
        )
    print(f"MRR: {agg.mrr:.3f}")


if __name__ == "__main__":
    main()
