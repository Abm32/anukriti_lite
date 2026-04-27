# DeepVariant on Consumer Hardware (Intel i7, 16GB RAM, RTX 3060)

> Optimized setup for running DeepVariant on a typical developer workstation and feeding output to SynthaTrial.

**Target system:** Intel i7 CPU, 16 GB RAM, RTX 3060 4GB VRAM

---

## 1. Hardware Assessment

| Component | Capability | Recommendation |
|-----------|------------|----------------|
| **Intel i7 CPU** | DeepVariant uses AVX-512/AVX2 and Intel MKL. OpenVINO can accelerate the CNN. | **Primary engine** — run on CPU with OpenVINO |
| **16 GB RAM** | Limit parallel shards to avoid OOM | Use `--num_shards=4` to `6` (not 8+) |
| **RTX 3060 4GB VRAM** | GPU image may OOM during `call_variants` (cloud uses 16GB+ GPUs) | **Optional** — try GPU; fall back to CPU if OOM |

---

## 2. Prerequisites

### 2.1 Align Sequencing Data (If You Have FASTQ)

DeepVariant requires **aligned reads** (BAM/CRAM). If you have raw FASTQ:

```bash
# Example: BWA-MEM alignment (Illumina)
bwa mem -t 4 reference.fa read1.fq read2.fq | samtools sort -o aligned.bam
samtools index aligned.bam
```

### 2.2 Install Docker

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y docker.io
sudo usermod -aG docker $USER
```

### 2.3 Pull DeepVariant Image

```bash
BIN_VERSION="1.8.0"
docker pull google/deepvariant:"${BIN_VERSION}"
```

---

## 3. Run DeepVariant (CPU + OpenVINO)

For Intel i7, use the CPU image with OpenVINO acceleration:

```bash
INPUT_DIR="/path/to/input"   # BAM + reference FASTA
OUTPUT_DIR="/path/to/output"
mkdir -p "${OUTPUT_DIR}"

docker run \
  -v "${INPUT_DIR}:/input" \
  -v "${OUTPUT_DIR}:/output" \
  google/deepvariant:"${BIN_VERSION}" \
  /opt/deepvariant/bin/run_deepvariant \
  --model_type=WGS \
  --ref=/input/your_reference.fa \
  --reads=/input/your_aligned.bam \
  --output_vcf=/output/output.vcf.gz \
  --output_gvcf=/output/output.g.vcf.gz \
  --call_variants_extra_args="use_openvino=true" \
  --num_shards=4
```

**Key flags for your hardware:**

- `--call_variants_extra_args="use_openvino=true"` — Intel CPU acceleration (v1.1.0+; omit if unsupported)
- `--num_shards=4` — Safe for 16GB RAM; increase to 6 if stable, avoid 8+

**Model types:** `WGS` (Illumina), `WES` (exome), `PACBIO`, `ONT_R104` (Nanopore)

---

## 4. Single-Chromosome Run (Faster for PGx)

For chr10 (CYP2C19, CYP2C9) — ~30–60 min on your system:

```bash
docker run \
  -v "${INPUT_DIR}:/input" \
  -v "${OUTPUT_DIR}:/output" \
  google/deepvariant:"${BIN_VERSION}" \
  /opt/deepvariant/bin/run_deepvariant \
  --model_type=WGS \
  --ref=/input/your_reference.fa \
  --reads=/input/your_aligned.bam \
  --regions "chr10:96000000-97000000" \
  --output_vcf=/output/output_chr10.vcf.gz \
  --output_gvcf=/output/output_chr10.g.vcf.gz \
  --call_variants_extra_args="use_openvino=true" \
  --num_shards=2
```

---

## 5. GPU Option (Optional, May OOM)

RTX 3060 4GB VRAM may work for small regions. If you get OOM, fall back to CPU.

```bash
docker run --gpus 1 \
  -v "${INPUT_DIR}:/input" \
  -v "${OUTPUT_DIR}:/output" \
  google/deepvariant:"${BIN_VERSION}-gpu" \
  /opt/deepvariant/bin/run_deepvariant \
  --model_type=WGS \
  --ref=/input/your_reference.fa \
  --reads=/input/your_aligned.bam \
  --regions "chr10:96000000-97000000" \
  --output_vcf=/output/output_chr10.vcf.gz \
  --output_gvcf=/output/output_chr10.g.vcf.gz \
  --num_shards=1
```

**If GPU OOM:** Remove `--gpus 1`, use CPU image instead, add `--call_variants_extra_args="use_openvino=true"`.

---

## 6. Connect to SynthaTrial

Once you have `output.vcf.gz`:

```bash
# Full PGx analysis
python main.py \
  --vcf /path/to/output.vcf.gz \
  --vcf-chr10 /path/to/output.vcf.gz \
  --drug-name Warfarin

# Or filter to PGx regions first (for large VCFs)
python scripts/filter_vcf_to_pgx_regions.py output.vcf.gz pgx_only.vcf.gz
python main.py --vcf pgx_only.vcf.gz --drug-name Warfarin
```

---

## 7. End-to-End Pipeline

```
FASTQ (optional) → BWA-MEM → BAM
    → DeepVariant (CPU + OpenVINO)
    → output.vcf.gz
    → SynthaTrial (main.py)
    → PGx report
```

---

## 8. Troubleshooting

| Issue | Solution |
|-------|----------|
| `Killed` or OOM | Reduce `--num_shards` to 2 or 4 |
| GPU OOM | Use CPU image instead; add `use_openvino=true` |
| `use_openvino` not found | Omit the flag; CPU still works well without OpenVINO |
| Slow | Use `--regions` for single chromosome; expect 30–60 min for chr10 |

---

## References

- [DEEPVARIANT_QUICKSTART.md](DEEPVARIANT_QUICKSTART.md) — Docker commands
- [DEEPVARIANT_TIER3_VALIDATION.md](DEEPVARIANT_TIER3_VALIDATION.md) — Validation script
- [DeepVariant GitHub](https://github.com/google/deepvariant)
