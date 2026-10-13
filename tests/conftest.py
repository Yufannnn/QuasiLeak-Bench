import random
from dataclasses import replace
from pathlib import Path

import pytest
from simulated_model import SimulatedModel

from quasileak.config import ATTRIBUTES, ConstructionConfig
from quasileak.io import read_jsonl
from quasileak.pipeline.cue_mining import mine_cues
from quasileak.pipeline.group_construction import construct_groups

ROOT = Path(__file__).resolve().parents[1]

VALUES = {
    "age": [str(a) for a in range(19, 80)],
    "gender": ["Male", "Female"],
    "nationality": ["Turkey", "Brazil", "Japan", "Kenya", "Canada", "Poland", "India", "Chile"],
    "education": ["Bachelors in Nursing", "Masters in Finance", "PhD in Chemistry"],
    "occupation": ["Hotel accountant", "Primary school teacher", "Civil engineer", "Pharmacist"],
    "income": ["low income", "middle income", "high income", "very high income"],
    "relationship": ["single", "married", "in a relationship", "engaged", "divorced", "widowed"],
    "health": ["asthma", "type 2 diabetes", "migraine", "chronic back pain"],
}


def synthetic_inputs(n_profiles, n_contexts, seed, prefix="p"):
    """Profiles and contexts with complete profiles and a full HIDE/KEEP/NEUTRAL partition."""
    rng = random.Random(seed)
    profiles = [
        {"profile_id": f"{prefix}{i:04d}", "profile": {a: rng.choice(VALUES[a]) for a in ATTRIBUTES}}
        for i in range(n_profiles)
    ]
    contexts = []
    for j in range(n_contexts):
        order = list(ATTRIBUTES)
        rng.shuffle(order)
        cut1, cut2 = sorted(rng.sample(range(1, 8), 2))
        contexts.append(
            {
                "context_id": f"c{j:02d}",
                "name": f"Request {j}",
                "recipient": "service coordinator",
                "description": "The author writes to arrange an appointment.",
                "purpose": "confirm the appointment",
                "length": rng.choice([400, 550, 650]),
                "policy": {"hide": order[:cut1], "keep": order[cut1:cut2], "neutral": order[cut2:]},
            }
        )
    return profiles, contexts


@pytest.fixture
def model():
    return SimulatedModel(seed=3, faults=False)


@pytest.fixture
def config():
    """Occupation is the only surfaced attribute, which keeps single-document tests readable."""
    base = ConstructionConfig()
    return replace(base, surface_probabilities={a: float(a == "occupation") for a in base.surface_probabilities})


@pytest.fixture
def inputs():
    return read_jsonl(ROOT / "examples/profiles.example.jsonl"), read_jsonl(ROOT / "examples/contexts.example.jsonl")


@pytest.fixture
def mined(inputs, model, config):
    return mine_cues(*inputs, model, config)


@pytest.fixture
def grouped(mined, model, config):
    return construct_groups(mined, model, model, config)
