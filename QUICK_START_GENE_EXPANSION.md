# Quick Start: Gene Panel Expansion
## Get from 8 to 100+ genes in 2 weeks

**For**: Developers implementing production-ready pharmacogenomics
**Time**: 2 weeks focused work
**Impact**: 1250% increase in gene coverage, 90% cost reduction

---

## Week 1: Foundation

### Day 1-2: Database Setup

```bash
# 1. Create database schema
cd data/pgx
sqlite3 pharmacogenes.db < ../../scripts/schema.sql

# 2. Load Tier 1 genes
python scripts/init_gene_database.py --tier 1

# 3. Verify
sqlite3 pharmacogenes.db "SELECT COUNT(*) FROM genes;"
# Expected: 15 genes
```

### Day 3-4: Code Integration

```bash
# 1. Install new dependencies
pip install requests beautifulsoup4

# 2. Test database backend
pytest tests/test_variant_db_v2.py -v

# 3. Update vcf_processor.py
# Replace hardcoded VARIANT_DB with database calls

# 4. Run integration tests
pytest tests/test_gene_panel_expansion.py -v
```

### Day 5: Automated Sync

```bash
# 1. Sync PharmVar data
python scripts/pharmvar_sync.py --genes CYP3A4 CYP3A5 CYP1A2

# 2. Sync CPIC phenotypes
python scripts/cpic_sync.py --genes CYP3A4 CYP3A5 CYP1A2

# 3. Validate
python scripts/validate_pgx_data.py --all

# 4. Deploy to staging
make deploy-staging
```

---

## Week 2: Scale & Optimize

### Day 6-7: Targeted Extraction

```bash
# 1. Create BED file
python scripts/extract_pharmacogene_regions.py --create-bed

# 2. Extract regions (one-time, 30 min)
python scripts/extract_pharmacogene_regions.py --extract-all

# 3. Verify size reduction
du -sh data/genomes/pharmacogenes_*.vcf.gz
# Expected: ~500MB total (vs 150GB original)

# 4. Update VCF paths in config
# Point to pharmacogenes_chr*.vcf.gz instead of ALL.chr*.vcf.gz
```

### Day 8-9: Add Remaining Genes

```bash
# 1. Sync all Tier 1 genes (15 total)
python scripts/pharmvar_sync.py --tier 1

# 2. Sync all Tier 2 genes (50 total)
python scripts/pharmvar_sync.py --tier 2

# 3. Performance test
python scripts/benchmark_gene_panel.py --genes 100

# 4. Optimize slow queries
python scripts/optimize_database.py
```

### Day 10: Production Deploy

```bash
# 1. Final validation
pytest tests/ -v --cov=src

# 2. Build production database
python scripts/build_production_db.py

# 3. Deploy
make deploy-production

# 4. Monitor
python scripts/production_monitor.py --watch
```

---

## Key Files to Create

### 1. Database Schema (`scripts/schema.sql`)

```sql
-- See docs/GENE_PANEL_EXPANSION_SPEC.md Section 3.1
-- Copy the CREATE TABLE statements
```

### 2. Database Backend (`src/variant_db_v2.py`)

```python
# See docs/GENE_PANEL_EXPANSION_SPEC.md Section 4.1
# Implements get_gene_variants(), get_phenotype_translation()
```

### 3. PharmVar Sync (`scripts/pharmvar_sync.py`)

```python
# See docs/GENE_PANEL_EXPANSION_SPEC.md Section 4.2
# Automates PharmVar data downloads
```

### 4. CPIC Sync (`scripts/cpic_sync.py`)

```python
# See docs/GENE_PANEL_EXPANSION_SPEC.md Section 4.2
# Scrapes CPIC phenotype tables
```

### 5. Region Extraction (`scripts/extract_pharmacogene_regions.py`)

```python
# See docs/GENE_PANEL_EXPANSION_SPEC.md Section 4.3
# Extracts only pharmacogene regions from VCFs
```

---

## Validation Checklist

Before deploying to production, verify:

- [ ] Database has 100+ genes
- [ ] All Tier 1 genes have variants
- [ ] All Tier 1 genes have phenotypes
- [ ] Database size < 20MB
- [ ] Query performance < 100ms (p95)
- [ ] Automated sync runs successfully
- [ ] Integration tests pass (100%)
- [ ] No regressions in existing functionality
- [ ] Documentation updated
- [ ] Monitoring alerts configured

---

## Troubleshooting

### Database Connection Errors

```python
# Check database exists
import os
assert os.path.exists("data/pgx/pharmacogenes.db")

# Check schema
import sqlite3
conn = sqlite3.connect("data/pgx/pharmacogenes.db")
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
print([row[0] for row in cursor.fetchall()])
# Expected: ['genes', 'variants', 'phenotypes', 'drug_gene_pairs', 'data_versions']
```

### PharmVar Sync Failures

```bash
# Check network connectivity
curl -I https://www.pharmvar.org/download

# Check gene name format
# PharmVar uses lowercase: cyp2d6, not CYP2D6

# Manual download for testing
wget https://www.pharmvar.org/download/cyp2d6_alleles.tsv
```

### Performance Issues

```sql
-- Check database size
SELECT
    (SELECT COUNT(*) FROM genes) as gene_count,
    (SELECT COUNT(*) FROM variants) as variant_count,
    (SELECT COUNT(*) FROM phenotypes) as phenotype_count;

-- Check slow queries
EXPLAIN QUERY PLAN
SELECT * FROM variants WHERE gene_id = 1;

-- Add missing indexes
CREATE INDEX IF NOT EXISTS idx_gene_rsid ON variants(gene_id, rsid);
```

---

## Next Steps After Week 2

1. **Week 3-4**: Add patient VCF upload feature
2. **Week 5-6**: Clinical report templates
3. **Week 7-8**: EHR integration
4. **Week 9-10**: HIPAA compliance audit
5. **Week 11-12**: Clinical validation studies

---

## Resources

- **PharmVar**: https://www.pharmvar.org/
- **CPIC Guidelines**: https://cpicpgx.org/guidelines/
- **dbSNP**: https://www.ncbi.nlm.nih.gov/snp/
- **1000 Genomes**: https://www.internationalgenome.org/

---

## Support

Questions? Check:
1. `PRODUCTION_READINESS_ANALYSIS.md` - Strategic overview
2. `docs/GENE_PANEL_EXPANSION_SPEC.md` - Technical details
3. `tests/test_gene_panel_expansion.py` - Working examples
