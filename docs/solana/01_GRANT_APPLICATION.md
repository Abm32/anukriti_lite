# Superteam Agentic Engineering Grant Draft

Grant link: https://superteam.fun/earn/grants/agentic-engineering

## What The Colosseum Screenshot Link Means

The form asks for proof of your Colosseum Copilot crowdedness/landscape check. That means: open Copilot, run the project idea search, take a screenshot of the result showing the cluster/similar projects, upload that image somewhere public like Google Drive or Notion, and paste that public URL in the field. I cannot upload to your personal Drive from here, so use the evidence below and attach your own screenshot link.

## Step 1: Basics

**Project Title**
> Anukriti Web3 Verification Layer

**One Line Description**
> Anukriti hashes PGx simulation outputs and anchors them on-chain for private, tamper-proof trial validation.

**TG username**
> t.me/abhimanyurb

**Wallet Address**
> 4XmeXzdgK95jZWyhX5FMonLzY239nYqr3bmeMejGKX9Q

## Step 2: Details

**Project Details**
> Anukriti, initially built under the SynthaTrial name, is an AI-assisted pharmacogenomics platform for clinical-trial cohort stratification. The system uses deterministic CPIC/PharmVar logic for PGx calls; AI helps with explanation, review, and engineering, but does not make the clinical decision.
>
> This grant funds a lightweight Web3 verification layer where each simulation output is cryptographically hashed and can be anchored on-chain. The product now prepares privacy-preserving SHA-256 attestations for `/trial/export` payloads and Solana devnet memo strings that can be included in transactions. Sensitive sample-level genomic rows stay off-chain; the chain stores only a hash/proof reference so sponsors and reviewers can verify that a trial design artifact was not changed after generation.
>
> The wedge is deliberately narrow: PGx simulation or trial export -> deterministic canonical hash -> optional Solana devnet memo/proof -> later verification. This creates a tamper-proof, auditable record of trial design decisions without exposing sensitive genomic data.

**Deadline**
> May 31, 2026, Asia/Calcutta

**Proof of Work**
> GitHub repo: https://github.com/Abm32/Synthatrial
>
> Live demo: https://anukriti.abhimanyurb.com
>
> API docs: https://anukritibackend.abhimanyurb.com/docs
>
> Solana branch: `solana-anukriti`
>
> Implemented for this grant: `src/solana_attestation.py`, `/trial/export` attestation output, and tests in `tests/test_solana_attestation.py`.
>
> Existing shipped work: multi-chromosome VCF support, deterministic PGx calls, FHIR output, drug-drug-gene interaction analysis, polygenic risk analysis, CPIC/PharmVar data pipelines, and AWS Bedrock/Nova explanations.
>
> AI session transcripts attached: `claude-session.jsonl` and `codex-session.jsonl`.

**Personal X Profile**
> https://x.com/AbhimanyuRB2

**Personal GitHub Profile**
> https://github.com/Abm32

**Colosseum Crowdedness Score**
> Colosseum Copilot evidence: nearest cluster is `v1-c7`, "Solana-Based Healthcare Solutions", with 78 projects and 1 winner. Closest match: Dezi Network, a privacy-preserving decentralized clinical research framework using ZKPs and federated learning on Solana.
>
> Differentiation: Anukriti's Web3 verification layer is narrower and more verifiable: deterministic PGx simulation and trial-stratification provenance, not generic medical records, health data NFTs, or broad federated clinical research infrastructure.
>
> Evidence link: https://github.com/Abm32/Synthatrial/blob/solana-anukriti/docs/COLOSSEUM_COPILOT_EVIDENCE.md
>
> Optional screenshot link: [upload Copilot screenshot and paste public link here]

**AI Session Transcript**
> Attach `claude-session.jsonl` and/or `codex-session.jsonl` from the project root.

## Step 3: Milestones

**Goals and Milestones**
> 1. May 7, 2026: Finalize the simulation-output attestation schema and grant demo flow.
> 2. May 14, 2026: Integrate proof generation into the main Anukriti simulation workflow.
> 3. May 21, 2026: Complete optional Solana devnet anchoring, lookup verification, and tamper-failure tests.
> 4. May 28, 2026: Polish Streamlit judge demo, setup docs, and submission copy.
> 5. May 31, 2026: Submit final repo, AI transcript Drive link, Colosseum link, and demo notes.

**Primary KPI**
> One reproducible end-to-end proof demo with deterministic hash verification and an optional Solana devnet memo/proof reference for an Anukriti simulation or trial export.

**Final Tranche Checkbox**
> I understand that to receive the final tranche I must submit the Colosseum project link, GitHub repo, and AI subscription receipt.

## Submission Checklist

- Grant draft text above
- `claude-session.jsonl` or `codex-session.jsonl`
- Colosseum Copilot evidence link or screenshot public link
- GitHub repo and `solana-anukriti` branch
- AI subscription receipt

Submit here: https://superteam.fun/earn/grants/agentic-engineering
