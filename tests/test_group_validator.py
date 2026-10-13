import copy

import pytest

from quasileak.schemas import validate_grouped


def corrupt(row, damage):
    group = row["groups"][0]
    cues = group["cues"]
    if damage == "foreign cue":
        cues[0] = "a phrase nobody probed"
    elif damage == "score":
        group["conf"] = 0.1
    elif damage == "arity":
        group["k"] = 4 if group["k"] != 4 else 2
    elif damage == "placement":
        group["dist"] = "ADJACENT"
    elif damage == "secondary":
        group["secondary_attributes"] = ["income"]
    elif damage == "audit":
        row["secondary_audits"] = row["secondary_audits"][1:]
    elif damage == "self-revealing cue":
        pool = next(d for d in row["diagnostics"] if d["attribute"] == group["attr"])["candidates"]
        next(c for c in pool if c["cue"] == cues[0])["alone_confidence"] = 0.99
    elif damage == "distractor count":
        row["decoys"]["selected_ids"] = row["decoys"]["selected_ids"][:1]
        row["decoys"]["selected_spans"] = row["decoys"]["selected_spans"][:1]
    elif damage == "leaking distractor":
        chosen = row["decoys"]["selected_ids"][0]
        next(d for d in row["decoy_candidates"] if d["decoy_id"] == chosen)["cold_leaks"] = [{"case": "singleton"}]
    elif damage == "distractor overlaps cue":
        chosen = row["decoys"]["selected_ids"][0]
        candidate = next(d for d in row["decoy_candidates"] if d["decoy_id"] == chosen)
        candidate["spans"] = [cues[0].split()[-1] + " sticker"]
        row["decoys"]["selected_spans"][0] = candidate["spans"][0]
    elif damage == "accepted plan":
        row["accepted_attributes"] = []


DAMAGES = [
    "foreign cue",
    "score",
    "arity",
    "placement",
    "secondary",
    "audit",
    "self-revealing cue",
    "distractor count",
    "leaking distractor",
    "distractor overlaps cue",
    "accepted plan",
]


@pytest.mark.parametrize("damage", DAMAGES)
def test_rejects_corruption(grouped, config, damage):
    row = copy.deepcopy(grouped[0])
    assert row["groups"], "the fixture must construct a group"
    corrupt(row, damage)
    with pytest.raises(ValueError):
        validate_grouped([row], config)


def test_reuse_cap(grouped, config):
    rows = []
    for i in range(6):
        row = copy.deepcopy(grouped[0])
        row["profile_id"] = f"copy{i}"
        row["sample_id"] = f"copy{i}--" + row["context_id"]
        rows.append(row)
    with pytest.raises(ValueError, match="reuse cap"):
        validate_grouped(rows, config)
