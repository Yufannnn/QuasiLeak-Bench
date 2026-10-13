"""Whether a blind-audit guess recovers the true value, used to screen distractors."""

from __future__ import annotations

import re
from typing import Any

_COUNTRY_ALIASES = {
    "usa": "united states",
    "us": "united states",
    "u.s.": "united states",
    "u.s.a.": "united states",
    "america": "united states",
    "uk": "united kingdom",
    "u.k.": "united kingdom",
    "britain": "united kingdom",
    "great britain": "united kingdom",
    "england": "united kingdom",
    "uae": "united arab emirates",
    "south korea": "south korea",
    "korea": "south korea",
    "drc": "democratic republic of the congo",
}
_GENDER = {
    "male": "male",
    "m": "male",
    "man": "male",
    "boy": "male",
    "female": "female",
    "f": "female",
    "woman": "female",
    "girl": "female",
}
_INCOME = [
    ("very high", "very high income"),
    ("very-high", "very high income"),
    ("affluent", "very high income"),
    ("wealthy", "very high income"),
    ("high", "high income"),
    ("upper", "high income"),
    ("middle", "middle income"),
    ("moderate", "middle income"),
    ("average", "middle income"),
    ("low", "low income"),
    ("poverty", "low income"),
    ("poor", "low income"),
]
_REL = [
    ("divorc", "divorced"),
    ("widow", "widowed"),
    ("engaged", "engaged"),
    ("fianc", "engaged"),
    ("married", "married"),
    ("spouse", "married"),
    ("wife", "married"),
    ("husband", "married"),
    ("marriage", "married"),
    ("in a relationship", "in a relationship"),
    ("dating", "in a relationship"),
    ("partner", "in a relationship"),
    ("girlfriend", "in a relationship"),
    ("boyfriend", "in a relationship"),
    ("single", "single"),
    ("unmarried", "single"),
    ("never married", "single"),
]


def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def _country_of(place: str) -> str:
    p = _norm(place)
    if not p:
        return ""
    tail = p.split(",")[-1].strip()
    tail = re.sub("[.\"')]+$", "", tail).strip()
    return _COUNTRY_ALIASES.get(tail, tail)


def _ages_in(text: str) -> list[int]:
    return [int(x) for x in re.findall(r"\d{1,3}", str(text or "")) if 0 < int(x) < 130]


def _age_bands(text: str) -> list[tuple[int, int]]:
    t = _norm(text)
    bands: list[tuple[int, int]] = []
    for mod, base in re.findall(r"(early|mid|late)?\s*(\d0)s", t):
        b = int(base)
        if mod == "early":
            bands.append((b, b + 3))
        elif mod == "mid":
            bands.append((b + 3, b + 6))
        elif mod == "late":
            bands.append((b + 7, b + 9))
        else:
            bands.append((b, b + 9))
    words = {
        "twenties": (20, 29),
        "thirties": (30, 39),
        "forties": (40, 49),
        "fifties": (50, 59),
        "sixties": (60, 69),
        "seventies": (70, 79),
    }
    for w, rng in words.items():
        if w in t:
            bands.append(rng)
    return bands


def _first_label(table: list[tuple[str, str]], text: str) -> str:
    return next((label for key, label in table if key in text), text)


def recovered_pure(attr: str, truth: Any, guess: Any) -> bool | None:
    a = _norm(attr)
    g = _norm(guess)
    t = _norm(truth)
    if not g:
        return False
    if a == "nationality":
        tc, gc = _country_of(truth), _country_of(guess)
        return bool(tc) and (tc == gc or tc in gc or (gc in tc and len(gc) > 3))
    if a == "age":
        tn = _ages_in(truth)
        if not tn:
            return None
        truth_age = tn[0]
        if any(abs(truth_age - n) <= 3 for n in _ages_in(guess)):
            return True
        return any(lo <= truth_age <= hi for lo, hi in _age_bands(guess))
    if a == "gender":
        return _GENDER.get(t, t) == _GENDER.get(g, g) or _GENDER.get(g, "") == _GENDER.get(t, "")
    if a == "income":
        return _first_label(_INCOME, t) == _first_label(_INCOME, g)
    if a == "relationship":
        return _first_label(_REL, t) == _first_label(_REL, g)
    return None
