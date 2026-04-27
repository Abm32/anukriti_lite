# AIdeas: Predicting Drug Risks Before Clinical Trials - Project Anukriti

**An AI-powered in silico pharmacogenomics platform that simulates personalized drug responses across genetically diverse synthetic patient cohorts - enabling scalable pre-clinical safety screening without animal testing.**

**Author:** Abhimanyu
**Published:** Feb 23, 2026
**Updated:** March 2026
**Category:** Social Impact - Healthcare Equity

**Long-form article (equity research, CPIC/PharmVar citations, precise AWS roles):** see [BUILDER_CENTER_LONG_FORM.md](BUILDER_CENTER_LONG_FORM.md) in this repo.

---

## My Vision

Every year, billions of dollars are spent on drug development, yet ~90% of drug candidates fail during clinical trials - many due to adverse drug reactions (ADRs) that were never caught in pre-clinical testing.

**A major reason: a genetic blind spot.**

Most early-stage genomic datasets are heavily skewed toward populations of European ancestry. When drugs reach globally diverse populations, unexpected - sometimes fatal - reactions emerge.

**Project Anukriti** is an AI-powered in silico pharmacogenomics platform designed to simulate how a patient's genetic profile interacts with a drug - entirely computationally.

Given a drug (by name or molecular SMILES string) and a patient's genomic profile, Project Anukriti:

- **Extracts clinically relevant genetic variants** from key pharmacogenes (CYP2D6, CYP2C19, CYP2C9, UGT1A1, SLCO1B1, VKORC1) across chromosomes 2, 6, 10, 11, 12, 16, 19, and 22
- **Maps variants to star alleles and metabolizer phenotypes** using CPIC-grade rules with deterministic PharmVar-aligned allele calling
- **Retrieves supporting pharmacogenomic evidence** via a Bedrock-powered RAG layer (**Amazon Titan** embeddings) with local CPIC guideline retrieval
- **Uses Amazon Nova Lite or Nova Pro (via AWS Bedrock)** by default for structured, explainable clinical interpretations — not decisions; **Claude** on Bedrock or **Google Gemini** optional
- **Outputs a clinical-style report**: Risk Level · Mechanism · Recommendation · Confidence Score
- **Supports PDF export** for real-world usability with downloadable clinical reports
- **Drug-triggered PGx**: Shows only drug-relevant genes (Warfarin → CYP2C9 + VKORC1; Statins → SLCO1B1; Clopidogrel → CYP2C19)
- **S3 VCF support**: VCF files can be loaded from local paths or `s3://` URLs — the pipeline automatically downloads S3 files to temp storage when needed for Tabix querying

**Important:** The LLM does not make risk decisions — it explains the outputs of a deterministic pharmacogenomic engine. This separation is intentional and critical for reliability in a healthcare context.

---

## Why This Matters

### The Human Cost of the Genetic Blind Spot

When **Codeine** is prescribed to a patient who is a CYP2D6 Ultra-Rapid Metabolizer, their body converts it to Morphine so rapidly that a standard dose can cause fatal respiratory depression. When **Warfarin** is given to a CYP2C9 Poor Metabolizer, the drug accumulates in the bloodstream, dramatically increasing the risk of life-threatening bleeding.

These are not rare edge cases. These gene variants are common across South Asian, East Asian, and African populations - populations historically underrepresented in clinical genomic datasets. The harm is real, preventable, and disproportionately falls on communities that are already medically underserved.

### The Cost of the Status Quo

- Traditional animal model testing costs **$10,000+ per drug candidate** and takes months
- Molecular dynamics simulations require HPC clusters and weeks of compute time
- Neither approach screens for human population-level genetic diversity

**Project Anukriti completes a full drug-patient pharmacogenomic simulation in approximately 5 seconds**, on cloud infrastructure, at a fraction of the cost. More importantly, it can do this for thousands of synthetic patient profiles representing diverse ancestries - something no animal model can do.

### Democratizing Pre-Clinical Safety

By making population-diverse drug safety simulation accessible, Project Anukriti creates a tool that can:

- Help pharmaceutical researchers catch population-specific risks before Phase I trials
- Reduce the rate of late-stage trial failures driven by genetic factors
- Eventually inform more equitable and personalized prescribing guidelines globally

---

## How I Built This

### Architecture Overview

Project Anukriti is built on a modular, lightweight pipeline that avoids the need for supercomputing resources — and separates clinical decision logic from AI explanation.

**Pipeline:** User → Streamlit UI → FastAPI (Docker on EC2) → Deterministic PGx Engine → Titan RAG → **Nova** (or Claude/Gemini) explanation → Structured Output + PDF

### Key Components

#### 1. Cheminformatics Layer (RDKit)

Drug inputs are accepted either by name (from a curated library of 7 drugs: Warfarin, Clopidogrel, Codeine, Ibuprofen, Metoprolol, Simvastatin, Irinotecan) or as a raw SMILES string. RDKit processes the SMILES into **Morgan fingerprints** (radius 2, 2048-bit) - dense molecular vector representations that enable structural similarity search. An in-memory cache avoids recomputation for repeated queries.

#### 2. Targeted Pharmacogene Panel

Rather than expensive whole-genome analysis, Anukriti implements a **targeted panel** focused on the pharmacogenes with the highest clinical impact across **8 chromosomes** (2, 6, 10, 11, 12, 16, 19, 22):

- **Chr22**: CYP2D6 (~25% of drugs)
- **Chr10**: CYP2C19, CYP2C9 (antiplatelet, anticoagulation, NSAIDs)
- **Chr2**: UGT1A1 (irinotecan)
- **Chr12**: SLCO1B1 (statin myopathy)
- **Chr16**: VKORC1 (warfarin sensitivity)

**Tabix-based VCF querying** makes variant extraction ~1000× faster than naive genome scans. Genotype-to-phenotype translation uses a **Targeted Variant Lookup** against Tier 1 clinical variants (e.g., CYP2D6*4, CYP2C9*3) - aligned with CPIC guidelines.

#### 3. Deterministic PGx Engine (Core Decision Layer)

This is the clinical brain of the system - and it **contains no LLM**. Risk decisions are made by hard-coded CPIC-aligned rules:

- **CYP2C19**: PharmVar allele table (TSV) + CPIC phenotype table (JSON) → deterministic diplotype calling (*1/*2 → Intermediate Metabolizer)
- **Warfarin**: CYP2C9 + VKORC1 variants → `warfarin_response.json` → dosing recommendation
- **SLCO1B1**: rs4149056 genotype → statin myopathy risk (CC = Poor Function)
- **Drug-triggered PGx**: Only shows genes relevant to the selected drug (Warfarin → CYP2C9 + VKORC1; Statins → SLCO1B1)

Outputs are **deterministic, auditable, and reproducible** - treated as ground truth before the LLM ever sees them.

#### 4. RAG Retrieval Layer (Amazon Titan + local / OpenSearch)

CPIC guidelines and pharmacogenomic reference data are embedded using **Amazon Titan Text Embeddings** (Bedrock). Similarity search uses **in-memory cosine** over local vectors or **Amazon OpenSearch Serverless** when `OPENSEARCH_HOST` is configured and authorized. **ChEMBL** provides structural drug context for similar-drug retrieval; if OpenSearch is unavailable, the app uses a **labeled mock similar-drug list** for demos.

**Local CPIC retrieval**: Curated PGx data in `data/pgx/` (PharmVar TSV + CPIC JSON) is versioned in the repo for reproducibility — no live CPIC API at runtime.

#### 5. LLM backends (Amazon Nova default; Claude / Gemini optional)

- **Amazon Nova Lite / Nova Pro** (Bedrock): default in app and API for AWS-native, cost-efficient explanations when model access is enabled.
- **Claude 3** (Bedrock): optional; same prompt contract.
- **Google Gemini**: optional via direct API for non-Bedrock environments.

The LLM receives deterministic PGx results and retrieved text. Its role is strictly constrained: **explain only** — not to override the engine. Audit metadata records model ID and **failure hints** when Bedrock returns errors.

#### 6. Structured Output + PDF Report

Final output includes:

- **Risk Level** (LOW / MEDIUM / HIGH)
- **Genotype and Phenotype** (e.g., CYP2C19 *1/*2 → Intermediate Metabolizer)
- **Mechanism and Clinical Reasoning** (LLM-generated explanation)
- **Dosing Implication** (CPIC-aligned recommendation)
- **Confidence Score** (based on CPIC evidence strength)
- **Downloadable PDF report** for real-world usability

#### 7. AWS Cloud-Native Architecture

- **S3**: Genomic objects and reports where deployed; Intelligent Tiering / lifecycle as configured. VCF pipeline supports **local paths** and **`s3://`** (download to temp for Tabix).
- **Amazon Bedrock**: **Titan** embeddings; **Nova Lite/Pro** (default) or **Claude** for explanations.
- **Lambda**: Optional — API can invoke a batch function when `AWS_LAMBDA_FUNCTION_NAME` and credentials are set; **interactive cohort** simulation runs **in-process** (`PopulationSimulator`).
- **Step Functions**: Optional — demo orchestration when `AWS_STEP_FUNCTIONS_STATE_MACHINE` is set.
- **IAM / CloudWatch**: Least-privilege patterns and observability for deployments.

**Cost:** Demo targets **AWS Free Tier–friendly** usage (small EC2, bounded Bedrock calls); production cost varies.

**Sidebar status:** Streamlit shows S3/Lambda/Step Functions **connectivity** when checks succeed; core PGx still runs without them.

#### 8. Deployment & Infrastructure

- **Backend**: FastAPI + Docker
- **Frontend**: Streamlit with minimalistic UI, 3D molecular visualization (py3Dmol + stmol), Lottie animations
- **Infrastructure**: AWS EC2 (Free Tier t2.micro or t3.micro for ₹400-₹750/month)
- **Design**: Bedrock-native, cost-efficient, scalable
- **Multi-platform support**: Render.com, Vercel, Heroku, AWS EC2 with intelligent platform selection

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| **Cheminformatics** | RDKit |
| **VCF Processing** | Tabix (via pysam) |
| **Embeddings** | Amazon Titan (Bedrock); vector store optional (OpenSearch / in-memory) |
| **Drug Database** | ChEMBL (when vector search available; else mock similar-drug labels in UI) |
| **LLM** | Amazon Nova Lite/Pro (Bedrock, default); Claude (Bedrock); Google Gemini (optional) |
| **Genomic Data** | 1000 Genomes Project (VCF) |
| **Guidelines** | CPIC, PharmVar |
| **Backend** | FastAPI + Docker |
| **Frontend** | Streamlit (minimalistic UI with 3D visualization) |
| **Infrastructure** | AWS EC2 / Render.com / Vercel / Heroku |
| **AWS Services** | S3, Bedrock (Titan + Nova/Claude), optional Lambda/Step Functions, CloudWatch |

---

## Key Milestones

✅ Built and validated the targeted pharmacogene variant lookup system across 8 chromosomes
✅ Implemented Tabix-based VCF querying for ~1000× faster genomic processing
✅ Designed CPIC-grade deterministic PGx engine as the core risk decision layer
✅ Integrated Claude 3 via AWS Bedrock + Google Gemini as strictly constrained explanation layers
✅ Validated outputs against CPIC Level A guidelines on 60+ synthetic patients (Warfarin–CYP2C9, Codeine–CYP2D6, Clopidogrel–CYP2C19)
✅ Built Simulation Lab, Batch Mode, Analytics, and About tabs with PDF export
✅ Implemented drug-triggered PGx (shows only drug-relevant genes)
✅ Added dual LLM backend support with per-request override
✅ Deployed production-ready FastAPI backend with interactive API documentation
✅ Created minimalistic Streamlit UI with 3D molecular visualization and Lottie animations
✅ Achieved 5-second simulation time on cloud infrastructure
✅ Implemented multi-platform deployment automation (AWS EC2, Render, Vercel, Heroku)
✅ **Full AWS Infrastructure Integration** - S3 genomic data storage, Lambda batch processing, Step Functions trial orchestration
✅ **Production AWS Deployment** - Live AWS account (403732031470) with complete infrastructure:
  - **S3 Buckets**: synthatrial-genomic-data (16 VCF files across 8 chromosomes), synthatrial-reports (PDF storage)
  - **Lambda Function**: synthatrial-batch-processor (batch population simulation)
  - **Step Functions**: synthatrial-trial-orchestrator (clinical trial workflow orchestration)
  - **IAM Roles**: synthatrial-lambda-role, synthatrial-stepfunctions-role (secure service integration)
✅ **Population-Scale Simulation** - AWS Lambda-powered batch processing supporting up to 10,000 patients with cost-effective parallel processing ($0.0001 per patient)
✅ **Cloud-Native Architecture** - Complete AWS service integration with S3 genomic data storage, automated PDF report generation, and scalable trial orchestration
✅ **S3 VCF Path Support** - VCF pipeline accepts both local paths and `s3://` URLs; S3 files are automatically downloaded when needed for Tabix querying
✅ **Batch Mode Cohort Simulation** - Configurable cohort-based population simulation (50–2,000 patients, drug selection: Warfarin, Clopidogrel, Codeine) with POST `/population-simulate` API for custom parameters; displays population diversity, risk distribution, and AWS Lambda/Step Functions usage
✅ **Real-Time AWS Status in Sidebar** - Live indicators for S3 genomic connectivity, Lambda availability, and Step Functions availability with graceful fallback when services are unavailable

---

## Demo

🔗 **Live Demo**: [anukriti.abhimanyurb.com](https://anukriti.abhimanyurb.com)
🔗 **API Documentation**: [anukritibackend.abhimanyurb.com/docs](https://anukritibackend.abhimanyurb.com/docs)

**Note:** The live demo uses AWS Bedrock with rate limits. If the simulation is unresponsive, please refer to the demo screenshots and video.

### Interface Highlights

#### Simulation Lab - Configure Trial Parameters
Users select a drug from the standard library (7 curated drugs) or enter a custom SMILES string, then configure the patient's genetic profile by setting metabolizer phenotypes for each relevant enzyme. **Drug-triggered PGx** automatically highlights only the genes relevant to the selected drug with orange "Relevant" tags.

#### Batch Mode - Cohort-Based Population Simulation
The **Batch Mode** tab offers high-throughput cohort simulation: users configure cohort size (50–2,000 patients), select a drug (Warfarin, Clopidogrel, Codeine), and run a population simulation. Results show cohort overview, population diversity (AFR, EUR, EAS, SAS, AMR), risk distribution chart, performance metrics (throughput, total time), and whether AWS Lambda or Step Functions were used. The backend supports both GET (default demo) and POST (custom parameters) for `/population-simulate`.

#### Simulation Results - Patient Genetics Tab
After running the simulation, the system displays the full synthetic patient profile used in the prediction, including all pharmacogene statuses and any co-morbidities. **Deterministic PGx results** (Warfarin, SLCO1B1) are shown separately with CPIC-aligned recommendations.

#### Simulation Results - Similar Drugs Retrieved Tab
The RAG context is made transparent: users can see exactly which structurally similar drugs (e.g., Acenocoumarol, Dicumarol, Benziodarone for Warfarin) were retrieved and used as evidence.

#### Simulation Results - Predicted Response + Risk Tab
The final output displays:
- **Risk Level** (prominent badge: LOW/MEDIUM/HIGH)
- **Predicted Reaction** (clinical interpretation)
- **Biological Mechanism** (pharmacogenomic explanation)
- **Dosing Implication** (CPIC-aligned recommendation)
- **Confidence Score** (evidence strength)
- **Processing Time** (typically ~5 seconds)
- **Downloadable PDF report** for clinical documentation

---

## What I Learned

### Technical Insights

**1. Separate decisions from explanations**

Early iterations asked the LLM to make the risk determination. Outputs sounded authoritative but were clinically unreliable. The breakthrough was architectural: **hard-coded CPIC rules make the decision, Claude/Gemini explains it**. The moment the LLM stopped guessing and started explaining, reliability transformed.

**2. Targeted beats comprehensive**

My initial instinct was to analyze the entire genome. In practice, focusing on a **curated panel of Tier 1 clinical variants** across key pharmacogenes produced far more clinically meaningful — and computationally feasible — results. Biological precision beats brute-force coverage.

**3. Cheminformatics is underrated in AI pipelines**

RDKit's Morgan fingerprints provided a surprisingly effective bridge between chemical structure and semantic similarity, enabling the RAG system to retrieve genuinely analogous drugs rather than superficially related ones.

**4. Lightweight RAG can outperform heavy infrastructure**

NumPy cosine similarity over Titan embeddings was faster and more cost-efficient than a managed vector database for this use case — and more than sufficient for the retrieval quality needed. **Local CPIC retrieval** from versioned repo data eliminates runtime API dependencies.

**5. Drug-triggered PGx improves clinical relevance**

Showing only drug-relevant genes (Warfarin → CYP2C9 + VKORC1; Statins → SLCO1B1) matches real-world clinical alerting systems and reduces cognitive load for users.

**6. S3-native VCF handling enables hybrid deployment**

Supporting both local and `s3://` VCF paths in the same pipeline allows the same codebase to run in local development (local files), single-instance EC2 (local disk), or multi-instance deployments (S3). The pipeline transparently downloads S3 files when needed, keeping the analysis logic unchanged.

**7. Dual LLM backend provides flexibility**

Supporting both Gemini (Google) and Bedrock (AWS) with per-request override allows users to choose based on cost, latency, and regional availability - critical for global deployment.

### Broader Lessons

**1. The presentation of AI outputs matters as much as the outputs themselves**

A correct prediction buried in a wall of text is not useful. Designing the UI to surface **Risk Level, Mechanism, and Clinical Implication** as distinct, scannable sections — with PDF export — made the system dramatically more interpretable and practically usable.

**2. Responsible AI framing is non-negotiable in healthcare**

From the very first build, Project Anukriti has carried a clear disclaimer: **"Research prototype — outputs are synthetic predictions and must not be used for clinical decision-making."** This is not just a legal consideration; it shapes every design decision.

**3. Genomic diversity in AI is an equity issue**

This project started as a technical challenge and became something more personal. The genetic blind spot in drug development has real human consequences, disproportionately affecting populations in South Asia, Africa, and East Asia. Building tools that account for this diversity — even at the prototype stage — feels like meaningful work.

**4. Minimalistic UI design enhances usability**

The shift to a clean, minimalistic interface with 3D molecular visualization, Lottie animations, and drug-triggered PGx highlighting made the platform more accessible to non-technical users while maintaining scientific rigor.

**5. Production-ready infrastructure matters**

Moving from prototype to production-ready deployment with Docker, FastAPI, multi-platform support, and automated deployment pipelines transformed the platform from a research tool into a scalable solution ready for real-world applications.

---

## Current Status & Future Work

### Production-Ready Features (v0.4 Beta)

✅ **Deterministic CPIC/PharmVar-aligned calling** for CYP2C19 and Warfarin (CYP2C9 + VKORC1)
✅ **Drug-triggered PGx** (shows only drug-relevant genes)
✅ **Dual LLM backend** (Gemini + Bedrock) with per-request override
✅ **PDF report generation** for clinical documentation
✅ **Multi-platform deployment** (AWS EC2, Render, Vercel, Heroku)
✅ **Interactive API documentation** (Swagger UI + ReDoc)
✅ **Minimalistic UI** with 3D molecular visualization and Lottie animations
✅ **Batch Mode** with cohort-based population simulation (configurable size, drug, POST API)
✅ **5-second simulation time** on cloud infrastructure
✅ **AWS Cloud-Native Architecture** - Complete production infrastructure with S3, Lambda, Step Functions, and CloudWatch integration
✅ **Population-Scale Simulation** - AWS Lambda-powered batch processing supporting up to 10,000 patients with cost-effective parallel processing ($0.0001 per patient)
✅ **Production AWS Account** - Live infrastructure on AWS Account 403732031470 with 16 VCF files across 8 chromosomes stored in S3

### Limitations & Future Work

⚠️ **Incomplete allele coverage**: Current implementation supports single-variant defining alleles (e.g., CYP2C19*2). Multi-variant haplotypes and CNVs are future work.
⚠️ **No copy-number/structural variants (CNVs)** for CYP2D6 yet (star alleles like *5 deletion, *XN duplications).
⚠️ **Phenotype and drug guidance** are guideline-derived (CPIC/PharmVar) where data files exist but are not a substitute for clinical testing.

**Planned Enhancements:**
- Multi-variant haplotype phasing for complex star alleles
- CNV detection for CYP2D6 duplications/deletions
- Expanded gene panel (TPMT, DPYD, G6PD)
- Real-time clinical trial matching
- Population-specific risk stratification

---

## Disclaimer

**Project Anukriti is a research prototype.** Outputs are synthetic predictions and must not be used for clinical decision-making, diagnosis, or treatment. **Not medical advice.**

---

## Links & Resources

- **Live Demo**: [anukriti.abhimanyurb.com](https://anukriti.abhimanyurb.com)
- **API Documentation**: [anukritibackend.abhimanyurb.com/docs](https://anukritibackend.abhimanyurb.com/docs)
- **GitHub Repository**: [github.com/Abm32/Synthatrial](https://github.com/Abm32/Synthatrial)
- **Technical Documentation**: See README.md in repository

---

## Tags

#aideas-2025 #ai-agents #social-good #aspiring-builders #healthcare-life-sciences-industry #pharmacogenomics #precision-medicine #drug-safety #clinical-trials #aws-bedrock #google-gemini #cpic-guidelines #pharmvar
