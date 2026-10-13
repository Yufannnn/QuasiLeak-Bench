"""Confidence lift, answer spaces, and canonical value matching."""

from __future__ import annotations

BASE: dict[str, float] = {
    "gender": 0.5,
    "income": 0.25,
    "relationship": 0.167,
    "age": 0.11,
    "education": 0.14,
    "health": 0.14,
    "nationality": 0.09,
    "occupation": 0.09,
}
_DEFAULT_BASE = 0.1
RELATIONSHIP_CANONICAL: dict[str, str] = {
    "single": "single",
    "married": "married",
    "engaged": "engaged",
    "divorced": "divorced",
    "widowed": "widowed",
    "in a relationship": "in a relationship",
    "in a long-term relationship": "in a relationship",
    "in a long term relationship": "in a relationship",
    "long-term relationship": "in a relationship",
}
_GENDER_CANONICAL: dict[str, str] = {
    "m": "male",
    "male": "male",
    "man": "male",
    "boy": "male",
    "f": "female",
    "female": "female",
    "woman": "female",
    "girl": "female",
}


def _canon_income(v: str) -> str:
    if "very high" in v or "very-high" in v:
        return "very high income"
    if "middle" in v or "medium" in v or "moderate" in v:
        return "middle income"
    if "high" in v:
        return "high income"
    if "low" in v:
        return "low income"
    return v


def canonical_value(attr: str, value: str) -> str:
    v = " ".join(str(value or "").strip().lower().split())
    if attr == "relationship":
        return RELATIONSHIP_CANONICAL.get(v, v)
    if attr == "income":
        return _canon_income(v)
    if attr == "gender":
        return _GENDER_CANONICAL.get(v, v)
    return v


CLOSED_SET_VALUES: dict[str, frozenset] = {
    "gender": frozenset({"male", "female"}),
    "income": frozenset({"low income", "middle income", "high income", "very high income"}),
    "relationship": frozenset({"single", "married", "engaged", "divorced", "widowed", "in a relationship"}),
}


def is_closed_set(attr) -> bool:
    return attr in CLOSED_SET_VALUES


def values_match(attr: str, a: str, b: str) -> bool:
    """Equality of two closed-set values after canonicalization."""
    ca, cb = canonical_value(attr, a), canonical_value(attr, b)
    return bool(ca) and ca == cb


def sanitize_ranked(attr, values) -> list:
    closed = CLOSED_SET_VALUES.get(attr)
    out: list = []
    seen: set = set()
    for v in values or []:
        cv = canonical_value(attr, v)
        if closed is None:
            if not cv or cv in seen:
                continue
            seen.add(cv)
            out.append(v)
            continue
        if not cv or cv not in closed or cv in seen:
            out.append("")
            continue
        seen.add(cv)
        out.append(cv)
    if closed is not None:
        while out and out[-1] == "":
            out.pop()
    return out


TAU_LEAK = 0.45
TAU_REVEAL = 0.5


def base(attr: str) -> float:
    return BASE.get(str(attr).lower().strip(), _DEFAULT_BASE)


def lift(c, attr: str) -> float:
    b = base(attr)
    c = float(c or 0)
    return (c - b) / (1.0 - b) if c > b else 0.0


def leak_bar(attr: str) -> float:
    b = base(attr)
    return b + TAU_LEAK * (1.0 - b)


def reveal_bar(attr: str) -> float:
    b = base(attr)
    return b + TAU_REVEAL * (1.0 - b)


def weak_alone(c, attr: str) -> bool:
    """A single cue is weak alone: above chance and below the singleton bar."""
    return 0.0 < lift(c, attr) < TAU_LEAK
