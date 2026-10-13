"""Distractor count and selection against the final cue set."""

from __future__ import annotations

import hashlib
import random
from collections import Counter

from .keys import content_tokens, nested, reuse_key

DISTRACTOR_KINDS = ("near-miss", "wrong-direction", "admin-artifact", "jargon", "object", "mundane")
MIN_DISTRACTORS, MAX_DISTRACTORS = 2, 4
COUNT_LAW = "Binomial(8, 0.25) clipped to [2, 4]"


def distractor_count(sample_id: str) -> int:
    rng = random.Random(int(hashlib.sha256(f"{sample_id}|distractors".encode()).hexdigest(), 16))
    draws = sum(rng.random() < 0.25 for _ in range(8))
    return max(MIN_DISTRACTORS, min(MAX_DISTRACTORS, draws))


def eligible(candidate: dict, cue_tokens: set[str]) -> bool:
    return (
        candidate.get("cold_leaks") == []
        and candidate.get("kind") in DISTRACTOR_KINDS
        and not any(content_tokens(s) & cue_tokens for s in candidate["spans"])
    )


def select(ranked: list[dict], n: int, use: Counter, cap: int) -> list[dict] | None:
    """Pick ``n`` distractors: under the reuse cap, at most one wrong-direction, varied kinds."""
    available = [c for c in ranked if all(use[reuse_key(s)] < cap for s in c["spans"])]
    chosen: list[dict] = []
    for c in available:
        if c["kind"] == "wrong-direction" and any(x["kind"] == "wrong-direction" for x in chosen):
            continue
        if any(nested(s, t) for s in c["spans"] for x in chosen for t in x["spans"]):
            continue
        chosen.append(c)
        if len(chosen) == n:
            break
    if len(chosen) < n:
        return None
    if n >= 2 and len({c["kind"] for c in chosen}) == 1:
        head = chosen[:-1]
        swap = next(
            (
                c
                for c in available
                if c not in head
                and c["kind"] != head[0]["kind"]
                and not any(nested(s, t) for s in c["spans"] for x in head for t in x["spans"])
                and not (c["kind"] == "wrong-direction" and any(x["kind"] == "wrong-direction" for x in head))
            ),
            None,
        )
        if swap is not None:
            chosen = head + [swap]
    return chosen


def attach(row: dict, config, use: Counter) -> None:
    """Select this document's distractors from its audited pool and record the plan."""
    sid = row["sample_id"]
    cue_tokens = set().union(*(content_tokens(c) for g in row["groups"] for c in g["cues"]))
    pool = [c for c in row["decoy_candidates"] if eligible(c, cue_tokens)]
    ranked = sorted(pool, key=lambda c: (-c["tempting_score"], c["decoy_id"]))
    n = distractor_count(sid)
    chosen = select(ranked, n, use, config.distractor_reuse_cap)
    if chosen is None:
        raise ValueError(f"{n} distractors required, but the audited pool cannot supply them")
    for c in chosen:
        for s in c["spans"]:
            use[reuse_key(s)] += 1
    row["decoys"] = {
        "n_selected": len(chosen),
        "law": COUNT_LAW,
        "selected_ids": [c["decoy_id"] for c in chosen],
        "selected_spans": [s for c in chosen for s in c["spans"]],
    }
