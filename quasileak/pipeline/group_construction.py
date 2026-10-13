"""Stage 2, group construction: probe, search, curate, audit, and draw distractors."""

from __future__ import annotations

import copy
from collections import Counter

from .. import confidence
from ..config import ATTRIBUTES
from ..groups import distractors
from ..groups.curation import curate, placement
from ..groups.keys import cue_key, reuse_key
from ..groups.search import pair_groups, search_attribute
from ..groups.validator import validate_groups
from ..llm.parsing import probe_rows, request_object
from ..prompts.construction import MONOTONE_SYS, build_joint_prompt
from ..schemas import for_record, require, validate_grouped, validate_mined
from .cue_mining import generate_candidates
from .distractors import generate_distractors
from .probing import probe_attribute, replacement_feedback


def probe_pool(record, proposer, verifier, config):
    """Singleton and pair probes; one proposal retry for attributes with no pair to build on."""
    record = copy.deepcopy(record)
    diagnostics = {
        a: probe_attribute(a, pool, record["profile"], verifier, config) for a, pool in record["candidates"].items()
    }
    proposed = {a: {cue_key(c["cue"]) for c in pool} for a, pool in record["candidates"].items()}
    retries = []
    for _ in range(config.replacement_rounds):
        view = {"diagnostics": list(diagnostics.values())}
        stalled = [
            d for a, d in diagnostics.items() if not (pair_groups(view, a).verified or pair_groups(view, a).promising)
        ]
        if not stalled:
            break
        attributes = [d["attribute"] for d in stalled]
        fresh = generate_candidates(
            record["profile"],
            record["context"],
            attributes,
            proposer,
            config,
            replacement_feedback(stalled),
            exclude={a: proposed[a] for a in attributes},
        )
        retries.append(attributes)
        for attr, pool in fresh.items():
            record["candidates"][attr] = pool
            proposed[attr] |= {cue_key(c["cue"]) for c in pool}
            diagnostics[attr] = probe_attribute(attr, pool, record["profile"], verifier, config)
    record.update(
        stage="group_construction",
        diagnostics=list(diagnostics.values()),
        proposal_retries=retries,
        joint_probes=[],
        secondary_audits=[],
    )
    return record


def joint_probe(verifier, row, attribute, cues):
    """Recovery verdict of the verifier for ``attribute`` from the cue group alone."""
    user = build_joint_prompt(
        attribute, row["profile"][attribute], [dict(order=len(cues), cues=list(cues))], confidence.reveal_bar(attribute)
    )
    reply = request_object(
        verifier, system=MONOTONE_SYS, user=user, validate=lambda o: probe_rows(o, ["1"], flag="reveals")
    )
    return reply["1"]


def audit_group(verifier, row, attr, cues):
    """Other attributes that the selected group reveals, verified with the joint test."""
    secondary = []
    for other in ATTRIBUTES:
        if other == attr:
            continue
        verdict = joint_probe(verifier, row, other, cues)
        row["secondary_audits"].append(dict(group_attribute=attr, attribute=other, cues=list(cues), verdict=verdict))
        if verdict["confidence"] >= confidence.reveal_bar(other):
            secondary.append(other)
    return secondary


def finalize(row, selected, proposer, verifier, config, distractor_use):
    """Record the curated groups with their audits and placement targets, then add distractors."""
    sid = row["sample_id"]
    row["groups"] = []
    for attr in sorted(row["surface_attributes"]):
        group = selected.get((sid, attr))
        if group is None:
            continue
        row["groups"].append(
            dict(
                attr=attr,
                k=group.k,
                cues=list(group.cues),
                conf=group.conf,
                src=group.src,
                base=list(group.base),
                base_conf=group.base_conf,
                dist=placement(sid, attr),
                secondary_attributes=audit_group(verifier, row, attr, group.cues),
            )
        )
    row["accepted_attributes"] = [g["attr"] for g in row["groups"]]
    final_cues = {g["attr"]: g["cues"] for g in row["groups"]}
    row["decoy_candidates"] = generate_distractors(row, final_cues, proposer, verifier, config, distractor_use)
    distractors.attach(row, config, distractor_use)


def construct_groups(mined, proposer, verifier, config, previous=None):
    validate_mined(mined)
    previous = previous or []
    if previous:
        validate_grouped(previous, config)
        require(
            not {r["sample_id"] for r in mined} & {r["sample_id"] for r in previous},
            "Current and previous construction samples overlap",
        )
    cue_use = Counter(reuse_key(c) for r in previous for g in r["groups"] for c in g["cues"])
    distractor_use = Counter(reuse_key(s) for r in previous for s in r["decoys"]["selected_spans"])

    rows = []
    for record in mined:
        with for_record(record["sample_id"], "pair probing"):
            rows.append(probe_pool(record, proposer, verifier, config))
    results = {}
    for row in rows:

        def probe(attribute, cues, row=row):
            verdict = joint_probe(verifier, row, attribute, cues)
            row["joint_probes"].append(dict(attribute=attribute, cues=list(cues), verdict=verdict))
            return verdict["confidence"]

        with for_record(row["sample_id"], "group search"):
            for attr in sorted(row["surface_attributes"]):
                results[row["sample_id"], attr] = search_attribute(row, attr, probe, config, cue_use)

    selected = curate(results, config, cue_use)
    for row in rows:
        with for_record(row["sample_id"], "audit and distractors"):
            finalize(row, selected, proposer, verifier, config, distractor_use)

    validate_grouped(rows, config)
    if previous:
        validate_groups(previous + rows, config)
    return rows
