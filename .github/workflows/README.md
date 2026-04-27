# SynthaTrial CI/CD Workflows

This directory contains GitHub Actions workflows for automated building, testing, security scanning, and deployment of the SynthaTrial platform.

## Workflow Overview

### 🏗️ `docker-build.yml` - Main Build Pipeline
**Triggers:** Push to main/develop, tags, pull requests, manual dispatch

**Features:**
- Multi-architecture builds (AMD64, ARM64)
- Comprehensive test suites (unit, integration, property-based)
- Security scanning with Trivy
- Container registry deployment
- Performance testing
- Automated notifications

**Jobs:**
1. **Code Quality & Security** - Pre-commit hooks, Bandit, Safety
2. **Test Suite** - Unit, integration, and property-based tests
3. **Docker Build** - Multi-arch builds for dev, prod, dev-enhanced
4. **Container Testing** - Startup and compose validation
5. **Multi-Architecture Validation** - Cross-platform compatibility
6. **Performance Testing** - Basic load and response time tests
7. **Deployment** - Registry push and status updates
8. **Notification & Reporting** - Build reports and status

### 🔒 `security-scan.yml` - Security Scanning
**Triggers:** Daily schedule (2 AM UTC), manual dispatch

**Features:**
- Code security analysis (Bandit, Semgrep)
- Dependency vulnerability scanning (Safety, pip-audit)
- Container security scanning (Trivy)
- Secret detection (TruffleHog)
- Automated issue creation for critical vulnerabilities

**Scan Types:**
- `all` - Complete security scan
- `code` - Source code analysis only
- `dependencies` - Dependency vulnerabilities only
- `containers` - Container image scanning only

### 🚀 `release.yml` - Release and Deployment
**Triggers:** Release published, manual dispatch

**Features:**
- Version validation and format checking
- Multi-architecture release builds
- Release-specific testing
- Security validation for releases
- Environment deployment (staging/production)
- Post-deployment verification

**Environments:**
- `staging` - Pre-production testing
- `production` - Live deployment

### 🔍 `pr-validation.yml` - Pull Request Validation
**Triggers:** PR opened/updated, PR reviews

**Features:**
- Fast feedback for pull requests
- Code quality checks
- Quick test execution
- Docker build validation
- Security scanning
- Performance impact assessment
- Documentation validation
- Automated PR comments with results

## Configuration

### Environment Variables

Set these in your repository settings under **Settings > Secrets and variables > Actions**:

```bash
# Required for container registry
GITHUB_TOKEN  # Automatically provided

# Optional for enhanced features
DOCKER_HUB_USERNAME    # Docker Hub deployment
DOCKER_HUB_TOKEN       # Docker Hub authentication
SLACK_WEBHOOK_URL      # Slack notifications
TEAMS_WEBHOOK_URL      # Teams notifications
```

### Workflow Customization

#### Build Configuration
```yaml
# In docker-build.yml
env:
  REGISTRY: ghcr.io                    # Container registry
  IMAGE_NAME: ${{ github.repository }} # Image name
  PLATFORMS: linux/amd64,linux/arm64  # Target platforms
```

#### Security Thresholds
```yaml
# In security-scan.yml
inputs:
  severity_threshold:
    default: 'medium'  # low, medium, high, critical
```

#### Test Configuration
```yaml
# Test timeouts and parallelization
pytest --timeout=300 --maxfail=5 -x
```

## Usage Examples

### Manual Workflow Dispatch

#### Trigger Security Scan
```bash
# Via GitHub CLI
gh workflow run security-scan.yml \
  -f scan_type=all \
  -f severity_threshold=high

# Via GitHub UI
# Go to Actions > Security Scanning > Run workflow
```

#### Trigger Release
```bash
# Via GitHub CLI
gh workflow run release.yml \
  -f version=v1.2.0 \
  -f environment=staging

# Create release via GitHub UI
# Go to Releases > Create a new release
```

#### Force Docker Rebuild
```bash
# Via GitHub CLI
gh workflow run docker-build.yml \
  -f force_rebuild=true \
  -f skip_tests=false
```

### Workflow Status Badges

Add these to your README.md:

```markdown
[![Docker Build](https://github.com/your-org/synthatrial/actions/workflows/docker-build.yml/badge.svg)](https://github.com/your-org/synthatrial/actions/workflows/docker-build.yml)
[![Security Scan](https://github.com/your-org/synthatrial/actions/workflows/security-scan.yml/badge.svg)](https://github.com/your-org/synthatrial/actions/workflows/security-scan.yml)
[![PR Validation](https://github.com/your-org/synthatrial/actions/workflows/pr-validation.yml/badge.svg)](https://github.com/your-org/synthatrial/actions/workflows/pr-validation.yml)
```

## Workflow Artifacts

Each workflow generates artifacts for debugging and reporting:

### Build Artifacts
- `test-results-*` - Test execution results and coverage
- `security-reports` - Security scan results
- `container-security-scan` - Container vulnerability reports
- `build-report` - Comprehensive build summary

### Security Artifacts
- `code-security-reports` - Source code security analysis
- `dependency-security-reports` - Dependency vulnerability reports
- `container-security-reports-*` - Container security scans
- `security-summary-report` - Consolidated security report

### Release Artifacts
- `release-security-report` - Release-specific security scan
- `release-report` - Release deployment summary

### PR Artifacts
- `pr-security-reports` - PR-specific security analysis
- `pr-summary` - Pull request validation summary

## Troubleshooting

### Common Issues

#### Build Failures
```bash
# Check build logs
gh run view --log

# Re-run failed jobs
gh run rerun --failed
```

#### Security Scan Failures
```bash
# View security reports
gh run download <run-id> -n security-summary-report

# Check specific vulnerability
trivy image --format table synthatrial:latest
```

#### Multi-Architecture Build Issues
```bash
# Test local multi-arch build
docker buildx build --platform linux/amd64,linux/arm64 -t test .

# Check buildx setup
docker buildx ls
```

### Performance Optimization

#### Faster Builds
- Use build cache: `cache-from: type=gha`
- Parallel test execution: `pytest -n auto`
- Skip tests for documentation changes: `if: needs.pr-info.outputs.has_code_changes == 'true'`

#### Resource Management
- Adjust timeouts: `timeout-minutes: 30`
- Limit concurrent jobs: `max-parallel: 2`
- Use matrix strategy for parallel execution

## Integration with SynthaTrial

### Docker Integration
The workflows integrate with SynthaTrial's Docker infrastructure:
- Uses existing Dockerfiles (`docker/Dockerfile.dev`, `docker/Dockerfile.prod`)
- Leverages docker-compose configurations
- Integrates with Makefile commands

### Testing Integration
- Runs existing test suites (`tests/validation_tests.py`, `tests/quick_test.py`)
- Executes property-based tests with Hypothesis
- Validates containerized environments

### Security Integration
- Uses SynthaTrial's security scanner (`scripts/security_scanner.py`)
- Integrates with existing monitoring (`scripts/production_monitor.py`)
- Validates SSL certificate management

## Monitoring and Alerts

### Workflow Monitoring
- GitHub Actions dashboard for workflow status
- Automated issue creation for critical failures
- Slack/Teams integration for notifications

### Performance Monitoring
- Build time tracking
- Test execution metrics
- Container startup performance

### Security Monitoring
- Daily vulnerability scans
- Dependency update notifications
- Critical vulnerability alerts

## Best Practices

### Development Workflow
1. Create feature branch
2. Make changes with tests
3. Push to trigger PR validation
4. Address any validation failures
5. Merge after approval
6. Automatic deployment to staging
7. Manual promotion to production

### Security Workflow
1. Daily automated security scans
2. Review security reports weekly
3. Address critical vulnerabilities immediately
4. Update dependencies regularly
5. Monitor security advisories

### Release Workflow
1. Create release candidate
2. Run comprehensive testing
3. Security validation
4. Deploy to staging
5. User acceptance testing
6. Deploy to production
7. Monitor post-deployment

## Support

For workflow issues:
1. Check workflow logs in GitHub Actions
2. Review artifact reports
3. Consult troubleshooting section
4. Create issue with workflow run details

For SynthaTrial-specific issues:
1. Review root README (Troubleshooting section)
2. Check container logs: `make logs`
3. Run local validation: `make test`
4. Consult implementation documentation
