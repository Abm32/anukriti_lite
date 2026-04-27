"""
Critical Pharmacogenomic Variants Database

Contains Tier 1 Clinical Variants (CPIC Level A) for CYP enzymes.
Source: PharmVar and CPIC Guidelines

This replaces naive variant counting with targeted allele lookup based on
specific rsIDs (Reference SNP IDs) that are known to affect enzyme function.
"""

from typing import Any, Dict, List, Optional, Tuple, cast

# ---------------------------------------------------------------------------
# Allele → Function mapping (PharmVar/CPIC-style)
# Grounds metabolizer inference in allele calling. Format: "GENE*allele" -> clinical interpretation
# Used for transparent interpretation and benchmark evaluation.
# ---------------------------------------------------------------------------
ALLELE_FUNCTION_MAP: Dict[str, str] = {
    # CYP2D6 (PharmVar)
    "CYP2D6*1": "Normal function",
    "CYP2D6*2": "Normal function",
    "CYP2D6*3": "No function",
    "CYP2D6*4": "No function",
    "CYP2D6*5": "No function (gene deletion)",
    "CYP2D6*6": "No function",
    "CYP2D6*9": "Reduced function",
    "CYP2D6*10": "Reduced function",
    "CYP2D6*17": "Reduced function",
    "CYP2D6*41": "Reduced function",
    "CYP2D6*1xN": "Increased function (duplication)",
    # CYP2C19 (PharmVar)
    "CYP2C19*1": "Normal function",
    "CYP2C19*2": "Loss of function",
    "CYP2C19*3": "Loss of function",
    "CYP2C19*4": "Loss of function",
    "CYP2C19*5": "Loss of function (gene deletion)",
    "CYP2C19*8": "Loss of function",
    "CYP2C19*9": "Reduced function",
    "CYP2C19*17": "Increased function",
    # CYP2C9 (PharmVar)
    "CYP2C9*1": "Normal function",
    "CYP2C9*2": "Reduced function",
    "CYP2C9*3": "Reduced function",
    "CYP2C9*5": "Reduced function",
    "CYP2C9*6": "No function",
    "CYP2C9*8": "Reduced function",
    "CYP2C9*11": "Reduced function",
    # UGT1A1
    "UGT1A1*1": "Normal function",
    "UGT1A1*28": "Reduced function",
    "UGT1A1*6": "Reduced function",
    # TPMT (Thiopurine S-methyltransferase)
    "TPMT*1": "Normal function",
    "TPMT*2": "No function",
    "TPMT*3A": "No function",
    "TPMT*3B": "No function",
    "TPMT*3C": "No function",
    "TPMT*4": "No function",
    # DPYD (Dihydropyrimidine Dehydrogenase)
    "DPYD*1": "Normal function",
    "DPYD*2A": "No function",
    "DPYD*13": "No function",
    "DPYDc.2846A>T": "Reduced function",
    "DPYDHapB3": "Reduced function",
    # SLCO1B1 (transporter)
    "SLCO1B1*1": "Normal function",
    "SLCO1B1*5": "Loss of function",
    "SLCO1B1*15": "Reduced function",
    # Future: HLA-B*57:01 (abacavir hypersensitivity) - add when implementing HLA typing
    # "HLA-B*57:01": "Positive – abacavir hypersensitivity risk"
}

# Genes currently supported for allele→function mapping and profile.
# Beyond CYP Big 3: UGT1A1 (irinotecan), SLCO1B1 (statins) are implemented.
# Planned: HLA-B*57:01 (abacavir) for DILI/hypersensitivity.
SUPPORTED_PROFILE_GENES = [
    "CYP2D6",
    "CYP2C19",
    "CYP2C9",
    "UGT1A1",
    "SLCO1B1",
    "TPMT",
    "DPYD",
]


def get_allele_function(gene: str, allele: str) -> Optional[str]:
    """
    Return PharmVar/CPIC-style function string for a gene*allele.
    E.g. get_allele_function("CYP2D6", "*4") -> "No function"
    """
    key = f"{gene}{allele}" if allele.startswith("*") else f"{gene}*{allele}"
    return ALLELE_FUNCTION_MAP.get(key)


def get_allele_interpretation(gene: str, alleles_found: List[str]) -> List[str]:
    """
    Return list of interpretation strings for display, e.g. ["CYP2D6*4: No function"].
    Structural variants (DEL/DUP) are included.
    """
    out: List[str] = []
    for a in alleles_found:
        if "_DEL" in str(a) or a == f"{gene}_DEL":
            out.append(f"{gene}*5 (gene deletion): No function")
            continue
        if "_DUP" in str(a) or a == f"{gene}_DUP":
            out.append(f"{gene} duplication: Increased function")
            continue
        func = get_allele_function(gene, a)
        if func:
            out.append(f"{gene}{a}: {func}")
        else:
            out.append(f"{gene}{a}: (see PharmVar)")
    return out


# Critical Pharmacogenomic Variants (The "Famous" Ones)
# Source: PharmVar and CPIC Guidelines

VARIANT_DB = {
    "CYP2D6": {
        "rs3892097": {
            "allele": "*4",
            "impact": "Null",
            "name": "Splicing Defect (1846G>A)",
            "activity_score": 0.0,
        },
        "rs1065852": {
            "allele": "*10",
            "impact": "Reduced",
            "name": "100C>T",
            "activity_score": 0.5,
        },
        "rs16947": {
            "allele": "*2",
            "impact": "Normal",
            "name": "2850C>T (Common)",
            "activity_score": 1.0,
        },
        "rs28371725": {
            "allele": "*41",
            "impact": "Reduced",
            "name": "2988G>A",
            "activity_score": 0.5,
        },
        "rs35742686": {
            "allele": "*3",
            "impact": "Null",
            "name": "2549delA",
            "activity_score": 0.0,
        },
        "rs5030655": {
            "allele": "*6",
            "impact": "Null",
            "name": "1707delT",
            "activity_score": 0.0,
        },
        "rs5030865": {
            "allele": "*9",
            "impact": "Reduced",
            "name": "2613_2615delAAG",
            "activity_score": 0.5,
        },
        "rs28371706": {
            "allele": "*17",
            "impact": "Reduced",
            "name": "1023C>T",
            "activity_score": 0.5,
        },
        # Gene deletion (structural variant)
        "CYP2D6_DEL": {
            "allele": "*5",
            "impact": "Null",
            "name": "Gene Deletion",
            "activity_score": 0.0,
        },
        # Gene duplication (structural variant)
        "CYP2D6_DUP": {
            "allele": "*1xN",
            "impact": "Increased",
            "name": "Gene Duplication",
            "activity_score": 1.0,  # Multiplied by copy number
        },
    },
    "CYP2C19": {
        "rs4244285": {
            "allele": "*2",
            "impact": "Null",
            "name": "Splicing Defect (681G>A)",
            "activity_score": 0.0,
        },
        "rs4986893": {
            "allele": "*3",
            "impact": "Null",
            "name": "Stop Codon (636G>A)",
            "activity_score": 0.0,
        },
        "rs12248560": {
            "allele": "*17",
            "impact": "Increased",
            "name": "Promoter Variant (-806C>T)",
            "activity_score": 1.0,
        },
        "rs28399504": {
            "allele": "*4",
            "impact": "Null",
            "name": "1A>G",
            "activity_score": 0.0,
        },
        "rs56337013": {
            "allele": "*8",
            "impact": "Null",
            "name": "358T>C",
            "activity_score": 0.0,
        },
        "rs72552267": {
            "allele": "*9",
            "impact": "Reduced",
            "name": "431G>A",
            "activity_score": 0.5,
        },
        # Gene deletion
        "CYP2C19_DEL": {
            "allele": "*5",
            "impact": "Null",
            "name": "Gene Deletion",
            "activity_score": 0.0,
        },
    },
    "CYP2C9": {
        "rs1799853": {
            "allele": "*2",
            "impact": "Reduced",
            "name": "Arg144Cys (430C>T)",
            "activity_score": 0.5,
        },
        "rs1057910": {
            "allele": "*3",
            "impact": "Reduced",
            "name": "Ile359Leu (1075A>C)",
            "activity_score": 0.5,
        },
        "rs28371686": {
            "allele": "*5",
            "impact": "Reduced",
            "name": "Asp360Glu",
            "activity_score": 0.5,
        },
        "rs9332131": {
            "allele": "*6",
            "impact": "Null",
            "name": "818delA",
            "activity_score": 0.0,
        },
        "rs28371685": {
            "allele": "*8",
            "impact": "Reduced",
            "name": "449G>A",
            "activity_score": 0.5,
        },
        "rs7900194": {
            "allele": "*11",
            "impact": "Reduced",
            "name": "1003C>T",
            "activity_score": 0.5,
        },
        # Gene deletion
        "CYP2C9_DEL": {
            "allele": "*5",
            "impact": "Null",
            "name": "Gene Deletion",
            "activity_score": 0.0,
        },
    },
    # --- Phase II Enzymes (Conjugation) ---
    "UGT1A1": {
        "rs8175347": {
            "allele": "*28",
            "impact": "Reduced",
            "name": "TA Repeat Insertion",
            "activity_score": 0.5,  # Reduced expression
        },
        "rs4148323": {
            "allele": "*6",
            "impact": "Reduced",
            "name": "G71R",
            "activity_score": 0.5,
        },
        "rs3064744": {  # Gilbert's syndrome marker (often linked to *28)
            "allele": "*28",  # Linked
            "impact": "Reduced",
            "name": "Promoter Variant",
            "activity_score": 0.5,
        },
    },
    # --- TPMT (Thiopurine S-methyltransferase) ---
    "TPMT": {
        "rs1800462": {
            "allele": "*2",
            "impact": "Null",
            "name": "238G>C",
            "activity_score": 0.0,
        },
        "rs1800460": {
            "allele": "*3A",
            "impact": "Null",
            "name": "460G>A (with rs1142345)",
            "activity_score": 0.0,
        },
        "rs1142345": {
            "allele": "*3C",
            "impact": "Null",
            "name": "719A>G",
            "activity_score": 0.0,
        },
        "rs1800584": {
            "allele": "*4",
            "impact": "Null",
            "name": "626-1G>A",
            "activity_score": 0.0,
        },
    },
    # --- DPYD (Dihydropyrimidine Dehydrogenase) ---
    "DPYD": {
        "rs3918290": {
            "allele": "*2A",
            "impact": "Null",
            "name": "IVS14+1G>A (splice site)",
            "activity_score": 0.0,
        },
        "rs55886062": {
            "allele": "*13",
            "impact": "Null",
            "name": "1679T>G (I560S)",
            "activity_score": 0.0,
        },
        "rs67376798": {
            "allele": "c.2846A>T",
            "impact": "Reduced",
            "name": "2846A>T (D949V)",
            "activity_score": 0.5,
        },
        "rs56038477": {
            "allele": "HapB3",
            "impact": "Reduced",
            "name": "Haplotype B3",
            "activity_score": 0.5,
        },
    },
    # --- Transporters ---
    "SLCO1B1": {
        "rs4149056": {
            "allele": "*5",
            "impact": "Reduced Transport",
            "name": "Val174Ala",
            "activity_score": 0.0,  # Loss of function
        },
        "rs2306283": {
            "allele": "*15",
            "impact": "Reduced Transport",
            "name": "Asp130Asn",
            "activity_score": 0.5,
        },
    },
}


def get_activity_score_for_allele(gene: str, rsid: str) -> float:
    """
    Get the activity score for a specific variant.

    Args:
        gene: Gene name (CYP2D6, CYP2C19, CYP2C9)
        rsid: Variant rsID or structural variant identifier

    Returns:
        Activity score (0.0 to 1.0), or None if variant not found
    """
    gene_db = VARIANT_DB.get(gene, {})
    variant_info = gene_db.get(rsid)
    if variant_info:
        return float(cast(Any, variant_info.get("activity_score", 0.0)))
    return None


def get_phenotype_prediction(
    gene: str, alleles_found: list, copy_number: int = 2
) -> str:
    """
    Predicts metabolizer status based on found alleles using Activity Score method.

    Based on CPIC/PharmVar guidelines:
    - AS = 0: Poor Metabolizer
    - AS = 0.5-1.0: Intermediate Metabolizer
    - AS = 1.5-2.0: Extensive Metabolizer (Normal)
    - AS > 2.0: Ultra-Rapid Metabolizer (requires duplication)

    Args:
        gene: Gene name (CYP2D6, CYP2C19, CYP2C9)
        alleles_found: List of allele identifiers found (e.g., ['*4', '*10'])
        copy_number: Gene copy number (default 2, can be 0, 1, 2, 3+ for duplications)

    Returns:
        Metabolizer status string
    """
    if not alleles_found:
        # No variants found = wild-type (*1/*1)
        # Default: Extensive Metabolizer (Normal) - THIS IS THE CORRECT DEFAULT
        # In pharmacogenomics, absence of known variants = normal function
        base_score = 1.0
        total_score = base_score * copy_number
    else:
        # Calculate Activity Score from found alleles
        gene_db = VARIANT_DB.get(gene, {})
        total_score = 0.0
        matched_alleles_count = (
            0  # Track how many alleles actually matched our database
        )

        # Check for structural variants first (deletions/duplications)
        has_deletion = False
        has_duplication = False
        for allele in alleles_found:
            if f"{gene}_DEL" in str(allele) or "DEL" in str(allele):
                has_deletion = True
                copy_number = 0  # Gene deletion
            if f"{gene}_DUP" in str(allele) or "DUP" in str(allele):
                has_duplication = True
                copy_number = 3  # At least one extra copy

        # Sum activity scores from alleles
        for allele in alleles_found:
            # Skip structural variant markers (handled above)
            if f"{gene}_DEL" in str(allele) or f"{gene}_DUP" in str(allele):
                continue

            # Wild-type *1 is normal function (1.0) and may not be in VARIANT_DB
            if allele == "*1":
                total_score += 1.0
                matched_alleles_count += 1
                continue

            # Find variant info by allele name
            matched = False
            for rsid, variant_info in gene_db.items():
                if variant_info["allele"] == allele:
                    total_score += float(
                        cast(Any, variant_info.get("activity_score", 0.0))
                    )
                    matched_alleles_count += 1
                    matched = True
                    break

            # If allele didn't match our database, it's an unknown variant
            # Unknown variants should NOT affect phenotype (default to wild-type)
            # We ignore unknown variants - they don't contribute to the score

        # CRITICAL FIX: If NO alleles matched our database, default to Extensive Metabolizer
        # This prevents "guilty until proven innocent" bug
        # Rule: In pharmacogenomics, absence of evidence = normal function
        if matched_alleles_count == 0 and not has_deletion:
            # No known variants found - patient is wild-type (*1/*1)
            # Default assumption: Extensive Metabolizer (Normal)
            total_score = 1.0 * copy_number

        # Adjust for copy number (duplications/deletions)
        if has_deletion or copy_number == 0:
            # Gene deletion - no function
            total_score = 0.0
        elif has_duplication or copy_number > 2:
            # Duplication detected - multiply activity score
            total_score = total_score * (copy_number / 2.0)
        elif copy_number == 1:
            # Single copy (hemizygous)
            total_score = total_score / 2.0

    # Classify based on Activity Score
    # CRITICAL: Default assumption is Extensive Metabolizer (normal function)
    # Only classify as Poor/Intermediate if we have evidence of reduced/null function
    # This prevents dangerous "guilty until proven innocent" classification
    if total_score > 2.0:
        return "ultra_rapid_metabolizer"
    elif total_score >= 1.5:
        return "extensive_metabolizer"  # Normal function (wild-type *1/*1 = 2.0)
    elif total_score >= 0.5:
        return "intermediate_metabolizer"
    else:
        # Only return Poor Metabolizer if we have evidence (matched alleles with 0.0 score)
        # If total_score is 0.0 but no alleles matched, we already set it to 2.0 above
        return "poor_metabolizer"


def get_variant_info(gene: str, rsid: str) -> dict:
    """
    Get detailed information about a specific variant.

    Args:
        gene: Gene name
        rsid: Variant rsID

    Returns:
        Dictionary with variant information, or None if not found
    """
    gene_db = VARIANT_DB.get(gene, {})
    return gene_db.get(rsid)


def list_critical_variants(gene: str) -> list:
    """
    List all critical variants for a given gene.

    Args:
        gene: Gene name

    Returns:
        List of rsIDs for that gene
    """
    gene_db = VARIANT_DB.get(gene, {})
    return list(gene_db.keys())
