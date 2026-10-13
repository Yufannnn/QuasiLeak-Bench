"""Phrase keys: exact strings for corpus reuse caps, normalized keys for overlap checks."""

from __future__ import annotations

import re
import unicodedata

_STOPWORDS = frozenset(
    "a an the of in on at to for and or but with without your my our their his her its this that "
    "these those is are was were be been being as by from into over under about after before out "
    "up down i you we they it he she do does need want get got have has had will would can could "
    "please so if then than also just only more most some any each per via re not no".split()
)


def cue_key(text: str) -> str:
    """Normalized key for duplicate and overlap checks, so spelling and spacing variants match."""
    text = unicodedata.normalize("NFKC", str(text)).casefold()
    text = re.sub(r"[‐-―_/-]+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(text.split())


def reuse_key(text: str) -> str:
    """Key for the corpus reuse caps: each exact phrase counts on its own."""
    return str(text).strip()


def nested(a: str, b: str) -> bool:
    """Whether one phrase occurs inside the other as whole words, so both cannot appear exactly once."""
    ka, kb = f" {cue_key(a)} ", f" {cue_key(b)} "
    return ka in kb or kb in ka


def content_tokens(text: str) -> set[str]:
    return {w for w in re.sub(r"[^a-z0-9]+", " ", str(text).lower()).split() if len(w) >= 3 and w not in _STOPWORDS}
