# ZerveHack submission: Anukriti (PGx Insight Engine)

## Question

**A system that decides when NOT to trust AI in medical explanations.**

Core question: **When can we safely generate PGx explanations — and how do we *measure* whether the system is truly grounded in the right evidence?**

## Data

- **CPIC-aligned evidence corpus**: `data/pgx/cpic/*.json`
- **Labeled query set for retrieval evaluation** (reproducible): `data/training/pgx_sft.jsonl` generated from the corpus
- **Deterministic correctness benchmarks**: GeT‑RM truth sets + expanded synthetic validation (via `scripts/run_benchmark_comparison.py`)

## Analysis (what we ran)

1) **Retrieval quality** (precision@k / recall@k / MRR / nDCG)

   - Artifact: `zervehack/artifacts/pgx_retrieval_eval.json`
   - Summary: `zervehack/artifacts/pgx_retrieval_eval_summary.md`
2) **Hintless retrieval stress-test** (more realistic user prompts)

   - Artifact: `zervehack/artifacts/pgx_retrieval_eval_hintless.json`
3) **Correctness + ablation benchmark**

   - Artifact: `zervehack/artifacts/benchmark_comparison.json`

## Insights (judge-friendly)

- **Measurable reliability gap**: hintless queries can lead to weak grounding.
- **Safety implication**: weak grounding + confident language is unsafe in medical explanations.
- **System design response**: we enforce **evidence-confidence gating** and expose backend health (no silent fallbacks).

## Deployment (bonus)

We expose a small judge-facing API surface (FastAPI) and a UI surface (Streamlit):

- **API**:
  - `GET /zervehack/status` → retrieval backend mode + vector backend + operational metrics
  - `POST /zervehack/retrieve` → returns evidence rows with **scores** and a **refusal** when confidence is low
- **UI**:
  - Streamlit “Analytics” → **Evidence & Trust Dashboard** (calls the above endpoints)

## Demo script (≈5 minutes)

1) **Frame (30s)**: “We don’t just generate explanations; we measure whether they’re grounded in the right evidence.”
2) **Run analysis (90s)**:
   - Show `zervehack/REPORT.md` and the artifacts in `zervehack/artifacts/`.
   - Call out retrieval metrics + hintless stress-test.
3) **Live API (60s)**:
   - Hit `GET /zervehack/status`.
   - Run `POST /zervehack/retrieve` with a warfarin or statin query and show doc ids + evidence payload.
4) **Live UI (60–90s)**:
   - Open Streamlit → Analytics → “ZerveHack Panel”.
   - Show retrieved evidence + operational metrics in one view.
5) **Close (30s)**: 2 insights + 1 concrete next step (better embeddings / evidence gating).

## Reproduce locally

```bash
# 1) Install deps
python -m pip install -r requirements.txt

# 2) Generate labeled retrieval dataset (gitignored)
python training/lm_finetune/export_pgx_sft_jsonl.py --out data/training/pgx_sft.jsonl

# 3) Generate artifacts
python scripts/zervehack/run_pgx_retrieval_eval_artifact.py
python scripts/zervehack/run_pgx_retrieval_eval_hintless.py
python scripts/run_benchmark_comparison.py --expanded 25 --output zervehack/artifacts/benchmark_comparison.json

# 4) Run API + UI
uvicorn api:app --host 0.0.0.0 --port 8000
streamlit run app.py
```
