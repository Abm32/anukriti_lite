# SynthaTrial Clinical Validation Roadmap

**Version:** 1.0
**Last updated:** April 2026
**Classification:** Non-device Clinical Decision Support (CDS) — 21st Century Cures Act §520(o)(1)(E)

---

## Overview

This document defines the three-stage pathway from research prototype to clinical utility for the SynthaTrial pharmacogenomics engine. It is intended for regulatory reviewers, clinical partners, IRB committees, and pharmaceutical/CRO integration partners.

SynthaTrial is currently positioned as a **research-grade pharmacogenomics tool** (Stage 0). The roadmap below describes the evidence-generation activities required to progress to clinical decision support (Stage 1) and real-world clinical utility (Stage 2).

---

## Regulatory Classification (Current)

SynthaTrial meets the four-factor test for **non-device CDS** under 21st Century Cures Act §520(o)(1)(E):

| Factor | SynthaTrial Status |
|--------|-------------------|
| Not intended to acquire, process, or analyze medical images or signals | ✅ Processes VCF genomic data only |
| Not intended for use in connection with a serious or immediately life-threatening condition | ✅ Research use; outputs labeled as decision support, not prescription |
| Intended for use by a healthcare professional who can independently review the basis | ✅ All CPIC citations, diplotype data, and confidence tiers are shown |
| Not intended to replace clinical judgment | ✅ All outputs include "consult your healthcare provider" framing |

**Reference:** [FDA CDS Compliance](FDA_CDS_COMPLIANCE.md)

---

## Stage 0: Research Prototype (Current — Q1 2026)

**Status:** Operational
**Use:** Research, drug development simulation, educational

### What Is In Place

- Deterministic CPIC/PharmVar allele calling for 15 Tier-1 pharmacogenes
- Population diversity simulation using 1000 Genomes Phase 3 (2,504 individuals; AFR, AMR, EAS, EUR, SAS superpopulations)
- AWS Bedrock (Nova/Claude) LLM explanation layer — clearly labeled as AI-generated context, not clinical guidance
- Full audit trail: every output references CPIC guideline version, rsID, diplotype, and confidence tier
- Regulatory classification documentation (this document, FDA_CDS_COMPLIANCE.md, LDT_DIFFERENTIATION.md)

### Limitations (Explicitly Declared)

- Gene panel: 15 Tier-1 genes. Comprehensive pharmacogenome (PharmCAT-level 50+ genes) requires CPIC guideline expansion.
- CYP2D6 CNV: Heuristic v1 resolution (DEL/DUP + copy number). Not equivalent to Cyrius or Stargazer.
- Validation: CPIC-aligned fixture testing and Coriell cell line concordance. Not prospective clinical validation.
- No patient data is processed or stored. All genomic data is sourced from publicly released, de-identified 1000 Genomes Project VCFs.

### Data Ethics and IRB Note

All genomic data used by SynthaTrial is sourced exclusively from:
- **1000 Genomes Project Phase 3**: Publicly released, de-identified data from an IRB-approved international consortium. Available via AWS Open Data Program (s3://1000genomes) with no egress charges.
- **Coriell Cell Line Repository**: NIST/Genome in a Bottle (GIAB) reference samples (NA12878, etc.) used solely for technical concordance testing.

SynthaTrial does **not** collect, store, or transmit patient identifiable information. VCF files processed via the API are held in memory during the request lifecycle only and are not persisted.

---

## Stage 1: Clinical Utility MVP (Target: Q3–Q4 2026)

**Trigger:** Institutional partner engagement (CLIA laboratory, academic medical center, or CRO)

### Objectives

1. **Prospective concordance study**: Compare SynthaTrial diplotype calls against a CLIA-certified PGx laboratory (e.g., Genomind, OneOme, or equivalent) for ≥500 de-identified samples across all 15 Tier-1 genes. Target: ≥99% concordance for CPIC Level A genes.

2. **GIAB reference sample validation**: Full validation against NA12878 (HG001), NA24385, and NA24631 Genome in a Bottle samples using known truth genotypes.

3. **IRB-approved protocol**: Partner with an academic medical center to conduct the prospective study under an IRB-approved protocol. De-identified residual samples from routine clinical PGx testing are sufficient.

4. **Preprint publication**: Submit concordance results to a peer-reviewed preprint server (bioRxiv, medRxiv) to establish public, citable evidence for accuracy.

5. **FHIR integration pilot**: Deploy the `/analyze/fhir-report` endpoint in a sandbox EHR environment (Epic SMART on FHIR or Cerner FHIR API) to validate interoperability.

### Key Metrics for Stage 1 Completion

| Metric | Target |
|--------|--------|
| Concordance with CLIA lab (CPIC Level A genes) | ≥99% |
| Concordance with CLIA lab (CPIC Level B genes) | ≥95% |
| NA12878 genotype accuracy | ≥99.5% |
| Sample size | ≥500 de-identified samples |
| IRB approval | Obtained |
| Preprint submitted | Yes |

---

## Stage 2: Clinical Decision Support (Target: 2027)

**Trigger:** Stage 1 completion + commercial/institutional partner commitment

### Objectives

1. **Peer-reviewed publication**: Full clinical utility study published in a peer-reviewed journal (e.g., *Clinical Pharmacology & Therapeutics*, *Pharmacogenomics*, or *JAMIA*).

2. **Real-world evidence study**: Retrospective or prospective study demonstrating clinical outcomes benefit (e.g., reduced adverse drug events in CYP2B6 PM patients on efavirenz, or NAT2 slow acetylator patients on isoniazid).

3. **FDA Software Pre-Submission**: If desired by a clinical partner, initiate an FDA Pre-Submission (Q-Submission) for the CDS tool under the FDA's voluntary 2023 AI/ML-Based SaMD Action Plan framework.

4. **CLIA LDT differentiation**: If deployed with a wet-lab partner, clearly partition the interpretation software (this tool) from the CLIA-regulated laboratory test. See [LDT_DIFFERENTIATION.md](LDT_DIFFERENTIATION.md).

5. **Equity outcome metrics**: Publish population-stratified accuracy and clinical outcome data demonstrating that equity-focused diverse cohort simulation improves dosing predictions for underrepresented populations.

### Regulatory Pathway Options at Stage 2

| Pathway | When Applicable | Notes |
|---------|----------------|-------|
| Non-device CDS (current) | If all four §520(o)(1)(E) factors remain satisfied | Most likely pathway; no FDA submission required |
| Software Pre-Submission | If clinical partners want FDA engagement before deployment | Voluntary; establishes relationship with FDA |
| De Novo / 510(k) | Only if tool is intended to replace clinical judgment | Not current intent; would require significant re-scoping |

---

## Partner Integration Points

### For CLIA Laboratories

SynthaTrial can serve as the interpretation software layer on top of a CLIA-certified genotyping platform. The CLIA regulation covers the wet-lab assay; interpretation software is not within CLIA scope when it displays the basis for its recommendations and does not replace clinical judgment.

Contact path: Provide your CLIA lab's VCF output format; SynthaTrial accepts standard VCF 4.1+ files via the `/vcf-profile` or `/analyze` API endpoints.

### For Pharmaceutical / CRO Partners

SynthaTrial provides trial stratification via the `/trial/export` endpoint (clopidogrel + CYP2C19, warfarin + CYP2C9/VKORC1, efavirenz + CYP2B6 workflows). FHIR output is available via `/analyze/fhir-report` for EHR integration pilots.

See [PHARMA_INTEGRATION_GUIDE.md](../PHARMA_INTEGRATION_GUIDE.md) for technical integration details.

### For Academic Medical Centers

We are actively seeking IRB-approved retrospective study partners. Requirements: HIPAA-compliant data transfer agreement, de-identified residual VCF data from routine PGx panels, 500+ samples across diverse ancestries.

---

## Contact

For partnership inquiries, regulatory questions, or IRB protocol discussions, reference this document and reach out via the SynthaTrial repository.

---

*This roadmap is a living document and will be updated as partnerships are established and validation milestones are achieved.*
