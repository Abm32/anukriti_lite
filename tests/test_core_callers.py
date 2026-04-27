"""Comprehensive tests for core pharmacogenomics callers: allele_caller, warfarin_caller, slco1b1_caller."""

import json
from pathlib import Path

import pandas as pd
import pytest

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "pgx"


# ---------------------------------------------------------------------------
# allele_caller tests
# ---------------------------------------------------------------------------
class TestAltDosage:
    """Test alt_dosage genotype parsing."""

    def test_homozygous_ref(self):
        from src.allele_caller import alt_dosage

        assert alt_dosage("0/0") == 0
        assert alt_dosage("0|0") == 0

    def test_heterozygous(self):
        from src.allele_caller import alt_dosage

        assert alt_dosage("0/1") == 1
        assert alt_dosage("1/0") == 1
        assert alt_dosage("0|1") == 1
        assert alt_dosage("1|0") == 1

    def test_homozygous_alt(self):
        from src.allele_caller import alt_dosage

        assert alt_dosage("1/1") == 2
        assert alt_dosage("1|1") == 2

    def test_empty_and_invalid(self):
        from src.allele_caller import alt_dosage

        assert alt_dosage("") is None
        assert alt_dosage("./.") is None
        assert alt_dosage("2/1") is None


class TestGenotypeToAlleles:
    """Test _genotype_to_alleles helper."""

    def test_hom_ref(self):
        from src.allele_caller import _genotype_to_alleles

        assert _genotype_to_alleles("G", "A", "0/0") == ["G", "G"]

    def test_het(self):
        from src.allele_caller import _genotype_to_alleles

        assert _genotype_to_alleles("G", "A", "0/1") == ["G", "A"]

    def test_hom_alt(self):
        from src.allele_caller import _genotype_to_alleles

        assert _genotype_to_alleles("G", "A", "1/1") == ["A", "A"]

    def test_phased(self):
        from src.allele_caller import _genotype_to_alleles

        assert _genotype_to_alleles("G", "A", "1|0") == ["A", "G"]

    def test_missing_allele_padded(self):
        from src.allele_caller import _genotype_to_alleles

        # Single-allele GT should be padded with ref
        result = _genotype_to_alleles("G", "A", "1")
        assert len(result) == 2
        assert result[0] == "A"
        assert result[1] == "G"


class TestCallStarAlleles:
    """Test call_star_alleles with real PharmVar data."""

    def test_no_variants_returns_empty(self):
        from src.allele_caller import call_star_alleles, load_pharmvar_alleles

        table = load_pharmvar_alleles("cyp2c19", base_dir=DATA_DIR)
        counts = call_star_alleles({}, table)
        assert counts == {}

    def test_cyp2c19_star2_het(self):
        from src.allele_caller import call_star_alleles, load_pharmvar_alleles

        table = load_pharmvar_alleles("cyp2c19", base_dir=DATA_DIR)
        variants = {"rs4244285": ("G", "A", "0/1")}
        counts = call_star_alleles(variants, table)
        assert counts.get("*2") == 1

    def test_cyp2c19_star2_hom(self):
        from src.allele_caller import call_star_alleles, load_pharmvar_alleles

        table = load_pharmvar_alleles("cyp2c19", base_dir=DATA_DIR)
        variants = {"rs4244285": ("G", "A", "1/1")}
        counts = call_star_alleles(variants, table)
        assert counts.get("*2") == 2

    def test_cyp2c19_star17_het(self):
        from src.allele_caller import call_star_alleles, load_pharmvar_alleles

        table = load_pharmvar_alleles("cyp2c19", base_dir=DATA_DIR)
        variants = {"rs12248560": ("C", "T", "0/1")}
        counts = call_star_alleles(variants, table)
        assert counts.get("*17") == 1


class TestCallStarAllelesSimple:
    """Test the simple (rsid -> alt) calling interface."""

    def test_no_match_returns_star1(self):
        from src.allele_caller import call_star_alleles_simple, load_pharmvar_alleles

        table = load_pharmvar_alleles("cyp2c19", base_dir=DATA_DIR)
        result = call_star_alleles_simple({}, table)
        assert result == ["*1"]

    def test_single_match(self):
        from src.allele_caller import call_star_alleles_simple, load_pharmvar_alleles

        table = load_pharmvar_alleles("cyp2c19", base_dir=DATA_DIR)
        result = call_star_alleles_simple({"rs4244285": "A"}, table)
        assert "*2" in result

    def test_two_matches(self):
        from src.allele_caller import call_star_alleles_simple, load_pharmvar_alleles

        table = load_pharmvar_alleles("cyp2c19", base_dir=DATA_DIR)
        result = call_star_alleles_simple({"rs4244285": "A", "rs12248560": "T"}, table)
        assert "*2" in result
        assert "*17" in result


class TestBuildDiplotype:
    """Test diplotype string construction."""

    def test_empty_returns_star1_star1(self):
        from src.allele_caller import build_diplotype

        assert build_diplotype({}) == "*1/*1"

    def test_single_allele_pads_star1(self):
        from src.allele_caller import build_diplotype

        assert build_diplotype({"*2": 1}) == "*1/*2"

    def test_two_copies_same(self):
        from src.allele_caller import build_diplotype

        assert build_diplotype({"*2": 2}) == "*2/*2"

    def test_two_different_alleles_sorted(self):
        from src.allele_caller import build_diplotype

        result = build_diplotype({"*17": 1, "*2": 1})
        assert result == "*17/*2"


class TestBuildDiplotypeSimple:
    """Test build_diplotype_simple."""

    def test_empty_list(self):
        from src.allele_caller import build_diplotype_simple

        assert build_diplotype_simple([]) == "*1/*1"

    def test_one_allele(self):
        from src.allele_caller import build_diplotype_simple

        assert build_diplotype_simple(["*3"]) == "*1/*3"

    def test_two_alleles(self):
        from src.allele_caller import build_diplotype_simple

        assert build_diplotype_simple(["*2", "*3"]) == "*2/*3"


class TestDiplotypeToPhenotype:
    """Test phenotype translation using real CPIC data."""

    def test_cyp2c19_normal(self):
        from src.allele_caller import (
            diplotype_to_phenotype,
            load_cpic_translation_for_gene,
        )

        table = load_cpic_translation_for_gene("cyp2c19", base_dir=DATA_DIR)
        assert diplotype_to_phenotype("*1/*1", table) == "Normal Metabolizer"

    def test_cyp2c19_intermediate(self):
        from src.allele_caller import (
            diplotype_to_phenotype,
            load_cpic_translation_for_gene,
        )

        table = load_cpic_translation_for_gene("cyp2c19", base_dir=DATA_DIR)
        assert diplotype_to_phenotype("*1/*2", table) == "Intermediate Metabolizer"

    def test_cyp2c19_poor(self):
        from src.allele_caller import (
            diplotype_to_phenotype,
            load_cpic_translation_for_gene,
        )

        table = load_cpic_translation_for_gene("cyp2c19", base_dir=DATA_DIR)
        assert diplotype_to_phenotype("*2/*2", table) == "Poor Metabolizer"

    def test_unknown_diplotype(self):
        from src.allele_caller import diplotype_to_phenotype

        assert diplotype_to_phenotype("*99/*99", {}) == "Unknown Metabolizer Status"


class TestCpicDisplayToNormalized:
    """Test the display -> normalized phenotype mapper."""

    def test_normal(self):
        from src.allele_caller import cpic_display_to_normalized

        assert (
            cpic_display_to_normalized("Normal Metabolizer") == "extensive_metabolizer"
        )

    def test_intermediate(self):
        from src.allele_caller import cpic_display_to_normalized

        assert (
            cpic_display_to_normalized("Intermediate Metabolizer")
            == "intermediate_metabolizer"
        )

    def test_poor(self):
        from src.allele_caller import cpic_display_to_normalized

        assert cpic_display_to_normalized("Poor Metabolizer") == "poor_metabolizer"

    def test_rapid(self):
        from src.allele_caller import cpic_display_to_normalized

        assert (
            cpic_display_to_normalized("Rapid Metabolizer") == "extensive_metabolizer"
        )

    def test_ultrarapid(self):
        from src.allele_caller import cpic_display_to_normalized

        assert (
            cpic_display_to_normalized("Ultrarapid Metabolizer")
            == "ultra_rapid_metabolizer"
        )

    def test_garbage(self):
        from src.allele_caller import cpic_display_to_normalized

        assert cpic_display_to_normalized("banana") == "unknown"


class TestInterpretCYP2C19:
    """End-to-end CYP2C19 interpretation."""

    def test_wildtype(self):
        from src.allele_caller import interpret_cyp2c19

        result = interpret_cyp2c19({}, base_dir=DATA_DIR)
        assert result["gene"] == "CYP2C19"
        assert result["alleles"] == "*1/*1"
        assert result["phenotype"] == "Normal Metabolizer"

    def test_star2_carrier(self):
        from src.allele_caller import interpret_cyp2c19

        result = interpret_cyp2c19({"rs4244285": "A"}, base_dir=DATA_DIR)
        assert result["alleles"] == "*1/*2"
        assert result["phenotype"] == "Intermediate Metabolizer"


class TestCallGeneFromVariants:
    """Test the unified call_gene_from_variants function."""

    def test_cyp2c19_wildtype(self):
        from src.allele_caller import call_gene_from_variants

        result = call_gene_from_variants("cyp2c19", {}, base_dir=DATA_DIR)
        assert result is not None
        assert result["diplotype"] == "*1/*1"
        assert result["phenotype_display"] == "Normal Metabolizer"
        assert result["phenotype_normalized"] == "extensive_metabolizer"
        assert result["verification_status"] == "locus_not_queried"

    def test_cyp2c19_verified_with_site_observed(self):
        from src.allele_caller import call_gene_from_variants

        result = call_gene_from_variants(
            "cyp2c19",
            {"rs4244285": ("G", "A", "0/0")},
            base_dir=DATA_DIR,
        )
        assert result is not None
        assert result["verification_status"] == "verified_against_pharmvar_cpic_table"

    def test_cyp2c19_ambiguous_gt(self):
        from src.allele_caller import call_gene_from_variants

        result = call_gene_from_variants(
            "cyp2c19",
            {"rs4244285": ("G", "A", "./.")},
            base_dir=DATA_DIR,
        )
        assert result is not None
        assert result["verification_status"] == "ambiguous_genotype"

    def test_nonexistent_gene_returns_none(self):
        from src.allele_caller import call_gene_from_variants

        result = call_gene_from_variants("fakegene", {}, base_dir=DATA_DIR)
        assert result is None


class TestLoadErrors:
    """Test error handling for missing data files."""

    def test_missing_pharmvar_raises(self):
        from src.allele_caller import load_pharmvar_alleles

        with pytest.raises(FileNotFoundError):
            load_pharmvar_alleles("fakegene", base_dir=DATA_DIR)

    def test_missing_cpic_raises(self):
        from src.allele_caller import load_cpic_translation_for_gene

        with pytest.raises(FileNotFoundError):
            load_cpic_translation_for_gene("fakegene", base_dir=DATA_DIR)


# ---------------------------------------------------------------------------
# warfarin_caller tests
# ---------------------------------------------------------------------------
class TestCallCYP2C9:
    """Test CYP2C9 star allele calling for warfarin."""

    def test_wildtype(self):
        from src.warfarin_caller import call_cyp2c9

        assert call_cyp2c9({}, base_dir=DATA_DIR) == "*1/*1"

    def test_star2_carrier(self):
        from src.warfarin_caller import call_cyp2c9

        assert call_cyp2c9({"rs1799853": "T"}, base_dir=DATA_DIR) == "*1/*2"

    def test_star3_carrier(self):
        from src.warfarin_caller import call_cyp2c9

        assert call_cyp2c9({"rs1057910": "C"}, base_dir=DATA_DIR) == "*1/*3"

    def test_star2_star3_compound_het(self):
        from src.warfarin_caller import call_cyp2c9

        result = call_cyp2c9({"rs1799853": "T", "rs1057910": "C"}, base_dir=DATA_DIR)
        assert result == "*2/*3"


class TestCallVKORC1:
    """Test VKORC1 genotype calling."""

    def test_no_variant_unknown(self):
        from src.warfarin_caller import call_vkorc1

        assert call_vkorc1({}) == "Unknown"

    def test_single_a_returns_ga(self):
        from src.warfarin_caller import call_vkorc1

        assert call_vkorc1({"rs9923231": "A"}) == "GA"

    def test_single_g_returns_gg(self):
        from src.warfarin_caller import call_vkorc1

        assert call_vkorc1({"rs9923231": "G"}) == "GG"

    def test_comma_het(self):
        from src.warfarin_caller import call_vkorc1

        assert call_vkorc1({"rs9923231": "G,A"}) == "GA"

    def test_comma_hom_a(self):
        from src.warfarin_caller import call_vkorc1

        assert call_vkorc1({"rs9923231": "A,A"}) == "AA"

    def test_comma_hom_g(self):
        from src.warfarin_caller import call_vkorc1

        assert call_vkorc1({"rs9923231": "G,G"}) == "GG"


class TestCallVKORC1FromGT:
    """Test VKORC1 calling from VCF genotype fields."""

    def test_hom_ref(self):
        from src.warfarin_caller import call_vkorc1_from_gt

        assert call_vkorc1_from_gt("G", "A", "0/0") == "GG"

    def test_het(self):
        from src.warfarin_caller import call_vkorc1_from_gt

        assert call_vkorc1_from_gt("G", "A", "0/1") == "GA"

    def test_hom_alt(self):
        from src.warfarin_caller import call_vkorc1_from_gt

        assert call_vkorc1_from_gt("G", "A", "1/1") == "AA"

    def test_invalid_gt(self):
        from src.warfarin_caller import call_vkorc1_from_gt

        assert call_vkorc1_from_gt("G", "A", "./.") == "Unknown"


class TestCallCYP2C9FromVCF:
    """Test CYP2C9 calling from VCF variant map."""

    def test_wildtype(self):
        from src.warfarin_caller import call_cyp2c9_from_vcf

        assert call_cyp2c9_from_vcf({}, base_dir=DATA_DIR) == "*1/*1"

    def test_het_star2(self):
        from src.warfarin_caller import call_cyp2c9_from_vcf

        var_map = {"rs1799853": ("C", "T", "0/1")}
        assert call_cyp2c9_from_vcf(var_map, base_dir=DATA_DIR) == "*1/*2"

    def test_hom_star2(self):
        from src.warfarin_caller import call_cyp2c9_from_vcf

        var_map = {"rs1799853": ("C", "T", "1/1")}
        assert call_cyp2c9_from_vcf(var_map, base_dir=DATA_DIR) == "*2/*2"


class TestInterpretWarfarin:
    """End-to-end warfarin interpretation."""

    def test_normal_dose(self):
        from src.warfarin_caller import interpret_warfarin

        result = interpret_warfarin({"rs9923231": "G"}, base_dir=DATA_DIR)
        assert result["drug"] == "Warfarin"
        assert result["CYP2C9"] == "*1/*1"
        assert result["VKORC1"] == "GG"
        assert result["recommendation"] == "Normal dose requirement"

    def test_cyp2c9_star2_vkorc1_ga(self):
        from src.warfarin_caller import interpret_warfarin

        result = interpret_warfarin(
            {"rs1799853": "T", "rs9923231": "A"}, base_dir=DATA_DIR
        )
        assert result["CYP2C9"] == "*1/*2"
        assert result["VKORC1"] == "GA"
        assert "dose reduction" in result["recommendation"].lower()

    def test_no_vkorc1_unknown(self):
        from src.warfarin_caller import interpret_warfarin

        result = interpret_warfarin({}, base_dir=DATA_DIR)
        assert result["VKORC1"] == "Unknown"


class TestInterpretWarfarinFromVCF:
    """Test warfarin interpretation from VCF variant map."""

    def test_normal_dose_vcf(self):
        from src.warfarin_caller import interpret_warfarin_from_vcf

        var_map = {"rs9923231": ("G", "A", "0/0")}
        result = interpret_warfarin_from_vcf(var_map, base_dir=DATA_DIR)
        assert result is not None
        assert result["CYP2C9"] == "*1/*1"
        assert result["VKORC1"] == "GG"

    def test_het_vkorc1_vcf(self):
        from src.warfarin_caller import interpret_warfarin_from_vcf

        var_map = {"rs9923231": ("G", "A", "0/1")}
        result = interpret_warfarin_from_vcf(var_map, base_dir=DATA_DIR)
        assert result is not None
        assert result["VKORC1"] == "GA"


# ---------------------------------------------------------------------------
# slco1b1_caller tests
# ---------------------------------------------------------------------------
class TestSLCO1B1AltDosage:
    """Test SLCO1B1 module's own alt_dosage."""

    def test_values(self):
        from src.slco1b1_caller import alt_dosage

        assert alt_dosage("0/0") == 0
        assert alt_dosage("0/1") == 1
        assert alt_dosage("1/1") == 2
        assert alt_dosage("./.") is None


class TestInterpretSLCO1B1:
    """Test SLCO1B1 phenotype interpretation with drug recommendations."""

    def test_tt_normal(self):
        from src.slco1b1_caller import interpret_slco1b1

        result = interpret_slco1b1("TT", "simvastatin")
        assert result["phenotype"] == "Normal Function"
        assert result["risk"] == "Low myopathy risk"
        assert "Standard" in result["recommendation"]

    def test_tc_decreased(self):
        from src.slco1b1_caller import interpret_slco1b1

        result = interpret_slco1b1("TC", "simvastatin")
        assert result["phenotype"] == "Decreased Function"
        assert (
            "lower dose" in result["recommendation"].lower()
            or "alternate" in result["recommendation"].lower()
        )

    def test_cc_poor(self):
        from src.slco1b1_caller import interpret_slco1b1

        result = interpret_slco1b1("CC", "simvastatin")
        assert result["phenotype"] == "Poor Function"
        assert (
            "Avoid" in result["recommendation"]
            or "alternative" in result["recommendation"].lower()
        )

    def test_case_insensitive_genotype(self):
        from src.slco1b1_caller import interpret_slco1b1

        result = interpret_slco1b1("tt", "simvastatin")
        assert result["phenotype"] == "Normal Function"

    def test_atorvastatin(self):
        from src.slco1b1_caller import interpret_slco1b1

        result = interpret_slco1b1("CC", "atorvastatin")
        assert result["phenotype"] == "Poor Function"
        assert result["recommendation"] != "No guideline available"

    def test_rosuvastatin(self):
        from src.slco1b1_caller import interpret_slco1b1

        result = interpret_slco1b1("TC", "rosuvastatin")
        assert result["phenotype"] == "Decreased Function"
        assert "dose" in result["recommendation"].lower()

    def test_unknown_drug(self):
        from src.slco1b1_caller import interpret_slco1b1

        result = interpret_slco1b1("TT", "pravastatin")
        assert result["recommendation"] == "No guideline available"

    def test_invalid_genotype_returns_empty(self):
        from src.slco1b1_caller import interpret_slco1b1

        result = interpret_slco1b1("XX", "simvastatin")
        assert result == {}


class TestLoadSLCO1B1Phenotypes:
    """Test backward-compatible phenotype loader."""

    def test_loads_all_genotypes(self):
        from src.slco1b1_caller import load_slco1b1_phenotypes

        table = load_slco1b1_phenotypes(base_dir=DATA_DIR)
        assert "TT" in table
        assert "TC" in table
        assert "CC" in table

    def test_phenotype_values(self):
        from src.slco1b1_caller import load_slco1b1_phenotypes

        table = load_slco1b1_phenotypes(base_dir=DATA_DIR)
        assert table["TT"] == "Normal Function"
        assert table["CC"] == "Poor Function"


class TestInterpretSLCO1B1FromVCF:
    """Test SLCO1B1 interpretation from VCF variant map."""

    def test_no_variant_returns_none(self):
        from src.slco1b1_caller import interpret_slco1b1_from_vcf

        result = interpret_slco1b1_from_vcf({}, base_dir=DATA_DIR)
        assert result is None

    def test_hom_ref_tt(self):
        from src.slco1b1_caller import interpret_slco1b1_from_vcf

        var_map = {"rs4149056": ("T", "C", "0/0")}
        result = interpret_slco1b1_from_vcf(var_map, base_dir=DATA_DIR)
        assert result is not None
        assert result["genotype"] == "TT"
        assert result["phenotype"] == "Normal Function"

    def test_het_tc(self):
        from src.slco1b1_caller import interpret_slco1b1_from_vcf

        var_map = {"rs4149056": ("T", "C", "0/1")}
        result = interpret_slco1b1_from_vcf(var_map, base_dir=DATA_DIR)
        assert result is not None
        assert result["genotype"] == "TC"
        assert result["phenotype"] == "Decreased Function"

    def test_hom_alt_cc(self):
        from src.slco1b1_caller import interpret_slco1b1_from_vcf

        var_map = {"rs4149056": ("T", "C", "1/1")}
        result = interpret_slco1b1_from_vcf(var_map, base_dir=DATA_DIR)
        assert result is not None
        assert result["genotype"] == "CC"
        assert result["phenotype"] == "Poor Function"

    def test_invalid_gt(self):
        from src.slco1b1_caller import interpret_slco1b1_from_vcf

        var_map = {"rs4149056": ("T", "C", "./.")}
        result = interpret_slco1b1_from_vcf(var_map, base_dir=DATA_DIR)
        assert result is not None
        assert result["genotype"] == "Unknown"
