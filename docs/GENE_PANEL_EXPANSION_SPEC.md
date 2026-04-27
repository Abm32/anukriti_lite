# Gene Panel Expansion: Technical Specification
## Scaling from 8 to 100+ Pharmacogenes

**Version**: 1.0
**Date**: April 10, 2026
**Status**: APPROVED FOR IMPLEMENTATION
**Priority**: P0 (CRITICAL)

---

## 1. Overview

This specification details the technical implementation for expanding Anukriti's pharmacogene panel from 8 genes to 100+ genes while maintaining performance and reducing storage costs.

### Goals

1. Support 100+ pharmacogenes without VCF file size explosion
2. Reduce storage from 150GB → 20MB (7500x compression)
3. Enable real-time patient profiling (< 5 seconds)
4. Automate data curation pipeline
5. Maintain CPIC/PharmVar compliance

### Non-Goals

- Full genome analysis (out of scope)
- Structural variant calling beyond CNVs (future work)
- Population genetics analysis (future work)

---

## 2. Architecture Changes

### 2.1 Current Architecture (Limitations)

```
VCF Files (40GB)
    ↓
vcf_processor.py (tabix extraction)
    ↓
variant_db.py (hardcoded dict)
    ↓
allele_caller.py (TSV/JSON lookup)
    ↓
Patient Profile
```

**Problems**:
- VCF files too large (40GB → 150GB for 100 genes)
- variant_db.py hardcoded (doesn't scale)
- Manual TSV/JSON curation (2-4 hours per gene)

### 2.2 New Architecture (Scalable)

```
PharmVar/CPIC APIs
    ↓
Automated Sync Pipeline
    ↓
pharmacogenes.db (SQLite, 10-20MB)
    ↓
variant_db.py (DB-backed)
    ↓
allele_caller.py (unchanged)
    ↓
Patient Profile
```

**Benefits**:
- No VCF downloads for common queries
- Dynamic gene loading from database
- Automated updates (weekly sync)
- 7500x storage reduction

---

## 3. Database Schema

### 3.1 Core Tables


```sql
-- Pharmacogene definitions
CREATE TABLE genes (
    gene_id INTEGER PRIMARY KEY,
    gene_symbol TEXT NOT NULL UNIQUE,
    chromosome TEXT NOT NULL,
    start_pos INTEGER NOT NULL,
    end_pos INTEGER NOT NULL,
    build TEXT NOT NULL DEFAULT 'GRCh37',
    tier INTEGER NOT NULL DEFAULT 2,  -- 1=critical, 2=standard, 3=research
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_gene_symbol (gene_symbol),
    INDEX idx_chromosome (chromosome)
);

-- Variant definitions (PharmVar)
CREATE TABLE variants (
    variant_id INTEGER PRIMARY KEY,
    gene_id INTEGER NOT NULL,
    rsid TEXT NOT NULL,
    chromosome TEXT NOT NULL,
    position INTEGER NOT NULL,
    ref_allele TEXT NOT NULL,
    alt_allele TEXT NOT NULL,
    allele_name TEXT NOT NULL,  -- e.g., "*2", "*3"
    function TEXT NOT NULL,      -- "Normal", "Reduced", "No function"
    activity_score REAL NOT NULL,
    pharmvar_version TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (gene_id) REFERENCES genes(gene_id),
    INDEX idx_rsid (rsid),
    INDEX idx_gene_rsid (gene_id, rsid),
    INDEX idx_position (chromosome, position)
);

-- Diplotype to phenotype mappings (CPIC)
CREATE TABLE phenotypes (
    phenotype_id INTEGER PRIMARY KEY,
    gene_id INTEGER NOT NULL,
    diplotype TEXT NOT NULL,
    phenotype_display TEXT NOT NULL,
    phenotype_normalized TEXT NOT NULL,
    cpic_version TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (gene_id) REFERENCES genes(gene_id),
    INDEX idx_gene_diplotype (gene_id, diplotype)
);

-- Drug-gene interactions
CREATE TABLE drug_gene_pairs (
    pair_id INTEGER PRIMARY KEY,
    drug_name TEXT NOT NULL,
    gene_id INTEGER NOT NULL,
    cpic_level TEXT,  -- "A", "B", "C", "D"
    guideline_url TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (gene_id) REFERENCES genes(gene_id),
    INDEX idx_drug (drug_name),
    INDEX idx_gene (gene_id)
);

-- Data provenance tracking
CREATE TABLE data_versions (
    version_id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,  -- "PharmVar", "CPIC"
    version TEXT NOT NULL,
    download_date TIMESTAMP NOT NULL,
    record_count INTEGER,
    checksum TEXT
);
```

### 3.2 Initial Data Load

**Tier 1 Genes** (15 genes, load immediately):
```python
TIER_1_GENES = [
    # Current (already implemented)
    ("CYP2D6", "22", 42522500, 42530900),
    ("CYP2C19", "10", 96535040, 96625463),
    ("CYP2C9", "10", 96698415, 96749147),
    ("UGT1A1", "2", 234668875, 234689625),
    ("SLCO1B1", "12", 21288593, 21397223),
    ("VKORC1", "16", 31102163, 31107800),
    ("TPMT", "6", 18128542, 18155374),
    ("DPYD", "1", 97543299, 97883432),

    # New (critical expansion)
    ("CYP3A4", "7", 99376140, 99391055),
    ("CYP3A5", "7", 99245913, 99277621),
    ("CYP1A2", "15", 75041185, 75048543),
    ("CYP2B6", "19", 41497204, 41524792),
    ("NAT2", "8", 18248755, 18258723),
    ("GSTM1", "1", 110230414, 110237831),
    ("GSTT1", "22", 24376190, 24384284),
]
```

---

## 4. Implementation Plan

### 4.1 Phase 1: Database Backend (Days 1-3)

**File**: `src/variant_db_v2.py` (new)

```python
"""
Database-backed variant lookup for scalable pharmacogene panel.
Replaces hardcoded VARIANT_DB dict with SQLite backend.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_DB_PATH = Path(__file__).parent.parent / "data" / "pgx" / "pharmacogenes.db"
_CONN: Optional[sqlite3.Connection] = None

def get_connection() -> sqlite3.Connection:
    """Get or create database connection (singleton)."""
    global _CONN
    if _CONN is None:
        _CONN = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _CONN.row_factory = sqlite3.Row
    return _CONN

def get_gene_variants(gene_symbol: str) -> List[Dict]:
    """
    Get all variants for a gene from database.
    Returns list of dicts with rsid, allele, function, activity_score.
    """
    conn = get_connection()
    cursor = conn.execute("""
        SELECT v.rsid, v.allele_name, v.function, v.activity_score,
               v.ref_allele, v.alt_allele, v.position
        FROM variants v
        JOIN genes g ON v.gene_id = g.gene_id
        WHERE g.gene_symbol = ?
        ORDER BY v.position
    """, (gene_symbol,))

    return [dict(row) for row in cursor.fetchall()]

def get_phenotype_translation(gene_symbol: str) -> Dict[str, str]:
    """
    Get diplotype → phenotype mapping for a gene.
    Returns dict: {"*1/*2": "Intermediate Metabolizer", ...}
    """
    conn = get_connection()
    cursor = conn.execute("""
        SELECT p.diplotype, p.phenotype_display
        FROM phenotypes p
        JOIN genes g ON p.gene_id = g.gene_id
        WHERE g.gene_symbol = ?
    """, (gene_symbol,))

    return {row["diplotype"]: row["phenotype_display"]
            for row in cursor.fetchall()}

def get_gene_location(gene_symbol: str, build: str = "GRCh37") -> Optional[Dict]:
    """Get chromosome and position range for a gene."""
    conn = get_connection()
    cursor = conn.execute("""
        SELECT chromosome, start_pos, end_pos
        FROM genes
        WHERE gene_symbol = ? AND build = ?
    """, (gene_symbol, build))

    row = cursor.fetchone()
    return dict(row) if row else None

def list_supported_genes(tier: Optional[int] = None) -> List[str]:
    """List all genes in database, optionally filtered by tier."""
    conn = get_connection()
    if tier is None:
        cursor = conn.execute("SELECT gene_symbol FROM genes ORDER BY gene_symbol")
    else:
        cursor = conn.execute(
            "SELECT gene_symbol FROM genes WHERE tier = ? ORDER BY gene_symbol",
            (tier,)
        )
    return [row["gene_symbol"] for row in cursor.fetchall()]
```

**Migration Strategy**:
1. Keep `variant_db.py` for backward compatibility
2. Add `variant_db_v2.py` with database backend
3. Update `allele_caller.py` to try DB first, fall back to dict
4. Deprecate `variant_db.py` after testing


### 4.2 Phase 2: Automated Data Pipeline (Days 4-7)

**File**: `scripts/pharmvar_sync.py` (new)

```python
"""
Automated PharmVar data synchronization.
Downloads allele definitions and generates database entries.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from pathlib import Path

PHARMVAR_BASE = "https://www.pharmvar.org/download"

def download_gene_alleles(gene_symbol: str) -> pd.DataFrame:
    """
    Download PharmVar allele definition file for a gene.
    Returns DataFrame with columns: allele, rsid, alt, function, activity_score
    """
    # PharmVar provides TSV downloads per gene
    url = f"{PHARMVAR_BASE}/{gene_symbol.lower()}_alleles.tsv"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # Parse TSV
        df = pd.read_csv(io.StringIO(response.text), sep="\t", comment="#")

        # Standardize columns
        df = df.rename(columns={
            "Allele": "allele",
            "rsID": "rsid",
            "Alt": "alt",
            "Function": "function"
        })

        # Map function to activity score
        df["activity_score"] = df["function"].map({
            "Normal function": 1.0,
            "Increased function": 1.5,
            "Reduced function": 0.5,
            "No function": 0.0,
            "Loss of function": 0.0,
        })

        return df

    except Exception as e:
        print(f"Error downloading {gene_symbol}: {e}")
        return pd.DataFrame()

def sync_gene_to_database(gene_symbol: str, conn: sqlite3.Connection):
    """Download and insert gene data into database."""
    df = download_gene_alleles(gene_symbol)
    if df.empty:
        return False

    # Get gene_id
    cursor = conn.execute(
        "SELECT gene_id FROM genes WHERE gene_symbol = ?",
        (gene_symbol,)
    )
    row = cursor.fetchone()
    if not row:
        print(f"Gene {gene_symbol} not in database")
        return False

    gene_id = row[0]

    # Insert variants
    for _, row in df.iterrows():
        conn.execute("""
            INSERT OR REPLACE INTO variants
            (gene_id, rsid, allele_name, function, activity_score, pharmvar_version)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            gene_id,
            row["rsid"],
            row["allele"],
            row["function"],
            row["activity_score"],
            "2026-04"  # Version from download date
        ))

    conn.commit()
    print(f"Synced {len(df)} variants for {gene_symbol}")
    return True

def sync_all_tier1_genes():
    """Sync all Tier 1 genes from PharmVar."""
    conn = get_connection()
    tier1_genes = list_supported_genes(tier=1)

    for gene in tier1_genes:
        print(f"Syncing {gene}...")
        sync_gene_to_database(gene, conn)

    print(f"Sync complete: {len(tier1_genes)} genes updated")
```

**File**: `scripts/cpic_sync.py` (new)

```python
"""
Automated CPIC guideline synchronization.
Scrapes diplotype → phenotype mappings from CPIC website.
"""

import requests
from bs4 import BeautifulSoup
import json

CPIC_BASE = "https://cpicpgx.org/guidelines"

def scrape_cpic_phenotypes(gene_symbol: str) -> Dict[str, str]:
    """
    Scrape CPIC phenotype table for a gene.
    Returns dict: {"*1/*2": "Intermediate Metabolizer", ...}
    """
    # CPIC provides downloadable tables per gene
    url = f"{CPIC_BASE}/{gene_symbol.lower()}-phenotype-table"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", class_="phenotype-table")

        if not table:
            return {}

        phenotypes = {}
        for row in table.find_all("tr")[1:]:  # Skip header
            cols = row.find_all("td")
            if len(cols) >= 2:
                diplotype = cols[0].text.strip()
                phenotype = cols[1].text.strip()
                phenotypes[diplotype] = phenotype

        return phenotypes

    except Exception as e:
        print(f"Error scraping CPIC for {gene_symbol}: {e}")
        return {}

def sync_cpic_to_database(gene_symbol: str, conn: sqlite3.Connection):
    """Download and insert CPIC phenotypes into database."""
    phenotypes = scrape_cpic_phenotypes(gene_symbol)
    if not phenotypes:
        return False

    # Get gene_id
    cursor = conn.execute(
        "SELECT gene_id FROM genes WHERE gene_symbol = ?",
        (gene_symbol,)
    )
    row = cursor.fetchone()
    if not row:
        return False

    gene_id = row[0]

    # Insert phenotypes
    for diplotype, phenotype_display in phenotypes.items():
        # Normalize phenotype for internal use
        phenotype_normalized = phenotype_display.lower().replace(" ", "_")

        conn.execute("""
            INSERT OR REPLACE INTO phenotypes
            (gene_id, diplotype, phenotype_display, phenotype_normalized, cpic_version)
            VALUES (?, ?, ?, ?, ?)
        """, (
            gene_id,
            diplotype,
            phenotype_display,
            phenotype_normalized,
            "2026-04"
        ))

    conn.commit()
    print(f"Synced {len(phenotypes)} phenotypes for {gene_symbol}")
    return True
```

### 4.3 Phase 3: Targeted VCF Extraction (Days 8-10)

**File**: `scripts/extract_pharmacogene_regions.py` (new)

```python
"""
Extract only pharmacogene regions from full chromosome VCFs.
Reduces 150GB → 500MB (300x compression).
"""

import subprocess
from pathlib import Path

def create_bed_file(output_path: str = "data/pgx/pharmacogenes.bed"):
    """
    Create BED file with all pharmacogene regions.
    Format: chr10\t96535040\t96625463\tCYP2C19
    """
    conn = get_connection()
    cursor = conn.execute("""
        SELECT chromosome, start_pos, end_pos, gene_symbol
        FROM genes
        WHERE build = 'GRCh37'
        ORDER BY chromosome, start_pos
    """)

    with open(output_path, "w") as f:
        for row in cursor.fetchall():
            f.write(f"{row['chromosome']}\t{row['start_pos']}\t{row['end_pos']}\t{row['gene_symbol']}\n")

    print(f"Created BED file: {output_path}")
    return output_path

def extract_regions(vcf_path: str, bed_path: str, output_path: str):
    """
    Use tabix to extract only pharmacogene regions from VCF.
    Requires .tbi index file.
    """
    cmd = [
        "tabix",
        "-h",  # Include header
        "-R", bed_path,  # Regions file
        vcf_path
    ]

    with open(output_path, "w") as f:
        subprocess.run(cmd, stdout=f, check=True)

    print(f"Extracted regions to: {output_path}")

    # Compress output
    subprocess.run(["bgzip", "-f", output_path], check=True)
    subprocess.run(["tabix", "-p", "vcf", f"{output_path}.gz"], check=True)

    return f"{output_path}.gz"

def extract_all_chromosomes(genomes_dir: str = "data/genomes"):
    """Extract pharmacogene regions from all chromosome VCFs."""
    bed_path = create_bed_file()
    genomes_path = Path(genomes_dir)

    for vcf_file in genomes_path.glob("ALL.chr*.vcf.gz"):
        chr_name = vcf_file.stem.split(".")[1]  # Extract "chr10" from filename
        output_path = genomes_path / f"pharmacogenes_{chr_name}.vcf"

        print(f"Processing {vcf_file.name}...")
        extract_regions(str(vcf_file), bed_path, str(output_path))

    print("Extraction complete!")
```

**Usage**:
```bash
# One-time extraction (run after downloading full VCFs)
python scripts/extract_pharmacogene_regions.py

# Result: data/genomes/pharmacogenes_chr*.vcf.gz (500MB total)
# Can delete original ALL.chr*.vcf.gz files (save 150GB)
```

---

## 5. Testing Strategy

### 5.1 Unit Tests

**File**: `tests/test_variant_db_v2.py`

```python
def test_database_connection():
    """Test database connection and schema."""
    conn = get_connection()
    assert conn is not None

    # Check tables exist
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    tables = {row[0] for row in cursor.fetchall()}
    assert "genes" in tables
    assert "variants" in tables
    assert "phenotypes" in tables

def test_get_gene_variants():
    """Test variant lookup for known gene."""
    variants = get_gene_variants("CYP2D6")
    assert len(variants) > 0
    assert "rsid" in variants[0]
    assert "allele_name" in variants[0]
    assert "activity_score" in variants[0]

def test_get_phenotype_translation():
    """Test phenotype lookup for known gene."""
    phenotypes = get_phenotype_translation("CYP2C19")
    assert "*1/*2" in phenotypes
    assert "Intermediate" in phenotypes["*1/*2"]

def test_tier1_genes_present():
    """Verify all Tier 1 genes are in database."""
    tier1 = list_supported_genes(tier=1)
    assert len(tier1) >= 15
    assert "CYP3A4" in tier1
    assert "CYP3A5" in tier1
```

### 5.2 Integration Tests

**File**: `tests/test_gene_panel_expansion.py`

```python
def test_end_to_end_new_gene():
    """Test complete workflow with newly added gene."""
    # Use CYP3A4 as test case
    gene = "CYP3A4"

    # 1. Check gene in database
    location = get_gene_location(gene)
    assert location is not None
    assert location["chromosome"] == "7"

    # 2. Get variants
    variants = get_gene_variants(gene)
    assert len(variants) > 0

    # 3. Get phenotypes
    phenotypes = get_phenotype_translation(gene)
    assert len(phenotypes) > 0

    # 4. Test allele calling (mock VCF data)
    mock_variants = {
        "rs776746": ("G", "A", "0/1")  # CYP3A5*3
    }
    result = call_gene_from_variants(gene, mock_variants)
    assert result is not None
    assert "diplotype" in result

def test_performance_100_genes():
    """Verify database performance with 100 genes."""
    import time

    genes = list_supported_genes()
    assert len(genes) >= 100

    start = time.time()
    for gene in genes[:100]:
        variants = get_gene_variants(gene)
        phenotypes = get_phenotype_translation(gene)
    elapsed = time.time() - start

    # Should complete in < 5 seconds
    assert elapsed < 5.0
```

---

## 6. Deployment Plan

### 6.1 Staging Deployment (Day 11)

1. Build database with Tier 1 genes (15 genes)
2. Deploy to staging environment
3. Run integration tests
4. Performance benchmarking
5. Manual QA testing

### 6.2 Production Deployment (Day 12)

1. Database migration (add new tables)
2. Deploy code changes
3. Run smoke tests
4. Monitor for 24 hours
5. Gradual rollout (10% → 50% → 100%)

### 6.3 Rollback Plan

- Keep old `variant_db.py` as fallback
- Database changes are additive (no breaking changes)
- Can revert code deployment without data loss
- Monitoring alerts for performance degradation

---

## 7. Success Criteria

✅ **Functional**:
- All 15 Tier 1 genes working
- Database queries < 100ms (p95)
- Automated sync runs successfully
- Backward compatibility maintained

✅ **Performance**:
- Patient profile generation < 5 seconds
- Database size < 20MB
- No VCF downloads for common queries

✅ **Quality**:
- 100% test coverage for new code
- Zero regressions in existing functionality
- Data validation passes for all genes

---

## 8. Future Work

### Phase 2 Expansion (Weeks 3-4)
- Add remaining 85 genes (Tier 2 + 3)
- Implement patient VCF upload
- Add clinical report templates

### Phase 3 Optimization (Weeks 5-6)
- Database query optimization
- Caching layer for common queries
- Real-time monitoring dashboard

### Phase 4 Clinical Integration (Weeks 7-8)
- EHR integration
- HIPAA compliance audit
- Clinical validation studies
