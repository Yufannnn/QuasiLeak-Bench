"""Checks for construction inputs and intermediate records."""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager

from .config import ATTRIBUTES
from .llm.parsing import probability
from .pipeline.spans import place


def require(condition, message):
    if not condition:
        raise ValueError(message)


@contextmanager
def for_record(sample_id, stage):
    """Name the record and stage in any error raised while processing it."""
    try:
        yield
    except ValueError as exc:
        raise ValueError(f"{sample_id} ({stage}): {exc}") from exc


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate_profile(profile):
    require(
        isinstance(profile, dict) and set(profile) == set(ATTRIBUTES),
        "A full profile requires exactly the eight attributes",
    )
    for attr, value in profile.items():
        require(
            nonempty(value) or (attr == "age" and type(value) is int and 0 < value < 130),
            f"Invalid profile value for {attr}",
        )


def validate_context(context):
    require(isinstance(context, dict), "Context must be an object")
    for field in ("context_id", "name", "recipient", "description", "purpose"):
        require(nonempty(context.get(field)), f"Context requires {field}")
    require(
        type(context.get("length")) is int and context["length"] > 0, "Context length must be a positive word count"
    )
    policy = context.get("policy")
    require(
        isinstance(policy, dict) and set(policy) == {"hide", "keep", "neutral"},
        "Context requires the complete hide/keep/neutral policy",
    )
    for attributes in policy.values():
        require(
            isinstance(attributes, list) and all(isinstance(a, str) for a in attributes),
            "Policy classes must be attribute lists",
        )
    all_attrs = [a for values in policy.values() for a in values]
    require(Counter(all_attrs) == Counter(ATTRIBUTES), "Policy must partition all eight attributes exactly once")


def unique_ids(rows, field="sample_id"):
    require(isinstance(rows, list) and bool(rows), "Input must contain records")
    ids = [r.get(field) for r in rows]
    require(all(nonempty(s) for s in ids), f"Every row requires {field}")
    require(len(set(ids)) == len(ids), f"Duplicate {field}")


def validate_inputs(profiles, contexts):
    unique_ids(profiles, "profile_id")
    unique_ids(contexts, "context_id")
    for row in profiles:
        require("--" not in row["profile_id"], "Profile IDs must not contain --")
        validate_profile(row.get("profile"))
    for row in contexts:
        require("--" not in row["context_id"], "Context IDs must not contain --")
        validate_context(row)


def validate_candidate(candidate):
    require(isinstance(candidate, dict) and nonempty(candidate.get("cue")), "Candidate requires cue text")
    require(isinstance(candidate.get("hints_at"), str), "Candidate requires hints_at")
    require(isinstance(candidate.get("mechanism"), str), "Candidate requires mechanism")
    require(
        isinstance(candidate.get("also_fits"), list) and all(nonempty(v) for v in candidate["also_fits"]),
        "Candidate requires alternative values",
    )


def validate_mined(rows):
    unique_ids(rows)
    for row in rows:
        require(row.get("stage") == "cue_mining", "Expected cue_mining records")
        validate_profile(row.get("profile"))
        validate_context(row.get("context"))
        require(row.get("policy") == row["context"]["policy"], "Policy differs from context")
        require(row.get("context_id") == row["context"]["context_id"], "Context ID mismatch")
        require(nonempty(row.get("profile_id")), "Missing profile_id")
        require(row["sample_id"] == row["profile_id"] + "--" + row["context_id"], "Sample identity mismatch")
        attrs = row.get("surface_attributes")
        require(
            isinstance(attrs, list)
            and len(attrs) <= 4
            and all(a in ATTRIBUTES for a in attrs)
            and len(attrs) == len(set(attrs)),
            "Invalid surface plan",
        )
        pool = row.get("candidates")
        require(isinstance(pool, dict) and set(pool) == set(attrs), "Candidate attributes differ from surface plan")
        for candidates in pool.values():
            require(isinstance(candidates, list), "Candidates must be a list")
            for candidate in candidates:
                validate_candidate(candidate)
            cues = [c["cue"] for c in candidates]
            require(len(cues) == len(set(cues)), "Duplicate candidate cue")


def validate_probe_evidence(row):
    diagnostics = row.get("diagnostics")
    require(isinstance(diagnostics, list), "Missing probe diagnostics")
    require(
        Counter(d.get("attribute") for d in diagnostics) == Counter(row["surface_attributes"]),
        "Probe attributes differ from surface plan",
    )
    for diagnostic in diagnostics:
        for candidate in diagnostic["candidates"]:
            validate_candidate(candidate)
            probability(candidate.get("alone_confidence"))
            require(type(candidate.get("drops_at_singleton")) is bool, "Missing singleton decision")
            require(
                isinstance(candidate.get("alone_top3"), list) and bool(candidate["alone_top3"]),
                "Missing singleton ranked response",
            )
        cues = {c["cue"] for c in diagnostic["candidates"]}
        for pair in diagnostic["pairs"]:
            require(
                pair["cue_a"] in cues and pair["cue_b"] in cues and pair["cue_a"] != pair["cue_b"],
                "Pair references unknown or duplicate cues",
            )
            probability(pair.get("joint_confidence"))
        winner = diagnostic.get("winner_pair")
        require(
            winner is None
            or (isinstance(winner, list) and len(winner) == 2 and len(set(winner)) == 2 and set(winner) <= cues),
            "Invalid winning pair",
        )


def validate_grouped(rows, config):
    from .groups.validator import validate_groups  # imported here: the validator imports require from this module

    mined = [{**r, "stage": "cue_mining"} for r in rows]
    validate_mined(mined)
    for row in rows:
        require(row.get("stage") == "group_construction", "Expected group_construction records")
        validate_probe_evidence(row)
    validate_groups(rows, config)


def validate_documents(rows, plans=None):
    unique_ids(rows)
    plan_map = {r["sample_id"]: r for r in plans} if plans is not None else None
    if plan_map is not None:
        require(
            [r["sample_id"] for r in rows] == [r["sample_id"] for r in plans],
            "Document IDs/order differ from writing plans",
        )
    for row in rows:
        require(row.get("stage") == "document_writing", "Expected document_writing records")
        validate_profile(row.get("profile"))
        validate_context(row.get("context"))
        require(row.get("policy") == row["context"]["policy"], "Document policy mismatch")
        doc, plan = row.get("document"), row.get("plan")
        require(nonempty(doc) and isinstance(plan, dict), "Document requires text and its plan")
        groups = plan.get("sets")
        require(isinstance(groups, list) and isinstance(plan.get("decoys"), list), "Invalid writing plan")
        for group in groups:
            require(
                group.get("attr") in ATTRIBUTES and type(group.get("k")) is int and group["k"] in (2, 3, 4),
                "Invalid group attribute or order",
            )
            require(
                group.get("dist") in ("NEAR", "MEDIUM", "FAR")
                and isinstance(group.get("cues"), list)
                and len(group["cues"]) == group["k"],
                "Invalid cue or distance plan",
            )
        spans = [c for g in groups for c in g["cues"]] + plan["decoys"]
        require(all(nonempty(s) for s in spans) and len(set(spans)) == len(spans), "Required spans must be distinct")
        expected, bad = place(doc, spans)
        require(not bad, f"{row['sample_id']}: required phrases missing, repeated, or overlapping: {bad}")
        require(row.get("spans") == expected, "Span text or offsets differ from the document")
        if plan_map is not None:
            source = plan_map[row["sample_id"]]
            require(
                groups == source["groups"] and plan["decoys"] == source["decoys"]["selected_spans"],
                "Writer changed its accepted construction plan",
            )
            require(
                all(row.get(k) == source.get(k) for k in ("profile", "context", "policy", "profile_id", "context_id")),
                "Writer changed source identity or task inputs",
            )
