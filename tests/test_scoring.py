import copy
import gzip
import importlib.util
import json
from pathlib import Path

import pytest

SCORER = Path(__file__).resolve().parents[1] / "scorer" / "score.py"
spec = importlib.util.spec_from_file_location("qlb_score", SCORER)
qlb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qlb)

# tokens: alpha 0-5, one 6-9, middle 10-16, beta 17-21, two 22-25
DOC = "alpha one middle beta two"
OTHERS = ["gender", "nationality", "education", "occupation", "income", "relationship", "health"]
ROW = {
    "sample_id": "d",
    "document": DOC,
    "policy": {"hide": ["age"], "keep": OTHERS, "neutral": []},
    "gold": {
        "groups": [{"group_id": "g1", "attribute": "age", "cue_ids": ["s1", "s2"], "secondary_attributes": []}],
        "spans": [
            {"span_id": "s1", "group_id": "g1", "text": "alpha one", "start": 0, "end": 9},
            {"span_id": "s2", "group_id": "g1", "text": "beta two", "start": 17, "end": 25},
        ],
        "distractors": [],
    },
}
EXACT = [(0, 9), (17, 25)]


def group(attribute, *spans):
    return {"attribute": attribute, "spans": [{"start": a, "end": b} for a, b in spans]}


def write(path, rows):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "wt", encoding="utf-8") as fh:
        fh.write("".join(json.dumps(r) + "\n" for r in rows))


@pytest.fixture
def score(tmp_path):
    def run(predictions, row=ROW, extra_rows=()):
        write(tmp_path / "data.jsonl.gz", [row])
        write(tmp_path / "pred.jsonl", [{"sample_id": "d", "predictions": predictions}, *extra_rows])
        return qlb.score(tmp_path / "pred.jsonl", tmp_path / "data.jsonl.gz")

    return run


def test_exact_match(score):
    s = score([group("age", *EXACT)])
    assert s["P-GF1"] == s["B-GF1"] == s["E-GF1"] == s["E_R"] == 100.0
    assert s["E_C"] == s["E_L"] == s["B_G"] == s["B_A"] == 100.0
    assert s["N_pred"] == 1 and s["DSR"] == 0.0


def test_verbatim_strings_match_offsets(score):
    s = score([{"attribute": "age", "spans": ["alpha one", "beta two"]}])
    assert s["P-GF1"] == 100.0


def test_verbatim_string_resolves_to_first_occurrence(score):
    row = copy.deepcopy(ROW)
    row["document"] = DOC + " alpha one"
    s = score([{"attribute": "age", "spans": ["beta two", " alpha one "]}], row)
    assert s["P-GF1"] == 100.0  # trimmed, then located at offset 0


def test_evidence_key_is_accepted(tmp_path):
    write(tmp_path / "data.jsonl", [ROW])
    write(tmp_path / "pred.jsonl", [{"sample_id": "d", "evidence": [{"attribute": "age", "spans": ["alpha one", "beta two"]}]}])
    assert qlb.score(tmp_path / "pred.jsonl", tmp_path / "data.jsonl")["P-GF1"] == 100.0


def test_unplaceable_object_counts_with_zero_credit(score):
    s = score([group("age", *EXACT), {"attribute": "age", "spans": ["not in the document", "nor this"]}, "junk"])
    assert s["N_pred"] == 3
    assert s["P-GP"] == pytest.approx(100 / 3, abs=1e-4) and s["P-GR"] == 100.0


def test_unknown_attribute_earns_no_binding_credit(score):
    s = score([group("favourite colour", *EXACT)])
    assert s["P-GF1"] == 0.0 and s["E-GF1"] == 100.0 and s["B_A"] == 0.0


def test_empty_prediction(score):
    assert score([])["P-GF1"] == 0.0


def test_wrong_attribute_keeps_structural_credit(score):
    s = score([group("gender", *EXACT)])
    assert s["P-GF1"] == 0.0 and s["E-GF1"] == 100.0


def test_partial_group(score):
    # one of two cues found (E_C = 0.25), one of two returned spans is a cue (E_L = 0.5)
    assert score([group("age", (0, 9), (10, 16))])["P-GF1"] == 12.5


def test_span_below_iou_threshold(score):
    assert score([group("age", (0, 2), (17, 19))])["P-GF1"] == 0.0


def test_verified_secondary_earns_half(score):
    row = copy.deepcopy(ROW)
    row["policy"] = {"hide": ["age", "income"], "keep": [a for a in OTHERS if a != "income"], "neutral": []}
    row["gold"]["groups"][0]["secondary_attributes"] = ["income"]
    assert score([group("income", *EXACT)], row)["P-GF1"] == 50.0


def test_keep_prediction_costs_precision(score):
    s = score([group("age", *EXACT), group("gender", (10, 16), (17, 21))])
    assert s["P-GP"] == pytest.approx(100 / 3, abs=1e-4)  # 1 / (2 predictions + 1 KEEP flag)
    assert s["E-GP"] == 50.0


def test_secondary_hide_label_on_keep_group_is_exempt(score):
    row = copy.deepcopy(ROW)
    row["policy"] = {"hide": ["income"], "keep": ["age"] + [a for a in OTHERS if a != "income"], "neutral": []}
    row["gold"]["groups"][0]["secondary_attributes"] = ["income"]
    s = score([group("income", *EXACT)], row)
    assert s["P-GP"] == 100.0  # neither counted as a prediction nor as a KEEP flag


def test_groups_align_one_to_one(score):
    s = score([group("age", *EXACT), group("age", (0, 9), (17, 21))])
    assert s["P-GP"] == 50.0 and s["P-GR"] == 100.0


def test_distractor_selection_rate(score):
    row = copy.deepcopy(ROW)
    row["gold"]["distractors"] = [{"distractor_id": "r1d0", "kind": "near-miss", "text": "middle", "start": 10, "end": 16}]
    assert score([group("age", (0, 9), (10, 16))], row)["DSR"] == 100.0
    assert score([group("age", *EXACT)], row)["DSR"] == 0.0


def test_cue_recall_ignores_grouping_and_policy(score):
    # each cue is found by a different, wrongly labelled group; E_R counts both cues
    s = score([group("gender", (0, 9), (10, 16)), group("income", (17, 25), (10, 16))])
    assert s["E_R"] == 100.0 and s["P-GF1"] == 0.0


def test_duplicate_rows_are_rejected(score):
    with pytest.raises(ValueError, match="duplicate"):
        score([], extra_rows=[{"sample_id": "d", "predictions": []}])


def test_missing_document_is_rejected(tmp_path):
    write(tmp_path / "data.jsonl.gz", [ROW])
    write(tmp_path / "pred.jsonl", [])
    with pytest.raises(ValueError, match="cover every document"):
        qlb.score(tmp_path / "pred.jsonl", tmp_path / "data.jsonl.gz")
