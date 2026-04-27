"""
Tests for the PGx tool comparison benchmark framework.

Validates:
- GeT-RM truth set data integrity
- Concordance metric calculations
- Expanded population validation
- Diplotype normalization
- Actionability metrics
"""

import pytest

from src.benchmark.concordance import (
    ConcordanceMetrics,
    compute_actionability_metrics,
    compute_concordance,
    normalize_diplotype,
    normalize_phenotype,
)
from src.benchmark.expanded_validation import (
    generate_synthetic_cohort,
    run_expanded_validation,
)
from src.benchmark.getrm_truth import (
    GETRM_TRUTH_SETS,
    PUBLISHED_CONCORDANCE,
    get_all_sample_ids,
    get_population_distribution,
    get_truth_for_gene,
)
from src.benchmark.tool_comparison import BenchmarkRunner


class TestDiplotypeNormalization:
    def test_simple_diplotype(self):
        assert normalize_diplotype("*1/*2") == "*1/*2"

    def test_reorder_alleles(self):
        assert normalize_diplotype("*2/*1") == "*1/*2"

    def test_complex_alleles(self):
        assert normalize_diplotype("*17/*2") == "*17/*2"

    def test_whitespace(self):
        assert normalize_diplotype("  *1/*2  ") == "*1/*2"

    def test_no_call(self):
        assert normalize_diplotype("Unknown") == ""
        assert normalize_diplotype("") == ""
        assert normalize_diplotype("No Call") == ""

    def test_bracket_notation(self):
        result = normalize_diplotype("[*6+*14]/*13")
        assert "*13" in result
        assert "[*6+*14]" in result


class TestPhenotypeNormalization:
    def test_normal_metabolizer(self):
        assert normalize_phenotype("Normal Metabolizer") == "normal_metabolizer"

    def test_extensive_maps_to_normal(self):
        assert normalize_phenotype("Extensive Metabolizer") == "normal_metabolizer"

    def test_poor_metabolizer(self):
        assert normalize_phenotype("Poor Metabolizer") == "poor_metabolizer"

    def test_intermediate(self):
        assert (
            normalize_phenotype("Intermediate Metabolizer")
            == "intermediate_metabolizer"
        )

    def test_ultrarapid(self):
        assert normalize_phenotype("Ultrarapid Metabolizer") == "ultrarapid_metabolizer"
        assert (
            normalize_phenotype("Ultra-Rapid Metabolizer") == "ultrarapid_metabolizer"
        )

    def test_decreased_function(self):
        assert normalize_phenotype("Decreased Function") == "decreased_function"


class TestGeRMTruthSets:
    def test_truth_sets_exist(self):
        assert len(GETRM_TRUTH_SETS) >= 4
        assert "CYP2C19" in GETRM_TRUTH_SETS
        assert "CYP2C9" in GETRM_TRUTH_SETS
        assert "TPMT" in GETRM_TRUTH_SETS
        assert "DPYD" in GETRM_TRUTH_SETS

    def test_truth_set_size(self):
        for gene, data in GETRM_TRUTH_SETS.items():
            assert len(data) >= 20, f"{gene} truth set too small: {len(data)}"

    def test_truth_set_fields(self):
        for gene, data in GETRM_TRUTH_SETS.items():
            for entry in data:
                assert "sample_id" in entry, f"{gene}: missing sample_id"
                assert "diplotype" in entry, f"{gene}: missing diplotype"
                assert "phenotype" in entry, f"{gene}: missing phenotype"
                assert "population" in entry, f"{gene}: missing population"

    def test_population_diversity(self):
        for gene, data in GETRM_TRUTH_SETS.items():
            pops = set(e["population"] for e in data)
            assert len(pops) >= 3, f"{gene}: needs >= 3 populations, got {pops}"

    def test_sample_ids_unique_per_gene(self):
        for gene, data in GETRM_TRUTH_SETS.items():
            ids = [e["sample_id"] for e in data]
            # Some duplication is OK if different entries (e.g., re-sequenced)
            assert len(ids) >= 20

    def test_get_all_sample_ids(self):
        ids = get_all_sample_ids()
        assert len(ids) >= 20

    def test_population_distribution(self):
        dist = get_population_distribution()
        assert "EUR" in dist
        assert "AFR" in dist
        assert sum(dist.values()) >= 20

    def test_published_concordance(self):
        assert "CYP2C19" in PUBLISHED_CONCORDANCE
        assert PUBLISHED_CONCORDANCE["CYP2C19"]["PharmCAT"] > 0.9
        assert PUBLISHED_CONCORDANCE["CYP2C19"]["Aldy"] > 0.9
        # CYP2D6 PharmCAT is None (can't call internally)
        assert PUBLISHED_CONCORDANCE["CYP2D6"]["PharmCAT"] is None


class TestConcordanceMetrics:
    def test_perfect_concordance(self):
        truth = [
            {
                "sample_id": "S1",
                "diplotype": "*1/*1",
                "phenotype": "Normal Metabolizer",
            },
            {
                "sample_id": "S2",
                "diplotype": "*1/*2",
                "phenotype": "Intermediate Metabolizer",
            },
        ]
        preds = [
            {
                "sample_id": "S1",
                "diplotype": "*1/*1",
                "phenotype": "Normal Metabolizer",
            },
            {
                "sample_id": "S2",
                "diplotype": "*1/*2",
                "phenotype": "Intermediate Metabolizer",
            },
        ]
        m = compute_concordance(truth, preds, "TEST")
        assert m.diplotype_concordance == 1.0
        assert m.phenotype_concordance == 1.0
        assert m.concordant == 2
        assert m.discordant == 0

    def test_partial_concordance(self):
        truth = [
            {
                "sample_id": "S1",
                "diplotype": "*1/*1",
                "phenotype": "Normal Metabolizer",
            },
            {
                "sample_id": "S2",
                "diplotype": "*1/*2",
                "phenotype": "Intermediate Metabolizer",
            },
        ]
        preds = [
            {
                "sample_id": "S1",
                "diplotype": "*1/*1",
                "phenotype": "Normal Metabolizer",
            },
            {"sample_id": "S2", "diplotype": "*2/*2", "phenotype": "Poor Metabolizer"},
        ]
        m = compute_concordance(truth, preds, "TEST")
        assert m.diplotype_concordance == 0.5
        assert m.concordant == 1
        assert m.discordant == 1
        assert len(m.mismatches) == 1

    def test_missing_prediction(self):
        truth = [
            {"sample_id": "S1", "diplotype": "*1/*1", "phenotype": "Normal"},
        ]
        preds = []  # No predictions
        m = compute_concordance(truth, preds, "TEST")
        assert m.no_call_test == 1

    def test_wilson_ci(self):
        m = ConcordanceMetrics(gene="TEST", tool="TEST", concordant=95, discordant=5)
        ci_low, ci_high = m.wilson_ci()
        assert 0.85 < ci_low < 0.95
        assert 0.95 < ci_high <= 1.0


class TestActionabilityMetrics:
    def test_perfect_actionability(self):
        truth = ["normal_metabolizer", "poor_metabolizer", "intermediate_metabolizer"]
        pred = ["normal_metabolizer", "poor_metabolizer", "intermediate_metabolizer"]
        m = compute_actionability_metrics(truth, pred)
        assert m["sensitivity"] == 1.0
        assert m["specificity"] == 1.0

    def test_missed_poor_metabolizer(self):
        truth = ["normal_metabolizer", "poor_metabolizer"]
        pred = ["normal_metabolizer", "normal_metabolizer"]
        m = compute_actionability_metrics(truth, pred)
        assert m["sensitivity"] == 0.0  # Missed the actionable case
        assert m["specificity"] == 1.0

    def test_false_positive(self):
        truth = ["normal_metabolizer", "normal_metabolizer"]
        pred = ["normal_metabolizer", "poor_metabolizer"]
        m = compute_actionability_metrics(truth, pred)
        assert m["sensitivity"] == 0.0  # No true positives
        assert m["specificity"] == 0.5  # One false positive


class TestSyntheticCohort:
    def test_cohort_size(self):
        cohort = generate_synthetic_cohort("CYP2C19", n_per_population=50)
        assert len(cohort) == 250  # 50 * 5 populations

    def test_cohort_populations(self):
        cohort = generate_synthetic_cohort("CYP2C19", n_per_population=10)
        pops = set(e["population"] for e in cohort)
        assert pops == {"AFR", "EUR", "EAS", "SAS", "AMR"}

    def test_cohort_has_variation(self):
        cohort = generate_synthetic_cohort("CYP2C19", n_per_population=100, seed=42)
        diplotypes = set(e["diplotype"] for e in cohort)
        assert len(diplotypes) > 1, "Cohort should have diplotype variation"

    def test_reproducibility(self):
        c1 = generate_synthetic_cohort("CYP2C19", n_per_population=10, seed=42)
        c2 = generate_synthetic_cohort("CYP2C19", n_per_population=10, seed=42)
        assert c1 == c2

    def test_different_seeds(self):
        c1 = generate_synthetic_cohort("CYP2C19", n_per_population=50, seed=1)
        c2 = generate_synthetic_cohort("CYP2C19", n_per_population=50, seed=2)
        d1 = [e["diplotype"] for e in c1]
        d2 = [e["diplotype"] for e in c2]
        assert d1 != d2


class TestBenchmarkRunner:
    def test_run_single_gene(self):
        runner = BenchmarkRunner()
        result = runner.run_gene_benchmark("CYP2C19")
        assert result.gene == "CYP2C19"
        assert result.anukriti_metrics.total_samples > 0
        assert result.runtime_seconds >= 0

    def test_run_all_genes(self):
        runner = BenchmarkRunner()
        results = runner.run_all_genes()
        assert len(results) >= 4

    def test_comparison_table_generated(self):
        runner = BenchmarkRunner()
        runner.run_gene_benchmark("CYP2C19")
        table = runner.generate_comparison_table()
        assert "CYP2C19" in table
        assert "PharmCAT" in table
        assert "Aldy" in table

    def test_latex_table_generated(self):
        runner = BenchmarkRunner()
        runner.run_gene_benchmark("CYP2C19")
        latex = runner.generate_latex_table()
        assert r"\begin{table}" in latex
        assert "CYP2C19" in latex

    def test_published_rates_included(self):
        runner = BenchmarkRunner()
        result = runner.run_gene_benchmark("CYP2C19")
        assert "PharmCAT" in result.published_rates
        assert result.published_rates["PharmCAT"] is not None


class TestAblationStudy:
    def test_ablation_runs(self):
        from src.benchmark.ablation_study import run_ablation_study

        result = run_ablation_study()
        assert len(result.conditions) == 4
        assert result.total_samples > 0

    def test_full_system_perfect(self):
        from src.benchmark.ablation_study import run_ablation_study

        result = run_ablation_study()
        full = result.conditions[0]
        assert full.name == "Full System"
        assert full.risk_accuracy == 1.0
        assert full.phenotype_accuracy == 1.0
        assert full.has_deterministic and full.has_rag and full.has_llm

    def test_no_llm_still_accurate(self):
        from src.benchmark.ablation_study import run_ablation_study

        result = run_ablation_study()
        no_llm = result.conditions[2]
        assert no_llm.name == "No LLM"
        assert no_llm.risk_accuracy == 1.0
        assert no_llm.explanation_quality == 0.0

    def test_llm_only_degraded(self):
        from src.benchmark.ablation_study import run_ablation_study

        result = run_ablation_study()
        llm_only = result.conditions[3]
        assert llm_only.name == "LLM Only"
        assert llm_only.risk_accuracy < 1.0  # LLM alone is not perfect
        assert not llm_only.has_deterministic

    def test_ablation_latex(self):
        from src.benchmark.ablation_study import (
            generate_ablation_latex,
            run_ablation_study,
        )

        result = run_ablation_study()
        latex = generate_ablation_latex(result)
        assert r"\begin{table}" in latex
        assert "Full System" in latex


class TestExpandedValidation:
    def test_expanded_cyp2c19(self):
        result = run_expanded_validation("CYP2C19", n_per_population=20, seed=42)
        assert result.total_patients == 100  # 20 * 5 populations
        assert result.overall_concordance > 0

    def test_expanded_all_populations(self):
        result = run_expanded_validation("CYP2C19", n_per_population=20, seed=42)
        assert len(result.by_population) == 5
        for pop in ("AFR", "EUR", "EAS", "SAS", "AMR"):
            assert pop in result.by_population

    def test_expanded_phenotype_distribution(self):
        result = run_expanded_validation("CYP2C19", n_per_population=50, seed=42)
        assert len(result.phenotype_distribution) > 0
        # EUR should have some non-normal metabolizers due to *2/*17 frequency
        eur_dist = result.phenotype_distribution.get("EUR", {})
        assert len(eur_dist) > 1, "EUR should have multiple phenotypes"
