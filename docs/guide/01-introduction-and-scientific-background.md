# Chapter 1: Introduction & Scientific Background

## 1.1 The Drug Development Problem

Over 90% of drug candidates fail in clinical trials, costing the pharmaceutical industry
billions annually. A significant contributor to this failure rate is the **genetic blind spot** —
the inability to predict how individual patients will metabolize and respond to drugs based
on their genetic makeup.

Pharmacogenomics (PGx) addresses this by studying how genetic variants in drug-metabolizing
enzymes, transporters, and targets influence drug efficacy and toxicity.

### Real-World Impact

Consider these clinical scenarios that motivate the platform:

- **DPYD deficiency + 5-Fluorouracil**: A patient with DPYD *1/*2A (Intermediate Metabolizer)
  receives standard-dose 5-FU for colorectal cancer. Without PGx testing, they face a 50%+ risk
  of severe, potentially fatal toxicity. CPIC recommends 50% dose reduction.

- **CYP2D6 Ultra-Rapid Metabolizer + Codeine**: A patient converts codeine to morphine at
  dangerously high rates, risking respiratory depression. Multiple pediatric deaths have been
  documented (Gasche et al., 2004).

- **CYP2C19 Poor Metabolizer + Clopidogrel**: A patient with *2/*2 cannot activate the
  antiplatelet drug, leading to stent thrombosis. CPIC recommends alternative agents like
  prasugrel or ticagrelor.

## 1.2 Why In Silico Trials?

Traditional clinical trials require thousands of participants, years of time, and hundreds of
millions of dollars. In silico pharmacogenomics offers:

1. **Pre-screening**: Identify at-risk populations before enrollment
2. **Dose optimization**: Predict optimal dosing by genotype
3. **Safety signal detection**: Model adverse drug reactions across diverse ancestries
4. **Cost reduction**: Reduce Phase I/II failure rates through virtual cohorts

## 1.3 The Pharmacogenomics Landscape

### CPIC (Clinical Pharmacogenetics Implementation Consortium)

CPIC provides evidence-based guidelines mapping gene/drug pairs to clinical recommendations.
Each guideline is assigned an evidence level:

| Level | Meaning | Example |
|-------|---------|---------|
| A | Strong evidence, actionable | CYP2C19 + clopidogrel |
| A/B | Strong-to-moderate evidence | CYP2D6 + codeine |
| B | Moderate evidence | UGT1A1 + irinotecan |

Anukriti focuses on **CPIC Level A** gene-drug pairs for maximum clinical relevance.

### Existing Tools

| Tool | Approach | Strengths | Limitations |
|------|----------|-----------|-------------|
| **PharmCAT** | Rule-based, CPIC-curated | Gold standard, clinically validated | GRCh38 only, no LLM explanation |
| **Aldy** | Computational, SV-aware | Best CYP2D6 CNV calling | Limited gene coverage |
| **Stargazer** | Statistical genotyper | Good for WGS data | No clinical recommendations |

### Where Anukriti Fits

Anukriti combines **deterministic CPIC/PharmVar-based calling** (matching PharmCAT's accuracy)
with **LLM-powered explanation** (Gemini/Claude) to provide:

- Reproducible, auditable allele calling (no LLM hallucination risk in calling)
- Natural language clinical explanations (LLM explains, not decides)
- Population-scale simulation capability
- Cloud-native scalability via AWS

## 1.4 The 8-Gene Panel

Anukriti covers 8 pharmacogenes across 4 functional categories:

### Phase I Metabolism (CYP450 Enzymes)
| Gene | Chromosome | Key Drugs | Key Alleles |
|------|------------|-----------|-------------|
| CYP2D6 | chr22 | Codeine, tamoxifen, SSRIs | *1, *4, *5, *10, *41 |
| CYP2C19 | chr10 | Clopidogrel, PPIs, voriconazole | *1, *2, *3, *17 |
| CYP2C9 | chr10 | Warfarin, NSAIDs, phenytoin | *1, *2, *3 |

### Phase II Metabolism (Conjugation Enzymes)
| Gene | Chromosome | Key Drugs | Key Alleles |
|------|------------|-----------|-------------|
| UGT1A1 | chr2 | Irinotecan, atazanavir | *1, *6, *28, *36, *37 |
| TPMT | chr6 | Azathioprine, mercaptopurine | *1, *2, *3A, *3B, *3C |
| DPYD | chr1 | 5-FU, capecitabine | *1, *2A, *13, HapB3 |

> **Note**: DPYD (chr1) is supported in the allele caller and data tables but chr1 VCF is not in the standard 8-chromosome download set. TPMT (chr6) VCF is downloadable but genes are not yet mapped in the VCF processor. Both callers work with manual variant input.

### Drug Targets
| Gene | Chromosome | Key Drugs | Key Variants |
|------|------------|-----------|--------------|
| VKORC1 | chr16 | Warfarin | rs9923231 (G>A) |

### Drug Transporters
| Gene | Chromosome | Key Drugs | Key Variants |
|------|------------|-----------|--------------|
| SLCO1B1 | chr12 | Statins (simvastatin, atorvastatin) | rs4149056 (T>C) |

## 1.5 Project Goals

1. **100% concordance** with GeT-RM consensus genotypes across all 8 genes
2. **Publication-quality validation** with 2,253 patients (GeT-RM + synthetic + clinical)
3. **Clinical transparency** — deterministic calling with LLM explanation, not prediction
4. **Population equity** — validated across 5 global ancestries (AFR, EUR, EAS, SAS, AMR)
5. **Production readiness** — Docker, AWS, CI/CD, security scanning

## 1.6 Key References

1. Relling & Klein (2011). CPIC: Clinical Pharmacogenetics Implementation Consortium. *Clin Pharmacol Ther*.
2. Sangkuhl et al. (2020). PharmVar and CPIC. *Clin Pharmacol Ther*.
3. Pratt et al. (2016). Recommendations for GeT-RM program. *Clin Pharmacol Ther*.
4. Halman et al. (2024). Multi-tool PGx comparison. *PMC11315677*.
5. Gaedigk et al. (2019). PharmVar: Pharmacogene Variation Consortium. *Clin Pharmacol Ther*.

---

**Next**: [Chapter 2 — Architecture Overview](02-architecture-overview.md)
