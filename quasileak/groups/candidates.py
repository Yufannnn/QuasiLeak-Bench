"""Candidate representation and complementary-pair prioritization."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import combinations


@dataclass
class Candidate:
    cue: str
    hints_at: str
    also_fits: list[str]
    mechanism: str = ""
    alone_top3: list[str] = field(default_factory=list)
    alone_rank: int = 99
    alone_confidence: float = 0.0
    alone_reasoning: str = ""
    drops_at_singleton: bool | None = None
    singleton_drop_reason: str = ""
    also_leaks: list[dict] = field(default_factory=list)


def _rank_risk(c: Candidate) -> int:
    """How close the cue alone came to naming the truth: 3 for rank 1 down to 0 when absent."""
    return {1: 3, 2: 2, 3: 1}.get(c.alone_rank, 0)


def _norm_fit_value(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _alternative_overlap_size(a: Candidate, b: Candidate, truth: str = "") -> int:
    truth_norm = _norm_fit_value(truth)
    a_alts = {_norm_fit_value(x) for x in a.also_fits or [] if _norm_fit_value(x) and _norm_fit_value(x) != truth_norm}
    b_alts = {_norm_fit_value(x) for x in b.also_fits or [] if _norm_fit_value(x) and _norm_fit_value(x) != truth_norm}
    return len(a_alts & b_alts)


def candidate_pairs(
    surviving: list[Candidate], *, truth: str = "", max_pairs: int = 24
) -> list[tuple[Candidate, Candidate]]:
    if len(surviving) < 2 or max_pairs <= 0:
        return []
    selected: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()

    for i in range(0, len(surviving) - 1, 2):
        seen.add((i, i + 1))
        selected.append((i, i + 1))
    remaining = [pair for pair in combinations(range(len(surviving)), 2) if pair not in seen]

    def sort_key(pair: tuple[int, int]) -> tuple[int, int, int, float, int]:
        i, j = pair
        a, b = surviving[i], surviving[j]
        same_mech = int(
            bool(a.mechanism and b.mechanism) and a.mechanism.strip().lower() == b.mechanism.strip().lower()
        )
        risk_score = _rank_risk(a) + _rank_risk(b)
        confidence_score = float(a.alone_confidence or 0.0) + float(b.alone_confidence or 0.0)
        return _alternative_overlap_size(a, b, truth), same_mech, risk_score, confidence_score, abs(i - j)

    selected.extend(sorted(remaining, key=sort_key))
    selected = selected[:max_pairs]
    return [(surviving[i], surviving[j]) for i, j in selected]
