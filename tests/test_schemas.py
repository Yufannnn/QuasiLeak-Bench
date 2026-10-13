import copy
from pathlib import Path

import pytest

from quasileak.config import ConstructionConfig, load_config
from quasileak.schemas import validate_inputs, validate_mined

ROOT = Path(__file__).resolve().parents[1]


def test_complete_profile_and_policy(inputs):
    profiles, contexts = copy.deepcopy(inputs)
    validate_inputs(profiles, contexts)
    del profiles[0]["profile"]["income"]
    with pytest.raises(ValueError, match="full profile"):
        validate_inputs(profiles, contexts)


def test_policy_partition(inputs):
    profiles, contexts = copy.deepcopy(inputs)
    contexts[0]["policy"]["keep"].append("age")
    with pytest.raises(ValueError, match="partition"):
        validate_inputs(profiles, contexts)


def test_duplicate_and_foreign_samples(mined):
    with pytest.raises(ValueError, match="Duplicate"):
        validate_mined(mined + mined)
    mined[0]["sample_id"] = "someone-else"
    with pytest.raises(ValueError, match="identity"):
        validate_mined(mined)


@pytest.mark.parametrize(
    "changes",
    [{"surface_cap": 5}, {"trio_fraction": 0.8, "quad_fraction": 0.3}, {"surface_probabilities": {"age": 0.25}}],
)
def test_invalid_config(changes):
    with pytest.raises(ValueError):
        ConstructionConfig(**changes)


def test_config_file_matches_defaults():
    assert load_config(ROOT / "configs/construction.yaml") == ConstructionConfig()
