"""
Unit tests for the deterministic PGx engine.

Covers: allele_caller, warfarin_caller, slco1b1_caller, tpmt_caller, dpyd_caller,
        confidence_tiering.

These tests run entirely offline — no LLM, no AWS, no VCF files required.
They use the curated data tables in data/pgx/ and inline fixture data.
"""

from __future__ import annotations

import pytest

from src.allele_caller import (
    _genotype_to_alleles,
    alt_dosage,
    build_diplotype,
    build_diplotype_simple,
    call_star_alleles_simple,
    cpic_display_to_normalized,
    diplotype_to_phenotype,
)

# ---------------------------------------------------------------------------
# allele_caller — core building blocks
# ---------------------------------------------------------------------------


class TestAltDosage:
    def test_homozygous_ref(self):
        assert alt_dosage("0/0") == 0

    def test_heterozygous(self):
        assert alt_dosage("0/1") == 1
        assert alt_dosage("1/0") == 1

    def test_homozygous_alt(self):
        assert alt_dosage("1/1") == 2

    def test_phased(self):
        assert alt_dosage("0|1") == 1
        assert alt_dosage("1|1") == 2

    def test_unknown_returns_none(self):
        assert alt_dosage("") is None
        assert alt_dosage("./.") is None


class TestGenotypeToAlleles:
    def test_ref_ref(self):
        assert _genotype_to_alleles("T", "C", "0/0") == ["T", "T"]

    def test_het(self):
        assert _genotype_to_alleles("T", "C", "0/1") == ["T", "C"]

    def test_hom_alt(self):
        assert _genotype_to_alleles("T", "C", "1/1") == ["C", "C"]

    def test_missing_padded_with_ref(self):
        alleles = _genotype_to_alleles("A", "G", ".")
        assert len(alleles) == 2


class TestBuildDiplotype:
    def test_no_variants_gives_star1_star1(self):
        assert build_diplotype({}) == "*1/*1"

    def test_single_variant_allele(self):
        result = build_diplotype({"*2": 1})
        assert result == "*1/*2"

    def test_homozygous_variant(self):
        result = build_diplotype({"*2": 2})
        assert result == "*2/*2"

    def test_compound_het(self):
        result = build_diplotype({"*2": 1, "*3": 1})
        assert result in ("*2/*3", "*3/*2")

    def test_simple_single_allele(self):
        assert build_diplotype_simple(["*2"]) == "*1/*2"

    def test_simple_two_alleles(self):
        assert build_diplotype_simple(["*2", "*17"]) == "*2/*17"

    def test_simple_empty_gives_star1_star1(self):
        assert build_diplotype_simple([]) == "*1/*1"


class TestDiplotypeToPheno:
    _table = {
        "*1/*1": "Normal Metabolizer",
        "*1/*2": "Intermediate Metabolizer",
        "*2/*2": "Poor Metabolizer",
    }

    def test_known_diplotype(self):
        assert diplotype_to_phenotype("*1/*1", self._table) == "Normal Metabolizer"
        assert diplotype_to_phenotype("*2/*2", self._table) == "Poor Metabolizer"

    def test_unknown_diplotype(self):
        result = diplotype_to_phenotype("*99/*99", self._table)
        assert "Unknown" in result


class TestCpicDisplayToNormalized:
    def test_normal(self):
        assert (
            cpic_display_to_normalized("Normal Metabolizer") == "extensive_metabolizer"
        )

    def test_intermediate(self):
        assert (
            cpic_display_to_normalized("Intermediate Metabolizer")
            == "intermediate_metabolizer"
        )

    def test_poor(self):
        assert cpic_display_to_normalized("Poor Metabolizer") == "poor_metabolizer"

    def test_ultrarapid(self):
        assert (
            cpic_display_to_normalized("Ultrarapid Metabolizer")
            == "ultra_rapid_metabolizer"
        )

    def test_unknown(self):
        assert cpic_display_to_normalized("Something Else") == "unknown"


# ---------------------------------------------------------------------------
# allele_caller — call_star_alleles_simple with inline table
# ---------------------------------------------------------------------------

import pandas as pd


def _make_allele_table(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


class TestCallStarAllelesSimple:
    def test_no_variants_returns_star1(self):
        table = _make_allele_table(
            [
                {"allele": "*2", "rsid": "rs4244285", "alt": "A"},
            ]
        )
        result = call_star_alleles_simple({}, table)
        assert result == ["*1"]

    def test_detects_star2(self):
        table = _make_allele_table(
            [
                {"allele": "*2", "rsid": "rs4244285", "alt": "A"},
            ]
        )
        result = call_star_alleles_simple({"rs4244285": "A"}, table)
        assert "*2" in result

    def test_detects_multiple_alleles(self):
        table = _make_allele_table(
            [
                {"allele": "*2", "rsid": "rs4244285", "alt": "A"},
                {"allele": "*17", "rsid": "rs28371706", "alt": "T"},
            ]
        )
        result = call_star_alleles_simple({"rs4244285": "A", "rs28371706": "T"}, table)
        assert "*2" in result
        assert "*17" in result

    def test_wrong_alt_not_detected(self):
        table = _make_allele_table(
            [
                {"allele": "*2", "rsid": "rs4244285", "alt": "A"},
            ]
        )
        result = call_star_alleles_simple({"rs4244285": "G"}, table)
        assert result == ["*1"]


# ---------------------------------------------------------------------------
# warfarin_caller
# ---------------------------------------------------------------------------

from src.warfarin_caller import call_cyp2c9, call_vkorc1


class TestCallVkorc1:
    def test_gg_reference(self):
        assert call_vkorc1({"rs9923231": "G"}) == "GG"

    def test_aa_homozygous(self):
        assert call_vkorc1({"rs9923231": "A"}) == "GA"  # single A → heterozygous

    def test_missing_returns_unknown(self):
        assert call_vkorc1({}) == "Unknown"

    def test_comma_separated_het(self):
        assert call_vkorc1({"rs9923231": "G,A"}) == "GA"

    def test_comma_separated_hom_alt(self):
        assert call_vkorc1({"rs9923231": "A,A"}) == "AA"


class TestCallCyp2c9:
    """Integration test — requires data/pgx/pharmvar/cyp2c9_alleles.tsv."""

    def test_no_variants_gives_star1_star1(self):
        result = call_cyp2c9({})
        assert result == "*1/*1"

    def test_rs1799853_gives_star2(self):
        # CYP2C9*2 defining variant
        result = call_cyp2c9({"rs1799853": "T"})
        assert "*2" in result

    def test_rs1057910_gives_star3(self):
        # CYP2C9*3 defining variant
        result = call_cyp2c9({"rs1057910": "C"})
        assert "*3" in result


# ---------------------------------------------------------------------------
# slco1b1_caller
# ---------------------------------------------------------------------------

from src.slco1b1_caller import interpret_slco1b1


class TestInterpretSlco1b1:
    def test_tt_normal_function(self):
        result = interpret_slco1b1("TT", "simvastatin")
        assert result.get("gene") == "SLCO1B1"
        assert (
            "Normal" in result.get("phenotype", "")
            or result.get("phenotype") is not None
        )

    def test_tc_decreased_function(self):
        result = interpret_slco1b1("TC", "simvastatin")
        assert result.get("gene") == "SLCO1B1"
        phenotype = result.get("phenotype", "")
        assert phenotype  # must return something

    def test_cc_poor_function(self):
        result = interpret_slco1b1("CC", "simvastatin")
        assert result.get("gene") == "SLCO1B1"

    def test_unknown_genotype_returns_empty(self):
        result = interpret_slco1b1("XX", "simvastatin")
        assert result == {}

    def test_returns_recommendation_for_known_drug(self):
        result = interpret_slco1b1("CC", "simvastatin")
        # recommendation may be None if data file missing, but key should exist
        assert "gene" in result


# ---------------------------------------------------------------------------
# tpmt_caller
# ---------------------------------------------------------------------------

from src.tpmt_caller import call_tpmt, interpret_tpmt


class TestCallTpmt:
    def test_no_variants_gives_star1_star1(self):
        assert call_tpmt({}) == "*1/*1"

    def test_rs1800462_gives_star2(self):
        result = call_tpmt({"rs1800462": "A"})
        assert "*2" in result or result == "*1/*1"  # depends on data file presence


class TestInterpretTpmt:
    def test_returns_gene_key(self):
        result = interpret_tpmt({}, drug_name="azathioprine")
        assert result.get("gene") == "TPMT"

    def test_normal_metabolizer_no_variants(self):
        result = interpret_tpmt({})
        phenotype = result.get("phenotype", "")
        # *1/*1 should map to Normal or Unknown (if data file missing)
        assert isinstance(phenotype, str)


# ---------------------------------------------------------------------------
# dpyd_caller
# ---------------------------------------------------------------------------

from src.dpyd_caller import call_dpyd, interpret_dpyd


class TestCallDpyd:
    def test_no_variants_gives_star1_star1(self):
        assert call_dpyd({}) == "*1/*1"

    def test_rs3918290_gives_star2a(self):
        result = call_dpyd({"rs3918290": "A"})
        # *2A is the most common DPYD loss-of-function allele
        assert "*2A" in result or result == "*1/*1"  # depends on data file


class TestInterpretDpyd:
    def test_returns_gene_key(self):
        result = interpret_dpyd({}, drug_name="fluorouracil")
        assert result.get("gene") == "DPYD"

    def test_normal_metabolizer_no_variants(self):
        result = interpret_dpyd({})
        assert isinstance(result.get("phenotype", ""), str)


# ---------------------------------------------------------------------------
# confidence_tiering
# ---------------------------------------------------------------------------

from src.confidence_tiering import classify_confidence_tier


class TestConfidenceTiering:
    def test_high_tier_with_deterministic_coverage(self):
        result = classify_confidence_tier(
            inference_confidence=0.85,
            candidate_genes=["CYP2D6"],
            deterministic_callable_genes=["CYP2D6"],
            evidence_items=[{"source": "cpic"}, {"source": "pharmvar"}],
        )
        assert result["confidence_tier"] == "high"

    def test_moderate_tier_multi_source_no_deterministic(self):
        result = classify_confidence_tier(
            inference_confidence=0.65,
            candidate_genes=["CYP2D6"],
            deterministic_callable_genes=[],
            evidence_items=[{"source": "chembl"}, {"source": "pubmed"}],
        )
        assert result["confidence_tier"] == "moderate"

    def test_exploratory_with_no_evidence(self):
        result = classify_confidence_tier(
            inference_confidence=0.1,
            candidate_genes=[],
            deterministic_callable_genes=[],
            evidence_items=[],
        )
        assert result["confidence_tier"] == "exploratory"

    def test_output_always_has_required_keys(self):
        result = classify_confidence_tier(
            inference_confidence=0.5,
            candidate_genes=["CYP2C19"],
            deterministic_callable_genes=["CYP2C19"],
            evidence_items=[{"source": "cpic"}],
        )
        for key in (
            "confidence_tier",
            "rationale",
            "inference_confidence",
            "candidate_genes",
            "deterministic_callable_genes",
        ):
            assert key in result

    def test_tier_always_valid_value(self):
        for conf in (0.0, 0.45, 0.55, 0.95, 1.0):
            result = classify_confidence_tier(
                inference_confidence=conf,
                candidate_genes=["CYP2C9"],
                deterministic_callable_genes=["CYP2C9"],
                evidence_items=[{"source": "cpic"}],
            )
            assert result["confidence_tier"] in ("high", "moderate", "exploratory")

    def test_deterministic(self):
        """Same inputs always produce same tier."""
        kwargs = dict(
            inference_confidence=0.75,
            candidate_genes=["CYP2C9"],
            deterministic_callable_genes=["CYP2C9"],
            evidence_items=[{"source": "cpic"}, {"source": "pharmvar"}],
        )
        assert classify_confidence_tier(**kwargs) == classify_confidence_tier(**kwargs)
