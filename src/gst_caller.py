"""
CPIC-grade GSTM1/GSTT1 null genotype caller.

GSTM1 and GSTT1 are glutathione S-transferase genes that undergo homozygous
deletion polymorphisms. Unlike SNP-based genes, the "null" genotype is the
complete absence of gene copies (copy number = 0).

Detection approach:
- VCF/array: Homozygous DEL at the gene locus
- PCR-based: Absence of amplification product (clinical standard)
- This caller interprets DEL VCF records or absence-of-signal markers

CPIC Level B — evidence supports association but clinical guidelines less
prescriptive than Level A genes.

Key drugs: busulfan, oxaliplatin, cisplatin, cyclophosphamide (cancer chemotherapy).

Equity note:
- GSTM1 null frequency: AFR ~25%, EUR ~50%, EAS ~55%, SAS ~35%
- GSTT1 null frequency: AFR ~20%, EUR ~15%, EAS ~55%, SAS ~25%
- Combined null (both genes deleted): EAS patients at highest risk
  for cisplatin ototoxicity in pediatric cancer treatment

Data: data/pgx/cpic/gst_phenotypes.json, gst_guidelines.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

DEFAULT_PGX_DIR = Path(__file__).resolve().parent.parent / "data" / "pgx"

GSTM1_LOCUS_RSIDS = {"rs1056806", "rs4147581", "rs366631"}
GSTT1_LOCUS_RSIDS = {"rs71748309", "rs2266637"}

_NULL_MARKER_RSIDS: Dict[str, str] = {
    "rs1056806": "GSTM1",
    "rs4147581": "GSTM1",
    "rs366631": "GSTM1",
    "rs71748309": "GSTT1",
    "rs2266637": "GSTT1",
}


def _pgx_path(*parts: str, base_dir: Optional[Path] = None) -> Path:
    base = base_dir or DEFAULT_PGX_DIR
    return base.joinpath(*parts)


def load_gst_guidelines(base_dir: Optional[Path] = None) -> Dict:
    path = _pgx_path("cpic", "gst_guidelines.json", base_dir=base_dir)
    if not path.is_file():
        return {}
    with open(path) as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def interpret_gstm1(
    copy_number: int = 2,
    drug_name: str = "",
    base_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Interpret GSTM1 phenotype from copy number.
    copy_number: 0 = Null/Null, 1 = Present/Null, 2 = Present/Present
    """
    if copy_number == 0:
        genotype = "Null/Null"
        phenotype = "No Function (Null Genotype)"
    elif copy_number == 1:
        genotype = "Present/Null"
        phenotype = "Intermediate Function"
    else:
        genotype = "Present/Present"
        phenotype = "Normal Function"

    recommendation = "No specific guideline available"
    drug = (drug_name or "").strip().lower()
    if drug:
        guidelines = load_gst_guidelines(base_dir=base_dir)
        if drug in guidelines:
            recommendation = guidelines[drug].get(
                phenotype, "No guideline for this phenotype"
            )

    return {
        "gene": "GSTM1",
        "genotype": genotype,
        "copy_number": copy_number,
        "phenotype": phenotype,
        "recommendation": recommendation,
        "cpic_level": "B",
        "equity_note": (
            "GSTM1 null frequency varies by ancestry: ~25% AFR, ~50% EUR, ~55% EAS. "
            "Null genotype linked to increased platinum chemotherapy neurotoxicity "
            "and altered busulfan metabolism in HSCT conditioning."
        ),
    }


def interpret_gstt1(
    copy_number: int = 2,
    drug_name: str = "",
    base_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Interpret GSTT1 phenotype from copy number.
    copy_number: 0 = Null/Null, 1 = Present/Null, 2 = Present/Present
    """
    if copy_number == 0:
        genotype = "Null/Null"
        phenotype = "No Function (Null Genotype)"
    elif copy_number == 1:
        genotype = "Present/Null"
        phenotype = "Intermediate Function"
    else:
        genotype = "Present/Present"
        phenotype = "Normal Function"

    recommendation = "No specific guideline available"
    drug = (drug_name or "").strip().lower()
    if drug:
        guidelines = load_gst_guidelines(base_dir=base_dir)
        if drug in guidelines:
            recommendation = guidelines[drug].get(
                phenotype, "No guideline for this phenotype"
            )

    return {
        "gene": "GSTT1",
        "genotype": genotype,
        "copy_number": copy_number,
        "phenotype": phenotype,
        "recommendation": recommendation,
        "cpic_level": "B",
        "equity_note": (
            "GSTT1 null frequency: ~20% AFR, ~15% EUR, ~55% EAS. "
            "Combined GSTM1+GSTT1 null genotype ('double null') is most frequent "
            "in East Asian patients and confers highest cisplatin ototoxicity risk."
        ),
    }


def interpret_gst_from_vcf(
    var_map: Dict[str, Tuple[str, str, str]],
    drug_name: str = "",
    base_dir: Optional[Path] = None,
) -> Dict[str, Dict]:
    """
    Infer GSTM1/GSTT1 null genotype from VCF.
    Looks for DEL/homozygous absence at known locus markers.
    Returns dict with 'GSTM1' and 'GSTT1' interpretation dicts.
    """
    gstm1_cn = 2
    gstt1_cn = 2

    for rsid, (ref, alt, gt) in var_map.items():
        gene = _NULL_MARKER_RSIDS.get(rsid)
        if gene is None:
            continue
        alt_upper = (alt or "").upper()
        if "<DEL>" in alt_upper or "DEL" in alt_upper or alt_upper == ".":
            if "0/0" in gt or "0|0" in gt:
                pass
            elif "1/1" in gt or "1|1" in gt:
                if gene == "GSTM1":
                    gstm1_cn = 0
                else:
                    gstt1_cn = 0
            elif "0/1" in gt or "0|1" in gt or "1/0" in gt or "1|0" in gt:
                if gene == "GSTM1":
                    gstm1_cn = 1
                else:
                    gstt1_cn = 1

    return {
        "GSTM1": interpret_gstm1(gstm1_cn, drug_name=drug_name, base_dir=base_dir),
        "GSTT1": interpret_gstt1(gstt1_cn, drug_name=drug_name, base_dir=base_dir),
    }


def interpret_gst_combined(
    gstm1_copy_number: int = 2,
    gstt1_copy_number: int = 2,
    drug_name: str = "",
    base_dir: Optional[Path] = None,
) -> Dict[str, object]:
    """
    Combined GSTM1+GSTT1 interpretation with combined phenotype and drug guidance.
    """
    gstm1 = interpret_gstm1(gstm1_copy_number, drug_name=drug_name, base_dir=base_dir)
    gstt1 = interpret_gstt1(gstt1_copy_number, drug_name=drug_name, base_dir=base_dir)

    double_null = gstm1_copy_number == 0 and gstt1_copy_number == 0
    combined_note = ""
    if double_null:
        combined_note = (
            "DOUBLE NULL GENOTYPE (GSTM1 null + GSTT1 null): Highest risk category. "
            "Associated with significantly elevated cisplatin ototoxicity in pediatric "
            "oncology and increased platinum chemotherapy toxicity broadly. "
            "Most prevalent in East Asian populations (~30% double null)."
        )

    return {
        "GSTM1": gstm1,
        "GSTT1": gstt1,
        "combined_null": double_null,
        "combined_note": combined_note,
    }
