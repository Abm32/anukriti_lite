# Chapter 8: Frontend, Backend & API

Anukriti provides three interfaces: a Streamlit web UI, a FastAPI REST API, and a CLI
for batch processing.

## 8.1 Streamlit Frontend (`app.py`)

### Overview

The web UI is the primary user interface, providing interactive pharmacogenomics analysis
for clinicians, researchers, and reviewers.

**Launch**:
```bash
streamlit run app.py --server.port=8501
```

### UI Components

#### 1. Patient Input Section

Two input modes:

**Manual genotype entry**:
- Gene selector dropdown (all 8 genes)
- Allele selector for each gene (star alleles or genotypes)
- VKORC1 manual selector (GG/GA/AA) — added for completeness
- Population/ancestry selector (AFR, EUR, EAS, SAS, AMR)

**VCF file upload**:
- Drag-and-drop VCF upload
- Automatic sample extraction
- Sample selector for multi-sample VCFs
- Reference genome auto-detection (GRCh37/38)

#### 2. Drug Input Section

- Drug name text input
- SMILES string input with validation
- 3D molecular visualization (py3Dmol + stmol)
- Drug structure display (RDKit 2D depiction)

#### 3. Analysis Results

- Per-gene PGx cards:
  - Diplotype and phenotype
  - Risk level indicator (color-coded)
  - CPIC recommendation
  - LLM-generated explanation
  - Confidence score with evidence level
- Drug trigger highlighting (relevant genes for selected drug)
- Warfarin dose recommendation panel (if warfarin selected)

#### 4. Population Simulation

- Cohort size slider (100 - 10,000)
- Ancestry distribution inputs
- Real-time progress bar
- Results visualizations:
  - Phenotype distribution charts (per gene)
  - Ancestry breakdown
  - Adverse event predictions
  - Performance metrics

#### 5. PDF Report Generation

- One-click PDF generation
- Includes all PGx results, recommendations, and LLM explanations
- Download button for the generated PDF

#### 6. Sidebar

- Health check panel (API status indicators)
- Session-based analytics counters (patients analyzed, reports generated)
- Real-time metrics (replaces previous hardcoded demo values)
- Validation dashboard with test status

### Session State Management

The app uses Streamlit session state for:
- Patient profile persistence across rerenders
- Analysis result caching
- Analytics counters (session-based, not hardcoded)
- VCF file state

## 8.2 FastAPI Backend (`api.py`)

### Overview

The REST API provides programmatic access to all PGx functionality.

**Launch**:
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

### Endpoints

#### `POST /analyze`

Full drug-patient analysis:

```json
// Request
{
    "drug_name": "clopidogrel",
    "drug_smiles": "OC(=O)[C@H]1N2CCc3sccc3[C@@H]2CC1Cl",
    "patient_profile": {
        "genotypes": {
            "CYP2C19": "*1/*2",
            "CYP2D6": "*1/*1"
        },
        "ancestry": "EUR"
    }
}

// Response
{
    "status": "success",
    "results": {
        "CYP2C19": {
            "diplotype": "*1/*2",
            "phenotype": "Intermediate Metabolizer",
            "risk_level": "moderate",
            "recommendation": "Consider alternative antiplatelet",
            "confidence": 0.95
        }
    },
    "explanation": "...",  // LLM-generated
    "similar_drugs": [...]
}
```

#### `POST /analyze/novel-drug`

Novel drug analysis with confidence tiers:

```json
// Request
{
    "drug_name": "ExampleDrug",
    "drug_smiles": "...",
    "targets": ["CYP2C19"],
    "metabolism_enzymes": ["CYP2C19"],
    "evidence_notes": "Phase 2 trial data"
}

// Response includes confidence_tier: "high" | "moderate" | "exploratory"
// and decision_grade for trial-facing use
```

#### `GET /novel-drug/validation-artifact`

Returns the benchmark artifact summary for novel drug analysis.

#### `GET /trial/workflows`

Returns supported deterministic MVP workflows:

```json
{
    "workflows": [
        {"id": "clopidogrel", "genes": ["CYP2C19"], "call_states": ["called", "cannot_call", "insufficient_data"]},
        {"id": "warfarin", "genes": ["CYP2C9", "VKORC1"], "call_states": ["called", "cannot_call", "insufficient_data"]}
    ]
}
```

#### `POST /trial/export`

Cohort export with explicit call confidence states:

```json
// Request: array of patient genotypes + drug
// Response: rows with call_state: "called" | "cannot_call" | "insufficient_data"
```

#### `POST /simulate`

Population simulation:

```json
// Request
{"drug": "warfarin", "cohort_size": 1000, "ancestry_distribution": {"EUR": 0.5, "AFR": 0.25, "EAS": 0.25}}

// Response: phenotype distributions, adverse event predictions, performance metrics
```

#### `POST /vcf/sample-ids`

Extract sample IDs from uploaded VCF:

```json
// Request: multipart/form-data with VCF file

// Response
{
    "samples": ["HG00096", "HG00097", "HG00099"],
    "reference_genome": "GRCh37",
    "variant_count": 1247
}
```

#### `POST /vcf/patient-profile`

Generate full patient profile from VCF:

```json
// Request
{
    "vcf_path": "/path/to/file.vcf.gz",
    "sample_id": "HG00096",
    "reference_genome": "GRCh37"
}

// Response
{
    "sample_id": "HG00096",
    "genes": {
        "CYP2C19": {"diplotype": "*1/*2", "phenotype": "Intermediate Metabolizer"},
        "CYP2C9": {"diplotype": "*1/*1", "phenotype": "Normal Metabolizer"},
        ...
    }
}
```

#### `GET /health` / `GET /` / `GET /health-fast`

Three-tier health check system (non-blocking):

```json
// GET /health-fast — ultra-fast (< 2 seconds), no AWS checks
{"status": "healthy", "version": "0.4"}

// GET / — fast (< 5 seconds), basic connectivity
{"status": "healthy", "components": {"pgx_engine": "ok"}}

// GET /health — detailed (< 15 seconds), includes AWS service status
{
    "status": "healthy",
    "components": {
        "pgx_engine": "ok",
        "llm": "ok",
        "vector_db": "opensearch",
        "chembl": "ok",
        "s3_genomic": "connected",
        "lambda": "configured",
        "step_functions": "configured"
    },
    "version": "0.4"
}
```

The Streamlit UI uses `/health-fast` for quick connectivity testing. AWS service checks in `/health` are non-blocking with 10-second timeouts per service.

#### `POST /rag/retrieve`

RAG retrieval query:

```json
// Request
{
    "query": "CYP2C19 poor metabolizer clopidogrel",
    "top_k": 3
}

// Response
{
    "documents": [
        {"content": "CPIC guideline for clopidogrel...", "score": 0.92},
        ...
    ]
}
```

#### `GET /aws-status`

Real-time AWS service connectivity (non-blocking — only verifies client configuration):

```json
{
    "s3_genomic": {"status": "connected", "bucket": "synthatrial-genomic-data", "vcf_files": 16},
    "s3_reports": {"status": "connected", "bucket": "synthatrial-reports"},
    "lambda": {"status": "configured", "function": "synthatrial-batch-processor"},
    "step_functions": {"status": "configured"}
}
```

#### `GET /data-status`

Shows whether VCF data is sourced from S3 or local disk:

```json
{
    "vector_db": "opensearch",
    "vcf_chromosomes": ["chr22", "chr10", "chr16"],
    "vcf_source": "s3",
    "chembl_db_present": true
}
```

## 8.3 CLI / Batch Processing (`main.py`)

### Usage

```bash
# Single patient analysis
python main.py --drug warfarin --genotype '{"CYP2C9": "*1/*3", "VKORC1": "GA"}'

# Batch from JSON
python main.py --input patients.json --drug clopidogrel --output results.json

# VCF-based analysis
python main.py --vcf data/genomes/ALL.chr10.phase3.vcf.gz \
               --sample HG00096 \
               --drug clopidogrel

# Manual variant input
python main.py --variants '{"rs4244285": "G/A", "rs1799853": "C/T"}' \
               --drug warfarin
```

### Batch Input Format

```json
[
    {
        "patient_id": "P001",
        "genotypes": {"CYP2C19": "*1/*2", "CYP2C9": "*1/*1"},
        "drug": "clopidogrel",
        "ancestry": "EUR"
    },
    {
        "patient_id": "P002",
        "genotypes": {"CYP2C9": "*1/*3", "VKORC1": "GA"},
        "drug": "warfarin",
        "ancestry": "SAS"
    }
]
```

### LLM Backend Selection

```bash
# Use Gemini (default)
python main.py --llm gemini --drug warfarin ...

# Use Bedrock Claude
python main.py --llm bedrock --drug warfarin ...
```

## 8.4 PDF Report Generation (`src/report_pdf.py`)

Generates clinical-grade PDF reports using ReportLab:

```python
def generate_pdf_bytes(patient_data, pgx_results, explanation):
    """
    PDF includes:
    - Patient header (ID, ancestry, date)
    - Gene-by-gene PGx results table
    - Risk level indicators
    - CPIC recommendations
    - LLM-generated explanation
    - Confidence scores
    - Disclaimer / limitations
    """
```

Reports can be:
- Downloaded directly from the Streamlit UI
- Generated via the API
- Stored in S3 via `src/aws/s3_report_manager.py`

## 8.5 Example Files

Pre-built example inputs for quick testing:

| File | Drug | Genes | Purpose |
|------|------|-------|---------|
| `warfarin_examples.json` | Warfarin | CYP2C9, VKORC1 | Warfarin dosing scenarios |
| `statin_examples.json` | Simvastatin | SLCO1B1 | Statin myopathy risk |
| `slco1b1_examples.json` | Statins | SLCO1B1 | Extended SLCO1B1 scenarios |
| `cpic_examples.json` | Various | Multiple | General CPIC test cases |

## 8.6 3D Molecular Visualization

The Streamlit app renders drug structures using:

```python
# 2D structure (RDKit)
from rdkit import Chem
from rdkit.Chem import Draw
mol = Chem.MolFromSmiles(smiles)
img = Draw.MolToImage(mol)

# 3D structure (py3Dmol + stmol)
import py3Dmol
import stmol
viewer = py3Dmol.view()
viewer.addModel(mol_block, "sdf")
viewer.setStyle({"stick": {}})
stmol.showmol(viewer)
```

---

**Next**: [Chapter 9 — Cloud Infrastructure & DevOps](09-cloud-infrastructure-and-devops.md)
