"""Curation to the target arity mix, and placement targets (Algorithm 2, Curate)."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict

from .keys import cue_key, nested, reuse_key
from .search import Group, SearchResult

DISTANCES = ("NEAR", "MEDIUM", "FAR")


def curate(
    results: dict[tuple[str, str], SearchResult], config, prior_use: Counter | None = None
) -> dict[tuple[str, str], Group]:
    """Select one verified group per (sample, attribute) to the target arity mix."""
    used = Counter(prior_use or {})
    doc_cues: dict[str, set[str]] = defaultdict(set)
    doc_phrases: dict[str, list[str]] = defaultdict(list)
    selected: dict[tuple[str, str], Group] = {}

    def admissible(sid: str, group: Group) -> bool:
        keys = [cue_key(c) for c in group.cues]
        return (
            len(set(keys)) == len(keys)
            and all(used[reuse_key(c)] < config.cue_reuse_cap for c in group.cues)
            and not doc_cues[sid] & set(keys)
            and not any(nested(a, b) for i, a in enumerate(group.cues) for b in group.cues[i + 1 :])
            and not any(nested(c, p) for c in group.cues for p in doc_phrases[sid])
        )

    def take(sid: str, attr: str, group: Group) -> None:
        for c in group.cues:
            used[reuse_key(c)] += 1
            doc_cues[sid].add(cue_key(c))
            doc_phrases[sid].append(c)
        selected[sid, attr] = group

    def assign(sid: str, attr: str, result: SearchResult, arities) -> Group | None:
        for k in arities:
            for group in result.of_arity(k, verified=True):
                if admissible(sid, group):
                    take(sid, attr, group)
                    return group
        return None

    by_attr: dict[str, list[tuple[str, SearchResult]]] = defaultdict(list)
    for (sid, attr), result in sorted(results.items()):
        if result.verified:
            by_attr[attr].append((sid, result))

    for attr in sorted(by_attr):
        slots = by_attr[attr]
        target = {4: round(config.quad_fraction * len(slots)), 3: round(config.trio_fraction * len(slots))}
        count: Counter = Counter()
        open_slots = dict(slots)

        strongest_sid, strongest = max(
            ((sid, g) for sid, result in slots for g in result.verified),
            key=lambda x: (x[1].k, x[1].conf, x[0], x[1].cues),
        )
        if admissible(strongest_sid, strongest):
            take(strongest_sid, attr, strongest)
            count[strongest.k] += 1
            del open_slots[strongest_sid]

        for k in (4, 3):
            ranked = sorted(
                (sid for sid, r in open_slots.items() if r.of_arity(k, verified=True)),
                key=lambda sid: (-open_slots[sid].of_arity(k, verified=True)[0].conf, sid),
            )
            for sid in ranked:
                if count[k] >= target[k]:
                    break
                group = assign(sid, attr, open_slots[sid], [k])
                if group:
                    count[k] += 1
                    del open_slots[sid]

        for sid, result in sorted(open_slots.items()):
            group = assign(sid, attr, result, [2, 3, 4])
            if group:
                count[group.k] += 1
    return selected


def placement(sample_id: str, attr: str) -> str:
    """Placement target drawn before writing, uniformly over the three distances."""
    h = int(hashlib.sha256(f"{sample_id}|{attr}|distance".encode()).hexdigest(), 16)
    return DISTANCES[h % 3]
