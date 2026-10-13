#!/usr/bin/env python3
"""Training examples for the fine-tuning study.

    python training/build_examples.py --dataset data/quasileak_bench_data_full.jsonl --out training/out
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("render", HERE.parent / "prompts" / "render.py")
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)

ATTRIBUTES = ("age", "gender", "nationality", "income", "relationship", "health", "education", "occupation")
CLASSES = ("keep", "hide", "neutral")


def draw_policy(rng: random.Random) -> dict[str, list[str]]:
    while True:
        label = {a: rng.choice(CLASSES) for a in ATTRIBUTES}
        if "hide" in label.values():
            return {c: [a for a in ATTRIBUTES if label[a] == c] for c in CLASSES}


def answer(row: dict) -> dict:
    spans = {s["span_id"]: s for s in row["gold"]["spans"]}
    hide = set(row["policy"]["hide"])
    groups = [g for g in row["gold"]["groups"] if g["attribute"] in hide]
    return {"evidence": [{
        "attribute": g["attribute"],
        "spans": [spans[c]["text"] for c in g["cue_ids"]],
        "rationale": f"Alone each span is weak; together the {len(g['cue_ids'])} cues support the hidden {g['attribute']} value.",
    } for g in groups]}


def example(row: dict, condition: str, index: int) -> dict:
    target = answer(row)
    messages = render.render(row, shots=0) + [{"role": "assistant", "content": json.dumps(target, ensure_ascii=False, indent=2)}]
    return {"id": f"{row['sample_id']}#{condition}{index}", "n_hidden_groups": len(target["evidence"]), "messages": messages}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", required=True, help="quasileak_bench_data_full.jsonl")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    split = json.loads((HERE / "split.json").read_text(encoding="utf-8"))
    side_of = {p: side for side in ("train", "dev", "test") for p in split[side]}
    rng = random.Random(split["seed"])
    out = {name: [] for name in ("train_A", "train_B", "dev_A", "dev", "test")}
    for row in render.read_jsonl(args.dataset):
        side = side_of[row["profile"]["profile_id"]]
        if side == "train":
            out["train_A"].append(example(row, "A", 0))
            out["train_B"].append(example(row, "B", 0))
            for i in (1, 2):
                out["train_B"].append(example({**row, "policy": draw_policy(rng)}, "B", i))
            continue
        if side == "dev":
            out["dev_A"].append(example(row, "A", 0))
        out[side].append(row)
        draw_policy(rng)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, rows in out.items():
        with open(args.out / f"{name}.jsonl", "w", encoding="utf-8", newline="\n") as fh:
            fh.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        print(name, len(rows))


if __name__ == "__main__":
    main()
