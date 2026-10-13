from dataclasses import replace

import pytest

from quasileak.pipeline.document_writing import write_documents
from quasileak.pipeline.spans import place
from quasileak.schemas import validate_documents


def test_writer_offsets(grouped, model, config):
    rows = write_documents(grouped, model, config)
    validate_documents(rows, grouped)
    assert rows[0]["plan"]["sets"] == grouped[0]["groups"]
    for span in rows[0]["spans"]:
        assert rows[0]["document"][span["start"] : span["end"]] == span["text"]


@pytest.mark.parametrize(
    "text, placed",
    [
        ("I found the linen invoice today.", True),
        ("Linen invoice papers arrived today.", True),  # capital first letter at a sentence start
        ("Today. Linen invoice papers arrived.", True),
        ("I found the Linen invoice today.", False),  # capital first letter mid-sentence
        ("I found the linen invoices today.", False),  # inside a longer word
        ("The linen invoice and the linen invoice.", False),  # twice
        ("Nothing relevant here.", False),
    ],
)
def test_phrase_placement(text, placed):
    spans, bad = place(text, ["linen invoice"])
    assert (not bad) is placed
    if placed:
        assert text[spans[0]["start"] : spans[0]["end"]].lower() == "linen invoice"


def test_overlapping_phrases():
    spans, bad = place("I kept the tax folder copy.", ["tax folder", "folder copy"])
    assert spans == [] and set(bad) == {"tax folder", "folder copy"}


def test_writer_gives_up(grouped, model, config):
    calls = []

    def omit(**kwargs):
        calls.append(kwargs)
        return "This message has none of the required phrases."

    model.generate = omit
    with pytest.raises(ValueError, match="writer failed"):
        write_documents(grouped, model, replace(config, writer_attempts=3))
    assert len(calls) == 3 and "left out" in calls[1]["user"]


def test_writer_attempt_count(grouped, model, config):
    generate = model.generate
    drafts = []

    def first_draft_misses(**kwargs):
        drafts.append(kwargs)
        text = generate(**kwargs)
        return "Hello, a short note." if len(drafts) == 1 else text

    model.generate = first_draft_misses
    rows = write_documents(grouped, model, config)
    assert rows[0]["writer_attempts"] == 2


def test_bad_offsets(grouped, model, config):
    rows = write_documents(grouped, model, config)
    rows[0]["spans"][0]["end"] += 1
    with pytest.raises(ValueError, match="offsets"):
        validate_documents(rows, grouped)
