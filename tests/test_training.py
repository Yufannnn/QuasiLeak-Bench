import importlib.util
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_examples", ROOT / "training" / "build_examples.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def test_drawn_policies_partition_attributes_with_a_hide():
    rng = random.Random(0)
    for _ in range(50):
        policy = build.draw_policy(rng)
        assert sorted(a for c in policy.values() for a in c) == sorted(build.ATTRIBUTES)
        assert policy["hide"]


def test_answer_lists_hide_groups_only():
    row = {
        "policy": {"hide": ["age"], "keep": ["gender"], "neutral": []},
        "gold": {
            "spans": [
                {"span_id": "s1", "text": "a b", "start": 0, "end": 3},
                {"span_id": "s2", "text": "c d", "start": 4, "end": 7},
                {"span_id": "s3", "text": "e f", "start": 8, "end": 11},
                {"span_id": "s4", "text": "g h", "start": 12, "end": 15},
            ],
            "groups": [
                {"attribute": "gender", "cue_ids": ["s3", "s4"]},
                {"attribute": "age", "cue_ids": ["s1", "s2"]},
            ],
        },
    }
    assert [g["attribute"] for g in build.answer(row)["evidence"]] == ["age"]
    assert build.answer(row)["evidence"][0]["spans"] == ["a b", "c d"]


def test_split_is_profile_disjoint():
    split = json.loads((ROOT / "training" / "split.json").read_text(encoding="utf-8"))
    sides = [set(split[s]) for s in ("train", "dev", "test")]
    assert [len(s) for s in sides] == [350, 50, 100]
    assert not (sides[0] & sides[1] or sides[0] & sides[2] or sides[1] & sides[2])
