"""Construction parameters and model-role configuration."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

ATTRIBUTES = ("age", "gender", "nationality", "education", "occupation", "income", "relationship", "health")
TEMPERATURES = {
    "cue_mining": 0.7,
    "cue_mining_retry": 0.9,
    "distractors": 0.95,
    "writer": 0.8,
    "writer_retry": 0.95,
}


@dataclass(frozen=True)
class ConstructionConfig:
    seed: int = 7
    contexts_per_profile: int = 10
    context_slack: int = 100
    candidates_per_attribute: int = 8
    max_pairs: int = 24
    replacement_rounds: int = 1
    surface_probabilities: dict = field(
        default_factory=lambda: {
            "age": 0.25,
            "gender": 0.25,
            "nationality": 0.25,
            "education": 0.25,
            "occupation": 0.25,
            "income": 0.25,
            "relationship": 0.25,
            "health": 0.25,
        }
    )
    surface_cap: int = 4
    promising_bases: int = 8
    verified_bases: int = 4
    extensions_per_base: int = 5
    trio_fraction: float = 0.25
    quad_fraction: float = 0.10
    cue_reuse_cap: int = 5
    distractor_reuse_cap: int = 5
    distractor_rounds: int = 2
    writer_attempts: int = 5
    length_multiplier: float = 1.1
    # Sampling temperatures of the proposer and writer calls. Verifier calls decode at 0.
    temperatures: dict = field(default_factory=lambda: dict(TEMPERATURES))

    def __post_init__(self):
        if set(self.surface_probabilities) != set(ATTRIBUTES):
            raise ValueError("surface_probabilities must list all eight attributes")
        if not 1 <= self.surface_cap <= 4:
            raise ValueError("surface_cap must be between 1 and 4")
        if self.trio_fraction + self.quad_fraction > 1:
            raise ValueError("trio_fraction + quad_fraction must not exceed 1")
        if set(self.temperatures) != set(TEMPERATURES):
            raise ValueError(f"temperatures must set exactly {sorted(TEMPERATURES)}")

    def to_dict(self):
        return asdict(self)


def load_mapping(path: str | Path) -> dict:
    text = Path(path).read_text(encoding="utf-8-sig")
    obj = yaml.safe_load(text)
    if not isinstance(obj, dict):
        raise ValueError("Configuration must be an object")
    return obj


def load_config(path=None) -> ConstructionConfig:
    return ConstructionConfig(**load_mapping(path)) if path else ConstructionConfig()


JUDGE_PANELS = ("census_judges", "compatibility_judges")
QUALITY_CHECK_MODELS = ("quality_check_judges", "quality_check_arbiter")


def judge_panels(path) -> dict[str, list[str]]:
    config = load_mapping(path)
    panels = {}
    for name in JUDGE_PANELS:
        models = config.get(name)
        if not isinstance(models, list) or not models or not all(isinstance(m, str) and m.strip() for m in models):
            raise ValueError(f"{name} must list at least one model")
        panels[name] = [m.strip() for m in models]
    return panels


def model_roles(path=None) -> dict[str, str]:
    config = {k: v for k, v in (load_mapping(path) if path else {}).items() if k not in JUDGE_PANELS + QUALITY_CHECK_MODELS}
    unknown = set(config) - {"proposer", "verifier", "writer"}
    if unknown:
        raise ValueError(f"Unknown model roles: {sorted(unknown)}")
    result = {}
    for role in ("proposer", "verifier", "writer"):
        entry = config.get(role, {})
        if not isinstance(entry, dict) or set(entry) - {"model"}:
            raise ValueError(f"{role} must contain a model name")
        model = entry.get("model") or os.environ.get("LLM_MODEL", "")
        if not isinstance(model, str) or not model.strip():
            raise ValueError(f"Set LLM_MODEL or the {role} model in --models")
        result[role] = model.strip()
    return result


def load_env(path=None):
    """Load KEY=value lines; variables already set in the environment win."""
    if path is None:
        return
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep or not key.strip():
            raise ValueError(f"Invalid line {number} in {path}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)
