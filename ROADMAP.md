# Project Anukriti / SynthaTrial — Roadmap & Research Guide

> Strategic next steps and research sources for advancing the pharmacogenomics platform.

**Last Updated:** March 2026

---

## Part 1: Next Steps (Prioritized)

### 1.1 Technical — Allele & Gene Coverage

| Priority | Area | Description | Status |
|----------|------|-------------|--------|
| **High** | CYP2D6 CNVs | Add copy-number/structural variant handling (star-5 deletion, xN duplications). | Planned |
| **High** | Multi-variant haplotypes | Extend beyond single-variant defining alleles to phased haplotypes for CYP2C19, CYP2C9. | Planned |
| ~~Medium~~ | ~~Gene panel: TPMT~~ | ~~Add TPMT (chr6) for thiopurines.~~ | **DONE** — `src/tpmt_caller.py`, data files, tests |
| ~~Medium~~ | ~~Gene panel: DPYD~~ | ~~Add DPYD (chr1) for fluoropyrimidines.~~ | **DONE** — `src/dpyd_caller.py`, data files, tests |
| **Medium** | Gene panel: G6PD | Add G6PD (chrX) for rasburicase, primaquine. | Planned |
| ~~Medium~~ | ~~CSV batch pipeline~~ | ~~Implement Batch Mode CSV upload → per-patient analysis.~~ | **DONE** — functional in Streamlit UI |
| **Medium** | HLA-B typing | Add HLA-B*57:01 (chr6) for abacavir hypersensitivity. | Planned |
| **Medium** | CYP3A4 | Add CYP3A4 (chr7) — metabolizes ~50% of drugs. | Planned |

### 1.2 Product — Clinical Relevance

| Priority | Area | Description | Effort |
|----------|------|-------------|--------|
| **High** | VCF in Simulation Lab | Allow users to upload VCF or select S3 VCF in the UI instead of manual phenotype entry only. | 1–2 weeks |
| **Medium** | Population-specific risk | Add ancestry-aware risk stratification (AFR, EAS, SAS vs EUR). | 2–3 weeks |
| **Medium** | Clinical trial matching | Integrate ClinicalTrials.gov or similar API for trial eligibility based on PGx profile. | 2–4 weeks |
| **Low** | EHR integration | Design EHR-compatible API for clinical workflow integration. | 4+ weeks |

### 1.3 Infrastructure

| Priority | Area | Description | Effort |
|----------|------|-------------|--------|
| **Medium** | AWS setup automation | CloudFormation/Terraform scripts for S3, Lambda, Step Functions provisioning. | 1–2 weeks |
| **Low** | Cost monitoring | CloudWatch dashboards, budget alerts, cost breakdown by service. | 1 week |

---

## Part 2: Research Sources

### 2.1 Pharmacogenomics Guidelines & Data

| Source | URL | Use For |
|--------|-----|---------|
| **CPIC** | [cpicpgx.org](https://cpicpgx.org) | Gene–drug guidelines, implementation levels, dosing recommendations |
| **PharmVar** | [pharmvar.org](https://pharmvar.org) | Allele definitions, nomenclature, CNV/structural variant info |
| **PharmGKB** | [pharmgkb.org](https://pharmgkb.org) | Gene–drug interactions, clinical annotations, level of evidence |
| **ClinVar** | [ncbi.nlm.nih.gov/clinvar](https://www.ncbi.nlm.nih.gov/clinvar/) | Pathogenic/likely pathogenic variant classifications |
| **dbSNP** | [ncbi.nlm.nih.gov/snp](https://www.ncbi.nlm.nih.gov/snp/) | rsIDs, allele frequencies by population |

### 2.2 CYP2D6 CNVs (Critical Gap)

| Source | Focus |
|--------|--------|
| **PharmVar CYP2D6** | CNV definitions, star-5 deletion, xN duplications, structural variants |
| **Gaedigk et al.** | CYP2D6 CNV calling methodology, allele assignment algorithms |
| **CPIC Codeine Guideline** | CYP2D6 phenotype → dosing recommendations, ultra-rapid/poor metabolizer handling |
| **PharmCAT** (open source) | Reference implementation for CPIC-based PGx; CNV handling patterns |

### 2.3 Population Diversity

| Source | Focus |
|--------|--------|
| **1000 Genomes** | AFR, EUR, EAS, SAS, AMR allele frequencies; already used for VCF data |
| **gnomAD** | Population-specific allele frequencies, constraint scores |
| **HGDP** | Human Genome Diversity Project; underrepresented populations |

### 2.4 Clinical Trials

| Source | Focus |
|--------|--------|
| **ClinicalTrials.gov** | [clinicaltrials.gov](https://clinicaltrials.gov) — Trial eligibility, inclusion/exclusion, PGx criteria |
| **EU Clinical Trials Register** | [clinicaltrialsregister.eu](https://www.clinicaltrialsregister.eu) — European trials |

### 2.5 Communities & Standards

| Source | Focus |
|--------|--------|
| **GA4GH** | Global Alliance for Genomics and Health — Standards, data sharing |
| **PGRN** | Pharmacogenomics Research Network — Research, implementation |
| **CPIC GitHub / Mailing List** | Implementation questions, edge cases, guideline updates |

### 2.6 Technical Implementation

| Source | Focus |
|--------|--------|
| **pysam / htslib** | VCF parsing, CNV detection, structural variant handling |
| **bcftools** | CNV calling, haplotype phasing, variant normalization |
| **PharmCAT** | [github.com/PharmGKB/PharmCAT](https://github.com/PharmGKB/PharmCAT) — CPIC implementation reference |

---

## Part 3: Suggested Research Sequence

### Phase 1: CYP2D6 CNVs (2–3 weeks)

1. Read PharmVar CYP2D6 allele definitions and CNV nomenclature.
2. Study PharmCAT’s CYP2D6 CNV handling (source code).
3. Review Gaedigk et al. papers on CYP2D6 copy-number calling.
4. Implement CNV detection (e.g., exon coverage, *5/*XN logic) in `src/allele_caller.py` or new module.

### Phase 2: TPMT / DPYD / G6PD (2–4 weeks)

1. CPIC guidelines for TPMT (thiopurines), DPYD (fluoropyrimidines), G6PD (rasburicase, etc.).
2. PharmVar allele tables for each gene.
3. Map chr6 (TPMT), chr1 (DPYD), chrX (G6PD) variants to existing or new VCF chromosomes.
4. Add phenotype callers following existing CYP2C19/Warfarin pattern.

### Phase 3: Population Stratification (1–2 weeks)

1. Extract population-specific allele frequencies from gnomAD or 1000 Genomes.
2. Add ancestry field to patient profile (AFR, EUR, EAS, SAS, AMR).
3. Adjust risk/confidence based on population representation in evidence.

### Phase 4: Clinical Trial Matching (2–4 weeks)

1. Explore ClinicalTrials.gov API and data model.
2. Define PGx-related eligibility criteria mapping.
3. Build trial-matching endpoint or UI section.

---

## Part 4: Quick Reference — Key Files

| Component | Location |
|-----------|----------|
| Allele calling | `src/allele_caller.py` |
| Warfarin caller | `src/warfarin_caller.py` |
| SLCO1B1 caller | `src/slco1b1_caller.py` |
| TPMT caller | `src/tpmt_caller.py` |
| DPYD caller | `src/dpyd_caller.py` |
| VCF processing | `src/vcf_processor.py` |
| Drug–gene triggers | `src/pgx_triggers.py` |
| CPIC/PharmVar data | `data/pgx/` |
| Population simulator | `src/population_simulator.py` |

---

## Part 5: Current Limitations (from docs)

- **Single-variant alleles only** — Multi-variant haplotypes and CNVs are future work.
- **No CYP2D6 CNVs** — star-5 deletion, xN duplications not yet supported.
- **Manual profiles in UI** — VCF-based profiles used via CLI/API; UI uses manual phenotype entry.
- **TPMT/DPYD VCF** — Callers implemented but require chr6/chr1 VCF files for VCF-based calling.
- **G6PD, HLA-B, CYP3A4** — Not yet implemented; planned for future phases.

---

## Links

- **Live Demo:** [anukriti.abhimanyurb.com](https://anukriti.abhimanyurb.com)
- **API Docs:** [anukritibackend.abhimanyurb.com/docs](https://anukritibackend.abhimanyurb.com/docs)
- **GitHub:** [github.com/Abm32/Synthatrial](https://github.com/Abm32/Synthatrial)
