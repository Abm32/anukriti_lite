# Anukriti (SynthaTrial) — Comprehensive Project Guide

## An LLM-Augmented Pharmacogenomics Platform for In Silico Clinical Trials

This guide provides a complete, detailed walkthrough of the Anukriti platform — from
scientific foundations to production deployment. It is organized into 10 chapters
covering every aspect of the system.

---

## Table of Contents

| Chapter | Title | Description |
|---------|-------|-------------|
| [01](01-introduction-and-scientific-background.md) | Introduction & Scientific Background | The pharmacogenomics problem, clinical motivation, and project goals |
| [02](02-architecture-overview.md) | Architecture Overview | System design, hybrid deterministic+LLM approach, data flow |
| [03](03-pharmacogenomics-engine.md) | Pharmacogenomics Engine | 8-gene panel, allele calling, phenotype prediction, CPIC/PharmVar data |
| [04](04-llm-and-rag-integration.md) | LLM & RAG Integration | Gemini/Claude backends, OpenSearch/Pinecone vector search, retrieval-augmented generation |
| [05](05-vcf-processing-pipeline.md) | VCF Processing Pipeline | VCF parsing, GRCh37/38 support, remote access, patient profile generation |
| [06](06-population-simulation.md) | Population Simulation & Ancestry | Synthetic cohorts, gnomAD frequencies, 5-ancestry support, throughput benchmarks |
| [07](07-benchmarking-and-validation.md) | Benchmarking & Validation | GeT-RM truth sets, tool comparison, ablation study, clinical cases |
| [08](08-frontend-backend-api.md) | Frontend, Backend & API | Streamlit UI, FastAPI endpoints, PDF reports, CLI interface |
| [09](09-cloud-infrastructure-and-devops.md) | Cloud Infrastructure & DevOps | AWS integration, Docker, CI/CD, security scanning, SSL |
| [10](10-testing-and-quality.md) | Testing & Quality Assurance | 400+ tests, property-based testing, code quality, pre-commit hooks |

---

## Quick Facts

| Metric | Value |
|--------|-------|
| Genes covered | 8 (CYP2D6, CYP2C19, CYP2C9, UGT1A1, SLCO1B1, VKORC1, TPMT, DPYD) |
| Validation samples | 2,253 (240 GeT-RM + 2,000 synthetic + 13 clinical cases) |
| Diplotype concordance | 100% (95% CI: 88.6-100%) |
| Throughput | Hardware-dependent — run `scripts/benchmark_performance.py` locally for accurate numbers |
| Tests | 400+ (unit, integration, property-based) |
| Default LLM backend | Amazon Nova Lite/Pro on AWS Bedrock (`LLM_BACKEND=nova`) |
| Alternative backends | Google Gemini (`LLM_BACKEND=gemini`), Bedrock Claude (`LLM_BACKEND=bedrock`) |
| Target conference | Samanwaya'26 (IEEE format) |
| Live demo | [anukriti.abhimanyurb.com](https://anukriti.abhimanyurb.com) |

---

## How to Use This Guide

- **New contributors**: Start with Chapters 1-2 for context, then Chapter 3 for the core engine
- **Frontend/backend developers**: Jump to Chapter 8
- **DevOps/deployment**: Chapter 9
- **Researchers/reviewers**: Chapters 6-7 for validation methodology
- **Paper reviewers**: Chapter 7 maps directly to the paper's results sections
