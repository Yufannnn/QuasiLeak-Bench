import json
import sys
from pathlib import Path

import pytest
from simulated_model import SimulatedModel

from quasileak.cli import main
from quasileak.io import read_jsonl

ROOT = Path(__file__).resolve().parents[1]


def run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["quasileak", *argv])
    return main()


@pytest.fixture
def offline(monkeypatch):
    """Serve every model role from one shared offline simulator."""
    shared = SimulatedModel(seed=5, faults=True)
    monkeypatch.setattr("quasileak.construction_cli.LLMClient", lambda *args, **kwargs: shared)
    monkeypatch.setenv("LLM_MODEL", "offline-model")
    return shared


def test_construct_then_validate(tmp_path, monkeypatch, offline, config):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config.to_dict()), encoding="utf-8")
    out = tmp_path / "outputs"
    assert (
        run(
            monkeypatch,
            "construct",
            "--profiles",
            str(ROOT / "examples/profiles.example.jsonl"),
            "--contexts",
            str(ROOT / "examples/contexts.example.jsonl"),
            "--config",
            str(config_file),
            "--output",
            str(out),
        )
        == 0
    )
    names = ["cue_mining.jsonl", "group_construction.jsonl", "document_writing.jsonl"]
    assert sorted(p.name for p in out.iterdir()) == sorted(names)
    ids = [[r["sample_id"] for r in read_jsonl(out / name)] for name in names]
    assert ids[0] == ids[1] == ids[2]
    assert (
        run(
            monkeypatch,
            "validate",
            "--input",
            str(out / "document_writing.jsonl"),
            "--plans",
            str(out / "group_construction.jsonl"),
            "--config",
            str(config_file),
        )
        == 0
    )

    with pytest.raises(SystemExit):
        run(
            monkeypatch,
            "construct",
            "--profiles",
            str(ROOT / "examples/profiles.example.jsonl"),
            "--contexts",
            str(ROOT / "examples/contexts.example.jsonl"),
            "--config",
            str(config_file),
            "--output",
            str(out),
        )


def test_stages_run_one_at_a_time(tmp_path, monkeypatch, offline, config):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config.to_dict()), encoding="utf-8")
    mined, grouped, written = (tmp_path / n for n in ("mined.jsonl", "grouped.jsonl", "written.jsonl"))
    assert (
        run(
            monkeypatch,
            "mine-cues",
            "--profiles",
            str(ROOT / "examples/profiles.example.jsonl"),
            "--contexts",
            str(ROOT / "examples/contexts.example.jsonl"),
            "--config",
            str(config_file),
            "--output",
            str(mined),
        )
        == 0
    )
    assert (
        run(monkeypatch, "build-groups", "--input", str(mined), "--config", str(config_file), "--output", str(grouped))
        == 0
    )
    assert (
        run(
            monkeypatch,
            "write-documents",
            "--input",
            str(grouped),
            "--config",
            str(config_file),
            "--output",
            str(written),
        )
        == 0
    )
    assert read_jsonl(written)[0]["stage"] == "document_writing"
