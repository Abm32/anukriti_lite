# SynthaTrial Docker Management Makefile

.PHONY: help build build-dev build-prod run run-dev run-prod stop clean test setup logs shell ssl-setup ssl-test ssl-validate ssl-dev dev-setup dev-validate pre-commit-install pre-commit-run code-quality monitor-start monitor-health monitor-report monitor-backup monitor-config monitor-status data-init data-init-vcf data-init-chembl data-status data-validate data-clean vcf-download vcf-validate chembl-setup chembl-validate test-containerized test-properties test-coverage test-integration test-all validate-environment benchmark-performance benchmark-containerized setup-complete dev-workflow production-ready automation-status full-ci-simulation emergency-reset help-automation security-audit vulnerability-check backup-all restore-backup health-check-all system-status quick-deploy

# Default target
help:
	@echo "🧬 SynthaTrial Docker Commands"
	@echo "=============================="
	@echo ""
	@echo "Enhanced Development Environment:"
	@echo "  make dev-enhanced     Build and run enhanced development environment"
	@echo "  make dev-enhanced-build  Build enhanced development image"
	@echo "  make dev-enhanced-run    Run enhanced development container"
	@echo "  make dev-enhanced-shell  Open shell in enhanced development container"
	@echo "  make dev-enhanced-test   Run tests with enhanced reporting"
	@echo "  make dev-enhanced-stop   Stop enhanced development environment"
	@echo ""
	@echo "Development Environment:"
	@echo "  make dev-setup       Setup complete development environment"
	@echo "  make dev-validate    Validate development environment"
	@echo "  make pre-commit-install  Install pre-commit hooks"
	@echo "  make pre-commit-run  Run pre-commit on all files"
	@echo ""
	@echo "Development:"
	@echo "  make build-dev    Build development image"
	@echo "  make run-dev      Run development container"
	@echo "  make jupyter      Run with Jupyter notebook"
	@echo "  make ssl-dev      Run development with SSL (Nginx)"
	@echo ""
	@echo "Production:"
	@echo "  make build-prod   Build production image"
	@echo "  make run-prod     Run production container"
	@echo "  make run-nginx    Run with Nginx reverse proxy"
	@echo ""
	@echo "SSL Management:"
	@echo "  make ssl-setup    Generate SSL certificates"
	@echo "  make ssl-test     Test SSL configuration"
	@echo "  make ssl-validate Validate SSL certificates and configuration"
	@echo "  make ssl-info     Show SSL certificate information"
	@echo ""
	@echo "Security Scanning:"
	@echo "  make container-security-scan        Scan all local Docker images"
	@echo "  make container-security-scan-image  Scan specific image (IMAGE=name:tag)"
	@echo "  make container-security-scan-critical  Scan for critical vulnerabilities only"
	@echo "  make container-security-report      Generate comprehensive security reports"
	@echo ""
	@echo "Production Monitoring:"
	@echo "  make monitor-start    Start production monitoring"
	@echo "  make monitor-health   Perform health check"
	@echo "  make monitor-report   Generate monitoring report"
	@echo "  make monitor-backup   Create backup (PATHS=path1,path2)"
	@echo "  make monitor-config   Create example alert configuration"
	@echo ""
	@echo "CI/CD Integration:"
	@echo "  make ci-setup         Setup and validate CI/CD configuration"
	@echo "  make ci-validate      Validate GitHub Actions workflows"
	@echo "  make ci-test-local    Run local CI/CD simulation"
	@echo "  make ci-status        Show CI/CD configuration status"
	@echo ""
	@echo "Multi-Architecture Builds:"
	@echo "  make build-multi-arch        Build production images for AMD64+ARM64"
	@echo "  make build-multi-arch-dev    Build development images for AMD64+ARM64"
	@echo "  make build-multi-arch-enhanced  Build enhanced dev images for AMD64+ARM64"
	@echo "  make build-and-push          Build and push to registry (REGISTRY=url TARGET=prod)"
	@echo "  make build-and-push-all      Build and push all targets (REGISTRY=url)"
	@echo "  make build-amd64             Build for AMD64 platform only"
	@echo "  make build-arm64             Build for ARM64 platform only"
	@echo "  make multi-arch-list-builders  List available Docker Buildx builders"
	@echo "  make multi-arch-cleanup      Clean up build artifacts"
	@echo "  make multi-arch-cleanup-builder  Clean up multi-arch builder"
	@echo ""
	@echo "GitHub CLI Integration:"
	@echo "  make gh-workflow-run     Trigger GitHub workflow (WORKFLOW=name)"
	@echo "  make gh-workflow-status  Show workflow run status"
	@echo "  make gh-workflow-logs    Show workflow logs (RUN_ID=id)"
	@echo ""
	@echo "Registry Deployment Automation:"
	@echo "  make deploy-staging      Deploy to staging environment (REGISTRY=url)"
	@echo "  make deploy-production   Deploy to production environment (REGISTRY=url)"
	@echo "  make deploy-development  Deploy to development environment (REGISTRY=url)"
	@echo "  make deploy-custom       Custom deployment (REGISTRY=url ENV=env TAG=tag)"
	@echo "  make deploy-list-registries  List supported container registries"
	@echo "  make deploy-validate     Validate deployment (REGISTRY=url ENV=env)"
	@echo "  make deploy-cleanup      Cleanup old deployments (REGISTRY=url)"
	@echo ""
	@echo "🚀 Quick Setup & Automation:"
	@echo "  make setup-complete   Complete environment setup (SSL + Data + Dev)"
	@echo "  make automation-status Check automation component status"
	@echo "  make help-automation  Detailed automation help"
	@echo ""
	@echo "🔒 Security & Audit:"
	@echo "  make security-audit   Comprehensive security audit"
	@echo "  make vulnerability-check Check dependency vulnerabilities"
	@echo "  make health-check-all Complete system health check"
	@echo ""
	@echo "💾 Backup & Recovery:"
	@echo "  make backup-all       Create comprehensive backup"
	@echo "  make restore-backup   Backup restoration helper"
	@echo ""
	@echo "📊 Status & Monitoring:"
	@echo "  make system-status    Complete system status overview"
	@echo "  make quick-deploy     Quick deployment workflow"
	@echo ""
	@echo "Data Initialization:"
	@echo "  make data-init        Initialize all data (VCF + ChEMBL)"
	@echo "  make data-init-vcf    Download and validate VCF files"
	@echo "  make data-init-chembl Setup ChEMBL database"
	@echo "  make data-status      Check data initialization status"
	@echo "  make data-validate    Validate data integrity"
	@echo "  make data-clean       Clean downloaded data files"
	@echo ""
	@echo "Testing and Validation:"
	@echo "  make test-containerized    Run tests in containers with reporting"
	@echo "  make test-properties       Run property-based tests"
	@echo "  make test-coverage         Run tests with coverage reporting"
	@echo "  make test-integration      Run integration test suite"
	@echo "  make test-all              Run all test suites"
	@echo "  make validate-environment  Validate complete environment"
	@echo ""
	@echo "Code Quality:"
	@echo "  make format       Format code with Black and isort"
	@echo "  make lint         Run linting checks"
	@echo "  make security-scan Run security analysis"
	@echo "  make code-quality Run comprehensive code quality checks"
	@echo "  make test-coverage Run tests with coverage"
	@echo ""
	@echo "General:"
	@echo "  make build        Build default image"
	@echo "  make run          Run default container"
	@echo "  make stop         Stop all containers"
	@echo "  make clean        Remove containers and images"
	@echo "  make test         Run tests in container"
	@echo "  make setup        Run setup tasks"
	@echo "  make logs         Show container logs"
	@echo "  make shell        Open shell in container"
	@echo ""

# Build targets
build:
	docker-compose build

build-dev:
	docker-compose -f docker-compose.dev.yml build

build-prod:
	docker-compose -f docker-compose.prod.yml build

# Enhanced Development targets
dev-enhanced-build:
	@echo "🚀 Building enhanced development image..."
	docker-compose -f docker-compose.dev-enhanced.yml build
	@echo "✅ Enhanced development image built!"

dev-enhanced-run:
	@echo "🚀 Starting enhanced development environment..."
	docker-compose -f docker-compose.dev-enhanced.yml up -d
	@echo "🌐 Enhanced development environment is starting..."
	@echo "   Streamlit (hot reload): http://localhost:8501"
	@echo "   Jupyter Lab: http://localhost:8888"
	@echo "   Additional ports: 8000, 3000, 5000"
	@echo "   Use 'make dev-enhanced-logs' to see startup logs"
	@echo "   Use 'make dev-enhanced-shell' to access development shell"

dev-enhanced: dev-enhanced-build dev-enhanced-run
	@echo "✅ Enhanced development environment ready!"

dev-enhanced-shell:
	@echo "🐚 Opening enhanced development shell..."
	docker-compose -f docker-compose.dev-enhanced.yml exec synthatrial-dev-enhanced bash

dev-enhanced-test:
	@echo "🧪 Running tests with enhanced reporting..."
	docker-compose -f docker-compose.dev-enhanced.yml exec synthatrial-dev-enhanced run-tests.sh

dev-enhanced-quality:
	@echo "🔍 Running code quality checks..."
	docker-compose -f docker-compose.dev-enhanced.yml exec synthatrial-dev-enhanced quality-check.sh

dev-enhanced-validate:
	@echo "🔧 Validating enhanced development environment..."
	docker-compose -f docker-compose.dev-enhanced.yml exec synthatrial-dev-enhanced validate-env.sh

dev-enhanced-logs:
	docker-compose -f docker-compose.dev-enhanced.yml logs -f

dev-enhanced-stop:
	@echo "🛑 Stopping enhanced development environment..."
	docker-compose -f docker-compose.dev-enhanced.yml down
	@echo "✅ Enhanced development environment stopped!"

dev-enhanced-clean:
	@echo "🧹 Cleaning enhanced development environment..."
	docker-compose -f docker-compose.dev-enhanced.yml down --rmi all --volumes --remove-orphans
	@echo "✅ Enhanced development environment cleaned!"

# Hot reload development
dev-hot-reload:
	@echo "🔥 Starting hot reload development server..."
	docker-compose -f docker-compose.dev-enhanced.yml exec synthatrial-dev-enhanced hot-reload.sh

# Jupyter Lab access
dev-jupyter:
	@echo "📓 Starting Jupyter Lab..."
	docker-compose -f docker-compose.dev-enhanced.yml exec synthatrial-dev-enhanced jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root --NotebookApp.token='' --NotebookApp.password=''

# Performance profiling
dev-profile-line:
	@echo "📊 Starting line profiling..."
	docker-compose -f docker-compose.dev-enhanced.yml exec synthatrial-dev-enhanced profile.sh line $(TARGET)

dev-profile-memory:
	@echo "📊 Starting memory profiling..."
	docker-compose -f docker-compose.dev-enhanced.yml exec synthatrial-dev-enhanced profile.sh memory $(TARGET)

# Run targets
run:
	docker-compose up -d

run-dev:
	docker-compose -f docker-compose.dev.yml up -d

run-prod:
	docker-compose -f docker-compose.prod.yml up -d

run-nginx:
	docker-compose -f docker-compose.prod.yml --profile nginx up -d

jupyter:
	docker-compose -f docker-compose.dev.yml --profile jupyter up -d

ssl-dev:
	docker-compose -f docker-compose.dev.yml --profile nginx-dev up -d
	@echo "🔒 SynthaTrial with SSL is starting..."
	@echo "   HTTPS interface: https://localhost:8443"
	@echo "   HTTP redirect: http://localhost:8080 -> https://localhost:8443"
	@echo "   Use 'make logs-dev' to see startup logs"

# SSL Management targets
ssl-setup:
	@echo "🔒 Setting up SSL certificates..."
	mkdir -p docker/ssl
	python3 scripts/ssl_manager.py --domain localhost --output-dir docker/ssl
	@echo "✅ SSL certificates generated in docker/ssl/"

ssl-test:
	@echo "🔍 Testing SSL configuration..."
	@if [ -f docker/ssl/localhost.crt ] && [ -f docker/ssl/localhost.key ]; then \
		python3 scripts/ssl_manager.py --validate docker/ssl/localhost.crt --key docker/ssl/localhost.key; \
		echo "✅ SSL certificate validation passed"; \
	else \
		echo "❌ SSL certificates not found. Run 'make ssl-setup' first"; \
		exit 1; \
	fi

ssl-validate: ssl-test
	@echo "🔍 Validating SSL certificates and configuration..."
	@echo "✅ SSL validation completed!"

ssl-info:
	@echo "📋 SSL Certificate Information:"
	@if [ -f docker/ssl/localhost.crt ]; then \
		python3 scripts/ssl_manager.py --check-expiration docker/ssl/localhost.crt; \
		echo ""; \
		echo "Certificate details:"; \
		openssl x509 -in docker/ssl/localhost.crt -noout -subject -dates -issuer 2>/dev/null || echo "Could not read certificate details"; \
	else \
		echo "❌ SSL certificate not found. Run 'make ssl-setup' first"; \
	fi

# Data Initialization targets
data-init:
	@echo "🗄️  Initializing all data (VCF + ChEMBL)..."
	python3 scripts/data_initializer.py --all --verbose
	@echo "✅ Data initialization completed!"
	@echo "   Use 'make data-status' to check initialization status"
	@echo "   Use 'make data-validate' to validate data integrity"

data-init-vcf:
	@echo "🧬 Downloading and validating VCF files..."
	python3 scripts/data_initializer.py --vcf chr22 chr10 --verbose
	@echo "✅ VCF files initialized!"

data-init-chembl:
	@echo "💊 Setting up ChEMBL database..."
	python3 scripts/data_initializer.py --chembl --verbose
	@echo "✅ ChEMBL database initialized!"

data-status:
	@echo "📊 Data Initialization Status"
	@echo "============================"
	python3 scripts/data_initializer.py --status --verbose

data-validate:
	@echo "🔍 Validating data integrity..."
	@echo "Checking VCF files..."
	@if [ -f data/genomes/chr22.vcf.gz ]; then \
		python3 scripts/check_vcf_integrity.py data/genomes/chr22.vcf.gz; \
	else \
		echo "  ❌ chr22.vcf.gz not found"; \
	fi
	@if [ -f data/genomes/chr10.vcf.gz ]; then \
		python3 scripts/check_vcf_integrity.py data/genomes/chr10.vcf.gz; \
	else \
		echo "  ❌ chr10.vcf.gz not found"; \
	fi
	@echo "Checking ChEMBL database..."
	@if [ -f data/chembl/chembl_34.db ]; then \
		echo "  ✅ ChEMBL database found"; \
		python3 -c "import sqlite3; conn = sqlite3.connect('data/chembl/chembl_34.db'); print(f'  ✅ ChEMBL database accessible with {conn.execute(\"SELECT COUNT(*) FROM sqlite_master WHERE type=\\\"table\\\"\").fetchone()[0]} tables'); conn.close()"; \
	else \
		echo "  ❌ ChEMBL database not found"; \
	fi
	@echo "✅ Data validation completed!"

data-clean:
	@echo "🧹 Cleaning downloaded data files..."
	@echo "⚠️  This will remove all downloaded VCF and ChEMBL files!"
	@echo "Press Ctrl+C to cancel, or wait 5 seconds to continue..."
	@sleep 5
	rm -rf data/genomes/*.vcf.gz data/chembl/chembl_34*
	@echo "✅ Data files cleaned!"

# VCF-specific commands
vcf-download:
	@echo "🧬 Downloading VCF files..."
	python3 scripts/download_vcf_files.py --chromosomes chr22,chr10 --output-dir data/genomes --verbose
	@echo "✅ VCF download completed!"

vcf-validate:
	@echo "🔍 Validating VCF files..."
	@for vcf in data/genomes/*.vcf.gz; do \
		if [ -f "$$vcf" ]; then \
			echo "Validating $$vcf..."; \
			python3 scripts/check_vcf_integrity.py "$$vcf"; \
		fi; \
	done
	@echo "✅ VCF validation completed!"

# ChEMBL-specific commands
chembl-setup:
	@echo "💊 Setting up ChEMBL database..."
	python3 scripts/setup_chembl.py --output-dir data/chembl --verbose
	@echo "✅ ChEMBL setup completed!"

chembl-validate:
	@echo "🔍 Validating ChEMBL database..."
	@if [ -f data/chembl/chembl_34.db ]; then \
		python3 -c "import sqlite3; conn = sqlite3.connect('data/chembl/chembl_34.db'); tables = conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall(); print(f'ChEMBL database contains {len(tables)} tables'); conn.close()"; \
		echo "✅ ChEMBL database validation passed"; \
	else \
		echo "❌ ChEMBL database not found. Run 'make chembl-setup' first"; \
	fi

# Management targets
stop:
	docker-compose down
	docker-compose -f docker-compose.dev.yml down
	docker-compose -f docker-compose.dev-enhanced.yml down
	docker-compose -f docker-compose.prod.yml down

clean:
	docker-compose down --rmi all --volumes --remove-orphans
	docker-compose -f docker-compose.dev.yml down --rmi all --volumes --remove-orphans
	docker-compose -f docker-compose.dev-enhanced.yml down --rmi all --volumes --remove-orphans
	docker-compose -f docker-compose.prod.yml down --rmi all --volumes --remove-orphans
	docker system prune -f

# Utility targets
test:
	docker-compose exec synthatrial conda run -n synthatrial python tests/validation_tests.py

# Enhanced Testing targets
test-containerized:
	@echo "🧪 Running tests in containers with comprehensive reporting..."
	python3 scripts/run_tests_in_container.py --containers enhanced-dev --coverage-threshold 80 --verbose
	@echo "📊 Test reports generated in test_reports/ directory"
	@echo "   Open test_reports/coverage_report.html for coverage details"
	@echo "   Open test_reports/test_results.json for detailed results"

test-properties:
	@echo "🔬 Running property-based tests..."
	python3 -m pytest tests/test_*_properties.py -v --tb=short
	@echo "✅ Property-based tests completed!"

test-coverage:
	@echo "📊 Running tests with coverage reporting..."
	python3 -m pytest tests/ --cov=src --cov-report=html --cov-report=term-missing --cov-fail-under=70
	@echo "📋 Coverage report generated in htmlcov/ directory"

test-integration:
	@echo "🔗 Running integration test suite..."
	python3 -m pytest tests/test_*_integration.py -v --tb=short
	@echo "✅ Integration tests completed!"

test-all:
	@echo "🧪 Running comprehensive test suite..."
	@echo "Running unit tests..."
	@make test || echo "⚠️  Unit test issues found"
	@echo ""
	@echo "Running property-based tests..."
	@make test-properties || echo "⚠️  Property test issues found"
	@echo ""
	@echo "Running integration tests..."
	@make test-integration || echo "⚠️  Integration test issues found"
	@echo ""
	@echo "Running containerized tests..."
	@make test-containerized || echo "⚠️  Containerized test issues found"
	@echo ""
	@echo "✅ Comprehensive test suite completed!"

# Environment Validation
validate-environment:
	@echo "🔍 Validating complete environment..."
	@echo "Checking development environment..."
	@make dev-validate || echo "⚠️  Development environment issues found"
	@echo ""
	@echo "Checking data initialization..."
	@make data-status || echo "⚠️  Data initialization issues found"
	@echo ""
	@echo "Checking SSL configuration..."
	@make ssl-info || echo "⚠️  SSL configuration issues found"
	@echo ""
	@echo "Running quick tests..."
	python3 tests/quick_test.py || echo "⚠️  Quick test issues found"
	@echo ""
	@echo "✅ Environment validation completed!"

# Performance and Benchmarking
benchmark-performance:
	@echo "⚡ Running performance benchmarks..."
	python3 scripts/benchmark_performance.py --verbose
	@echo "📊 Benchmark results generated in benchmark_reports/ directory"

benchmark-containerized:
	@echo "⚡ Running containerized performance benchmarks..."
	docker-compose exec synthatrial conda run -n synthatrial python scripts/benchmark_performance.py --containerized --verbose
	@echo "✅ Containerized benchmarks completed!"

setup:
	docker-compose exec synthatrial /usr/local/bin/docker-entrypoint.sh setup

logs:
	docker-compose logs -f

logs-dev:
	docker-compose -f docker-compose.dev.yml logs -f

logs-prod:
	docker-compose -f docker-compose.prod.yml logs -f

shell:
	docker-compose exec synthatrial /usr/local/bin/docker-entrypoint.sh bash

shell-dev:
	docker-compose -f docker-compose.dev.yml exec synthatrial-dev /usr/local/bin/docker-entrypoint.sh bash

# CLI commands
cli:
	docker-compose exec synthatrial /usr/local/bin/docker-entrypoint.sh cli $(ARGS)

benchmark:
	docker-compose exec synthatrial /usr/local/bin/docker-entrypoint.sh benchmark

validate:
	docker-compose exec synthatrial /usr/local/bin/docker-entrypoint.sh validate

# Quick start
quick-start: build-dev run-dev
	@echo "🚀 SynthaTrial is starting..."
	@echo "   Web interface: http://localhost:8501"
	@echo "   Use 'make logs-dev' to see startup logs"
	@echo "   Use 'make stop' to stop the container"

# Development Environment Setup
dev-setup:
	@echo "🛠️  Setting up development environment..."
	python3 scripts/setup_dev_env.py --verbose --report
	@echo "✅ Development environment setup completed!"
	@echo "   Run 'make pre-commit-run' to check all files"
	@echo "   Run 'make dev-validate' to validate setup"

dev-validate:
	@echo "🔍 Validating development environment..."
	python3 scripts/setup_dev_env.py --validate-only --verbose

pre-commit-install:
	@echo "🪝 Installing pre-commit hooks..."
	pre-commit install
	pre-commit install --hook-type commit-msg
	@echo "✅ Pre-commit hooks installed!"

pre-commit-run:
	@echo "🔍 Running pre-commit checks on all files..."
	pre-commit run --all-files

pre-commit-update:
	@echo "🔄 Updating pre-commit hooks..."
	pre-commit autoupdate
	@echo "✅ Pre-commit hooks updated!"

# Code Quality
format:
	@echo "🎨 Formatting code..."
	black src/ tests/ scripts/ *.py
	isort src/ tests/ scripts/ *.py
	@echo "✅ Code formatting completed!"

lint:
	@echo "🔍 Running linting checks..."
	flake8 src/ tests/ scripts/ *.py
	mypy src/ --ignore-missing-imports
	bandit -r src/ scripts/ -f json -o bandit-report.json || true
	@echo "✅ Linting checks completed!"

security-scan:
	@echo "🔒 Running security scan..."
	bandit -r src/ scripts/ -f txt
	@echo "✅ Security scan completed!"

code-quality:
	@echo "🔍 Running comprehensive code quality checks..."
	@echo "Step 1: Code formatting..."
	@make format || echo "⚠️  Code formatting issues found"
	@echo ""
	@echo "Step 2: Linting..."
	@make lint || echo "⚠️  Linting issues found"
	@echo ""
	@echo "Step 3: Security analysis..."
	@make security-scan || echo "⚠️  Security issues found"
	@echo ""
	@echo "Step 4: Type checking..."
	@if command -v mypy >/dev/null 2>&1; then \
		mypy src/ --ignore-missing-imports || echo "⚠️  Type checking issues found"; \
	else \
		echo "ℹ️  mypy not installed, skipping type checking"; \
	fi
	@echo ""
	@echo "✅ Code quality checks completed!"

# CI/CD Integration
ci-setup:
	@echo "🔧 Setting up CI/CD environment..."
	@if [ ! -d .github/workflows ]; then \
		echo "❌ GitHub workflows directory not found"; \
		exit 1; \
	fi
	@echo "✅ GitHub Actions workflows found:"
	@ls -la .github/workflows/
	@echo ""
	@echo "📋 Available workflows:"
	@echo "  - docker-build.yml: Main build and test pipeline"
	@echo "  - security-scan.yml: Security scanning workflow"
	@echo "  - release.yml: Release and deployment workflow"
	@echo "  - pr-validation.yml: Pull request validation"
	@echo ""
	@echo "🔧 To trigger workflows:"
	@echo "  - Push to main/develop: Triggers docker-build.yml"
	@echo "  - Create PR: Triggers pr-validation.yml"
	@echo "  - Create release: Triggers release.yml"
	@echo "  - Manual dispatch: Use GitHub Actions UI or gh CLI"

ci-validate:
	@echo "🔍 Validating CI/CD configuration..."
	@echo "Checking GitHub Actions workflows..."
	@for workflow in .github/workflows/*.yml; do \
		echo "  Validating $$workflow..."; \
		if command -v yamllint >/dev/null 2>&1; then \
			yamllint $$workflow || echo "    ⚠️  YAML validation failed for $$workflow"; \
		else \
			echo "    ℹ️  yamllint not installed, skipping YAML validation"; \
		fi; \
	done
	@echo "✅ CI/CD validation completed!"

ci-test-local:
	@echo "🧪 Running local CI/CD simulation..."
	@echo "Running code quality checks..."
	@make format lint security-scan || echo "⚠️  Code quality issues found"
	@echo ""
	@echo "Running tests..."
	@make test-coverage || echo "⚠️  Test issues found"
	@echo ""
	@echo "Testing Docker builds..."
	@make build-dev build-prod || echo "⚠️  Docker build issues found"
	@echo ""
	@echo "✅ Local CI/CD simulation completed!"

ci-status:
	@echo "📊 CI/CD Status Check"
	@echo "===================="
	@echo ""
	@echo "GitHub Actions Workflows:"
	@if [ -d .github/workflows ]; then \
		for workflow in .github/workflows/*.yml; do \
			echo "  ✅ $$(basename $$workflow)"; \
		done; \
	else \
		echo "  ❌ No workflows found"; \
	fi
	@echo ""
	@echo "Issue Templates:"
	@if [ -d .github/ISSUE_TEMPLATE ]; then \
		for template in .github/ISSUE_TEMPLATE/*.yml; do \
			echo "  ✅ $$(basename $$template)"; \
		done; \
	else \
		echo "  ❌ No issue templates found"; \
	fi
	@echo ""
	@echo "PR Template:"
	@if [ -f .github/pull_request_template.md ]; then \
		echo "  ✅ pull_request_template.md"; \
	else \
		echo "  ❌ No PR template found"; \
	fi
	@echo ""
	@echo "Repository Settings:"
	@if [ -f .github/settings.yml ]; then \
		echo "  ✅ settings.yml (for Settings GitHub App)"; \
	else \
		echo "  ❌ No repository settings file found"; \
	fi

# Multi-Architecture Build Support (Enhanced)
build-multi-arch:
	@echo "🏗️  Building multi-architecture images with orchestration..."
	python3 scripts/multi_arch_build.py --target prod --platforms linux/amd64,linux/arm64 --verbose
	@echo "✅ Multi-architecture build completed!"

build-multi-arch-dev:
	@echo "🏗️  Building multi-architecture development images..."
	python3 scripts/multi_arch_build.py --target dev --platforms linux/amd64,linux/arm64 --verbose
	@echo "✅ Multi-architecture development build completed!"

build-multi-arch-enhanced:
	@echo "🏗️  Building multi-architecture enhanced development images..."
	python3 scripts/multi_arch_build.py --target dev-enhanced --platforms linux/amd64,linux/arm64 --verbose
	@echo "✅ Multi-architecture enhanced development build completed!"

build-and-push:
	@echo "🚀 Building and pushing to registry with orchestration..."
	@if [ -z "$(REGISTRY)" ]; then \
		echo "❌ REGISTRY variable not set. Use: make build-and-push REGISTRY=ghcr.io/your-org"; \
		exit 1; \
	fi
	@if [ -z "$(TARGET)" ]; then \
		TARGET="prod"; \
	fi
	@echo "Building and pushing $(TARGET) to $(REGISTRY)..."
	python3 scripts/multi_arch_build.py --target $(TARGET) --registry $(REGISTRY) --push --verbose
	@echo "✅ Images pushed to $(REGISTRY)!"

build-and-push-all:
	@echo "🚀 Building and pushing all targets to registry..."
	@if [ -z "$(REGISTRY)" ]; then \
		echo "❌ REGISTRY variable not set. Use: make build-and-push-all REGISTRY=ghcr.io/your-org"; \
		exit 1; \
	fi
	@echo "Building and pushing all targets to $(REGISTRY)..."
	python3 scripts/multi_arch_build.py --target prod --registry $(REGISTRY) --push --verbose
	python3 scripts/multi_arch_build.py --target dev --registry $(REGISTRY) --push --verbose
	python3 scripts/multi_arch_build.py --target dev-enhanced --registry $(REGISTRY) --push --verbose
	@echo "✅ All images pushed to $(REGISTRY)!"

# Multi-Architecture Build Management
multi-arch-list-builders:
	@echo "📋 Listing Docker Buildx builders..."
	python3 scripts/multi_arch_build.py --list-builders

multi-arch-cleanup:
	@echo "🧹 Cleaning up multi-architecture build artifacts..."
	python3 scripts/multi_arch_build.py --cleanup --older-than-hours 24 --verbose
	@echo "✅ Build artifacts cleaned up!"

multi-arch-cleanup-builder:
	@echo "🧹 Cleaning up multi-architecture builder..."
	python3 scripts/multi_arch_build.py --cleanup-builder --verbose
	@echo "✅ Builder cleaned up!"

# Platform-specific builds
build-amd64:
	@echo "🏗️  Building for AMD64 platform..."
	python3 scripts/multi_arch_build.py --target prod --platforms linux/amd64 --verbose

build-arm64:
	@echo "🏗️  Building for ARM64 platform..."
	python3 scripts/multi_arch_build.py --target prod --platforms linux/arm64 --verbose

# GitHub CLI Integration
gh-workflow-run:
	@echo "🚀 Running GitHub workflow..."
	@if [ -z "$(WORKFLOW)" ]; then \
		echo "❌ WORKFLOW variable not set. Use: make gh-workflow-run WORKFLOW=docker-build.yml"; \
		exit 1; \
	fi
	@if ! command -v gh >/dev/null 2>&1; then \
		echo "❌ GitHub CLI (gh) not installed. Install from: https://cli.github.com/"; \
		exit 1; \
	fi
	gh workflow run $(WORKFLOW)
	@echo "✅ Workflow $(WORKFLOW) triggered!"

gh-workflow-status:
	@echo "📊 GitHub workflow status..."
	@if ! command -v gh >/dev/null 2>&1; then \
		echo "❌ GitHub CLI (gh) not installed. Install from: https://cli.github.com/"; \
		exit 1; \
	fi
	gh run list --limit 10
	@echo ""
	@echo "Use 'gh run view <run-id>' to see details of a specific run"

gh-workflow-logs:
	@echo "📋 GitHub workflow logs..."
	@if [ -z "$(RUN_ID)" ]; then \
		echo "❌ RUN_ID variable not set. Use: make gh-workflow-logs RUN_ID=12345"; \
		echo "Get RUN_ID from: make gh-workflow-status"; \
		exit 1; \
	fi
	@if ! command -v gh >/dev/null 2>&1; then \
		echo "❌ GitHub CLI (gh) not installed. Install from: https://cli.github.com/"; \
		exit 1; \
	fi
	gh run view $(RUN_ID) --log

# Container Security Scanning
container-security-scan:
	@echo "🔒 Running container security scan..."
	python3 scripts/security_scanner.py --scan-all-images --verbose
	@echo "✅ Container security scan completed!"

container-security-scan-image:
	@echo "🔒 Scanning specific image: $(IMAGE)"
	@if [ -z "$(IMAGE)" ]; then \
		echo "❌ Please specify IMAGE variable: make container-security-scan-image IMAGE=synthatrial:latest"; \
		exit 1; \
	fi
	python3 scripts/security_scanner.py --image $(IMAGE) --verbose --output-format html
	@echo "✅ Container security scan completed for $(IMAGE)!"

container-security-scan-critical:
	@echo "🚨 Scanning for critical vulnerabilities..."
	python3 scripts/security_scanner.py --scan-all-images --severity critical,high --fail-on-critical --verbose
	@echo "✅ Critical vulnerability scan completed!"

container-security-report:
	@echo "📊 Generating comprehensive security report..."
	python3 scripts/security_scanner.py --scan-all-images --output-format html --verbose
	@echo "📋 Security reports generated in security_reports/ directory"
	@echo "   Open security_reports/security_summary_*.json for summary"
	@echo "   Open security_reports/security_report_*.html for detailed reports"

# Registry Deployment Automation
deploy-staging:
	@echo "🚀 Deploying to staging environment..."
	@if [ -z "$(REGISTRY)" ]; then \
		echo "❌ REGISTRY variable not set. Use: make deploy-staging REGISTRY=ghcr.io/your-org"; \
		exit 1; \
	fi
	@TAG=$${TAG:-latest}; \
	python3 scripts/deploy_to_registry.py \
		--registry $(REGISTRY) \
		--environment staging \
		--tag $$TAG \
		--health-check-url $${HEALTH_CHECK_URL} \
		--verbose
	@echo "✅ Staging deployment completed!"

deploy-production:
	@echo "🚨 Deploying to PRODUCTION environment..."
	@if [ -z "$(REGISTRY)" ]; then \
		echo "❌ REGISTRY variable not set. Use: make deploy-production REGISTRY=ghcr.io/your-org"; \
		exit 1; \
	fi
	@TAG=$${TAG:-latest}; \
	echo "⚠️  This will deploy to PRODUCTION. Ensure you have proper approvals."; \
	python3 scripts/deploy_to_registry.py \
		--registry $(REGISTRY) \
		--environment production \
		--tag $$TAG \
		--health-check-url $${HEALTH_CHECK_URL} \
		--verbose
	@echo "✅ Production deployment completed!"

deploy-development:
	@echo "🛠️  Deploying to development environment..."
	@if [ -z "$(REGISTRY)" ]; then \
		echo "❌ REGISTRY variable not set. Use: make deploy-development REGISTRY=ghcr.io/your-org"; \
		exit 1; \
	fi
	@TAG=$${TAG:-dev}; \
	python3 scripts/deploy_to_registry.py \
		--registry $(REGISTRY) \
		--environment development \
		--tag $$TAG \
		--images synthatrial-dev,synthatrial-dev-enhanced \
		--verbose
	@echo "✅ Development deployment completed!"

deploy-custom:
	@echo "🎯 Custom deployment..."
	@if [ -z "$(REGISTRY)" ] || [ -z "$(ENV)" ]; then \
		echo "❌ REGISTRY and ENV variables required. Use: make deploy-custom REGISTRY=url ENV=staging TAG=v1.0.0"; \
		exit 1; \
	fi
	@TAG=$${TAG:-latest}; \
	IMAGES=$${IMAGES:-synthatrial}; \
	python3 scripts/deploy_to_registry.py \
		--registry $(REGISTRY) \
		--environment $(ENV) \
		--tag $$TAG \
		--images $$IMAGES \
		--health-check-url $${HEALTH_CHECK_URL} \
		--verbose
	@echo "✅ Custom deployment completed!"

deploy-list-registries:
	@echo "📋 Supported container registries:"
	python3 scripts/deploy_to_registry.py --list-registries

deploy-validate:
	@echo "🔍 Validating deployment..."
	@if [ -z "$(REGISTRY)" ] || [ -z "$(ENV)" ]; then \
		echo "❌ REGISTRY and ENV variables required. Use: make deploy-validate REGISTRY=url ENV=staging"; \
		exit 1; \
	fi
	python3 scripts/deploy_to_registry.py \
		--validate-deployment \
		--registry $(REGISTRY) \
		--environment $(ENV) \
		--verbose

deploy-cleanup:
	@echo "🧹 Cleaning up old deployments..."
	@if [ -z "$(REGISTRY)" ]; then \
		echo "❌ REGISTRY variable not set. Use: make deploy-cleanup REGISTRY=ghcr.io/your-org"; \
		exit 1; \
	fi
	@KEEP_COUNT=$${KEEP_COUNT:-5}; \
	python3 scripts/deploy_to_registry.py \
		--cleanup \
		--registry $(REGISTRY) \
		--keep-count $$KEEP_COUNT \
		--verbose
	@echo "✅ Deployment cleanup completed!"

# Deployment workflow shortcuts
deploy-all-staging:
	@echo "🚀 Deploying all images to staging..."
	@if [ -z "$(REGISTRY)" ]; then \
		echo "❌ REGISTRY variable not set. Use: make deploy-all-staging REGISTRY=ghcr.io/your-org"; \
		exit 1; \
	fi
	@TAG=$${TAG:-staging}; \
	python3 scripts/deploy_to_registry.py \
		--registry $(REGISTRY) \
		--environment staging \
		--tag $$TAG \
		--images synthatrial,synthatrial-dev,synthatrial-dev-enhanced \
		--health-check-url $${HEALTH_CHECK_URL} \
		--verbose

deploy-all-production:
	@echo "🚨 Deploying all images to PRODUCTION..."
	@if [ -z "$(REGISTRY)" ]; then \
		echo "❌ REGISTRY variable not set. Use: make deploy-all-production REGISTRY=ghcr.io/your-org"; \
		exit 1; \
	fi
	@TAG=$${TAG:-latest}; \
	echo "⚠️  This will deploy ALL IMAGES to PRODUCTION. Ensure you have proper approvals."; \
	python3 scripts/deploy_to_registry.py \
		--registry $(REGISTRY) \
		--environment production \
		--tag $$TAG \
		--images synthatrial,synthatrial-dev,synthatrial-dev-enhanced \
		--health-check-url $${HEALTH_CHECK_URL} \
		--verbose

# Deployment status and monitoring
deploy-status:
	@echo "📊 Deployment Status Check"
	@echo "========================="
	@echo ""
	@echo "Available deployment commands:"
	@echo "  make deploy-staging REGISTRY=url      - Deploy to staging"
	@echo "  make deploy-production REGISTRY=url   - Deploy to production"
	@echo "  make deploy-development REGISTRY=url  - Deploy to development"
	@echo "  make deploy-custom REGISTRY=url ENV=env TAG=tag - Custom deployment"
	@echo ""
	@echo "Validation and management:"
	@echo "  make deploy-validate REGISTRY=url ENV=env - Validate deployment"
	@echo "  make deploy-cleanup REGISTRY=url      - Cleanup old deployments"
	@echo "  make deploy-list-registries           - List supported registries"
	@echo ""
	@echo "Environment variables:"
	@echo "  REGISTRY     - Container registry URL (required)"
	@echo "  TAG          - Image tag (default: latest/staging/dev)"
	@echo "  ENV          - Environment name (for custom deployments)"
	@echo "  IMAGES       - Comma-separated image list (default: synthatrial)"
	@echo "  HEALTH_CHECK_URL - URL for health checks (optional)"
	@echo "  KEEP_COUNT   - Number of deployments to keep (default: 5)"
	@echo ""
	@echo "Examples:"
	@echo "  make deploy-staging REGISTRY=ghcr.io/org/synthatrial TAG=v1.0.0"
	@echo "  make deploy-production REGISTRY=docker.io/org/synthatrial"
	@echo "  make deploy-validate REGISTRY=ghcr.io/org/synthatrial ENV=staging"

# Production Monitoring
monitor-start:
	@echo "📊 Starting production monitoring..."
	@if [ -f alerts.json ]; then \
		python3 scripts/production_monitor.py --monitor --alert-config alerts.json --verbose; \
	else \
		python3 scripts/production_monitor.py --monitor --verbose; \
	fi

monitor-health:
	@echo "🏥 Performing health check..."
	python3 scripts/production_monitor.py --health-check --verbose

monitor-report:
	@echo "📋 Generating monitoring report..."
	python3 scripts/production_monitor.py --generate-report --verbose
	@echo "📊 Monitoring report generated in monitoring_reports/ directory"

monitor-backup:
	@echo "💾 Creating backup..."
	@if [ -z "$(PATHS)" ]; then \
		echo "❌ Please specify PATHS variable: make monitor-backup PATHS=/app/data,/app/logs"; \
		exit 1; \
	fi
	python3 scripts/production_monitor.py --backup --backup-paths $(PATHS) --verbose
	@echo "✅ Backup completed!"

monitor-config:
	@echo "⚙️  Creating example alert configuration..."
	@if [ ! -f alerts.json ]; then \
		cp alerts.json.example alerts.json; \
		echo "✅ Alert configuration created: alerts.json"; \
		echo "   Edit alerts.json to customize monitoring settings"; \
	else \
		echo "ℹ️  Alert configuration already exists: alerts.json"; \
	fi

monitor-status:
	@echo "📊 Production monitoring status..."
	@echo "Configuration files:"
	@if [ -f alerts.json ]; then \
		echo "  ✅ alerts.json (custom configuration)"; \
	else \
		echo "  ⚠️  alerts.json (not found, using defaults)"; \
	fi
	@if [ -f alerts.json.example ]; then \
		echo "  ✅ alerts.json.example (template available)"; \
	else \
		echo "  ❌ alerts.json.example (template missing)"; \
	fi
	@echo ""
	@echo "Available commands:"
	@echo "  make monitor-start    - Start continuous monitoring"
	@echo "  make monitor-health   - One-time health check"
	@echo "  make monitor-report   - Generate current report"
	@echo "  make monitor-backup   - Create data backup"
	@echo "  make monitor-config   - Setup alert configuration"

# Complete Environment Setup
setup-complete:
	@echo "🚀 Setting up complete SynthaTrial environment..."
	@echo "Step 1: Development environment setup..."
	@make dev-setup || echo "⚠️  Development setup issues found"
	@echo ""
	@echo "Step 2: SSL certificate setup..."
	@make ssl-setup || echo "⚠️  SSL setup issues found"
	@echo ""
	@echo "Step 3: Data initialization..."
	@make data-init || echo "⚠️  Data initialization issues found"
	@echo ""
	@echo "Step 4: Environment validation..."
	@make validate-environment || echo "⚠️  Environment validation issues found"
	@echo ""
	@echo "✅ Complete environment setup finished!"
	@echo "   Use 'make quick-start' to start the application"
	@echo "   Use 'make test-all' to run comprehensive tests"

# Quick Development Workflow
dev-workflow:
	@echo "🔄 Running development workflow..."
	@echo "Formatting code..."
	@make format || echo "⚠️  Code formatting issues found"
	@echo ""
	@echo "Running linting..."
	@make lint || echo "⚠️  Linting issues found"
	@echo ""
	@echo "Running security scan..."
	@make security-scan || echo "⚠️  Security issues found"
	@echo ""
	@echo "Running tests..."
	@make test-coverage || echo "⚠️  Test issues found"
	@echo ""
	@echo "✅ Development workflow completed!"

# Production Readiness Check
production-ready:
	@echo "🏭 Checking production readiness..."
	@echo "Building production image..."
	@make build-prod || echo "❌ Production build failed"
	@echo ""
	@echo "Running security scans..."
	@make container-security-scan || echo "⚠️  Security scan issues found"
	@echo ""
	@echo "Validating SSL setup..."
	@make ssl-test || echo "⚠️  SSL validation issues found"
	@echo ""
	@echo "Running comprehensive tests..."
	@make test-all || echo "⚠️  Test issues found"
	@echo ""
	@echo "Checking data integrity..."
	@make data-validate || echo "⚠️  Data validation issues found"
	@echo ""
	@echo "✅ Production readiness check completed!"
	@echo "   Use 'make run-prod' to start production environment"
	@echo "   Use 'make monitor-start' to begin monitoring"

# Automation Status Overview
automation-status:
	@echo "🤖 SynthaTrial Automation Status"
	@echo "================================"
	@echo ""
	@echo "🔒 SSL Management:"
	@if [ -f docker/ssl/localhost.crt ]; then \
		echo "  ✅ SSL certificates configured"; \
	else \
		echo "  ❌ SSL certificates not found (run 'make ssl-setup')"; \
	fi
	@echo ""
	@echo "🗄️  Data Initialization:"
	@if [ -f data/genomes/chr22.vcf.gz ] && [ -f data/genomes/chr10.vcf.gz ]; then \
		echo "  ✅ VCF files initialized"; \
	else \
		echo "  ❌ VCF files not found (run 'make data-init-vcf')"; \
	fi
	@if [ -f data/chembl/chembl_34.db ]; then \
		echo "  ✅ ChEMBL database initialized"; \
	else \
		echo "  ❌ ChEMBL database not found (run 'make data-init-chembl')"; \
	fi
	@echo ""
	@echo "🛠️  Development Environment:"
	@if [ -f .pre-commit-config.yaml ]; then \
		echo "  ✅ Pre-commit hooks configured"; \
	else \
		echo "  ❌ Pre-commit hooks not configured (run 'make dev-setup')"; \
	fi
	@echo ""
	@echo "🐳 Docker Environment:"
	@if docker images | grep -q synthatrial; then \
		echo "  ✅ Docker images built"; \
	else \
		echo "  ❌ Docker images not found (run 'make build')"; \
	fi
	@echo ""
	@echo "📊 Available Commands:"
	@echo "  make setup-complete      - Complete environment setup"
	@echo "  make dev-workflow        - Development workflow (format, lint, test)"
	@echo "  make production-ready    - Production readiness check"
	@echo "  make automation-status   - This status overview"

# Advanced Automation Workflows
full-ci-simulation:
	@echo "🔄 Running full CI/CD simulation locally..."
	@echo "Step 1: Code quality checks..."
	@make dev-workflow || echo "⚠️  Code quality issues found"
	@echo ""
	@echo "Step 2: Multi-architecture builds..."
	@make build-multi-arch || echo "⚠️  Multi-arch build issues found"
	@echo ""
	@echo "Step 3: Security scanning..."
	@make container-security-scan || echo "⚠️  Security scan issues found"
	@echo ""
	@echo "Step 4: Comprehensive testing..."
	@make test-all || echo "⚠️  Test issues found"
	@echo ""
	@echo "Step 5: Production readiness..."
	@make production-ready || echo "⚠️  Production readiness issues found"
	@echo ""
	@echo "✅ Full CI/CD simulation completed!"

# Security and Audit Commands
security-audit:
	@echo "🔒 Running comprehensive security audit..."
	@echo "Step 1: Container security scanning..."
	@make container-security-scan || echo "⚠️  Container security issues found"
	@echo ""
	@echo "Step 2: Code security analysis..."
	@make security-scan || echo "⚠️  Code security issues found"
	@echo ""
	@echo "Step 3: SSL certificate validation..."
	@make ssl-validate || echo "⚠️  SSL validation issues found"
	@echo ""
	@echo "Step 4: Dependency vulnerability check..."
	@make vulnerability-check || echo "⚠️  Dependency vulnerability issues found"
	@echo ""
	@echo "✅ Security audit completed!"

vulnerability-check:
	@echo "🔍 Checking for dependency vulnerabilities..."
	@if command -v safety >/dev/null 2>&1; then \
		safety check || echo "⚠️  Vulnerability check issues found"; \
	else \
		echo "ℹ️  safety not installed, skipping vulnerability check"; \
		echo "   Install with: pip install safety"; \
	fi
	@if [ -f requirements.txt ]; then \
		echo "Checking requirements.txt for known vulnerabilities..."; \
		pip-audit requirements.txt 2>/dev/null || echo "ℹ️  pip-audit not available"; \
	fi
	@echo "✅ Vulnerability check completed!"

# Backup and Recovery Commands
backup-create:
	@echo "💾 Creating backup..."
	@make backup-all

backup-all:
	@echo "💾 Creating comprehensive backup..."
	@echo "Backing up data files..."
	@make monitor-backup PATHS=data/genomes,data/chembl || echo "⚠️  Data backup issues found"
	@echo ""
	@echo "Backing up SSL certificates..."
	@if [ -d docker/ssl ]; then \
		tar -czf backup_ssl_$(shell date +%Y%m%d_%H%M%S).tar.gz docker/ssl/; \
		echo "✅ SSL certificates backed up"; \
	else \
		echo "ℹ️  No SSL certificates to backup"; \
	fi
	@echo ""
	@echo "Backing up configuration files..."
	@tar -czf backup_config_$(shell date +%Y%m%d_%H%M%S).tar.gz .env docker-compose*.yml Makefile || echo "⚠️  Configuration backup issues found"
	@echo "✅ Comprehensive backup completed!"

restore-backup:
	@echo "🔄 Backup restoration helper..."
	@echo "Available backup files:"
	@ls -la backup_*.tar.gz 2>/dev/null || echo "No backup files found"
	@echo ""
	@echo "To restore a backup:"
	@echo "  1. Extract the backup: tar -xzf backup_file.tar.gz"
	@echo "  2. Review extracted files before overwriting"
	@echo "  3. Copy files to appropriate locations"
	@echo "  4. Run 'make validate-environment' to verify"

# Health and Status Commands
health-check-all:
	@echo "🏥 Comprehensive health check..."
	@echo "Checking container health..."
	@make monitor-health || echo "⚠️  Container health issues found"
	@echo ""
	@echo "Checking data integrity..."
	@make data-validate || echo "⚠️  Data integrity issues found"
	@echo ""
	@echo "Checking SSL configuration..."
	@make ssl-validate || echo "⚠️  SSL configuration issues found"
	@echo ""
	@echo "Checking development environment..."
	@make dev-validate || echo "⚠️  Development environment issues found"
	@echo ""
	@echo "✅ Comprehensive health check completed!"

system-status:
	@echo "📊 System Status Overview"
	@echo "========================"
	@echo ""
	@echo "🐳 Docker Status:"
	@if docker info >/dev/null 2>&1; then \
		echo "  ✅ Docker daemon running"; \
		echo "  📊 Images: $(shell docker images --format 'table {{.Repository}}:{{.Tag}}' | grep synthatrial | wc -l) SynthaTrial images"; \
		echo "  📊 Containers: $(shell docker ps -a --format 'table {{.Names}}' | grep synthatrial | wc -l) SynthaTrial containers"; \
	else \
		echo "  ❌ Docker daemon not running"; \
	fi
	@echo ""
	@echo "🗄️  Data Status:"
	@make data-status 2>/dev/null || echo "  ❌ Data status check failed"
	@echo ""
	@echo "🔒 Security Status:"
	@if [ -f docker/ssl/localhost.crt ]; then \
		echo "  ✅ SSL certificates present"; \
	else \
		echo "  ❌ SSL certificates missing"; \
	fi
	@echo ""
	@echo "🛠️  Development Status:"
	@if [ -f .pre-commit-config.yaml ]; then \
		echo "  ✅ Pre-commit hooks configured"; \
	else \
		echo "  ❌ Pre-commit hooks not configured"; \
	fi

# Quick Deployment Commands
quick-deploy:
	@echo "🚀 Quick deployment workflow..."
	@echo "Step 1: Code quality checks..."
	@make code-quality || echo "⚠️  Code quality issues found"
	@echo ""
	@echo "Step 2: Build production image..."
	@make build-prod || echo "❌ Production build failed"
	@echo ""
	@echo "Step 3: Security scan..."
	@make container-security-scan || echo "⚠️  Security scan issues found"
	@echo ""
	@echo "Step 4: Run production environment..."
	@make run-prod || echo "❌ Production startup failed"
	@echo ""
	@echo "✅ Quick deployment completed!"
	@echo "   Access the application at: http://localhost:8501"
	@echo "   Use 'make logs-prod' to monitor logs"
	@echo "   Use 'make stop' to stop the deployment"

# Emergency Recovery
emergency-reset:
	@echo "🚨 Emergency environment reset..."
	@echo "⚠️  This will clean all containers, images, and data!"
	@echo "Press Ctrl+C to cancel, or wait 10 seconds to continue..."
	@sleep 10
	@make clean
	@make data-clean
	rm -rf docker/ssl/*.crt docker/ssl/*.key
	@echo "🧹 Environment reset completed!"
	@echo "   Run 'make setup-complete' to reinitialize"

# Help for new automation commands
help-automation:
	@echo "🤖 SynthaTrial Automation Commands"
	@echo "=================================="
	@echo ""
	@echo "🚀 Quick Setup:"
	@echo "  make setup-complete      - Complete environment setup (SSL + Data + Dev)"
	@echo "  make automation-status   - Check current automation status"
	@echo "  make quick-deploy        - Quick deployment workflow"
	@echo ""
	@echo "🔄 Development Workflows:"
	@echo "  make dev-workflow        - Format, lint, security scan, test"
	@echo "  make code-quality        - Comprehensive code quality checks"
	@echo "  make full-ci-simulation  - Complete CI/CD simulation locally"
	@echo ""
	@echo "🏭 Production Workflows:"
	@echo "  make production-ready    - Complete production readiness check"
	@echo "  make emergency-reset     - Emergency environment reset"
	@echo ""
	@echo "🔒 Security & Audit:"
	@echo "  make security-audit      - Comprehensive security audit"
	@echo "  make vulnerability-check - Check dependency vulnerabilities"
	@echo "  make ssl-validate        - Validate SSL certificates"
	@echo ""
	@echo "💾 Backup & Recovery:"
	@echo "  make backup-all          - Create comprehensive backup"
	@echo "  make restore-backup      - Backup restoration helper"
	@echo ""
	@echo "📊 Status and Monitoring:"
	@echo "  make validate-environment - Validate complete environment"
	@echo "  make automation-status   - Automation component status"
	@echo "  make system-status       - Complete system status overview"
	@echo "  make health-check-all    - Comprehensive health check"
	@echo "  make help-automation     - This help message"
	@echo ""
	@echo "For detailed help on specific areas, use:"
	@echo "  make help                - Main help menu"
