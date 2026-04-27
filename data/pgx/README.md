# PGx curated data (PharmVar / CPIC)

Research-grade allele definitions and phenotype translations. Not for clinical use.

- **pharmvar/** — Allele definitions (allele, rsid, alt, function) and variant tables (e.g. VKORC1: variant, rsid, risk_allele, effect). Source: PharmVar. *1 is the default when no variant is detected (no row required).
- **cpic/** — Diplotype → phenotype (CPIC guideline labels) and drug-specific tables (e.g. **warfarin_response.json**: CYP2C9 diplotype + VKORC1 genotype → dose recommendation).

**Genes covered:** CYP2C19 (alleles + phenotypes), CYP2C9 (alleles), VKORC1 (rs9923231), SLCO1B1 (rs4149056). **Warfarin** uses CYP2C9 + VKORC1 and `data/pgx/cpic/warfarin_response.json`; caller: `src/warfarin_caller.py`. **SLCO1B1** (statin myopathy) uses `data/pgx/cpic/slco1b1_phenotypes.json`; caller: `src/slco1b1_caller.py`. Which genes and PGx lines appear in the patient genetics summary is **drug-triggered** via `src/pgx_triggers.py` (Warfarin → CYP2C9 + VKORC1; Statins → SLCO1B1; Clopidogrel → CYP2C19).

When these files exist, SynthaTrial uses them for deterministic allele calling and phenotype/recommendation lookup. Use `interpret_cyp2c19(patient_variants)` for simple rsid→alt input; for Warfarin use `interpret_warfarin(patient_variants)` or `interpret_warfarin_from_vcf(variant_map)` from VCF. Coverage is incomplete (e.g. no CNVs for CYP2D6); see root README disclaimers.

**Sources and updates:** See `sources.md` for PharmVar, CPIC, Ensembl, dbSNP and versioning. Validate with `python scripts/update_pgx_data.py --validate` (supports both allele TSVs and variant TSVs). Use the same script (and `--gene`, `--fetch`) to refresh from open sources when needed.
