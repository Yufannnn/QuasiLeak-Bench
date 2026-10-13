"""Checks on the released corpus. They run wherever data/quasileak_bench_data.zip is present."""

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "quasileak_bench_data.zip"
pytestmark = pytest.mark.skipif(not ARCHIVE.exists(), reason="corpus zip not present")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def unpacked(tmp_path_factory):
    out = tmp_path_factory.mktemp("data")
    with zipfile.ZipFile(ARCHIVE) as z:
        z.extractall(out)
    return out


@pytest.mark.parametrize("name, documents", [("quasileak_bench_data_full", 5000), ("quasileak_bench_data_1k", 1000)])
def test_files_match_their_metadata(unpacked, name, documents):
    meta = json.loads((unpacked / "metadata" / f"{name}.json").read_text(encoding="utf-8"))
    raw = (unpacked / f"{name}.jsonl").read_bytes()
    assert meta["files"]["dataset"] == f"{name}.jsonl"
    assert meta["files"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert meta["files"]["lines"] == meta["dataset"]["documents"] == documents
    assert meta["scoring"]["scorer"]["sha256"] == hashlib.sha256((ROOT / "scorer/score.py").read_bytes()).hexdigest()


def test_example_predictions_score(unpacked):
    scorer = load("qlb_score", ROOT / "scorer" / "score.py")
    scores = scorer.score(ROOT / "examples" / "predictions_1k.jsonl", unpacked / "quasileak_bench_data_1k.jsonl")
    assert scores["P-GF1"] == 60.0163
    assert scores["N_pred"] == 665


def test_renderer_reproduces_the_shipped_prompts(unpacked):
    render = load("qlb_render", ROOT / "prompts" / "render.py")
    with open(unpacked / "quasileak_bench_data_full.jsonl", encoding="utf-8") as fh:
        first = json.loads(fh.readline())
    for shots, name in ((0, "zero_shot_messages.json"), (3, "few_shot_messages.json")):
        shipped = json.loads((ROOT / "prompts" / name).read_text(encoding="utf-8"))
        assert render.render(first, shots) == shipped["messages"]
