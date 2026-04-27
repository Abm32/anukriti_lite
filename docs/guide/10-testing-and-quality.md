# Chapter 10: Testing & Quality Assurance

Anukriti has a comprehensive test suite with 400+ tests across unit, integration, and
property-based testing categories.

## 10.1 Test Suite Overview

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html

# Run specific category
python -m pytest tests/ -m "not integration" -v   # Unit tests only
python -m pytest tests/ -m integration -v          # Integration only
python -m pytest tests/ -m property -v             # Property-based only
```

### Test File Inventory (27 files)

| File | Tests | Category | Focus |
|------|-------|----------|-------|
| `test_core_callers.py` | 77 | Unit | Allele calling, phenotype lookup |
| `test_benchmark_comparison.py` | 45 | Unit | Benchmark framework |
| `test_clinical_cases.py` | 20 | Unit | Published case validation |
| `test_cyp2d6_cnv.py` | ~10 | Unit | CYP2D6 structural variants |
| `test_tpmt_dpyd.py` | ~10 | Unit | TPMT/DPYD callers |
| `test_new_features.py` | ~15 | Unit | New feature validation |
| `test_cicd_pipeline_properties.py` | ~30 | Property | CI/CD automation |
| `test_security_monitoring_properties.py` | ~20 | Property | Security scanning |
| `test_security_scanner_properties.py` | ~10 | Property | Scanner behavior |
| `test_data_initialization_properties.py` | ~15 | Property | Data validation |
| `test_dev_environment_properties.py` | ~10 | Property | Dev environment |
| `test_vcf_download_properties.py` | ~15 | Property | VCF download |
| `test_http_https_redirection_properties.py` | ~10 | Property | HTTPS |
| `test_ssl_manager_properties.py` | ~10 | Property | SSL certificates |
| `test_complete_workflow_integration.py` | ~10 | Integration | End-to-end |
| `test_docker_environment_integration.py` | ~10 | Integration | Docker |
| `test_ssl_integration.py` | ~10 | Integration | SSL/TLS |
| `test_security_scanner_integration.py` | 13 | Integration | Security |
| `test_github_actions_integration.py` | ~10 | Integration | GitHub Actions |
| `test_deploy_to_registry_integration.py` | ~10 | Integration | Registry |
| `test_multi_arch_build_integration.py` | ~10 | Integration | Multi-arch |
| `test_vcf_download_integration.py` | ~10 | Integration | VCF download |
| `test_chembl_setup_integration.py` | ~10 | Integration | ChEMBL |
| `test_containerized_testing_integration.py` | ~10 | Integration | Containers |
| `test_containerized_enhanced_features.py` | ~10 | Integration | Enhanced containers |
| `test_integration_runner.py` | ~5 | Integration | Test runner |
| `quick_test.py` | ~5 | Smoke | Quick validation |
| `validation_tests.py` | ~10 | Validation | General checks |

## 10.2 Core PGx Tests (`tests/test_core_callers.py`)

77 tests covering the deterministic engine:

### Allele Calling Tests

```python
class TestAltDosage:
    """Test VCF genotype → ALT dosage conversion."""
    def test_homozygous_ref(self):
        assert alt_dosage("0/0") == 0

    def test_heterozygous(self):
        assert alt_dosage("0/1") == 1

    def test_homozygous_alt(self):
        assert alt_dosage("1/1") == 2

    def test_phased_genotype(self):
        assert alt_dosage("0|1") == 1

class TestGenotypeToAlleles:
    """Test REF/ALT/GT → actual bases conversion."""
    def test_het_ref_alt(self):
        assert _genotype_to_alleles("G", "A", "0/1") == ("G", "A")

class TestCallStarAlleles:
    """Test variant → star allele calling."""
    def test_cyp2c19_star2(self):
        variants = {"rs4244285": ("G", "A", "0/1")}
        result = call_star_alleles(variants, "CYP2C19")
        assert "*2" in result["alleles"]

    def test_no_variants_gives_star1_star1(self):
        result = call_star_alleles({}, "CYP2C19")
        assert result["diplotype"] == "*1/*1"
```

### Diplotype and Phenotype Tests

```python
class TestBuildDiplotype:
    """Test diplotype normalization."""
    def test_numeric_sorting(self):
        assert build_diplotype(["*17", "*2"], "CYP2C19") == "*2/*17"

    def test_star1_always_first(self):
        assert build_diplotype(["*3", "*1"], "CYP2C9") == "*1/*3"

class TestDiplotypeToPhenotype:
    """Test CPIC phenotype lookup."""
    def test_cyp2c19_poor(self):
        result = diplotype_to_phenotype("*2/*2", "CYP2C19")
        assert result == "Poor Metabolizer"

    def test_cyp2c19_normal(self):
        result = diplotype_to_phenotype("*1/*1", "CYP2C19")
        assert result == "Normal Metabolizer"
```

### Gene-Specific Caller Tests

```python
class TestWarfarinCaller:
    def test_cyp2c9_star1_star3(self):
        result = call_cyp2c9({"rs1057910": ("A", "C", "0/1")})
        assert result["diplotype"] == "*1/*3"

    def test_vkorc1_heterozygous(self):
        result = call_vkorc1({"rs9923231": ("G", "A", "0/1")})
        assert result["genotype"] == "GA"

class TestSlco1b1Caller:
    def test_normal_function(self):
        result = interpret_slco1b1({"rs4149056": ("T", "T", "0/0")})
        assert result["phenotype"] == "Normal Function"

    def test_decreased_function(self):
        result = interpret_slco1b1({"rs4149056": ("T", "C", "0/1")})
        assert result["phenotype"] == "Decreased Function"
```

### Load Error Tests

```python
class TestLoadErrors:
    """Test graceful handling of missing data files."""
    def test_missing_pharmvar_file(self):
        with pytest.raises(FileNotFoundError):
            load_pharmvar_alleles("NONEXISTENT_GENE")

    def test_missing_phenotype_file(self):
        with pytest.raises(FileNotFoundError):
            load_cpic_translation_for_gene("NONEXISTENT_GENE")
```

## 10.3 Benchmark Tests (`tests/test_benchmark_comparison.py`)

45 tests for the validation framework:

```python
class TestConcordanceMetrics:
    """Test statistical metrics."""
    def test_perfect_concordance(self):
        metrics = compute_concordance(calls, truth, "CYP2C19")
        assert metrics.concordance_rate == 1.0

    def test_wilson_ci(self):
        lower, upper = _wilson_ci(30, 30)
        assert lower > 0.88  # 88.6% lower bound

    def test_normalize_diplotype(self):
        assert normalize_diplotype("*2/*1") == "*1/*2"
        assert normalize_diplotype("CYP2C19 *1/*2") == "*1/*2"

class TestGetrmTruthSets:
    """Test ground truth data integrity."""
    def test_cyp2c19_sample_count(self):
        truth = get_truth_for_gene("CYP2C19")
        assert len(truth) == 30

    def test_all_genes_have_truth(self):
        for gene in SUPPORTED_GENES:
            assert len(get_truth_for_gene(gene)) == 30

class TestBenchmarkRunner:
    """Test benchmark execution."""
    def test_gene_benchmark(self):
        runner = BenchmarkRunner()
        result = runner.run_gene_benchmark("CYP2C19")
        assert result.anukriti_metrics.concordance_rate == 1.0

class TestAblationStudy:
    """Test ablation conditions."""
    def test_full_system_accuracy(self):
        result = run_ablation_study()
        assert result.conditions["full"].risk_accuracy == 1.0

    def test_llm_only_lower_accuracy(self):
        result = run_ablation_study()
        assert result.conditions["llm_only"].risk_accuracy < 0.80
```

## 10.4 Clinical Case Tests (`tests/test_clinical_cases.py`)

20 tests for published case validation:

```python
class TestClinicalCases:
    def test_data_file_exists(self):
        assert Path("data/clinical_cases/published_cases.json").exists()

    def test_load_cases(self):
        cases = load_clinical_cases()
        assert len(cases) == 13

    def test_all_cases_concordant(self):
        results = validate_clinical_cases()
        for result in results:
            assert result.concordant, f"Case {result.case_id} failed"

    def test_per_gene_concordance(self):
        results = validate_clinical_cases()
        genes = set(r.gene for r in results)
        for gene in genes:
            gene_results = [r for r in results if r.gene == gene]
            concordance = sum(r.concordant for r in gene_results) / len(gene_results)
            assert concordance == 1.0, f"{gene} concordance: {concordance}"
```

## 10.5 Property-Based Testing (Hypothesis)

Multiple test files use the Hypothesis framework for property-based testing:

```python
from hypothesis import given, strategies as st, settings, HealthCheck

class TestCICDPipelineProperties:
    @given(
        target=st.sampled_from(["dev", "prod", "dev-enhanced"]),
        platform=st.sampled_from(["linux/amd64", "linux/arm64"])
    )
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_build_config_always_valid(self, target, platform):
        config = BuildConfig(target=target, platform=platform)
        assert config.is_valid()

    @given(environment=environment_names(), images=image_names(), tags=image_tags())
    @settings(max_examples=25, deadline=None, derandomize=True)
    def test_deployment_config_valid(self, environment, images, tags):
        config = DeploymentConfig(environment=environment, images=images, tags=tags)
        # Property: all valid inputs produce valid configs
        assert config.validate()
```

Key features:
- `derandomize=True` for reproducible CI runs
- Custom strategies for domain-specific data
- `deadline=None` for complex test scenarios
- Health check suppression for slow tests

## 10.6 Integration Tests

### Docker Environment (`test_docker_environment_integration.py`)

```python
class TestDockerEnvironment:
    def test_dockerfile_exists(self):
        assert Path("Dockerfile").exists()

    def test_compose_files_valid(self):
        for f in ["docker-compose.yml", "docker-compose.dev.yml", "docker-compose.prod.yml"]:
            assert Path(f).exists()

    def test_container_startup(self):
        # Build and start container, verify health endpoint
        ...
```

### Security Scanner (`test_security_scanner_integration.py`)

```python
class TestSecurityScannerIntegration:
    def test_scanner_initialization_without_tools(self):
        scanner = SecurityScanner(tools=[])
        assert scanner.available_tools == []

    def test_trivy_scan_mock_success(self):
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = MockResult(stdout='{"Results": []}')
            result = scanner.scan_trivy("test-image")
            assert result["status"] == "pass"
```

### Complete Workflow (`test_complete_workflow_integration.py`)

End-to-end pipeline testing:
```python
class TestCompleteWorkflow:
    def test_vcf_to_report(self):
        # 1. Parse VCF
        # 2. Extract sample
        # 3. Call all genes
        # 4. Generate patient profile
        # 5. Run LLM explanation (mocked)
        # 6. Generate PDF report
        # 7. Verify all outputs
```

## 10.7 Test Configuration

### `pytest.ini`

```ini
[pytest]
testpaths = tests
markers =
    integration: Integration tests (may require external services)
    property: Property-based tests (Hypothesis)
    slow: Tests that take > 30 seconds
addopts = --timeout=120
```

### Test Reports

Multiple output formats supported:

```bash
# HTML report
pytest --html=tests/reports/report.html

# JSON report
pytest --json-report --json-report-file=tests/reports/report.json

# JUnit XML (for CI/CD)
pytest --junitxml=tests/reports/junit.xml

# Coverage
pytest --cov=src --cov-report=html:tests/reports/coverage
```

## 10.8 Code Quality Tools

### Pre-Commit Hooks

Every commit runs:

| Hook | Purpose |
|------|---------|
| black | Code formatting (consistent style) |
| isort | Import sorting |
| flake8 | Linting (PEP 8, complexity) |
| mypy | Type checking |
| bandit | Security scanning (code) |
| trim trailing whitespace | Clean whitespace |
| check yaml/json/toml | Config file validation |
| check python ast | Syntax validation |
| detect private key | Prevent credential commits |
| check for merge conflicts | Catch unresolved conflicts |
| check for large files | Prevent binary bloat |

### Configuration

- `black`: Default settings (88-char line length)
- `isort`: Compatible with black profile
- `flake8`: Max complexity 10, line length 127 (CI/CD)
- `mypy`: Strict mode for typed modules
- `bandit`: Scans for common Python security issues

## 10.9 Running the Full Test Suite

```bash
# Quick smoke test
python -m pytest tests/quick_test.py -v

# Core PGx tests (fastest)
python -m pytest tests/test_core_callers.py -v

# All unit tests (skip integration)
python -m pytest tests/ -m "not integration" -v

# Full suite (all 400+ tests)
python -m pytest tests/ -v --timeout=600

# With parallel execution
python -m pytest tests/ -n auto -v
```

### Expected Results

```
400+ passed, 0 failed (when all services mocked)
~10 tests may be flaky (security scanner, Hypothesis timing)
Typical runtime: 5-9 minutes for full suite
```

## 10.10 Continuous Integration

Tests run automatically on:
- Every push to `main`
- Every pull request
- Daily security scans (2 AM UTC)

CI matrix:
- Python 3.10, 3.11
- Test categories: unit, integration, property
- Docker build targets: dev, prod, dev-enhanced
- Platforms: linux/amd64, linux/arm64

---

**End of Guide**

Return to [Table of Contents](README.md)
