"""Group search for one attribute of one document, pairs first, then trios and quads by extension."""

from __future__ import annotations

from dataclasses import dataclass, field

from .. import confidence
from .keys import reuse_key


@dataclass(frozen=True)
class Group:
    attr: str
    cues: tuple[str, ...]
    conf: float
    base: tuple[str, ...] = ()
    base_conf: float | None = None
    src: str = "pair"  # "pair", or the kind of base extended: "promising" / "verified"

    @property
    def k(self) -> int:
        return len(self.cues)


@dataclass
class SearchResult:
    verified: list[Group] = field(default_factory=list)
    promising: list[Group] = field(default_factory=list)

    def of_arity(self, k: int, *, verified: bool) -> list[Group]:
        pool = self.verified if verified else self.promising
        return sorted((g for g in pool if g.k == k), key=lambda g: (-g.conf, g.cues))


def joint_bar(attr: str) -> float:
    return confidence.reveal_bar(attr)


def is_promising(attr: str, score: float) -> bool:
    return confidence.base(attr) <= score < joint_bar(attr)


def diagnostic(record: dict, attr: str) -> dict:
    return next(d for d in record["diagnostics"] if d["attribute"] == attr)


def weak_pool(record: dict, attr: str) -> list[str]:
    """Weak-alone cues of the attribute, strongest singleton score first."""
    kept = [c for c in diagnostic(record, attr)["candidates"] if not c["drops_at_singleton"]]
    return [c["cue"] for c in sorted(kept, key=lambda c: (-c["alone_confidence"], c["cue"]))]


def pair_groups(record: dict, attr: str) -> SearchResult:
    result = SearchResult()
    weak = set(weak_pool(record, attr))
    for pair in diagnostic(record, attr)["pairs"]:
        cues = (pair["cue_a"], pair["cue_b"])
        if not set(cues) <= weak:
            continue
        group = Group(attr, cues, pair["joint_confidence"])
        if pair["joint_rank"] == 1 and pair["joint_confidence"] >= joint_bar(attr):
            result.verified.append(group)
        elif is_promising(attr, pair["joint_confidence"]):
            result.promising.append(group)
    return result


def search_attribute(record: dict, attr: str, probe, config, used: dict[str, int]) -> SearchResult:
    """Run the pair, trio, and quad search for one attribute."""
    result = pair_groups(record, attr)
    pool = weak_pool(record, attr)
    probed: set[frozenset[str]] = {frozenset(g.cues) for g in result.verified + result.promising}

    def extend(base: Group) -> None:
        options = [c for c in pool if c not in base.cues and used.get(reuse_key(c), 0) < config.cue_reuse_cap]
        for cue in options[: config.extensions_per_base]:
            cues = base.cues + (cue,)
            if frozenset(cues) in probed:
                continue
            probed.add(frozenset(cues))
            score = probe(attr, list(cues))
            kind = "verified" if base.conf >= joint_bar(attr) else "promising"
            group = Group(attr, cues, score, base.cues, base.conf, kind)
            if score >= joint_bar(attr):
                result.verified.append(group)
                return
            if is_promising(attr, score):
                result.promising.append(group)

    for k in (3, 4):
        bases = (
            result.of_arity(k - 1, verified=False)[: config.promising_bases]
            + result.of_arity(k - 1, verified=True)[: config.verified_bases]
        )
        for base in bases:
            if all(used.get(reuse_key(c), 0) < config.cue_reuse_cap for c in base.cues):
                extend(base)
    return result
