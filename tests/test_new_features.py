"""Tests for new features: ancestry risk scoring, multi-variant haplotypes, VCF integration."""

import pandas as pd
import pytest


class TestAncestryRiskScoring:
    """Test ancestry-aware confidence scoring."""

    def test_strong_evidence_eur_cyp2d6(self):
        from src.ancestry_risk import compute_ancestry_confidence

        result = compute_ancestry_confidence("CYP2D6", "EUR")
        assert result["confidence"] >= 0.9
        assert result["evidence_level"] == "strong"
        assert result["population"] == "EUR"

    def test_limited_evidence_afr_dpyd(self):
        from src.ancestry_risk import compute_ancestry_confidence

        result = compute_ancestry_confidence("DPYD", "AFR")
        assert result["confidence"] < 0.7
        assert result["evidence_level"] in ("limited", "insufficient")

    def test_poor_metabolizer_penalty(self):
        from src.ancestry_risk import compute_ancestry_confidence

        normal = compute_ancestry_confidence("DPYD", "EAS")
        poor = compute_ancestry_confidence("DPYD", "EAS", phenotype="Poor Metabolizer")
        assert poor["confidence"] <= normal["confidence"]

    def test_unknown_population(self):
        from src.ancestry_risk import compute_ancestry_confidence

        result = compute_ancestry_confidence("CYP2D6", "UNKNOWN_POP")
        assert result["confidence"] == 0.5
        assert result["evidence_level"] == "unknown"

    def test_variant_frequency_lookup(self):
        from src.ancestry_risk import get_variant_frequency

        freq = get_variant_frequency("CYP2D6", "*4", "EUR")
        assert freq == 0.20
        freq_eas = get_variant_frequency("CYP2D6", "*4", "EAS")
        assert freq_eas == 0.01

    def test_variant_frequency_missing(self):
        from src.ancestry_risk import get_variant_frequency

        freq = get_variant_frequency("UNKNOWN_GENE", "*1", "EUR")
        assert freq is None

    def test_population_risk_summary(self):
        from src.ancestry_risk import get_population_risk_summary

        results = get_population_risk_summary(["CYP2D6", "DPYD"], "EUR")
        assert len(results) == 2
        assert all("confidence" in r for r in results)

    def test_all_valid_populations(self):
        from src.ancestry_risk import compute_ancestry_confidence

        for pop in ["AFR", "EUR", "EAS", "SAS", "AMR"]:
            result = compute_ancestry_confidence("CYP2D6", pop)
            assert 0 < result["confidence"] <= 1.0
            assert result["population"] == pop


class TestMultiVariantHaplotypeCaller:
    """Test multi-variant haplotype calling."""

    def test_multi_variant_heterozygous(self):
        from src.allele_caller import call_star_alleles_multi_variant

        haplo_df = pd.DataFrame(
            {
                "allele": ["*3A"],
                "rsids": ["rs1800460,rs1142345"],
                "alts": ["C,C"],
            }
        )
        variants = {
            "rs1800460": ("G", "C", "0/1"),
            "rs1142345": ("A", "C", "0/1"),
        }
        result = call_star_alleles_multi_variant(variants, haplo_df)
        assert result.get("*3A", 0) >= 1

    def test_multi_variant_homozygous(self):
        from src.allele_caller import call_star_alleles_multi_variant

        haplo_df = pd.DataFrame(
            {
                "allele": ["*3A"],
                "rsids": ["rs1800460,rs1142345"],
                "alts": ["C,C"],
            }
        )
        variants = {
            "rs1800460": ("G", "C", "1/1"),
            "rs1142345": ("A", "C", "1/1"),
        }
        result = call_star_alleles_multi_variant(variants, haplo_df)
        assert result.get("*3A", 0) == 2

    def test_multi_variant_missing_rsid(self):
        from src.allele_caller import call_star_alleles_multi_variant

        haplo_df = pd.DataFrame(
            {
                "allele": ["*3A"],
                "rsids": ["rs1800460,rs1142345"],
                "alts": ["C,C"],
            }
        )
        # Only one of two required rsIDs present
        variants = {
            "rs1800460": ("G", "C", "0/1"),
        }
        result = call_star_alleles_multi_variant(variants, haplo_df)
        assert result.get("*3A", 0) == 0

    def test_fallback_to_single_variant(self):
        from src.allele_caller import call_star_alleles_multi_variant

        # Table without 'rsids' column -> fallback
        single_df = pd.DataFrame(
            {
                "allele": ["*2"],
                "rsid": ["rs4244285"],
                "alt": ["A"],
            }
        )
        result = call_star_alleles_multi_variant(
            {"rs4244285": ("G", "A", "0/1")}, single_df
        )
        assert result.get("*2", 0) == 1


class TestVCFTPMTDPYDIntegration:
    """Test TPMT/DPYD integration in VCF processor."""

    def test_tpmt_gene_location(self):
        from src.vcf_processor import CYP_GENE_LOCATIONS

        assert "TPMT" in CYP_GENE_LOCATIONS
        assert CYP_GENE_LOCATIONS["TPMT"]["chrom"] == "6"

    def test_dpyd_gene_location(self):
        from src.vcf_processor import CYP_GENE_LOCATIONS

        assert "DPYD" in CYP_GENE_LOCATIONS
        assert CYP_GENE_LOCATIONS["DPYD"]["chrom"] == "1"

    def test_profile_genes_includes_new(self):
        from src.vcf_processor import PROFILE_GENES

        assert "TPMT" in PROFILE_GENES
        assert "DPYD" in PROFILE_GENES
        assert len(PROFILE_GENES) == 8

    def test_chrom_key_for_tpmt(self):
        from src.vcf_processor import _chrom_key_for_gene

        assert _chrom_key_for_gene("TPMT") == "chr6"

    def test_chrom_key_for_dpyd(self):
        from src.vcf_processor import _chrom_key_for_gene

        assert _chrom_key_for_gene("DPYD") == "chr1"

    def test_tpmt_from_vcf(self):
        from src.tpmt_caller import interpret_tpmt_from_vcf

        result = interpret_tpmt_from_vcf({"rs1800460": ("G", "C", "0/1")})
        assert result["gene"] == "TPMT"
        assert result["diplotype"] == "*1/*3A"
        assert result["phenotype"] == "Intermediate Metabolizer"

    def test_dpyd_from_vcf(self):
        from src.dpyd_caller import interpret_dpyd_from_vcf

        result = interpret_dpyd_from_vcf({"rs3918290": ("C", "T", "0/1")})
        assert result["gene"] == "DPYD"
        assert result["diplotype"] == "*1/*2A"
        assert result["phenotype"] == "Intermediate Metabolizer"
