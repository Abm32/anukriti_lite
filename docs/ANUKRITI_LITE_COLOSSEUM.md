# Anukriti Lite: Colosseum Build Notes

## Positioning

Anukriti Lite is the Colosseum-facing version of Anukriti: a lightweight Web3
verification layer for deterministic pharmacogenomics simulation outputs and
trial exports, with QVAC as the local explanation layer.

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
deterministic PGx simulation -> private off-chain artifact -> SHA-256 hash
-> optional Solana memo anchor -> reproducible verification
```

## Do We Need A Smart Contract?

Not for the current grant scope. The proof requirement is to make a simulation
artifact tamper-evident without exposing genomic data. A Solana Memo transaction
is enough for that because it immutably timestamps the compact string:

```text
anukriti:<schema_version>:<payload_hash>
```

A custom smart contract becomes useful later if Anukriti needs richer on-chain
state: project registries, reviewer permissions, cohort version indexes,
revocation, paid attestations, or program-owned authority rules. For the grant
demo, Memo is smaller, cheaper, easier to audit, and already compatible with
Phantom/browser-wallet signing.

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
status, and downloadable proof JSON. The normal `Run Simulation` workflow also
has an optional `Anchor proof on Solana devnet after simulation` checkbox. When
enabled, the backend submits the memo after the analysis returns and updates the
attestation with the transaction signature and Explorer URL.

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
deterministic PGx engine or Web3 verification layer.

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
`Anchor proof on Solana devnet after simulation` checkbox in the main Simulation
Lab, the `Anchor this proof to Solana devnet` button on the Solana Proofs page,
or call `POST /attestations/submit` with an attestation.

Setup:

```bash
solana config set --url devnet
solana-keygen new --outfile ~/.config/solana/id.json
solana airdrop 2
solana balance
```

Optional `.env` values:

```bash
SOLANA_RPC_URL=https://devnet.helius-rpc.com/?api-key=your_helius_key
SOLANA_KEYPAIR_PATH=/home/you/.config/solana/id.json
```

You can also use the older one-shot Lite demo submission path:

```json
{
  "workflow": "clopidogrel_cyp2c19",
  "submit_to_devnet": true
}
```

The API will attach the resulting signature and Explorer URL to the attestation.
