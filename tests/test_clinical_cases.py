"""Tests for clinical case validation using published case reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pytest

from src.benchmark.clinical_cases import (
    ClinicalCase,
    ClinicalValidationResult,
    generate_latex_table,
    load_clinical_cases,
    validate_clinical_cases,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PGX_DIR = DATA_DIR / "pgx" / "cpic"
CASES_PATH = DATA_DIR / "clinical_cases" / "published_cases.json"


def _load_phenotype_table(filename: str) -> Dict[str, str]:
    """Load a CPIC phenotype JSON, stripping metadata keys."""
    path = PGX_DIR / filename
    with open(path) as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _build_full_lookup() -> Dict[str, Dict[str, str]]:
    """Build complete phenotype lookup from all available CPIC tables."""
    lookup: Dict[str, Dict[str, str]] = {}

    # Standard star-allele-based genes
    gene_files = {
        "CYP2C19": "cyp2c19_phenotypes.json",
        "CYP2C9": "cyp2c9_phenotypes.json",
        "DPYD": "dpyd_phenotypes.json",
        "TPMT": "tpmt_phenotypes.json",
    }
    for gene, filename in gene_files.items():
        lookup[gene] = _load_phenotype_table(filename)

    # SLCO1B1: genotype-based (TT/TC/CC)
    slco_path = PGX_DIR / "slco1b1_phenotypes.json"
    with open(slco_path) as f:
        slco_data = json.load(f)
    rs_data = slco_data.get("rs4149056", {})
    lookup["SLCO1B1"] = {gt: info["phenotype"] for gt, info in rs_data.items()}

    # VKORC1: hardcoded from warfarin_caller (rs9923231 genotype)
    lookup["VKORC1"] = {
        "GG": "Normal Sensitivity",
        "GA": "Intermediate Sensitivity",
        "AG": "Intermediate Sensitivity",
        "AA": "High Sensitivity",
    }

    # CYP2D6: common diplotypes (no phenotype JSON exists)
    lookup["CYP2D6"] = {
        "*1/*1": "Normal Metabolizer",
        "*1/*2": "Normal Metabolizer",
        "*2/*2": "Normal Metabolizer",
        "*1/*4": "Intermediate Metabolizer",
        "*4/*4": "Poor Metabolizer",
        "*4/*5": "Poor Metabolizer",
        "*5/*5": "Poor Metabolizer",
        "*1/*1x3": "Ultrarapid Metabolizer",
        "*2/*2x2": "Ultrarapid Metabolizer",
        "*1/*1xN": "Ultrarapid Metabolizer",
    }

    # UGT1A1: common diplotypes (no phenotype JSON exists)
    lookup["UGT1A1"] = {
        "*1/*1": "Normal Metabolizer",
        "*1/*28": "Intermediate Metabolizer",
        "*28/*28": "Poor Metabolizer",
        "*1/*6": "Intermediate Metabolizer",
        "*6/*6": "Poor Metabolizer",
    }

    return lookup


class TestClinicalCasesDataFile:
    """Test the published cases JSON file."""

    def test_cases_file_exists(self) -> None:
        assert CASES_PATH.exists(), "published_cases.json not found"

    def test_cases_file_valid_json(self) -> None:
        with open(CASES_PATH) as f:
            data = json.load(f)
        assert "cases" in data
        assert len(data["cases"]) >= 10

    def test_all_cases_have_required_fields(self) -> None:
        with open(CASES_PATH) as f:
            data = json.load(f)
        required = {
            "case_id",
            "gene",
            "diplotype",
            "phenotype",
            "drug",
            "clinical_outcome",
            "expected_risk",
        }
        for case in data["cases"]:
            missing = required - set(case.keys())
            assert not missing, f"Case {case.get('case_id', '?')} missing: {missing}"

    def test_case_ids_unique(self) -> None:
        with open(CASES_PATH) as f:
            data = json.load(f)
        ids = [c["case_id"] for c in data["cases"]]
        assert len(ids) == len(set(ids)), "Duplicate case IDs found"

    def test_all_genes_covered(self) -> None:
        with open(CASES_PATH) as f:
            data = json.load(f)
        genes = {c["gene"] for c in data["cases"]}
        expected = {"CYP2D6", "CYP2C19", "CYP2C9", "DPYD", "TPMT", "SLCO1B1", "VKORC1"}
        assert expected.issubset(genes), f"Missing genes: {expected - genes}"


class TestLoadClinicalCases:
    """Test loading cases from JSON."""

    def test_load_all_cases(self) -> None:
        cases = load_clinical_cases()
        assert len(cases) >= 10

    def test_load_with_gene_filter(self) -> None:
        cases = load_clinical_cases(gene_filter="CYP2C19")
        assert all(c.gene == "CYP2C19" for c in cases)
        assert len(cases) >= 2

    def test_case_object_fields(self) -> None:
        cases = load_clinical_cases()
        case = cases[0]
        assert isinstance(case, ClinicalCase)
        assert case.case_id
        assert case.gene
        assert case.diplotype
        assert case.drug


class TestValidateClinicalCases:
    """Test validation against phenotype lookup tables."""

    @pytest.fixture()
    def lookup(self) -> Dict[str, Dict[str, str]]:
        return _build_full_lookup()

    @pytest.fixture()
    def cases(self) -> list:
        return load_clinical_cases()

    def test_validate_all_cases(self, cases: list, lookup: dict) -> None:
        result = validate_clinical_cases(cases, lookup)
        assert result.total_cases == len(cases)
        assert result.total_cases >= 10

    def test_high_concordance(self, cases: list, lookup: dict) -> None:
        result = validate_clinical_cases(cases, lookup)
        assert result.concordance >= 0.85, (
            f"Concordance {result.concordance:.1%} below 85% threshold. "
            f"Mismatches: {result.mismatches}"
        )

    def test_cyp2c19_cases_concordant(self, lookup: dict) -> None:
        cases = load_clinical_cases(gene_filter="CYP2C19")
        result = validate_clinical_cases(cases, lookup)
        assert result.concordance == 1.0, f"CYP2C19 mismatches: {result.mismatches}"

    def test_cyp2c9_cases_concordant(self, lookup: dict) -> None:
        cases = load_clinical_cases(gene_filter="CYP2C9")
        result = validate_clinical_cases(cases, lookup)
        assert result.concordance == 1.0, f"CYP2C9 mismatches: {result.mismatches}"

    def test_dpyd_cases_concordant(self, lookup: dict) -> None:
        cases = load_clinical_cases(gene_filter="DPYD")
        result = validate_clinical_cases(cases, lookup)
        assert result.concordance == 1.0, f"DPYD mismatches: {result.mismatches}"

    def test_tpmt_cases_concordant(self, lookup: dict) -> None:
        cases = load_clinical_cases(gene_filter="TPMT")
        result = validate_clinical_cases(cases, lookup)
        assert result.concordance == 1.0, f"TPMT mismatches: {result.mismatches}"

    def test_slco1b1_cases_concordant(self, lookup: dict) -> None:
        cases = load_clinical_cases(gene_filter="SLCO1B1")
        result = validate_clinical_cases(cases, lookup)
        assert result.concordance == 1.0, f"SLCO1B1 mismatches: {result.mismatches}"

    def test_cyp2d6_cases_concordant(self, lookup: dict) -> None:
        cases = load_clinical_cases(gene_filter="CYP2D6")
        result = validate_clinical_cases(cases, lookup)
        assert result.concordance == 1.0, f"CYP2D6 mismatches: {result.mismatches}"

    def test_vkorc1_cases_concordant(self, lookup: dict) -> None:
        cases = load_clinical_cases(gene_filter="VKORC1")
        result = validate_clinical_cases(cases, lookup)
        assert result.concordance == 1.0, f"VKORC1 mismatches: {result.mismatches}"


class TestClinicalValidationResult:
    """Test result formatting."""

    def test_summary_table(self) -> None:
        lookup = _build_full_lookup()
        cases = load_clinical_cases()
        result = validate_clinical_cases(cases, lookup)
        table = result.summary_table()
        assert "CLINICAL CASE VALIDATION" in table
        assert "concordance" in table

    def test_to_dict(self) -> None:
        lookup = _build_full_lookup()
        cases = load_clinical_cases()
        result = validate_clinical_cases(cases, lookup)
        d = result.to_dict()
        assert "total_cases" in d
        assert "concordance" in d
        assert "cases" in d

    def test_latex_table(self) -> None:
        lookup = _build_full_lookup()
        cases = load_clinical_cases()
        result = validate_clinical_cases(cases, lookup)
        latex = generate_latex_table(result)
        assert r"\begin{table}" in latex
        assert r"clinical-cases" in latex
        assert r"\end{table}" in latex
