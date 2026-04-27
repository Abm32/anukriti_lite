#!/usr/bin/env python3
"""
LoRA supervised fine-tuning on chat JSONL (messages format).

Multi-GPU (e.g. MI300X x8):
  accelerate launch --num_processes 8 training/lm_finetune/train_lora_sft.py \\
    --model_name Qwen/Qwen2.5-7B-Instruct \\
    --dataset_path data/training/pgx_sft.jsonl \\
    --output_dir training_outputs/pgx_lora

Single GPU / CPU debug (tiny subset):
  python training/lm_finetune/train_lora_sft.py --max_steps 10 --model_name ...
"""

from __future__ import annotations

import argparse
import inspect
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import torch
from datasets import Dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_jsonl_messages(path: Path) -> Dataset:
    rows: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if "messages" not in obj:
                continue
            rows.append({"messages": obj["messages"]})
    if not rows:
        raise SystemExit(f"No examples found in {path}")
    return Dataset.from_list(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--model_name",
        type=str,
        default="Qwen/Qwen2.5-7B-Instruct",
        help="HF hub id (use an instruct/chat model with apply_chat_template).",
    )
    ap.add_argument(
        "--dataset_path",
        type=Path,
        default=Path("data/training/pgx_sft.jsonl"),
    )
    ap.add_argument(
        "--output_dir",
        type=Path,
        default=Path("training_outputs/pgx_lora"),
    )
    ap.add_argument("--num_train_epochs", type=float, default=1.0)
    ap.add_argument("--per_device_train_batch_size", type=int, default=1)
    ap.add_argument("--gradient_accumulation_steps", type=int, default=8)
    ap.add_argument("--learning_rate", type=float, default=2e-4)
    ap.add_argument("--max_seq_length", type=int, default=2048)
    ap.add_argument("--lora_r", type=int, default=16)
    ap.add_argument("--lora_alpha", type=int, default=32)
    ap.add_argument("--lora_dropout", type=float, default=0.05)
    ap.add_argument("--max_steps", type=int, default=-1)
    ap.add_argument(
        "--logging_steps",
        type=int,
        default=10,
        help="Log metrics every N steps.",
    )
    ap.add_argument(
        "--save_steps",
        type=int,
        default=200,
        help="Save a checkpoint every N optimizer steps.",
    )
    ap.add_argument(
        "--save_total_limit",
        type=int,
        default=2,
        help="Max checkpoints to keep on disk.",
    )
    ap.add_argument(
        "--use_4bit",
        action="store_true",
        help="QLoRA-style 4-bit load (requires bitsandbytes compatible with your platform).",
    )
    args = ap.parse_args()

    if not args.dataset_path.is_file():
        raise SystemExit(
            f"Dataset not found: {args.dataset_path}. "
            "Run: python training/lm_finetune/export_pgx_sft_jsonl.py"
        )

    tokenizer = AutoTokenizer.from_pretrained(args.model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quant_kwargs = {}
    if args.use_4bit:
        from transformers import BitsAndBytesConfig

        quant_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        quant_kwargs["device_map"] = "auto"

    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        **quant_kwargs,
    )

    peft_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=(
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ),
    )

    dataset = load_jsonl_messages(args.dataset_path)

    def formatting_func(example: Dict[str, Any]) -> str:
        msgs: List[Dict[str, str]] = example["messages"]
        return tokenizer.apply_chat_template(
            msgs,
            tokenize=False,
            add_generation_prompt=False,
        )

    sft_params = inspect.signature(SFTConfig.__init__).parameters
    sft_kw: Dict[str, Any] = {
        "output_dir": str(args.output_dir),
        "num_train_epochs": args.num_train_epochs,
        "per_device_train_batch_size": args.per_device_train_batch_size,
        "gradient_accumulation_steps": args.gradient_accumulation_steps,
        "learning_rate": args.learning_rate,
        "logging_steps": args.logging_steps,
        "save_steps": args.save_steps,
        "save_total_limit": args.save_total_limit,
        "bf16": True,
        "gradient_checkpointing": True,
        "report_to": "none",
        "max_steps": args.max_steps if args.max_steps > 0 else -1,
    }
    if "max_seq_length" in sft_params:
        sft_kw["max_seq_length"] = args.max_seq_length
        sft_kw["dataset_text_field"] = None
    elif "max_length" in sft_params:
        sft_kw["max_length"] = args.max_seq_length
    # TRL 1.x: assistant_only_loss=True requires chat_template to contain
    # `{% generation %}` for assistant token masking. Qwen2.5 templates often do not,
    # which raises at tokenize time — only enable when supported.
    if "assistant_only_loss" in sft_params:
        tpl = getattr(tokenizer, "chat_template", None) or ""
        supports_assistant_masks = "{% generation %}" in tpl
        sft_kw["assistant_only_loss"] = supports_assistant_masks
        if not supports_assistant_masks:
            logger.info(
                "Chat template has no {% generation %} block; training with "
                "assistant_only_loss=False (full-sequence LM loss on formatted chat)."
            )
    sft_kw = {k: v for k, v in sft_kw.items() if k in sft_params}
    training_args = SFTConfig(**sft_kw)

    tr_sig = inspect.signature(SFTTrainer.__init__).parameters
    tr_kw: Dict[str, Any] = {
        "model": model,
        "args": training_args,
        "train_dataset": dataset,
        "peft_config": peft_config,
        "formatting_func": formatting_func,
    }
    if "processing_class" in tr_sig:
        tr_kw["processing_class"] = tokenizer
    elif "tokenizer" in tr_sig:
        tr_kw["tokenizer"] = tokenizer
    else:
        raise SystemExit(
            "Installed trl.SFTTrainer has neither processing_class nor tokenizer; upgrade/downgrade trl."
        )
    trainer = SFTTrainer(**tr_kw)
    trainer.train()
    trainer.save_model(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))
    logger.info("Saved adapter + tokenizer to %s", args.output_dir)


if __name__ == "__main__":
    main()
