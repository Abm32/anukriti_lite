# Anukriti Solana Attestations

Anukriti integrates a lightweight Web3 verification layer where each simulation output is cryptographically hashed and can be anchored on-chain. The sensitive pharmacogenomics data stays off-chain; Solana stores only a deterministic proof reference.

## Flow

1. Generate a deterministic trial export through `POST /trial/export`.
2. Canonicalize the export payload with sorted JSON keys, excluding any existing `attestation` field.
3. Hash the canonical payload with SHA-256.
4. Build a Solana devnet memo:

   ```text
   anukriti:anukriti.trial_export_attestation.v1:<payload_hash>
   ```

5. Submit that memo in a devnet transaction and store the resulting signature beside the export artifact.
6. Recompute the export hash later to verify the artifact was not changed.

## Privacy Model

The full trial export stays off-chain. The Solana memo contains only a hash and schema label, not sample IDs, variants, phenotypes, recommendations, or cohort rows.

## API Output

`POST /trial/export` now returns an `attestation` block:

```json
{
  "schema_version": "anukriti.trial_export_attestation.v1",
  "network": "devnet",
  "hash_algorithm": "sha256",
  "payload_hash": "...",
  "solana": {
    "cluster": "devnet",
    "memo_program_id": "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
    "memo": "anukriti:anukriti.trial_export_attestation.v1:...",
    "devnet_proof_status": "prepared_not_submitted"
  }
}
```

## Verification

Use `src.solana_attestation.verify_trial_export_attestation(payload, attestation)` to verify that a local export still matches its proof artifact.
