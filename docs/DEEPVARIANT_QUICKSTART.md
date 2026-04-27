# DeepVariant Quick Start for SynthaTrial

> Copy-paste commands to run DeepVariant and produce VCF files compatible with SynthaTrial.

**Prerequisites:** Docker, BAM/CRAM file, reference genome (FASTA + .fai), ~16 GB RAM for full genome.

**For Intel i7 + 16GB RAM + RTX 3060:** See [DEEPVARIANT_HARDWARE_GUIDE.md](DEEPVARIANT_HARDWARE_GUIDE.md).

---

## 1. Pull the Docker Image

```bash
BIN_VERSION="1.8.0"
docker pull google/deepvariant:"${BIN_VERSION}"
```

---

## 2. Run DeepVariant (Full Command)

Mount your input and output directories, then run:

```bash
INPUT_DIR="/path/to/your/input"   # Contains: BAM, reference FASTA
OUTPUT_DIR="/path/to/your/output"
mkdir -p "${OUTPUT_DIR}"

docker run \
  -v "${INPUT_DIR}":"/input" \
  -v "${OUTPUT_DIR}":"/output" \
  google/deepvariant:"${BIN_VERSION}" \
  /opt/deepvariant/bin/run_deepvariant \
  --model_type=WGS \
  --ref=/input/your_reference.fasta \
  --reads=/input/your_aligned.bam \
  --output_vcf=/output/output.vcf.gz \
  --output_gvcf=/output/output.g.vcf.gz \
  --num_shards=4
```

Replace `your_reference.fasta` and `your_aligned.bam` with your actual file paths (as seen inside the container at `/input/`).

**Model types:** `WGS` (Illumina), `PACBIO`, `ONT_R104` (Nanopore), `HYBRID_PACBIO_ILLUMINA`. Use the one matching your sequencing technology.

---

## 3. Single-Chromosome Run (Testing on a Laptop)

Full WGS requires several hours and significant RAM. For testing or PGx-focused validation, limit to one chromosome:

**Chr10 (CYP2C19, CYP2C9 — core PGx genes):**

```bash
docker run \
  -v "${INPUT_DIR}":"/input" \
  -v "${OUTPUT_DIR}":"/output" \
  google/deepvariant:"${BIN_VERSION}" \
  /opt/deepvariant/bin/run_deepvariant \
  --model_type=WGS \
  --ref=/input/your_reference.fasta \
  --reads=/input/your_aligned.bam \
  --regions "chr10:96000000-97000000" \
  --output_vcf=/output/output_chr10.vcf.gz \
  --output_gvcf=/output/output_chr10.g.vcf.gz \
  --num_shards=1
```

Adjust the region to match your reference (e.g., `10:96000000-97000000` if your FASTA uses numeric chromosomes).

---

## 4. Feed Output to SynthaTrial

Once you have `output.vcf.gz` (or `output_chr10.vcf.gz`):

```bash
# CLI
python main.py --vcf /path/to/output.vcf.gz --vcf-chr10 /path/to/output.vcf.gz --drug-name Warfarin

# Or filter to PGx regions first (for large VCFs)
python scripts/filter_vcf_to_pgx_regions.py output.vcf.gz pgx_only.vcf.gz
python main.py --vcf pgx_only.vcf.gz --drug-name Warfarin
```

---

## 5. Notes

- **Full WGS:** Expect several hours on a multi-core machine. Cloud instances with AVX-512 complete in a few hours (~$2–3 per genome).
- **Chr10-only:** Typically 30–60 minutes on a laptop with 16 GB RAM.
- **Reference:** Must match your BAM alignment (GRCh37 or GRCh38). SynthaTrial supports both.
- **GPU:** Use `google/deepvariant:"${BIN_VERSION}-gpu"` and add `--gpus 1` to the `docker run` command for faster `call_variants`.

---

## References

- [DeepVariant GitHub](https://github.com/google/deepvariant)
- [DeepVariant Quick Start](https://github.com/google/deepvariant/blob/main/docs/deepvariant-quick-start.md)
- [SynthaTrial VCF Compatibility](guide/05-vcf-processing-pipeline.md#521-vcf-compatibility-requirements)
