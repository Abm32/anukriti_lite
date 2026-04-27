# Local Runtime Context

Date: 2026-04-27

This file is a handoff note so you can continue the Anukriti Lite setup tomorrow
without reconstructing the state from chat.

## Current Goal

Make Anukriti Lite ready as a strong Colosseum submission with:

- Deterministic pharmacogenomics trial exports.
- Solana hash/memo attestations for private, tamper-evident proof.
- QVAC local LLM explanations as an optional local backend.
- Streamlit demo surface for judges.

## Git State

Committed and pushed:

```text
commit: 2b0fce2
message: Position Anukriti Lite for Colosseum submission
remote: submission/main
repo: https://github.com/Abm32/anukriti_lite.git
branch in workspace: anukriti-lite-submission-main
```

The focused submission repo remote is:

```bash
git remote -v
# submission https://github.com/Abm32/anukriti_lite.git
```

## Files Added Or Updated For Submission

- `api.py`
  - Adds `_anukriti_lite_submission_metadata()`.
  - `GET /lite` now returns submission positioning for Colosseum, Solana, and QVAC.
  - `POST /lite/demo` now returns the same submission metadata plus export, attestation, verification, tamper demo, and optional devnet submission result.

- `app.py`
  - Adds a `Submission wedge` section to the `Solana Proofs` page.
  - Explains the Colosseum, Solana, and QVAC roles directly inside the live demo.

- `README.md`
  - Reframes Anukriti Lite as pharmacogenomics trial provenance.
  - Adds the submission thesis.

- `docs/ANUKRITI_LITE_COLOSSEUM.md`
  - Ties Solana and QVAC into one coherent judge-facing story.

- `docs/COLOSSEUM_SUBMISSION.md`
  - Copy-ready submission brief.

## Python Environment

Do not use the default `python` directly. It is:

```text
/usr/bin/python
Python 3.14.4
```

Use the existing project virtualenv instead:

```bash
.venv-train/bin/python --version
# Python 3.12.4
```

Dependency install completed successfully with:

```bash
.venv-train/bin/python -m pip install -r requirements.txt
```

The first sandboxed attempt failed because network access was blocked. The
approved escalated install completed successfully, including the large ML stack
and Torch. If you resume tomorrow and want to confirm, run:

```bash
.venv-train/bin/python -c "import fastapi, streamlit, pytest; print('python runtime ok')"
```

If that import fails after future environment changes, rerun:

```bash
.venv-train/bin/python -m pip install -r requirements.txt
```

## QVAC Environment

Node/npm are available when the shell loads your bash config:

```bash
source "$HOME/.bashrc" >/dev/null 2>&1
node --version
# v25.9.0
npm --version
# 11.13.0
```

QVAC dependency install completed successfully:

```bash
cd qvac
source "$HOME/.bashrc" >/dev/null 2>&1
npm install
```

Result:

```text
added 202 packages
found 0 vulnerabilities
```

This also created:

```text
qvac/package-lock.json
```

Keep it committed so the QVAC bridge dependencies are reproducible.

Run this check tomorrow:

```bash
cd qvac
source "$HOME/.bashrc" >/dev/null 2>&1
npm run check
```

QVAC role in the product:

- It is optional.
- It generates local explanation text.
- It does not make deterministic PGx calls.
- It does not publish anything to Solana.
- It uses `qvac/qvac_pgx_explain.mjs` and `@qvac/sdk`.

## Solana Environment

Prepared Solana proofs do not require a wallet. The app can generate:

```text
anukriti:<schema_version>:<payload_hash>
```

Actual devnet submission requires:

- Solana CLI installed.
- Configured devnet keypair.
- Devnet SOL.

Check tomorrow:

```bash
solana --version
solana config get
solana balance --url https://api.devnet.solana.com
```

If Solana CLI is not installed, the demo still works in prepared-proof mode.

## Start Commands

Once Python deps are installed:

Terminal 1:

```bash
.venv-train/bin/uvicorn api:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```bash
API_URL=http://127.0.0.1:8000 .venv-train/bin/streamlit run app.py
```

Open:

```text
http://127.0.0.1:8501
```

Judge demo path:

```text
Streamlit -> Solana Proofs -> Generate Proof
```

Optional API-only demo:

```bash
curl -s http://127.0.0.1:8000/lite

curl -s -X POST http://127.0.0.1:8000/lite/demo \
  -H "Content-Type: application/json" \
  -d '{"workflow":"clopidogrel_cyp2c19","submit_to_devnet":false}'
```

## Verification Commands

These checks were run and passed on 2026-04-27:

```bash
.venv-train/bin/python -c "import fastapi, streamlit, pytest; print('python runtime ok')"
.venv-train/bin/python -m py_compile api.py app.py
cd qvac && source "$HOME/.bashrc" >/dev/null 2>&1 && npm run check
.venv-train/bin/python -m pytest tests/test_qvac_llm.py tests/test_solana_attestation.py -q
```

Result:

```text
python runtime ok
QVAC node --check passed
8 passed in 1.05s
```

Run these again after any dependency or code changes:

```bash
.venv-train/bin/python -m py_compile api.py app.py
cd qvac && source "$HOME/.bashrc" >/dev/null 2>&1 && npm run check
.venv-train/bin/python -m pytest tests/test_qvac_llm.py tests/test_solana_attestation.py -q
```

If full tests are slow or pull models, at minimum verify:

```bash
.venv-train/bin/python -c "from api import app; print('api import ok')"
```

## Tomorrow's Next Steps

1. Confirm the Python install finished:

   ```bash
   .venv-train/bin/python -c "import fastapi, streamlit, pytest; print('python runtime ok')"
   ```

2. Run syntax and focused tests:

   ```bash
   .venv-train/bin/python -m py_compile api.py app.py
   .venv-train/bin/python -m pytest tests/test_qvac_llm.py tests/test_solana_attestation.py -q
   ```

3. Run QVAC check:

   ```bash
   cd qvac
   source "$HOME/.bashrc" >/dev/null 2>&1
   npm run check
   ```

4. Start API and Streamlit.

5. Open `Solana Proofs` and generate a proof.

6. Optional: configure Solana CLI and submit a devnet memo.

## Important Product Framing

Use this sentence for the submission:

```text
Anukriti Lite turns deterministic pharmacogenomics trial exports into private,
verifiable Solana proof artifacts, with QVAC available for local explanation text.
```

Use this explanation if asked what QVAC does:

```text
QVAC is the local explanation layer. It receives de-identified context and
deterministic PGx results, then writes concise clinical explanation text. It does
not decide the PGx result and it is separate from the Solana proof layer.
```

Use this explanation if asked what Solana does:

```text
Solana stores only a compact memo reference containing the schema label and
payload hash. The actual cohort rows, sample IDs, genotypes, phenotypes, and
recommendations stay off-chain.
```
