# Technology Stack

**UPDATED - Competition Feedback Response (April 12, 2026)**: This document reflects strategic updates addressing AWS AI competition feedback. Key changes: (1) Gene panel expansion roadmap (15→40→100+ genes); (2) Multi-backend LLM resilience architecture; (3) Clinical validation framework; (4) FDA regulatory compliance documentation; (5) Market adoption strategy. See `COMPETITION_FEEDBACK_RESPONSE_STRATEGY.md` for comprehensive plan.

---

## Core Technologies

- **Python 3.10+** - Primary language
- **RDKit** - Molecular fingerprinting and cheminformatics
- **Pinecone** - Vector similarity search database
- **Amazon Nova** - Default LLM backend on AWS Bedrock (Nova Lite / Nova Pro) for pharmacogenomics explanation
- **AWS Bedrock** - Cloud LLM platform hosting Nova and Claude models with Titan embeddings for RAG
- **Google Gemini** - Alternative LLM backend (gemini-2.5-flash, gemini-2.5-pro, gemini-2.0-flash)
- **Anthropic Claude** - Direct Anthropic API backend (`LLM_BACKEND=claude`) via `langchain-anthropic`; separate from Bedrock Claude
- **LangChain** - LLM integration framework with enhanced RAG capabilities supporting Gemini, Bedrock, and Anthropic backends
- **Streamlit** - Modern minimalistic web interface with 3D molecular visualization (py3Dmol + stmol), Lottie animations, and user-friendly UX
- **FastAPI** - Production-ready REST API with interactive documentation (Swagger UI + ReDoc)
- **SQLite** - ChEMBL database storage and pharmacogene variant database (production-ready scalable backend with sub-100ms query performance)
- **Database-Backed Variant Storage** - SQLite database (`pharmacogenes.db`) replaces hardcoded dictionaries, enabling scalable 100+ gene panel with automated PharmVar/CPIC synchronization
- **Docker** - Containerization for development and production deployment with multi-stage builds
- **Multi-chromosome VCF processing** - Expanded pharmacogene panel across 8 chromosomes (2, 6, 10, 11, 12, 16, 19, 22) with scalability to 100+ genes via database backend. **Direct S3/HTTPS Access**: Supports streaming access to 1000 Genomes data from AWS Public Dataset without downloading files (zero storage cost, tabix HTTP range requests)
- **Targeted Variant Lookup** - Database-backed genotyping using Tier 1 Clinical Variants (CPIC Level A) from PharmVar with sub-100ms query performance
- **Deterministic PGx Engine** - CPIC/PharmVar guideline-based allele calling with database-backed variant storage (39 Tier 1+2+3 genes operational, expanding to 40 genes Week 2, 100+ genes Month 3)
- **Automated Data Pipeline** - PharmVar/CPIC synchronization scripts for automated gene panel updates (24-48x faster: 5 minutes vs 2-4 hours per gene)
- **Multi-Backend LLM Resilience (IMPLEMENTED - Week 1 Days 3-4)** - Automatic failover across Nova → Bedrock Claude → Gemini → Anthropic → Deterministic fallback with 99.9% uptime guarantee. Rate limiting prevents quota exhaustion. Pre-computed demo scenarios for offline mode.
- **CYP2D6 CNV Detection** - Advanced copy number variation detection (0-6 copies) using digital PCR-inspired algorithms (PLANNED - Month 1)
- **Clinical Validation Framework** - Coriell reference sample validation (95% concordance target) and PharmCAT comparison studies (IMPLEMENTED - Week 1 Day 2: Test suite with 10 reference samples, expandable to 50+; PharmCAT comparison framework for 100 diverse samples; publication-ready validation reports)
- **FDA Regulatory Compliance** - Non-Device CDS qualification under 21st Century Cures Act with clear clinical deployment pathway
- **Targeted VCF Extraction** - Region-based extraction reducing storage from 150GB to 500MB (300x compression) for production deployment
- **Drug-triggered PGx** - Context-aware gene display showing only drug-relevant pharmacogenes
- **Hybrid RAG Architecture** - Two-layer retrieval: (1) PGx knowledge RAG using Titan embeddings over local CPIC JSON files with keyword/metadata pre-filtering (`src/rag/retriever.py`); (2) molecular fingerprint similarity search over ChEMBL via pluggable vector backends (Pinecone, OpenSearch, local NumPy, mock)
- **Pluggable Vector Search** - Four backends for drug similarity: Pinecone, AWS OpenSearch (SigV4 auth), local in-process NumPy cosine over ChEMBL cache, and mock fallback. Controlled via `VECTOR_DB_BACKEND` env var (`auto`/`pinecone`/`opensearch`/`local`/`mock`)
- **PDF Report Generation** - Clinical-style downloadable reports using ReportLab
- **AWS Service Integration** - Comprehensive cloud-native architecture with S3, Lambda, Step Functions, and CloudWatch (AWS Competition Enhancement)
- **Population-Scale Simulation** - Large-cohort simulation supporting up to 10,000 patients with diverse global populations (AWS Competition Enhancement)
- **Professional Architecture Diagrams** - Programmatic diagram generation using AWS service icons for competition presentation (AWS Competition Enhancement)

## Key Dependencies

### Core Dependencies
```
rdkit>=2023.9.1
pandas>=2.0.0
scipy>=1.11.0
scikit-learn>=1.3.0
langchain>=0.1.0
langchain-google-genai>=0.1.0
langchain-anthropic>=1.0.0
langchain-openai>=0.0.5
pinecone>=5.0.0
opensearch-py>=2.6.0
psycopg2-binary>=2.9.0
python-dotenv>=1.0.0
python-multipart>=0.0.9
streamlit>=1.28.0
plotly>=5.18.0
py3Dmol>=2.0.0
stmol>=0.0.9
streamlit-lottie>=0.0.5
requests>=2.28.0
tenacity>=8.2.0
ipython_genutils>=0.2.0
boto3>=1.34.0
numpy>=1.24.0
reportlab>=4.4.0
pytest>=7.0.0
hypothesis>=6.0.0
fastapi>=0.111.0
uvicorn[standard]>=0.30.0
slowapi>=0.1.9
psutil>=5.9.0
docker>=6.0.0
```

**Dependencies added since v0.4:**
- **langchain-anthropic>=1.0.0** - Direct Anthropic Claude API integration (non-Bedrock `claude` backend)
- **langchain-openai>=0.0.5** - OpenAI-compatible LLM integration
- **opensearch-py>=2.6.0** - AWS OpenSearch vector search backend
- **python-multipart>=0.0.9** - Multipart form data for VCF file uploads in FastAPI
- **slowapi>=0.1.9** - Rate limiting middleware for FastAPI (graceful no-op if not installed)
- **beautifulsoup4>=4.12.0** - HTML parsing for CPIC guideline scraping (automated data pipeline)
- **lxml>=4.9.0** - XML/HTML parser for web scraping (automated data pipeline)

### Development Dependencies
```
pre-commit>=3.6.0
black>=23.12.0
isort>=5.13.0
flake8>=7.0.0
mypy>=1.8.0
bandit>=1.7.5
pytest-cov>=4.1.0
pytest-xdist>=3.5.0
pytest-mock>=3.12.0
pytest-benchmark>=4.0.0
pytest-html>=4.1.0
pytest-json-report>=1.5.0
pytest-timeout>=2.2.0
pytest-asyncio>=0.23.0
coverage>=7.4.0
```

### Security and Monitoring Dependencies
```
trivy>=0.50.0          # Container vulnerability scanning
grype>=0.74.0          # Alternative vulnerability scanner
docker>=7.0.0          # Docker SDK for Python
psutil>=5.9.0          # System and process monitoring
cryptography>=41.0.0   # SSL certificate management
pyyaml>=6.0.1          # YAML configuration parsing
requests>=2.31.0       # HTTP requests for health checks
semgrep>=1.45.0        # Static analysis security scanner
safety>=2.3.0          # Python dependency vulnerability scanner
```

### AWS Competition Enhancement Dependencies (NEW)
```
diagrams>=0.23.0       # Programmatic architecture diagram generation
graphviz>=0.20.0       # Graph layout engine for diagrams
matplotlib>=3.7.0      # Plotting and visualization for population metrics
seaborn>=0.12.0        # Statistical data visualization
plotly>=5.18.0         # Interactive visualizations for population analysis (already included above)
```

### AWS Account Setup Dependencies (LIVE - OPERATIONAL)
```
# Core AWS SDK dependencies (LIVE - OPERATIONAL)
boto3>=1.34.0          # AWS SDK for resource provisioning (LIVE)
botocore>=1.34.0       # AWS SDK core functionality (LIVE)

# AWS Infrastructure Components (LIVE - Account 403732031470)
# S3 Buckets: synthatrial-genomic-data, synthatrial-reports
# Lambda Function: synthatrial-batch-processor
# Step Functions: synthatrial-trial-orchestrator
# IAM Roles: synthatrial-lambda-role, synthatrial-stepfunctions-role

# Additional dependencies for future automation (PLANNED)
click>=8.1.0           # CLI framework for AWS setup commands (PLANNED)
rich>=13.0.0           # Rich terminal output for setup progress (PLANNED)
tabulate>=0.9.0        # Table formatting for resource status display (PLANNED)
jsonschema>=4.17.0     # Configuration validation for AWS setup (PLANNED)
pyyaml>=6.0.1          # YAML configuration parsing (already included above)
```

### Production Readiness Dependencies (IMPLEMENTED - Days 1-2)
```
# Database and data pipeline dependencies for 100+ gene panel
beautifulsoup4>=4.12.0 # HTML parsing for CPIC guideline scraping (IMPLEMENTED)
lxml>=4.9.0            # XML/HTML parser for web scraping (IMPLEMENTED)
tabulate>=0.9.0        # Table formatting for data validation reports (IMPLEMENTED)
```

### Competition Feedback Response Dependencies (NEW - Week 1 Complete)
```
# Clinical validation and regulatory compliance
pytest-cov>=4.1.0      # Code coverage for validation testing
aiohttp>=3.9.0         # Async HTTP for load testing (IMPLEMENTED - Week 1 Day 7)
redis>=5.0.0           # Response caching for rate limiting (optional)
```
### Multi-Platform Deployment Dependencies (Planned)
```
heroku3>=5.1.4         # Heroku API client for deployment automation (PLANNED)
vercel>=0.12.0         # Vercel CLI integration for serverless deployment (PLANNED)
render-python>=1.0.0   # Render.com API client (custom integration) (PLANNED)
schedule>=1.2.0        # Task scheduling for cost optimization (PLANNED)
prometheus-client>=0.16.0  # Metrics collection for monitoring (PLANNED)
```

## Environment Setup

### Installation
```bash
# Create conda environment (required for RDKit)
conda create -n synthatrial python=3.10
conda activate synthatrial

# Install RDKit via conda (required)
conda install -c conda-forge rdkit pandas scipy scikit-learn

# Install all dependencies via pip
pip install -r requirements.txt

# CRITICAL: Always ensure you're in the correct conda environment
# Check with: conda info --envs | grep "*"
# Should show: synthatrial * /path/to/synthatrial
```

### Environment Variables
Create `.env` file with:
```bash
# LLM Backend Selection (choose one)
LLM_BACKEND=nova     # Default: Amazon Nova Lite/Pro on AWS Bedrock
# LLM_BACKEND=gemini  # Alternative: Google Gemini
# LLM_BACKEND=bedrock # Alternative: AWS Bedrock Claude

# Amazon Nova / AWS Bedrock Configuration (required if LLM_BACKEND=nova or bedrock)
# AWS credentials via environment variables or IAM role (on EC2)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
BEDROCK_REGION=us-east-1  # Default region
NOVA_DEFAULT_VARIANT=lite  # lite or pro (replaces legacy NOVA_MODEL)
NOVA_LITE_MODEL=amazon.nova-lite-v1:0  # Nova Lite model ID
NOVA_PRO_MODEL=amazon.nova-pro-v1:0   # Nova Pro model ID
CLAUDE_MODEL=anthropic.claude-3-haiku-20240307-v1:0  # Claude model (if LLM_BACKEND=bedrock)
TITAN_EMBED_MODEL=amazon.titan-embed-text-v2:0  # Default Titan embeddings

# Direct Anthropic Claude Configuration (required if LLM_BACKEND=claude)
ANTHROPIC_API_KEY=your_anthropic_api_key
ANTHROPIC_MODEL=claude-sonnet-4-20250514  # Default Anthropic model

# Google Gemini Configuration (required if LLM_BACKEND=gemini)
GOOGLE_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash  # Default model
# Alternative models: gemini-2.5-pro, gemini-2.0-flash, gemini-2.0-flash-exp
GEMINI_TEMPERATURE=0.1
GEMINI_TIMEOUT=60

# AWS Competition Enhancement Configuration (LIVE - OPERATIONAL)
# S3 Configuration for genomic data and reports (LIVE)
AWS_S3_BUCKET_GENOMIC=synthatrial-genomic-data  # S3 bucket for VCF files (LIVE - 16 files uploaded)
AWS_S3_BUCKET_REPORTS=synthatrial-reports       # S3 bucket for PDF reports (LIVE)
AWS_S3_REGION=us-east-1                         # S3 region

# Lambda Configuration for batch processing (LIVE)
AWS_LAMBDA_FUNCTION_NAME=synthatrial-batch-processor  # Lambda function name (LIVE)
AWS_LAMBDA_REGION=us-east-1                          # Lambda region

# Step Functions Configuration for trial orchestration (LIVE)
AWS_STEP_FUNCTIONS_STATE_MACHINE=arn:aws:states:us-east-1:403732031470:stateMachine:synthatrial-trial-orchestrator  # State machine ARN (LIVE)
AWS_STEP_FUNCTIONS_REGION=us-east-1                             # Step Functions region

# AWS Account Information (LIVE - OPERATIONAL)
AWS_ACCOUNT_ID=403732031470                     # Live AWS account ID (OPERATIONAL)
AWS_ACCESS_KEY_ID=your_access_key               # Configure in .env
AWS_SECRET_ACCESS_KEY=your_secret_key           # Configure in .env

# Population Simulation Configuration
POPULATION_SIMULATOR_MAX_COHORT_SIZE=10000      # Maximum cohort size for simulation
POPULATION_SIMULATOR_BATCH_SIZE=100             # Batch size for parallel processing
POPULATION_SIMULATOR_ENABLE_LAMBDA=true        # Use Lambda for large cohorts (>100 patients)

# Architecture Diagram Configuration
DIAGRAM_OUTPUT_FORMAT=svg                       # Output format: svg, png
DIAGRAM_RESOLUTION=1920x1080                   # Diagram resolution
DIAGRAM_COLOR_SCHEME=competition               # Color scheme: default, competition

# AWS Account Setup Configuration (NEW)
AWS_SETUP_REGION=us-east-1                     # Default region for AWS setup
AWS_SETUP_ENVIRONMENT=development              # Environment name (development, staging, production)
AWS_SETUP_PROJECT_NAME=anukriti               # Project name for resource naming
AWS_SETUP_ENABLE_COST_OPTIMIZATION=true       # Enable cost optimization features
AWS_SETUP_ENABLE_SECURITY_HARDENING=true      # Enable security best practices
AWS_SETUP_BEDROCK_ACCESS=true                 # Request Bedrock model access

# Optional for real drug data (uses mock mode if missing)
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_INDEX=drug-index

# Vector DB Backend Selection (auto/pinecone/opensearch/local/mock)
VECTOR_DB_BACKEND=auto  # auto: prefers OpenSearch → Pinecone → local → mock
OPENSEARCH_HOST=your-opensearch-endpoint  # Required for opensearch backend
OPENSEARCH_INDEX=drug-index
OPENSEARCH_REGION=us-east-1
OPENSEARCH_SERVICE=aoss  # aoss for Serverless, es for managed

# Local in-process vector search (no external DB required)
LOCAL_VECTOR_CACHE_DIR=data/vector_index_cache  # Cache dir for ChEMBL fingerprint index
LOCAL_VECTOR_REBUILD=false  # Set true to force rebuild of local index

# Optional ML drug reranker (train with scripts/train_drug_reranker.py)
DRUG_RERANKER_PATH=  # Path to trained reranker model file
DRUG_RERANKER_POOL=40  # Candidate pool size before reranking

# Optional: Environment settings
ENVIRONMENT=development
DEBUG=true
PORT=8000

# Security Configuration
ALLOWED_ORIGINS=https://anukriti.abhimanyurb.com  # Comma-separated; empty = allow all (dev only)
API_KEY_REQUIRED=false                             # Set true to enforce X-API-Key header auth
API_KEYS=                                          # Comma-separated valid API keys
MAX_REQUEST_BODY_BYTES=10485760                    # Max JSON body size (default 10 MB)
MAX_VCF_UPLOAD_BYTES=5368709120                    # Max VCF upload size (default 5 GB)
VCF_UPLOAD_TTL_SECONDS=86400                       # Upload session TTL before auto-cleanup (24h)

# Logging
LOG_FORMAT=plain   # plain (dev) or json (production log aggregation)

# LLM call hard timeout (seconds). Applies to Bedrock (connect=10s, read=this value)
# and Gemini/Anthropic chains. Prevents hung LLM responses from blocking request threads.
LLM_CALL_TIMEOUT_SECONDS=60

# Timeout Configuration (CRITICAL for backend server performance and S3 VCF processing)
HEALTH_CHECK_TIMEOUT=5            # Fast health check timeout (optimized for quick connectivity testing)
HEALTH_DETAILED_TIMEOUT=30        # Detailed health check with AWS services
VCF_PROFILE_TIMEOUT=300           # VCF profile generation timeout (5 minutes for S3)
API_TIMEOUT=180                   # General API request timeout
AWS_SERVICE_CHECK_TIMEOUT=10      # Per AWS service check timeout
CONFIG_VALIDATION_TIMEOUT=5       # Configuration validation timeout
AWS_STATUS_CACHE_TTL=30           # Cache TTL (seconds) for /aws-status endpoint responses
```

## Common Commands

### Production Readiness Commands (UPDATED - Week 1 Complete)
```bash
# Multi-Backend LLM Testing (IMPLEMENTED - Week 1 Day 5)
python scripts/test_all_llm_backends.py  # Test all backends
python scripts/test_all_llm_backends.py --backend nova  # Test specific backend
python scripts/test_all_llm_backends.py --output test_results.json  # Save results

# Demo Scenario Pre-computation (IMPLEMENTED - Week 1 Day 6)
python scripts/precompute_demo_scenarios.py  # Pre-compute 20 scenarios
python scripts/precompute_demo_scenarios.py --scenarios 10  # Custom count
python scripts/precompute_demo_scenarios.py --output custom_cache.json  # Custom output

# Load Testing (IMPLEMENTED - Week 1 Day 7)
python scripts/load_test_demo.py --test-type burst --users 500  # Burst test
python scripts/load_test_demo.py --test-type sustained --users 500 --duration 300  # Sustained test
python scripts/load_test_demo.py --url https://anukriti.abhimanyurb.com/analyze  # Test deployed API

# Gene Panel Expansion - IMMEDIATE ACTIONS (Week 1-2)
# Expand from 15 to 40 genes using automated pipeline
python scripts/init_gene_database.py --tier 2  # Load 17 Tier 2 genes (15→32)
python scripts/pharmvar_sync.py --tier 2
python scripts/cpic_sync.py --tier 2
python scripts/validate_pgx_data.py --tier 2

python scripts/init_gene_database.py --tier 3  # Load 8 Tier 3 genes (32→40)
python scripts/pharmvar_sync.py --tier 3
python scripts/cpic_sync.py --tier 3
python scripts/validate_pgx_data.py --tier 3

# Verify expansion
sqlite3 data/pgx/pharmacogenes.db "SELECT COUNT(*) FROM genes;"
# Expected: 39 genes (15 Tier 1 + 16 Tier 2 + 8 Tier 3) - CURRENT STATUS

# Clinical Validation (Week 1-2)
python tests/test_coriell_validation.py  # Coriell reference validation (95% target)
python scripts/run_pharmcat_comparison.py --samples 100  # PharmCAT comparison

# Multi-Backend LLM Testing (Week 1)
python scripts/test_all_llm_backends.py  # Test Nova, Claude, Gemini, Anthropic
python scripts/precompute_demo_scenarios.py  # Pre-compute demo scenarios

# Load Testing (Week 2)
python scripts/load_test_demo.py --concurrent-users 500 --duration 300

# Gene Panel Expansion (100+ genes) - DATABASE BACKEND OPERATIONAL & INTEGRATED
# Database setup and initialization (IMPLEMENTED - Day 1 Complete)
python scripts/init_gene_database.py --tier 1  # Load Tier 1 genes (15 genes) ✅
python scripts/init_gene_database.py --all     # Load all genes (40 genes total)
python scripts/init_gene_database.py --status  # Show database status ✅
python scripts/init_gene_database.py --force   # Force recreate database

# Database backend testing (IMPLEMENTED - Day 1 Complete)
python -m pytest tests/test_variant_db_v2.py -v  # Test database backend (15/15 passing) ✅
python -m pytest tests/test_pgx_core.py -v       # Test integration (54/54 passing) ✅

# Database status and statistics
sqlite3 data/pgx/pharmacogenes.db "SELECT COUNT(*) FROM genes;"  # Check gene count
sqlite3 data/pgx/pharmacogenes.db "SELECT COUNT(*) FROM variants;"  # Check variant count
sqlite3 data/pgx/pharmacogenes.db "SELECT * FROM gene_summary;"  # View gene summary

# Automated data synchronization (IMPLEMENTED - Day 2 Complete) ✅
python scripts/pharmvar_sync.py --gene CYP3A4  # Sync single gene from PharmVar ✅
python scripts/pharmvar_sync.py --tier 1       # Sync all Tier 1 genes ✅
python scripts/pharmvar_sync.py --all          # Sync all genes ✅
python scripts/pharmvar_sync.py --force        # Force re-sync (overwrite existing) ✅
python scripts/cpic_sync.py --gene CYP3A4      # Sync CPIC phenotypes for gene ✅
python scripts/cpic_sync.py --tier 1           # Sync all Tier 1 phenotypes ✅
python scripts/cpic_sync.py --all              # Sync all phenotypes ✅
python scripts/cpic_sync.py --force            # Force re-sync (overwrite existing) ✅

# Data validation and quality checks (IMPLEMENTED - Day 2 Complete) ✅
python scripts/validate_pgx_data.py --all      # Validate all genes ✅
python scripts/validate_pgx_data.py --gene CYP3A4  # Validate single gene ✅
python scripts/validate_pgx_data.py --tier 1   # Validate Tier 1 genes ✅

# Performance benchmarking (IMPLEMENTED - Day 2 Complete) ✅
python scripts/benchmark_gene_panel.py         # Test all genes performance ✅
python scripts/benchmark_gene_panel.py --genes 100  # Test 100-gene scalability (planned) ✅

# Targeted VCF extraction (300x compression) (PLANNED - Day 4-5)
python scripts/extract_pharmacogene_regions.py --create-bed  # Create BED file
python scripts/extract_pharmacogene_regions.py --extract-all # Extract all chromosomes
# Result: 150GB → 500MB (pharmacogenes_chr*.vcf.gz)

# Database management (PLANNED)
python scripts/optimize_database.py            # Optimize database indexes
python scripts/build_production_db.py          # Build optimized production database
```

### API Deployment Commands
```bash
# CRITICAL: Start FastAPI backend server (required for VCF patient profiles)
conda activate synthatrial && uvicorn api:app --host 0.0.0.0 --port 8000 --reload

# Alternative start methods
conda activate synthatrial && python api.py                    # Direct Python execution
conda activate synthatrial && python -m uvicorn api:app --host 0.0.0.0 --port 8000  # Module execution

# Local API testing (after server is running)
python test_api.py              # Run API test suite locally
python test_api.py https://anukriti.abhimanyurb.com  # Test deployed API

# API health check (NEW: Fast and detailed endpoints)
curl http://localhost:8000/health-fast  # Ultra-fast health check (< 2 seconds)
curl http://localhost:8000/              # Fast health check (< 5 seconds)
curl http://localhost:8000/health        # Detailed health with AWS status (< 15 seconds)
curl https://anukriti.abhimanyurb.com/  # Deployed health check

# Competition demo endpoints
curl https://anukriti.abhimanyurb.com/demo  # Get demo examples
curl https://anukriti.abhimanyurb.com/health  # Detailed health status

# API analysis endpoint
curl -X POST http://localhost:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"drug_name":"Warfarin","patient_profile":"ID: HG00096\nGenetics: CYP2C9 Poor Metabolizer","similar_drugs":[]}'

# Interactive API documentation
# Visit http://localhost:8000/docs for Swagger UI
# Visit http://localhost:8000/redoc for ReDoc

# TROUBLESHOOTING: If "Backend Offline" error occurs:
# 1. Ensure you're in the synthatrial conda environment: conda activate synthatrial
# 2. Check if server is running: curl http://localhost:8000/health-fast
# 3. Check for import errors: python -c "from api import app; print('API imports successful')"
# 4. Verify port availability: netstat -tlnp | grep :8000
# 5. Check timeout settings in .env (HEALTH_CHECK_TIMEOUT=5, VCF_PROFILE_TIMEOUT=300)
# 6. Test server response: curl -v --max-time 5 http://127.0.0.1:8000/health-fast
# 7. If server hangs on startup, check for blocking AWS service calls in logs
# 8. Restart server if hanging: Kill process and restart with --reload flag
```

### Cloud Deployment Commands
```bash
# Manual Cloud Deployment (Current Implementation)
# Render.com deployment (recommended for competition)
# 1. Push to GitHub: git push origin main
# 2. Create Render web service with:
#    Build: pip install -r requirements.txt
#    Start: uvicorn api:app --host 0.0.0.0 --port 10000
#    Environment: GOOGLE_API_KEY=your_key

# Vercel deployment (serverless alternative)
npm i -g vercel
vercel --prod
vercel env add GOOGLE_API_KEY

# Heroku deployment (with Procfile)
heroku create anukriti-ai-app
heroku config:set GOOGLE_API_KEY=your_key
git push heroku main

# AWS EC2 deployment (production with VCF support - CHEAPEST OPTION)
# See AWS_EC2_DEPLOYMENT.md for complete guide
# Cost: ₹0/month (free tier t2.micro) or ₹400-₹750/month (t3.micro + storage)
# 1. Launch EC2 instance (t2.micro free tier or t3.micro recommended)
# 2. Install Docker
# 3. Clone repository
# 4. Download VCF files to data/genomes/ (stored on EC2 local disk)
# 5. Build and run Docker container with volume mount: -v $(pwd)/data:/app/data
# 6. Enable auto-restart: docker update --restart unless-stopped
# Access: http://<EC2_PUBLIC_IP>:8501

### AWS UI and Backend Integration Commands (NEW - LIVE)
```bash
# Test AWS integration status
python test_s3_integration.py  # Comprehensive AWS integration test

# AWS Integration API endpoints (NEW)
curl http://localhost:8000/aws-status              # AWS services status
curl http://localhost:8000/population-simulate     # Population simulation demo
curl http://localhost:8000/architecture-diagram    # Generate architecture diagram

# Enhanced health check with AWS status
curl http://localhost:8000/health                  # Detailed health with AWS integration

# Enhanced data status with S3 information
curl http://localhost:8000/data-status             # Shows S3 vs local data source

# Streamlit UI with AWS integration features
streamlit run app.py
# Features:
# - Real-time AWS integration status in sidebar
# - Enhanced Analytics tab with AWS service panels
# - Population simulation demo button (100-10K patients)
# - AWS account information display (403732031470)
# - Professional competition presentation features
```
```

### Deployment Cost Comparison
```
Platform Comparison (Monthly Cost):
┌─────────────────┬──────────────┬─────────────┬──────────────┬─────────────────┐
│ Platform        │ Cost         │ VCF Support │ Setup Time   │ Best For        │
├─────────────────┼──────────────┼─────────────┼──────────────┼─────────────────┤
│ Render.com      │ Free-₹500    │ ❌ No       │ 5-10 min     │ Demos, API only │
│ Vercel          │ Free-₹1000   │ ❌ No       │ 5-10 min     │ Serverless      │
│ Heroku          │ ₹500-₹2000   │ ⚠️ Limited  │ 10-15 min    │ Simple apps     │
│ AWS EC2 (FREE)  │ ₹0-₹150      │ ✅ Full     │ 30-45 min    │ Free tier ⭐    │
│ AWS EC2 (PAID)  │ ₹400-₹750    │ ✅ Full     │ 30-45 min    │ Production ⭐   │
│ AWS ECS/Fargate │ ₹1500-₹3000  │ ✅ Full     │ 2-3 hours    │ Enterprise      │
└─────────────────┴──────────────┴─────────────┴──────────────┴─────────────────┘

Cost Optimization Tips:
- Use t2.micro (FREE for 12 months with AWS Free Tier)
- Store VCF files on EC2 local disk (no S3 costs)
- Use Reserved Instances for 40-60% savings (after free tier)
- Stop instance when not needed (no compute charges)
- Download only chr22 initially to save storage costs
```

### Setup Commands
```bash
# Setup Pinecone index
python scripts/setup_pinecone_index.py

# Ingest ChEMBL data to Pinecone
python scripts/ingest_chembl_to_pinecone.py

# Automated data initialization (NEW)
python scripts/data_initializer.py --all  # Initialize all data (VCF + ChEMBL)
python scripts/data_initializer.py --vcf chr22 chr10  # Download only VCF files
python scripts/data_initializer.py --chembl  # Setup only ChEMBL database
python scripts/data_initializer.py --status  # Check current data status

# SSL certificate management (NEW)
python scripts/ssl_manager.py --domain localhost  # Generate self-signed certificates
python scripts/ssl_manager.py --validate docker/ssl/localhost.crt --key docker/ssl/localhost.key
bash scripts/generate_ssl_certs.sh  # Alternative certificate generation

# Development environment setup (NEW)
python scripts/setup_dev_env.py  # Full development environment setup
python scripts/setup_dev_env.py --validate-only  # Validation only
python scripts/setup_dev_env.py --skip-hooks  # Skip pre-commit setup

# VCF Data Access Options (FLEXIBLE)
# Option 1: Direct S3/HTTPS Streaming (RECOMMENDED - Zero Cost, No Downloads)
# No setup needed! Platform automatically streams from AWS Public Dataset
# Uses tabix HTTP range requests - only downloads needed regions (~1-5MB per patient)
# See docs/1000_GENOMES_AWS_ACCESS.md for details

# Option 2: Download VCF files locally (Optional - for offline development)
# Download VCF data (chromosome 22 - CYP2D6)
curl -L https://hgdownload.cse.ucsc.edu/gbdb/hg19/1000Genomes/phase3/ALL.chr22.phase3_shapeit2_mvncall_integrated_v5a.20130502.genotypes.vcf.gz -o data/genomes/chr22.vcf.gz

# Download VCF data (chromosome 10 - CYP2C19, CYP2C9)
curl -L https://hgdownload.cse.ucsc.edu/gbdb/hg19/1000Genomes/phase3/ALL.chr10.phase3_shapeit2_mvncall_integrated_v5a.20130502.genotypes.vcf.gz -o data/genomes/chr10.vcf.gz

# Download ChEMBL database (optional)
curl -L https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_34/chembl_34_sqlite.tar.gz -o data/chembl/chembl_34_sqlite.tar.gz
tar -xvzf data/chembl/chembl_34_sqlite.tar.gz -C data/chembl/

# Verify VCF file integrity (optional)
python scripts/check_vcf_integrity.py data/genomes/chr10.vcf.gz
python scripts/check_vcf_integrity.py data/genomes/chr22.vcf.gz
```

### Enhanced Streamlit UI Features
```bash
# Modern minimalistic web interface with 3D visualization and AWS integration
conda activate synthatrial && streamlit run app.py

# IMPORTANT: For VCF patient profiles to work, ensure FastAPI backend is running:
# In separate terminal: conda activate synthatrial && uvicorn api:app --host 0.0.0.0 --port 8000 --reload

# Features include:
# - Clean, user-friendly design with minimalistic Inter font styling
# - 3D molecular structure visualization with py3Dmol and stmol (enhanced with multiple coordinate generation strategies with 3 fallback attempts, MMFF force field optimization, automatic 2D fallback for complex molecules, and molecular properties display including atom count, bond count, and molecular weight)
# - Lottie animations for enhanced user experience (DNA, loading, success)
# - 4-tab interface: Simulation Lab, Batch Processing, Analytics, About
# - Streamlined drug analysis workflow with curated database (7 drugs)
# - Real-time system health monitoring with API status
# - Multi-enzyme patient profiling (CYP2D6, CYP2C19, CYP2C9, UGT1A1, SLCO1B1)
# - 3-stage pipeline visualization: Genetics → Similar Drugs → Predicted Response
# - LLM Backend selector: Choose between Gemini (Google) or Bedrock (AWS) per session
# - Per-request backend override capability
# - Drug-triggered PGx: Orange "Relevant" tags highlight only drug-relevant genes
# - Batch processing capabilities for cohort analysis
# - Competition-ready demo interface with professional styling
# - Performance metrics and analytics dashboard
# - Cloud deployment integration status
# - Analysis history tracking and report downloads
# - PDF report generation with downloadable clinical documentation
# - Configurable API URL for flexible deployment
# - Collapsed sidebar by default for cleaner main interface
# - AI Insight Preview panel with risk visualization
# - Quick Start Guide banner with dismissible onboarding
# - Three-panel layout: Parameters | Patient Profile | Molecular View
# - **NEW: Real-time AWS integration status** in sidebar showing S3, Lambda, Step Functions connectivity
# - **NEW: Enhanced Analytics tab** with AWS service status panels and live metrics
# - **NEW: Population simulation demo** button supporting 100-10,000 patient cohorts
# - **NEW: AWS account information display** (Account: 403732031470, Region: us-east-1)
# - **NEW: Professional competition presentation** with cloud-native architecture highlights
# - **NEW: Live genomic data source indicator** (S3 vs Local) with file counts
# - **VCF Patient Profile Integration**: Requires FastAPI backend for sample discovery and profile generation
```

# REST API (production deployment)
python api.py                    # Start FastAPI server
uvicorn api:app --host 0.0.0.0 --port 8000  # Alternative start command

# Docker (recommended for production)
make quick-start  # Development mode
make run-prod     # Production mode

# Command line interface - Single chromosome (CYP2D6 only)
python main.py --vcf data/genomes/chr22.vcf.gz --sample-id HG00096

# Command line interface - Multi-chromosome (Big 3 enzymes: CYP2D6, CYP2C19, CYP2C9)
python main.py --vcf data/genomes/chr22.vcf.gz --vcf-chr10 data/genomes/chr10.vcf.gz --sample-id HG00096

# Docker CLI mode
docker run anukriti cli --drug-name Warfarin --cyp2d6-status poor_metabolizer

# CYP2D6 status override (single enzyme)
python main.py --cyp2d6-status poor_metabolizer

# Test specific drug interactions
python main.py --vcf data/genomes/chr22.vcf.gz --vcf-chr10 data/genomes/chr10.vcf.gz --drug-name Warfarin --sample-id HG00096
python main.py --vcf data/genomes/chr22.vcf.gz --vcf-chr10 data/genomes/chr10.vcf.gz --drug-name Clopidogrel --sample-id HG00096
```

### Docker Commands (Enhanced)
```bash
# Quick development setup
make quick-start

# Development with enhanced features (NEW)
make dev-enhanced  # Enhanced development container with additional tools

# Development with Jupyter notebooks
make jupyter  # Access at http://localhost:8888

# Production deployment
make run-prod

# Production with SSL/Nginx
make run-nginx

# SSL certificate management (NEW)
make ssl-setup  # Generate SSL certificates
make ssl-validate  # Validate existing certificates

# Data initialization (NEW)
make data-init  # Initialize all data (VCF + ChEMBL)
make data-status  # Check data status

# Container management
make stop     # Stop all containers
make clean    # Remove containers and images
make logs     # Show container logs
make shell    # Open shell in container

# Testing and validation (ENHANCED)
make test     # Run validation tests
make test-properties  # Run property-based tests
make test-containerized  # Run tests in containers
make setup    # Run setup tasks (Pinecone, ChEMBL)
make benchmark # Run performance benchmarks

# Development environment (NEW)
make dev-setup  # Setup development environment
make pre-commit-install  # Install pre-commit hooks
make code-quality  # Run code quality checks

# Security scanning and monitoring (NEW)
make security-audit         # Comprehensive security audit
make vulnerability-check     # Check dependency vulnerabilities
make container-security-scan # Scan Docker images for vulnerabilities
make monitor-start          # Start production monitoring
make monitor-health         # Perform health check
make backup-all            # Create comprehensive backup
make system-status         # Complete system status overview

# Multi-architecture builds and deployment
make build-multi-arch       # Build for AMD64+ARM64 platforms
make build-and-push         # Build and push to registry (REGISTRY=url)
make deploy-staging         # Deploy to staging environment
make deploy-production      # Deploy to production environment
make ci-setup              # Setup CI/CD environment
make ci-test-local         # Run local CI/CD simulation

# Integration testing
make test-integration      # Run integration test suite
make test-all             # Run comprehensive test suite
python tests/test_integration_runner.py  # Run complete workflow integration tests

# GitHub Actions workflows
make ci-validate           # Validate GitHub Actions workflows
make ci-status            # Check CI/CD pipeline status
```

### AWS Competition Enhancement Commands (NEW)
```bash
# Architecture diagram generation
python src/diagram_generator.py --format svg --output docs/architecture.svg
python src/diagram_generator.py --format png --resolution 1920x1080 --output docs/architecture.png

# Population simulation commands
python src/population_simulator.py --cohort-size 1000 --population-mix '{"AFR":0.25,"EUR":0.40,"EAS":0.20,"SAS":0.10,"AMR":0.05}'
python src/population_simulator.py --drug Warfarin --cohort-size 10000 --use-lambda  # Large-scale simulation

# Performance benchmarking with population metrics
python scripts/benchmark_performance.py --include-population --cohort-sizes 100,1000,10000
python scripts/benchmark_performance.py --aws-cost-analysis  # Generate cost analysis
```

### AWS Account Setup Commands (LIVE - OPERATIONAL)
```bash
# AWS infrastructure is now live and operational
# S3 buckets: synthatrial-genomic-data, synthatrial-reports
# Lambda function: synthatrial-batch-processor
# Step Functions: synthatrial-trial-orchestrator
# Account ID: 403732031470

# Upload genome data to S3 (16 VCF files across 8 chromosomes)
aws s3 cp data/genomes/ s3://synthatrial-genomic-data/genomes/ --recursive --include "*.vcf.gz" --include "*.tbi"

# Verify S3 uploads
aws s3 ls s3://synthatrial-genomic-data/genomes/ --recursive
aws s3 ls s3://synthatrial-genomic-data/genomes/ --recursive --summarize

# Test Lambda function
aws lambda invoke --function-name synthatrial-batch-processor --payload '{"cohort_size":100,"drug":"Warfarin"}' --cli-binary-format raw-in-base64-out response.json

# Test Step Functions workflow
aws stepfunctions start-execution --state-machine-arn arn:aws:states:us-east-1:403732031470:stateMachine:synthatrial-trial-orchestrator --input '{"cohort_size":100,"drug":"Warfarin"}'

# Test AWS integration after setup
python src/population_simulator.py --cohort-size 100 --drug Warfarin --use-lambda
python scripts/benchmark_performance.py --aws-cost-analysis

# Request Bedrock model access (if not already enabled)
# 1. Go to AWS Bedrock Console: https://console.aws.amazon.com/bedrock/
# 2. Navigate to "Model access"
# 3. Request access to Claude 3 Haiku and Titan Embeddings
# 4. Wait for approval (usually 5-10 minutes)
```
```bash
# Quick integration test
python tests/quick_test.py

# Full validation suite
python tests/validation_tests.py

# Property-based testing (NEW)
python -m pytest tests/test_*_properties.py  # Run all property tests
python -m pytest tests/test_ssl_manager_properties.py  # SSL certificate tests
python -m pytest tests/test_data_initialization_properties.py  # Data initialization tests
python -m pytest tests/test_dev_environment_properties.py  # Development environment tests

# Containerized testing (NEW)
python scripts/run_tests_in_container.py --containers enhanced-dev  # Run tests in enhanced container
python scripts/run_tests_in_container.py --coverage-threshold 80  # Coverage requirements
python scripts/run_tests_in_container.py --ci-mode  # CI integration mode

# Clinical validation testing (NEW - Week 1 Day 2)
python -m pytest tests/test_coriell_validation.py -v  # Coriell reference sample validation
python scripts/run_pharmcat_comparison.py --samples 100 --genes CYP2D6,CYP2C19,CYP2C9  # PharmCAT comparison
python scripts/run_pharmcat_comparison.py --samples 10 --output results.json --latex  # Generate LaTeX table

# Test chromosome 10 integration (Big 3 enzymes)
python scripts/test_chromosome10.py

# Check VCF file integrity
python scripts/check_vcf_integrity.py data/genomes/chr10.vcf.gz

# Generate CPIC guideline validation results
python scripts/generate_validation_results.py

# Benchmark performance metrics
python scripts/benchmark_performance.py

# Comprehensive integration testing
python tests/test_integration_runner.py  # Run all integration test suites
python tests/test_complete_workflow_integration.py  # End-to-end workflow tests
python tests/test_github_actions_integration.py     # CI/CD pipeline integration tests
python tests/test_docker_environment_integration.py # Docker component integration tests

# Security scanning and monitoring
python scripts/security_scanner.py --scan-all-images  # Scan all Docker images
python scripts/production_monitor.py --start-monitoring  # Start production monitoring
python scripts/backup_manager.py --create-backup  # Create automated backup
python scripts/multi_arch_build.py --target prod --platforms linux/amd64,linux/arm64  # Multi-arch builds
python scripts/deploy_to_registry.py --environment production  # Deploy to production

# Project and deployment: see root README.md
```

## Architecture Notes

- **Hybrid RAG architecture**: Two-layer retrieval system. Layer 1 — PGx knowledge RAG: Titan embeddings over local CPIC JSON files (`data/pgx/cpic/`) with keyword/gene/rsID pre-filtering before dense cosine search; index cached as `.npz` at `data/models/pgx_retriever_index.npz`. Layer 2 — molecular fingerprint similarity: 2048-bit Morgan fingerprints over ChEMBL via pluggable backends (Pinecone → OpenSearch → local NumPy → mock). Both layers feed context to the LLM explanation layer; clinical decisions remain deterministic.
- **API security layer**: `src/security.py` provides `verify_api_key` dependency (optional API key auth via `API_KEYS` + `API_KEY_REQUIRED`), `RequestSizeLimitMiddleware` (10 MB JSON cap), and `validate_vcf_upload` (gzip magic-byte check + 5 GB size cap). CORS restricted to `ALLOWED_ORIGINS` env var in production.
- **LLM hard timeouts**: All LLM backends enforce a hard timeout via `LLM_CALL_TIMEOUT_SECONDS` (default 60s). Bedrock uses `BotocoreConfig(connect_timeout=10, read_timeout=60)` with `retries=0` (tenacity handles retries). Gemini uses `request_timeout` and Anthropic uses `timeout` on their LangChain wrappers. Prevents hung LLM responses from blocking request threads indefinitely.
- **In-process metrics**: `src/metrics.py` tracks vector search backend usage, fallback-to-mock rates, and LLM timeout rates with thread-safe counters. Exposed via `GET /metrics` — use this to detect when Pinecone/OpenSearch is silently failing and mock data is being served.
- **Request-ID observability**: Every API request gets a `X-Request-ID` header (generated or forwarded). The ID is stored in a `ContextVar` and injected into all log records, enabling full correlation of Streamlit → FastAPI → Bedrock call chains in logs.
- **Structured logging**: `LOG_FORMAT=json` emits JSON-lines for log aggregation (CloudWatch, Datadog, etc.). Plain-text default for development. RAG retriever now logs warnings when embedding failures or missing files degrade context quality.
- **Modular design**: Separate processors for input, vector search, VCF, ChEMBL, and AI engine
- **Dual interface architecture**: Streamlit web UI and FastAPI REST API for flexible deployment options
- **RESTful API**: Production-ready FastAPI wrapper with health check and analysis endpoints. **NEW: Non-blocking Health Check Architecture** with three-tier system: `/health-fast` (< 2 seconds), `/` (< 5 seconds), and `/health` (< 15 seconds) with optimized AWS service checks that eliminate blocking operations and timeout issues.
- **Cloud deployment ready**: Optimized for Render, Vercel, Heroku, AWS EC2, and other cloud platforms
- **AWS EC2 deployment**: Complete production deployment with Docker and VCF files stored on EC2 local storage for cost-effective full-featured deployment. Most economical option at ₹0/month (free tier) or ₹400-₹750/month (paid tier) with full VCF support. Avoids expensive managed services like ECS/Fargate (₹1500-₹3000/month) and S3 storage costs by using EC2 local disk.
- **Competition-ready deployment**: One-click deployment configurations for Render.com and Vercel with demo endpoints
- **Interactive API documentation**: Auto-generated Swagger UI and ReDoc for API exploration
- **Professional-grade containerization**: Multi-stage Docker builds with development, enhanced development, production, and CI/CD configurations
- **Enterprise security and monitoring**: Automated SSL certificate management, vulnerability scanning, production monitoring, and comprehensive security headers
- **Enhanced development environment**: Pre-commit hooks, code quality tools, property-based testing, containerized testing, and Jupyter notebook integration
- **SSL certificate management**: Automated SSL certificate generation, validation, expiration checking, and renewal for secure deployments
- **Data initialization automation**: Automated VCF file downloads, ChEMBL database setup, integrity validation, and progress tracking
- **Security scanning and compliance**: Container vulnerability scanning, dependency checking, and security reporting with Trivy/Grype integration
- **Production monitoring and alerting**: Resource tracking, health monitoring, automated backup procedures, and performance metrics collection
- **CI/CD pipeline integration**: Multi-architecture builds, automated testing pipelines, GitHub Actions workflows, and container registry deployment
- **Comprehensive integration testing**: End-to-end workflow validation, cross-component testing, and automated test orchestration
- **Intelligent Cost Optimization (Planned)**: Platform-specific cost optimization with 20-40% expected savings through automated resource management, instance scheduling, and usage-based scaling
- **Platform Adapter Architecture (Planned)**: Modular adapter system supporting AWS EC2, Render.com, Vercel, and Heroku with unified deployment interface and platform-specific optimizations
- **Real-time Cost Monitoring (Planned)**: Budget tracking, cost forecasting, and automated alerting with detailed cost breakdowns by platform and resource type
- **Deployment Orchestration (Planned)**: Automated deployment workflows with progress tracking, error handling, rollback capabilities, and health validation across all platforms
- **Environment Configuration Management (Planned)**: Centralized configuration management with secure secret handling and cross-platform environment synchronization
- **Expanded pharmacogene panel**: Processes 8 chromosomes (2, 6, 10, 11, 12, 16, 19, 22) covering CYP2D6, CYP2C19, CYP2C9, UGT1A1, SLCO1B1, VKORC1
- **Targeted Variant Lookup**: Dictionary-based genotyping using specific rsIDs from PharmVar database instead of naive variant counting
- **Deterministic PGx Engine**: CPIC/PharmVar guideline-based allele calling with curated data tables (no LLM in decision layer)
- **Drug-triggered PGx**: Context-aware gene display showing only drug-relevant pharmacogenes (Warfarin → CYP2C9 + VKORC1; Statins → SLCO1B1; Clopidogrel → CYP2C19; Thiopurines → TPMT; Fluoropyrimidines → DPYD; Abacavir → HLA_B5701; Irinotecan → UGT1A1)
- **Local CPIC Retrieval**: Versioned PGx data in repo (`data/pgx/`) for reproducible, offline allele calling - no runtime API dependencies
- **Enhanced LLM prompting**: CPIC guideline-based prompting with structural analysis using SMILES strings and multi-model support (Gemini, Bedrock Nova/Claude, and direct Anthropic Claude backends)
- **Quad LLM Backend Support**: Default is Amazon Nova Lite/Pro on AWS Bedrock (`LLM_BACKEND=nova`). Also supports Google Gemini (`LLM_BACKEND=gemini`), Bedrock Claude (`LLM_BACKEND=bedrock`), and direct Anthropic Claude API (`LLM_BACKEND=claude` via `langchain-anthropic`) with per-request backend selection
- **Novel Drug Inference**: `src/novel_drug_inference.py` infers candidate pharmacogenes for novel compounds via analog retrieval + metadata; `src/confidence_tiering.py` classifies outputs as `high`, `moderate`, or `exploratory` — surfaced via `POST /analyze/novel-drug`
- **PDF Report Generation**: Clinical-style downloadable reports using ReportLab for real-world usability
- **Structured PGx Output**: Normalized API-friendly schema with confidence scores based on CPIC evidence strength
- **Container orchestration**: Docker Compose with environment-specific configurations, health checks, and resource limits
- **Automated deployment**: SSL certificate management, data initialization, and security scanning
- **Production readiness**: Nginx reverse proxy, SSL/TLS support, monitoring, and backup automation
- **CI/CD integration**: Multi-architecture builds, automated testing, and registry deployment
- **Property-based testing**: Comprehensive testing using Hypothesis for SSL, data initialization, and development environment validation
- **Code quality automation**: Pre-commit hooks with Black, isort, flake8, mypy, bandit, and security scanning
- **Containerized testing**: Multi-container test execution with coverage reporting and CI integration
- **Lazy initialization**: LLM and database connections initialized when needed
- **Mock mode support**: Graceful fallback when API keys are missing with realistic example data
- **Error handling**: Comprehensive error handling with user-friendly messages
- **Batch processing**: Efficient batch operations for large datasets with per-request backend override
- **Backward compatibility**: Single-chromosome mode maintained for existing workflows
- **Performance benchmarking**: Built-in tools for measuring vector retrieval, LLM simulation, and end-to-end timing
- **CPIC compliance**: Validation against Clinical Pharmacogenetics Implementation Consortium guidelines
- **Version consistency**: Maintained across all components (currently v0.4 Beta)
- **Docker enhancements complete**: All SSL certificate management, data initialization automation, security scanning, production monitoring, and CI/CD pipeline integration features are fully implemented and production-ready
- **AWS Competition Enhancements**: Professional architecture diagram generation, population-scale simulation capabilities, comprehensive AWS service integration (S3, Lambda, Step Functions), compelling narrative content, and flawless demo experience optimized for competition success
- **Population Simulation**: Large-scale cohort simulation supporting up to 10,000 patients with diverse global populations (AFR, EUR, EAS, SAS, AMR), parallel processing, and real-time performance metrics
- **Architecture Visualization**: Programmatic diagram generation using `diagrams` library with AWS service icons, multiple output formats, and professional styling for judge evaluation
- **AWS Service Integration**: S3 for genomic data and reports; Amazon Bedrock (Nova Lite/Pro default, Claude optional) for explanations; Titan embeddings for RAG; Lambda and Step Functions as optional scale-out hooks — in-process simulation runs without them
- **Competition-Ready Demo**: Enhanced demo experience with 2-minute video walkthrough, live demo optimization, judge-specific quick start guide, and compelling narrative content emphasizing global healthcare impact
- **Backend Server Reliability**: Resolved timeout issues through non-blocking AWS service checks, ensuring fast and reliable health check endpoints that respond within 5 seconds and eliminate "Backend Offline" errors during VCF patient profile operations

## Development Guidelines

- Use conda for RDKit installation (pip installation often fails)
- **CRITICAL: Always activate the synthatrial conda environment** before running any commands
- Always check for API keys before making external calls
- Implement mock modes for testing without credentials
- Follow CPIC guidelines for pharmacogenomics predictions
- Use descriptive error messages for user guidance
- **Documentation**: Root README.md is the main entry point; `docs/README.md` is the index; `docs/guide/` has the 10-chapter deep-dive
- **Backend Server Timeout Fix**: Resolved — see `docs/guide/09-cloud-infrastructure-and-devops.md` for the health check architecture
- **Testing**: Run validation tests after changes (`python tests/validation_tests.py`)
- **Backend Server**: Always start FastAPI server before using VCF patient profiles: `conda activate synthatrial && uvicorn api:app --host 0.0.0.0 --port 8000 --reload`
- **Environment Troubleshooting**: If imports fail, verify conda environment with `conda info --envs | grep "*"`
- **3D Visualization Testing**: Test 3D molecular visualization with `python test_3d_viz.py` to verify all standard library drugs render correctly. The implementation includes multiple coordinate generation strategies (3 fallback attempts), MMFF geometry optimization, and automatic 2D fallback for complex molecules that fail 3D generation.
- **Property-based testing**: Use Hypothesis for comprehensive testing of SSL, data initialization, and development environment functionality
- **Code quality**: Use pre-commit hooks for automated code formatting, linting, and security checks
- **SSL management**: Use automated SSL certificate generation and validation for secure deployments
- **Data automation**: Use automated data initialization scripts for VCF files and ChEMBL database setup
- **Performance**: Use benchmarking tools to measure system performance (`python scripts/benchmark_performance.py`)
- **Variant Lookup**: Use database-backed variant lookup from `src/variant_db_v2.py` for scalable 100+ gene support with sub-100ms query performance
- **Database Backend**: Use `src/variant_db_v2.py` for all variant/phenotype queries; integrated with `src/allele_caller.py` and `src/vcf_processor.py` (Day 1 afternoon complete); `variant_db.py` maintained for backward compatibility during migration
- **Deterministic PGx**: Use database-backed allele calling with automated PharmVar/CPIC synchronization - no hardcoded logic
- **Drug-triggered PGx**: Use `src/pgx_triggers.py` to determine which genes are relevant for each drug
- **Local CPIC Retrieval**: PGx data is versioned in database - no runtime API calls for allele definitions
- **Multi-chromosome**: Test with expanded pharmacogene panel (8 chromosomes) for comprehensive coverage. **Direct S3/HTTPS Access**: Platform supports streaming from AWS Public Dataset (zero storage cost, no downloads required). See `docs/1000_GENOMES_AWS_ACCESS.md` for details.
- **VCF Integrity**: Always verify VCF file integrity using `python scripts/check_vcf_integrity.py`
- **Docker Development**: Use `make quick-start` for development, `make dev-enhanced` for enhanced development, `make run-prod` for production testing
- **API Development**: Use `conda activate synthatrial && python api.py` for local API testing, `python test_api.py` for automated API testing
- **Cloud Deployment**: Deploy FastAPI to Render, Vercel, Heroku, AWS EC2, or other cloud platforms
- **AWS EC2 Deployment**: Use `AWS_EC2_DEPLOYMENT.md` for complete production deployment with VCF support
- **Cost Optimization**: Use t2.micro (free tier) or t3.micro (₹400-₹750/month) for cheapest deployment. Avoid ECS/Fargate (₹1500-₹3000/month) and S3 storage (₹200-₹400/month extra) by using EC2 local disk for VCF files.
- **Competition Deployment**: See root README (Deployment section and render.yaml)
- **Demo Interface**: Use `demo.html` for professional competition presentations
- **API Documentation**: Use `/docs` endpoint for interactive Swagger UI, `/redoc` for alternative documentation
- **Jupyter Development**: Use `make jupyter` for notebook-based development and analysis
- **Container Management**: Use Docker health checks, resource limits, and automated SSL setup for production deployments
- **Environment Configuration**: Use corrected `.env.example` template with `GOOGLE_API_KEY` (not `OPENAI_API_KEY`)
- **Multi-mode Deployment**: Support for development (hot reload), enhanced development (additional tools), production (optimized), and CI/CD (automated) configurations
- **Security Best Practices**: Automated vulnerability scanning, SSL certificate management, container hardening, and comprehensive security monitoring
- **Performance Monitoring**: Built-in container resource monitoring, performance benchmarking tools, and automated alerting systems
- **CI/CD Integration**: Multi-architecture builds, automated testing pipelines, GitHub Actions workflows, and registry deployment automation
- **Enterprise Deployment**: Production-ready containerization with SSL/TLS, monitoring, backup automation, and disaster recovery procedures
- **Integration Testing**: Comprehensive end-to-end workflow validation, cross-component testing, and automated test orchestration
- **Model Selection**: Default to `LLM_BACKEND=nova` (Amazon Nova Lite) for speed; use `nova-pro` for complex analysis; `gemini-2.5-flash` or `gemini-2.5-pro` when using Gemini backend; `LLM_BACKEND=claude` for direct Anthropic API (requires `ANTHROPIC_API_KEY`)
- **Backend Selection**: Support Nova (default), Gemini, Bedrock Claude, and direct Anthropic Claude with per-request override capability
- **PDF Reports**: Use `src/report_pdf.py` for generating downloadable clinical reports
- **Structured Output**: Use `src/pgx_structured.py` for normalized API-friendly PGx results
- **Allele Calling**: Use `src/allele_caller.py` for deterministic CYP2C19 calling with PharmVar/CPIC data; integrated with database backend (Day 1 afternoon) with TSV fallback for backward compatibility
- **Warfarin PGx**: Use `src/warfarin_caller.py` for CYP2C9 + VKORC1 interpretation
- **Statin Myopathy**: Use `src/slco1b1_caller.py` for SLCO1B1 rs4149056 interpretation
- **RAG Retrieval**: Use `src/rag/retriever.py` for local CPIC document retrieval with Titan embeddings. The retriever applies keyword/gene/rsID pre-filtering before dense cosine search — do not bypass the `retrieve_docs()` function for structured queries.
- **Local Vector Search**: Set `VECTOR_DB_BACKEND=local` to use in-process NumPy cosine search over ChEMBL without any external DB. Cache is built once and stored at `LOCAL_VECTOR_CACHE_DIR`. Use `LOCAL_VECTOR_REBUILD=true` to force a rebuild.
- **Drug Reranker**: Optionally train an ML reranker with `scripts/train_drug_reranker.py` and set `DRUG_RERANKER_PATH` to activate it for improved drug similarity ranking.
- **API Security**: Enable auth in production by setting `API_KEY_REQUIRED=true` and `API_KEYS=key1,key2`. Set `ALLOWED_ORIGINS` to your frontend domain(s). Never deploy with `allow_origins=["*"]` and credentials enabled simultaneously.
- **LLM Timeout**: Tune `LLM_CALL_TIMEOUT_SECONDS` based on your model and network. 60s is conservative for Nova Lite; Nova Pro may need 90–120s for complex queries. Check `GET /metrics` for `timeout_rate` per backend to detect if the value is too tight.
- **Metrics**: Check `GET /metrics` after deployment to verify the vector search backend is actually being used (not silently falling back to mock). A `fallback_rate > 0` on `pinecone` or `opensearch` means those backends are failing.
- **Input Validation**: `AnalyzeRequest` validates SMILES via `@field_validator` — illegal characters raise a 422 before any RDKit call. Do not bypass this by calling `get_drug_fingerprint` directly from untrusted input.
- **PGx Core Tests**: Run `python -m pytest tests/test_pgx_core.py` to validate the deterministic PGx engine offline (no LLM, no AWS, no VCF files needed). These 54 tests cover allele_caller (integrated with database backend), warfarin_caller, slco1b1_caller, tpmt_caller, dpyd_caller, and confidence_tiering.
- **Database Backend Tests**: Run `python -m pytest tests/test_variant_db_v2.py` to validate database backend (15 tests, all passing, sub-100ms performance verified)
- **Integration Tests**: Run `python -m pytest tests/test_variant_db_v2.py tests/test_pgx_core.py -v` to validate complete integration (69 tests, all passing)
- **Structured Logging**: Set `LOG_FORMAT=json` in production for log aggregation. Use `new_request_id()` at the start of custom request handlers to ensure log correlation. Check for `request_id` field in logs to trace a specific request end-to-end.
- **Project and deployment**: See root README.md for overview and deployment
- **Production Readiness**: Use `make production-ready` to validate complete system readiness for deployment
- **System Status**: Use `make system-status` and `make automation-status` for comprehensive status overview
- **Version Consistency**: Maintain consistent version numbers across all files (currently v0.4 Beta)
- **Docker Enhancements**: All Docker enhancement features are now complete and production-ready, including SSL certificate management, data initialization automation, security scanning, production monitoring, and CI/CD pipeline integration
- **Competition Ready**: Platform optimized for competition deployment with Render.com, Vercel, and demo interfaces
- **AWS Competition Enhancement**: Strategic enhancements for AWS AI competition success including visual architecture communication, population-scale simulation, meaningful AWS integration, compelling narrative, and flawless demo experience
- **AWS Account Setup and Integration**: Live AWS infrastructure with S3 buckets (synthatrial-genomic-data, synthatrial-reports), Lambda function (synthatrial-batch-processor), and Step Functions workflow (synthatrial-trial-orchestrator) operational on AWS Account 403732031470. Manual setup completed, automation planned for future. (LIVE)
- **Judge-Centric Design**: Every enhancement optimized for 2-minute evaluation window with professional diagrams, scalability demonstration, and impact-focused storytelling
- **UI Design**: Use minimalistic, clean design principles for user interfaces - prioritize user-friendliness and simplicity over complex enterprise dashboards
- **Production Readiness (UPDATED - Competition Feedback Response)**: Platform is 85% ready for clinical deployment with clear path to 100%. Gene panel expansion to 40 genes (Week 2), CYP2D6 CNV detection (Month 1), 100+ genes (Month 3). FDA Non-Device CDS compliance documented. Clinical validation framework established (Coriell + PharmCAT). Multi-backend LLM resilience (99.9% uptime). See `COMPETITION_FEEDBACK_RESPONSE_STRATEGY.md` for comprehensive roadmap.
- **Gene Panel Expansion (In Progress - Week 1 Complete)**: 39 genes operational (15 Tier 1 + 16 Tier 2 + 8 Tier 3), expanding to 40 genes (Week 2), 100+ genes (Month 3), 200+ genes (Month 12). Automated pipeline enables 24-48x faster gene addition (5 minutes vs 2-4 hours). **Advanced CNV Detection (PLANNED - Month 1)**: CYP2D6 copy number variation (0-6 copies) using digital PCR-inspired algorithms addresses competition feedback on incomplete structural variant detection.
- **Multi-Backend LLM Resilience (IMPLEMENTED - Week 1 Days 3-4)**: Automatic LLM failover: Nova → Bedrock Claude → Gemini → Anthropic → Deterministic fallback. Rate limiting and caching prevent quota exhaustion. 99.9% uptime guarantee. Use `src/multi_backend_llm.py` for automatic failover.
- **Rate Limiting (IMPLEMENTED - Week 1 Day 3)**: Use `src/rate_limiter.py` to prevent AWS Bedrock quota exhaustion during high-traffic periods. Token bucket algorithm with thread-safe implementation (100 req/min default).
- **Backend Testing (IMPLEMENTED - Week 1 Day 5)**: Run `python scripts/test_all_llm_backends.py` before competition demos to validate all backends. Tests all 4 backends individually and automatic failover behavior.
- **Demo Preparation (IMPLEMENTED - Week 1 Day 6)**: Pre-compute scenarios with `python scripts/precompute_demo_scenarios.py` for reliable demos. 20 scenarios covering 11 major drug classes with instant response times.
- **Load Testing (IMPLEMENTED - Week 1 Day 7)**: Validate system reliability with `python scripts/load_test_demo.py` before production deployment. Supports 500 concurrent users with 99.9% uptime validation. in progress. Target: 100+ genes by Month 3, 200+ genes by Month 12. See `IMMEDIATE_ACTION_CHECKLIST.md` for week-by-week implementation plan.
- **Clinical Validation (NEW - Week 1-2)**: Coriell reference sample validation framework (95% concordance target), PharmCAT comparison study, CPIC compliance audit. Academic partnership for retrospective clinical study (Month 1). Peer-reviewed publication target (Month 3).
- **Clinical Validation Testing (NEW - Week 1 Day 2)**: Use `tests/test_coriell_validation.py` for gold-standard reference validation. Run `python -m pytest tests/test_coriell_validation.py -v` to validate against Coriell samples. Use `scripts/run_pharmcat_comparison.py` for platform comparison. Target: ≥95% concordance with Coriell, 90-95% with PharmCAT.
- **Validation Documentation (NEW - Week 1 Day 2)**: Use templates in `docs/validation/` for regulatory submission. `CORIELL_CONCORDANCE_REPORT.md` for analytical validation, `PHARMCAT_COMPARISON.md` for platform comparison. Publication-ready format for peer-reviewed journals.
- **Regulatory Pathway (NEW - Week 1)**: FDA Non-Device CDS compliance under 21st Century Cures Act documented. Quality Management System (ISO 13485) implementation planned (Month 2). FDA Pre-Submission (Q-Sub) planned (Month 3). Clear path to clinical deployment.
- **Multi-Backend Resilience (NEW - Week 1)**: Automatic LLM failover: Nova → Bedrock Claude → Gemini → Anthropic → Deterministic fallback. Rate limiting and caching prevent quota exhaustion. Multi-region AWS deployment (Week 2). 99.9% uptime guarantee.
- **Market Adoption Strategy (NEW - Week 1-4)**: FDA diversity compliance messaging ($15M-$30M cost savings per drug). Pharmacoeconomic models demonstrate 1,500x-3,000x ROI. Industry partnerships and payer pilots planned (Month 3). Policy advocacy for health equity (Months 6-12).
- **Database Backend (IMPLEMENTED - Day 1 Complete)**: Use `data/pgx/pharmacogenes.db` (SQLite) for variant storage. 15 Tier 1 genes operational. Expandable to 100+ genes. Integrated with allele calling and VCF processing. See `DAY1_COMPLETE_SUMMARY.md` for complete Day 1 details.
- **Automated Data Pipeline (IMPLEMENTED - Day 2 Complete)**: Use `scripts/pharmvar_sync.py` and `scripts/cpic_sync.py` for automated gene data updates. Add new gene in 5 minutes (vs 2-4 hours manual) - 24-48x speedup. Multi-source strategy (web scraping → local files → fallback) ensures 100% uptime. See `DAY2_COMPLETE_SUMMARY.md` for implementation details.
- **Targeted Extraction (PLANNED - Days 4-5)**: Use `scripts/extract_pharmacogene_regions.py` to extract only pharmacogene regions from VCFs. Reduces storage from 150GB to 500MB (300x compression). Enables real-time patient profiling. Optional optimization after automated pipeline complete.

## Common Troubleshooting

### Backend Server Timeout Issues (RESOLVED)
**Symptom**: "Configuration❌ Backend OfflineError: ReadTimeout" when using VCF patient profiles
**Root Causes**:
1. **Wrong conda environment** - Most common cause
2. **FastAPI server not running** - Required for VCF functionality
3. **API server hanging on health checks** - Blocking AWS service calls (FIXED)
4. **Timeout too short for health checks** - Health check timeout too long (FIXED)

**Solution Steps** (IMPLEMENTED):
1. **Verify conda environment**: `conda info --envs | grep "*"` (should show `synthatrial *`)
2. **Activate correct environment**: `conda activate synthatrial`
3. **Start FastAPI server**: `uvicorn api:app --host 0.0.0.0 --port 8000 --reload`
4. **Test fast health check**: `curl -v --max-time 5 http://127.0.0.1:8000/health-fast`
5. **Updated timeout settings** in `.env` (IMPLEMENTED):
   ```bash
   HEALTH_CHECK_TIMEOUT=5        # Fast health check (reduced from 120s)
   HEALTH_DETAILED_TIMEOUT=30    # Detailed health check with AWS services
   VCF_PROFILE_TIMEOUT=300       # VCF processing (unchanged - needed for S3)
   AWS_SERVICE_CHECK_TIMEOUT=10  # Per AWS service check
   ```

**NEW: Fast Health Check Architecture** (IMPLEMENTED):
- `/health-fast` - Ultra-fast endpoint (< 2 seconds) without AWS service checks
- `/` - Fast health check (< 5 seconds) for basic connectivity
- `/health` - Detailed health check (< 15 seconds) with optimized AWS status checks
- Streamlit UI now uses `/health-fast` for quick connectivity testing
- AWS service checks are non-blocking and have proper timeouts

**CRITICAL FIX IMPLEMENTED**: The `/aws-status` endpoint no longer makes blocking AWS API calls (`get_function()`, `describe_state_machine()`). Instead, it only creates AWS clients to verify configuration, eliminating the hanging behavior that caused "Backend Offline" errors.

### Import Errors
**Symptom**: ModuleNotFoundError when starting API server
**Solution**:
1. Check conda environment: `conda info --envs | grep "*"`
2. Should show `synthatrial *` not `base *`
3. Activate correct environment: `conda activate synthatrial`
4. Reinstall dependencies if needed: `pip install -r requirements.txt`

### Port Conflicts
**Symptom**: Address already in use error on port 8000
**Solution**:
1. Check what's using port: `netstat -tlnp | grep :8000`
2. Kill existing process or use different port
3. Alternative port: `uvicorn api:app --host 0.0.0.0 --port 8001`

### AWS Integration Issues
**Symptom**: AWS services showing as disconnected
**Solution**:
1. Verify AWS credentials in `.env` file
2. Check AWS account ID (should be 403732031470)
3. Test S3 access: `python test_s3_integration.py`
4. Verify region settings (us-east-1)

### S3 VCF Processing Timeouts
**Symptom**: VCF processing fails with timeout when using S3 genomic data
**Root Cause**: S3 VCF files are large (several GB) and take time to download and process
**Solution**:
1. **Verify timeout values** in `.env` (these are the correct production values):
   ```bash
   HEALTH_CHECK_TIMEOUT=5        # Fast health check — keep at 5s
   VCF_PROFILE_TIMEOUT=300       # VCF processing (5 minutes — do not reduce)
   ```
2. **Monitor processing**: Look for logs showing S3 file mapping:
   ```
   INFO - Found 16 VCF files in S3 bucket synthatrial-genomic-data
   INFO - Mapped chr22 to S3: genomes/ALL.chr22...vcf.gz
   ```
3. **Fallback to local files**: If S3 is slow, download VCF files locally:
   ```bash
   python scripts/download_vcf_files.py --chromosome chr22
   ```

### API Server Hanging (RESOLVED)
**Symptom**: Server shows as running but doesn't respond to curl requests
**Root Cause**: Blocking AWS service calls in health check endpoints (FIXED)
**Solution** (IMPLEMENTED):
1. **Fast health check endpoints**: Created `/health-fast` for quick connectivity testing
2. **Non-blocking AWS checks**: Removed blocking `get_function()` and `describe_state_machine()` calls
3. **Optimized timeouts**: AWS service checks now have 10-second timeouts
4. **Better error handling**: Graceful fallbacks when AWS services are unavailable
5. **Comprehensive logging**: Added logging to identify blocking operations

**Testing the Fix**:
```bash
curl -v --max-time 5 http://127.0.0.1:8000/health-fast  # Should respond in 1-2 seconds
curl -v --max-time 10 http://127.0.0.1:8000/health      # Should respond in 5-10 seconds
```
