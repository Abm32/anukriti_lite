# Anukriti Lite: Colosseum Build Notes

## Positioning

Anukriti Lite is the Colosseum-facing version of Anukriti: a focused Solana proof
layer for deterministic pharmacogenomics trial exports, with QVAC as the local
explanation layer.

The product claim is deliberately narrow:

- Cohort PGx rows stay off-chain.
- Anukriti canonicalizes the export payload and hashes it with SHA-256.
- Solana stores only a compact memo proof reference.
- Reviewers can verify that a trial export was not changed after generation.
- QVAC can explain the deterministic result locally from de-identified context.
- Normal Simulation Lab runs also return a `simulation_result_attestation` proof,
  so hashing is now part of the real AI-engine pipeline, not only a standalone demo.

The submission thesis is:

```text
deterministic PGx export -> private off-chain artifact -> Solana proof reference
-> QVAC local explanation -> reproducible verification
```

## Demo Flow

1. Start the root Anukriti backend and Streamlit prototype.
2. Open the Streamlit app and choose `Solana Proofs` in the sidebar.
3. Choose `Clopidogrel / CYP2C19` or `Warfarin / CYP2C9 + VKORC1`.
4. Click `Generate Proof`.
5. Inspect:
   - deterministic cohort export rows
   - payload hash
   - Solana memo string
   - successful verification
   - tampered export rejection

The remix/video folders are not part of this implementation. The Colosseum
workaround lives in the root API and Streamlit prototype.

## Streamlit Surface

The root `app.py` includes a `Solana Proofs` sidebar page. It calls the root API
endpoints below and displays the proof artifact, export rows, verification result,
tamper failure, and downloadable JSON.

The main `Simulation Lab` also includes a `Solana Proof` result tab after each
run. That tab displays the per-simulation payload hash, schema, memo, proof
status, and downloadable proof JSON.

## API Surface

- `GET /lite` returns product metadata.
- `POST /lite/demo` returns a self-contained demo export, attestation, verification,
  and tamper check.
- `POST /analyze` returns an `attestation` block for the actual simulation result.
- `POST /analyze/novel-drug` returns an `attestation` block for novel-drug runs.
- `POST /attestations/verify` verifies any payload/attestation pair.
- `POST /attestations/submit` optionally submits an attestation memo using the local
  Solana CLI and configured devnet wallet.

`/trial/export` remains the real cohort export endpoint. The Lite API exists so a
hackathon judge can understand the complete proof loop without depending on local
VCF availability.

`GET /lite` and `POST /lite/demo` also include a `submission` object that spells
out the Colosseum wedge, the Solana privacy boundary, and the QVAC role.

## QVAC Partner Track

QVAC is wired as an optional local LLM explanation backend without replacing the
deterministic PGx engine or Solana proof layer.

```bash
cd qvac
npm install
npm run check
```

Then either select `QVAC (Local)` in the Streamlit sidebar, or send
`"llm_backend": "qvac"` to `POST /analyze` or `POST /analyze/novel-drug`.

The Python pipeline still performs PGx interpretation, retrieval, structured
output, and attestation. The QVAC bridge only receives de-identified clinical
context and returns explanatory text using the local `@qvac/sdk` model.

This is important for judging: QVAC is not competing with the deterministic
engine or the Solana proof. It makes the artifact more understandable while the
hash/memo layer makes the artifact auditable.

## Local Run

Backend:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Streamlit prototype:

```bash
streamlit run app.py
```

## Optional Devnet Submission

The default demo prepares the memo proof without submitting it. To submit through
the backend, configure the Solana CLI with a funded devnet keypair, then use the
`Submit memo to Solana devnet with local CLI` checkbox in the Streamlit page or
call `POST /lite/demo` with:

```json
{
  "workflow": "clopidogrel_cyp2c19",
  "submit_to_devnet": true
}
```

The API will attach the resulting signature and Explorer URL to the attestation.
