# DeepVariant Readiness: What You Can Do With Limited Resources

> Practical, low-cost actions to make SynthaTrial "DeepVariant-ready" without GPUs, cloud budget, or significant compute.

**Assumptions:** Laptop or single machine, no GPU cluster, minimal/no cloud spend, limited time (hours, not weeks).

---

## Tier 1: Zero Cost, Zero Compute (Do First)

These require only editing docs and code. No new dependencies, no running heavy tools.

### 1.1 Add "Recommended Variant Callers" to README

**Effort:** 15 minutes

Add a short section to the main README (e.g., near "Data Pipeline" or "VCF Processing"):

```markdown
### Recommended Upstream Variant Callers

SynthaTrial consumes standard VCF files. For best accuracy in pharmacogenes (CYP2D6, CYP2C19, etc.), we recommend:

- **DeepVariant** — CNN-based; excels in difficult regions (CYP2D6, MHC). Supports Illumina, PacBio, Nanopore. [github.com/google/deepvariant](https://github.com/google/deepvariant)
- **GATK HaplotypeCaller** — Industry standard for Illumina WGS.
- **bcftools mpileup** — Lightweight; good for targeted panels.

See [docs/DEEPVARIANT_ANALYSIS.md](docs/DEEPVARIANT_ANALYSIS.md) for compatibility details.
```

**Impact:** Users and collaborators immediately know DeepVariant is supported and preferred.

---

### 1.2 Document VCF Requirements

**Effort:** 30 minutes

Add a small "VCF compatibility" subsection (or expand existing) that states:

- Standard VCF 4.x
- GRCh37 or GRCh38
- GT field (0/0, 0/1, 1/1 or 0|1, 1|0 for phased)
- rsIDs preferred for PharmVar lookup; chr:pos:ref:alt works with annotation
- SVTYPE (DEL/DUP) in INFO for CYP2D6 CNVs

**Impact:** DeepVariant users know exactly what SynthaTrial expects. Reduces support questions.

---

### 1.3 Phased Genotype Handling — Already Done

Your `vcf_processor.py` and callers already treat `0|1` and `0/1` equivalently (e.g., `alt_dosage`, `warfarin_caller`, `allele_caller`). No code change needed.

**Impact:** SynthaTrial is already compatible with phased DeepVariant output.

---

## Tier 2: Minimal Code (No New Dependencies)

### 2.1 PGx Gene Region Filter Script

**Effort:** 1–2 hours

Create `scripts/filter_vcf_to_pgx_regions.py` that:

- Takes a VCF path and output path
- Uses tabix to extract only PGx gene regions (chr1, 2, 6, 10, 12, 16, 22)
- Writes a smaller VCF with just those regions

**Why:** Ultra-rapid pipeline users produce 4M+ variants; filtering to ~30 PGx variants makes SynthaTrial ingestion trivial. Uses existing `tabix` (you already use it in `vcf_processor.py`).

**Impact:** Enables "PGx-only" workflow for critical care or targeted analysis.

---

### 2.2 DeepVariant Docker Command Reference

**Effort:** 30 minutes

Create `docs/DEEPVARIANT_QUICKSTART.md` with:

- The exact Docker command to run DeepVariant (copy from DeepVariant docs)
- How to run on a **single chromosome** (e.g., chr10) for testing: `--regions chr10:96000000-97000000`
- Note: "Full WGS requires several hours and significant RAM; single-chromosome runs are feasible on a laptop."

**Impact:** Users with BAM/CRAM get a copy-paste path. No script execution required from you.

---

## Tier 3: Optional — Single-Chromosome Validation (If You Have Docker + RAM)

**Effort:** 2–4 hours (mostly wait time)
**Requirements:** Docker, ~16 GB RAM, ~10 GB disk

### 3.1 Run DeepVariant on chr10 Only

DeepVariant can be run with `--regions` to limit to one chromosome. Chr10 contains CYP2C19 and CYP2C9 — core PGx genes.

**Steps:**

1. Get a small test BAM (e.g., GIAB sample, chr10 only — ~1–2 GB)
2. Get chr10 reference (FASTA slice or full reference)
3. Run DeepVariant Docker with `--regions chr10`
4. Feed output VCF to SynthaTrial: `python main.py --vcf output.vcf.gz --vcf-chr10 output.vcf.gz --drug-name Warfarin`

**Impact:** Validates end-to-end: DeepVariant VCF → SynthaTrial → PGx report. Proves compatibility for demos and collaboration talks.

**Note:** Full genome DeepVariant is not realistic on a laptop. Chr10-only is the practical limit for "I ran it myself" validation.

---

## Tier 4: Defer (Requires Real Resources)

| Action | Why defer |
|--------|-----------|
| `scripts/run_deepvariant.sh` wrapper | Running DeepVariant needs BAM + reference + hours. Users who have those can run Docker directly. A wrapper adds value only if you offer cloud automation. |
| Sniffles + merge for CYP2D6 CNV | Adds complexity; Sniffles is another tool. Your SVTYPE parsing already works; document that users should merge SV caller output if they need CNVs. |
| AWS Batch / Step Functions integration | Requires AWS setup, Batch queues, significant engineering. |
| Joint validation on GeT-RM | Requires obtaining truth samples, running DeepVariant (compute), and comparison scripts. |

---

## Checklist: "DeepVariant-Ready" With Limited Resources

| Task | Effort | Status |
|------|--------|--------|
| Add "Recommended variant callers" to README | 15 min | [x] |
| Document VCF requirements | 30 min | [x] |
| Create `scripts/filter_vcf_to_pgx_regions.py` | 1–2 hr | [x] |
| Create `docs/DEEPVARIANT_QUICKSTART.md` (Docker commands) | 30 min | [x] |
| (Optional) Run DeepVariant validation script | 2–4 hr | [x] |

**Total realistic effort:** ~3–4 hours for Tier 1 + Tier 2. Tier 3 is optional.

---

## Summary

With limited resources, you can make SynthaTrial "DeepVariant-ready" by:

1. **Documentation** — Recommend DeepVariant, state VCF requirements, provide Docker quickstart.
2. **Small utilities** — PGx region filter for large VCFs.
3. **(Optional)** — Single-chromosome DeepVariant run to validate the pipeline.

You do **not** need to run full DeepVariant, integrate Sniffles, or build cloud automation. The goal is to signal compatibility and give users a clear path. Your existing VCF parser and phased genotype handling already support DeepVariant output.
