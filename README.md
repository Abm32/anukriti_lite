# Anukriti Lite

Colosseum submission for privacy-preserving pharmacogenomics trial provenance.

Anukriti Lite combines a deterministic pharmacogenomics engine with AI-generated
explanations, a lightweight Web3 verification layer, and an optional QVAC local
LLM bridge. It is a research prototype and is not intended for clinical use.

**Submission thesis:** Anukriti hashes simulation outputs and optionally anchors
them on-chain, enabling verifiable, tamper-proof validation of trial decisions
without exposing sensitive genomic data.

## What It Does

- Runs patient/drug pharmacogenomics simulations through FastAPI and Streamlit.
- Uses deterministic PGx callers for genes such as CYP2C19, CYP2C9, VKORC1,
  SLCO1B1, TPMT, DPYD, HLA-B*57:01, and HLA-B*15:02.
- Keeps patient data and full simulation outputs off-chain.
- Hashes canonical simulation/export payloads with SHA-256.
- Creates tamper-evident Web3 proof artifacts for trial design decisions.
- Produces Solana memo strings in the form
  `anukriti:<schema_version>:<payload_hash>`.
- Adds a QVAC partner-track backend for local LLM explanations via `@qvac/sdk`.

## Repo Shape

- `api.py` - FastAPI backend and API routes.
- `app.py` - Streamlit prototype UI.
- `src/` - PGx callers, retrieval, LLM bridges, Solana attestation code.
- `data/pgx/` - compact CPIC/PharmVar-style local PGx data.
- `qvac/` - QVAC JS SDK bridge.
- `docs/COLOSSEUM_SUBMISSION.md` - copy-ready Colosseum/Solana/QVAC submission
  brief.
- `docs/ANUKRITI_LITE_COLOSSEUM.md` - judge-facing flow.
- `docs/SOLANA_ATTESTATION.md` - attestation design.
- `tests/` - focused unit tests for PGx, QVAC, and attestations.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Start the API:

```bash
uvicorn api:app --host 127.0.0.1 --port 8000
```

Start the UI:

```bash
streamlit run app.py
```

Open `http://127.0.0.1:8501`.

## Solana Proof Flow

The app returns an `attestation` block for `/analyze`, `/analyze/novel-drug`,
`/trial/export`, and `/lite/demo`.

The default proof status is `prepared_not_submitted`: the backend prepares a
memo-safe Solana payload but does not publish patient data. Optional devnet
submission can be enabled from the Solana Proofs page when the host has a funded
devnet wallet and Solana CLI configured.

For the strongest judge demo, call `GET /lite` for the positioning metadata,
then `POST /lite/demo` to show export -> hash -> Solana memo -> verification ->
tamper rejection in one response.

## QVAC Partner Track

QVAC is optional. It does not replace the deterministic PGx engine; it only
generates explanation text from de-identified context.

```bash
cd qvac
npm install
npm run check
```

Then select `QVAC (Local)` in Streamlit or send:

```json
{
  "drug_name": "Clopidogrel",
  "patient_profile": "ID: demo\nAge: 45\nGenetics:\nCYP2C19: Poor Metabolizer",
  "llm_backend": "qvac"
}
```

to `POST /analyze`.

## Tests

```bash
python -m pytest tests/test_qvac_llm.py tests/test_solana_attestation.py -q
python -m pytest tests/test_core_callers.py tests/test_hla_caller.py tests/test_tpmt_dpyd.py -q
```

## Important Safety Notes

- Research/education only.
- LLMs explain deterministic outputs; they do not decide clinical risk.
- Solana stores only hashes/memos, not PHI or raw genetic data.
- Keep `.env`, wallets, VCF files, model caches, and generated videos out of git.
