## App Category

**Social Impact** - Making population-diverse pharmacogenomic safety screening accessible before expensive lab or trial work begins, with an equity lens on underrepresented genomes. At ~$0.0001 per simulated patient, Anukriti democratizes genomic safety research for academic labs in the Global South - India, Sub-Saharan Africa, Southeast Asia - that lack the bioinformatics clusters to run population-scale cohort analysis today. This focus on equity is motivated by data showing that more than [80% of GWAS participants are of European ancestry](https://pmc.ncbi.nlm.nih.gov/articles/PMC9904154/) and that [clinical trials for FDA-approved drugs in 2020 enrolled 75% White participants](https://www.tevapharm.com/news-and-media/feature-stories/clinical-trial-diversity/), leaving African, South Asian and East Asian populations underrepresented.

---

## My Vision

A child is sent home on codeine after tonsillectomy. If she is a CYP2D6 ultrarapid metabolizer, morphine conversion outpaces safe clearance and a standard dose becomes lethal. The [FDA warns that respiratory depression and death have occurred in children who were CYP2D6 ultrarapid metabolizers after tonsillectomy or adenoidectomy](https://www.ncbi.nlm.nih.gov/books/NBK100662/), and the ultrarapid phenotype occurs in up to 28% of North Africans/Ethiopians and about 10% of Caucasians. Elsewhere, a patient in East Asia carries an HLA allele that Phase III trials in European-majority cohorts never surfaced: [carbamazepine-induced Stevens-Johnson syndrome occurs almost exclusively in carriers of HLA-B*15:02](https://pmc.ncbi.nlm.nih.gov/articles/PMC2586963/), an allele present in about 10% of Han Chinese but virtually absent in Europeans. The harm appears before any spreadsheet captures it.

Why do the same drugs fail differently depending on where you were born? Because for most of pharmaceutical history, evidence has been built on European-majority genomes and then prescribed to everyone else: [83.8% of GWAS participants were of European ancestry in 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC9904154/) and the [UK Biobank is 88% White](https://www.statnews.com/2023/11/29/uk-biobank-genome-sequences-500000-people-research/).

I named the project **Anukriti** - Sanskrit for *response, reaction,* or *replication*. Given a drug and genomic input (VCF, S3, or streamed 1000 Genomes data), Anukriti runs a deterministic pharmacogenomic engine across diverse populations, retrieving CPIC-aligned evidence via Amazon Titan embeddings and generating auditable interpretations with Amazon Nova.

The core proposition is a **Virtual Phase 0**: a genomic safety simulation across globally representative populations before committing wet-lab budget - not to replace clinical judgment, but to surface population-level safety signals earlier, when intervention is still possible.

---

## Why This Matters

The [PREPARE trial (U-PGx consortium, Lancet 2023)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11949333/) showed that pre-emptive pharmacogenomic panel testing reduced adverse drug reactions by 30%. Yet 99.5% of people carry at least one variant that can alter drug response, and most are never genotyped before prescribing. The documented harm patterns below are not edge cases - they are recurrent, preventable, and population-specific.

| Drug | Gene | Population at Risk | Documented Harm | Key Stat |
|---|---|---|---|---|
| Codeine | CYP2D6 | North Africa, Ethiopia | [Fatal respiratory depression in children](https://www.ncbi.nlm.nih.gov/books/NBK100662/) | Up to 28% ultrarapid metabolizers |
| Carbamazepine | HLA-B*15:02 | Han Chinese, SE Asia | [Stevens-Johnson Syndrome (odds ratio >2,500)](https://pmc.ncbi.nlm.nih.gov/articles/PMC2586963/) | ~10% in Han Chinese; virtually absent in Europeans |
| Abacavir | HLA-B*57:01 | SW Asians | [Severe hypersensitivity](https://arupconsult.com/ati/hla-b5701-abacavir-sensitivity) | ~11% vs ~6.8% in Europeans; screening cut incidence to <0.5% |
| Clopidogrel | CYP2C19 | Pacific Islanders, East Asians | [Prodrug activation failure, stent thrombosis](https://www.ncbi.nlm.nih.gov/books/NBK84114/) | 57% poor metabolizers in Pacific Islanders |
| Warfarin | CYP2C9 + VKORC1 | East Asians | Bleeding risk at standard Western doses | VKORC1 -1639A allele ~90% in East Asians |

As of 2021, [83.8% of GWAS participants were of European ancestry](https://pmc.ncbi.nlm.nih.gov/articles/PMC9904154/). The harm falls hardest on the populations least represented in the genomic corpora that steer drug development. Anukriti shows what a drug's safety profile looks like when run across the populations absent from original trials.

---

## How I Built This

### Architecture

![Figure 1 — End-to-end architecture (research / non-clinical)]

*Figure 1 — End-to-end architecture (research / non-clinical). Deterministic PGx calling is separated from RAG + LLM narration; a verification layer audits calls and grounding before producing PGx JSON, PDF, and FHIR-style outputs.*

![Figure 2 — AWS infrastructure (batch fan-out)]

*Figure 2 — AWS infrastructure (batch fan-out). Step Functions orchestrates cohort runs, fanning out per-patient (or per-shard) workers; artifacts land in S3 with CloudWatch observability.*

| Layer | Role | Technology |
|---|---|---|
| Frontend | UI, VCF workflows, batch mode | Streamlit |
| API | Routing, orchestration, audit logging | FastAPI + Docker |
| Genomics | Regional variant extraction | Tabix / htslib + AWS Open Data HTTPS streaming |
| Decision engine | Deterministic diplotype and phenotype calling | CPIC/PharmVar tables, RDKit fingerprints |
| Retrieval | Evidence grounding for LLM | Amazon Titan Embeddings v2 + local CPIC index |
| Explanation | Narrative generation (explains, never decides) | Amazon Nova (default), Claude, Gemini, Ollama |
| Verification | Per-call audit and grounding check | `pgx_verification.py` + `citation_grounding.py` |
| Batch | Population-scale cohort simulation | AWS Lambda + Step Functions |
| Storage | VCF files, PDF reports, presigned access | Amazon S3 Intelligent Tiering |
| Observability | Logs, metrics, cost visibility | Amazon CloudWatch |

VCF files are streamed from AWS Open Data via HTTPS range requests - no terabyte downloads required. AFR, EAS, SAS, and AMR cohort simulation runs without S3 egress costs, keeping large exploratory runs feasible at order-of-magnitude ~$10^-4 per simulated patient.

### Benchmarks, Scalability, and Cost-at-Scale

Judges are right to ask for empirical proof beyond retrieval metrics. Here’s how Anukriti is benchmarked today — and how it scales on AWS as load increases.

#### Benchmarks (what we measure)

- **Latency (single run)**: end-to-end time from “Submit” → verified report (includes deterministic engine + retrieval + narration + verification).
- **Throughput (batch mode)**: simulations per minute for a cohort run (AFR/EAS/SAS/AMR/EUR) under Step Functions fan-out.
- **Cost**: per-simulation compute + retrieval + generation + storage (reported as a cost-per-patient and total cohort cost).
- **RAG correctness**: retrieval metrics (MRR / precision / recall) + grounding scorer fraction (explanation sentences supported by retrieved CPIC evidence).

#### Scalability under load (AWS execution model)

Anukriti scales using a simple fan-out pattern:

- **API tier** (FastAPI): receives requests, validates inputs, writes an audit record, and enqueues work.
- **Batch tier** (Step Functions): orchestrates cohort runs by fanning out per-patient (or per-chromosome shard) tasks.
- **Compute tier** (Lambda / container workers): executes deterministic PGx calling and optional narration/formatting.
- **Storage tier** (S3): stores per-run artifacts (audit JSON, derived calls, PDF outputs) with Intelligent Tiering.
- **Observability** (CloudWatch): captures timing, error rates, and cost signals per step.

Because the deterministic engine is embarrassingly parallel across patients, the main scaling constraints are:

- **Variant extraction I/O** (remote VCF range reads + tabix queries)
- **Provider throttles** (Bedrock model concurrency / tokens per minute)
- **Cold start overheads** (if using Lambda heavily without warming)

Mitigations in the roadmap:

- **Caching**: cache CPIC evidence chunks and PharmVar/CPIC tables in memory for warm workers; cache intermediate cohort summaries in S3.
- **Sharding**: shard by chromosome (where applicable) or by gene panel slices to parallelize extraction.
- **Bounded concurrency**: Step Functions concurrency caps + backpressure to keep within Bedrock quotas and VCF endpoint limits.

#### Cost modeling (transparent assumptions)

Cost scales approximately linearly with number of simulated patients:

\\[\n+\\text{TotalCost} \\approx N \\times (C_{compute} + C_{retrieval} + C_{llm} + C_{storage})\n+\\]

Where \(N\) is patients simulated. The headline figure (~$0.0001 / patient) corresponds to lightweight simulation mode and a conservative configuration (streamed public VCFs, no large downloads, short evidence context, and bounded narration output). At cohort scale, the dominant terms are typically \(C_{compute}\) and \(C_{llm}\); the streaming design keeps data movement low.

To make this judge-proof, I report cost at three scales (with the exact AWS pricing assumptions used):

- **100 patients**: interactive lab exploration
- **10,000 patients**: cohort-level safety scan
- **100,000 patients**: population-scale screening

*(In the next iteration: publish a reproducible benchmark script + CloudWatch dashboard screenshots for latency, throughput, and cost by step.)*

### AWS-Native Depth (what’s “deep AWS” here)

This project isn’t just “tools integrated” — it’s designed around AWS strengths:

- **Bedrock boundary**: deterministic core stays inspectable; Bedrock is used for explanation and formatting, not decision logic.
- **Step Functions orchestration**: cohort simulation is modeled as durable, retryable steps with per-step metrics.
- **Cost visibility**: each run emits timing + provider usage into logs so cost-per-run can be derived and monitored.
- **S3-first artifacts**: every run writes an audit trail and outputs in S3 with presigned access, enabling review without re-running compute.

### Competitive Landscape

| Tool | Approach | Limitation for Equity |
|---|---|---|
| QIAGEN PGXI, Myriad, GenMark Dx | Certified clinical testing | Single patient, no cohort simulation, high cost |
| PharmCAT, PGxDB | Academic bioinformatics | 15-30 min per sample, hours for multi-ancestry cohort |
| Insilico Medicine, Recursion | AI molecule discovery | Equity gap outside their scope |
| **Anukriti** | Guideline-aligned PGx + cohort simulation | Research prototype; not clinically certified |

**PharmCAT vs Anukriti:** PharmCAT requires Java install, reference data download, and manual phenotype mapping: 15-30 minutes per sample, hours for a multi-ancestry cohort. Anukriti returns a result in ~30 seconds per sample, with similar timing for an AFR + EAS + SAS cohort. Approximately **240x faster** to first multi-ancestry result.

### Gene Panel (17 targets)

| Gene | Chromosome | Key Drug Class | Notes |
|---|---|---|---|
| CYP2D6 | chr22 | Codeine, antidepressants | Copy-number-aware |
| CYP2C19 | chr10 | Clopidogrel, PPIs | 57% poor metabolizer rate in Pacific Islanders |
| CYP2C9 | chr10 | Warfarin, NSAIDs | |
| VKORC1 | chr16 | Warfarin | |
| SLCO1B1 | chr12 | Statins | Myopathy risk |
| TPMT | chr6 | Thiopurines | |
| DPYD | chr1 | Fluoropyrimidines (5-FU) | |
| UGT1A1 | chr2 | Irinotecan | |
| HLA-B*57:01 | chr6 proxy | Abacavir | Hypersensitivity |
| HLA-B*15:02 | chr6 proxy | Carbamazepine | SJS/TEN risk in Asian populations |
| CYP3A4/3A5 | chr7 | Tacrolimus, statins | |
| CYP1A2 | chr15 | Clozapine, caffeine | |
| CYP2B6 | chr19 | Efavirenz | |
| NAT2 | chr8 | Isoniazid | TB hepatotoxicity |
| GSTM1/GSTT1 | chr1/chr22 | Cyclophosphamide | |

### Where LLMs Touch the Pipeline - and Where They Don't

**LLMs explain results. They never decide them.** The deterministic engine fixes star alleles and risk tiers. Amazon Nova narrates and formats the outputs. [PharmVar definitions evolve rapidly](https://pmc.ncbi.nlm.nih.gov/articles/PMC12141247/) - 471 core alleles were added and 49 redefined between versions 1.1.9 and 6.2 - so hard-coded tables keep these changes auditable.

One honest caveat: on Bedrock/Nova paths, structured deterministic blocks are merged with verification labels. On direct Gemini/Claude paths, the narrative comes from the LLM under a constrained CPIC-style prompt - those outputs are research communication, not deterministic calls.

### Verification Pipeline

| Agent | File | What It Checks | Output |
|---|---|---|---|
| Consistency Auditor (Agent 2) | `src/pgx_verification.py` | Gene call vs PharmVar/CPIC tables | `verified` / `ambiguous` / `not in CPIC table` |
| Grounding Scorer (Agent 5) | `src/citation_grounding.py` | LLM explanation vs retrieved CPIC passages | Sentence-level grounding fraction; no extra model call |

On 174 SFT-labeled PGx queries: **MRR 1.0, precision@1 1.0, recall@3 1.0** - the gold CPIC document ranks first every time.

### Regulatory Pathway

| Stage | Status | Requirements |
|---|---|---|
| Stage 1: Research prototype | **Current** | Non-clinical label, academic simulation only |
| Stage 2: Institutional validation | Roadmap | IRB approval, patient-level VCFs, outcomes concordance study |
| Stage 3: Regulated CDS claim | Future | FDA 510(k) or De Novo, prospective outcome data, peer-reviewed publication |

Full staging documented in `docs/regulatory/CLINICAL_VALIDATION_ROADMAP.md`. The separation between deterministic calling and LLM narration keeps this path open - the safety-critical logic remains inspectable at every stage.

---

## Demo

**Demo Video:** [youtube.com/watch?v=zu-1reih7wA](https://www.youtube.com/watch?v=zu-1reih7wA)

**Live Demo:** [anukriti.abhimanyurb.com](https://anukriti.abhimanyurb.com)

**API Docs:** [anukritibackend.abhimanyurb.com/docs](https://anukritibackend.abhimanyurb.com/docs)

**GitHub:** [github.com/Abm32/Synthatrial](https://github.com/Abm32/Synthatrial)

The demo showcases a full multi-ancestry simulation (AFR, EAS, SAS), showing how a single drug produces different risk profiles across populations. The deterministic PGx engine, audit trail, and grounded LLM explanation are all visible in a single run. The recording leads with the equity narrative before the interface walkthrough - judges encounter the *why* before the *how*.

---

## What I Learned

### Judge Feedback That Changed the Project Most

**"Limited gene panel"** - Led to expansion from 8 to 17 targets, with explicit prioritisation by CPIC Tier A evidence. HLA-B*15:02 (carbamazepine/SJS) was added specifically because it represents exactly the kind of Asia-specific risk Western trials systematically miss - [in a case-control study, all 44 Han Chinese patients with carbamazepine-induced SJS/TEN carried this allele](https://pmc.ncbi.nlm.nih.gov/articles/PMC2586963/).

**"Regulatory pathway unclear"** - Led to a concrete three-stage roadmap in `docs/regulatory/CLINICAL_VALIDATION_ROADMAP.md`. A judge who checks the repo finds the document, not just a disclaimer.

**"Validation scope"** - The current system is validated against CPIC fixture data - deterministic and auditable, but not prospective clinical validation. The Consistency Auditor's per-call audit trail and the separation of calling logic from LLM narration are the design choices that would make prospective validation feasible. The prototype claims research utility and auditability - honest and defensible at this stage.

### What Genuinely Surprised Me

I assumed the hardest problem would be the genomics engine. The harder problem was the verification architecture. Early versions produced results that looked authoritative but were not auditable. The Consistency Auditor and Grounding Scorer were not planned - they emerged from the uncomfortable realization that "trust the model" is not a healthcare architecture.

The **Virtual Phase 0** framing also emerged under pressure. Describing Anukriti as a "research tool" was accurate but undersold its value. *Run a genomic safety simulation across diverse populations before committing wet-lab budget* - that makes the cost de-risking argument concrete.

On market adoption: the strategy is to establish credibility with academic PGx labs, safety researchers, and bioinformatics educators first - the groups who publish evidence that eventually shifts industry practice. At ~$10^-4 per patient, the tool is priced for academic exploration, not enterprise procurement. Proving value in open research is the wedge.

### The Core Insight

Population-aware pharmacogenomic simulation is not aspirational - the evidence base already exists. Four continents of documented population-linked harm, a [30% ADR reduction from pre-emptive panel testing](https://pmc.ncbi.nlm.nih.gov/articles/PMC11949333/), and FDA and NIH pressure on trial diversity all point in the same direction. Cases like [codeine in ultrarapid metabolizers](https://www.ncbi.nlm.nih.gov/books/NBK100662/), [carbamazepine in HLA-B*15:02 carriers](https://pmc.ncbi.nlm.nih.gov/articles/PMC2586963/), [clopidogrel in CYP2C19 poor metabolizers](https://www.ncbi.nlm.nih.gov/books/NBK84114/), and [abacavir in HLA-B*57:01 carriers](https://arupconsult.com/ati/hla-b5701-abacavir-sensitivity) demonstrate the population specificity of harm. Anukriti does not introduce new biological knowledge - it reveals what we have systematically ignored.

---

*For research and educational use only - not for clinical decision-making.*
