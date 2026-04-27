"""Tests for TPMT and DPYD pharmacogene callers."""

import pytest


class TestTPMTCaller:
    """Test TPMT allele calling and phenotype interpretation."""

    def test_tpmt_no_variants_normal(self):
        from src.tpmt_caller import interpret_tpmt

        result = interpret_tpmt({})
        assert result["gene"] == "TPMT"
        assert result["diplotype"] == "*1/*1"
        assert result["phenotype"] == "Normal Metabolizer"

    def test_tpmt_star3a_intermediate(self):
        from src.tpmt_caller import interpret_tpmt

        result = interpret_tpmt({"rs1800460": "C"}, drug_name="azathioprine")
        assert result["diplotype"] == "*1/*3A"
        assert result["phenotype"] == "Intermediate Metabolizer"
        assert "Reduce dose" in result["recommendation"]

    def test_tpmt_star2_intermediate(self):
        from src.tpmt_caller import interpret_tpmt

        result = interpret_tpmt({"rs1800462": "G"})
        assert result["diplotype"] == "*1/*2"
        assert result["phenotype"] == "Intermediate Metabolizer"

    def test_tpmt_poor_metabolizer(self):
        from src.tpmt_caller import interpret_tpmt

        result = interpret_tpmt(
            {"rs1800460": "C", "rs1142345": "C"}, drug_name="azathioprine"
        )
        assert result["phenotype"] == "Poor Metabolizer"
        assert (
            "alternative" in result["recommendation"].lower()
            or "reduce" in result["recommendation"].lower()
        )

    def test_tpmt_vcf_no_variants(self):
        from src.tpmt_caller import interpret_tpmt_from_vcf

        result = interpret_tpmt_from_vcf({})
        assert result["phenotype"] == "Normal Metabolizer"

    def test_tpmt_vcf_heterozygous(self):
        from src.tpmt_caller import interpret_tpmt_from_vcf

        result = interpret_tpmt_from_vcf({"rs1800460": ("G", "C", "0/1")})
        assert result["diplotype"] == "*1/*3A"
        assert result["phenotype"] == "Intermediate Metabolizer"

    def test_tpmt_drug_recommendation_mercaptopurine(self):
        from src.tpmt_caller import interpret_tpmt

        result = interpret_tpmt({"rs1800460": "C"}, drug_name="mercaptopurine")
        assert "Reduce dose" in result["recommendation"]

    def test_tpmt_drug_recommendation_thioguanine(self):
        from src.tpmt_caller import interpret_tpmt

        result = interpret_tpmt(
            {"rs1800460": "C", "rs1142345": "C"}, drug_name="thioguanine"
        )
        assert (
            "alternative" in result["recommendation"].lower()
            or "reduce" in result["recommendation"].lower()
        )


class TestDPYDCaller:
    """Test DPYD allele calling and phenotype interpretation."""

    def test_dpyd_no_variants_normal(self):
        from src.dpyd_caller import interpret_dpyd

        result = interpret_dpyd({})
        assert result["gene"] == "DPYD"
        assert result["diplotype"] == "*1/*1"
        assert result["phenotype"] == "Normal Metabolizer"

    def test_dpyd_star2a_intermediate(self):
        """Heterozygous *1/*2A is Intermediate Metabolizer per CPIC 2024 update."""
        from src.dpyd_caller import interpret_dpyd

        result = interpret_dpyd({"rs3918290": "T"}, drug_name="fluorouracil")
        assert result["diplotype"] == "*1/*2A"
        assert result["phenotype"] == "Intermediate Metabolizer"
        assert "50%" in result["recommendation"] or "Reduce" in result["recommendation"]

    def test_dpyd_c2846_intermediate(self):
        from src.dpyd_caller import interpret_dpyd

        result = interpret_dpyd({"rs67376798": "T"}, drug_name="capecitabine")
        assert result["diplotype"] == "*1/c.2846A>T"
        assert result["phenotype"] == "Intermediate Metabolizer"
        assert "50%" in result["recommendation"]

    def test_dpyd_hapb3_intermediate(self):
        from src.dpyd_caller import interpret_dpyd

        result = interpret_dpyd({"rs56038477": "C"}, drug_name="fluorouracil")
        assert "HapB3" in result["diplotype"]
        assert result["phenotype"] == "Intermediate Metabolizer"

    def test_dpyd_star13_intermediate(self):
        """Heterozygous *1/*13 is Intermediate Metabolizer per CPIC 2024 update."""
        from src.dpyd_caller import interpret_dpyd

        result = interpret_dpyd({"rs55886062": "A"}, drug_name="fluorouracil")
        assert result["diplotype"] == "*1/*13"
        assert result["phenotype"] == "Intermediate Metabolizer"

    def test_dpyd_vcf_no_variants(self):
        from src.dpyd_caller import interpret_dpyd_from_vcf

        result = interpret_dpyd_from_vcf({})
        assert result["phenotype"] == "Normal Metabolizer"

    def test_dpyd_vcf_heterozygous_star2a(self):
        from src.dpyd_caller import interpret_dpyd_from_vcf

        result = interpret_dpyd_from_vcf({"rs3918290": ("C", "T", "0/1")})
        assert result["diplotype"] == "*1/*2A"
        assert result["phenotype"] == "Intermediate Metabolizer"

    def test_dpyd_capecitabine_recommendation(self):
        """Heterozygous *1/*2A → dose reduction, not avoidance."""
        from src.dpyd_caller import interpret_dpyd

        result = interpret_dpyd({"rs3918290": "T"}, drug_name="capecitabine")
        assert "Reduce" in result["recommendation"] or "50%" in result["recommendation"]

    def test_dpyd_tegafur_recommendation(self):
        """Heterozygous *1/*2A → dose reduction, not avoidance."""
        from src.dpyd_caller import interpret_dpyd

        result = interpret_dpyd({"rs3918290": "T"}, drug_name="tegafur")
        assert "Reduce" in result["recommendation"] or "50%" in result["recommendation"]


class TestDrugGeneTriggers:
    """Test that new drug-gene triggers are correctly configured."""

    def test_thiopurine_triggers(self):
        from src.pgx_triggers import DRUG_GENE_TRIGGERS

        assert DRUG_GENE_TRIGGERS["azathioprine"] == ["TPMT"]
        assert DRUG_GENE_TRIGGERS["mercaptopurine"] == ["TPMT"]
        assert DRUG_GENE_TRIGGERS["thioguanine"] == ["TPMT"]

    def test_fluoropyrimidine_triggers(self):
        from src.pgx_triggers import DRUG_GENE_TRIGGERS

        assert DRUG_GENE_TRIGGERS["fluorouracil"] == ["DPYD"]
        assert DRUG_GENE_TRIGGERS["capecitabine"] == ["DPYD"]
        assert DRUG_GENE_TRIGGERS["tegafur"] == ["DPYD"]

    def test_cyp2d6_triggers(self):
        from src.pgx_triggers import DRUG_GENE_TRIGGERS

        assert DRUG_GENE_TRIGGERS["codeine"] == ["CYP2D6"]
        assert DRUG_GENE_TRIGGERS["tramadol"] == ["CYP2D6"]

    def test_irinotecan_trigger(self):
        from src.pgx_triggers import DRUG_GENE_TRIGGERS

        assert DRUG_GENE_TRIGGERS["irinotecan"] == ["UGT1A1"]


class TestVariantDB:
    """Test that variant DB includes new genes."""

    def test_tpmt_in_variant_db(self):
        from src.variant_db import VARIANT_DB

        assert "TPMT" in VARIANT_DB
        assert "rs1800462" in VARIANT_DB["TPMT"]
        assert "rs1800460" in VARIANT_DB["TPMT"]
        assert "rs1142345" in VARIANT_DB["TPMT"]

    def test_dpyd_in_variant_db(self):
        from src.variant_db import VARIANT_DB

        assert "DPYD" in VARIANT_DB
        assert "rs3918290" in VARIANT_DB["DPYD"]
        assert "rs55886062" in VARIANT_DB["DPYD"]
        assert "rs67376798" in VARIANT_DB["DPYD"]
        assert "rs56038477" in VARIANT_DB["DPYD"]

    def test_supported_genes_updated(self):
        from src.variant_db import SUPPORTED_PROFILE_GENES

        assert "TPMT" in SUPPORTED_PROFILE_GENES
        assert "DPYD" in SUPPORTED_PROFILE_GENES
        assert len(SUPPORTED_PROFILE_GENES) == 7
