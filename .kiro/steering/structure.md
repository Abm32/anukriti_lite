# Project Structure

## Directory Organization

```
Anukriti/
├── .env                       # Environment variables (create from .env.example)
├── .env.example              # Environment template with competition settings
├── render.yaml               # Render.com deployment configuration
├── vercel.json               # Vercel serverless deployment configuration
├── Procfile                  # Heroku deployment configuration
├── runtime.txt               # Python runtime specification
├── demo.html                 # Competition demo interface
├── AWS_EC2_DEPLOYMENT.md     # Complete AWS EC2 deployment guide with VCF support
├── docs/aws/AWS_SETUP_GUIDE.md  # AWS account setup and integration guide (LIVE)
├── AWS_INTEGRATION_COMPLETE.md # AWS integration completion status and next steps (NEW)
├── COMPETITION_FEEDBACK_RESPONSE_STRATEGY.md # Comprehensive strategy addressing competition feedback (NEW - April 12, 2026)
├── IMMEDIATE_ACTION_CHECKLIST.md # Week-by-week implementation plan for feedback response (NEW - April 12, 2026)
├── lambda-trust-policy.json  # IAM trust policy for Lambda execution role (LIVE)
├── lambda/                   # AWS Lambda deployment package (LIVE)
│   ├── lambda_function.py    # Lambda function for batch processing (LIVE)
│   ├── lambda-deployment-package.zip # Lambda deployment package (LIVE)
│   └── stepfunctions-trust-policy.json # IAM trust policy for Step Functions (LIVE)
├── state-machine-definition.json # Step Functions state machine definition (LIVE)
├── .dockerignore             # Docker ignore file
├── Dockerfile                # Multi-stage Docker build
├── docker-compose.yml        # Docker Compose configuration
├── docker-compose.dev.yml    # Development Docker Compose
├── docker-compose.prod.yml   # Production Docker Compose
├── docker-entrypoint.sh      # Docker entrypoint script
├── Makefile                  # Docker management commands
├── README.md                 # Main project documentation
├── requirements.txt          # Python dependencies
├── app.py                    # Streamlit web interface
├── main.py                   # CLI entry point
├── api.py                    # FastAPI REST API wrapper
├── test_api.py               # API test suite
├── test_3d_viz.py            # 3D molecular visualization test suite
├── test_s3_integration.py    # AWS S3 integration status test (NEW)
├── AWS_UI_BACKEND_INTEGRATION_COMPLETE.md # AWS UI and backend integration completion summary (NEW)
├── BACKEND_SERVER_TIMEOUT_FIX_IMPLEMENTED.md # Backend server timeout fix implementation details (NEW)
├── STEERING_DOCS_HEALTH_CHECK_ARCHITECTURE_UPDATE.md # Health check architecture fix documentation (NEW)
├── src/                      # Core application modules
│   ├── __init__.py
│   ├── input_processor.py    # SMILES → Molecular fingerprint conversion
│   ├── vector_search.py      # Pinecone/OpenSearch similarity search
│   ├── agent_engine.py       # LLM-based pharmacogenomics simulation
│   ├── llm_bedrock.py        # AWS Bedrock LLM integration (Nova + Claude)
│   ├── embeddings_bedrock.py # AWS Bedrock Titan embeddings
│   ├── rag_bedrock.py        # Bedrock-based RAG implementation
│   ├── rag/                  # RAG system components
│   │   └── retriever.py      # Local PGx retrieval with Titan embeddings
│   ├── pgx_structured.py     # Structured PGx output formatting
│   ├── novel_drug_inference.py # Novel drug hypothesis + candidate gene inference
│   ├── confidence_tiering.py # Confidence tier classification (high/moderate/exploratory)
│   ├── ancestry_risk.py      # Ancestry-aware confidence scoring
│   ├── remote_vcf.py         # Remote VCF / tabix access
│   ├── report_pdf.py         # PDF report generation (ReportLab)
│   ├── pgx_triggers.py       # Drug → gene trigger map (drug-triggered PGx)
│   ├── allele_caller.py      # Deterministic CPIC/PharmVar allele calling (integrated with database backend - Day 1 Afternoon)
│   ├── warfarin_caller.py    # Warfarin PGx (CYP2C9 + VKORC1)
│   ├── slco1b1_caller.py     # SLCO1B1 (statin myopathy) interpretation
│   ├── tpmt_caller.py        # TPMT (thiopurine) interpretation
│   ├── dpyd_caller.py        # DPYD (fluoropyrimidine) interpretation
│   ├── vcf_processor.py      # VCF file processing and genetic analysis (integrated with database backend - Day 1 Afternoon)
│   ├── variant_db.py         # Targeted variant lookup database (PharmVar Tier 1) - LEGACY
│   ├── variant_db_v2.py      # Database-backed variant lookup (NEW - Day 1 Complete: Morning foundation + Afternoon integration)
│   ├── chembl_processor.py   # ChEMBL database integration
│   ├── config.py             # Centralised configuration (loads .env)
│   ├── exceptions.py         # Custom exception hierarchy
│   ├── logging_config.py     # Structured logging with request_id context variable
│   ├── security.py           # API key auth, request size middleware, VCF upload validation
│   ├── metrics.py            # In-process counters: vector search fallback rates, LLM timeouts
│   ├── resilience.py         # Circuit breaker for vector DB calls
│   ├── rate_limiter.py       # Bedrock rate limiter for quota management (NEW - Week 1)
│   ├── multi_backend_llm.py  # Multi-backend LLM with automatic failover (NEW - Week 1)
│   ├── cnv_detector.py       # CYP2D6 CNV detection module (PLANNED - Month 1)
│   ├── diagram_generator.py  # Architecture diagram generation (AWS Competition Enhancement)
│   ├── population_simulator.py # Population-scale simulation engine (AWS Competition Enhancement)
│   └── aws/                  # AWS service integration modules (AWS Competition Enhancement)
│       ├── __init__.py
│       ├── s3_genomic_manager.py    # S3 integration for genomic data
│       ├── s3_report_manager.py     # S3 integration for PDF reports
│       ├── lambda_batch_processor.py # Lambda integration for batch processing
│       └── step_functions_orchestrator.py # Step Functions for trial orchestration
├── tests/                    # Test suite
│   ├── __init__.py
│   ├── quick_test.py         # Quick integration tests
│   ├── validation_tests.py   # Comprehensive validation suite
│   ├── test_variant_db_v2.py # Database backend unit tests (NEW - Day 1 Complete: 15/15 passing)
│   ├── test_coriell_validation.py # Coriell reference sample validation (NEW - Week 1)
│   ├── test_pgx_core.py      # Deterministic PGx engine tests (54/54 passing, integrated with database backend)
│   ├── test_ssl_manager_properties.py          # SSL certificate property tests (NEW)
│   ├── test_ssl_integration.py                 # SSL integration tests (NEW)
│   ├── test_http_https_redirection_properties.py # HTTP to HTTPS redirection tests (NEW)
│   ├── test_data_initialization_properties.py  # Data initialization property tests (NEW)
│   ├── test_vcf_download_properties.py         # VCF download property tests (NEW)
│   ├── test_vcf_download_integration.py        # VCF download integration tests (NEW)
│   ├── test_chembl_setup_integration.py        # ChEMBL setup integration tests (NEW)
│   ├── test_dev_environment_properties.py      # Development environment property tests (NEW)
│   ├── test_containerized_testing_integration.py # Containerized testing integration (NEW)
│   ├── test_containerized_enhanced_features.py # Enhanced container features tests (NEW)
│   ├── test_security_scanner_properties.py     # Security scanning property tests (NEW)
│   ├── test_security_scanner_integration.py    # Security scanning integration tests (NEW)
│   ├── test_security_monitoring_properties.py  # Security monitoring property tests (NEW)
│   ├── test_cicd_pipeline_properties.py        # CI/CD pipeline property tests (NEW)
│   ├── test_deploy_to_registry_properties.py   # Registry deployment property tests (NEW)
│   ├── test_deploy_to_registry_integration.py  # Registry deployment integration tests (NEW)
│   ├── test_multi_arch_build_integration.py    # Multi-architecture build integration tests (NEW)
│   ├── test_complete_workflow_integration.py   # Complete workflow integration tests (NEW)
│   ├── test_github_actions_integration.py      # GitHub Actions integration tests (NEW)
│   ├── test_docker_environment_integration.py  # Docker environment integration tests (NEW)
│   ├── test_coriell_validation.py              # Coriell reference sample validation (NEW - Week 1 Day 2)
│   └── test_integration_runner.py              # Comprehensive integration test runner (NEW)
├── scripts/                  # Utility and setup scripts
│   ├── README.md
│   ├── schema.sql                   # Database schema for pharmacogenes.db (NEW - Day 1 Complete)
│   ├── init_gene_database.py        # Database initialization script (NEW - Day 1 Complete)
│   ├── test_all_llm_backends.py     # Test all LLM backends (Nova/Claude/Gemini/Anthropic) (NEW - Week 1)
│   ├── precompute_demo_scenarios.py # Pre-compute demo scenarios for offline mode (NEW - Week 1)
│   ├── load_test_demo.py            # Load testing for competition traffic (NEW - Week 2)
│   ├── aws_setup.py                 # Main CLI interface for AWS account setup and integration (PLANNED - manual setup completed)
│   ├── aws/                         # AWS setup and management modules (PLANNED - manual setup completed)
│   │   ├── aws_setup_orchestrator.py    # Main orchestration system for AWS setup (PLANNED)
│   │   ├── resource_provisioner.py      # AWS resource creation and configuration (PLANNED)
│   │   ├── security_configurator.py     # Security and IAM management (PLANNED)
│   │   ├── service_validator.py         # Integration validation and testing (PLANNED)
│   │   ├── cost_monitor.py              # Cost monitoring and optimization (PLANNED)
│   │   └── environment_manager.py       # Environment configuration management (PLANNED)
│   ├── setup_pinecone_index.py      # Pinecone index creation
│   ├── ingest_chembl_to_pinecone.py # ChEMBL data ingestion
│   ├── list_models.py               # Available LLM models
│   ├── list_models_v2.py            # Enhanced model listing with API queries
│   ├── benchmark_performance.py     # Performance benchmarking (vector retrieval, LLM, end-to-end, population simulation, AWS cost analysis)
│   ├── test_chromosome10.py         # Big 3 enzymes integration testing
│   ├── check_vcf_integrity.py       # VCF file validation and integrity checking
│   ├── generate_validation_results.py # CPIC guideline validation and accuracy metrics
│   ├── ssl_manager.py               # SSL certificate management (NEW)
│   ├── generate_ssl_certs.sh        # SSL certificate generation script (NEW)
│   ├── data_initializer.py          # Data initialization orchestrator (NEW)
│   ├── download_vcf_files.py        # VCF file download automation (NEW)
│   ├── setup_chembl.py              # ChEMBL database setup automation (NEW)
│   ├── setup_dev_env.py             # Development environment setup (NEW)
│   ├── run_tests_in_container.py    # Containerized testing with reporting (NEW)
│   ├── security_scanner.py          # Container security scanning and vulnerability detection (NEW)
│   ├── production_monitor.py        # Production monitoring and resource tracking (NEW)
│   ├── backup_manager.py            # Automated backup and recovery procedures (NEW)
│   ├── multi_arch_build.py          # Multi-architecture build orchestration (NEW)
│   ├── deploy_to_registry.py        # Container registry deployment automation (NEW)
│   ├── update_pgx_data.py           # PGx data update utilities
│   ├── pharmvar_sync.py             # Automated PharmVar data synchronization (IMPLEMENTED - Day 2 Complete)
│   ├── cpic_sync.py                 # Automated CPIC guideline synchronization (IMPLEMENTED - Day 2 Complete)
│   ├── extract_pharmacogene_regions.py # Targeted VCF extraction (300x compression) (PLANNED - Day 4-5)
│   ├── validate_pgx_data.py         # PGx data validation and quality checks (IMPLEMENTED - Day 2 Complete)
│   ├── benchmark_gene_panel.py      # Gene panel performance benchmarking (IMPLEMENTED - Day 2 Complete)
│   ├── optimize_database.py         # Database query optimization (PLANNED)
│   └── build_production_db.py       # Build optimized production database (PLANNED)
├── notebooks/                # Jupyter notebooks for development and analysis
│   └── README.md            # Notebook usage guide and examples
├── data/                     # Data storage (create directories as needed)
│   ├── chembl/              # ChEMBL database files
│   │   └── chembl_34_sqlite/
│   │       └── chembl_34.db
│   ├── genomes/             # VCF genomic data files
│   │   ├── ALL.chr2.*.vcf.gz   # Chromosome 2 (UGT1A1) — active
│   │   ├── ALL.chr6.*.vcf.gz   # Chromosome 6 (TPMT) — downloadable, not yet mapped in VCF processor
│   │   ├── ALL.chr10.*.vcf.gz  # Chromosome 10 (CYP2C19, CYP2C9) — active
│   │   ├── ALL.chr11.*.vcf.gz  # Chromosome 11 (reserved) — downloadable, not used
│   │   ├── ALL.chr12.*.vcf.gz  # Chromosome 12 (SLCO1B1) — active
│   │   ├── ALL.chr16.*.vcf.gz  # Chromosome 16 (VKORC1) — active (Warfarin PGx)
│   │   ├── ALL.chr19.*.vcf.gz  # Chromosome 19 (reserved) — downloadable, not used
│   │   ├── ALL.chr22.*.vcf.gz  # Chromosome 22 (CYP2D6) — active
│   │   └── pharmacogenes_chr*.vcf.gz  # Targeted extraction (PLANNED - Day 4-5) - 300x compressed
│   ├── pgx/                 # Curated PGx data (versioned in repo)
│   ├── pharmacogenes.db # SQLite database for 100+ gene panel (NEW - Day 1 Complete - 39 genes operational: 15 Tier 1 + 16 Tier 2 + 8 Tier 3)
│   │   ├── pharmacogenes.bed # BED file for targeted extraction (PLANNED - Day 4-5)
│   │   ├── pharmvar/        # PharmVar allele definitions (TSV)
│   │   │   ├── cyp2c19_alleles.tsv
│   │   │   ├── cyp2c9_alleles.tsv
│   │   │   └── ...
│   │   ├── cpic/            # CPIC phenotype translations (JSON)
│   │   │   ├── cyp2c19_phenotypes.json
│   │   │   ├── warfarin_response.json
│   │   │   ├── slco1b1_phenotypes.json
│   │   │   ├── statin_guidelines.json
│   │   │   └── ...
│   │   └── sources.md       # Data provenance and versioning
│   └── models/              # Cached models and indexes
│       └── pgx_retriever_index_v2.npz  # RAG retrieval index
├── docs/                    # Documentation (points to root README)
│   ├── README.md
│   ├── architecture.png         # Professional architecture diagram (AWS Competition Enhancement)
│   ├── aws_integration.png      # AWS service integration diagram (AWS Competition Enhancement)
│   ├── population_simulation.png # Population simulation visualization (AWS Competition Enhancement)
│   └── validation/              # Clinical validation documentation (NEW - Week 1 Day 2)
│       ├── CORIELL_CONCORDANCE_REPORT.md  # Analytical validation report (3,200 words)
│       └── PHARMCAT_COMPARISON.md         # Platform comparison report (3,600 words)
├── .kiro/                   # Kiro IDE configuration and project specs
│   ├── hooks/              # Agent hooks for automated workflows
│   ├── specs/              # Feature specifications and implementation plans
│   │   ├── aws-account-setup/            # AWS Account Setup and Integration spec (NEW)
│   │   ├── aws-ec2-deployment/           # AWS EC2 deployment spec
│   │   ├── aws-competition-enhancements/ # AWS AI competition enhancements spec (IMPLEMENTED)
│   │   ├── docker-enhancements/          # Docker enhancements spec
│   │   └── multi-platform-deployment/    # Multi-platform deployment automation spec (PLANNED)
│   └── steering/           # Steering documentation (tech, product, structure)
│       ├── tech.md         # Technology stack and development guidelines
│       ├── product.md      # Product overview and functionality
│       └── structure.md    # Project structure and conventions
├── docker/                  # Docker configuration files
│   ├── Dockerfile.dev       # Development Dockerfile
│   ├── Dockerfile.dev-enhanced # Enhanced development Dockerfile (NEW)
│   ├── Dockerfile.prod      # Production Dockerfile
│   ├── nginx.conf           # Nginx reverse proxy configuration with SSL
│   ├── nginx-ssl-setup.sh   # SSL certificate setup script (NEW)
│   ├── nginx-entrypoint.sh  # Nginx Docker entrypoint with SSL (NEW)
│   ├── README.md            # Docker SSL configuration documentation (NEW)
│   └── ssl/                 # SSL certificate storage directory (NEW)
├── .pre-commit-config.yaml  # Pre-commit hooks configuration (NEW)
├── pyproject.toml           # Python project configuration with dev dependencies (NEW)
├── pytest.dev.ini           # Development pytest configuration (NEW)
├── docker-compose.dev-enhanced.yml # Enhanced development Docker Compose (NEW)
├── .github/                 # GitHub Actions and repository configuration (NEW)
│   ├── workflows/           # CI/CD workflow definitions
│   │   ├── docker-build.yml     # Main Docker build and test pipeline
│   │   ├── security-scan.yml    # Security scanning workflow
│   │   ├── pr-validation.yml    # Pull request validation
│   │   └── release.yml          # Release and deployment workflow
│   ├── ISSUE_TEMPLATE/      # Issue templates for bug reports, features, security
│   ├── pull_request_template.md # Pull request template
│   └── settings.yml         # Repository settings configuration
├── security_reports/        # Security scanning reports
├── monitoring_reports/      # Production monitoring reports
├── deployment_reports/      # Deployment automation reports
├── build_reports/          # Multi-architecture build reports
└── backups/                # Automated backup storage
```

## Module Responsibilities

### Core Modules (`src/`)

- **`input_processor.py`**: Validates SMILES strings and converts to 2048-bit Morgan fingerprints using RDKit
- **`vector_search.py`**: Pluggable drug similarity search with four backends: AWS OpenSearch (SigV4 auth, `aoss`/`es`), Pinecone, local in-process NumPy cosine over ChEMBL fingerprint cache, and mock fallback. Backend selected via `VECTOR_DB_BACKEND` env var (`auto`/`opensearch`/`pinecone`/`local`/`mock`). Supports optional ML reranker via `DRUG_RERANKER_PATH`.
- **`agent_engine.py`**: LLM integration using LangChain for pharmacogenomics analysis with enhanced CPIC guideline-based prompting, structural analysis using SMILES strings, and support for four backends: Amazon Nova (default), Gemini, Bedrock Claude, and direct Anthropic Claude (`LLM_BACKEND=claude` via `langchain-anthropic`)
- **`llm_bedrock.py`**: AWS Bedrock LLM integration — `generate_pgx_response_nova()` for Amazon Nova Lite/Pro (default), `generate_pgx_response()` for Claude 3 models
- **`novel_drug_inference.py`**: Infers candidate pharmacogenes for novel compounds via analog retrieval and metadata evidence; used by `POST /analyze/novel-drug`
- **`confidence_tiering.py`**: Classifies novel drug analysis outputs into `high`, `moderate`, or `exploratory` confidence tiers; provides `decision_grade` for trial-facing use
- **`ancestry_risk.py`**: Ancestry-aware confidence scoring using gnomAD population frequencies and CPIC evidence strength per population
- **`remote_vcf.py`**: Remote VCF access via tabix for 1000 Genomes FTP; Ensembl REST API fallback for individual variant lookup
- **`embeddings_bedrock.py`**: AWS Bedrock Titan embeddings integration for vector similarity search
- **`rag_bedrock.py`**: Bedrock-based RAG pipeline — builds a query from drug name + patient profile + similar drugs, retrieves top-k PGx docs via `src/rag/retriever.py`, then calls Nova or Claude for explanation. Falls back to a hardcoded PGx stub when retrieval returns no docs.
- **`rag/`**: RAG system components for document retrieval and context generation
  - **`retriever.py`**: Hybrid PGx retrieval layer — applies keyword/gene/rsID pre-filtering then dense cosine similarity using Titan embeddings over local CPIC JSON files. Index cached as `.npz` at `data/models/pgx_retriever_index.npz`. Exposes `retrieve(query, top_k)` → `List[str]` and `retrieve_docs(query, top_k)` → `List[PgxDoc]`.
- **`pgx_structured.py`**: Structured pharmacogenomics output formatting and confidence scoring
- **`report_pdf.py`**: PDF report generation for analysis results using ReportLab
- **`pgx_triggers.py`**: Drug → gene trigger map for context-aware PGx display (CPIC-style). Covers: Warfarin → CYP2C9+VKORC1; Statins → SLCO1B1; Clopidogrel → CYP2C19; Thiopurines (azathioprine, mercaptopurine, thioguanine) → TPMT; Fluoropyrimidines (fluorouracil, capecitabine, tegafur) → DPYD; Abacavir → HLA_B5701; Irinotecan → UGT1A1; CYP2D6 substrates (codeine, tramadol, metoprolol, dextromethorphan) → CYP2D6
- **`allele_caller.py`**: Deterministic CPIC/PharmVar allele calling (CYP2C19, CYP2C9) using curated data tables. **Database Backend Integration (Day 1 Afternoon)**: Tries database backend first (`variant_db_v2.py`), falls back to TSV files for backward compatibility. Also provides `call_star_alleles_multi_variant()` for multi-rsID haplotype calling, `build_diplotype()`, and `diplotype_to_phenotype()` utilities used by all gene-specific callers.
- **`warfarin_caller.py`**: Warfarin PGx interpretation (CYP2C9 + VKORC1) with deterministic calling
- **`slco1b1_caller.py`**: SLCO1B1 (statin myopathy) rs4149056 interpretation with CPIC-grade phenotyping
- **`vcf_processor.py`**: Processes VCF files to extract pharmacogene variants and generate patient profiles. Supports multi-chromosome analysis (chromosomes 2, 6, 10, 11, 12, 16, 19, 22) for expanded pharmacogene panel with targeted variant lookup and drug-triggered profile generation. **Database Backend Integration (Day 1 Afternoon)**: Uses database backend for gene locations and profile genes, falls back to hardcoded values for backward compatibility. **Direct S3/HTTPS Access**: Supports streaming access to 1000 Genomes data from AWS Public Dataset without downloading files (zero storage cost, tabix HTTP range requests). Accepts both local file paths and S3 URLs (`s3://1000genomes/...`) with automatic detection via `VCF_SOURCE_MODE` environment variable.
- **`variant_db.py`**: Targeted variant lookup database containing Tier 1 Clinical Variants (CPIC Level A) from PharmVar with activity scores and structural variant detection. **Legacy**: Hardcoded dictionary for 8 genes. **Migration Path**: Use `variant_db_v2.py` for database-backed 100+ gene support. Maintained for backward compatibility during migration.
- **`variant_db_v2.py`** (NEW - Day 1 Complete): Database-backed variant lookup for scalable 100+ gene panel. Replaces hardcoded `VARIANT_DB` dict with SQLite backend (`pharmacogenes.db`). Provides `get_gene_variants()`, `get_phenotype_translation()`, `get_gene_location()`, and `list_supported_genes()` with sub-100ms query performance. 39 genes operational (15 Tier 1 + 16 Tier 2 + 8 Tier 3). Backward-compatible API with `variant_db.py`. **Integration Complete (Day 1 Afternoon)**: Integrated with `allele_caller.py` and `vcf_processor.py` with graceful fallback to TSV/JSON files.
- **`chembl_processor.py`**: Extracts drug information from ChEMBL SQLite database
- **`config.py`**: Centralised configuration — loads `.env`, exposes typed class attributes, `validate_required()` checks credentials for all four LLM backends (Gemini, Nova, Bedrock Claude, Anthropic Claude) and vector DB backends
- **`exceptions.py`**: Custom exception hierarchy (`LLMError`, `VectorSearchError`, `ConfigurationError`)
- **`logging_config.py`**: Structured logging with `request_id_var` context variable for correlating Streamlit → FastAPI → Bedrock call chains. Supports JSON output (`LOG_FORMAT=json`) for log aggregation and plain-text for development. Exposes `new_request_id()` / `get_request_id()` helpers used by the request-ID middleware in `api.py`.
- **`security.py`**: Security primitives — `verify_api_key` FastAPI `Depends()` guard (reads `API_KEYS` + `API_KEY_REQUIRED`, no-ops when unconfigured), `RequestSizeLimitMiddleware` (rejects oversized JSON bodies before reading), `validate_vcf_upload` (checks `.vcf.gz` extension + gzip magic bytes `\x1f\x8b` + size cap before writing to disk).
- **`metrics.py`**: Lightweight in-process counters for operational observability. `record_search(backend, fell_back, error)` tracks vector search backend usage and fallback-to-mock rates. `record_llm_call(backend, timeout, error)` tracks LLM call counts, timeouts, and errors. `snapshot()` returns a JSON-serialisable dict exposed via `GET /metrics`.
- **`resilience.py`**: Circuit breaker for vector DB calls
- **`population_simulator.py`**: Population-scale simulation engine supporting diverse global populations (AFR, EUR, EAS, SAS, AMR), parallel processing, real-time metrics, and scalability up to 10,000 patients (AWS Competition Enhancement)

### AWS Integration Modules (`src/aws/`) - AWS Competition Enhancement

- **`s3_genomic_manager.py`**: S3 integration for genomic data storage with VCF file management, presigned URLs, and Intelligent Tiering cost optimization
- **`s3_report_manager.py`**: S3 integration for PDF report storage with lifecycle policies, automatic cleanup, and secure sharing via presigned URLs
- **`lambda_batch_processor.py`**: Lambda integration for batch processing — optional scale-out path invoked when `AWS_LAMBDA_FUNCTION_NAME` is configured; in-process `PopulationSimulator` handles cohort runs without it
- **`step_functions_orchestrator.py`**: Step Functions integration for trial workflow orchestration — optional when `AWS_STEP_FUNCTIONS_STATE_MACHINE` ARN is configured; the API works without it

### Entry Points

- **`app.py`**: Minimalistic Streamlit web interface with enhanced 3D molecular visualization (py3Dmol + stmol with 3 fallback coordinate generation strategies, MMFF force field optimization, automatic 2D fallback for complex molecules, and molecular properties display showing atom count, bond count, and molecular weight), Lottie animations (DNA, loading, success), streamlined user experience with Inter font, curated drug database (7 drugs: Warfarin, Clopidogrel, Codeine, Ibuprofen, Metoprolol, Simvastatin, Irinotecan), batch processing capabilities, and competition-ready features. Features a 4-tab interface (Simulation Lab, Batch Processing, Analytics, About) with configurable API URL, real-time system status, multi-enzyme patient profiling (CYP2D6, CYP2C19, CYP2C9, UGT1A1, SLCO1B1), 3-stage pipeline visualization (Genetics → Similar Drugs → Predicted Response), LLM backend selector (Gemini/Bedrock), per-request backend override capability, drug-triggered PGx highlighting with orange "Relevant" tags, AI Insight Preview panel, Quick Start Guide banner, three-panel layout (Parameters | Patient Profile | Molecular View), sidebar collapsed by default for cleaner main interface, **real-time AWS integration status display in sidebar**, **enhanced Analytics tab with AWS service status panels**, **population simulation demo button (100-10K patients)**, and **professional competition presentation features with live AWS account information**. **VCF Patient Profile Integration**: Requires FastAPI backend server (`api.py`) to be running for VCF sample discovery, patient profile generation, and direct VCF file uploads (bgzipped .vcf.gz with optional .tbi index).
- **`api.py`**: FastAPI REST API wrapper. Key endpoints: `POST /analyze`, `POST /analyze/novel-drug`, `GET /novel-drug/validation-artifact`, `GET /trial/workflows`, `POST /trial/export`, `POST /simulate`, `POST /vcf/sample-ids`, `POST /vcf/patient-profile`, `POST /vcf-upload`, `POST /vcf-upload-samples`, `POST /vcf-upload-profile`, `DELETE /vcf-upload/{upload_id}`, `GET /health`, `POST /rag/retrieve`, `GET /metrics`. **Fast Health Check Architecture**: `/health-fast` (< 2 seconds), `/` (< 5 seconds), `/health` (< 15 seconds). Supports Amazon Nova (default), Gemini, Bedrock Claude, and direct Anthropic Claude backends with per-request override. **Security**: CORS restricted via `ALLOWED_ORIGINS` env var, API key auth via `verify_api_key` dependency, `RequestSizeLimitMiddleware` on all JSON endpoints, VCF upload size + magic-byte validation, background TTL cleanup of stale upload sessions. **Input validation**: `AnalyzeRequest` enforces field length limits (`drug_name` ≤ 200, `patient_profile` ≤ 20,000, `drug_smiles` ≤ 2,000 chars) and validates SMILES character set and `llm_backend` enum. **Observability**: request-ID middleware injects `X-Request-ID` into every request/response; `GET /metrics` exposes live vector search fallback rates and LLM timeout rates.
- **`main.py`**: Command-line interface supporting both VCF and manual patient profiles. Supports single-chromosome (CYP2D6 only) and multi-chromosome (expanded pharmacogene panel) analysis with `--vcf-chr10` parameter for chromosome 10 data and additional chromosome support

### Testing (`tests/`)

- **`quick_test.py`**: Fast integration tests for imports, file existence, and basic functionality
- **`validation_tests.py`**: Comprehensive test suite with known CYP2D6 substrates and expected outcomes
- **`test_api.py`**: Automated test suite for FastAPI endpoints with local and deployed testing capabilities (NEW)
- **`test_3d_viz.py`**: Comprehensive 3D molecular visualization test suite validating SMILES parsing, 3D coordinate generation with 3 fallback strategies, MMFF force field optimization, py3Dmol rendering, automatic 2D fallback for complex molecules, and molecular properties display for all standard library drugs (NEW)
- **`test_s3_integration.py`**: Comprehensive AWS S3 integration status test validating S3 genomic data connectivity, VCF file discovery (S3 vs local), AWS services availability (Lambda, Step Functions), and integration summary reporting (NEW)
- **`test_pgx_core.py`**: Unit tests for the deterministic PGx engine — covers allele_caller (alt_dosage, genotype parsing, diplotype building, phenotype lookup, database backend integration), warfarin_caller (CYP2C9 + VKORC1), slco1b1_caller, tpmt_caller, dpyd_caller, and confidence_tiering. 54 tests, runs fully offline with no LLM or AWS dependencies. **Integration Verified (Day 1 Afternoon)**: All tests passing with database backend integration.
- **`test_coriell_validation.py`** (NEW - Week 1 Day 2): Coriell reference sample validation test suite with 10 reference samples (expandable to 50+). Validates analytical accuracy against gold-standard references with ≥95% concordance target. Includes parametrized tests for individual samples, overall concordance calculation, gene-specific and population-specific metrics, detailed discrepancy reporting, and placeholders for CYP2D6 CNV detection (Month 1) and rare variant detection (Month 3). Publication-ready validation framework for regulatory submission.

### Scripts (`scripts/`)

- **AWS setup automation**: Live AWS infrastructure operational (S3, Lambda, Step Functions on Account 403732031470) with 16 genomic files uploaded to S3. Manual setup completed using `docs/aws/AWS_SETUP_GUIDE.md`. Automation scripts planned for future deployment scenarios. See `docs/aws/AWS_INTEGRATION_COMPLETE.md` for current status and next steps.
- **`schema.sql`**: Database schema for pharmacogenes.db with 5 tables (genes, variants, phenotypes, drug_gene_pairs, data_versions) (NEW - Day 1)
- **`init_gene_database.py`**: Database initialization script for loading Tier 1/2/3 genes with status checking and force recreate capability (NEW - Day 1)
- **`pharmvar_sync.py`**: Automated PharmVar allele definition synchronization with multi-source data strategy (web scraping → local files → fallback) and activity score mapping (NEW - Day 2)
- **`cpic_sync.py`**: Automated CPIC phenotype translation synchronization with standard phenotype library for 15 genes (NEW - Day 2)
- **`validate_pgx_data.py`**: Comprehensive data quality validation for gene metadata, variant quality, and phenotype quality with CI/CD integration (NEW - Day 2)
- **`benchmark_gene_panel.py`**: Gene panel performance benchmarking verifying sub-100ms query performance across all genes (NEW - Day 2)
- **`run_pharmcat_comparison.py`** (VERIFIED - Week 1 Day 2): PharmCAT comparison script for head-to-head platform validation. Compares Anukriti vs PharmCAT on 100 samples from 1000 Genomes Project with diverse population coverage (25% each: African, Asian, European, Hispanic). Supports multiple genes (CYP2D6, CYP2C19, CYP2C9, TPMT, DPYD, SLCO1B1, VKORC1, UGT1A1), JSON output, LaTeX table generation for publications, and Docker-based PharmCAT execution. Target: 90-95% concordance accounting for algorithm differences.
- **`setup_pinecone_index.py`**: Creates Pinecone index with correct configuration (2048 dimensions, cosine metric)
- **`ingest_chembl_to_pinecone.py`**: Batch ingestion of ChEMBL drugs into Pinecone vector database
- **`list_models.py`**: Lists available Gemini models for testing different LLM versions
- **`list_models_v2.py`**: Enhanced model listing with direct API queries and detailed model information including capabilities and performance metrics
- **`test_chromosome10.py`**: Comprehensive testing suite for Big 3 enzymes integration and multi-chromosome functionality
- **`check_vcf_integrity.py`**: Validates VCF file integrity, checks for corruption, and verifies download completeness with detailed reporting
- **`generate_validation_results.py`**: Generates comprehensive validation results for research and paper documentation with CPIC compliance metrics
- **`benchmark_performance.py`**: Performance benchmarking for single and multi-chromosome processing with detailed timing analysis, population simulation performance metrics, and AWS service integration benchmarks with cost analysis
- **`ssl_manager.py`**: SSL certificate management with generation, validation, expiration checking, and renewal (NEW)
- **`generate_ssl_certs.sh`**: Shell script for automated SSL certificate generation (NEW)
- **`test_aws_integration.py`**: AWS service integration testing for S3, Lambda, and Step Functions with comprehensive validation (AWS Competition Enhancement)
- **`prepare_competition_demo.py`**: Competition demo preparation including video script generation, performance validation, and narrative content updates (AWS Competition Enhancement)
- **`data_initializer.py`**: Data initialization orchestrator for automated VCF and ChEMBL setup (NEW)
- **`download_vcf_files.py`**: Automated VCF file downloads with integrity validation (NEW)
- **`setup_chembl.py`**: Automated ChEMBL database download and setup (NEW)
- **`setup_dev_env.py`**: Development environment setup with pre-commit hooks and code quality tools (NEW)
- **`security_scanner.py`**: Container security scanning with vulnerability detection, compliance checking, and security reporting using Trivy/Grype integration (NEW)
- **`production_monitor.py`**: Production monitoring with resource tracking, health monitoring, alerting, and performance metrics collection (NEW)
- **`backup_manager.py`**: Automated backup and recovery procedures with data integrity validation and disaster recovery capabilities (NEW)
- **`multi_arch_build.py`**: Multi-architecture build orchestration for AMD64/ARM64 platforms with build optimization and artifact management (NEW)
- **`deploy_to_registry.py`**: Container registry deployment automation with environment-specific deployment, health checks, and rollback capabilities (NEW)

### Documentation

- **`README.md`** (root): Single source of truth — setup, data, deployment, commands, architecture, troubleshooting, API (interactive docs at /docs when running).
- **`docs/README.md`**: Documentation index with links to all guides and chapters.
- **`docs/guide/`**: 10-chapter comprehensive guide covering architecture, PGx engine, LLM/RAG, VCF pipeline, population simulation, benchmarking, frontend/API, DevOps, and testing. Chapters 01–10 in `docs/guide/`.
- **`docs/aws/`**: AWS deployment, setup, and integration guides (AWS_SETUP_GUIDE.md, AWS_EC2_DEPLOYMENT.md, OPENSEARCH_VECTOR_SETUP.md).
- **`PRODUCTION_READINESS_ANALYSIS.md`** (NEW): Comprehensive production readiness assessment identifying critical gene coverage gap (8 genes vs 100+ needed) with detailed solutions, cost analysis, risk assessment, and 6-8 week roadmap to clinical deployment.
- **`EXECUTIVE_SUMMARY_PRODUCTION_READINESS.md`** (NEW): Executive-level overview of production readiness status, key problems, three-pronged solution (database backend, automated pipeline, targeted extraction), cost-benefit analysis, and recommendations.
- **`DAY1_MORNING_COMPLETE.md`** (NEW - Day 1): Morning session completion summary covering database schema design, initialization script, database backend module, and unit tests (15/15 passing).
- **`DAY1_AFTERNOON_COMPLETE.md`** (NEW - Day 1): Afternoon session completion summary covering integration with allele_caller.py and vcf_processor.py, backward compatibility verification, and integration testing (69/69 tests passing).
- **`DAY1_COMPLETE_SUMMARY.md`** (NEW - Day 1): Comprehensive Day 1 summary with architecture diagrams, test results, and next steps for Day 2.
- **`QUICK_STATUS_DAY1.md`** (NEW - Day 1): Quick reference for Day 1 completion status and verification commands.
- **`DAY2_COMPLETE_SUMMARY.md`** (NEW - Day 2): Day 2 completion summary covering PharmVar sync, CPIC sync, data validation, and automated pipeline (24-48x speedup achieved).
- **`QUICK_STATUS_DAY2.md`** (NEW - Day 2): Quick reference for Day 2 completion status and verification commands.
- **`WEEK1_DAY1_COMPLETE.md`** (NEW - Week 1 Day 1): Day 1 completion summary with gene panel expansion (39 genes) and FDA regulatory documentation (15,300 words).
- **`WEEK1_DAY2_COMPLETE.md`** (NEW - Week 1 Day 2): Day 2 completion summary with clinical validation framework establishment (6,800 words of validation documentation).
- **`QUICK_STATUS_WEEK1_DAY2.md`** (NEW - Week 1 Day 2): Quick status reference for Day 2 completion.
- **`docs/validation/`** (NEW - Week 1 Day 2): Clinical validation documentation directory
  - **`CORIELL_CONCORDANCE_REPORT.md`**: Analytical validation report template (3,200 words) for Coriell reference sample validation. Includes methods, results tables, discrepancy analysis, regulatory implications (FDA Non-Device CDS compliance), and publication-ready format for peer-reviewed journals.
  - **`PHARMCAT_COMPARISON.md`**: Platform comparison report template (3,600 words) for head-to-head comparison with PharmCAT. Includes 100 diverse samples, algorithm comparison, clinical implications, and publication-ready format.
- **`DAYS_1_2_COMPLETE.md`** (NEW - Days 1-2): Comprehensive Days 1-2 summary with progress overview, achievements, testing results, and next steps.
- **`IMPLEMENTATION_PROGRESS_SUMMARY.md`** (NEW - Days 1-2): Overall implementation progress tracking with metrics, achievements, and remaining work.
- **`NEXT_STEPS_DAY3.md`** (NEW - Day 3): Day 3 task breakdown with performance benchmarking, documentation updates, and git commit instructions.
- **`docs/GENE_PANEL_EXPANSION_SPEC.md`** (NEW): Technical specification for scaling from 8 to 100+ genes including database schema, implementation plan, testing strategy, and deployment procedures.
- **`QUICK_START_GENE_EXPANSION.md`** (NEW): Practical 2-week implementation guide with day-by-day tasks, validation checklist, troubleshooting, and next steps.
- **`ACTION_PLAN_IMMEDIATE.md`** (NEW): Start-today action plan with hour-by-hour breakdown for Days 1-10, success criteria, rollback plan, and immediate next steps.
- **`docs/1000_GENOMES_AWS_ACCESS.md`** (NEW): Complete technical guide for direct S3/HTTPS streaming access to 1000 Genomes data from AWS Public Dataset, including usage examples, performance characteristics, troubleshooting, and cost analysis (zero storage cost, no downloads required).
- **`1000_GENOMES_S3_OPTIMIZATION.md`** (NEW): Quick summary of S3 streaming optimization, highlighting zero-cost access and automatic detection capabilities.
- **`S3_ACCESS_ALREADY_IMPLEMENTED.md`** (NEW): Confirmation document showing that S3/HTTPS streaming is already implemented in the platform with code references and configuration details.
- **`test_1000genomes_s3_access.py`** (NEW): Test script for validating S3/HTTPS streaming access to 1000 Genomes data with comprehensive checks for URL validation, configuration, and API helper functions.
- **`GENE_ACCESS_ARCHITECTURE_EXPLANATION.md`** (NEW - Week 1): Comprehensive 300+ line guide explaining how the system accesses 39 genes through the database backend architecture, including data flow diagrams, verification commands, and Python examples.
- **`GENE_PANEL_EXPANSION_EXPLAINED.md`** (NEW): Detailed explanation of gene panel expansion complexity, showing that adding a gene requires 150-500 database records (not just a name), documenting the automated pipeline achievement (24-48x speedup), and explaining why "39 genes operational" represents ~6,000-20,000 validated database records.
- **`DATA_SOURCE_FLOW.md`** (NEW - Week 1): Complete 300+ line guide explaining where gene data comes from, covering three data sources (NCBI Gene database for gene metadata, PharmVar for variant definitions, CPIC for phenotype mappings), complete data flow from external sources through automated pipeline to SQLite database, verification commands, and example gene addition process. Includes multi-source fallback strategy ensuring 100% uptime.

### Kiro IDE Configuration (`.kiro/`)

- **`hooks/`**: Agent hooks for automated workflows
  - Automated actions triggered by IDE events (file edits, commits, etc.)
  - Custom workflows for development automation
- **`specs/`**: Feature specifications and implementation plans
  - **`aws-account-setup/`**: AWS Account Setup and Integration specification with automated resource provisioning, security configuration, and service validation (LIVE - manual setup completed on AWS Account 403732031470 with 16 genomic files uploaded to S3, automation scripts planned)
  - **`aws-ec2-deployment/`**: AWS EC2 deployment specification with requirements, design, and tasks
  - **`docker-enhancements/`**: Docker enhancements specification for SSL, data initialization, security, and CI/CD
  - **`aws-competition-enhancements/`**: AWS AI competition winning enhancements specification with strategic platform optimizations for judge evaluation, population-scale simulation, meaningful AWS integration, and compelling narrative (IMPLEMENTED)
  - **`backend-server-timeout-fix/`**: Backend server timeout fix specification addressing API server hanging issues, implementing fast health check endpoints, and optimizing AWS service checks (IMPLEMENTED)
  - **`multi-platform-deployment/`**: Multi-platform deployment automation specification (PLANNED - not yet implemented)
  - Each spec contains: requirements.md, design.md, tasks.md, and README.md
- **`steering/`**: Steering documentation files
  - **`tech.md`**: Technology stack, dependencies, commands, and development guidelines
  - **`product.md`**: Product overview, functionality, use cases, and target users
  - **`structure.md`**: Project structure, module responsibilities, and conventions

### Competition and Demo Files

- **`demo.html`**: Professional competition demo interface with gradient design and real-time API integration
- **AWS Competition Enhancement Documentation**: Strategic enhancement documentation for AWS AI competition success
  - **Architecture diagrams**: Professional visual communication of system architecture with AWS service integration (docs/architecture.png, docs/aws_integration.png, docs/population_simulation.png)
  - **Population simulation demonstrations**: Large-scale cohort simulation showcasing scalability and performance
  - **Compelling narrative content**: Healthcare impact messaging and technical differentiation from "GPT wrapper" projects
  - **Judge-friendly documentation**: Optimized for 2-minute evaluation window with clear value proposition
- **`render.yaml`**: One-click Render.com deployment configuration
- **`vercel.json`**: Vercel serverless deployment configuration
- **`Procfile`**: Heroku deployment configuration
- **`runtime.txt`**: Python runtime specification for cloud platforms
- **`AWS_EC2_DEPLOYMENT.md`**: Complete AWS EC2 deployment guide with Docker containerization and VCF file storage. Provides the most cost-effective production deployment strategy (₹0-₹750/month) using EC2 local storage instead of expensive managed services.
- **`.env.example`**: Environment template with competition and cloud deployment settings

### Examples (`examples/`) (NEW)

- **`deployment_example.py`**: Deployment automation example scripts
- **`anukriti_frontend_example.html`**: Beautiful dark-themed frontend UI for FastAPI with neon cyan accents, pre-loaded drug examples, and color-coded risk levels

### Docker Configuration (`docker/`)

- **`Dockerfile.dev`**: Development-optimized Docker image with debugging tools, hot reloading, and Jupyter notebook support
- **`Dockerfile.dev-enhanced`**: Enhanced development Docker image with additional development tools, code quality tools, and testing frameworks (NEW)
- **`Dockerfile.prod`**: Production-optimized Docker image with minimal size, security hardening, and SSL support
- **`nginx.conf`**: Nginx reverse proxy configuration with SSL support, WebSocket handling, and security headers
- **`nginx-ssl-setup.sh`**: Automated SSL certificate detection and setup script (NEW)
- **`nginx-entrypoint.sh`**: Docker entrypoint script with SSL initialization (NEW)
- **`README.md`**: Docker SSL configuration documentation and usage guide (NEW)
- **`ssl/`**: SSL certificate storage directory for development and production certificates (NEW)

### GitHub Actions and CI/CD (`/.github/`)

- **`workflows/docker-build.yml`**: Main CI/CD pipeline with multi-architecture builds, testing, and deployment automation
- **`workflows/security-scan.yml`**: Security scanning workflow with vulnerability detection and compliance reporting
- **`workflows/pr-validation.yml`**: Pull request validation with automated testing and code quality checks
- **`workflows/release.yml`**: Release and deployment workflow with automated registry deployment
- **`ISSUE_TEMPLATE/`**: Issue templates for bug reports, feature requests, and security issues
- **`pull_request_template.md`**: Standardized pull request template with checklist and guidelines
- **`settings.yml`**: Repository settings configuration for automated repository management

### Security and Monitoring (`/security_reports/`, `/monitoring_reports/`)

- **Security Reports**: Automated vulnerability scanning reports, compliance assessments, and security metrics
- **Monitoring Reports**: Production monitoring data, performance metrics, resource utilization, and health status
- **Deployment Reports**: Deployment automation logs, success/failure tracking, and rollback procedures
- **Build Reports**: Multi-architecture build logs, platform-specific metrics, and build artifact tracking
- **Backup Reports**: Automated backup status, integrity validation, and recovery procedures

### Jupyter Notebooks (`notebooks/`)

- **Development and Analysis**: Interactive notebooks for data exploration, model testing, and performance analysis
- **Environment Integration**: Full access to Anukriti modules and dependencies within containerized Jupyter environment
- **Use Cases**: VCF data exploration, ChEMBL analysis, model validation, and performance benchmarking

### Integration Testing (`tests/test_*_integration.py`)

- **Complete Workflow Integration**: End-to-end testing of SSL + Data + Deployment workflows
- **GitHub Actions Integration**: CI/CD pipeline testing and workflow validation
- **Docker Environment Integration**: Container orchestration and environment consistency testing
- **Security and Monitoring Integration**: Security scanning and production monitoring validation
## File Naming Conventions

- **Python modules**: Snake case (e.g., `input_processor.py`)
- **Classes**: Pascal case (e.g., `DrugProcessor`)
- **Functions**: Snake case (e.g., `get_drug_fingerprint`)
- **Constants**: Upper snake case (e.g., `VALIDATION_CASES`)
- **Data files**: Descriptive names with appropriate extensions (e.g., `chembl_34.db`, `chr22.vcf.gz`, `chr10.vcf.gz`)

## Import Patterns

```python
# Standard library imports first
import os
import sys
from typing import List

# Third-party imports
import pandas as pd
from rdkit import Chem
from langchain_google_genai import ChatGoogleGenerativeAI

# Local imports last
from src.input_processor import get_drug_fingerprint
from src.vector_search import find_similar_drugs
```

## Configuration Management

- **Environment variables**: Stored in `.env` file, loaded via `python-dotenv`
- **Environment template**: `.env.example` includes competition deployment settings and cloud platform configurations
- **Default values**: Provided for optional configurations (e.g., `GEMINI_MODEL`, `ENVIRONMENT`, `DEBUG`)
- **Graceful fallbacks**: Mock modes when API keys are missing
- **Validation**: Check for required files and configurations at runtime
- **Cloud deployment configuration**: Platform-specific deployment files (render.yaml, vercel.json, Procfile)
- **Competition settings**: Optimized environment variables for demo and competition deployment
- **Docker environment**: Automated environment setup and validation in containerized deployments
- **Development configuration**: `.env.dev` and `pytest.dev.ini` for development-specific settings
- **Pre-commit configuration**: `.pre-commit-config.yaml` for automated code quality checks
- **Python project configuration**: `pyproject.toml` with development dependencies and tool configurations
- **Security scanning configuration**: Automated vulnerability scanning with Trivy/Grype integration and security reporting
- **Production monitoring configuration**: Resource tracking, health monitoring, alerting, and performance metrics collection
- **CI/CD pipeline configuration**: GitHub Actions workflows for automated builds, testing, and deployment
- **Multi-architecture build configuration**: AMD64/ARM64 platform support with build optimization
- **Backup and recovery configuration**: Automated backup procedures with integrity validation and disaster recovery
- **Conda environment management**: Critical requirement to use `synthatrial` conda environment for all operations
- **Backend server configuration**: FastAPI server must be running for VCF patient profile functionality
- **Timeout configuration management**: Critical timeout settings optimized for backend server performance and S3 VCF processing:
  - `HEALTH_CHECK_TIMEOUT=5` - Fast health check timeout (reduced from 120s for quick connectivity)
  - `HEALTH_DETAILED_TIMEOUT=30` - Detailed health check with AWS services
  - `VCF_PROFILE_TIMEOUT=300` - VCF profile generation timeout (5 minutes for large S3 files)
  - `AWS_SERVICE_CHECK_TIMEOUT=10` - Per AWS service check timeout
  - `CONFIG_VALIDATION_TIMEOUT=5` - Configuration validation timeout

## Error Handling Patterns

- **Descriptive error messages**: Include specific guidance for resolution
- **Graceful degradation**: Continue with reduced functionality when possible
- **User-friendly output**: Clear status messages and progress indicators
- **Exception chaining**: Preserve original error context while providing user guidance
- **Backend connectivity**: Clear error messages when FastAPI server is not running ("Backend Offline" error) with specific timeout vs connection error handling
- **Environment validation**: Automatic detection and guidance for conda environment issues
- **Timeout handling**: Comprehensive timeout management with fast health checks (5s) and optimized S3 VCF processing (300s) with fallback mechanisms
- **S3 processing indicators**: Progress messages and status updates for large file operations
- **Health check optimization**: Multiple health check endpoints for different use cases (fast connectivity vs detailed status)
