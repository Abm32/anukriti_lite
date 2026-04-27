# PGx Data Sources (Versioned)

SynthaTrial uses **one-time curated tables** (versioned in the repo), not live APIs, for star-allele calling. This keeps results reproducible and avoids dependency on external services at runtime.

---

## Data provenance (this repo)

Record source, download date, and version when you add or refresh files. Update this section and the table below when you pull new data.

### CYP2C19 Alleles

- **Source:** PharmVar CYP2C19 allele definitions (curated downloads)
- **File:** `pharmvar/cyp2c19_alleles.tsv`
- **Content:** Minimal clinically relevant set (*2, *3, *17); *1 is default (no row).
- **Downloaded:** 2026-02-15 (initial)
- **Version:** PharmVar-based minimal set (no PharmVar release version tagged; update when refreshed from https://www.pharmvar.org/download )

### CYP2C19 Phenotype Translation

- **Source:** CPIC CYP2C19 guideline supplement (genotype–phenotype tables)
- **File:** `cpic/cyp2c19_phenotypes.json`
- **Content:** Diplotype → phenotype label (e.g. *1/*2 → Intermediate Metabolizer).
- **Version:** CPIC guideline–aligned (update to e.g. “CPIC 2023 update” when refreshed from https://cpicpgx.org/guidelines/ )

### CYP2C9 Alleles (Warfarin)

- **Source:** PharmVar CYP2C9 allele definitions (curated downloads)
- **File:** `pharmvar/cyp2c9_alleles.tsv`
- **Content:** Minimal clinically relevant set (*2, *3); *1 is default.
- **Downloaded:** 2026-02-15 (initial)

### VKORC1 Variants (Warfarin)

- **Source:** CPIC/PharmVar warfarin guideline (rs9923231 -1639G>A)
- **File:** `pharmvar/vkorc1_variants.tsv`
- **Content:** rs9923231 risk allele A → increased sensitivity (lower dose).
- **Downloaded:** 2026-02-15 (initial)

### Warfarin Response (CYP2C9 + VKORC1)

- **Source:** CPIC-style warfarin dose sensitivity (genotype → recommendation)
- **File:** `cpic/warfarin_response.json`
- **Content:** CYP2C9 diplotype + VKORC1 genotype (GG/GA/AA) → dose recommendation.
- **Version:** Simplified MVP; consult CPIC warfarin guideline for full tables.

---

## Why no single “PGx API”?

Pharmacogenomics data is openly available but **fragmented**:

| Source        | What it provides              | API?                    | How we use it                          |
|---------------|-------------------------------|-------------------------|----------------------------------------|
| **PharmVar**  | Star-allele definitions       | Curated downloads (no stable REST API) | Downloaded, converted to TSV in `pharmvar/` |
| **CPIC**      | Diplotype → phenotype, guidelines | Guideline PDFs and tables (downloadable); no full allele-calling API | Curated JSON in `cpic/`                |
| **PharmGKB**  | Drug–gene annotations         | API (may need registration) | Reference only                        |
| **Ensembl**   | rsID → position, consequences | Open REST API           | Optional variant metadata              |
| **dbSNP**     | Variant definitions           | NCBI API                | Optional verification                  |

**Best practice:** Download or export curated tables once, document version and date, and ship them in `data/pgx/`. Do not call external APIs during allele calling.

---

## PharmVar (allele definitions)

- **Site:** https://www.pharmvar.org/
- **Downloads:** https://www.pharmvar.org/download — curated allele definition files (TSV, VCF, FASTA per gene). PharmVar does not provide a stable public REST API; we download and convert to our TSV format.

Our format: `pharmvar/<gene>_alleles.tsv` with columns `allele`, `rsid`, `alt`, `function`. *1 is default (no row). Source and version should be recorded below when you refresh.

---

## CPIC (phenotype translation)

- **Guidelines:** https://cpicpgx.org/guidelines/ — guideline PDFs and phenotype translation tables (downloadable).
- **Files:** https://files.cpicpgx.org/data/report/current/ (e.g. allele summary, gene-specific tables). CPIC does not provide an official API for star-allele definitions; their JSON resources are limited and not designed for automated allele calling. We use one-time downloaded/curated tables.

Our format: `cpic/<gene>_phenotypes.json` — diplotype string → phenotype label (e.g. `"*1/*2"` → `"Intermediate Metabolizer"`). Document CPIC guideline version and date when you refresh.

---

## Ensembl (variant metadata)

- **REST API:** https://rest.ensembl.org/
- Example: `GET https://rest.ensembl.org/variation/human/rs4244285?content-type=application/json` for chromosome, position, alleles. Useful for validating rsIDs or building region-based pipelines; not required for the curated TSV/JSON in this repo.

---

## NCBI dbSNP

- **API:** https://api.ncbi.nlm.nih.gov/variation/v0/beta/refsnp/<id> (e.g. 4244285 for rs4244285). Useful for verifying alleles; not required for curated tables.

---

## Versioning table

When you update `pharmvar/` or `cpic/` files, update the provenance section above and this table:

| Data set      | Source / version | Date updated |
|---------------|------------------|--------------|
| cyp2c19_alleles.tsv | PharmVar CYP2C19 (minimal set) | 2026-02-15 |
| cyp2c19_phenotypes.json | CPIC CYP2C19 guideline (phenotype translation) | 2026-02-15 |
| cyp2c9_alleles.tsv | PharmVar CYP2C9 (minimal set *2, *3) | 2026-02-15 |
| vkorc1_variants.tsv | CPIC/PharmVar rs9923231 | 2026-02-15 |
| warfarin_response.json | CPIC-style Warfarin dose table | 2026-02-15 |

Run `python scripts/update_pgx_data.py --validate` to check existing files. Use `scripts/update_pgx_data.py` (and its `--help`) to refresh from upstream when needed; then update provenance, this table, and commit.
