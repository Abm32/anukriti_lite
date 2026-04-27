# Anukriti MVP Trial Wedge

## ICP

- Translational medicine leads, biomarker leads, and pharmacometrics teams
- Seed to Series A biotech companies and CROs with existing VCF cohorts
- Immediate use case: retrospective PGx stratification before protocol decisions

## Single Wedge Workflow

1. Load cohort VCF(s)
2. Run deterministic PGx interpretation
3. Export trial-ready cohort rows for review

The wedge is designed to answer: "Would this cohort be stratified differently if PGx signals were applied now?"

## Scope Freeze

Only two workflows are in the MVP promise:

- `clopidogrel_cyp2c19`
- `warfarin_cyp2c9_vkorc1`

Everything else is secondary until pilot traction is demonstrated.

## API Contract

- `GET /trial/workflows` lists supported workflows.
- `POST /trial/export` returns deterministic rows with:
  - `called`
  - `cannot_call`
  - `insufficient_data`

Each row includes explicit `call_reason` so failures are visible and auditable.

## What Is Deferred

- Broad multi-gene expansion
- Clinical deployment narrative
- Complex AI UX enhancements
- Non-essential RAG/vector optimization work for trial MVP
