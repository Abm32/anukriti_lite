# Data Source Flow: Where Does the Gene Data Come From?

**Question:** "From where does this get?"

**Answer:** The gene panel data comes from three sources and flows through an automated pipeline.

---

## Data Sources

### 1. Gene Metadata (Hardcoded in `init_gene_database.py`)
**Source:** Manually curated from NCBI Gene database

```python
# scripts/init_gene_database.py
TIER_1_GENES = [
    # Format: (gene_symbol, chromosome, start_pos, end_pos, tier, build)
    ("CYP2D6", "22", 42522500, 42530900, 1, "GRCh37"),
    ("CYP2C19", "10", 96535040, 96625463, 1, "GRCh37"),
    ("CYP2C9", "10", 96698415, 96749147, 1, "GRCh37"),
    # ... 15 total Tier 1 genes
]

TIER_2_GENES = [
    ("CYP3A4", "7", 99376140, 99391055, 2, "GRCh37"),
    ("CYP3A5", "7", 99245913, 99277621, 2, "GRCh37"),
    # ... 16 total Tier 2 genes
]

TIER_3_GENES = [
    ("OPRM1", "6", 154039662, 154158662, 3, "GRCh37"),
    ("COMT", "22", 19929263, 19957263, 3, "GRCh37"),
    # ... 8 total Tier 3 genes
]
```

**Where this comes from:**
- NCBI Gene database: https://www.ncbi.nlm.nih.gov/gene
- Genome build: GRCh37 (hg19)
- Manually verified genomic coordinates

---

### 2. Variant Definitions (PharmVar Database)
**Source:** PharmVar - Pharmacogene Variation Consortium

**Website:** https://www.pharmvar.org/

**What PharmVar provides:**
- Star allele definitions (*1, *2, *3, *4, etc.)
- rsID identifiers (rs3892097, rs4986893, etc.)
- Genomic positions
- Reference/alternate alleles
- Functional classifications (Normal/Reduced/No function)

**Example PharmVar data for CYP2D6:**
```
Allele    rsID         Position    Ref  Alt  Function
*1        -            -           -    -    Normal function
*2        rs16947      42526694    C    T    Normal function
*3        rs35742686   42522613    A    DEL  No function
*4        rs3892097    42526694    C    T    No function
*5        -            -           -    -    No function (gene deletion)
... (150+ more variants)
```

**How we get it:**
```bash
# Automated download via scripts/pharmvar_sync.py
python scripts/pharmvar_sync.py --gene CYP2D6

# Downloads from: https://www.pharmvar.org/download/cyp2d6_alleles.tsv
# Parses TSV file
# Inserts into variants table
```

---

### 3. Phenotype Mappings (CPIC Database)
**Source:** CPIC - Clinical Pharmacogenetics Implementation Consortium

**Website:** https://cpicpgx.org/

**What CPIC provides:**
- Diplotype → Phenotype translations
- Activity score calculations
- Clinical guidelines
- Drug-gene interaction recommendations

**Example CPIC data for CYP2D6:**
```
Diplotype    Phenotype                    Activity Score
*1/*1        Normal Metabolizer           2.0
*1/*4        Intermediate Metabolizer     1.0
*4/*4        Poor Metabolizer             0.0
*1/*2xN      Ultra-rapid Metabolizer      3.0
... (50+ more diplotypes)
```

**How we get it:**
```bash
# Automated download via scripts/cpic_sync.py
python scripts/cpic_sync.py --gene CYP2D6

# Scrapes from: https://cpicpgx.org/guidelines/
# Parses HTML tables
# Inserts into phenotypes table
```

---

## Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA SOURCES (External)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. NCBI Gene Database                                          │
│     https://www.ncbi.nlm.nih.gov/gene                          │
│     → Gene coordinates (chr, start, end)                        │
│                                                                  │
│  2. PharmVar Database                                           │
│     https://www.pharmvar.org/                                   │
│     → Star alleles, rsIDs, functions, activity scores          │
│                                                                  │
│  3. CPIC Database                                               │
│     https://cpicpgx.org/                                        │
│     → Diplotype→Phenotype mappings, clinical guidelines        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  AUTOMATED PIPELINE (Scripts)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Step 1: Initialize Gene Metadata                              │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ python scripts/init_gene_database.py --tier 1          │   │
│  │                                                         │   │
│  │ Reads: TIER_1_GENES list (hardcoded)                  │   │
│  │ Writes: genes table in pharmacogenes.db               │   │
│  │ Output: 15 genes loaded                                │   │
│  └────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  Step 2: Sync PharmVar Variants                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ python scripts/pharmvar_sync.py --tier 1               │   │
│  │                                                         │   │
│  │ Downloads: PharmVar TSV files (web scraping)          │   │
│  │ Parses: Star alleles, rsIDs, functions                │   │
│  │ Writes: variants table in pharmacogenes.db            │   │
│  │ Output: ~2,500 variants loaded                         │   │
│  └────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  Step 3: Sync CPIC Phenotypes                                  │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ python scripts/cpic_sync.py --tier 1                   │   │
│  │                                                         │   │
│  │ Scrapes: CPIC guideline pages (HTML parsing)          │   │
│  │ Parses: Diplotype→Phenotype tables                    │   │
│  │ Writes: phenotypes table in pharmacogenes.db          │   │
│  │ Output: ~750 phenotypes loaded                         │   │
│  └────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  Step 4: Validate Data Quality                                 │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ python scripts/validate_pgx_data.py --tier 1           │   │
│  │                                                         │   │
│  │ Checks: Completeness, consistency, CPIC compliance    │   │
│  │ Output: Validation report                              │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  DATABASE (Local Storage)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  File: data/pgx/pharmacogenes.db (SQLite)                      │
│                                                                  │
│  Tables:                                                         │
│  ┌──────────────────────────────────────────────────────┐     │
│  │ genes          → 39 genes                            │     │
│  │ variants       → ~6,100 variants                     │     │
│  │ phenotypes     → ~1,950 phenotypes                   │     │
│  │ drug_gene_pairs → ~450 drug-gene interactions        │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  APPLICATION (Runtime)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Module: src/variant_db_v2.py                                  │
│                                                                  │
│  Functions:                                                      │
│  • get_gene_variants(gene_symbol)                              │
│  • get_phenotype_translation(gene_symbol, diplotype)           │
│  • get_gene_location(gene_symbol)                              │
│  • list_supported_genes()                                       │
│                                                                  │
│  Used by:                                                        │
│  • src/allele_caller.py (allele calling)                       │
│  • src/vcf_processor.py (VCF processing)                       │
│  • api.py (REST API endpoints)                                 │
│  • app.py (Streamlit UI)                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Example: Adding CYP3A4 Gene

### Step 1: Gene Metadata (Manual)
```python
# Already in init_gene_database.py TIER_2_GENES list
("CYP3A4", "7", 99376140, 99391055, 2, "GRCh37")
```

**Source:** NCBI Gene database
**URL:** https://www.ncbi.nlm.nih.gov/gene/1576
**Data:** Chromosome 7, positions 99376140-99391055

### Step 2: PharmVar Sync (Automated)
```bash
python scripts/pharmvar_sync.py --gene CYP3A4
```

**Downloads from:** https://www.pharmvar.org/download/cyp3a4_alleles.tsv

**Example data:**
```
Allele  rsID        Position   Ref  Alt  Function
*2      rs35599367  99357983   C    T    Normal function
*3      rs4986910   99358371   T    C    No function
*4      rs4987161   99359739   G    A    Reduced function
... (150+ more variants)
```

**Inserts into database:**
```sql
INSERT INTO variants (gene_id, rsid, position, ref_allele, alt_allele,
                      allele_name, function, activity_score)
VALUES
  (15, 'rs35599367', 99357983, 'C', 'T', '*2', 'Normal function', 1.0),
  (15, 'rs4986910', 99358371, 'T', 'C', '*3', 'No function', 0.0),
  (15, 'rs4987161', 99359739, 'G', 'A', '*4', 'Reduced function', 0.5);
```

### Step 3: CPIC Sync (Automated)
```bash
python scripts/cpic_sync.py --gene CYP3A4
```

**Scrapes from:** https://cpicpgx.org/guidelines/guideline-for-tacrolimus-and-cyp3a5/

**Example data:**
```
Diplotype    Phenotype
*1/*1        Normal Metabolizer
*1/*2        Normal Metabolizer
*1/*3        Intermediate Metabolizer
... (50+ more diplotypes)
```

**Inserts into database:**
```sql
INSERT INTO phenotypes (gene_id, diplotype, phenotype_display, phenotype_normalized)
VALUES
  (15, '*1/*1', 'Normal Metabolizer', 'normal_metabolizer'),
  (15, '*1/*2', 'Normal Metabolizer', 'normal_metabolizer'),
  (15, '*1/*3', 'Intermediate Metabolizer', 'intermediate_metabolizer');
```

---

## Verification

### Check what's in the database:
```bash
# Connect to database
sqlite3 data/pgx/pharmacogenes.db

# Check gene count
SELECT COUNT(*) FROM genes;
-- Output: 39

# Check variant count
SELECT COUNT(*) FROM variants;
-- Output: ~6,100

# Check phenotype count
SELECT COUNT(*) FROM phenotypes;
-- Output: ~1,950

# Check specific gene
SELECT * FROM genes WHERE gene_symbol = 'CYP3A4';
-- Output: gene_id, gene_symbol, chromosome, start_pos, end_pos, tier

# Check variants for CYP3A4
SELECT COUNT(*) FROM variants WHERE gene_id =
  (SELECT gene_id FROM genes WHERE gene_symbol = 'CYP3A4');
-- Output: ~150 variants
```

---

## Summary

**Where does the data come from?**

1. **Gene coordinates:** NCBI Gene database (manually curated, hardcoded in `init_gene_database.py`)
2. **Variant definitions:** PharmVar database (automated download via `pharmvar_sync.py`)
3. **Phenotype mappings:** CPIC database (automated scraping via `cpic_sync.py`)

**How does it get into the system?**

1. Run `init_gene_database.py` → Creates genes table
2. Run `pharmvar_sync.py` → Downloads and loads variants
3. Run `cpic_sync.py` → Scrapes and loads phenotypes
4. Run `validate_pgx_data.py` → Validates data quality

**Where is it stored?**

- Local SQLite database: `data/pgx/pharmacogenes.db`
- 4 tables: genes, variants, phenotypes, drug_gene_pairs

**How is it accessed?**

- Python module: `src/variant_db_v2.py`
- Used by: allele_caller.py, vcf_processor.py, api.py, app.py

---

**Created:** April 12, 2026
**Purpose:** Explain data source flow and pipeline
**Audience:** Developers, technical reviewers
