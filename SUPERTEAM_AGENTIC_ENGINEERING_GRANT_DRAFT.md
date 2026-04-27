# Superteam Agentic Engineering Grant Draft

Grant link: https://superteam.fun/earn/grants/agentic-engineering

## What The Colosseum Screenshot Link Means

The form asks for proof of your Colosseum Copilot crowdedness/landscape check. That means: open Copilot, run the project idea search, take a screenshot of the result showing the cluster/similar projects, upload that image somewhere public like Google Drive or Notion, and paste that public URL in the field. I cannot upload to your personal Drive from here, so use the evidence below and attach your own screenshot link.

## Step 1: Basics

**Project Title**
> Anukriti Attestations

**One Line Description**
> A Solana devnet proof layer for Anukriti that turns deterministic PGx trial exports into privacy-preserving, tamper-evident cohort attestations.

**TG username**
> t.me/abhimanyurb

**Wallet Address**
> 4XmeXzdgK95jZWyhX5FMonLzY239nYqr3bmeMejGKX9Q

## Step 2: Details

**Project Details**
> Anukriti, initially built under the SynthaTrial name, is an AI-assisted pharmacogenomics platform for clinical-trial cohort stratification. The system uses deterministic CPIC/PharmVar logic for PGx calls; AI helps with explanation, review, and engineering, but does not make the clinical decision.
>
> This grant funds the Solana attestation layer. The product now prepares a privacy-preserving SHA-256 attestation for `/trial/export` payloads and a Solana devnet memo string that can be anchored in a transaction. Sensitive sample-level genomic rows stay off-chain; the chain stores only a hash/proof reference so sponsors and reviewers can verify that a cohort export was not changed after generation.
>
> The wedge is deliberately narrow: PGx trial export -> deterministic canonical hash -> Solana devnet memo/proof -> later verification. This is stronger than a generic healthcare data app because it focuses on provenance for high-value clinical-trial artifacts.

**Deadline**
> April 24, 2026, Asia/Calcutta

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
> Differentiation: Anukriti Attestations is narrower and more verifiable: deterministic PGx trial-stratification export provenance, not generic medical records, health data NFTs, or broad federated clinical research infrastructure.
>
> Evidence link: https://github.com/Abm32/Synthatrial/blob/solana-anukriti/docs/COLOSSEUM_COPILOT_EVIDENCE.md
>
> Optional screenshot link: [upload Copilot screenshot and paste public link here]

**AI Session Transcript**
> Attach `claude-session.jsonl` and/or `codex-session.jsonl` from the project root.

## Step 3: Milestones

**Goals and Milestones**
> 1. April 18, 2026: Define and document the trial-export attestation schema.
> 2. April 20, 2026: Ship deterministic local attestation generation for `/trial/export`.
> 3. April 22, 2026: Add the Solana devnet memo/proof path and verification tests.
> 4. April 23, 2026: Record an end-to-end demo: PGx export -> attestation -> Solana proof reference -> verification.
> 5. April 24, 2026: Submit final repo, AI transcript, Colosseum link, and demo notes.

**Primary KPI**
> One reproducible end-to-end attestation demo with deterministic hash verification and a Solana devnet memo/proof reference for an Anukriti trial export.

**Final Tranche Checkbox**
> I understand that to receive the final tranche I must submit the Colosseum project link, GitHub repo, and AI subscription receipt.

## Submission Checklist

- Grant draft text above
- `claude-session.jsonl` or `codex-session.jsonl`
- Colosseum Copilot evidence link or screenshot public link
- GitHub repo and `solana-anukriti` branch
- AI subscription receipt

Submit here: https://superteam.fun/earn/grants/agentic-engineering
