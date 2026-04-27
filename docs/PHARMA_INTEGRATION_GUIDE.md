# SynthaTrial Pharma Integration Guide

**Version:** 1.0 | **Audience:** CROs, Pharma Sponsors, Clinical Pharmacologists
**API Base:** `https://your-deployment.amazonaws.com` (or local `http://localhost:8000`)

---

## Overview

SynthaTrial is a pharmacogenomics simulation and trial stratification API. It enables
pharmaceutical sponsors and CROs to:

1. **Stratify trial cohorts** by PGx genotype using 1000 Genomes population data
2. **Simulate diverse patient populations** with equity-aware ancestry representation
3. **Identify DDGI risks** in polypharmacy trial populations
4. **Generate FHIR-compatible genomic reports** for EHR integration pilots
5. **Estimate drug exposure variability** from gene panel simulation

---

## Quick Start (5 minutes)

### 1. Health Check

```bash
curl https://your-deployment.com/health-fast
# Returns: {"status": "ok", "version": "0.5.0"}
```

### 2. Analyze a Drug-Patient Profile

```bash
curl -X POST https://your-deployment.com/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "drug_name": "efavirenz",
    "patient_id": "DEMO_001",
    "genetics": "CYP2B6 *6/*6 Poor Metabolizer",
    "ancestry": "AFR"
  }'
```

### 3. Trial Stratification (Clopidogrel + CYP2C19)

```bash
curl -X POST https://your-deployment.com/trial/export \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": "clopidogrel_cyp2c19",
    "sample_ids": ["HG00096", "HG00097", "NA19625", "HG01112"],
    "source": "open_data"
  }'
```

---

## API Reference

### Core PGx Analysis

#### `POST /analyze`

Single drug-patient pharmacogenomics analysis.

**Request:**
```json
{
  "drug_name": "warfarin",
  "patient_id": "PT001",
  "genetics": "CYP2C9 *2/*3, VKORC1 AA",
  "age": 65,
  "conditions": ["Atrial Fibrillation"],
  "ancestry": "EUR"
}
```

**Response:**
```json
{
  "risk": "High",
  "recommendation": "Reduce warfarin starting dose. Standard dose likely causes over-anticoagulation...",
  "pgx_structured": {
    "gene": "CYP2C9",
    "diplotype": "*2/*3",
    "phenotype": "Poor Metabolizer",
    "cpic_level": "A"
  },
  "llm_explanation": "...",
  "backend_used": "nova"
}
```

#### `POST /analyze/batch`

Analyze multiple drug-patient pairs in a single request. Ideal for cohort simulation.

```bash
curl -X POST https://your-deployment.com/analyze/batch \
  -H "Content-Type: application/json" \
  -d '{
    "requests": [
      {"drug_name": "efavirenz", "patient_id": "AFR_001", "genetics": "CYP2B6 *6/*6"},
      {"drug_name": "efavirenz", "patient_id": "EUR_001", "genetics": "CYP2B6 *1/*1"},
      {"drug_name": "efavirenz", "patient_id": "AFR_002", "genetics": "CYP2B6 *6/*18"}
    ]
  }'
```

---

### Drug-Drug-Gene Interaction Detection

#### `POST /analyze/ddgi`

Detects pharmacogenomic amplification of drug-drug interactions.

**Request:**
```json
{
  "gene_phenotypes": {
    "CYP2D6": "Poor Metabolizer",
    "CYP2C19": "Normal Metabolizer"
  },
  "drugs": ["codeine", "fluoxetine"],
  "min_risk_level": "MODERATE"
}
```

**Response (abbreviated):**
```json
{
  "summary": {
    "overall_alert_level": "HIGH",
    "total_interactions": 1,
    "priority_action": "Avoid codeine in CYP2D6 Poor Metabolizers..."
  },
  "interactions": [{
    "gene": "CYP2D6",
    "risk_level": "HIGH",
    "mechanism": "Codeine requires CYP2D6 for conversion to morphine...",
    "recommendation": "Use morphine or hydromorphone instead.",
    "equity_note": "CYP2D6 PM rate: North African ~30% — major equity concern."
  }]
}
```

**Implemented DDGI scenarios:**
- CYP2D6 PM + codeine + fluoxetine → opioid toxicity (HIGH)
- CYP2C19 PM + clopidogrel + omeprazole → stent thrombosis (HIGH)
- CYP2B6 PM + efavirenz + rifampin → HIV/TB ARV exposure (MODERATE)
- NAT2 SA + isoniazid + rifampin → hepatotoxicity (HIGH)
- TPMT PM + azathioprine + allopurinol → myelosuppression (CRITICAL)
- CYP3A5 Poor + tacrolimus + azole → transplant toxicity (HIGH)
- SLCO1B1 Poor + statin + gemfibrozil → rhabdomyolysis (HIGH)

---

### Trial Stratification

#### `GET /trial/workflows`

List available trial stratification workflows.

#### `POST /trial/export`

Export cohort stratification data for a PGx-guided trial.

**Available workflows:**
- `clopidogrel_cyp2c19` — Antiplatelet therapy; CYP2C19 LOF genotyping
- `warfarin_cyp2c9_vkorc1` — Anticoagulation; CYP2C9 + VKORC1 diplotyping

**Request:**
```json
{
  "workflow": "clopidogrel_cyp2c19",
  "sample_ids": ["HG00096", "NA19625", "HG01112", "NA18498"],
  "source": "open_data",
  "dataset_id": null
}
```

**Response row example:**
```json
{
  "sample_id": "NA18498",
  "workflow": "clopidogrel_cyp2c19",
  "drug_name": "clopidogrel",
  "gene": "CYP2C19",
  "diplotype_or_genotype": "*2/*2",
  "phenotype": "Poor Metabolizer",
  "recommendation_category": "Alternative therapy",
  "recommendation_text": "Use prasugrel or ticagrelor instead of clopidogrel",
  "call_state": "called"
}
```

---

### Equity-Focused Efavirenz + CYP2B6 Trial Stratification

This workflow demonstrates the equity use case for HIV antiretroviral research.

**Clinical context:** CYP2B6 *6 and *18 alleles are substantially more common in
African-ancestry populations (~50% *6 carriers, ~10% *18 carriers). Standard efavirenz
600mg/day causes CNS toxicity (nightmares, dizziness, depression) and treatment
discontinuation in CYP2B6 Poor Metabolizers. This workflow stratifies a multi-ancestry
cohort to identify patients needing dose adjustment.

```bash
# Step 1: Get streaming population data
curl https://your-deployment.com/vcf-datasets/streaming-status

# Step 2: Analyze efavirenz PGx across population
curl -X POST https://your-deployment.com/population-simulate \
  -H "Content-Type: application/json" \
  -d '{
    "drug_name": "efavirenz",
    "population_size": 100,
    "ancestries": ["AFR", "EUR", "EAS", "SAS"],
    "target_gene": "CYP2B6"
  }'

# Step 3: For individual patients, use the analyze endpoint
curl -X POST https://your-deployment.com/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "drug_name": "efavirenz",
    "patient_id": "AFR_HIV_001",
    "genetics": "CYP2B6 *6/*6 Poor Metabolizer",
    "ancestry": "AFR",
    "conditions": ["HIV"]
  }'
```

**Expected stratification output:**
| Ancestry | PM rate (CYP2B6) | Recommendation |
|----------|-----------------|----------------|
| AFR | ~25% *6/*6 | Dose reduction to 400mg; TDM monitoring |
| EUR | ~5% *6/*6 | Standard 600mg dose appropriate |
| EAS | ~3% *6/*6 | Standard 600mg dose appropriate |
| SAS | ~8% *6/*6 | Monitor; TDM if CNS symptoms |

---

### FHIR Genomics Report

#### `POST /analyze/fhir-report`

Generate an HL7 FHIR R4 Genomics Reporting bundle for EHR integration.

**Request:**
```json
{
  "patient_id": "de-identified-PT001",
  "drug_name": "warfarin",
  "ancestry": "EUR",
  "gene_results": [
    {
      "gene": "CYP2C9",
      "diplotype": "*2/*3",
      "phenotype": "Poor Metabolizer",
      "recommendation": "Reduce starting dose by 25-50%; monitor INR closely",
      "cpic_level": "A"
    },
    {
      "gene": "VKORC1",
      "diplotype": "AA",
      "phenotype": "Sensitive (Low dose)",
      "recommendation": "Patient is VKORC1 sensitive; use lower starting dose",
      "cpic_level": "A"
    }
  ]
}
```

**Response:** Full FHIR R4 Bundle (JSON) with `DiagnosticReport` + `Observation` resources,
conformant with HL7 FHIR Genomics Reporting IG.

**Compatible with:**
- Epic SMART on FHIR
- Cerner FHIR API (R4)
- Any HL7 R4-compliant EHR system

---

### Regulatory Classification

#### `GET /regulatory/classification`

Returns machine-readable CDS classification metadata. Useful for integration
partners who need to document the regulatory status of this tool in their workflows.

```bash
curl https://your-deployment.com/regulatory/classification
```

Returns: FDA CDS classification, validation stage, data ethics statement, gene panel.

---

## 1000 Genomes Data Access

SynthaTrial streams population data directly from the 1000 Genomes Project via AWS
Open Data Program — **no local download required**.

- **URL scheme:** `https://1000genomes.s3.amazonaws.com/...`
- **Method:** HTTPS tabix range requests (fetches only the genomic regions of interest)
- **Cost:** $0 — AWS Open Data Program, no egress charges
- **Coverage:** 2,504 individuals; 5 superpopulations (AFR, AMR, EAS, EUR, SAS)

Check streaming status:
```bash
curl https://your-deployment.com/vcf-datasets/streaming-status
```

---

## Polygenic Risk Score Analysis

Beyond pharmacogenomics, SynthaTrial provides simplified PRS for equity demonstration:

#### `POST /analyze/polygenic-risk`

```json
{
  "patient_variants": {
    "rs7903146": "T",
    "rs8050136": "0/1"
  },
  "ancestry": "AFR"
}
```

Returns CAD and T2D polygenic risk scores with equity analysis showing how EUR-trained
weights systematically misclassify risk in non-European populations.

---

## Integration Architecture

```
                    ┌─────────────────────────────────┐
                    │         Your System              │
                    │  (EHR / Trial Management / CRO) │
                    └──────────────┬──────────────────┘
                                   │ REST API / FHIR R4
                                   ▼
                    ┌─────────────────────────────────┐
                    │       SynthaTrial API            │
                    │    FastAPI + AWS Bedrock          │
                    │  /analyze  /trial  /analyze/fhir │
                    └──────────────┬──────────────────┘
                     ┌─────────────┼──────────────────┐
                     ▼             ▼                  ▼
              ┌──────────┐  ┌──────────────┐  ┌──────────────┐
              │ CPIC/    │  │ 1000 Genomes │  │ AWS Bedrock  │
              │ PharmVar │  │  AWS S3      │  │ Nova/Claude  │
              │ (local)  │  │  (streaming) │  │  (optional)  │
              └──────────┘  └──────────────┘  └──────────────┘
```

---

## Cost Model

| Feature | Cost |
|---------|------|
| 1000 Genomes data access | $0 (AWS Open Data Program) |
| API compute | AWS Lambda/EC2 (Free Tier eligible for pilots) |
| LLM explanation (Nova) | ~$0.0001/request (Amazon Nova Lite) |
| FHIR report generation | Included, no additional cost |
| DDGI analysis | Included, deterministic, no LLM cost |
| PRS analysis | Included, deterministic, no LLM cost |

**Estimated cost:** $0.0001 per patient analysis (LLM explanation layer only). Deterministic
PGx calling, FHIR generation, and DDGI detection are computationally negligible.

---

## Contact and Partnership

For integration pilots, IRB protocol discussions, or regulatory review:

1. Reference the [Clinical Validation Roadmap](regulatory/CLINICAL_VALIDATION_ROADMAP.md)
2. Review [FDA CDS Compliance](regulatory/FDA_CDS_COMPLIANCE.md)
3. Check the repository for latest API documentation

**Partnership opportunities:**
- **CLIA Laboratory Partners:** VCF input/output integration; concordance study collaboration
- **CRO Partners:** Trial stratification workflow customization; batch cohort analysis
- **Academic Partners:** IRB-approved retrospective validation study; publication collaboration
- **EHR Vendors:** FHIR integration pilot; SMART on FHIR app development
