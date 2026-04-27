# Chapter 3: Pharmacogenomics Engine

The deterministic PGx engine is the core of Anukriti. It takes genetic variants as input
and produces reproducible, auditable pharmacogenomics predictions without any LLM involvement.

## 3.1 Data Foundation

### PharmVar Allele Definitions (`data/pgx/pharmvar/`)

Each gene has a TSV file defining its star alleles:

```
# Example: cyp2c19_alleles.tsv
allele    rsid         position    ref    alt    function
*2        rs4244285    94781859    G      A      No function
*3        rs4986893    94780653    G      A      No function
*17       rs12248560   94761900    C      T      Increased function
```

**Coverage by gene:**

| File | Gene | Alleles | Key Variants |
|------|------|---------|--------------|
| `cyp2c19_alleles.tsv` | CYP2C19 | *1, *2, *3, *17 | rs4244285, rs4986893, rs12248560 |
| `cyp2c9_alleles.tsv` | CYP2C9 | *1, *2, *3 | rs1799853, rs1057910 |
| `cyp2d6_alleles.tsv` | CYP2D6 | *1, *4, *5, *10, *41 | rs3892097, rs1065852, rs28371725 |
| `tpmt_alleles.tsv` | TPMT | *1, *2, *3A, *3B, *3C, *4 | rs1800462, rs1800460, rs1142345 |
| `dpyd_alleles.tsv` | DPYD | *1, *2A, *3, *9A | rs3918290, rs55886062, rs67376798 |
| `ugt1a1_alleles.tsv` | UGT1A1 | *1, *6, *28, *36, *37 | rs8175347, rs4148323 |
| `slco1b1_variants.tsv` | SLCO1B1 | T/C genotype | rs4149056 |
| `vkorc1_variants.tsv` | VKORC1 | G/A genotype | rs9923231, rs7294, rs8050894 |

### CPIC Phenotype Tables (`data/pgx/cpic/`)

Each gene has a JSON file mapping diplotypes to phenotypes:

```json
// Example: cyp2c19_phenotypes.json
{
  "*1/*1": {"phenotype": "Normal Metabolizer", "activity_score": 2.0},
  "*1/*2": {"phenotype": "Intermediate Metabolizer", "activity_score": 1.0},
  "*2/*2": {"phenotype": "Poor Metabolizer", "activity_score": 0.0},
  "*1/*17": {"phenotype": "Rapid Metabolizer", "activity_score": 2.5},
  "*17/*17": {"phenotype": "Ultra-rapid Metabolizer", "activity_score": 3.0}
}
```

**Special patterns:**
- **CYP2D6**: Uses activity score system (*1=1.0, *4=0.0, *10=0.5, *41=0.5)
- **SLCO1B1**: Genotype-based lookup (TT/TC/CC), not star allele diplotypes
- **VKORC1**: Genotype-based lookup (GG/GA/AA), same pattern as SLCO1B1
- **UGT1A1**: Covers TA repeat polymorphisms (*28=TA7, *37=TA8, *36=TA5)

### Drug-Specific Guidelines

Four drug-specific CPIC guideline JSONs:

| File | Drug(s) | Genes | Recommendation Type |
|------|---------|-------|---------------------|
| `warfarin_response.json` | Warfarin | CYP2C9 + VKORC1 | Dose adjustment (mg/day) |
| `statin_guidelines.json` | Simvastatin, atorvastatin | SLCO1B1 | Drug/dose selection |
| `thiopurine_guidelines.json` | Azathioprine, mercaptopurine | TPMT | Dose fraction |
| `fluoropyrimidine_guidelines.json` | 5-FU, capecitabine | DPYD | Dose reduction/avoidance |

### Data Provenance (`data/pgx/sources.md`)

All data files are versioned with source attribution:
- PharmVar version and download date
- CPIC guideline publication references
- Ensembl/dbSNP coordinate versions
- GRCh37 and GRCh38 positions

## 3.2 Core Allele Caller (`src/allele_caller.py`)

This is the most critical module — it translates VCF variants into star allele diplotypes.

### Key Functions

#### `load_pharmvar_alleles(gene)`
Loads the TSV file for a given gene and returns a dict mapping rsid → allele info.

#### `call_star_alleles(variants, gene)`
The main calling function:

1. Load PharmVar allele definitions for the gene
2. For each variant in the patient's VCF:
   - Look up the rsid in PharmVar
   - Check if the ALT allele matches a known star allele defining variant
   - Track which alleles are "hit" (have their defining variant present)
3. Build the star allele assignment:
   - If a defining variant is heterozygous (0/1): one copy of the variant allele + one *1
   - If homozygous (1/1): two copies of the variant allele
   - If no variants match: *1/*1 (reference/wild-type)

#### `build_diplotype(alleles, gene)`
Normalizes allele pairs into a canonical diplotype string:

```python
# Sorting rule: numeric order, not alphabetical
# *1/*17  (correct — *1 < *17)
# *2/*3   (correct — *2 < *3)
# *10/*4  (correct — *4 < *10, numerically)
```

#### `diplotype_to_phenotype(diplotype, gene)`
Loads the CPIC JSON and performs exact-match lookup:

```python
phenotype_data = load_cpic_translation_for_gene(gene)
result = phenotype_data.get(diplotype)
# Returns: {"phenotype": "Poor Metabolizer", "activity_score": 0.0}
```

#### `alt_dosage(genotype_str)`
Converts VCF genotype field to ALT allele count:
- `"0/0"` → 0 (homozygous reference)
- `"0/1"` or `"1/0"` → 1 (heterozygous)
- `"1/1"` → 2 (homozygous alternate)

### Calling Logic Illustrated

```
Input VCF variant:  chr10:94781859  G→A  GT=0/1  (rs4244285)

1. Load cyp2c19_alleles.tsv
2. rs4244285 maps to CYP2C19*2 (No function)
3. Genotype 0/1 = heterozygous → one *2 allele
4. No other CYP2C19 variants found → other allele is *1
5. Build diplotype: *1/*2
6. Lookup in cyp2c19_phenotypes.json:
   "*1/*2" → "Intermediate Metabolizer"
```

## 3.3 Gene-Specific Callers

### Warfarin Caller (`src/warfarin_caller.py`)

Warfarin requires two genes: CYP2C9 (metabolism) + VKORC1 (target sensitivity).

```python
# Flow:
variants = {"rs1799853": ("C", "T", "0/1"), "rs9923231": ("G", "A", "0/1")}

cyp2c9_result = call_cyp2c9(variants)
# → {"diplotype": "*1/*2", "phenotype": "Intermediate Metabolizer"}

vkorc1_result = call_vkorc1(variants)
# → {"genotype": "GA", "sensitivity": "Intermediate Sensitivity"}

recommendation = interpret_warfarin(cyp2c9_result, vkorc1_result)
# → {"dose_adjustment": "Reduce 20-40%", "initial_dose": "3-4 mg/day"}
```

The warfarin response table (`warfarin_response.json`) is a matrix:

```
              VKORC1 GG    VKORC1 GA    VKORC1 AA
CYP2C9 *1/*1  5-7 mg/day   3-4 mg/day   1.5-2 mg/day
CYP2C9 *1/*2  3-4 mg/day   3-4 mg/day   1.5-2 mg/day
CYP2C9 *1/*3  3-4 mg/day   1.5-2 mg/day 0.5-2 mg/day
CYP2C9 *2/*2  3-4 mg/day   1.5-2 mg/day 0.5-2 mg/day
...
```

### SLCO1B1 Caller (`src/slco1b1_caller.py`)

SLCO1B1 uses a single-variant genotype approach (rs4149056):

```
TT → Normal function → Standard statin therapy
TC → Decreased function → Use lower-intensity statin, monitor
CC → Poor function → Avoid simvastatin, consider alternatives
```

### TPMT Caller (`src/tpmt_caller.py`)

TPMT uses multi-variant haplotype calling:

```
rs1800462 (G>C) → *2
rs1800460 (A>G) → *3A (requires rs1142345 too)
rs1142345 (A>G) → *3C (alone) or *3A (with rs1800460)
rs1800584 (G>T) → *4
```

Drug-specific recommendations:
- Azathioprine: dose adjustment by phenotype
- Mercaptopurine: dose adjustment by phenotype

### DPYD Caller (`src/dpyd_caller.py`)

DPYD is critical for fluoropyrimidine safety:

```
rs3918290 (IVS14+1G>A) → *2A (No function)
rs55886062 (1679T>G)   → *13 (Decreased function)
rs67376798 (2846A>T)   → c.2846A>T (Decreased function)
rs56038477 (1129-5923C>G) → HapB3 (Decreased function)
```

CPIC phenotype corrections (important):
- `*1/*2A` → **Intermediate Metabolizer** (NOT Poor — corrected per CPIC)
- `*2A/*2A` → **Poor Metabolizer**
- `*1/*13` → **Intermediate Metabolizer**

## 3.4 Variant Database (`src/variant_db.py`)

Provides lookup functions independent of the allele caller:

```python
ALLELE_FUNCTION_MAP = {
    "CYP2D6*4": "No function",
    "CYP2D6*10": "Decreased function",
    "CYP2C19*2": "No function",
    "CYP2C19*17": "Increased function",
    ...
}

SUPPORTED_PROFILE_GENES = [
    "CYP2D6", "CYP2C19", "CYP2C9", "UGT1A1",
    "SLCO1B1", "VKORC1", "TPMT", "DPYD"
]
```

## 3.5 Drug-Gene Triggers (`src/pgx_triggers.py`)

Maps drug names to relevant pharmacogenes:

```python
DRUG_GENE_TRIGGERS = {
    "warfarin": ["CYP2C9", "VKORC1"],
    "clopidogrel": ["CYP2C19"],
    "simvastatin": ["SLCO1B1"],
    "atorvastatin": ["SLCO1B1"],
    "azathioprine": ["TPMT"],
    "mercaptopurine": ["TPMT"],
    "5-fluorouracil": ["DPYD"],
    "capecitabine": ["DPYD"],
    "codeine": ["CYP2D6"],
    "irinotecan": ["UGT1A1"],
    ...
}
```

When a user inputs a drug, the system automatically highlights the relevant gene results.

## 3.6 Structured Output (`src/pgx_structured.py`)

Normalizes all PGx outputs into a consistent schema:

```python
{
    "gene": "CYP2C19",
    "variant": "rs4244285",
    "genotype": "G/A",
    "diplotype": "*1/*2",
    "phenotype": "Intermediate Metabolizer",
    "risk_level": "moderate",
    "recommendation": "Consider alternative to clopidogrel",
    "explanation": "...",  # From LLM
    "confidence": 0.95     # CPIC evidence strength
}
```

Confidence scoring reflects CPIC evidence:
- Level A gene/drug pairs: 0.90-0.95
- Well-studied populations (EUR): higher confidence
- Under-studied populations (AMR): lower confidence

---

**Next**: [Chapter 4 — LLM & RAG Integration](04-llm-and-rag-integration.md)
