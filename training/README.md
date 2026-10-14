# Fine-tuning

The recipe behind the paper's fine-tuned Qwen3.5-4B. The split is by profile: 350 profiles
for training, 50 for development, 100 for test (`split.json`).

```bash
pip install -e ".[train]"
python training/build_examples.py --dataset data/quasileak_bench_data_full.jsonl --out training/out
python training/train_lora.py --model-id Qwen/Qwen3.5-4B --train training/out/train_A.jsonl \
    --dev training/out/dev_A.jsonl --out training/runs/A_s1 --epochs 3 --seed 1 --merge
python training/train_lora.py --model-id Qwen/Qwen3.5-4B --train training/out/train_B.jsonl \
    --dev training/out/dev_A.jsonl --out training/runs/B_s1 --epochs 1 --seed 1 --merge
```

| | own policy (A) | + reassigned policies (B) |
|---|---|---|
| training examples | 3,500 | 10,500 |
| epochs | 3 | 1 |
| seeds | 1, 2, 3 | 1, 2, 3 |

Both use LoRA rank 16, alpha 32, dropout 0.05 on all linear layers, learning rate 1e-4 with a cosine
schedule and 3% warmup, effective batch 16, and the final epoch's adapter.

To evaluate, render `training/out/test.jsonl` with `prompts/render.py --shots 0`,
decode greedily with thinking off and up to 2,048 new tokens, and score against `training/out/test.jsonl`.
