"""Pins the prompt text. Any edit to a prompt constant, or to code that renders one, changes a
hash here."""

import hashlib

from quasileak.config import ConstructionConfig
from quasileak.pipeline.cue_mining import render_candidates
from quasileak.pipeline.inputs import census_prompt, compatibility_prompt
from quasileak.prompts import (
    calibration,
    construction,
    cue_mining,
    distractors,
    document_writer,
    granularity,
    inputs,
    probing,
    quality_check,
)

EXPECTED = {
    "calibration.CONFIDENCE_CALIBRATION": "d10ccec0d37792ec",
    "construction.BINARY_GENDER_RULE": "9917578fd052387d",
    "construction.CONFIDENCE_CALIBRATION": "d10ccec0d37792ec",
    "construction.JOINT_TEMPLATE": "07322d28072ebdfa",
    "construction.MONOTONE_SYS": "977d519d64606872",
    "cue_mining.BRAINSTORM_RETRY_TEMPLATE": "b058e1540b286f05",
    "cue_mining.BRAINSTORM_SYSTEM": "0b9715937e53e7a9",
    "cue_mining.BRAINSTORM_TEMPLATE": "7cd9e589646db034",
    "cue_mining.RETRY_HINT": "201ef1b6fadba9af",
    "distractors.DECOY_AUDIT_SYSTEM": "07b7149d3c3b38ff",
    "distractors.DECOY_AUDIT_TEMPLATE": "ab5f856daf6b0007",
    "distractors.DECOY_SYSTEM": "e1c349163f32c958",
    "distractors.DECOY_TEMPLATE": "1503af509c16095b",
    "document_writer.DECOY_RULE": "3050e765a390d4bf",
    "document_writer.NO_BUNDLE": "77c2f3182a0d1482",
    "document_writer.PROMPT_TEMPLATE": "d3ebf3415fd1deba",
    "document_writer.RETRY_BLURTED": "8a4e7687da153f2d",
    "document_writer.RETRY_MISSING": "9dee7aa7c4c330eb",
    "document_writer.RULES_TAIL": "b4f7a5c3b1ff8e39",
    "document_writer.RUN_ALLOW": "26487c523c1d7214",
    "document_writer.RUN_AVOID": "584b7cc58b0437d9",
    "document_writer.SYSTEM": "23ee0425c6d7c981",
    "document_writer.VOICE": "af2bb4b8a09c29a0",
    "granularity.TARGET_GRANULARITY_RULES": "4866ba0008d334fd",
    "inputs.CENSUS_SYSTEM": "f4a4cc6309a4f2c5",
    "inputs.COMPATIBILITY_INTRO": "6f0699d9d5e762ba",
    "inputs.COMPATIBILITY_RULES_TAIL": "8ffe8ded9b3401ea",
    "inputs.COMPATIBILITY_SYSTEM": "94e2d2ef0347f841",
    "probing.ALONE_SYSTEM": "16fd312f41d689fd",
    "probing.ALONE_TEMPLATE": "da86cf6d15ee0de4",
    "probing.CONFIDENCE_CALIBRATION": "d10ccec0d37792ec",
    "probing.PAIR_SYSTEM": "18f9830255fe5e53",
    "probing.PAIR_TEMPLATE": "5b86cfc395533bee",
    "quality_check.CUE_SYS": "f8508124256e4c54",
    "quality_check.LEAK_SYS": "7aa6176990218bf7",
    "quality_check.REALISM_SYS": "c7e479bdcd4ec2ed",
    "quality_check.SHARED_SYS": "10bac22fa441986b",
    "rendered.census": "3ecd72fdb23d273f",
    "rendered.compatibility": "cf002ed777b42525",
    "rendered.cue_mining": "5781f5fa2370f93c",
    "rendered.cue_mining_retry": "fa75b7ec907fb9f5",
    "rendered.granularity": "e5b82a8b204b2cc5",
    "rendered.joint": "27e3431f8352e38e",
    "rendered.qc": "fc05a260a1c3801b",
    "rendered.writer": "179f5276a6bf9463",
}

PROFILE = {
    "age": "34",
    "gender": "Female",
    "nationality": "Kenya",
    "education": "Masters in Finance",
    "occupation": "Pharmacist",
    "income": "middle income",
    "relationship": "married",
    "health": "asthma",
}
CONTEXT = {
    "context_id": "c01",
    "name": "Pharmacy booking",
    "recipient": "pharmacist",
    "description": "Book a vaccine.",
    "purpose": "book a slot",
    "length": 400,
    "policy": {"hide": ["health"], "keep": ["age"], "neutral": []},
}


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def test_prompt_constants():
    modules = (calibration, construction, cue_mining, distractors, document_writer, granularity, inputs, probing, quality_check)
    found = {
        f"{mod.__name__.rsplit('.', 1)[1]}.{name}": digest(value)
        for mod in modules
        for name, value in vars(mod).items()
        if isinstance(value, str) and not name.startswith("__") and len(value) > 40
    }
    assert found == {k: v for k, v in EXPECTED.items() if not k.startswith("rendered.")}


def test_rendered_prompts():
    plan = {
        "sets": [{"attr": "health", "k": 2, "dist": "NEAR", "cues": ["inhaler refill", "spacer cap"]}],
        "decoys": ["blue lanyard"],
    }
    plan["roles"] = document_writer.span_roles("s1", plan["sets"], plan["decoys"])
    record = {"sample_id": "s1", "profile": PROFILE, "context": CONTEXT}
    document = "One.\n\nTwo."
    rendered = {
        "cue_mining": render_candidates(PROFILE, CONTEXT, ["health", "income"], ConstructionConfig()),
        "cue_mining_retry": render_candidates(
            PROFILE, CONTEXT, ["health"], ConstructionConfig(), failures=[{"attribute": "health"}]
        ),
        "joint": construction.build_joint_prompt(
            "health", "asthma", [{"order": 2, "cues": ["inhaler refill", "spacer cap"]}], 0.57
        ),
        "granularity": granularity.target_granularity_note("income", "middle income")
        + granularity.truth_block(PROFILE, exclude="income"),
        "writer": document_writer.build_writer_prompt(record, plan, 440, missing=["spacer cap"]),
        "qc": quality_check.cue_user(
            "s1", document, PROFILE, [{"group_id": "g1", "attribute": "health", "cues": ["One"]}]
        )
        + quality_check.leak_user("s1", document, ["One"])
        + quality_check.realism_user("s1", "One.", CONTEXT, PROFILE),
        "census": census_prompt(PROFILE),
        "compatibility": compatibility_prompt(PROFILE, [CONTEXT]),
    }
    for name, text in rendered.items():
        assert digest(text) == EXPECTED[f"rendered.{name}"], name
