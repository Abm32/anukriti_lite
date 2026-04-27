# Project Anukriti (SynthaTrial) — Updated Overview

## App Category

**Social Impact** — Making pharmacogenomic safety insight easier to explore before expensive lab or trial work, with an equity lens on diverse genomes.

---

## Executive Summary

**Project Anukriti** (repository: **SynthaTrial**, v0.5 MVP) is a research prototype for *in silico* pharmacogenomics. Given a drug from a curated library or a SMILES string, plus a genomic profile from **manual phenotypes**, **local VCFs**, **uploads**, **your S3 bucket**, or **streamed 1000 Genomes / AWS Open Data** VCFs, the system produces structured outputs: risk-style framing, per-gene phenotypes, mechanism-style narrative, confidence-style fields where implemented, **PDF** and **FHIR R4 Genomics Reporting–style** exports, **drug–drug–gene interaction (DDGI)** hints, optional **polygenic risk** demos, and **per-run audit metadata** (model ID, vector backend, timing). Outputs are for **research and education**, not clinical care.

**Core genotyping and calling are deterministic** for the supported panel: CPIC- and PharmVar-aligned tables and callers in-repo, Tabix-based regional extraction, and drug-triggered gene focus. **Large language models narrate and contextualize**; for several high-value drug–gene pairs the API also attaches **structured, rule-based PGx** (e.g. TPMT–thiopurines, DPYD–fluoropyrimidines, SLCO1B1–statins) when the request path uses the Bedrock/Nova explanation stack. Other backends (e.g. direct Gemini/Claude simulation) follow a **heavily constrained CPIC-style prompt**; the UI/API still log **backend, vector source, and parsed risk** where available.

**Default explanation stack on AWS** is **Amazon Nova Lite or Nova Pro on Bedrock**, with **Amazon Titan Text Embeddings v2** for RAG over versioned guideline-oriented text. **Claude on Bedrock** remains supported where your account has access. **Optional Google Gemini** and **local Ollama** (via multi-backend fallback) help demos when Bedrock or cloud keys are constrained.

**Similar-drug (chemical) context** uses molecular fingerprints against **Pinecone** (default), **local ChEMBL-backed cosine search** (`VECTOR_DB_BACKEND=local`, no cloud cost), **AWS OpenSearch** (optional), or a **mock** list if the configured backend is unavailable — so cheminformatics retrieval is **pluggable**, not hard-wired to one vendor.

The product thesis remains **equity through representation**: screening against genetically diverse reference cohorts helps surface population-relevant pharmacogenomic patterns earlier in research and training workflows.

---

## The Problem

Drug development wastes enormous time and money on late failures; many adverse outcomes have a pharmacogenomic component. A practical gap is underrepresentation of non-European ancestry in early genomic resources, so population-specific pharmacogenomic risks are under-explored until late stages.

This project does **not** replace animal studies, predict full clinical trial outcomes, or replace licensed pharmacogenomic testing. It makes guideline-aligned, auditable pharmacogenomic-style screening easier to run at scale on diverse genomes for research, education, and safety communication.

Two examples that make this concrete:

- When **codeine** is prescribed to a **CYP2D6 ultrarapid metabolizer**, conversion to morphine can be so rapid that standard doses risk fatal respiratory depression.
- When **warfarin** is given to a **CYP2C9 poor metabolizer**, accumulation can dramatically increase bleeding risk.

These variants are common across South Asian, East Asian, and African populations — groups historically underrepresented in many clinical genomic datasets. The harm is real, preventable, and disproportionately affects underserved communities.

---

## Vision

Project Anukriti simulates drug–genome interaction for a **defined pharmacogene panel** using computational rules and transparent evidence retrieval, so teams can explore what-if safety questions before wet lab or trial investment — with explicit limits stated in the product.

**In scope**

- CPIC-style interpretation for **16 gene targets** (15 Tier-1 pharmacogenes plus **HLA-B\*57:01** via proxy) with expanded triggers for **CYP3A4/3A5, CYP1A2, CYP2B6, NAT2, GSTM1, GSTT1** where drug mappings exist.
- VCF-driven variant extraction and allele/phenotype calling for that panel; **CYP2D6** copy-number cues from structural/CN-style fields where present.
- **Drug-triggered PGx** in the UI (only relevant genes highlighted for the chosen drug).
- Explainable narratives grounded in retrieved guidelines (Titan + local index; path to OpenSearch / other vector stores).
- Cohort / batch views, async jobs with polling for heavy VCF paths, **trial export** contract for stratification workflows.

**Out of scope**

- General PK/PD or toxicology prediction; predicting overall trial success; autonomous medical decisions; diagnostic or prescribing advice.

---

## What the Product Does

Given a drug and a genomic source, the stack can:

- **Extract** variants in pharmacogene regions using **Tabix** on per-chromosome VCFs: local `data/genomes`, **S3** URLs, **upload** with server-side indexing, or **HTTPS range access** to 1000 Genomes / Open Data (default streaming mode avoids full downloads where configured).
- **Call** diplotypes/phenotypes with **deterministic** CPIC/PharmVar-oriented logic and in-repo JSON/TSV/DB assets (`data/pgx/…`, optional SQLite pharmacogene DB).
- **Highlight** only genes relevant to the chosen drug via **`DRUG_GENE_TRIGGERS`** (e.g. warfarin → CYP2C9 + VKORC1; statins → SLCO1B1 ± CYP3A4; abacavir → HLA proxy; tacrolimus → CYP3A5/3A4; isoniazid → NAT2; cyclophosphamide → CYP2B6 + GST; etc.).
- **Retrieve** similar approved drugs via **fingerprint + vector search** (Pinecone / local ChEMBL / OpenSearch / mock).
- **Explain** via **Nova / Claude / Gemini**, with **`GET /health/llm-status`** and UI hints; optional **Ollama** for fully local text generation in constrained environments.
- **Export** PDF reports, **`POST /analyze/fhir-report`** (FHIR Genomics Reporting–oriented bundle), **`POST /analyze/ddgi`** (drug–drug–gene structured output), **`POST /analyze/polygenic-risk`** (simplified CAD/T2D PRS demo using 1000G-style streaming), CSV cohort summaries, and **`POST /trial/export`** for MVP trial stratification rows (`GET /trial/workflows`).

The **Streamlit** UI includes the **Simulation Lab**, **batch/cohort** mode, dataset discovery, **VCF profile jobs** with polling, **3D structure** view (RDKit), and status banners (e.g. streaming latency, LLM backend).

---

## How It Was Built

### Architecture (current)

**Typical path:** User → **Streamlit** → **FastAPI** (`api.py`) → **fingerprint** → **vector search** (Pinecone / local / OpenSearch / mock) → **PGx pipeline** (VCF → tabix → callers) → **LLM explanation** (Bedrock Nova default, or Gemini / Claude / Ollama per configuration) → **structured response + audit + optional PDF/FHIR**.

**Separation of concerns:** Variant calling and table lookups are **code-defined and reproducible**. LLMs **produce human-readable explanations** and, depending on backend, **RAG-grounded** text; structured deterministic blocks are **merged where implemented** (notably for specific drugs on the Bedrock/Nova PGx explanation path). Treat narrative **risk labels** as **research communication** unless paired with explicit structured caller output for that drug.

**Demo video:** https://www.youtube.com/watch?v=zu-1reih7wA

### Three layers

| Layer | Role |
|--------|------|
| **Data plane** | Tabix/htslib-style regional queries; remote VCF without full-file download; `vcf-datasets` / `vcf-samples`; uploads; async **`/jobs/vcf-profile`**; TTL caches. |
| **Decision engine** | Deterministic rules and curated tables; RDKit SMILES/fingerprints; reproducible logs (e.g. variants found per gene region). |
| **Explanation & product** | Titan embeddings + local (or remote) retrieval; Nova/Claude/Gemini/Ollama; Streamlit UX; exports and audit JSON. |

### AWS (Bedrock-native default)

- **Amazon Bedrock** — Titan embeddings; Nova Lite/Pro; Claude where enabled.
- **Amazon EC2** — typical deployment for FastAPI + Streamlit (e.g. Docker Compose).
- **Amazon S3** — optional genomic objects and report storage with lifecycle/presigned patterns where configured.
- **Lambda / Step Functions** — optional hooks for large batch orchestration; **interactive** cohort paths often run **in-process** — see README for accurate positioning.
- **CloudWatch / IAM** — logging and least-privilege access patterns.

The prototype is designed to remain **affordable** on small instances and bounded Bedrock usage for demos.

### Pharmacogene panel (16 targets, multi-chromosome)

Fifteen Tier-1 genes plus **HLA-B\*57:01** (HCP5 proxy): **CYP2D6, CYP2C19, CYP2C9, UGT1A1, SLCO1B1, VKORC1, TPMT, DPYD**, **CYP3A4, CYP3A5, CYP1A2, CYP2B6, NAT2, GSTM1, GSTT1**, **HLA_B5701**. Coverage spans **multiple chromosomes** (not a single “8-gene, 7-chr” snapshot — the codebase aligns with **8+ chromosomes** for panel regions).

### Deterministic PGx engine

- Allele/phenotype tables: CPIC-oriented JSON, PharmVar TSVs, optional **`pharmacogenes.db`** for unified lookup experiments (**`variant_db_v2`**).
- **Warfarin**, **SLCO1B1**, **TPMT**, **DPYD**, **CYP3A4/3A5**, **CYP1A2**, **CYP2B6**, **NAT2**, **GST** combined caller, **HLA-B\*57:01** proxy, **CYP2D6** with CNV-aware paths where data supports it.

### Technology stack (updated)

| Layer | Technology |
|--------|------------|
| Frontend | Streamlit |
| Backend | FastAPI, Uvicorn, optional Docker |
| Genomics | Tabix/VCF; 1000 Genomes; AWS Open Data HTTPS/S3 |
| Cheminformatics | RDKit; ChEMBL; **Pinecone / local NumPy / OpenSearch** for similarity |
| Guidelines / PGx data | Versioned in-repo CPIC/PharmVar-aligned assets |
| AI | Titan v2; Nova; Claude; Gemini; **Ollama** (local fallback) |
| Cloud | EC2, S3, Lambda/SFN optional, CloudWatch, IAM |
| Exports | PDF; FHIR-style JSON; CSV; trial export API |

---

## Demo

- **Live demo:** anukriti.abhimanyurb.com
- **API docs:** anukritibackend.abhimanyurb.com/docs
- **GitHub:** github.com/Abm32/Synthatrial
- **Video:** https://www.youtube.com/watch?v=zu-1reih7wA

**Simulation Lab** — Standard library or custom SMILES; manual or VCF profile; VCF sources include Auto, Local, S3, S3 Open Data, Remote 1000G, Upload; background profile jobs; similar-drug panel shows **live vector backend** (Pinecone vs local vs mock) via `/data-status`.

**Batch / cohort** — Population-style analytics and exports (throughput depends on environment).

**New API surfaces (high level)** — `/analyze/fhir-report`, `/analyze/ddgi`, `/analyze/polygenic-risk`, `/vcf-datasets/streaming-status`, `/health/llm-status`, `/validation/concordance-summary`, `/regulatory/classification`, `/trial/workflows` + `/trial/export`.

---

## Validation

Interpretations are checked against **CPIC Level A–style** examples and expanded validation fixtures where present; technical concordance work references **GIAB/Coriell** style samples in documentation — **not** a regulatory validation package. See `docs/regulatory/CLINICAL_VALIDATION_ROADMAP.md` and `docs/validation/` for the staged pathway.

---

## What We Learned (still true, slightly refined)

- **Separate calling from narration** remains the right pattern for trustworthy health-adjacent AI; the codebase continues to move **deterministic tables and Tabix** ahead of free-form text.
- **Targeted panels** beat whole-genome sprawl for debuggability and guideline alignment.
- **Nova on Bedrock** keeps demos **AWS-native** when other models are gated.
- **Streaming VCFs** keep diverse-cohort demos **storage-cheap**.
- **Pluggable vector search** (Pinecone vs local ChEMBL) balances **cost** and **fidelity** for similar-drug context.
- **Async jobs + caching** keep the UI responsive on real VCF work.
- **Genomic diversity** is an equity issue; tooling should make non-European representation **default-class**, not an afterthought.

---

## Current Status and Known Limitations

**Strengths (beta / research prototype)**

- **16-gene** triggered panel with expanded drug map; deterministic callers and VCF pipeline; multiple LLM backends + Ollama; Pinecone/local/OpenSearch vector options; FHIR/DDGI/PRS endpoints; trial export MVP; audit fields; streaming 1000G path.

**Limitations**

- Incomplete phasing and **full** CYP2D6 structural resolution in all samples.
- Not whole-genome PGx; not a certified **CDS** device; **not for real patients**.
- Live demos may hit **Bedrock quotas**, **Pinecone/OpenSearch** misconfiguration, or **missing ChEMBL DB** for local vectors — fallbacks exist but change behavior (e.g. mock neighbors).
- Some narrative risk lines may not parse to Low/Medium/High until the model matches template; **parsing heuristics** are improved over time.

**Future work**

- Richer CYP2D6 activity models; **G6PD**, more HLA; deeper EHR/trial integration; managed vector stores; broader clinical validation.

---

*Project Anukriti / SynthaTrial is a research prototype. Outputs are for research and education and must not be used for clinical decision-making, diagnosis, or treatment. Not medical advice.*
