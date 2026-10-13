"""Locate required phrases in a written document."""

from __future__ import annotations

import re

_SHORT_WORDS = 8


def _starts_sentence(doc: str, start: int) -> bool:
    before = doc[:start].rstrip(" \t")
    return not before or before[-1] in ".!?\n"


def occurrences(doc: str, phrase: str) -> list[tuple[int, str]]:
    """Whole-word occurrences of ``phrase`` as (start, text), including a sentence-initial capital."""
    variants = {phrase}
    capital = phrase[:1].upper() + phrase[1:]
    if capital != phrase:
        variants.add(capital)
    pattern = r"(?<!\w)(?:" + "|".join(re.escape(v) for v in sorted(variants)) + r")(?!\w)"
    found = []
    for m in re.finditer(pattern, doc):
        if m.group(0) != phrase and not _starts_sentence(doc, m.start()):
            continue
        found.append((m.start(), m.group(0)))
    return found


def place(doc: str, phrases: list[str]) -> tuple[list[dict], list[str]]:
    """Spans for phrases placed exactly once, and the phrases that are missing, repeated, or overlapping."""
    spans, bad = [], []
    for phrase in phrases:
        hits = occurrences(doc, phrase)
        if len(hits) != 1:
            bad.append(phrase)
            continue
        start, text = hits[0]
        spans.append(dict(planned_text=phrase, text=text, start=start, end=start + len(text)))
    ordered = sorted(spans, key=lambda s: s["start"])
    for left, right in zip(ordered, ordered[1:]):
        if left["end"] > right["start"]:
            bad.extend(s["planned_text"] for s in (left, right) if s["planned_text"] not in bad)
    if bad:
        return [], bad
    return spans, []


def short_cue_sentences(doc: str, cues: list[str]) -> list[str]:
    """Sentences under eight words that carry a cue."""
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+", doc):
        sentence = sentence.strip()
        if sentence and len(sentence.split()) < _SHORT_WORDS and any(occurrences(sentence, c) for c in cues):
            out.append(sentence)
    return out
