"""Tests for risk level parsing from LLM simulation text."""

from src.agent_engine import extract_risk_level


def test_canonical_risk_level_line():
    assert extract_risk_level("RISK LEVEL: Low\n\nPREDICTED REACTION: ok") == "Low"


def test_markdown_bold_risk_level():
    assert extract_risk_level("- **RISK LEVEL:** High\n\nMore text") == "High"


def test_title_case_risk_level():
    assert extract_risk_level("Risk Level: Medium\n\nDetails follow.") == "Medium"


def test_risk_level_is_prose():
    assert (
        extract_risk_level(
            "Based on CPIC, the overall risk level is high for this patient."
        )
        == "High"
    )


def test_unknown_returns_none():
    assert extract_risk_level("No structured output here.") is None
