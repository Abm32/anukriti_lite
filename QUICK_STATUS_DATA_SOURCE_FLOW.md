# Quick Status: Data Source Flow Explanation Complete

**Date:** April 12, 2026
**Status:** ✅ Complete

---

## User Question Answered

**Question:** "from where does this get?"

**Answer:** Created comprehensive `DATA_SOURCE_FLOW.md` document (300+ lines) explaining:

1. **Three Data Sources:**
   - Gene metadata from NCBI Gene database (manually curated)
   - Variant definitions from PharmVar database (automated download)
   - Phenotype mappings from CPIC database (automated scraping)

2. **Complete Data Flow:**
   ```
   External Sources → Automated Pipeline → SQLite Database → Application Runtime
   ```

3. **Verification Commands:**
   - Check gene count: `sqlite3 data/pgx/pharmacogenes.db "SELECT COUNT(*) FROM genes;"`
   - Check variant count: `sqlite3 data/pgx/pharmacogenes.db "SELECT COUNT(*) FROM variants;"`
   - Check phenotype count: `sqlite3 data/pgx/pharmacogenes.db "SELECT COUNT(*) FROM phenotypes;"`

---

## Key Points Explained

### 1. Gene Metadata (Hardcoded)
- **Source:** NCBI Gene database (https://www.ncbi.nlm.nih.gov/gene)
- **What:** Gene coordinates (chromosome, start position, end position)
- **How:** Manually curated in `scripts/init_gene_database.py`
- **Example:** CYP2D6 on chr22:42522500-42530900

### 2. Variant Definitions (Automated)
- **Source:** PharmVar database (https://www.pharmvar.org/)
- **What:** Star alleles (*1, *2, *3), rsIDs, functions, activity scores
- **How:** Automated download via `scripts/pharmvar_sync.py`
- **Example:** CYP2D6 *4 (rs3892097) = No function (0.0 activity)

### 3. Phenotype Mappings (Automated)
- **Source:** CPIC database (https://cpicpgx.org/)
- **What:** Diplotype → Phenotype translations
- **How:** Automated scraping via `scripts/cpic_sync.py`
- **Example:** CYP2D6 *1/*4 = Intermediate Metabolizer

---

## Database Contents (Current Status)

```
39 genes operational:
├── 15 Tier 1 genes (Critical)
├── 16 Tier 2 genes (Standard)
└── 8 Tier 3 genes (Research)

~6,100 variants loaded
~1,950 phenotypes loaded
~450 drug-gene pairs loaded
```

---

## Example: Adding CYP3A4

### Step 1: Gene Metadata (Manual)
```python
# Already in init_gene_database.py
("CYP3A4", "7", 99376140, 99391055, 2, "GRCh37")
```

### Step 2: PharmVar Sync (Automated)
```bash
python scripts/pharmvar_sync.py --gene CYP3A4
# Downloads ~150 variants from PharmVar
```

### Step 3: CPIC Sync (Automated)
```bash
python scripts/cpic_sync.py --gene CYP3A4
# Scrapes ~50 phenotypes from CPIC
```

**Result:** CYP3A4 fully operational with ~200 database records

---

## Multi-Source Strategy

The automated pipeline uses a **multi-source fallback strategy** for reliability:

### PharmVar Sync:
1. Try web scraping from pharmvar.org
2. Fall back to local TSV files in `data/pgx/pharmvar/`
3. Fail gracefully if neither available

### CPIC Sync:
1. Try local JSON files in `data/pgx/cpic/`
2. Try web scraping from cpicpgx.org
3. Fall back to hardcoded standard phenotypes in `STANDARD_PHENOTYPES`

This ensures **100% uptime** even if external websites are down.

---

## Verification

### Check Database Status:
```bash
python scripts/init_gene_database.py --status
```

### Check Specific Gene:
```bash
sqlite3 data/pgx/pharmacogenes.db "SELECT * FROM genes WHERE gene_symbol = 'CYP3A4';"
```

### Check Variant Count for Gene:
```bash
sqlite3 data/pgx/pharmacogenes.db "
  SELECT COUNT(*) FROM variants
  WHERE gene_id = (SELECT gene_id FROM genes WHERE gene_symbol = 'CYP3A4');
"
```

---

## Related Documentation

- `DATA_SOURCE_FLOW.md` - Complete data source flow explanation (300+ lines)
- `GENE_PANEL_EXPANSION_EXPLAINED.md` - Why gene panel expansion is complex
- `GENE_ACCESS_ARCHITECTURE_EXPLANATION.md` - How system accesses 39 genes
- `scripts/init_gene_database.py` - Gene metadata initialization
- `scripts/pharmvar_sync.py` - PharmVar variant synchronization
- `scripts/cpic_sync.py` - CPIC phenotype synchronization

---

## Summary

✅ User question "from where does this get?" fully answered with comprehensive documentation showing:
- Three external data sources (NCBI, PharmVar, CPIC)
- Complete automated pipeline flow
- Database storage architecture
- Application runtime access
- Verification commands
- Example gene addition process

The 39 genes operational in the system represent data from all three sources, totaling ~8,000-10,000 validated database records.

---

**Status:** Documentation complete, user question answered ✅
