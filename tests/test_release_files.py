import json
from pathlib import Path

import jsonschema
import pytest

from quasileak.io import read_jsonl

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = sorted(ROOT.glob("schemas/*.json")) + [ROOT / "scorer/prediction_schema.json"]


@pytest.mark.parametrize("path", SCHEMAS, ids=lambda p: p.name)
def test_schemas_are_valid(path):
    schema = json.loads(path.read_text(encoding="utf-8"))
    jsonschema.validators.validator_for(schema).check_schema(schema)


def test_prediction_schema_accepts_both_span_forms():
    schema = json.loads((ROOT / "scorer/prediction_schema.json").read_text(encoding="utf-8"))
    jsonschema.validate({"sample_id": "d", "predictions": [{"attribute": "age", "spans": ["a b", "c d"]}]}, schema)
    jsonschema.validate({"sample_id": "d", "evidence": [{"attribute": "age", "spans": [{"start": 0, "end": 3}, "c d"]}]}, schema)


def test_example_predictions_cover_the_1k_subset():
    rows = read_jsonl(ROOT / "examples/predictions_1k.jsonl")
    assert len(rows) == len({r["sample_id"] for r in rows}) == 1000
