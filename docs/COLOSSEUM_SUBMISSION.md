# Anukriti Lite Colosseum Submission Brief

## Project Title

Anukriti Lite

## One-Liner

Anukriti Lite turns deterministic pharmacogenomics trial exports into private,
verifiable Solana proof artifacts, with QVAC available for local explanation
text.

## Short Description

Anukriti Lite is a focused clinical-trial provenance product. It runs
deterministic pharmacogenomics logic for trial cohort rows, keeps the sensitive
rows off-chain, canonicalizes the export, hashes it with SHA-256, and prepares a
Solana memo proof reference. Sponsors, reviewers, or auditors can later verify
that the export was not changed after generation.

QVAC is integrated as a local LLM explanation backend. It does not decide the
clinical result. The deterministic PGx engine remains the source of truth, while
QVAC converts de-identified context and PGx calls into concise explanation text.

## Why It Belongs In Colosseum

Most crypto healthcare ideas start broad: medical records, data marketplaces,
identity, or patient portals. Anukriti Lite is deliberately narrower. It focuses
on one high-value artifact in clinical research: the pharmacogenomics cohort
export used to stratify trial participants.

The wedge is:

```text
PGx trial export -> canonical JSON -> SHA-256 hash -> Solana memo -> verification
```

That makes the product easy to demo, privacy-preserving by default, and useful
for real audit workflows.

## Solana Integration

Solana is the proof layer. The full export stays off-chain. The memo contains
only:

```text
anukriti:<schema_version>:<payload_hash>
```

Implemented surfaces:

- `src/solana_attestation.py` builds canonical hashes, Solana memo strings, and
  verification results.
- `POST /trial/export` returns deterministic cohort rows plus an attestation.
- `POST /lite/demo` returns a complete demo export, attestation, verification,
  and tamper failure.
- `POST /attestations/verify` verifies payloads against attestations.
- `POST /attestations/submit` can submit the memo through a configured Solana
  devnet CLI wallet.
- Streamlit includes a `Solana Proofs` page for judge demos.

## QVAC Integration

QVAC is the local explanation layer. It is optional, private, and downstream of
deterministic PGx calling.

Implemented surfaces:

- `qvac/qvac_pgx_explain.mjs` uses `@qvac/sdk` and
  `LLAMA_3_2_1B_INST_Q4_0`.
- `src/qvac_llm.py` provides the Python bridge.
- `POST /analyze` and `POST /analyze/novel-drug` accept
  `"llm_backend": "qvac"`.
- Streamlit exposes `QVAC (Local)` in the backend selector.

Setup:

```bash
cd qvac
npm install
npm run check
```

## Partner Stack

Recommended sponsor/partner stack for Anukriti Lite:

- **Phantom** for wallet-side signing of Solana memo attestations.
- **Helius** for reliable Solana RPC, proof submission, and memo lookup.
- **QVAC** for local explanation text from deterministic PGx outputs.
- **Arcium** as the privacy roadmap for encrypted aggregate cohort analytics.
- **World ID** as a future reviewer/human verification layer.
- **Squads Multisig / Altitude** for production signer, treasury, and authority
  security.

The detailed partner map is in `docs/COLOSSEUM_PARTNER_STRATEGY.md`.

## Judge Demo Script

1. Start the API:

   ```bash
   uvicorn api:app --host 127.0.0.1 --port 8000
   ```

2. Start Streamlit:

   ```bash
   streamlit run app.py
   ```

3. Open `Solana Proofs`.
4. Choose `Clopidogrel / CYP2C19`.
5. Click `Generate Proof`.
6. Show the deterministic export rows, payload hash, Solana memo, valid
   verification result, and tamper rejection.
7. Optional: select `QVAC (Local)` in the main Simulation Lab and run a PGx
   explanation using the local QVAC bridge.

## Evaluation Sound Bite

Anukriti Lite is not asking judges to trust an AI answer or upload patient data
to a chain. It proves a deterministic, off-chain pharmacogenomics artifact with a
minimal Solana memo, then uses QVAC locally to explain the result without making
the clinical decision.

## Safety Boundary

Anukriti Lite is a research prototype, not a clinical decision system. Solana
stores only a schema label and hash. QVAC explains deterministic outputs; it does
not replace CPIC/PharmVar-style PGx logic.
