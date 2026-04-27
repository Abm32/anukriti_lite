#!/usr/bin/env python3
"""
Load a base instruct model + PEFT LoRA adapter and run a single chat generation.

Example:
  python training/lm_finetune/infer_lora.py \\
    --adapter_path training_outputs/pgx_lora_smoke \\
    --user_prompt "Explain CYP2C19 poor metabolizer implications for clopidogrel (research only)."
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
        help="Directory with adapter_config.json + adapter_model.safetensors (+ tokenizer files).",
    )
    ap.add_argument(
        "--system_prompt",
        type=str,
        default=(
            "You are a pharmacogenomics research assistant. "
            "Outputs are for research and education only—not medical advice."
        ),
    )
    ap.add_argument(
        "--user_prompt",
        type=str,
        default=(
            "In plain language, what does CYP2C19 poor metabolizer status imply for "
            "clopidogrel in a research briefing? State uncertainty and limitations."
        ),
    )
    ap.add_argument("--max_new_tokens", type=int, default=256)
    ap.add_argument(
        "--match_export_user_format",
        action="store_true",
        help=(
            "Wrap --user_prompt like export_pgx_sft_jsonl.py (Context + drug + patient + "
            "briefing instructions). Use when the adapter was trained on that export; "
            "short bare questions otherwise tend to trigger generic boilerplate."
        ),
    )
    ap.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="If >0, enable sampling (do_sample) with this temperature.",
    )
    ap.add_argument("--top_p", type=float, default=0.9)
    ap.add_argument(
        "--repetition_penalty",
        type=float,
        default=1.0,
        help="e.g. 1.1–1.2 to reduce repeated boilerplate paragraphs.",
    )
    args = ap.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.adapter_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    model = PeftModel.from_pretrained(model, args.adapter_path)
    model.eval()

    user_content = args.user_prompt
    if args.match_export_user_format:
        user_content = (
            "Context (CPIC-aligned research excerpt; not a complete clinical guideline):\n"
            f"{args.user_prompt}\n\n"
            "Drug of interest: as implied by the question.\n"
            "Patient: Hypothetical teaching case; genotypes illustrative only.\n\n"
            "Explain the pharmacogenomic implication in plain language for a research "
            "protocol briefing. Cite uncertainty and next verification steps."
        )

    messages = [
        {"role": "system", "content": args.system_prompt},
        {"role": "user", "content": user_content},
    ]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    gen_kw: dict = {"max_new_tokens": args.max_new_tokens}
    if args.temperature and args.temperature > 0:
        gen_kw["do_sample"] = True
        gen_kw["temperature"] = args.temperature
        gen_kw["top_p"] = args.top_p
    if args.repetition_penalty and args.repetition_penalty != 1.0:
        gen_kw["repetition_penalty"] = args.repetition_penalty
    with torch.no_grad():
        out = model.generate(**inputs, **gen_kw)
    print(tokenizer.decode(out[0], skip_special_tokens=True))


if __name__ == "__main__":
    main()
