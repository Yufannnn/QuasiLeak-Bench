import json

import pytest

from quasileak.pipeline.inputs import assign, parse_census, parse_compatibility, route, score_pairs

PASS = {f"P{i}": "PASS" for i in range(1, 6)}


def verdict(**fails):
    return {**PASS, **{k: "FAIL" for k in fails}}


def test_census_routing():
    assert route([PASS, PASS]) == "accept"
    assert route([verdict(P2=1), verdict(P2=1)]) == "reject"
    assert route([verdict(P2=1), PASS]) == "human_review"
    assert route([verdict(P4=1), verdict(P5=1)]) == "accept"
    assert route([PASS, None]) == "human_review"


def test_census_parsing():
    assert parse_census('noise {"P1": "PASS", "P2": "PASS", "P3": "FAIL", "P4": "PASS", "P5": "PASS", "reasons": {}}') == verdict(P3=1)
    assert parse_census('{"P1": "maybe"}') is None


def test_compatibility_score_is_criteria_met():
    rubric = {f"R{i}": int(i <= 7) for i in range(1, 11)}
    reply = json.dumps({"c1": {"score": 3, "rubric": rubric}, "c2": {"score": 6}})
    assert parse_compatibility(reply) == {"c1": 7, "c2": 6}


class Judge:
    def __init__(self, scores):
        self.scores = scores

    def generate(self, *, system, user):
        return json.dumps({c: {"score": s} for c, s in self.scores.items()})


def test_consensus_is_mean_times_ten():
    profiles = [{"profile_id": "p1", "profile": {"age": "30"}}]
    contexts = [{"context_id": "c1", "name": "x"}]
    scores = score_pairs(profiles, contexts, [Judge({"c1": 6}), Judge({"c1": 8}), Judge({"c1": 7})])
    assert scores == {("p1", "c1"): pytest.approx(70.0)}


def test_assignment_meets_quotas_and_maximizes_fit():
    pytest.importorskip("scipy")
    profiles, contexts = ["p1", "p2", "p3", "p4"], ["c1", "c2"]
    scores = {(p, c): (90.0 if c == "c1" else 10.0) for p in profiles for c in contexts}
    rows = assign(scores, profiles, contexts, per_profile=1, slack=1)
    counts = {c: sum(r["context_id"] == c for r in rows) for c in contexts}
    assert len(rows) == 4 and counts == {"c1": 3, "c2": 1}
