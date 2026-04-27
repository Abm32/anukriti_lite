#!/usr/bin/env bash
#
# Tier 3: DeepVariant + SynthaTrial validation
#
# Downloads DeepVariant quickstart test data (chr20), runs DeepVariant,
# then validates the output VCF with SynthaTrial.
#
# Requirements: Docker, ~16 GB RAM, ~2 GB disk, wget
# Runtime: ~15-30 min (download + DeepVariant + validation)
#
# Usage: ./scripts/run_deepvariant_validation.sh [WORK_DIR]
#   WORK_DIR defaults to ./deepvariant_validation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORK_DIR="${1:-${REPO_ROOT}/deepvariant_validation}"
BIN_VERSION="1.8.0"
DATA_URL="https://storage.googleapis.com/deepvariant/quickstart-testdata"

echo "=== DeepVariant + SynthaTrial Validation ==="
echo "Work directory: ${WORK_DIR}"
mkdir -p "${WORK_DIR}"/{input,output}
INPUT_DIR="${WORK_DIR}/input"
OUTPUT_DIR="${WORK_DIR}/output"

# Stage 1: Download test data (chr20, ~10kb region)
echo ""
echo "--- Stage 1: Downloading test data ---"
for f in NA12878_S1.chr20.10_10p1mb.bam NA12878_S1.chr20.10_10p1mb.bam.bai \
         ucsc.hg19.chr20.unittest.fasta ucsc.hg19.chr20.unittest.fasta.fai; do
  if [[ ! -f "${INPUT_DIR}/${f}" ]]; then
    echo "Downloading ${f}..."
    if command -v wget &>/dev/null; then
      wget -q -O "${INPUT_DIR}/${f}" "${DATA_URL}/${f}"
    elif command -v curl &>/dev/null; then
      curl -sL -o "${INPUT_DIR}/${f}" "${DATA_URL}/${f}"
    else
      echo "Need wget or curl to download test data"
      exit 1
    fi
  else
    echo "Already have ${f}"
  fi
done

# Stage 2: Run DeepVariant
echo ""
echo "--- Stage 2: Running DeepVariant (chr20 test region) ---"
docker run \
  -v "${INPUT_DIR}:/input" \
  -v "${OUTPUT_DIR}:/output" \
  google/deepvariant:"${BIN_VERSION}" \
  /opt/deepvariant/bin/run_deepvariant \
  --model_type=WGS \
  --ref=/input/ucsc.hg19.chr20.unittest.fasta \
  --reads=/input/NA12878_S1.chr20.10_10p1mb.bam \
  --regions "chr20:10,000,000-10,010,000" \
  --output_vcf=/output/output.vcf.gz \
  --output_gvcf=/output/output.g.vcf.gz \
  --num_shards=1

if [[ ! -f "${OUTPUT_DIR}/output.vcf.gz" ]]; then
  echo "DeepVariant failed: output.vcf.gz not found"
  exit 1
fi
echo "DeepVariant completed: ${OUTPUT_DIR}/output.vcf.gz"

# Stage 3: Validate with SynthaTrial
echo ""
echo "--- Stage 3: Validating with SynthaTrial ---"
# Use same VCF for chr22/chr10 paths; chr20 has no PGx genes so we get default phenotypes.
# This validates VCF format compatibility and pipeline execution.
# Sample ID is auto-detected from VCF header.
cd "${REPO_ROOT}"
VCF_SOURCE_MODE=local \
AWS_ACCESS_KEY_ID='' \
AWS_SECRET_ACCESS_KEY='' \
AWS_SESSION_TOKEN='' \
python main.py \
  --vcf "${OUTPUT_DIR}/output.vcf.gz" \
  --vcf-chr10 "${OUTPUT_DIR}/output.vcf.gz" \
  --drug-name Warfarin

echo ""
echo "=== Validation complete ==="
echo "DeepVariant output: ${OUTPUT_DIR}/output.vcf.gz"
echo "SynthaTrial accepted the VCF and produced a profile."
echo ""
echo "Note: chr20 has no PGx genes; phenotypes are defaults. For chr10 (CYP2C19/CYP2C9)"
echo "validation, use your own chr10 BAM with DeepVariant --regions chr10."
