# Chapter 9: Cloud Infrastructure & DevOps

This chapter covers Docker containerization, AWS cloud services, CI/CD pipelines,
security scanning, and production deployment.

## 9.1 Docker Architecture

### Multi-Stage Production Dockerfile

The main `Dockerfile` uses a multi-stage build:

```dockerfile
# Stage 1: Base with conda
FROM continuumio/miniconda3:latest AS base
RUN conda create -n anukriti python=3.10

# Stage 2: Dependencies
FROM base AS dependencies
COPY requirements.txt .
RUN conda run -n anukriti pip install -r requirements.txt
RUN conda install -n anukriti -c conda-forge rdkit htslib

# Stage 3: Application
FROM dependencies AS application
COPY src/ /app/src/
COPY data/ /app/data/
COPY app.py api.py main.py /app/

# Stage 4: Production
FROM application AS production
USER anukriti  # Non-root (uid 1000)
EXPOSE 8501 8000
CMD ["streamlit", "run", "app.py", "--server.port=8501"]
```

### Docker Compose Variants

| File | Purpose | Services |
|------|---------|----------|
| `docker-compose.yml` | Basic dev | Frontend + Backend |
| `docker-compose.dev.yml` | Development | Frontend + Backend + volume mounts |
| `docker-compose.dev-enhanced.yml` | Full dev stack | + Postgres + Redis + ELK + Prometheus + Grafana |
| `docker-compose.prod.yml` | Production | Optimized, no dev tools, restart policies |

### Dev-Enhanced Stack

```yaml
services:
  frontend:       # Streamlit (port 8501)
  backend:        # FastAPI (port 8000)
  postgres:       # PostgreSQL database
  redis:          # Redis cache
  elasticsearch:  # ELK stack
  logstash:       # Log aggregation
  kibana:         # Log visualization
  prometheus:     # Metrics collection
  grafana:        # Metrics dashboards
```

### Multi-Architecture Builds

**Script**: `scripts/multi_arch_build.py`

Supported platforms:
- `linux/amd64` (x86_64 — primary)
- `linux/arm64` (ARM — Apple Silicon, AWS Graviton)
- `linux/arm/v7` (32-bit ARM)
- `linux/386` (32-bit x86)

```bash
# Build multi-arch manifest
python scripts/multi_arch_build.py --platforms linux/amd64,linux/arm64 --push
```

Uses Docker buildx for cross-platform compilation.

## 9.2 AWS Cloud Services

### Health Check Architecture (Non-Blocking)

The API uses a three-tier health check system to prevent server hangs:

| Endpoint | Timeout | AWS Checks | Use Case |
|----------|---------|------------|----------|
| `/health-fast` | < 2s | None | Streamlit connectivity test |
| `/` | < 5s | None | Basic liveness probe |
| `/health` | < 15s | Yes (10s/service) | Detailed status monitoring |

AWS service checks in `/health` are non-blocking — they only verify client configuration, not live API calls. This resolved previous "Backend Offline" timeout errors.

### S3 Genomic Data Manager (`src/aws/s3_genomic_manager.py`)

```python
class S3GenomicDataManager:
    def __init__(self, bucket_name="synthatrial-genomic-data"):
        self.s3 = boto3.client("s3")
        self.bucket = bucket_name

    def upload_vcf(self, vcf_path, metadata=None):
        """Upload VCF with metadata tags (sample_id, reference_genome)."""

    def download_vcf(self, s3_key, local_path):
        """Download VCF from S3."""

    def generate_presigned_url(self, s3_key, expiry=3600):
        """Generate temporary access URL (1-hour default)."""
```

Storage features:
- Intelligent Tiering for cost optimization
- Lifecycle policies (transition to Glacier after 90 days)
- Server-side encryption (AES-256)

### S3 Report Manager (`src/aws/s3_report_manager.py`)

Parallel structure for PDF report storage:
- Upload generated PDFs
- Presigned URL generation for secure downloads
- Report search and organization by patient/date
- Lifecycle policies (retain reports for 1 year)

### Lambda Batch Processor (`src/aws/lambda_batch_processor.py`)

```python
class LambdaBatchProcessor:
    def process_batch(self, patients, drug, batch_size=100):
        """
        1. Chunk patients into batches of 100
        2. Invoke Lambda function per batch (async)
        3. Collect results
        4. Aggregate and return
        """

    def estimate_cost(self, n_patients):
        """Estimate AWS Lambda cost for N patients."""
```

### Step Functions Orchestrator (`src/aws/step_functions_orchestrator.py`)

```python
class StepFunctionsOrchestrator:
    def start_clinical_trial_simulation(self, trial_params):
        """
        State machine flow:
        Generate Cohort → Split Batches → Map(Lambda) → Aggregate → Report → S3
        """
```

Configuration: `state-machine-definition.json`
IAM policies: `lambda-trust-policy.json`, `stepfunctions-trust-policy.json`

### AWS Bedrock Integration

- **Claude**: `src/llm_bedrock.py` — PGx explanation generation
- **Titan Embeddings**: `src/embeddings_bedrock.py` — Text embedding for RAG

## 9.3 CI/CD Pipelines (`.github/workflows/`)

### Main CI/CD (`docker-build.yml`)

Triggers: Push to main, pull requests

```yaml
jobs:
  lint:
    - flake8 (E9, F63, F7, F82 — fatal errors)
    - Max complexity: 10
    - Line length: 127

  test:
    - pytest -m "not integration"
    - Mock credentials (GOOGLE_API_KEY, PINECONE_API_KEY)
    - Coverage reporting
```

### Docker Build Pipeline (`docker-build.yml`)

8-job comprehensive pipeline:

```
┌─────────────┐
│ code-quality │ → pre-commit, Bandit, Safety
└──────┬──────┘
       │
┌──────┴──────┐
│    test     │ → pytest matrix (Python 3.10/3.11 × unit/integration/property)
└──────┬──────┘
       │
┌──────┴──────────┐
│  docker-build   │ → Multi-target (dev, prod, dev-enhanced)
└──────┬──────────┘
       │
┌──────┴──────────┐     ┌──────────────────┐
│ container-test  │     │  multi-arch-test  │ → QEMU arm64 validation
└──────┬──────────┘     └──────┬───────────┘
       │                       │
┌──────┴──────────┐     ┌──────┴──────────┐
│ performance-test│     │                 │
└──────┬──────────┘     │                 │
       │                │                 │
┌──────┴────────────────┴─────────────────┐
│              deploy                      │ → Registry push (ghcr.io)
└──────────────────┬───────────────────────┘
                   │
┌──────────────────┴───────────────────────┐
│              notify                       │ → Build report
└──────────────────────────────────────────┘
```

### Security Scan Pipeline (`security-scan.yml`)

**Schedule**: Daily at 2 AM UTC + on push/PR

Scan types:
| Tool | Target | Category |
|------|--------|----------|
| Bandit | Python source code | SAST |
| Safety | Python dependencies | SCA |
| pip-audit | Python dependencies | SCA |
| Trivy | Docker containers | Container security |
| Checkov | Infrastructure-as-code | IaC |
| TruffleHog | Git history | Secret detection |
| Semgrep | Source code patterns | SAST |

Output: JSON reports, GitHub issues for CRITICAL/HIGH findings.

### PR Validation (`pr-validation.yml`)

Validates:
- PR title format
- Branch naming convention
- Commit message style
- Required reviewers

### Release Pipeline (`release.yml`)

Triggered by git tags (v*):
- Creates GitHub release
- Generates changelog from commits
- Publishes Docker images tagged with version

## 9.4 Security

### Pre-Commit Hooks

Configured via `.pre-commit-config.yaml`:

```yaml
repos:
  - hooks:
    - black          # Code formatting
    - isort          # Import sorting
    - flake8         # Linting
    - mypy           # Type checking
    - bandit         # Security scanning
    - trim trailing whitespace
    - check yaml/json/toml
    - check python ast
    - detect private key
    - check for merge conflicts
    - check for large files
```

### Security Scanner (`scripts/security_scanner.py`)

Local security scanning:
```bash
python scripts/security_scanner.py --scan-type all
```

Scans: Bandit (code), Safety (dependencies), Trivy (containers)

### SSL/TLS (`scripts/ssl_manager.py`)

```bash
# Generate self-signed certs for development
python scripts/ssl_manager.py --generate --env dev

# Validate production certificates
python scripts/ssl_manager.py --validate --env prod
```

Certificates stored in `docker/ssl/`:
- `localhost.crt` / `localhost.key` (development)
- `127.0.0.1.crt` / `127.0.0.1.key` (production)

### Nginx Reverse Proxy

`docker/nginx.conf`:
- HTTPS termination
- HTTP → HTTPS redirection
- Proxy to Streamlit (8501) and FastAPI (8000)
- Security headers (HSTS, X-Frame-Options, etc.)

### Credential Management

- `.env` file (gitignored) for local development
- `.env.example` template with placeholder values
- CI/CD uses GitHub Actions secrets
- AWS IAM roles for production (no hardcoded keys)
- Previous credential exposure fixed (commit 92288df)

## 9.5 Deployment Targets

### Docker Registry (`scripts/deploy_to_registry.py`)

```python
class RegistryDeployer:
    """Deploy to multiple container registries."""

    registries = [
        RegistryConfig("ghcr.io", "GitHub Container Registry"),
        RegistryConfig("docker.io", "Docker Hub"),
        RegistryConfig("*.dkr.ecr.*.amazonaws.com", "AWS ECR"),
    ]
```

Features:
- Multi-arch manifest creation
- Rollback support (keep previous version)
- Health check after deployment

### Cloud Platforms

| Platform | Config File | Notes |
|----------|-------------|-------|
| Render | `render.yaml` | Web service deployment |
| Vercel | `vercel.json` | Serverless deployment |
| Heroku | `Procfile` | PaaS deployment |
| AWS EC2 | `docs/aws/AWS_EC2_DEPLOYMENT.md` | Full guide |

### Production Monitoring (`scripts/production_monitor.py`)

```python
class ProductionMonitor:
    def check_health(self):
        """Monitor API latency, error rates, resource usage."""

    def send_alert(self, channel, message):
        """Alert via Slack or email on threshold breach."""
```

### Backup Management (`scripts/backup_manager.py`)

```python
class BackupManager:
    def backup_data(self, target="s3"):
        """Backup PGx data, reports, and configuration to S3."""

    def restore(self, backup_id):
        """Restore from a specific backup."""
```

## 9.6 Development Environment Setup

**Script**: `scripts/setup_dev_env.py`

```bash
python scripts/setup_dev_env.py
```

Sets up:
1. Pre-commit hooks
2. Code quality tools (black, isort, flake8, mypy, bandit)
3. Hot reload configuration for Streamlit
4. Git hooks configuration
5. Environment validation

Flags:
- `--validate-only`: Check without installing
- `--skip-hooks`: Skip pre-commit setup
- `--verbose`: Detailed output

## 9.7 Makefile

Common operations:

```makefile
make quick-start      # Start dev environment (recommended)
make dev-enhanced     # Enhanced dev with extra tools
make run-prod         # Start production
make run-nginx        # Production with SSL/Nginx
make test             # Run validation tests
make test-properties  # Run property-based tests
make lint             # Run linters
make build            # Build Docker images
make push             # Push to registry
make clean            # Clean up containers and images
make logs             # Show container logs
make shell            # Open shell in container
make security-audit   # Comprehensive security audit
make monitor-start    # Start production monitoring
make backup-all       # Create comprehensive backup
make system-status    # Complete system status overview
make data-init        # Initialize all data (VCF + ChEMBL)
make data-status      # Check data status
make ssl-setup        # Generate SSL certificates
```

---

**Next**: [Chapter 10 — Testing & Quality Assurance](10-testing-and-quality.md)
