# PGx LoRA SFT (scaffold)

Build **supervised fine-tuning** data from versioned CPIC-aligned JSON under `data/pgx/cpic/`, then train a **LoRA** adapter on a chat instruct model (default `Qwen/Qwen2.5-7B-Instruct`).

## Prerequisites

1. **PyTorch for your hardware** — install *before* `requirements-train.txt`. On **AMD MI300X**, use your provider’s **ROCm** image or wheels; do not assume CUDA `bitsandbytes`.
2. **HF token** if the base model is gated: `huggingface-cli login` or `HF_TOKEN`.

```bash
python3 -m venv .venv-train
source .venv-train/bin/activate
pip install -r training/lm_finetune/requirements-train.txt
```

Optional **QLoRA** (`--use_4bit`): requires `bitsandbytes` built for your stack; often **not** available on ROCm—prefer **bf16 LoRA** on MI300X.

## Data

```bash
python training/lm_finetune/export_pgx_sft_jsonl.py
# writes data/training/pgx_sft.jsonl (gitignored)
```

Licensing: CPIC-derived text is for **research and internal tooling** only; respect [CPIC](https://cpicpgx.org/) terms and do not ship verbatim guideline prose as a commercial product without permission.

## Single-GPU smoke test

```bash
accelerate launch --num_processes 1 training/lm_finetune/train_lora_sft.py \
  --model_name Qwen/Qwen2.5-7B-Instruct \
  --dataset_path data/training/pgx_sft.jsonl \
  --output_dir training_outputs/pgx_lora_smoke \
  --max_steps 5 \
  --per_device_train_batch_size 1 \
  --gradient_accumulation_steps 1
```

## 8× GPU (DDP via Accelerate)

```bash
accelerate config   # multi-GPU, bf16, etc.
accelerate launch --num_processes 8 training/lm_finetune/train_lora_sft.py \
  --model_name Qwen/Qwen2.5-7B-Instruct \
  --dataset_path data/training/pgx_sft.jsonl \
  --output_dir training_outputs/pgx_lora
```

For **70B** or **ZeRO-3 / FSDP**, use Hugging Face DeepSpeed / FSDP recipes and larger `per_device` + gradient accumulation; this script is a minimal LoRA entry point.

## What to do next (pick one path)

You already proved the pipeline works if **`training_outputs/.../adapter_model.safetensors`** exists.

1. **Try the adapter (quick)** — loads base model from Hub + your small LoRA on disk:

   ```bash
   python training/lm_finetune/infer_lora.py \
     --adapter_path training_outputs/pgx_lora_smoke
   ```

   Use **`--user_prompt "..."`** to test PGx-style questions.

2. **Train for real** — one full epoch (or more steps) into a new folder:

   ```bash
   accelerate launch --num_processes 1 training/lm_finetune/train_lora_sft.py \
     --model_name Qwen/Qwen2.5-7B-Instruct \
     --dataset_path data/training/pgx_sft.jsonl \
     --output_dir training_outputs/pgx_lora_v1 \
     --num_train_epochs 1 \
     --per_device_train_batch_size 1 \
     --gradient_accumulation_steps 8 \
     --save_steps 50 \
     --logging_steps 10 \
     --max_steps -1
   ```

   Then run **`infer_lora.py`** with `--adapter_path training_outputs/pgx_lora_v1`.

3. **Merge (optional, large disk)** — only if you need a **single** model directory (full 7B size) for a server that does not use PEFT:

   ```bash
   python training/lm_finetune/merge_lora.py \
     --adapter_path training_outputs/pgx_lora_smoke \
     --output_dir training_outputs/pgx_lora_merged
   ```

   Most workflows can **skip merge** and keep base + adapter.

## Backing up adapters (GitHub vs Hugging Face)

`training_outputs/` is **gitignored** (ephemeral GPU runs). To publish an adapter:

1. **Preferred for weights:** upload the adapter folder to [Hugging Face Hub](https://huggingface.co/docs/hub/models-uploading) (`huggingface-cli upload` or the web UI). Keep only adapter + tokenizer sidecars—do not commit the base model.

2. **GitHub with Git LFS:** GitHub rejects plain Git blobs **> 100 MB**. Copy the run to a stable path and let LFS track `*.safetensors` there:

   ```bash
   # one-time on your laptop
   git lfs install

   # from the machine that has the files (example layout)
   mkdir -p artifacts/lora/pgx_lora_32b_v1
   rsync -avz user@droplet:~/SynthaTrial-repo/training_outputs/pgx_lora_32b_v1/ artifacts/lora/pgx_lora_32b_v1/

   git add artifacts/lora/pgx_lora_32b_v1
   git commit -m "chore: add PGx LoRA adapter (LFS)"
   git push origin main
   ```

   The repo root `.gitattributes` routes `artifacts/**/*.safetensors` through **Git LFS**. Check [Git LFS billing](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage) if you store many revisions.

## Next steps (RAG / retrieval)

- Add **dense retrieval** pairs (`query` → `passage`) in a separate JSONL and train an **embedding** model or use the same corpus for **DPO** preference pairs after SFT.
- Expand beyond CPIC tables with licensed guideline snippets and de-identified or synthetic VCF summaries.
