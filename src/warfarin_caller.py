"""
Deterministic Warfarin PGx: CYP2C9 + VKORC1.

Uses curated PharmVar allele definitions (CYP2C9) and variant table (VKORC1)
plus CPIC-style warfarin_response.json for dose-sensitivity interpretation.
Benchmark-validated; chr10 (CYP2C9) and chr16 (VKORC1) drive the pipeline when present.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .allele_caller import (
    build_diplotype_simple,
    call_star_alleles_simple,
    load_pharmvar_table,
)

DEFAULT_PGX_DIR = Path(__file__).resolve().parent.parent / "data" / "pgx"


def alt_dosage(gt: str):
    """VCF genotype → ALT allele dosage (0, 1, or 2)."""
    if gt in ("0/0", "0|0"):
        return 0
    if gt in ("0/1", "1/0", "0|1", "1|0"):
        return 1
    if gt in ("1/1", "1|1"):
        return 2
    return None


def _pgx_path(*parts: str, base_dir: Optional[Path] = None) -> Path:
    base = base_dir or DEFAULT_PGX_DIR
    return base.joinpath(*parts)


def call_cyp2c9(
    patient_variants: Dict[str, str], base_dir: Optional[Path] = None
) -> str:
    """
    Detect CYP2C9 *2 and *3 alleles from rsIDs (simple variant dict: rsid -> alt).
    Default = *1. Returns diplotype string (e.g. *1/*2, *2/*3).
    """
    path = _pgx_path("pharmvar", "cyp2c9_alleles.tsv", base_dir=base_dir)
    if not path.is_file():
        return "*1/*1"
    table = load_pharmvar_table(path)
    detected = call_star_alleles_simple(patient_variants, table)
    return build_diplotype_simple(detected)


def call_vkorc1(
    patient_variants: Dict[str, str], base_dir: Optional[Path] = None
) -> str:
    """
    VKORC1 genotype at rs9923231. Returns GG / GA / AA.
    patient_variants: rsid -> alt (single allele) or "G,A" / "A,G" for heterozygous.
    Single letter: "A" -> one A allele (other assumed G) -> GA; "G" -> GG.
    """
    raw = patient_variants.get("rs9923231")
    if raw is None:
        return "Unknown"
    s = str(raw).strip().upper()
    if "," in s:
        alleles = [a.strip().upper() for a in s.split(",") if a.strip()]
        if len(alleles) >= 2:
            uniq = sorted(set(alleles))
            if uniq == ["A", "G"]:
                return "GA"
            if uniq == ["A"]:
                return "AA"
            if uniq == ["G"]:
                return "GG"
        if len(alleles) == 1:
            return "GA" if alleles[0] == "A" else "GG"
    if s == "A":
        return "GA"
    if s == "G":
        return "GG"
    return "Unknown"


def load_warfarin_table(base_dir: Optional[Path] = None) -> Dict[str, str]:
    """Load CPIC-style warfarin_response.json (key -> recommendation)."""
    path = _pgx_path("cpic", "warfarin_response.json", base_dir=base_dir)
    if not path.is_file():
        return {}
    with open(path, "r") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def interpret_warfarin(
    patient_variants: Dict[str, str], base_dir: Optional[Path] = None
) -> Dict[str, str]:
    """
    Deterministic Warfarin PGx interpretation using CYP2C9 + VKORC1.
    patient_variants: rsid -> alt (e.g. rs1799853 -> T, rs9923231 -> A or G,A).
    Returns dict with drug, CYP2C9, VKORC1, recommendation.
    """
    cyp2c9 = call_cyp2c9(patient_variants, base_dir=base_dir)
    vkorc1 = call_vkorc1(patient_variants, base_dir=base_dir)
    table = load_warfarin_table(base_dir=base_dir)
    key = f"CYP2C9 {cyp2c9} + VKORC1 {vkorc1}"
    recommendation = table.get(
        key, "Unknown genotype combination — consult CPIC guideline"
    )
    return {
        "drug": "Warfarin",
        "CYP2C9": cyp2c9,
        "VKORC1": vkorc1,
        "recommendation": recommendation,
    }


def call_cyp2c9_from_vcf(
    var_map: Dict[str, Tuple[str, str, str]], base_dir: Optional[Path] = None
) -> str:
    """
    CYP2C9 diplotype from VCF genotype map; dosage-correct (0/1 → *1/*2, 1/1 → *2/*2).
    """
    path = _pgx_path("pharmvar", "cyp2c9_alleles.tsv", base_dir=base_dir)
    if not path.is_file():
        return "*1/*1"
    table = load_pharmvar_table(path)
    detected: List[str] = []
    for _, row in table.iterrows():
        rsid = str(row.get("rsid", "")).strip()
        alt_needed = str(row.get("alt", "")).strip()
        allele = str(row.get("allele", "")).strip()
        if not rsid or rsid in ("-", "") or not allele:
            continue
        if rsid not in var_map:
            continue
        ref, alt, gt = var_map[rsid]
        if alt != alt_needed:
            continue
        dosage = alt_dosage(gt)
        if dosage == 1:
            detected.append(allele)
        elif dosage == 2:
            detected.append(allele)
            detected.append(allele)
    if not detected:
        return "*1/*1"
    if len(detected) == 1:
        return f"*1/{detected[0]}"
    two = sorted(detected[:2])
    return f"{two[0]}/{two[1]}"


def call_vkorc1_from_gt(ref: str, alt: str, gt: str) -> str:
    """VKORC1 genotype GG/GA/AA from VCF ref, alt, and GT (diploid-correct)."""
    dosage = alt_dosage(gt)
    if dosage == 0:
        return f"{ref}{ref}"
    if dosage == 1:
        return f"{ref}{alt}"
    if dosage == 2:
        return f"{alt}{alt}"
    return "Unknown"


def _vkorc1_genotype_from_vcf(var_map: Dict[str, Tuple[str, str, str]]) -> str:
    """Get VKORC1 genotype GG/GA/AA from VCF-style rsid -> (ref, alt, gt)."""
    t = var_map.get("rs9923231")
    if not t:
        return "Unknown"
    ref, alt, gt = t
    return call_vkorc1_from_gt(ref, alt, gt)


def interpret_warfarin_from_vcf(
    variant_map: Dict[str, Tuple[str, str, str]], base_dir: Optional[Path] = None
) -> Optional[Dict[str, str]]:
    """
    Deterministic Warfarin interpretation from VCF genotype map (rsid -> (ref, alt, gt)).
    Uses CYP2C9 PharmVar table for star alleles and VKORC1 rs9923231 for genotype.
    Returns same shape as interpret_warfarin, or None if no Warfarin-relevant variants.
    """
    cyp2c9_path = _pgx_path("pharmvar", "cyp2c9_alleles.tsv", base_dir=base_dir)
    if not cyp2c9_path.is_file():
        return None
    cyp2c9 = call_cyp2c9_from_vcf(variant_map, base_dir=base_dir)
    vkorc1 = _vkorc1_genotype_from_vcf(variant_map)
    warfarin_table = load_warfarin_table(base_dir=base_dir)
    key = f"CYP2C9 {cyp2c9} + VKORC1 {vkorc1}"
    recommendation = warfarin_table.get(
        key, "Unknown genotype combination — consult CPIC guideline"
    )
    return {
        "drug": "Warfarin",
        "CYP2C9": cyp2c9,
        "VKORC1": vkorc1,
        "recommendation": recommendation,
    }
