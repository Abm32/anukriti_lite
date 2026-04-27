"""
Deterministic HLA proxy interpretations for anticonvulsants and abacavir.

Uses tag SNPs in lieu of full HLA sequencing (research / education only).
"""

from __future__ import annotations

from typing import Any, Dict


def interpret_hla_b1502_anticonvulsant(
    proxy_positive: bool, drug_name: str
) -> Dict[str, Any]:
    """
    HLA-B*15:02 tags severe cutaneous adverse reactions (SJS/TEN) with
    carbamazepine, phenytoin, oxcarbazepine (CPIC Level A evidence).

    Proxy: rs3909184 ALT tags HLA-B*15:02 in many East Asian populations.
    Not a substitute for sequence-based HLA typing.
    """
    d = (drug_name or "").strip().lower()
    label = {
        "carbamazepine": "carbamazepine",
        "oxcarbazepine": "oxcarbazepine",
        "phenytoin": "phenytoin",
    }.get(d, d or "anticonvulsant")

    if proxy_positive:
        return {
            "gene": "HLA-B*15:02",
            "variant": "rs3909184 (LD proxy for HLA-B*15:02 in many populations)",
            "genotype": "proxy positive (≥1 ALT)",
            "phenotype": "HLA-B*15:02 signal (proxy)",
            "risk": "High",
            "recommendation": (
                f"Elevated SJS/TEN risk with {label} per CPIC-style anticonvulsant guidance. "
                "Consider alternatives when clinically appropriate; confirm with sequence-based "
                "HLA-B*15:02 typing before clinical decisions."
            ),
        }

    return {
        "gene": "HLA-B*15:02",
        "variant": "rs3909184",
        "genotype": "proxy negative",
        "phenotype": "No *15:02 proxy signal at tag SNP",
        "risk": "Low",
        "recommendation": (
            f"No elevated SJS/TEN risk from this proxy alone for {label}; "
            "standard vigilance and clinical assessment still apply."
        ),
    }


def interpret_hla_b5701_abacavir(proxy_positive: bool) -> Dict[str, Any]:
    """HLA-B*57:01 / abacavir hypersensitivity (rs2395029 proxy)."""
    if proxy_positive:
        return {
            "gene": "HLA-B*57:01",
            "variant": "rs2395029 (HCP5 proxy for HLA-B*57:01)",
            "genotype": "proxy positive",
            "phenotype": "HLA-B*57:01 signal (proxy)",
            "risk": "High",
            "recommendation": (
                "Abacavir is contraindicated with HLA-B*57:01 per CPIC; "
                "use alternative therapy unless negative HLA-B*57:01 confirmed by clinical test."
            ),
        }
    return {
        "gene": "HLA-B*57:01",
        "variant": "rs2395029",
        "genotype": "proxy negative",
        "phenotype": "No *57:01 proxy signal",
        "risk": "Low",
        "recommendation": "No abacavir hypersensitivity signal from this proxy; standard monitoring.",
    }
