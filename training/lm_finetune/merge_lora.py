#!/usr/bin/env python3
"""
Merge LoRA weights into the base model and save a standalone model directory (no PEFT at runtime).

Example:
  python training/lm_finetune/merge_lora.py \\
    --adapter_path training_outputs/pgx_lora_smoke \\
    --output_dir training_outputs/pgx_lora_merged
"""

from __future__ import annotations

import argparse

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--base_model",
        type=str,
        default="Qwen/Qwen2.5-7B-Instruct",
        help="HF hub id for the base model (must match training).",
    )
    ap.add_argument(
        "--adapter_path",
        type=str,
        required=True,
        help="Directory with adapter_config.json + adapter_model.safetensors.",
    )
    ap.add_argument(
        "--output_dir",
        type=str,
        required=True,
        help="Where to write merged model + tokenizer (large disk usage ~full 7B).",
    )
    args = ap.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.adapter_path, trust_remote_code=True)
    base = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    model = PeftModel.from_pretrained(base, args.adapter_path)
    merged = model.merge_and_unload()
    merged.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"Merged model saved to {args.output_dir}")


if __name__ == "__main__":
    main()
