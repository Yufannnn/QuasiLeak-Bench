import json
from dataclasses import replace

import pytest

from quasileak.groups.keys import cue_key
from quasileak.pipeline.cue_mining import generate_candidates, mine_cues


class Scripted:
    """Returns the scripted replies in order and records every prompt."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    def generate(self, *, system, user, temperature=0.0):
        self.prompts.append(user)
        return json.dumps(self.replies.pop(0))


def cues(*phrases):
    return [dict(cue=p, hints_at="signal", mechanism="axis", also_fits=["other"]) for p in phrases]


def test_mining_is_deterministic(inputs, model, config):
    first = mine_cues(*inputs, model, config)
    assert first == mine_cues(*inputs, model, config)
    assert first[0]["surface_attributes"] == ["occupation"]
    assert first[0]["profile"] == inputs[0][0]["profile"]
    assert first[0]["policy"] == inputs[1][0]["policy"]


def test_no_surfaced_attributes(inputs, model, config):
    config = replace(config, surface_probabilities=dict.fromkeys(config.surface_probabilities, 0.0))
    rows = mine_cues(*inputs, model, config)
    assert len(rows) == 1 and rows[0]["candidates"] == {} and model.calls == 0


def test_retry_excludes_earlier_cues(inputs, config):
    profile, context = inputs[0][0]["profile"], inputs[1][0]
    earlier = {"occupation": {cue_key("tax folder"), cue_key("linen invoice")}}
    client = Scripted(
        {"occupation": cues("Tax-folder", "shift roster")},  # a spelling variant of an earlier cue
        {"occupation": cues("guest billing", "shift roster")},
    )
    reply = generate_candidates(profile, context, ["occupation"], client, config, failures=[], exclude=earlier)
    assert [c["cue"] for c in reply["occupation"]] == ["guest billing", "shift roster"]
    assert len(client.prompts) == 2 and "Return the complete requested JSON" in client.prompts[1]


def test_duplicates_after_normalization(inputs, config):
    profile, context = inputs[0][0]["profile"], inputs[1][0]
    client = Scripted(
        {"occupation": cues("tax folder", "Tax  folder")}, {"occupation": cues("tax folder", "shift roster")}
    )
    reply = generate_candidates(profile, context, ["occupation"], client, config)
    assert len(client.prompts) == 2 and len(reply["occupation"]) == 2


def test_noncompliant_endpoint(inputs, config):
    profile, context = inputs[0][0]["profile"], inputs[1][0]
    client = Scripted(*[{"wrong": []}] * 3)
    with pytest.raises(ValueError, match="Invalid structured"):
        generate_candidates(profile, context, ["occupation"], client, config)


def test_assignments_select_pairs():
    from quasileak.pipeline.cue_mining import assigned_pairs

    profiles = [{"profile_id": "p1"}, {"profile_id": "p2"}]
    contexts = [{"context_id": "c1"}, {"context_id": "c2"}]
    assert len(assigned_pairs(profiles, contexts)) == 4
    pairs = assigned_pairs(profiles, contexts, [{"profile_id": "p2", "context_id": "c1"}])
    assert [(p["profile_id"], c["context_id"]) for p, c in pairs] == [("p2", "c1")]
    with pytest.raises(ValueError, match="unknown"):
        assigned_pairs(profiles, contexts, [{"profile_id": "p3", "context_id": "c1"}])
