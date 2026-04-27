"""Deterministic HLA proxy callers."""

from src.hla_caller import (
    interpret_hla_b1502_anticonvulsant,
    interpret_hla_b5701_abacavir,
)


def test_hla_b1502_positive_high_risk():
    r = interpret_hla_b1502_anticonvulsant(True, "carbamazepine")
    assert r["risk"] == "High"
    assert "SJS" in r["recommendation"] or "TEN" in r["recommendation"]


def test_hla_b1502_negative_low_risk():
    r = interpret_hla_b1502_anticonvulsant(False, "phenytoin")
    assert r["risk"] == "Low"


def test_hla_b57_abacavir_positive():
    r = interpret_hla_b5701_abacavir(True)
    assert r["risk"] == "High"
    assert "abacavir" in r["recommendation"].lower()
