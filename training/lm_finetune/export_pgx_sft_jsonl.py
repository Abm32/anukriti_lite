#!/usr/bin/env python3
"""
Build a supervised fine-tuning (SFT) JSONL dataset from repo-shipped CPIC-aligned JSON.

Output format: one JSON object per line, each with a "messages" list for chat models:
  [{"role":"system",...},{"role":"user",...},{"role":"assistant",...}]

This is intended for research / RAG-style explanation tuning—not clinical deployment.
Review CPIC/PharmGKB licensing before redistributing derived datasets.

Usage (from repo root):
  python training/lm_finetune/export_pgx_sft_jsonl.py \\
    --out data/training/pgx_sft.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
CPIC_DIR = REPO_ROOT / "data" / "pgx" / "cpic"

SYSTEM = (
    "You are a pharmacogenomics research assistant. Your answers are for research "
    "and education only—not medical advice, diagnosis, or prescribing. "
    "Ground every claim in the provided context. If context is insufficient, say so. "
    "Do not invent patient genotypes or allele calls. Remind the reader that clinical "
    "decisions require licensed professionals and formal testing."
)

SYNTHETIC_PROFILES = [
    "Synthetic cohort participant (de-identified); genotype confirmed in research assay only.",
    "Research VCF profile (not for clinical use); star alleles from pipeline output.",
    "Hypothetical teaching case; genotypes illustrative only.",
]


def _flatten_cpic_obj(obj: Any, prefix: str = "") -> Iterator[Tuple[str, str]]:
    """Yield (path_key, value_str) leaves for nested dicts."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).startswith("_"):
                continue
            p = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                yield from _flatten_cpic_obj(v, p)
            elif isinstance(v, (str, int, float, bool)):
                yield p, str(v)
            else:
                yield p, json.dumps(v, ensure_ascii=False)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _flatten_cpic_obj(v, f"{prefix}[{i}]")


def _infer_drug_hints(filename: str) -> List[str]:
    stem = Path(filename).stem.lower()
    hints = {
        "cyp2c19_phenotypes": ["clopidogrel", "omeprazole"],
        "cyp2c9_phenotypes": ["warfarin", "celecoxib"],
        "cyp2d6_phenotypes": ["codeine", "tramadol", "metoprolol"],
        "dpyd_phenotypes": ["fluorouracil", "capecitabine"],
        "tpmt_phenotypes": ["azathioprine", "mercaptopurine"],
        "ugt1a1_phenotypes": ["irinotecan"],
        "slco1b1_phenotypes": ["simvastatin", "atorvastatin"],
        "vkorc1_phenotypes": ["warfarin"],
        "warfarin_response": ["warfarin"],
        "statin_guidelines": ["simvastatin", "atorvastatin", "rosuvastatin"],
        "fluoropyrimidine_guidelines": ["fluorouracil", "capecitabine"],
        "thiopurine_guidelines": ["azathioprine", "mercaptopurine"],
    }
    return hints.get(stem, ["unspecified drug (use context only)"])


def _make_example(
    source_file: str,
    context_key: str,
    context_value: str,
    drug: str,
    rng: random.Random,
) -> Dict[str, List[Dict[str, str]]]:
    profile = rng.choice(SYNTHETIC_PROFILES)
    user = (
        f"Context (CPIC-aligned table excerpt from {source_file}; key `{context_key}`):\n"
        f"{context_value}\n\n"
        f"Drug of interest: {drug}\n"
        f"Patient: {profile}\n\n"
        "Explain the pharmacogenomic implication in plain language for a research "
        "protocol briefing. Cite uncertainty and next verification steps."
    )
    assistant = (
        f"Using only the provided context for `{context_key}`: the table indicates "
        f"«{context_value}». For {drug}, this is a research-level interpretation aligned "
        "with CPIC-style gene–drug knowledge in our corpus—not a directive for dosing. "
        "Analytical validation, indication-specific guidelines, and clinical judgment "
        "are still required. If any genotype is uncertain or imputed, repeat testing with "
        "an accredited assay is appropriate before clinical use."
    )
    return {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "meta": {"source": source_file, "key": context_key},
    }


def export_jsonl(out_path: Path, seed: int = 42) -> int:
    rng = random.Random(seed)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out_path.open("w", encoding="utf-8") as fout:
        for path in sorted(CPIC_DIR.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            drugs = _infer_drug_hints(path.name)
            for key, val in _flatten_cpic_obj(data):
                drug = rng.choice(drugs)
                ex = _make_example(path.name, key, val, drug, rng)
                fout.write(json.dumps(ex, ensure_ascii=False) + "\n")
                n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description="Export PGx SFT JSONL from data/pgx/cpic")
    ap.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "data" / "training" / "pgx_sft.jsonl",
    )
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    count = export_jsonl(args.out, seed=args.seed)
    print(f"Wrote {count} examples to {args.out}")


if __name__ == "__main__":
    main()
