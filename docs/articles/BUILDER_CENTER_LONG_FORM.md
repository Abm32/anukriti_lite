# AIdeas: Population-aware pharmacogenomics screening — Project Anukriti

**Guideline-first, in silico PGx on diverse genomes — research prototype**

**Category:** Social impact — healthcare equity and transparent AI for pharmacogenomics research.

**Last updated:** March 2026

This document merges the **research narrative** (equity, CPIC/PharmVar, citations) with the **current product** (Amazon Nova on Bedrock, Titan RAG, deterministic engine). Paste sections into **AWS Builder Center** as needed; trim for character limits.

---

## Executive summary

Project Anukriti is a **research and education** prototype for in silico pharmacogenomics. Given a drug (curated name or SMILES) and a genomic profile from **local files, uploads, S3, or streamed 1000 Genomes VCFs**, the system returns structured outputs: risk-style framing, per-gene phenotypes, mechanism-style narrative, confidence, PDF and FHIR-like exports, and per-run audit metadata.

**Decisions are deterministic.** A CPIC- and PharmVar-aligned rule engine performs calling and risk-style classification. **Large language models do not decide risk.** **Amazon Titan Text Embeddings** on **AWS Bedrock** ground retrieval; **Amazon Nova Lite** or **Nova Pro** on Bedrock (default) explain fixed outputs; **Claude** on Bedrock or **Google Gemini** are optional. When Bedrock fails, the API surfaces a **plain-language hint** (credentials, access, throttle) in audit metadata — not a generic “rate limit” only.

**Default stack:** `LLM_BACKEND=nova` in configuration; Streamlit defaults to **Nova (AWS)** with **Lite/Pro** selector.

**Equity thesis:** Many historic PGx and GWAS cohorts skew European; allele frequencies differ across **1000 Genomes** superpopulations (AFR, AMR, EAS, EUR, SAS). Early, computationally cheap screening on **diverse** reference genomes can surface population-relevant risks in **research** workflows — not as a substitute for clinical testing.

---

## Background: why population diversity matters

Modern pharmacogenomic research and genome-wide association studies have long been **skewed toward European ancestry**; reviews report that a large majority of participants in many GWAS cohorts are European, while initiatives such as **All of Us**, **PAGE**, **H3Africa**, and **TOPMed** work to broaden representation. Variant frequencies for genes such as **CYP2D6** and **CYP2C19** differ across groups; ignoring ancestry can worsen **health disparities** and mis-calibrate phenotype prediction. Reviews emphasize that **variation within groups exceeds variation between groups**, yet **allele frequencies differ across superpopulations** — so **representation in reference data** still matters for equitable precision medicine.

**Project Anukriti** does not solve population genetics; it offers a **transparent, guideline-aligned** way to run **CPIC-style** interpretations on **diverse synthetic or reference genomes** for education and research communication.

---

## CPIC, PharmVar, and database dynamism

**CPIC** translates genotypes into **therapeutic recommendations** for implemented gene–drug pairs; it focuses on **how to use** test results, not whether testing should be ordered. **PharmVar** maintains **star-allele** nomenclature. Star alleles are **versioned**: studies show hundreds of alleles added or redefined across PharmVar releases; outdated definitions can change diplotype calls. **Anukriti** uses **snapshotted** in-repo tables and documents that **updates** follow PharmVar/CPIC releases — integration with full **PharmCAT/PyPGx/Aldy**-style pipelines is future work.

---

## Technical foundations

### Tabix and remote VCFs

Variant extraction uses **Tabix**-indexed **bgzip** VCFs. Tabix retrieves **regions** without full-file downloads; **HTTPS** and **S3**-backed URIs support remote access (e.g. 1000 Genomes–style hosting). This lowers the barrier to running PGx on **many** samples.

### Deterministic PGx engine

The **core** contains **no** machine learning for risk decisions: VCF records are parsed, alleles matched to curated rules, diplotypes and phenotypes assigned, and outputs **auditable**. **CYP2D6** copy-number is only **partially** supported (structural tags / CN fields where present).

### Explanation: Titan + Nova (or Claude/Gemini)

After deterministic results and RAG context are fixed, **Nova Lite/Pro** or alternatives **explain** in plain language under **strict prompts**. **Titan** embeds CPIC-oriented text for similarity search (local NumPy cosine or **OpenSearch Serverless** when configured). If **OpenSearch** is unavailable (403 / not configured), **ChEMBL similar-drug** retrieval falls back to a **mock list** — the UI labels this explicitly.

### AWS services (precise roles)

| Component | Role |
|-----------|------|
| **Amazon EC2** | Dockerized FastAPI + Streamlit |
| **Amazon S3** | VCFs, reports; lifecycle / presigned URLs where used |
| **Amazon Bedrock** | Titan embeddings; Nova Lite/Pro; optional Claude |
| **AWS Lambda** | Optional: batch hooks when function name and credentials are set |
| **AWS Step Functions** | Optional: orchestration demo when state machine ARN is set |
| **Amazon CloudWatch** | Logs and metrics |
| **IAM** | Least-privilege roles |

**Interactive cohort simulation** primarily runs **in-process** (`PopulationSimulator` with threading). Lambda/Step Functions are **optional cloud paths** for batch/orchestration — not the sole execution path for every cohort run.

**Cost:** The demo is designed to be **Free Tier–friendly** (small instance, bounded cohorts, cached explanations); production cost depends on Bedrock calls and storage.

---

## Claims we can demonstrate

- Deterministic PGx for supported **CPIC Level A–style** examples (e.g. warfarin–CYP2C9/VKORC1, clopidogrel–CYP2C19) via fixture-style validation.
- **Tabix** regional queries including **remote** VCF access patterns.
- **PDF** and **FHIR-like JSON** exports with **audit** fields (`backend`, `model`, `llm_failure_hint` when applicable).
- **Trial export** MVP: `POST /trial/export` with `called` / `cannot_call` / `insufficient_data` states for supported workflows (`GET /trial/workflows`).

---

## Demo and links

Live demo: https://anukriti.abhimanyurb.com

Video: use the URL from your Builder Center post (e.g. YouTube).

GitHub: https://github.com/Abm32/Synthatrial

API docs (when deployed): configure `API_URL` to your FastAPI host; local default `http://127.0.0.1:8000/docs`.

---

## Limitations (explicit)

- Eight-gene **panel**; not whole-genome PGx.
- **PharmVar/CPIC** snapshots in-repo; not live PharmCAT.
- **No** full PK/PD, drug–drug interactions, or clinical validation.
- **Research prototype only** — not for diagnosis or treatment.

---

## Bibliography and references (from research draft)

Use for Builder Center “references” or footnotes as allowed.

1. Amazon Titan Text Embeddings — AWS / partner summaries on embedding dimensions and multilingual use.
2. Quantifying sample representation in global PGx studies (e.g. PMC systematic reviews).
3. Non-European inclusion in large genetic studies (PMC).
4. Genetic ancestry in PGx (PMC review).
5. CPIC: 10-year retrospective (PMC).
6. PharmVar / CYP2D6 GeneReviews (PMC).
7. Dynamic star-allele definitions (Frontiers Pharmacology 2025).
8. Star-allele nomenclature contradictions (PMC).
9. Tabix manual — htslib.org.
10. 1000 Genomes data access — NIH / genome.gov materials.
11. RDKit documentation — rdkit.org.
12. Step Functions orchestration — AWS documentation.

---

## Tags

#aideas-2025 #social-good #healthcare-life-sciences #amazon-bedrock #amazon-nova #APJC

---

## Disclaimer

Project Anukriti is a **research prototype**. Outputs are not for clinical use.
