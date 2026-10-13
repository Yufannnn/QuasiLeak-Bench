#!/usr/bin/env python3
"""Render the evaluation prompt for any benchmark row.

    python prompts/render.py --dataset data/quasileak_bench_data_full.jsonl --shots 3 --output requests.jsonl
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ATTRIBUTES = ("age", "gender", "nationality", "education", "occupation", "income", "relationship", "health")
DOC_OPEN, DOC_CLOSE = "DOCUMENT\n\n```\n", "\n```\n\nAUTHOR PROFILE"
POLICY_LINES = (("* Hide: ", "hide"), ("* Keep: ", "keep"), ("* Neutral: ", "neutral"))
TARGET = "TARGET CASE\n\n"


def load_template(shots: int) -> dict:
    name = {0: "zero_shot_messages.json", 3: "few_shot_messages.json"}[shots]
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def render_user(row: dict, template_user: str) -> str:
    """The target user message for one benchmark row."""
    user = template_user
    start = user.index(DOC_OPEN) + len(DOC_OPEN)
    end = user.index(DOC_CLOSE, start)
    user = user[:start] + row["document"] + user[end:]

    profile = {key: row["profile"][key] for key in ATTRIBUTES if key in row["profile"]}
    start = user.index("```json\n", user.index("AUTHOR PROFILE")) + len("```json\n")
    end = user.index("\n```", start)
    user = user[:start] + json.dumps(profile, ensure_ascii=False, separators=(",", ":")) + user[end:]

    for prefix, key in POLICY_LINES:
        start = user.index(prefix)
        end = user.index("\n", start)
        user = user[:start] + prefix + (", ".join(row["policy"][key]) or "(none)") + user[end:]
    return user


def render(row: dict, shots: int = 3) -> list[dict]:
    """The full message list for one row: system, any solved examples, then the target."""
    template = load_template(shots)
    messages = [dict(m) for m in template["messages"][:-1]]
    messages.append({"role": "user", "content": TARGET + render_user(row, template["user"])})
    return messages


def read_jsonl(path):
    with (gzip.open if str(path).endswith(".gz") else open)(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", required=True, help="quasileak_bench_data_full.jsonl or quasileak_bench_data_1k.jsonl, optionally gzipped")
    ap.add_argument("--shots", type=int, choices=(0, 3), default=3)
    ap.add_argument("--output", required=True, help="JSONL of rendered requests")
    args = ap.parse_args()
    with open(args.output, "w", encoding="utf-8", newline="\n") as fh:
        for row in read_jsonl(args.dataset):
            fh.write(json.dumps({"sample_id": row["sample_id"], "messages": render(row, args.shots)},
                                ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
