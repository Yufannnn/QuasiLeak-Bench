"""Full construction runs on a synthetic corpus with model faults switched on."""

import json
from collections import Counter

import pytest
from conftest import synthetic_inputs
from simulated_model import SimulatedModel

from quasileak import confidence
from quasileak.config import ConstructionConfig
from quasileak.groups.keys import nested, reuse_key
from quasileak.pipeline.cue_mining import mine_cues
from quasileak.pipeline.document_writing import write_documents
from quasileak.pipeline.group_construction import construct_groups
from quasileak.schemas import validate_documents, validate_grouped


def build(profiles, contexts, seed, previous=None):
    config = ConstructionConfig()
    model = SimulatedModel(seed=seed, faults=True)
    grouped = construct_groups(mine_cues(profiles, contexts, model, config), model, model, config, previous)
    return grouped, write_documents(grouped, model, config)


@pytest.fixture(scope="module")
def corpus():
    profiles, contexts = synthetic_inputs(24, 6, seed=17)
    return (profiles, contexts), *build(profiles, contexts, seed=17)


def test_records_validate(corpus):
    _, grouped, documents = corpus
    config = ConstructionConfig()
    validate_grouped(grouped, config)
    validate_documents(documents, grouped)
    assert len(documents) == 144


def test_corpus_invariants(corpus):
    _, grouped, documents = corpus
    use = Counter(reuse_key(c) for r in grouped for g in r["groups"] for c in g["cues"])
    assert max(use.values()) <= 5
    for row in grouped:
        phrases = [c for g in row["groups"] for c in g["cues"]] + row["decoys"]["selected_spans"]
        assert not any(nested(a, b) for i, a in enumerate(phrases) for b in phrases[i + 1 :])
        assert 2 <= row["decoys"]["n_selected"] <= 4
        for g in row["groups"]:
            assert g["conf"] >= confidence.reveal_bar(g["attr"]) and g["attr"] not in g["secondary_attributes"]
    for doc in documents:
        text = doc["document"]
        for span in doc["spans"]:
            assert text[span["start"] : span["end"]] == span["text"]
            assert (
                not text[span["start"] - 1 : span["start"]].isalnum()
                and not text[span["end"] : span["end"] + 1].isalnum()
            )


def test_arity_mix(corpus):
    _, grouped, _ = corpus
    arity = Counter(g["k"] for r in grouped for g in r["groups"])
    total = sum(arity.values())
    assert abs(arity[2] / total - 0.65) < 0.08 and abs(arity[4] / total - 0.10) < 0.06


def test_writer_retried(corpus):
    _, _, documents = corpus
    assert any(d["writer_attempts"] > 1 for d in documents)


def test_deterministic(corpus):
    (profiles, contexts), grouped, documents = corpus
    again_grouped, again_documents = build(profiles, contexts, seed=17)
    assert json.dumps(again_grouped, sort_keys=True) == json.dumps(grouped, sort_keys=True)
    assert json.dumps(again_documents, sort_keys=True) == json.dumps(documents, sort_keys=True)


def test_second_batch(corpus):
    (_, contexts), grouped, _ = corpus
    more, _ = synthetic_inputs(12, 6, seed=18, prefix="q")
    second, documents = build(more, contexts, seed=18, previous=grouped)
    use = Counter(reuse_key(c) for r in grouped + second for g in r["groups"] for c in g["cues"])
    assert max(use.values()) <= 5 and len(documents) == 72
