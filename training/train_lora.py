#!/usr/bin/env python3
"""LoRA fine-tuning with loss on the answer tokens only."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import torch
from torch.utils.data import Dataset


def ids_of(x):
    if hasattr(x, "input_ids"):
        x = x["input_ids"]
    if isinstance(x, torch.Tensor):
        x = x.tolist()
    if x and isinstance(x[0], list):
        x = x[0]
    return [int(t) for t in x]


class AnswerOnly(Dataset):
    def __init__(self, path: Path, tok, max_len: int):
        self.items = []
        for line in open(path, encoding="utf-8"):
            messages = json.loads(line)["messages"]
            prompt = ids_of(tok.apply_chat_template(messages[:-1], tokenize=True, add_generation_prompt=True))
            full = ids_of(tok.apply_chat_template(messages, tokenize=True, add_generation_prompt=False))
            if full[:len(prompt)] != prompt or len(full) <= len(prompt):
                eos = tok.eos_token_id if tok.eos_token_id is not None else tok.pad_token_id
                full = prompt + ids_of(tok(messages[-1]["content"], add_special_tokens=False)) + [eos]
            if len(full) > max_len:
                raise SystemExit(f"an example exceeds --max-len {max_len}; raise the limit rather than truncate")
            self.items.append({"input_ids": full, "labels": [-100] * len(prompt) + full[len(prompt):]})

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        return self.items[i]


def collator(pad_id: int):
    def collate(batch):
        n = max(len(b["input_ids"]) for b in batch)
        ids = torch.full((len(batch), n), pad_id, dtype=torch.long)
        labels = torch.full((len(batch), n), -100, dtype=torch.long)
        mask = torch.zeros((len(batch), n), dtype=torch.long)
        for i, b in enumerate(batch):
            k = len(b["input_ids"])
            ids[i, :k], labels[i, :k], mask[i, :k] = torch.tensor(b["input_ids"]), torch.tensor(b["labels"]), 1
        return {"input_ids": ids, "labels": labels, "attention_mask": mask}
    return collate


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--train", type=Path, required=True)
    ap.add_argument("--dev", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--alpha", type=int, default=32)
    ap.add_argument("--dropout", type=float, default=0.05)
    ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--max-len", type=int, default=4096)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--merge", action="store_true", help="also save the merged model")
    args = ap.parse_args()

    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    tok = AutoTokenizer.from_pretrained(args.model_id, trust_remote_code=True)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    train = AnswerOnly(args.train, tok, args.max_len)
    dev = AnswerOnly(args.dev, tok, args.max_len) if args.dev else None

    model = AutoModelForCausalLM.from_pretrained(args.model_id, dtype=torch.bfloat16, trust_remote_code=True,
                                                 attn_implementation="sdpa")
    model.config.use_cache = False
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(r=args.rank, lora_alpha=args.alpha, lora_dropout=args.dropout,
                                             target_modules="all-linear", task_type="CAUSAL_LM"))
    training = TrainingArguments(
        output_dir=str(args.out / "checkpoints"), num_train_epochs=args.epochs, learning_rate=args.lr,
        per_device_train_batch_size=args.batch, gradient_accumulation_steps=args.grad_accum,
        per_device_eval_batch_size=args.batch, bf16=True, logging_steps=10, lr_scheduler_type="cosine",
        warmup_ratio=0.03, weight_decay=0.0, seed=args.seed, save_strategy="epoch", save_total_limit=4,
        eval_strategy="epoch" if dev else "no", report_to=[], remove_unused_columns=False,
        gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False},
        dataloader_num_workers=2, optim="adamw_torch",
    )
    Trainer(model=model, args=training, train_dataset=train, eval_dataset=dev,
            data_collator=collator(tok.pad_token_id)).train()
    model.save_pretrained(str(args.out / "adapter"))
    tok.save_pretrained(str(args.out / "adapter"))
    if args.merge:
        merged = model.merge_and_unload()
        merged.save_pretrained(str(args.out / "merged"), safe_serialization=True)
        tok.save_pretrained(str(args.out / "merged"))


if __name__ == "__main__":
    main()
