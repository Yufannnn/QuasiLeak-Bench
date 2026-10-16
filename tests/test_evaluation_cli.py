"""Evaluation CLI contracts: scorer parity, prompt integrity, and comparable runs."""
import copy
import json
from pathlib import Path

import pytest

from quasileak.cli import main
from quasileak.evaluation_cli import released_module
from test_scoring import ROW


@pytest.fixture
def evaluation_files(tmp_path):
    row = copy.deepcopy(ROW)
    row["profile"] = {key: "example value" for key in ("age", *row["policy"]["keep"])}
    dataset = tmp_path / "data.jsonl"
    predictions = tmp_path / "predictions.jsonl"
    dataset.write_text(json.dumps(row) + "\n", encoding="utf-8")
    predictions.write_text(json.dumps({"sample_id": "d", "evidence": [
        {"attribute": "age", "spans": ["alpha one", "beta two"]}]
    }) + "\n", encoding="utf-8")
    return dataset, predictions


def score_file(dataset, predictions, output, *extra):
    assert main(["score", "--dataset", str(dataset), "--predictions", str(predictions),
                 "--output", str(output), *extra]) == 0
    return json.loads(output.read_text())


def test_score_matches_released_scorer(evaluation_files, tmp_path, capsys):
    dataset, predictions = evaluation_files
    output = tmp_path / "score.json"
    snapshot = score_file(dataset, predictions, output, "--name", "Detector A")
    assert snapshot["metrics"] == released_module("scorer").score(predictions, dataset)
    assert snapshot["metrics"]["P-GF1"] == 100
    assert len(snapshot["evaluation"]["scorer_sha256"]) == 64
    assert main(["report", str(output)]) == 0
    assert "Detector A" in capsys.readouterr().out


def test_render_preserves_complete_official_messages(evaluation_files, tmp_path):
    dataset, _ = evaluation_files
    output = tmp_path / "requests.jsonl"
    assert main(["render", "--dataset", str(dataset), "--shots", "3", "--output", str(output)]) == 0
    request = json.loads(output.read_text())
    row = json.loads(dataset.read_text())
    assert request == {"sample_id": "d", "messages": released_module("renderer").render(row, 3)}
    assert "AUTHOR PROFILE" in request["messages"][-1]["content"]
    assert "example value" in request["messages"][-1]["content"]


def test_check_coverage_schema_and_span_location(evaluation_files, capsys):
    dataset, predictions = evaluation_files
    argv = ["check", "--dataset", str(dataset), "--predictions", str(predictions)]
    assert main(argv) == 0
    assert "PASS" in capsys.readouterr().out
    original = predictions.read_text()
    for text, message in (("", "missing"), (original * 2, "duplicate"),
                          (original.replace("alpha one", "absent words"), "cannot be located"),
                          (original.replace('"age"', '"unknown"'), "not one of")):
        predictions.write_text(text)
        with pytest.raises(SystemExit) as caught:
            main(argv)
        assert caught.value.code == 1
        assert message in capsys.readouterr().err


def test_invalid_groups_are_not_filtered_when_scoring(evaluation_files, tmp_path):
    dataset, predictions = evaluation_files
    predictions.write_text(json.dumps({"sample_id": "d", "evidence": [
        {"attribute": "age", "spans": ["alpha one", "beta two"]}, "invalid group"]}) + "\n")
    snapshot = score_file(dataset, predictions, tmp_path / "score.json")
    assert snapshot["metrics"] == released_module("scorer").score(predictions, dataset)
    assert snapshot["metrics"]["N_pred"] == 2
    assert snapshot["metrics"]["P-GF1"] < 100


def test_compare_checks_evaluation_identity(evaluation_files, tmp_path, capsys):
    dataset, predictions = evaluation_files
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    score_file(dataset, predictions, a)
    score_file(dataset, predictions, b)
    assert main(["compare", str(a), str(b)]) == 0
    assert "Δ P-GF1" in capsys.readouterr().out
    score_file(dataset, predictions, b, "--gamma", "3")
    with pytest.raises(SystemExit):
        main(["compare", str(a), str(b)])
    assert "Cannot compare" in capsys.readouterr().err


def test_paired_policy_evaluation_uses_released_scorer(evaluation_files, tmp_path, capsys):
    dataset, predictions = evaluation_files
    row = json.loads(dataset.read_text())
    row["policy_original"] = row.pop("policy")
    row["policy_reassigned"] = {"hide": [], "keep": ["age", *row["policy_original"]["keep"]], "neutral": []}
    dataset.write_text(json.dumps(row) + "\n")
    after = tmp_path / "after.jsonl"
    after.write_text(json.dumps({"sample_id": "d", "evidence": []}) + "\n")
    output = tmp_path / "paired.json"
    snapshot = score_file(dataset, predictions, output, "--reassigned-predictions", str(after))
    assert snapshot["evaluation"]["arm"] == "paired"
    assert snapshot["metrics"] == released_module("scorer").score_policy_shift(predictions, after, dataset)
    assert main(["report", str(output)]) == 0
    assert "Suppress=100.0%" in capsys.readouterr().out


def test_report_accepts_legacy_but_comparison_requires_metadata(evaluation_files, tmp_path, capsys):
    dataset, predictions = evaluation_files
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps(released_module("scorer").score(predictions, dataset)))
    assert main(["report", str(legacy)]) == 0
    with pytest.raises(SystemExit):
        main(["compare", str(legacy)])
    assert "metadata" in capsys.readouterr().err


def test_output_cannot_overwrite_inputs(evaluation_files):
    dataset, predictions = evaluation_files
    for command, output in (("score", predictions), ("render", dataset)):
        argv = [command, "--dataset", str(dataset), "--output", str(output)]
        if command == "score":
            argv.extend(["--predictions", str(predictions)])
        before = output.read_bytes()
        with pytest.raises(SystemExit):
            main(argv)
        assert output.read_bytes() == before
