"""
Deterministic PGx call verification (Agent 2).

Labels the PharmVar + CPIC calling step with explicit coverage / grounding states.
No LLM calls — pure table + genotype checks.
"""

from __future__ import annotations

import re
from typing import Dict, Set, Tuple

import pandas as pd

# Status strings (stable API; use in metrics / UI)
VERIFY_VERIFIED = "verified_against_pharmvar_cpic_table"
VERIFY_AMBIGUOUS_GT = "ambiguous_genotype"
VERIFY_DIPLOTYPE_NOT_IN_CPIC = "diplotype_not_in_cpic_table"
VERIFY_LOCUS_NOT_QUERIED = "locus_not_queried"


def _alt_dosage(gt: str):
    """Same semantics as allele_caller.alt_dosage (avoid import cycle)."""
    if not gt:
        return None
    g = gt.replace("|", "/").strip()
    if g in ("0/0", "0|0"):
        return 0
    if g in ("0/1", "1/0", "0|1", "1|0"):
        return 1
    if g in ("1/1", "1|1"):
        return 2
    return None


def collect_pharmvar_rsids(table: pd.DataFrame) -> Set[str]:
    """All rsIDs that the PharmVar table uses for star-allele definitions."""
    out: Set[str] = set()
    if "rsid" in table.columns:
        for _, row in table.iterrows():
            r = str(row.get("rsid", "")).strip()
            if r and r not in ("-", ""):
                out.add(r)
    if "rsids" in table.columns:
        for _, row in table.iterrows():
            rsids_str = str(row.get("rsids", "")).strip()
            if not rsids_str:
                continue
            for r in rsids_str.split(","):
                r = r.strip()
                if r:
                    out.add(r)
    return out


def verify_pharmvar_cpic_call(
    table: pd.DataFrame,
    translation: Dict[str, str],
    variants: Dict[str, Tuple[str, str, str]],
    diplotype: str,
    phenotype_display: str,
) -> Tuple[str, str]:
    """
    Return (verification_status, verification_detail).

    Priority: ambiguous genotype → CPIC miss → locus not queried → verified.
    """
    table_rsids = collect_pharmvar_rsids(table)
    norm_diplo = diplotype.strip()
    keys = set(variants.keys())
    observed = table_rsids & keys

    for rsid in sorted(observed):
        gt = variants[rsid][2]
        if _alt_dosage(gt) is None:
            return (
                VERIFY_AMBIGUOUS_GT,
                f"Genotype at {rsid} is not a resolved diploid call ({gt!r}); "
                "star-allele dosage is ambiguous.",
            )

    in_translation = norm_diplo in translation
    unknown_pheno = (not in_translation) or (
        phenotype_display.strip().lower().startswith("unknown")
    )
    if unknown_pheno:
        return (
            VERIFY_DIPLOTYPE_NOT_IN_CPIC,
            "Diplotype is not mapped in the bundled CPIC phenotype table, "
            "or resolves to an unknown metabolizer label.",
        )

    if not observed:
        return (
            VERIFY_LOCUS_NOT_QUERIED,
            "No PharmVar-defining rsID from this gene was present in the variant input; "
            "reference star alleles (*1/*1) were assumed. "
            "If the VCF omitted hom-ref rows, this may still match the sample.",
        )

    return (
        VERIFY_VERIFIED,
        "Observed variant sites overlap the PharmVar table; diplotype maps to a CPIC "
        "phenotype entry; genotypes at those sites are resolved.",
    )
