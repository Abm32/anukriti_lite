# Chapter 2: Architecture Overview

## 2.1 Design Philosophy

Anukriti follows a single guiding principle:

> **The deterministic layer is the source of truth. The LLM explains, not decides.**

This hybrid architecture ensures:
- **Reproducibility**: Same VCF input always produces the same diplotype/phenotype
- **Auditability**: Every call traces to a PharmVar/CPIC table entry
- **Explainability**: LLM provides natural language context without altering predictions
- **Safety**: No LLM hallucination can change a clinical recommendation

## 2.1.1 Current MVP Scope Freeze

To ship a focused wedge, the active trial-facing scope is intentionally narrow:

- **Workflow A**: Clopidogrel -> CYP2C19
- **Workflow B**: Warfarin -> CYP2C9 + VKORC1
- **Primary artifact**: deterministic cohort export rows with explicit confidence state:
  - `called`
  - `cannot_call`
  - `insufficient_data`

Other genes remain in the codebase, but are not part of the current trial MVP promise.

## 2.2 Three-Layer Architecture

```
Layer 1: Deterministic PGx Engine
├── PharmVar allele definitions (TSV files)
├── CPIC phenotype tables (JSON files)
├── Gene-specific callers (warfarin, SLCO1B1, TPMT, DPYD)
└── Output: diplotype + phenotype + recommendation

Layer 2: Retrieval-Augmented Generation (RAG)
├── Drug fingerprinting (RDKit Morgan fingerprints)
├── Vector similarity search (OpenSearch/Pinecone)
├── ChEMBL drug database (targets, mechanisms, side effects)
└── CPIC document retrieval (local embeddings)

Layer 3: LLM Explanation Engine
├── Google Gemini (default)
├── AWS Bedrock Claude (alternative)
├── Prompt engineering with deterministic PGx data injection
└── Output: natural language explanation with citations
```

## 2.3 Data Flow

### Single Patient Analysis

```
Input: VCF file + Drug SMILES
          │
          ├──→ vcf_processor.py
          │    ├── Parse VCF (GRCh37 or GRCh38)
          │    ├── Extract PGx variants (rs IDs)
          │    ├── Call allele_caller.py
          │    │   ├── Load pharmvar/*_alleles.tsv
          │    │   ├── Match variants → star alleles
          │    │   └── Build diplotype (*1/*2)
          │    ├── Call gene-specific callers
          │    │   ├── warfarin_caller.py (CYP2C9 + VKORC1)
          │    │   ├── slco1b1_caller.py (SLCO1B1)
          │    │   ├── tpmt_caller.py (TPMT)
          │    │   └── dpyd_caller.py (DPYD)
          │    ├── Lookup phenotype via cpic/*_phenotypes.json
          │    └── Output: Patient Profile (genotypes + phenotypes)
          │
          ├──→ input_processor.py
          │    ├── Validate SMILES (RDKit)
          │    ├── Generate Morgan fingerprint (2048-bit)
          │    └── Output: Drug vector
          │
          ├──→ vector_search.py (OpenSearch/Pinecone)
          │    ├── Query similar drugs (top-k)
          │    └── Output: Similar drug profiles
          │
          ├──→ pgx_triggers.py
          │    ├── Map drug name → relevant genes
          │    └── Output: Gene trigger list
          │
          └──→ agent_engine.py (LLM)
               ├── Inject: Patient Profile + Similar Drugs + Gene Triggers
               ├── Generate explanation (Gemini or Claude)
               └── Output: Natural language clinical summary

Final Output:
├── Structured JSON (pgx_structured.py)
├── PDF report (report_pdf.py)
└── UI display (app.py / Streamlit)
```

### Population Simulation

```
Input: Drug + Cohort size + Ancestry distribution
          │
          └──→ population_simulator.py
               ├── Generate N synthetic patients
               │   ├── Sample alleles from gnomAD v4.1 frequencies
               │   ├── Assign ancestry (AFR/EUR/EAS/SAS/AMR)
               │   └── Build genotypes per gene
               ├── Run PGx engine per patient (ThreadPoolExecutor)
               ├── Aggregate phenotype distributions
               ├── Calculate performance metrics
               └── Output: CohortResults
                    ├── Per-ancestry phenotype breakdown
                    ├── Adverse event predictions
                    └── Throughput stats (patients/min)
```

## 2.4 Module Dependency Graph

### Core Dependencies

```
config.py ←──────────── (imported by ALL modules)
    │
exceptions.py ←──────── (structured error handling)
    │
logging_config.py ←──── (standardized logging)
    │
resilience.py ────────→ vector_search.py (circuit breaker)
```

### PGx Engine Dependencies

```
data/pgx/pharmvar/*.tsv ──→ allele_caller.py ──→ vcf_processor.py
data/pgx/cpic/*.json   ──→ allele_caller.py     │
                                                  │
variant_db.py ──────────────────────────────────→ │
pgx_triggers.py ────────────────────────────────→ │
                                                  │
warfarin_caller.py ─────────────────────────────→ │
slco1b1_caller.py ──────────────────────────────→ │
tpmt_caller.py ─────────────────────────────────→ │
dpyd_caller.py ──────────────────────────────────→ │
                                                  ↓
                                          Patient Profile
```

### LLM/RAG Dependencies

```
input_processor.py (RDKit) ──→ vector_search.py (OpenSearch/Pinecone)
                                      │
chembl_processor.py ─────────────────→ │
                                      ↓
                              agent_engine.py
                                      │
                    ┌─────────────────┼─────────────────┐
                    ↓                 ↓                 ↓
              Gemini LLM      Claude (direct)    Bedrock Claude
                                                       │
                                                rag_bedrock.py
                                                       │
                                                rag/retriever.py
                                                       │
                                              embeddings_bedrock.py
```

## 2.5 Entry Points

The platform has three entry points for different use cases:

### 1. Streamlit Web UI (`app.py`)

```bash
streamlit run app.py --server.port=8501
```

Full interactive UI with:
- Manual genotype input or VCF upload
- Drug SMILES input with 3D visualization (py3Dmol + stmol)
- Real-time PGx analysis for all 8 genes
- Population simulation (100-10,000 patients)
- PDF report generation and download
- Health check sidebar with API status monitoring
- Session-based analytics counters
- LLM backend selector (Nova/Gemini/Bedrock) per session

### 2. FastAPI REST API (`api.py`)

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Endpoints:
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/analyze` | Full drug-patient analysis |
| POST | `/analyze/novel-drug` | Novel drug analysis with confidence tiers |
| GET | `/novel-drug/validation-artifact` | Novel drug benchmark artifact |
| GET | `/trial/workflows` | Supported deterministic MVP workflows |
| POST | `/trial/export` | Cohort export with explicit call states |
| POST | `/simulate` | Population simulation |
| POST | `/vcf/sample-ids` | Extract sample IDs from VCF |
| POST | `/vcf/patient-profile` | Generate patient profile from VCF |
| GET | `/health` | Health check |
| POST | `/rag/retrieve` | RAG retrieval query |

### 3. CLI / Batch Processing (`main.py`)

```bash
python main.py --input patients.json --drug warfarin --output results.json
```

Supports:
- Batch analysis from JSON/CSV
- VCF-based cohort processing
- Manual variant input (rsid-to-alt mapping)
- Configurable LLM backend (Gemini vs Bedrock)

## 2.6 Key Configuration (`src/config.py`)

All configuration is centralized in a single `Config` class loading from `.env`:

```
# LLM Configuration
GOOGLE_API_KEY          → Gemini API
AWS_ACCESS_KEY_ID       → Bedrock Claude
AWS_SECRET_ACCESS_KEY   → Bedrock Claude
AWS_REGION              → us-east-1

# Vector Database
VECTOR_DB_BACKEND       → auto | opensearch | pinecone | mock
OPENSEARCH_HOST         → OpenSearch endpoint host
OPENSEARCH_INDEX        → OpenSearch index name
PINECONE_API_KEY        → Optional Pinecone backend auth

# Application Settings
LLM_TIMEOUT             → LLM call timeout (seconds)
ENVIRONMENT             → development/staging/production
```

Security note: `.env` is `.gitignore`d. Use `.env.example` as a template.

## 2.7 Directory Structure

```
SynthaTrial-repo/
├── app.py                          # Streamlit frontend
├── api.py                          # FastAPI backend
├── main.py                         # CLI entry point
├── src/
│   ├── config.py                   # Configuration
│   ├── exceptions.py               # Custom exceptions
│   ├── logging_config.py           # Logging setup
│   ├── resilience.py               # Circuit breaker
│   ├── allele_caller.py            # Core star allele calling
│   ├── variant_db.py               # Allele function database
│   ├── vcf_processor.py            # VCF → patient profile
│   ├── remote_vcf.py               # Remote VCF / tabix access
│   ├── pgx_triggers.py             # Drug → gene mapping
│   ├── pgx_structured.py           # Output normalization
│   ├── novel_drug_inference.py     # Novel drug hypothesis + confidence tiers
│   ├── confidence_tiering.py       # Confidence tier classification
│   ├── ancestry_risk.py            # Ancestry-aware confidence scoring
│   ├── warfarin_caller.py          # Warfarin PGx
│   ├── slco1b1_caller.py           # Statin PGx
│   ├── tpmt_caller.py              # Thiopurine PGx
│   ├── dpyd_caller.py              # Fluoropyrimidine PGx
│   ├── input_processor.py          # SMILES → fingerprint
│   ├── vector_search.py            # OpenSearch/Pinecone queries
│   ├── chembl_processor.py         # ChEMBL database
│   ├── agent_engine.py             # LLM orchestration
│   ├── llm_bedrock.py              # Bedrock Claude / Nova
│   ├── rag_bedrock.py              # Bedrock RAG pipeline
│   ├── embeddings_bedrock.py       # Titan embeddings
│   ├── rag/
│   │   └── retriever.py            # Local PGx retrieval
│   ├── population_simulator.py     # Population simulation
│   ├── report_pdf.py               # PDF generation
│   ├── diagram_generator.py        # Architecture diagrams
│   ├── aws/
│   │   ├── s3_genomic_manager.py   # S3 VCF storage
│   │   ├── s3_report_manager.py    # S3 report storage
│   │   ├── step_functions_orchestrator.py
│   │   └── lambda_batch_processor.py
│   └── benchmark/
│       ├── concordance.py           # Statistical metrics
│       ├── getrm_truth.py           # Ground truth sets
│       ├── tool_comparison.py       # vs PharmCAT/Aldy/Stargazer
│       ├── expanded_validation.py   # 2000-patient validation
│       ├── ablation_study.py        # Component analysis
│       ├── clinical_cases.py        # Published case validation
│       └── pharmcat_comparison.py   # Docker head-to-head
├── data/
│   ├── pgx/
│   │   ├── pharmvar/               # Allele TSV files (8 genes)
│   │   └── cpic/                   # Phenotype JSONs + drug guidelines
│   ├── genomes/                    # 1000 Genomes VCF files
│   ├── chembl/                     # ChEMBL SQLite database
│   ├── benchmark/                  # Benchmark results
│   └── clinical_cases/             # Published case reports
├── scripts/                        # 21 utility scripts
├── tests/                          # 27 test files, 400+ tests
├── docker/                         # Docker configs, SSL, nginx
├── .github/workflows/              # 6 CI/CD workflows
├── anukriti.tex                    # IEEE paper
└── anukriti_extended_abstract.tex  # Extended abstract
```

---

**Next**: [Chapter 3 — Pharmacogenomics Engine](03-pharmacogenomics-engine.md)
