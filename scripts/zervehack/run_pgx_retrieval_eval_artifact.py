#!/usr/bin/env python3
"""
Generate a shareable retrieval-eval artifact for ZerveHack.

This script:
1) Ensures data/training/pgx_sft.jsonl exists (exported from repo CPIC JSON).
2) Runs the PGx retrieval evaluation.
3) Writes JSON + a short markdown summary under zervehack/artifacts/.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, os.fspath(REPO_ROOT))

from src.eval.pgx_retrieval_eval import as_dict, evaluate_pgx_retrieval  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--queries",
        type=Path,
        default=REPO_ROOT / "data" / "training" / "pgx_sft.jsonl",
        help="Labeled queries JSONL (meta.source + meta.key).",
    )
    ap.add_argument("--top_k", type=int, default=10)
    ap.add_argument("--ks", type=str, default="1,3,5,10")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--examples", type=int, default=10)
    ap.add_argument(
        "--out_dir",
        type=Path,
        default=REPO_ROOT / "zervehack" / "artifacts",
    )
    args = ap.parse_args()

    ks = [int(x.strip()) for x in args.ks.split(",") if x.strip()]
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Ensure queries file exists (gitignored; generated locally)
    if not args.queries.is_file():
        exporter = REPO_ROOT / "training" / "lm_finetune" / "export_pgx_sft_jsonl.py"
        raise SystemExit(
            f"Missing {args.queries}. Generate it via: python {exporter} --out {args.queries}"
        )

    res = evaluate_pgx_retrieval(
        args.queries,
        top_k=int(args.top_k),
        ks=ks,
        limit=int(args.limit),
        examples=int(args.examples),
    )
    payload = as_dict(res)

    out_json = args.out_dir / "pgx_retrieval_eval.json"
    out_md = args.out_dir / "pgx_retrieval_eval_summary.md"

    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    scores = payload["scores"]

    def _get_metric(d: dict, k: int) -> float:
        if k in d:
            return float(d[k])
        if str(k) in d:
            return float(d[str(k)])
        raise KeyError(k)

    ks_sorted = sorted(int(k) for k in scores["precision_at_k"].keys())
    lines = [
        "## PGx retrieval evaluation (ZerveHack artifact)",
        "",
        f"- queries_scored: **{payload['n_queries']}**",
        f"- misses_top_k: **{payload['misses']}** (no relevant doc in top_k)",
        f"- MRR: **{scores['mrr']:.3f}**",
        "",
        "### Aggregate metrics",
        "",
        "| k | precision@k | recall@k | nDCG@k |",
        "|---:|---:|---:|---:|",
    ]
    for k in ks_sorted:
        p = _get_metric(scores["precision_at_k"], k)
        r = _get_metric(scores["recall_at_k"], k)
        n = _get_metric(scores["ndcg_at_k"], k)
        lines.append(f"| {k} | {p:.3f} | {r:.3f} | {n:.3f} |")

    lines.extend(
        [
            "",
            "### Example queries",
            "",
            "(See `pgx_retrieval_eval.json` for full example payload.)",
            "",
        ]
    )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
