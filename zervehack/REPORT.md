# ZerveHack: Anukriti as a data → insight engine

## Question

**How reliable is Anukriti’s PGx retrieval layer at finding the right CPIC-aligned evidence, and what does that imply for “safe” explanation generation?**

This is deliberately **data-first**: we quantify retrieval quality and system correctness, then turn those metrics into product decisions (what to deploy, what to gate, what to improve).

## Data used (all repo-local, reproducible)

- **Evidence corpus (CPIC-aligned JSON)**: `data/pgx/cpic/*.json`
- **Labeled retrieval queries**: `data/training/pgx_sft.jsonl` (generated locally via `training/lm_finetune/export_pgx_sft_jsonl.py`)
- **Deterministic correctness benchmarks + ablation**: `scripts/run_benchmark_comparison.py` (GeT-RM truth sets + expanded validation + simulated ablations)

## Analysis performed

### 1) Retrieval evaluation (two modes)

- **Mode A (traceability test)**: queries include explicit `source` + `key` identifiers, answering:
  “If the system is told which CPIC row it should cite, does it actually retrieve that exact row?”
- **Mode B (realistic test)**: we strip the explicit `source`/`key` hints and evaluate:
  “If a user asks about a drug + phenotype without naming row ids, can we retrieve the correct evidence?”

Artifacts:

- `zervehack/artifacts/pgx_retrieval_eval.json`
  `zervehack/artifacts/pgx_retrieval_eval_summary.md`
- `zervehack/artifacts/pgx_retrieval_eval_hintless.json`

### 2) Correctness + ablation benchmark

We run the tool-comparison benchmark runner and persist JSON output:

- `zervehack/artifacts/benchmark_comparison.json`

## Key results (high signal)

### Retrieval (Mode A: with explicit row id hints)

- **misses@10: 0 / 174**
- **MRR: 1.000**

Interpretation: the indexing + doc-id scheme is consistent, so the system can be audited end-to-end (“did we cite the row we intended?”).

### Retrieval (Mode B: hintless / realistic)

From `zervehack/artifacts/pgx_retrieval_eval_hintless.json`:

- **misses@10: 164 / 174**
- **MRR: ~0.020**
- **recall@10: ~0.057**

Interpretation: in an offline environment (no Bedrock embeddings), the current TF‑IDF fallback is **insufficient** for semantic matching. This is a concrete engineering insight: **production deployments should prefer a real embedding backend** (e.g., Titan via Bedrock) or improved local embeddings, and the UI/API should **surface “evidence confidence”** to avoid overstating explanations.

### Deterministic PGx correctness (GeT‑RM + expanded validation)

From `zervehack/artifacts/benchmark_comparison.json`:

- **GeT‑RM (8 genes, 30 samples each): 100% concordance**
- **Expanded validation (25 patients × 5 pops × 4 genes in this run): 100% diplotype + phenotype concordance**

Interpretation: the “clinical decision core” is deterministic and highly consistent with the benchmark suite; the LLM should remain an **explanation layer** with explicit evidence gating.

## 3–5 actionable insights (what judges want)

1) **Measurable reliability gap**: removing hints causes a steep drop in hintless retrieval quality, proving that naive user queries can produce ungrounded evidence selection.
2) **Safety implication (“so what?”)**: in medical explanations, weak grounding can mislead decisions; ungrounded confidence is a real harm vector.
3) **Design response (decision, not observation)**: we enforce **evidence-confidence gating**—if evidence confidence is low, we refuse to answer rather than hallucinate.
4) **Operational transparency**: we surface backend health and fallback modes so the system can’t silently degrade in demos or production.
5) **Roadmap**: improve hintless grounding with real embedding backends (Titan) or stronger local embeddings + better query normalization.

## How to reproduce locally (quick)

```bash
# 1) Generate labeled query dataset (gitignored)
python training/lm_finetune/export_pgx_sft_jsonl.py --out data/training/pgx_sft.jsonl

# 2) Run retrieval eval artifact (writes JSON + markdown summary)
python scripts/zervehack/run_pgx_retrieval_eval_artifact.py

# 3) Run “hintless” retrieval eval (realistic user queries)
python scripts/zervehack/run_pgx_retrieval_eval_hintless.py

# 4) Run correctness benchmark + ablation and save JSON
python scripts/run_benchmark_comparison.py --expanded 25 --output zervehack/artifacts/benchmark_comparison.json
```
