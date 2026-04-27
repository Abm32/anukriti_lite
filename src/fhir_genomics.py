"""
HL7 FHIR Genomics Reporting output module.

Generates FHIR R4 resources conformant with the HL7 FHIR Genomics Reporting
Implementation Guide (https://hl7.org/fhir/uv/genomics-reporting/).

Key resources generated:
  - DiagnosticReport (genomics-report profile)
  - Observation/variant — one per detected variant
  - Observation/genotype — diplotype per gene
  - Observation/implication — therapeutic implication per gene

This enables EHR integration with Epic SMART on FHIR, Cerner, and other
HL7-compliant systems that consume genomic diagnostic reports.

No external FHIR library dependency — constructs raw dicts (JSON-serializable).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# FHIR Genomics Reporting IG profile URLs
_PROFILES = {
    "report": "http://hl7.org/fhir/uv/genomics-reporting/StructureDefinition/genomics-report",
    "genotype": "http://hl7.org/fhir/uv/genomics-reporting/StructureDefinition/genotype",
    "variant": "http://hl7.org/fhir/uv/genomics-reporting/StructureDefinition/variant",
    "implication": "http://hl7.org/fhir/uv/genomics-reporting/StructureDefinition/therapeutic-implication",
    "overall": "http://hl7.org/fhir/uv/genomics-reporting/StructureDefinition/overall-interpretation",
}

# LOINC codes for FHIR Genomics Reporting
_LOINC = {
    "genomic_report": "81247-9",  # Master HL7 genetic variant reporting panel
    "genotype": "84413-4",  # Genotype display name
    "diplotype": "81252-9",  # Discrete genetic variant
    "drug_efficacy": "51961-1",  # Predicted phenotype
    "drug_metabolism": "79715-7",  # Drug metabolism phenotype
    "therapeutic_impl": "81259-4",  # Associated therapy
    "variant_id": "81252-9",  # Variant HGVS
    "ancestry": "86206-0",  # Population ancestry observation
}

# HGNC gene IDs for common PGx genes (for FHIR coding)
_HGNC_IDS: Dict[str, str] = {
    "CYP2D6": "HGNC:2625",
    "CYP2C19": "HGNC:2621",
    "CYP2C9": "HGNC:2623",
    "CYP3A4": "HGNC:2637",
    "CYP3A5": "HGNC:2638",
    "CYP1A2": "HGNC:2596",
    "CYP2B6": "HGNC:2615",
    "NAT2": "HGNC:7646",
    "UGT1A1": "HGNC:12530",
    "SLCO1B1": "HGNC:10959",
    "VKORC1": "HGNC:23663",
    "TPMT": "HGNC:12014",
    "DPYD": "HGNC:3012",
    "GSTM1": "HGNC:4632",
    "GSTT1": "HGNC:4641",
    "HLA_B5701": "HGNC:4932",
    "HLA_B1502": "HGNC:4932",
}

# PharmGKB drug IDs for common drugs (for FHIR coding)
_PHARMGKB_DRUGS: Dict[str, str] = {
    "warfarin": "PA451906",
    "clopidogrel": "PA449053",
    "codeine": "PA449088",
    "simvastatin": "PA451363",
    "tacrolimus": "PA451578",
    "efavirenz": "PA449441",
    "isoniazid": "PA449957",
    "azathioprine": "PA448516",
    "fluorouracil": "PA128406956",
    "capecitabine": "PA448771",
    "irinotecan": "PA450085",
    "abacavir": "PA448004",
    "cisplatin": "PA449014",
    "clozapine": "PA449061",
}


def _fhir_ref(resource_type: str, ref_id: str) -> Dict[str, str]:
    return {"reference": f"{resource_type}/{ref_id}"}


def _fhir_coding(system: str, code: str, display: str = "") -> Dict[str, Any]:
    c: Dict[str, Any] = {"system": system, "code": code}
    if display:
        c["display"] = display
    return c


def _loinc_coding(code: str, display: str = "") -> Dict[str, Any]:
    return _fhir_coding("http://loinc.org", code, display)


def _now_fhir() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_genotype_observation(
    gene: str,
    diplotype: str,
    phenotype: str,
    report_id: str,
    obs_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a FHIR Observation/genotype resource for a single gene."""
    oid = obs_id or str(uuid.uuid4())
    hgnc = _HGNC_IDS.get(gene, "")
    gene_display = gene.replace("_", "-")

    obs: Dict[str, Any] = {
        "resourceType": "Observation",
        "id": oid,
        "meta": {"profile": [_PROFILES["genotype"]]},
        "status": "final",
        "category": [
            {
                "coding": [
                    _fhir_coding(
                        "http://terminology.hl7.org/CodeSystem/observation-category",
                        "laboratory",
                        "Laboratory",
                    )
                ]
            }
        ],
        "code": {
            "coding": [_loinc_coding(_LOINC["genotype"], "Genotype display name")],
            "text": f"{gene_display} Genotype",
        },
        "issued": _now_fhir(),
        "derivedFrom": [_fhir_ref("DiagnosticReport", report_id)],
        "component": [
            {
                "code": {
                    "coding": [
                        _loinc_coding(_LOINC["diplotype"], "Discrete genetic variant")
                    ],
                    "text": "Diplotype",
                },
                "valueCodeableConcept": {
                    "coding": [
                        _fhir_coding(
                            "http://www.pharmvar.org",
                            f"{gene}:{diplotype}",
                            f"{gene_display} {diplotype}",
                        )
                    ],
                    "text": f"{gene_display} {diplotype}",
                },
            },
            {
                "code": {
                    "coding": [
                        _loinc_coding(
                            _LOINC["drug_metabolism"], "Drug metabolism phenotype"
                        )
                    ],
                    "text": "Metabolizer Phenotype",
                },
                "valueCodeableConcept": {
                    "coding": [
                        _fhir_coding(
                            "http://www.cpicpgx.org/terminology/phenotype",
                            phenotype.replace(" ", "_").lower(),
                            phenotype,
                        )
                    ],
                    "text": phenotype,
                },
            },
        ],
    }

    if hgnc:
        obs["component"].append(
            {
                "code": {
                    "coding": [
                        _fhir_coding("http://loinc.org", "48018-6", "Gene studied [ID]")
                    ],
                    "text": "Gene",
                },
                "valueCodeableConcept": {
                    "coding": [
                        _fhir_coding("http://www.genenames.org", hgnc, gene_display)
                    ],
                    "text": gene_display,
                },
            }
        )

    return obs


def build_therapeutic_implication(
    gene: str,
    phenotype: str,
    drug_name: str,
    recommendation: str,
    cpic_level: str,
    report_id: str,
    obs_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a FHIR Observation/therapeutic-implication resource."""
    oid = obs_id or str(uuid.uuid4())
    gene_display = gene.replace("_", "-")
    pharmgkb_id = _PHARMGKB_DRUGS.get(drug_name.lower(), "")

    drug_coding: Dict[str, Any] = {"text": drug_name}
    if pharmgkb_id:
        drug_coding["coding"] = [
            _fhir_coding("https://www.pharmgkb.org", pharmgkb_id, drug_name)
        ]

    return {
        "resourceType": "Observation",
        "id": oid,
        "meta": {"profile": [_PROFILES["implication"]]},
        "status": "final",
        "category": [
            {
                "coding": [
                    _fhir_coding(
                        "http://terminology.hl7.org/CodeSystem/observation-category",
                        "laboratory",
                    )
                ]
            }
        ],
        "code": {
            "coding": [_loinc_coding(_LOINC["therapeutic_impl"], "Associated therapy")],
            "text": f"{gene_display} Therapeutic Implication for {drug_name}",
        },
        "issued": _now_fhir(),
        "derivedFrom": [_fhir_ref("DiagnosticReport", report_id)],
        "component": [
            {
                "code": {"coding": [_loinc_coding("51963-7", "Medication assessed")]},
                "valueCodeableConcept": drug_coding,
            },
            {
                "code": {"coding": [_loinc_coding("93044-6", "Level of evidence")]},
                "valueCodeableConcept": {
                    "coding": [
                        _fhir_coding(
                            "http://www.cpicpgx.org/terminology/level",
                            cpic_level,
                            f"CPIC Level {cpic_level}",
                        )
                    ],
                    "text": f"CPIC Level {cpic_level}",
                },
            },
            {
                "code": {
                    "coding": [_loinc_coding("79716-5", "Therapeutic implication")]
                },
                "valueString": recommendation,
            },
            {
                "code": {
                    "coding": [
                        _loinc_coding(
                            _LOINC["drug_metabolism"], "Drug metabolism phenotype"
                        )
                    ]
                },
                "valueCodeableConcept": {
                    "coding": [
                        _fhir_coding(
                            "http://www.cpicpgx.org/terminology/phenotype",
                            phenotype.replace(" ", "_").lower(),
                            phenotype,
                        )
                    ],
                    "text": phenotype,
                },
            },
        ],
    }


def build_fhir_genomics_report(
    patient_id: str,
    gene_results: List[Dict[str, Any]],
    drug_name: Optional[str] = None,
    ancestry: Optional[str] = None,
    report_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a full FHIR R4 Bundle containing a DiagnosticReport (genomics-report profile)
    with genotype Observations and therapeutic implication Observations.

    Args:
        patient_id: De-identified patient/sample identifier.
        gene_results: List of dicts, each with keys:
            gene (str), diplotype (str), phenotype (str),
            recommendation (str, optional), cpic_level (str, optional),
            drug_name (str, optional).
        drug_name: The drug being analyzed (used for implication observations).
        ancestry: Reported or inferred ancestry for equity contextualization.
        report_id: Optional stable report ID; generated if not provided.

    Returns:
        FHIR R4 Bundle (transaction) as a dict, JSON-serializable.
    """
    rid = report_id or str(uuid.uuid4())
    now = _now_fhir()

    # Build contained Observations
    genotype_obs: List[Dict[str, Any]] = []
    implication_obs: List[Dict[str, Any]] = []
    observation_refs: List[Dict[str, str]] = []

    for result in gene_results:
        gene = result.get("gene", "")
        diplotype = result.get("diplotype", "*1/*1")
        phenotype = result.get("phenotype", "Unknown")
        recommendation = result.get("recommendation", "")
        cpic_level = result.get("cpic_level", "A")
        drug = result.get("drug_name") or drug_name or ""

        # Genotype observation
        geno_id = str(uuid.uuid4())
        geno_obs = build_genotype_observation(gene, diplotype, phenotype, rid, geno_id)
        genotype_obs.append(geno_obs)
        observation_refs.append(_fhir_ref("Observation", geno_id))

        # Therapeutic implication (only when drug is present and recommendation exists)
        if (
            drug
            and recommendation
            and recommendation
            not in (
                "No specific guideline available",
                "No guideline for this phenotype",
            )
        ):
            impl_id = str(uuid.uuid4())
            impl_obs = build_therapeutic_implication(
                gene, phenotype, drug, recommendation, cpic_level, rid, impl_id
            )
            implication_obs.append(impl_obs)
            observation_refs.append(_fhir_ref("Observation", impl_id))

    # DiagnosticReport
    diagnostic_report: Dict[str, Any] = {
        "resourceType": "DiagnosticReport",
        "id": rid,
        "meta": {"profile": [_PROFILES["report"]]},
        "status": "final",
        "category": [
            {
                "coding": [
                    _fhir_coding(
                        "http://terminology.hl7.org/CodeSystem/v2-0074",
                        "GE",
                        "Genetics",
                    )
                ]
            }
        ],
        "code": {
            "coding": [
                _loinc_coding(
                    _LOINC["genomic_report"],
                    "Master HL7 genetic variant reporting panel",
                )
            ],
            "text": "Pharmacogenomics Report",
        },
        "subject": {"identifier": {"value": patient_id}},
        "issued": now,
        "result": observation_refs,
        "conclusion": _build_conclusion(gene_results, drug_name, ancestry),
        "extension": [
            {
                "url": "http://hl7.org/fhir/uv/genomics-reporting/StructureDefinition/recommended-action",
                "valueReference": {
                    "display": (
                        "Consult a clinical pharmacist or pharmacogenomics specialist "
                        "before making prescribing decisions based on this report."
                    )
                },
            }
        ],
    }

    if ancestry:
        diagnostic_report["extension"].append(
            {
                "url": "http://hl7.org/fhir/StructureDefinition/patient-ancestry",
                "valueString": ancestry,
            }
        )

    # FHIR Bundle (transaction)
    bundle_entries: List[Dict[str, Any]] = []

    bundle_entries.append(
        {
            "fullUrl": f"DiagnosticReport/{rid}",
            "resource": diagnostic_report,
            "request": {"method": "POST", "url": "DiagnosticReport"},
        }
    )

    for obs in genotype_obs + implication_obs:
        bundle_entries.append(
            {
                "fullUrl": f"Observation/{obs['id']}",
                "resource": obs,
                "request": {"method": "POST", "url": "Observation"},
            }
        )

    return {
        "resourceType": "Bundle",
        "id": str(uuid.uuid4()),
        "meta": {
            "profile": [
                "http://hl7.org/fhir/uv/genomics-reporting/StructureDefinition/genomics-bundle"
            ]
        },
        "type": "transaction",
        "timestamp": now,
        "entry": bundle_entries,
    }


def _build_conclusion(
    gene_results: List[Dict[str, Any]],
    drug_name: Optional[str],
    ancestry: Optional[str],
) -> str:
    lines = [
        "Pharmacogenomics analysis completed. CPIC-aligned guideline interpretation."
    ]
    if drug_name:
        lines.append(f"Drug analyzed: {drug_name}.")
    abnormal = [
        r
        for r in gene_results
        if r.get("phenotype")
        and r["phenotype"]
        not in (
            "Normal Metabolizer",
            "Extensive Metabolizer",
            "Rapid Acetylator",
            "Normal Function",
            "Unknown",
        )
    ]
    if abnormal:
        genes_str = ", ".join(r["gene"] for r in abnormal)
        lines.append(
            f"Actionable PGx findings detected in: {genes_str}. "
            "Clinical review recommended before prescribing affected medications."
        )
    else:
        lines.append(
            "No high-priority actionable PGx findings detected for the analyzed genes."
        )
    if ancestry:
        lines.append(
            f"Reported ancestry: {ancestry}. Allele frequency context applied where available."
        )
    lines.append(
        "This report is generated by SynthaTrial (research prototype, Stage 0). "
        "Not validated for clinical use. Consult a clinical pharmacist or "
        "pharmacogenomics specialist for patient care decisions."
    )
    return " ".join(lines)


def pgx_results_to_fhir_input(
    pgx_analysis: Dict[str, Any],
    drug_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Convert a PGx analysis result dict (from /analyze endpoint) into the
    gene_results list format expected by build_fhir_genomics_report.
    """
    gene_results: List[Dict[str, Any]] = []

    # Extract from structured gene profiles
    genes = pgx_analysis.get("gene_profiles") or pgx_analysis.get("genes") or []
    if isinstance(genes, list):
        for g in genes:
            if isinstance(g, dict) and g.get("gene"):
                gene_results.append(
                    {
                        "gene": g.get("gene", ""),
                        "diplotype": g.get("diplotype")
                        or g.get("allele_call")
                        or "*1/*1",
                        "phenotype": g.get("phenotype") or g.get("status") or "Unknown",
                        "recommendation": g.get("recommendation")
                        or g.get("guideline")
                        or "",
                        "cpic_level": g.get("cpic_level") or "A",
                        "drug_name": drug_name or g.get("drug_name") or "",
                    }
                )

    # Fallback: extract from flat genetics string if no structured genes
    if not gene_results and pgx_analysis.get("genetics"):
        genetics_str = str(pgx_analysis["genetics"])
        gene_results.append(
            {
                "gene": "Multiple",
                "diplotype": genetics_str[:100],
                "phenotype": "See genetics field",
                "recommendation": "",
                "cpic_level": "A",
                "drug_name": drug_name or "",
            }
        )

    return gene_results
