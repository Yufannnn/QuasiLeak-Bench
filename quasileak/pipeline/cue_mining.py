"""Stage 1, cue mining: candidate cues for each surfaced attribute."""

from __future__ import annotations

import hashlib
import json
import random

from .. import confidence
from ..config import ATTRIBUTES
from ..groups.keys import cue_key
from ..llm.parsing import request_object
from ..prompts import cue_mining as prompt
from ..prompts.granularity import TARGET_GRANULARITY_RULES
from ..schemas import for_record, require, validate_candidate, validate_inputs, validate_mined


def profile_lines(profile):
    return "\n".join(f"- {a}: {profile[a]}" for a in ATTRIBUTES)


def render_candidates(profile, context, attributes, config, failures=None):
    values = dict(
        profile_lines=profile_lines(profile),
        context_name=context["name"],
        length=context["length"],
        recipient=context["recipient"],
        context_description=context["description"],
        n_per_attr=config.candidates_per_attribute,
        attr_lines="\n".join(f"  - {a}" for a in attributes),
        target_granularity_rules=TARGET_GRANULARITY_RULES,
    )
    if failures is not None:
        values.update(
            failure_lines=json.dumps(failures, indent=2),
            cycle_hint=prompt.RETRY_HINT,
            singleton_threshold=min(confidence.leak_bar(a) for a in attributes),
            threshold=min(confidence.reveal_bar(a) for a in attributes),
        )
        return prompt.BRAINSTORM_RETRY_TEMPLATE.format(**values)
    return prompt.BRAINSTORM_TEMPLATE.format(**values)


def generate_candidates(profile, context, attributes, client, config, failures=None, exclude=None):
    """Propose candidate cues; a retry never repeats a cue proposed before for the attribute."""
    if not attributes:
        return {}
    exclude = exclude or {}

    def validate(obj):
        require(set(obj) == set(attributes), "Candidate response must cover the requested attributes exactly")
        for attr, candidates in obj.items():
            require(isinstance(candidates, list) and candidates, "Candidate response must contain non-empty lists")
            for candidate in candidates:
                validate_candidate(candidate)
            keys = [cue_key(c["cue"]) for c in candidates]
            require(len(set(keys)) == len(keys), "Duplicate candidate phrases")
            repeated = sorted(set(keys) & exclude.get(attr, set()))
            require(not repeated, f"Repeated earlier proposals for {attr}: {repeated}")
        return obj

    return request_object(
        client,
        system=prompt.BRAINSTORM_SYSTEM,
        user=render_candidates(profile, context, attributes, config, failures),
        temperature=config.temperatures["cue_mining_retry" if failures is not None else "cue_mining"],
        validate=validate,
    )


def assigned_pairs(profiles, contexts, assignments=None):
    """(profile row, context) pairs to build: the given assignment, or every combination."""
    if assignments is None:
        return [(p, c) for p in profiles for c in contexts]
    by_profile = {p["profile_id"]: p for p in profiles}
    by_context = {c["context_id"]: c for c in contexts}
    pairs, seen = [], set()
    for row in assignments:
        key = (row.get("profile_id"), row.get("context_id"))
        if key[0] not in by_profile or key[1] not in by_context:
            raise ValueError(f"Assignment names an unknown profile or context: {key}")
        if key in seen:
            raise ValueError(f"Duplicate assignment: {key}")
        seen.add(key)
        pairs.append((by_profile[key[0]], by_context[key[1]]))
    return pairs


def mine_cues(profiles, contexts, client, config, assignments=None):
    validate_inputs(profiles, contexts)
    rows = []
    for profile_row, context in assigned_pairs(profiles, contexts, assignments):
        sid = profile_row["profile_id"] + "--" + context["context_id"]
        seed = int(hashlib.sha256(f"{config.seed}|{sid}".encode()).hexdigest(), 16)
        rng = random.Random(seed)
        declared = [a for cls in ("hide", "keep", "neutral") for a in context["policy"][cls]]
        attrs = [a for a in declared if rng.random() < config.surface_probabilities[a]]
        if len(attrs) > config.surface_cap:
            attrs = rng.sample(attrs, config.surface_cap)
        profile = {a: str(profile_row["profile"][a]) for a in ATTRIBUTES}
        with for_record(sid, "cue mining"):
            candidates = generate_candidates(profile, context, attrs, client, config)
        rows.append(
            dict(
                stage="cue_mining",
                sample_id=sid,
                profile_id=profile_row["profile_id"],
                context_id=context["context_id"],
                profile=profile,
                context=context,
                policy=context["policy"],
                surface_attributes=attrs,
                candidates=candidates,
            )
        )
    validate_mined(rows)
    return rows
