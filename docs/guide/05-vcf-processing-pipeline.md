# Chapter 5: VCF Processing Pipeline

The VCF (Variant Call Format) processing pipeline transforms raw genomic data into
structured patient profiles suitable for pharmacogenomics analysis.

## 5.1 Overview

```
VCF File (GRCh37 or GRCh38)
    │
    ├── Parse header (samples, reference genome)
    ├── Extract PGx gene regions (by chromosome + position)
    ├── Filter to known PGx rsIDs
    ├── Call star alleles per gene
    ├── Build diplotypes
    ├── Map to phenotypes
    └── Assemble patient profile
```

## 5.2 Dual Reference Genome Support

**Module**: `src/vcf_processor.py`

Anukriti supports both GRCh37 (hg19) and GRCh38 (hg38) coordinate systems:

```python
GENE_LOCATIONS_GRCH37 = {
    "CYP2C19": {"chr": "10", "start": 96522463, "end": 96612671},
    "CYP2C9":  {"chr": "10", "start": 96698415, "end": 96749148},
    "CYP2D6":  {"chr": "22", "start": 42522501, "end": 42526883},
    "SLCO1B1": {"chr": "12", "start": 21284127, "end": 21392730},
    "VKORC1":  {"chr": "16", "start": 31102175, "end": 31106699},
    "TPMT":    {"chr": "6",  "start": 18128542, "end": 18155374},
    "DPYD":    {"chr": "1",  "start": 97543300, "end": 98386615},
    "UGT1A1":  {"chr": "2",  "start": 234668879, "end": 234681945},
}

GENE_LOCATIONS_GRCH38 = {
    "CYP2C19": {"chr": "10", "start": 94762681, "end": 94855547},
    "CYP2C9":  {"chr": "10", "start": 94938683, "end": 94990091},
    # ... (different coordinates for GRCh38)
}
```

The pipeline auto-detects the reference genome from the VCF header or accepts it as a
parameter.

### 5.2.1 VCF Compatibility Requirements

SynthaTrial consumes standard VCF files from any variant caller (e.g., DeepVariant, GATK, bcftools). For compatibility:

| Requirement | Details |
|-------------|---------|
| **Format** | VCF 4.x (standard VCF or gVCF) |
| **Reference** | GRCh37 (hg19) or GRCh38 (hg38) |
| **Genotypes** | GT field required: `0/0`, `0/1`, `1/1` (unphased) or `0\|1`, `1\|0` (phased) |
| **rsIDs** | Preferred for PharmVar lookup; chr:pos:ref:alt works with annotation (e.g., bcftools annotate) |
| **Structural variants** | SVTYPE (DEL, DUP) in INFO for CYP2D6 CNVs; CN= optional for copy number |
| **Chromosomes** | chr1–chr22, chrX, chrY (chrN or N both accepted) |

**Recommended variant callers:** DeepVariant (best accuracy in difficult PGx regions), GATK HaplotypeCaller, bcftools mpileup. See [DEEPVARIANT_ANALYSIS.md](../DEEPVARIANT_ANALYSIS.md).

## 5.3 VCF Parsing (`parse_vcf`)

The parser handles standard VCF 4.x format:

```
##fileformat=VCFv4.3
##reference=GRCh37
#CHROM  POS     ID        REF  ALT  QUAL  FILTER  INFO       FORMAT    SAMPLE1
10      94781859 rs4244285 G    A    100   PASS    ...        GT:DP     0/1:30
```

Key processing steps:

1. **Header parsing**: Extract sample names, reference genome version
2. **Variant filtering**: Keep only variants in PGx gene regions
3. **rsID matching**: Match each variant to known PGx rsIDs
4. **Genotype extraction**: Parse GT field (0/0, 0/1, 1/1, .|.)
5. **Multi-allelic handling**: Support for multi-ALT variants (1/2, etc.)

Output per variant:
```python
{
    "rsid": "rs4244285",
    "ref": "G",
    "alt": "A",
    "genotype": "0/1",
    "chromosome": "10",
    "position": 94781859
}
```

## 5.4 Sample Extraction (`extract_samples`)

For multi-sample VCFs (e.g., 1000 Genomes with 2,504 samples):

```python
samples = extract_samples("ALL.chr10.phase3.vcf.gz")
# Returns: ["HG00096", "HG00097", "HG00099", ..., "NA21144"]
```

## 5.5 Gene Calling (`call_genes_for_sample`)

For each sample, runs all 8 gene callers:

```python
def call_genes_for_sample(variants, sample_id):
    results = {}

    # Standard star allele genes
    for gene in ["CYP2C19", "CYP2C9", "CYP2D6", "UGT1A1"]:
        gene_variants = filter_variants_for_gene(variants, gene)
        diplotype = call_star_alleles(gene_variants, gene)
        phenotype = diplotype_to_phenotype(diplotype, gene)
        results[gene] = {"diplotype": diplotype, "phenotype": phenotype}

    # Gene-specific callers
    results["warfarin"] = interpret_warfarin_from_vcf(variants)
    results["SLCO1B1"] = interpret_slco1b1_from_vcf(variants)
    results["TPMT"] = interpret_tpmt_from_vcf(variants)
    results["DPYD"] = interpret_dpyd_from_vcf(variants)

    return results
```

## 5.6 Patient Profile Assembly (`build_patient_profile`)

Aggregates all gene results into a structured profile:

```python
{
    "sample_id": "HG00096",
    "reference_genome": "GRCh37",
    "genes": {
        "CYP2C19": {
            "diplotype": "*1/*2",
            "phenotype": "Intermediate Metabolizer",
            "variants": [{"rsid": "rs4244285", "genotype": "0/1"}]
        },
        "CYP2C9": {
            "diplotype": "*1/*1",
            "phenotype": "Normal Metabolizer",
            "variants": []
        },
        "VKORC1": {
            "genotype": "GA",
            "phenotype": "Intermediate Sensitivity"
        },
        "SLCO1B1": {
            "genotype": "TT",
            "phenotype": "Normal Function"
        },
        ...
    },
    "drug_triggers": {
        "clopidogrel": ["CYP2C19"],
        "warfarin": ["CYP2C9", "VKORC1"],
        "simvastatin": ["SLCO1B1"]
    }
}
```

## 5.7 Remote VCF Access (`src/remote_vcf.py`)

For accessing 1000 Genomes data without downloading full files:

### Remote Tabix Query

```python
def query_1000_genomes_region(chromosome, start, end):
    """Query 1000 Genomes FTP using remote tabix."""
    url = f"ftp://ftp.1000genomes.ebi.ac.uk/.../ALL.chr{chromosome}.phase3.vcf.gz"
    # Uses htslib tabix for region-based extraction
    return variants_in_region
```

### Ensembl REST API Fallback

```python
def query_ensembl_variants(rsid):
    """Fallback to Ensembl REST API for individual variant lookup."""
    url = f"https://rest.ensembl.org/variation/human/{rsid}"
    response = requests.get(url, headers={"Content-Type": "application/json"})
    return variant_info
```

### Pre-Extracted PGx Panel

For efficiency, a PGx panel TSV can be pre-extracted from full VCFs:

```python
def extract_pgx_panel(vcf_path, output_path):
    """Extract only the ~30 PGx rsIDs from a full VCF."""
    pgx_rsids = get_all_pgx_rsids()  # All 8 genes' rsIDs
    # Write subset VCF with only PGx variants
```

## 5.8 Local 1000 Genomes Data

Pre-downloaded VCF files in `data/genomes/`:

| File | Chromosome | Genes | Status |
|------|------------|-------|--------|
| `ALL.chr2.phase3...vcf.gz` | chr2 | UGT1A1 | Active |
| `ALL.chr6.phase3...vcf.gz` | chr6 | TPMT | Downloadable; not yet mapped in VCF processor |
| `ALL.chr10.phase3...vcf.gz` | chr10 | CYP2C19, CYP2C9 | Active |
| `ALL.chr11.phase3...vcf.gz` | chr11 | (reserved) | Downloadable; not used |
| `ALL.chr12.phase3...vcf.gz` | chr12 | SLCO1B1 | Active |
| `ALL.chr16.phase3...vcf.gz` | chr16 | VKORC1 | Active (Warfarin PGx) |
| `ALL.chr19.phase3...vcf.gz` | chr19 | (reserved) | Downloadable; not used |
| `ALL.chr22.phase3...vcf.gz` | chr22 | CYP2D6 | Active |

All files include `.tbi` tabix index files for efficient region queries. Any `.vcf.gz` in `data/genomes/` whose filename contains the chromosome (e.g. `chr22`, `chr10`) is auto-discovered — no manual path configuration needed.

## 5.9 VCF Download & Validation

**Download**: `scripts/download_vcf_files.py`
```bash
python scripts/download_vcf_files.py
# Downloads all 8 chromosome files + tabix indices
```

**Validation**: `scripts/check_vcf_integrity.py`
```bash
python scripts/check_vcf_integrity.py
# Checks: file existence, tabix indexing, variant counts, sample names
```

## 5.10 CYP2D6 Structural Variant Handling

CYP2D6 is one of the most complex pharmacogenes due to:
- Gene deletions (*5): Entire gene absent → no enzyme
- Gene duplications (*1xN, *2xN): Extra copies → ultra-rapid metabolism
- Hybrid alleles: CYP2D6/CYP2D7 fusions

The platform handles these via `test_cyp2d6_cnv.py`:

```python
def _parse_svtype(info):
    """Extract structural variant type from VCF INFO field."""
    # DEL → gene deletion
    # DUP → gene duplication

def _cnv_allele_to_star(svtype, cn):
    """Map CNV to star allele."""
    # DEL (CN=0) → *5
    # DUP (CN=3+) → *1xN or *2xN

def infer_metabolizer_status(allele1, allele2, activity_scores):
    """Calculate activity score from two alleles including CNV."""
    total_score = activity_scores[allele1] + activity_scores[allele2]
    if total_score == 0: return "Poor Metabolizer"
    elif total_score < 1.25: return "Intermediate Metabolizer"
    elif total_score <= 2.25: return "Normal Metabolizer"
    else: return "Ultra-rapid Metabolizer"
```

---

**Next**: [Chapter 6 — Population Simulation & Ancestry](06-population-simulation.md)
