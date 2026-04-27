# Security Scanning Workflow Documentation

## Overview

The SynthaTrial Security Scanning Workflow (`security-scan.yml`) provides comprehensive automated security analysis for the entire application stack, including code, dependencies, containers, and infrastructure. This workflow implements enterprise-grade security scanning with configurable thresholds, automated issue creation, and detailed reporting.

## Features

### 🔍 Comprehensive Security Analysis
- **Code Security**: Static analysis with Bandit, Semgrep, secret detection, and dead code analysis
- **Dependency Security**: Vulnerability scanning with Safety, pip-audit, and OSV scanner
- **Container Security**: Multi-scanner analysis with Trivy, Grype, and Docker Scout
- **Infrastructure Security**: Configuration analysis with Checkov and Hadolint

### 🚨 Automated Vulnerability Management
- **Configurable Thresholds**: Set minimum severity levels for build blocking
- **Automated Issue Creation**: Create GitHub issues for critical vulnerabilities
- **Build Control**: Block builds when security thresholds are exceeded
- **Detailed Reporting**: Comprehensive security reports with remediation guidance

### 📊 Advanced Reporting
- **Multiple Output Formats**: JSON, SARIF, HTML, and Markdown reports
- **SBOM Generation**: Software Bill of Materials for compliance
- **GitHub Security Integration**: Upload SARIF results to GitHub Security tab
- **Comprehensive Summaries**: Executive-level security posture reports

## Workflow Triggers

### Automatic Triggers
```yaml
# Daily scheduled scans
schedule:
  - cron: '0 2 * * *'  # 2 AM UTC daily

# Code changes that affect security
push:
  branches: [ main, develop ]
  paths:
    - 'src/**'
    - 'scripts/**'
    - 'requirements.txt'
    - 'Dockerfile*'
    - 'docker/**'
    - '.github/workflows/**'

# Pull request validation
pull_request:
  branches: [ main, develop ]
  paths: [same as push]
```

### Manual Triggers
```yaml
workflow_dispatch:
  inputs:
    scan_type: [all, code, dependencies, containers, infrastructure]
    severity_threshold: [low, medium, high, critical]
    fail_on_high: [true, false]
    create_issues: [true, false]
    scan_all_images: [true, false]
```

## Job Architecture

### 1. Security Setup (`security-setup`)
- Configures scan parameters based on inputs and triggers
- Creates security reports directory
- Sets up job dependencies and outputs

### 2. Code Security Analysis (`code-security`)
- **Bandit**: Python security linter with custom configuration
- **Semgrep**: Multi-language static analysis with OWASP rules
- **TruffleHog**: Secret detection with verified patterns
- **Vulture**: Dead code analysis for security cleanup

### 3. Dependency Security Analysis (`dependency-security`)
- **Safety**: Python package vulnerability database
- **pip-audit**: OSV database vulnerability scanning
- **OSV Scanner**: Google's Open Source Vulnerabilities database
- **SBOM Generation**: CycloneDX and SPDX formats
- **License Analysis**: Dependency license compliance

### 4. Container Security Analysis (`container-security`)
- **Multi-Image Support**: Scans prod, dev, and dev-enhanced images
- **Trivy**: Comprehensive vulnerability and misconfiguration scanning
- **Grype**: Anchore's vulnerability scanner
- **Docker Scout**: Docker's native security scanning
- **SBOM Generation**: Container software bill of materials

### 5. Infrastructure Security Analysis (`infrastructure-security`)
- **Hadolint**: Dockerfile security and best practices
- **Checkov**: Infrastructure as Code security scanning
- **GitHub Actions**: Workflow security analysis
- **Configuration Review**: Docker Compose and CI/CD security

### 6. Security Validation (`security-validation`)
- **Threshold Enforcement**: Configurable severity-based build blocking
- **Comprehensive Analysis**: Aggregates results from all scanners
- **Pass/Fail Determination**: Controls build pipeline progression
- **Detailed Reporting**: Provides failure reasons and recommendations

### 7. Security Report Generation (`security-report`)
- **Comprehensive Reports**: JSON and Markdown formats
- **Executive Summary**: High-level security posture overview
- **Detailed Findings**: Category-specific vulnerability breakdowns
- **Recommendations**: Actionable remediation guidance
- **Artifact Inventory**: Complete list of generated reports

### 8. Automated Issue Creation (`create-security-issues`)
- **Critical Issue Creation**: Automatic GitHub issues for critical vulnerabilities
- **Dependency Issues**: Separate issues for dependency updates
- **Rich Context**: Includes scan details, recommendations, and artifact links
- **Team Assignment**: Configurable assignees and labels

### 9. Security Notification (`security-notification`)
- **Final Status**: Overall security scan results
- **Build Control**: Fails build if security thresholds exceeded
- **Artifact Summary**: Lists all available security reports
- **Status Reporting**: Comprehensive job result summary

## Configuration

### Environment Variables
```yaml
env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}
  SECURITY_REPORT_DIR: security_reports
  PYTHON_VERSION: '3.10'
```

### Severity Thresholds
- **Critical**: Only critical vulnerabilities block builds
- **High**: High and critical vulnerabilities block builds
- **Medium**: Medium, high, and critical vulnerabilities block builds
- **Low**: All vulnerabilities block builds

### Build Blocking Logic
```python
if fail_on_high == "true":
    if severity_threshold == "critical" and critical_count > 0:
        block_build = True
    elif severity_threshold in ["high", "medium", "low"]:
        if critical_count > 0 or high_count > 0:
            block_build = True
```

## Security Tools Integration

### Static Analysis Tools
- **Bandit**: Python-specific security linter
- **Semgrep**: Multi-language static analysis
- **Hadolint**: Dockerfile linting and security
- **Checkov**: Infrastructure as Code scanning

### Vulnerability Scanners
- **Trivy**: Container and filesystem vulnerability scanning
- **Grype**: Anchore's vulnerability scanner
- **Safety**: Python package vulnerability database
- **pip-audit**: Python package auditing
- **OSV Scanner**: Google's vulnerability database

### Compliance Tools
- **CycloneDX**: SBOM generation for compliance
- **SPDX**: Software Package Data Exchange format
- **SARIF**: Static Analysis Results Interchange Format

## Report Artifacts

### Code Security Reports
- `bandit-report.json/txt/html/csv` - Python security analysis
- `semgrep-*.json/txt/sarif` - Multi-language static analysis
- `trufflehog-secrets.json` - Secret detection results
- `vulture-deadcode.json/txt` - Dead code analysis

### Dependency Security Reports
- `safety-report.json/txt` - Python package vulnerabilities
- `pip-audit-*.json/txt` - Package auditing results
- `osv-*.json/txt` - OSV database results
- `dependency-tree.json/txt` - Dependency analysis
- `licenses.json/md/txt` - License compliance
- `sbom.json/xml` - Software Bill of Materials

### Container Security Reports
- `trivy-*-{image}.json/txt/sarif` - Container vulnerability scans
- `grype-*-{image}.json/txt/sarif` - Anchore vulnerability scans
- `docker-scout-{image}.json/sarif` - Docker security scans
- `sbom-*-{image}.json` - Container SBOM files
- `container-analysis-{image}.json/md` - Security posture analysis

### Infrastructure Security Reports
- `hadolint-*.json/txt` - Dockerfile security analysis
- `checkov-*.json/txt` - Infrastructure configuration scans
- `infrastructure-analysis.json/md` - Security posture summary

### Comprehensive Reports
- `comprehensive-security-report.json` - Complete security analysis
- `security-summary.md` - Executive summary report
- `security-validation-results.json` - Threshold validation results

## Integration with CI/CD

### GitHub Security Integration
```yaml
# Upload SARIF results to GitHub Security tab
- name: Upload SARIF results to GitHub Security
  uses: github/codeql-action/upload-sarif@v2
  with:
    sarif_file: ${{ env.SECURITY_REPORT_DIR }}/semgrep-results.sarif
```

### Build Pipeline Integration
The security workflow integrates with the main CI/CD pipeline:
1. **Pre-deployment**: Security scans run before deployment
2. **Build Blocking**: Critical vulnerabilities prevent deployment
3. **Issue Tracking**: Automated issue creation for vulnerability management
4. **Compliance**: SBOM generation for regulatory requirements

### Pull Request Integration
- **Fast Security Checks**: Lightweight scans on PRs
- **Full Scans**: Comprehensive analysis on main branch
- **Status Checks**: Security results visible in PR status

## Best Practices

### Security Threshold Configuration
```yaml
# Recommended for production
severity_threshold: 'high'
fail_on_high: true
create_issues: true

# Recommended for development
severity_threshold: 'medium'
fail_on_high: false
create_issues: false
```

### Scan Frequency
- **Daily Scheduled Scans**: Catch new vulnerabilities
- **Push-Triggered Scans**: Validate security on code changes
- **PR Scans**: Prevent security regressions

### Issue Management
- **Critical Issues**: Immediate attention required
- **High Issues**: Fix within 7 days
- **Medium/Low Issues**: Include in regular maintenance cycles

## Troubleshooting

### Common Issues

#### Scanner Installation Failures
```bash
# Trivy installation issues
sudo apt-get update && sudo apt-get install trivy

# Grype installation issues
curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh
```

#### Report Generation Failures
- Check Python dependencies are installed
- Verify report directory permissions
- Ensure JSON parsing handles empty results

#### Threshold Validation Issues
- Verify severity mapping between scanners
- Check threshold configuration syntax
- Review validation logic for edge cases

### Performance Optimization
- **Parallel Scanning**: Jobs run in parallel for speed
- **Caching**: Tool installations cached between runs
- **Selective Scanning**: Configure scan types based on changes

## Security Considerations

### Secrets Management
- **No Hardcoded Secrets**: All sensitive data via GitHub Secrets
- **Secret Scanning**: TruffleHog detects exposed secrets
- **Secure Defaults**: Conservative security configurations

### Access Control
- **Workflow Permissions**: Minimal required permissions
- **Issue Creation**: Controlled by workflow inputs
- **Report Access**: Artifacts available to authorized users

### Compliance
- **SBOM Generation**: Software Bill of Materials for compliance
- **Audit Trail**: Complete scan history and results
- **Regulatory Support**: SARIF and SPDX format support

## Future Enhancements

### Planned Features
- **Custom Security Policies**: Organization-specific rules
- **Integration Testing**: Security testing in live environments
- **Automated Remediation**: PR creation for dependency updates
- **Advanced Analytics**: Trend analysis and security metrics

### Tool Additions
- **CodeQL**: GitHub's semantic code analysis
- **Snyk**: Commercial vulnerability scanning
- **OWASP ZAP**: Dynamic application security testing
- **Container Runtime Security**: Runtime vulnerability detection

## Support and Maintenance

### Regular Updates
- **Scanner Updates**: Keep security tools current
- **Rule Updates**: Update security rules and policies
- **Threshold Review**: Adjust thresholds based on findings

### Monitoring
- **Workflow Health**: Monitor scan success rates
- **Performance Metrics**: Track scan duration and resource usage
- **Security Metrics**: Monitor vulnerability trends and resolution times

For questions or issues with the security scanning workflow, please:
1. Check the workflow logs for detailed error information
2. Review the generated security reports for specific findings
3. Consult the troubleshooting section above
4. Create an issue with the `security` and `workflow` labels
