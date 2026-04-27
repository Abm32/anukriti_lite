# Trial Evidence Pack

This pack defines a reproducible baseline for deterministic trial workflows.

## 1) Deterministic benchmark checks

Run:

```bash
python main.py --benchmark cpic_examples.json
python main.py --benchmark warfarin_examples.json
```

Expected outcome:

- CYP2C19 pathway benchmark reports deterministic expected-vs-predicted matches
- Warfarin benchmark reports deterministic recommendation matches

## 2) Trial workflow sanity checks (API)

Run:

```bash
curl -s http://localhost:8000/trial/workflows
```

Then call export for a small cohort:

```bash
curl -s -X POST http://localhost:8000/trial/export \
  -H "Content-Type: application/json" \
  -d '{
    "workflow":"clopidogrel_cyp2c19",
    "source":"auto",
    "sample_ids":["HG00096","HG00097"]
  }'
```

Repeat for warfarin:

```bash
curl -s -X POST http://localhost:8000/trial/export \
  -H "Content-Type: application/json" \
  -d '{
    "workflow":"warfarin_cyp2c9_vkorc1",
    "source":"auto",
    "sample_ids":["HG00096","HG00097"]
  }'
```

## 3) Evidence acceptance criteria

- No silent failure states
- Every row includes `call_state` and `call_reason`
- Summary counts reconcile with row states (`called`, `cannot_call`, `insufficient_data`)
- Mock vector fallback visibility remains explicit in `/analyze` audit

## 4) Partner-ready deliverables

- Raw JSON export from `/trial/export`
- Benchmark command outputs
- One-page interpretation memo per cohort:
  - Number of callable samples
  - Number requiring manual review
  - Actionable subgroup count for the target workflow

## 5) Novel-drug validation artifact

Generate baseline artifact:

```bash
python scripts/generate_novel_drug_validation_artifact.py
```

Inspect API artifact view:

```bash
curl -s http://localhost:8000/novel-drug/validation-artifact
```

Use `decision_grade` gates from `POST /analyze/novel-drug` before treating
novel-drug outputs as decision-grade guidance.
