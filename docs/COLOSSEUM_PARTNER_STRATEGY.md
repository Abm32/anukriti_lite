# Colosseum Partner Strategy

This is the partner fit map for Anukriti Lite. The goal is to use partners that
make the current product stronger without diluting the submission wedge.

## Product Wedge

Anukriti Lite proves deterministic pharmacogenomics trial exports:

```text
PGx export -> canonical JSON -> SHA-256 hash -> Solana memo -> verification
```

QVAC explains deterministic results locally. Solana proves artifact integrity.
Sensitive cohort rows stay off-chain.

## Best-Fit Partners For This Submission

### 1. Phantom

Fit: high.

Use Phantom Connect as the judge/user wallet path for signing or submitting
Solana memo attestations.

Why it fits:

- The current app already prepares Solana memo payloads.
- Phantom gives a clearer UX than asking every judge to configure a server-side
  Solana CLI wallet.
- Email signin helps non-crypto healthcare or trial users.

Near-term integration:

- Add a lightweight web demo route or React page that connects Phantom.
- Let the connected wallet submit the prepared memo transaction.
- Keep the current Streamlit/CLI route as the fallback.

Submission language:

```text
Phantom is the planned wallet UX for user-submitted Anukriti attestations:
reviewers connect a wallet, inspect the hash-only memo, and sign the proof
transaction without exposing cohort rows.
```

### 2. Helius

Fit: high.

Use Helius RPC for reliable devnet/mainnet transaction submission and proof
lookup.

Why it fits:

- Anukriti needs stable Solana reads/writes, not DeFi routing.
- The product can verify memo transactions by signature or address history.
- Helius gives a clear infrastructure story for productionizing proof lookup.

Near-term integration:

- Add `SOLANA_RPC_URL` to `.env`.
- Use Helius RPC when submitting or verifying memo signatures.
- Add a proof lookup endpoint that fetches transaction details and checks the
  memo content.

Submission language:

```text
Helius is the intended Solana RPC provider for reliable attestation submission
and memo proof lookup.
```

### 3. QVAC

Fit: already integrated.

Use QVAC as the local explanation layer.

Why it fits:

- Healthcare users need understandable explanations.
- QVAC can run locally and keep explanation generation separate from the
  deterministic PGx call.
- It gives the project a second sponsor-aligned track without changing the core
  proof loop.

Current integration:

- `qvac/qvac_pgx_explain.mjs` calls `@qvac/sdk`.
- `src/qvac_llm.py` bridges Python to Node.
- `POST /analyze` accepts `"llm_backend": "qvac"`.
- Streamlit exposes `QVAC (Local)`.

Submission language:

```text
QVAC explains deterministic PGx results locally from de-identified context. It
does not make the clinical call and does not publish data to Solana.
```

### 4. Arcium

Fit: high for future privacy roadmap, medium for current demo.

Use Arcium as the future encrypted computation layer for private cohort
analytics.

Why it fits:

- Anukriti is privacy-native by design.
- Today the chain sees only hashes; tomorrow encrypted computation could support
  aggregate PGx analytics without exposing participant-level rows.

Near-term integration:

- Position as roadmap, not required for the current demo.
- Define a future encrypted aggregate query:
  "count CYP2C19 poor metabolizers in a cohort without revealing sample rows."

Submission language:

```text
Arcium is a natural roadmap extension for encrypted cohort analytics: prove and
compute aggregate PGx properties while keeping individual trial rows private.
```

### 5. World ID

Fit: medium-high for access control and reviewer trust.

Use World ID to prove a reviewer/researcher is human without linking identity
across apps.

Why it fits:

- Clinical-trial workflows care about trusted reviewers and audit access.
- Proof-of-human can gate demo actions, proof requests, or reviewer workflows.
- ZK/unlinkable identity matches Anukriti's privacy stance.

Near-term integration:

- Gate optional proof submission or report download with World ID.
- Do not make World ID part of the core PGx proof loop.

Submission language:

```text
World ID can gate reviewer actions with unlinkable proof-of-human while keeping
the pharmacogenomics data itself off-chain.
```

### 6. Squads Multisig / Altitude

Fit: medium for production operations.

Use Squads Multisig to secure upgrade authorities, signer wallets, or production
attestation services. Use Altitude later for treasury operations.

Why it fits:

- If Anukriti runs a server-side signer, that signer should not be a single
  unchecked private key.
- Multisig is a strong operational story for a healthcare-adjacent product.

Near-term integration:

- Roadmap note: production signer and deployment authorities controlled by
  multisig.
- Not needed for the current judge demo.

Submission language:

```text
For production, Anukriti's attestation signer and program authorities should be
controlled by Squads Multisig rather than a single operator key.
```

### 7. Privy

Fit: medium, mostly as Phantom alternative.

Use Privy if the app needs embedded wallets with email onboarding and managed
Solana UX.

Why it fits:

- Similar user-onboarding value to Phantom Connect.
- Useful if the final product becomes a polished web app for sponsors and trial
  teams.

Recommendation:

- Choose Phantom first for this hackathon because it is explicitly recommended.
- Keep Privy as the fallback if Phantom Connect is not viable in the current UI.

## Lower-Fit Or Future-Only Partners

### Swig

Fit: medium-low for current product, possible future.

Swig's programmable smart wallets are interesting for agentic or policy-based
payments, but Anukriti's current core action is a proof memo. Use later if we add
delegated sponsor agents or policy-controlled attestations.

### MoonPay

Fit: low for current product.

MoonPay Agents are useful when agents need to move money. Anukriti is currently
proving clinical artifacts, not managing commerce.

### Metaplex

Fit: low-medium.

Metaplex agent registration could be interesting if Anukriti becomes an
on-chain clinical review agent. It is not necessary for the current proof demo.

### LI.FI

Fit: low.

Cross-chain liquidity is not part of the PGx attestation wedge.

### Vanish

Fit: low for current product.

Vanish is strong for private trading and swaps. Anukriti's privacy problem is
health data provenance, not trading strategy privacy.

### Reflect

Fit: low.

Stablecoin strategy software is not relevant to the current proof workflow.

### Condor

Fit: low.

Trading agents do not fit the Anukriti Lite submission.

### MoonPay / CASH / LI.FI Payment Flows

Fit: future only.

Could support paid reports or sponsor billing later, but adding payments now
would distract from the core proof story.

## Recommended Submission Stack

Use this stack in the Colosseum submission:

```text
Core:
- Solana memo attestations
- QVAC local explanations
- Helius RPC for reliable proof submission/lookup
- Phantom Connect for wallet signing UX

Roadmap:
- Arcium for encrypted aggregate cohort analytics
- World ID for privacy-preserving reviewer verification
- Squads Multisig for production signer/authority security
```

## What To Build Next

1. Add `SOLANA_RPC_URL` support and use it in Solana submission helpers.
2. Add a proof lookup endpoint that verifies memo content from a transaction
   signature.
3. Build a small Phantom-connected web page for wallet-side memo submission.
4. Keep Streamlit prepared-proof mode as the fallback demo.
5. Add Arcium and World ID to the roadmap section, not the critical path.

## Do Not Overbuild For Submission

Avoid adding DeFi, payments, NFTs, or trading-agent features before submission.
They would make Anukriti feel unfocused. The strongest story is:

```text
Private PGx artifact -> Solana proof -> local QVAC explanation -> reproducible audit
```
