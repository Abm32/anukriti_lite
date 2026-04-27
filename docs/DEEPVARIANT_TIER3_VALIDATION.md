# Tier 3: DeepVariant + SynthaTrial Validation

> Optional single-chromosome validation to prove end-to-end pipeline compatibility.

**Requirements:** Docker, ~16 GB RAM, ~2 GB disk, wget or curl
**Runtime:** ~15–30 minutes (download + DeepVariant + validation)

---

## Quick Run

```bash
./scripts/run_deepvariant_validation.sh
```

Or with a custom work directory:

```bash
./scripts/run_deepvariant_validation.sh /path/to/workdir
```

---

## What It Does

1. **Downloads** DeepVariant quickstart test data (chr20, ~10 kb region) from Google Cloud Storage
2. **Runs** DeepVariant Docker to produce `output.vcf.gz`
3. **Validates** by feeding the VCF to SynthaTrial (`main.py --vcf ... --drug-name Warfarin`)

The script forces **local-only discovery** during validation by setting `VCF_SOURCE_MODE=local`, so it does not attempt S3 chromosome downloads.

---

## Expected Output

- DeepVariant produces `output.vcf.gz` and `output.g.vcf.gz`
- SynthaTrial parses the VCF and generates a patient profile
- **Note:** chr20 has no PGx genes (CYP2D6, CYP2C19, etc. are on chr22, chr10). Phenotypes will be defaults. This validates **format compatibility** and **pipeline execution**, not PGx allele calling.

---

## Chr10 Validation (PGx Genes)

For meaningful CYP2C19/CYP2C9 validation, you need chr10 data:

1. Obtain a BAM with chr10 (e.g., from GIAB, 1000 Genomes, or your own sequencing)
2. Run DeepVariant with `--regions chr10:96000000-97000000` (or full chr10)
3. Feed the output to SynthaTrial:

```bash
python main.py --vcf output.vcf.gz --vcf-chr10 output.vcf.gz --drug-name Warfarin
```

See [DEEPVARIANT_QUICKSTART.md](DEEPVARIANT_QUICKSTART.md) for DeepVariant commands.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `tabix not found` | Install htslib: `conda install -c conda-forge htslib` |
| `Docker permission denied` | Run with `sudo` or add user to docker group |
| `No samples found in VCF` | Ensure DeepVariant completed; check `output.vcf.gz` exists |
| Out of memory | DeepVariant needs ~16 GB RAM; reduce `--num_shards` to 1 |
