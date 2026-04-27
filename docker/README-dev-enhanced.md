# Enhanced Development Docker Environment

This document describes the enhanced development Docker environment for SynthaTrial, providing comprehensive development tools, hot reloading, debugging utilities, and quality assurance features.

## Overview

The enhanced development environment (`docker/Dockerfile.dev-enhanced`) extends the standard development setup with:

- **Comprehensive Development Tools**: Full suite of code quality, testing, and debugging tools
- **Hot Reloading**: Automatic code reload for rapid development cycles
- **Jupyter Lab Integration**: Interactive development and analysis environment
- **Performance Profiling**: Built-in profiling tools for optimization
- **Code Quality Automation**: Pre-commit hooks, linting, formatting, and security scanning
- **Enhanced Testing**: Comprehensive test reporting with coverage metrics
- **Development Services**: Optional Redis, PostgreSQL, and email testing services

## Quick Start

### 1. Build and Run Enhanced Development Environment

```bash
# Build and start the enhanced development environment
make dev-enhanced

# Or step by step:
make dev-enhanced-build
make dev-enhanced-run
```

### 2. Access Development Services

Once running, you can access:

- **Streamlit (Hot Reload)**: http://localhost:8501
- **Jupyter Lab**: http://localhost:8888
- **Development Shell**: `make dev-enhanced-shell`

### 3. Development Commands

```bash
# Run tests with enhanced reporting
make dev-enhanced-test

# Run code quality checks
make dev-enhanced-quality

# Validate development environment
make dev-enhanced-validate

# View logs
make dev-enhanced-logs

# Stop environment
make dev-enhanced-stop
```

## Development Features

### Hot Reloading

The enhanced environment supports automatic code reloading:

```bash
# Start hot reload server (automatic in dev mode)
docker exec synthatrial-dev-enhanced hot-reload.sh

# Or via make command
make dev-hot-reload
```

### Code Quality Tools

Comprehensive code quality checking:

```bash
# Run all quality checks
docker exec synthatrial-dev-enhanced quality-check.sh

# Individual tools:
docker exec synthatrial-dev-enhanced black --check src/
docker exec synthatrial-dev-enhanced isort --check src/
docker exec synthatrial-dev-enhanced flake8 src/
docker exec synthatrial-dev-enhanced mypy src/
docker exec synthatrial-dev-enhanced bandit -r src/
docker exec synthatrial-dev-enhanced safety check
```

### Testing Framework

Enhanced testing with comprehensive reporting:

```bash
# Run tests with coverage and reporting
docker exec synthatrial-dev-enhanced run-tests.sh

# Run specific test types
docker exec synthatrial-dev-enhanced pytest tests/ --cov=src --html=reports/test-report.html
docker exec synthatrial-dev-enhanced pytest tests/ -m "property" --benchmark-json=reports/benchmark.json
```

### Performance Profiling

Built-in performance profiling tools:

```bash
# Line-by-line profiling
docker exec synthatrial-dev-enhanced profile.sh line src/input_processor.py

# Memory profiling
docker exec synthatrial-dev-enhanced profile.sh memory src/vector_search.py

# Real-time profiling (requires process ID)
docker exec synthatrial-dev-enhanced profile.sh spy <pid>
```

### Jupyter Lab Development

Interactive development and analysis:

```bash
# Access Jupyter Lab (automatically started in dev mode)
# Navigate to: http://localhost:8888

# Or start manually
docker exec synthatrial-dev-enhanced jupyter lab --ip=0.0.0.0 --port=8888
```

### Environment Validation

Comprehensive environment validation:

```bash
# Validate development environment
docker exec synthatrial-dev-enhanced validate-env.sh

# Check specific components
docker exec synthatrial-dev-enhanced python -c "import pytest, black, isort; print('✅ Dev tools OK')"
docker exec synthatrial-dev-enhanced conda list | grep -E "(pytest|black|isort)"
```

## Development Workflow

### 1. Setup Development Environment

```bash
# Initial setup
make dev-enhanced-build
make dev-enhanced-run

# Validate setup
make dev-enhanced-validate
```

### 2. Development Cycle

```bash
# 1. Make code changes (hot reload automatically applies)
# 2. Run tests
make dev-enhanced-test

# 3. Check code quality
make dev-enhanced-quality

# 4. Commit changes (pre-commit hooks run automatically)
git add .
git commit -m "Your changes"
```

### 3. Debugging and Analysis

```bash
# Open development shell
make dev-enhanced-shell

# Use Jupyter for interactive analysis
# Navigate to: http://localhost:8888

# Profile performance issues
make dev-profile-line TARGET=src/your_module.py
make dev-profile-memory TARGET=src/your_module.py
```

## Configuration

### Environment Variables

The enhanced development environment supports these variables:

```bash
# Core configuration
DEVELOPMENT_MODE=1
PYTHONPATH=/app
PYTHONUNBUFFERED=1

# Streamlit configuration
STREAMLIT_SERVER_HEADLESS=true
STREAMLIT_SERVER_ENABLE_CORS=false

# API keys (optional)
GOOGLE_API_KEY=your_key_here
PINECONE_API_KEY=your_key_here
```

### Volume Mappings

The development environment uses these volume mappings:

```yaml
volumes:
  # Source code (hot reload)
  - .:/app

  # Data persistence
  - ./data:/app/data
  - ./logs:/app/logs

  # Development artifacts
  - dev_reports:/app/reports
  - dev_coverage:/app/coverage
  - dev_notebooks:/app/notebooks/development

  # Development tools cache
  - dev_cache:/root/.cache
  - dev_conda_cache:/opt/conda/pkgs
```

### Port Mappings

Available development ports:

- `8501`: Streamlit web interface (hot reload)
- `8888`: Jupyter Lab
- `8000`: Additional development server
- `3000`: Node.js development server
- `5000`: Flask/FastAPI development server

## Optional Services

The enhanced development environment includes optional services:

### Redis (Development Cache)

```bash
# Redis is automatically started
# Access: localhost:6379
docker exec synthatrial-redis-dev redis-cli ping
```

### PostgreSQL (Development Database)

```bash
# PostgreSQL is automatically started
# Access: localhost:5432
# Database: synthatrial_dev
# User: dev_user
# Password: dev_password
```

### Mailhog (Email Testing)

```bash
# Mailhog is automatically started
# SMTP: localhost:1025
# Web UI: http://localhost:8025
```

## Development Scripts

The enhanced environment includes these development scripts:

### `/usr/local/bin/hot-reload.sh`
Starts Streamlit with automatic file watching and reloading.

### `/usr/local/bin/run-tests.sh`
Runs comprehensive test suite with coverage and reporting.

### `/usr/local/bin/quality-check.sh`
Runs all code quality checks (formatting, linting, security).

### `/usr/local/bin/validate-env.sh`
Validates development environment setup and dependencies.

### `/usr/local/bin/profile.sh`
Performance profiling utility with multiple profiling modes.

### `/usr/local/bin/health-check.sh`
Health check script for container monitoring.

## Troubleshooting

### Common Issues

#### Hot Reload Not Working

```bash
# Check file watcher
docker exec synthatrial-dev-enhanced which inotifywait

# Check watchdog
docker exec synthatrial-dev-enhanced python -c "import watchdog; print('OK')"

# Restart hot reload
docker exec synthatrial-dev-enhanced pkill -f streamlit
docker exec synthatrial-dev-enhanced hot-reload.sh
```

#### Jupyter Lab Not Accessible

```bash
# Check Jupyter status
docker exec synthatrial-dev-enhanced jupyter lab list

# Restart Jupyter
docker exec synthatrial-dev-enhanced jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root
```

#### Development Tools Missing

```bash
# Validate environment
make dev-enhanced-validate

# Check specific tools
docker exec synthatrial-dev-enhanced which black isort flake8 mypy bandit
```

#### Performance Issues

```bash
# Check resource usage
docker stats synthatrial-dev-enhanced

# Increase resource limits in docker-compose.dev-enhanced.yml
deploy:
  resources:
    limits:
      cpus: '8.0'
      memory: 16G
```

### Logs and Debugging

```bash
# View all logs
make dev-enhanced-logs

# View specific service logs
docker logs synthatrial-dev-enhanced
docker logs synthatrial-redis-dev
docker logs synthatrial-postgres-dev

# Debug container startup
docker exec synthatrial-dev-enhanced health-check.sh
```

## Best Practices

### 1. Code Quality

- Use pre-commit hooks for automatic quality checks
- Run `make dev-enhanced-quality` before committing
- Address linting and security issues promptly

### 2. Testing

- Write both unit tests and property-based tests
- Use `make dev-enhanced-test` for comprehensive testing
- Monitor test coverage reports

### 3. Performance

- Use profiling tools to identify bottlenecks
- Monitor resource usage during development
- Optimize hot paths identified by profiling

### 4. Development Workflow

- Use hot reload for rapid iteration
- Leverage Jupyter Lab for interactive development
- Validate environment setup regularly

### 5. Security

- Run security scans regularly
- Keep dependencies updated
- Follow secure coding practices

## Integration with CI/CD

The enhanced development environment integrates with CI/CD pipelines:

```bash
# Run CI-like checks locally
make dev-enhanced-quality
make dev-enhanced-test

# Generate reports for CI
docker exec synthatrial-dev-enhanced pytest --json-report --json-report-file=reports/ci-report.json
```

## Customization

### Adding Development Tools

To add new development tools, modify `docker/Dockerfile.dev-enhanced`:

```dockerfile
# Add new Python packages
RUN conda run -n $CONDA_ENV_NAME pip install --no-cache-dir \
    your-new-package>=1.0.0

# Add new system packages
RUN apt-get update && apt-get install -y \
    your-system-package
```

### Custom Development Scripts

Add custom scripts to `/usr/local/bin/` in the Dockerfile:

```dockerfile
RUN echo '#!/bin/bash\n\
# Your custom development script\n\
echo "Running custom development task..."\n\
' > /usr/local/bin/custom-dev.sh && chmod +x /usr/local/bin/custom-dev.sh
```

### Environment Configuration

Customize development configuration in `.dev_config.json`:

```json
{
  "hot_reload": true,
  "debug_mode": true,
  "auto_test": true,
  "coverage_reporting": true,
  "performance_profiling": true,
  "security_scanning": true,
  "code_quality_checks": true,
  "custom_features": {
    "feature1": true,
    "feature2": false
  }
}
```

This enhanced development environment provides a comprehensive, professional-grade development experience for SynthaTrial, enabling rapid development cycles while maintaining high code quality and performance standards.
