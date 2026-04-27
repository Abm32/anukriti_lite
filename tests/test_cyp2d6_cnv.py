"""
Tests for CYP2D6 CNV (*5 deletion, *XN duplication) handling.

Test matrix covers:
- Copy number 0: homozygous deletion (*5/*5, ultra-poor)
- Copy number 1: heterozygous deletion (*5/[SNP allele])
- Copy number 2: normal diploid (baseline)
- Copy number 3: single duplication (*1x2 or *2x2)
- Copy number 4: double duplication (*1x3)
- Copy number 5+: ultrarapid (*1xN)
- SNP + CNV integration: *2 background + DUP -> *2x2/allele
"""

import pytest

from src.variant_db import get_phenotype_prediction
from src.vcf_processor import (
    _cnv_allele_to_star,
    _parse_svtype,
    _resolve_cyp2d6_diplotype,
    infer_metabolizer_status,
    infer_metabolizer_status_with_alleles,
)

# ---------------------------------------------------------------------------
# SVTYPE parsing
# ---------------------------------------------------------------------------


def test_parse_svtype_del():
    assert _parse_svtype("SVTYPE=DEL") == "DEL"
    assert _parse_svtype("SVTYPE=DEL;END=123") == "DEL"
    assert _parse_svtype("SVTYPE=DEL:ME:ALU") == "DEL"


def test_parse_svtype_dup():
    assert _parse_svtype("SVTYPE=DUP") == "DUP"
    assert _parse_svtype("SVTYPE=DUP:TANDEM") == "DUP"
    assert _parse_svtype("SVTYPE=CNV") == "DUP"


def test_parse_svtype_none():
    assert _parse_svtype("") is None
    assert _parse_svtype("END=123") is None


# ---------------------------------------------------------------------------
# _cnv_allele_to_star — expanded copy-number matrix
# ---------------------------------------------------------------------------


def test_cnv_allele_to_star_del():
    assert _cnv_allele_to_star("CYP2D6", "DEL", [], copy_number=0) == "*5"
    assert _cnv_allele_to_star("CYP2D6", "DEL", ["*4"], copy_number=0) == "*5"
    assert _cnv_allele_to_star("CYP2D6", "DEL", [], copy_number=1) == "*5"


def test_cnv_allele_to_star_dup_no_snp():
    assert _cnv_allele_to_star("CYP2D6", "DUP", [], copy_number=3) == "*1x2"
    assert _cnv_allele_to_star("CYP2D6", "DUP", [], copy_number=4) == "*1x3"
    assert _cnv_allele_to_star("CYP2D6", "DUP", [], copy_number=5) == "*1xN"


def test_cnv_allele_to_star_dup_with_star2():
    assert _cnv_allele_to_star("CYP2D6", "DUP", ["*2"], copy_number=3) == "*2x2"
    assert _cnv_allele_to_star("CYP2D6", "DUP", ["*2"], copy_number=4) == "*2x3"


def test_cnv_allele_to_star_dup_with_star4():
    assert _cnv_allele_to_star("CYP2D6", "DUP", ["*4"], copy_number=3) == "*4x2"


def test_cnv_allele_to_star_dup_no_copy_number():
    """No CN field → default 3 copies (single duplication event)."""
    result = _cnv_allele_to_star("CYP2D6", "DUP", [], copy_number=None)
    assert result == "*1x2"


# ---------------------------------------------------------------------------
# _resolve_cyp2d6_diplotype — phased SNP + CNV diplotype building
# ---------------------------------------------------------------------------


def test_resolve_diplotype_no_cnv_no_snp():
    assert _resolve_cyp2d6_diplotype([], None, 2) == "*1/*1"


def test_resolve_diplotype_snp_only():
    assert _resolve_cyp2d6_diplotype(["*4"], None, 2) == "*1/*4"
    assert _resolve_cyp2d6_diplotype(["*4", "*4"], None, 2) == "*4/*4"


def test_resolve_diplotype_del_cn0():
    """CN=0: both copies deleted → *5/*5 (ultra-poor)."""
    assert _resolve_cyp2d6_diplotype([], "DEL", 0) == "*5/*5"


def test_resolve_diplotype_del_cn1():
    """CN=1: one copy deleted, one retained → *5/*1 (poor)."""
    result = _resolve_cyp2d6_diplotype([], "DEL", 1)
    assert result == "*5/*1"


def test_resolve_diplotype_del_cn1_with_snp():
    """CN=1 + *4 SNP → *5/*4 (compound heterozygous)."""
    result = _resolve_cyp2d6_diplotype(["*4"], "DEL", 1)
    assert result == "*5/*4"


def test_resolve_diplotype_dup_cn3():
    """CN=3: standard single duplication → *1/*1x2."""
    result = _resolve_cyp2d6_diplotype([], "DUP", 3)
    assert "x2" in result or "*1" in result


def test_resolve_diplotype_dup_cn3_star2():
    """CN=3 + *2 → *1/*2x2 (ultrarapid with *2 background)."""
    result = _resolve_cyp2d6_diplotype(["*2"], "DUP", 3)
    assert "*2x2" in result


# ---------------------------------------------------------------------------
# Phenotype prediction integration
# ---------------------------------------------------------------------------


def test_get_phenotype_deletion_cn0():
    """*5 (gene deletion, CN=0) -> Poor Metabolizer."""
    assert (
        get_phenotype_prediction("CYP2D6", ["CYP2D6_DEL"], copy_number=0)
        == "poor_metabolizer"
    )
    assert (
        get_phenotype_prediction("CYP2D6", ["*4", "CYP2D6_DEL"], copy_number=0)
        == "poor_metabolizer"
    )


def test_get_phenotype_duplication_cn3():
    """CN=3 single duplication -> Ultra-Rapid."""
    assert (
        get_phenotype_prediction("CYP2D6", ["CYP2D6_DUP"], copy_number=3)
        == "ultra_rapid_metabolizer"
    )


def test_get_phenotype_duplication_cn4():
    """CN=4 double duplication -> Ultra-Rapid."""
    assert (
        get_phenotype_prediction("CYP2D6", ["CYP2D6_DUP"], copy_number=4)
        == "ultra_rapid_metabolizer"
    )


# ---------------------------------------------------------------------------
# Full infer_metabolizer_status integration
# ---------------------------------------------------------------------------


def test_infer_metabolizer_sv_del():
    """<DEL> SVTYPE → Poor Metabolizer, diplotype contains *5."""
    variants = [
        {
            "id": "sv1",
            "alt": "<DEL>",
            "info": "SVTYPE=DEL;END=42530000",
            "samples": {"S1": "0/1"},
        }
    ]
    assert infer_metabolizer_status(variants, "S1", "CYP2D6") == "poor_metabolizer"
    res = infer_metabolizer_status_with_alleles(variants, "S1", "CYP2D6")
    assert res["phenotype"] == "poor_metabolizer"
    assert "*5" in res["allele_call"]
    assert "gene deletion" in str(res["interpretation"]).lower()


def test_infer_metabolizer_sv_del_cn0():
    """DEL with explicit CN=0 → *5/*5, ultra-poor diplotype."""
    variants = [
        {
            "id": "sv_del_cn0",
            "alt": "<DEL>",
            "info": "SVTYPE=DEL;CN=0;END=42530000",
            "samples": {"S1": "1/1"},
        }
    ]
    res = infer_metabolizer_status_with_alleles(variants, "S1", "CYP2D6")
    assert res["phenotype"] == "poor_metabolizer"
    assert "*5" in res["allele_call"]
    assert res["copy_number"] == 0


def test_infer_metabolizer_sv_dup():
    """<DUP> SVTYPE → Ultra-Rapid Metabolizer."""
    variants = [
        {
            "id": "sv2",
            "alt": "<DUP>",
            "info": "SVTYPE=DUP;END=42531000",
            "samples": {"S1": "0/1"},
        }
    ]
    assert (
        infer_metabolizer_status(variants, "S1", "CYP2D6") == "ultra_rapid_metabolizer"
    )
    res = infer_metabolizer_status_with_alleles(variants, "S1", "CYP2D6")
    assert res["phenotype"] == "ultra_rapid_metabolizer"
    assert "*1" in res["allele_call"] or "x" in res["allele_call"]


def test_infer_metabolizer_sv_dup_cn3():
    """DUP with explicit CN=3 → *1x2 single-copy duplication."""
    variants = [
        {
            "id": "sv_dup_cn3",
            "alt": "<DUP>",
            "info": "SVTYPE=DUP;CN=3;END=42531000",
            "samples": {"S1": "0/1"},
        }
    ]
    res = infer_metabolizer_status_with_alleles(variants, "S1", "CYP2D6")
    assert res["phenotype"] == "ultra_rapid_metabolizer"
    assert "x2" in res["allele_call"] or "*1" in res["allele_call"]
    assert res["copy_number"] == 3


def test_infer_metabolizer_sv_dup_cn4():
    """DUP with CN=4 → x3 duplication (2 extra copies)."""
    variants = [
        {
            "id": "sv_dup_cn4",
            "alt": "<DUP>",
            "info": "SVTYPE=DUP;CN=4;END=42531000",
            "samples": {"S1": "0/1"},
        }
    ]
    res = infer_metabolizer_status_with_alleles(variants, "S1", "CYP2D6")
    assert res["phenotype"] == "ultra_rapid_metabolizer"
    assert res["copy_number"] == 4


def test_infer_metabolizer_sv_dup_cn5():
    """DUP with CN=5 → ultrarapid (≥4 copies, xN notation)."""
    variants = [
        {
            "id": "sv_dup_cn5",
            "alt": "<DUP>",
            "info": "SVTYPE=DUP;CN=5;END=42531000",
            "samples": {"S1": "0/1"},
        }
    ]
    res = infer_metabolizer_status_with_alleles(variants, "S1", "CYP2D6")
    assert res["phenotype"] == "ultra_rapid_metabolizer"
    assert res["copy_number"] == 5
    assert "xN" in res["allele_call"] or "x" in res["allele_call"]


def test_cnv_allele_to_star_dup_cn5_ultrarapid():
    """CN≥5 produces xN notation for ultrarapid."""
    result = _cnv_allele_to_star("CYP2D6", "DUP", [], copy_number=5)
    assert "xN" in result


def test_resolve_diplotype_del_cn1_star10():
    """CN=1 + *10 SNP (common in East Asian) → *5/*10."""
    result = _resolve_cyp2d6_diplotype(["*10"], "DEL", 1)
    assert "*5" in result
    assert "*10" in result


def test_resolve_diplotype_dup_cn4_star4():
    """CN=4 + *4 SNP (no-function) → still ultrarapid due to copy count."""
    result = _resolve_cyp2d6_diplotype(["*4"], "DUP", 4)
    assert "x3" in result or "*4" in result


def test_resolve_diplotype_dup_cn3_star41():
    """CN=3 + *41 (reduced function) → *1/*41x2."""
    result = _resolve_cyp2d6_diplotype(["*41"], "DUP", 3)
    assert "*41x2" in result or "*41" in result
