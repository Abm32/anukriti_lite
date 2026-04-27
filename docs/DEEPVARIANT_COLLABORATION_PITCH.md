# SynthaTrial: Project Overview for DeepVariant Team Collaboration

> A detailed project description for discussions with the DeepVariant team. Use this document to introduce SynthaTrial, explain our pipeline, and propose collaboration opportunities.

---

## 1. Who We Are: SynthaTrial (Anukriti)

**SynthaTrial** (also known as **Anukriti**) is an open-source pharmacogenomics platform that democratizes personalized medicine by predicting drug responses from genetic data. We combine **deterministic CPIC/PharmVar-based allele calling** with **LLM-powered clinical explanation** to deliver actionable pharmacogenomics insights to healthcare providers, researchers, and clinics worldwide.

**Mission:** "Every preventable adverse drug reaction is one too many. Let's make personalized medicine the standard of care."

**Repository:** [github.com/Abm32/Synthatrial](https://github.com/Abm32/Synthatrial)  
**License:** MIT  
**Status:** Beta (v0.4), AWS AI Competition Finalist

---

## 2. The Problem We Solve

### Global Healthcare Crisis

- **2 million Americans** experience serious adverse drug reactions annually; **100,000 die**. Most are preventable with pharmacogenomics.
- **$30B+** in annual healthcare costs from preventable reactions.
- Rural clinics and underserved populations lack access to expensive lab-based PGx testing.
- Proprietary databases and vendor lock-in limit research and innovation.

### The Gap

Pharmacogenomics (PGx) is proven—CPIC guidelines exist for many gene-drug pairs. But the barrier is **accessibility**: expensive lab tests, complex workflows, and fragmented tools. We bridge that gap by making PGx analysis **open, reproducible, and cloud-native**.

---

## 3. What We Do: Technical Overview

### Core Capability

**Input:** A drug (name or SMILES) + a patient's genetics (manual phenotype or **VCF file)**  
**Output:** Drug response prediction, metabolizer phenotype, risk level, and clinical recommendations in natural language + PDF report

### Our Pipeline (Downstream of Variant Calling)

```
VCF Input (pre-called variants)
    │
    ├── Parse VCF (GRCh37 or GRCh38)
    ├── Extract variants in PGx gene regions (chr1, 2, 6, 10, 12, 16, 22)
    ├── Lookup rsIDs → PharmVar star alleles (*1, *2, *3, *17, etc.)
    ├── Map diplotypes → CPIC phenotypes (Poor/Intermediate/Extensive Metabolizer)
    ├── Drug-triggered PGx (only show genes relevant to the prescribed drug)
    ├── Generate patient profile
    └── LLM explains (Gemini/Claude) — risk, interpretation, citations
```

**Key point:** We consume **VCF files** — we do not perform variant calling. We assume someone has already run a variant caller (e.g., GATK, bcftools, or **DeepVariant**) on aligned sequencing data.

---

## 4. Our 9-Gene Pharmacogenomics Panel

We cover **9 pharmacogenes** across 8 chromosomes, with CPIC-style drug-gene triggers:

| Gene | Chromosome | Key Drugs | Key Variants |
|------|------------|-----------|--------------|
| **CYP2D6** | chr22 | Codeine, tamoxifen, SSRIs | *1, *4, *5, *10, *41, CNVs |
| **CYP2C19** | chr10 | Clopidogrel, PPIs | *1, *2, *3, *17 |
| **CYP2C9** | chr10 | Warfarin, NSAIDs | *1, *2, *3 |
| **VKORC1** | chr16 | Warfarin | rs9923231 |
| **SLCO1B1** | chr12 | Statins (simvastatin, atorvastatin) | rs4149056 |
| **UGT1A1** | chr2 | Irinotecan | *1, *6, *28, *36 |
| **TPMT** | chr6 | Azathioprine, mercaptopurine | *1, *2, *3A, *3B, *3C |
| **DPYD** | chr1 | 5-FU, capecitabine | *2A, *13, HapB3 |
| **HLA-B*57:01** | chr6 | Abacavir (proxy rs2395029) | Safety flag |

**Drug-triggered display:** Only drug-relevant genes are shown (e.g., Warfarin → CYP2C9 + VKORC1; Statins → SLCO1B1).

---

## 5. Architecture: Hybrid Deterministic + LLM

We follow a strict design principle:

> **The deterministic layer is the source of truth. The LLM explains, not decides.**

- **Deterministic:** PharmVar allele definitions (TSV) + CPIC phenotype tables (JSON). Same VCF → same diplotype/phenotype. Auditable, reproducible.
- **LLM:** Natural language explanation, risk communication, citations. No LLM output affects clinical calls.
- **No "GPT wrapper":** We differ from generic AI projects by keeping clinical accuracy in curated tables.

---

## 6. Infrastructure & Scale

- **Cloud-native:** AWS S3 (VCF storage), Lambda (batch processing), Step Functions (workflow orchestration), Bedrock (LLM).
- **Population simulation:** 10,000+ patient cohorts in ~10 minutes; 377,000+ patients/minute throughput.
- **Global diversity:** African, European, East Asian, South Asian, Admixed populations (1000 Genomes, gnomAD).
- **API:** REST endpoints (`/analyze`, `/vcf/patient-profile`, `/simulate`), Streamlit UI, CLI.

---

## 7. Where SynthaTrial Sits Relative to DeepVariant

**DeepVariant:** Raw sequencing reads (BAM/CRAM) + reference → **VCF**  
**SynthaTrial:** **VCF** → Pharmacogenomics interpretation (allele calling, phenotype, drug recommendations)

We are **complementary** — DeepVariant produces what we consume. We do not overlap; we are natural pipeline partners.

```
[Sequencing] → [Alignment] → [DeepVariant] → [VCF] → [SynthaTrial] → [PGx Report]
```

---

## 8. Why Collaborate with DeepVariant?

### For SynthaTrial

1. **End-to-end pipeline:** Users with BAM/CRAM (WGS, targeted panels) could run DeepVariant → SynthaTrial → PGx report in one workflow.
2. **Higher quality:** DeepVariant's accuracy (especially for indels and difficult regions) improves our allele calling quality for genes like CYP2D6 and CYP2C19.
3. **New sequencing tech:** DeepVariant supports Illumina, PacBio HiFi, Oxford Nanopore. We could accept VCFs from long-read or hybrid workflows.
4. **CYP2D6 CNVs:** We already parse SVTYPE (DEL/DUP) in VCF INFO for CYP2D6. DeepVariant's structural variant calling could improve our CNV coverage.

### For DeepVariant

1. **Downstream use case:** SynthaTrial is a concrete, clinically relevant application of DeepVariant output.
2. **Validation:** PGx genes have well-established truth sets (GeT-RM, PharmVar). We could validate DeepVariant output on these regions.
3. **Visibility:** Joint documentation or a reference pipeline could help both communities reach clinical labs and researchers.

---

## 9. Proposed Collaboration Formats

### Option A: Documentation & Cross-Linking (Low Effort)

- SynthaTrial documents DeepVariant as a recommended upstream variant caller.
- DeepVariant docs or blog could mention SynthaTrial as a downstream PGx application.
- No code changes.

### Option B: Reference Pipeline Script (Medium Effort)

- A script or small workflow that: `BAM/CRAM + FASTA → DeepVariant (Docker) → VCF → SynthaTrial`.
- Hosted in either repo or a shared "PGx pipeline" example.
- Enables users with raw sequencing data to go end-to-end.

### Option C: Joint Validation (Research)

- Run DeepVariant on GeT-RM or PharmVar truth-set samples.
- Compare DeepVariant VCF → SynthaTrial PGx calls vs. reference genotypes.
- Publish joint validation or benchmarking results.

### Option D: Cloud Integration (Longer Term)

- Integrate DeepVariant into AWS Step Functions (e.g., via AWS Batch).
- Flow: S3 BAM → DeepVariant → S3 VCF → SynthaTrial → PGx report.
- Enables clinical labs and research centers to run the full pipeline in the cloud.

---

## 10. Technical Compatibility

| Requirement | DeepVariant Output | SynthaTrial Expectation |
|-------------|--------------------|-------------------------|
| Format | VCF 4.x | VCF 4.x ✓ |
| Reference | GRCh37 / GRCh38 | Both supported ✓ |
| Genotypes | GT (0/0, 0/1, 1/1) | Same ✓ |
| rsIDs | Optional (dbSNP) | Preferred for PharmVar lookup; chr:pos:ref:alt works with annotation |
| Structural variants | SVTYPE in INFO | Supported (`_parse_svtype`, CYP2D6 CNV) ✓ |

---

## 11. Contact & Next Steps

We are open to collaboration in any of the formats above. We can:

- Add DeepVariant to our docs as a recommended variant caller.
- Create a reference pipeline script.
- Participate in joint validation or benchmarking.
- Discuss cloud integration or joint documentation.

**Suggested next steps:**

1. Brief sync call to align on scope and priorities.
2. Decide on a starting point (e.g., Option A or B).
3. Iterate on documentation or shared artifacts.

---

## 12. Quick Links

- **SynthaTrial GitHub:** [github.com/Abm32/Synthatrial](https://github.com/Abm32/Synthatrial)
- **Live Demo:** [anukriti-ai-competition.onrender.com](https://anukriti-ai-competition.onrender.com)
- **API Docs:** [anukritibackend.abhimanyurb.com/docs](https://anukritibackend.abhimanyurb.com/docs)
- **DeepVariant Analysis (internal):** [docs/DEEPVARIANT_ANALYSIS.md](DEEPVARIANT_ANALYSIS.md)

---

*Built for global healthcare equity. Open source. Open science.*
