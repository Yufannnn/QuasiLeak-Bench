"""Check that every constructed group carries the evidence the construction requires."""

from __future__ import annotations

from collections import Counter

from .. import confidence
from ..config import ATTRIBUTES
from ..schemas import require
from .distractors import DISTRACTOR_KINDS, MAX_DISTRACTORS, MIN_DISTRACTORS
from .keys import content_tokens, cue_key, nested, reuse_key
from .search import is_promising, joint_bar


def _pair_score(diagnostic: dict, cues: list[str]) -> list[dict]:
    return [p for p in diagnostic["pairs"] if {p["cue_a"], p["cue_b"]} == set(cues)]


def _probe_scores(probes: list[dict], attr: str, cues: list[str]) -> list[float]:
    return [p["verdict"]["confidence"] for p in probes if p["attribute"] == attr and set(p["cues"]) == set(cues)]


def _check_group(row: dict, group: dict) -> None:
    sid, attr, k, cues = row["sample_id"], group.get("attr"), group.get("k"), group.get("cues")
    diagnostics = {d["attribute"]: d for d in row["diagnostics"]}
    require(attr in ATTRIBUTES and attr in diagnostics, f"{sid}: unknown group attribute")
    require(type(k) is int and k in (2, 3, 4), f"{sid}: arity must be 2, 3, or 4")
    require(
        isinstance(cues, list)
        and len(cues) == k
        and len(set(cues)) == k
        and all(isinstance(c, str) and c for c in cues),
        f"{sid}: arity and cues disagree",
    )
    require(group.get("dist") in {"NEAR", "MEDIUM", "FAR"}, f"{sid}: missing placement target")

    pool = {c["cue"]: c for c in diagnostics[attr]["candidates"]}
    for cue in cues:
        candidate = pool.get(cue)
        require(
            candidate is not None and candidate["drops_at_singleton"] is False,
            f"{sid}: {cue!r} is not in the weak pool",
        )
        require(confidence.weak_alone(candidate["alone_confidence"], attr), f"{sid}: {cue!r} is not weak alone")
        require(
            not any(
                leak["confidence"] >= confidence.leak_bar(leak["attribute"]) for leak in candidate.get("also_leaks", [])
            ),
            f"{sid}: {cue!r} reveals another attribute alone",
        )

    if k == 2:
        require(group.get("src") == "pair", f"{sid}: a pair has no base")
        require(
            any(
                p["joint_rank"] == 1 and p["joint_confidence"] == group.get("conf") >= joint_bar(attr)
                for p in _pair_score(diagnostics[attr], cues)
            ),
            f"{sid}: pair lacks a verified probe",
        )
    else:
        require(
            group.get("conf") in _probe_scores(row["joint_probes"], attr, cues) and group["conf"] >= joint_bar(attr),
            f"{sid}: group lacks a verified probe",
        )
        base = group.get("base")
        require(
            isinstance(base, list) and len(base) == k - 1 and set(base) < set(cues),
            f"{sid}: group does not extend a base",
        )
        if k == 3:
            base_scores = [p["joint_confidence"] for p in _pair_score(diagnostics[attr], base)]
        else:
            base_scores = _probe_scores(row["joint_probes"], attr, base)
        require(group.get("base_conf") in base_scores, f"{sid}: base probe is missing")
        if group.get("src") == "promising":
            require(is_promising(attr, group["base_conf"]), f"{sid}: promising base is not promising")
        else:
            require(
                group.get("src") == "verified" and group["base_conf"] >= joint_bar(attr), f"{sid}: unknown base kind"
            )

    audits = [a for a in row["secondary_audits"] if a["group_attribute"] == attr and set(a["cues"]) == set(cues)]
    audited = Counter(a["attribute"] for a in audits)
    require(
        audited == Counter(a for a in ATTRIBUTES if a != attr),
        f"{sid}: group is not audited on every other attribute once",
    )
    verified = sorted(
        a["attribute"] for a in audits if a["verdict"]["confidence"] >= confidence.reveal_bar(a["attribute"])
    )
    require(
        isinstance(group.get("secondary_attributes"), list) and sorted(group["secondary_attributes"]) == verified,
        f"{sid}: secondary attributes differ from the audit",
    )


def validate_groups(rows, config):
    cue_use, distractor_use, arities = Counter(), Counter(), Counter()
    for row in rows:
        sid = row["sample_id"]
        groups = row.get("groups")
        require(isinstance(groups, list), f"{sid}: missing groups")
        require(
            [g.get("attr") for g in groups] == row.get("accepted_attributes"),
            f"{sid}: accepted attributes differ from groups",
        )
        require(len({g["attr"] for g in groups}) == len(groups), f"{sid}: two groups for one attribute")
        require(
            set(row["accepted_attributes"]) <= set(row["surface_attributes"]),
            f"{sid}: group for an attribute that was not surfaced",
        )
        doc_keys = []
        for group in groups:
            _check_group(row, group)
            keys = [cue_key(c) for c in group["cues"]]
            doc_keys.extend(keys)
            cue_use.update(reuse_key(c) for c in group["cues"])
            arities[group["k"]] += 1
        require(len(doc_keys) == len(set(doc_keys)), f"{sid}: a cue is shared by two groups")

        plan = row.get("decoys") or {}
        selected = plan.get("selected_ids")
        require(
            isinstance(selected, list)
            and MIN_DISTRACTORS <= len(selected) <= MAX_DISTRACTORS
            and len(set(selected)) == len(selected),
            f"{sid}: requires two to four distinct distractors",
        )
        pool = {d["decoy_id"]: d for d in row["decoy_candidates"]}
        require(
            len(pool) == len(row["decoy_candidates"]) and all(d in pool for d in selected), f"{sid}: unknown distractor"
        )
        chosen = [pool[d] for d in selected]
        require(
            all(d.get("cold_leaks") == [] and isinstance(d.get("cold_audit"), dict) for d in chosen),
            f"{sid}: distractor failed or lacks its audit",
        )
        require(all(d["kind"] in DISTRACTOR_KINDS for d in chosen), f"{sid}: unknown distractor kind")
        require(
            sum(d["kind"] == "wrong-direction" for d in chosen) <= 1, f"{sid}: more than one wrong-direction distractor"
        )
        spans = [s for d in chosen for s in d["spans"]]
        require(
            spans == plan.get("selected_spans") and len(set(spans)) == len(spans),
            f"{sid}: distractor plan differs from its pool",
        )
        cue_tokens = set().union(*(content_tokens(c) for g in groups for c in g["cues"]))
        require(
            not any(content_tokens(s) & cue_tokens for s in spans),
            f"{sid}: distractor shares a content word with a cue",
        )
        phrases = [c for g in groups for c in g["cues"]] + spans
        require(
            not any(nested(a, b) for i, a in enumerate(phrases) for b in phrases[i + 1 :]),
            f"{sid}: one planned phrase contains another",
        )
        distractor_use.update(reuse_key(s) for s in spans)

    require(all(n <= config.cue_reuse_cap for n in cue_use.values()), "A cue exceeds the corpus reuse cap")
    require(
        all(n <= config.distractor_reuse_cap for n in distractor_use.values()),
        "A distractor exceeds the corpus reuse cap",
    )
    return {
        "documents": len(rows),
        "groups": sum(arities.values()),
        "arities": dict(arities),
        "planted_cues": sum(cue_use.values()),
        "planted_distractors": sum(distractor_use.values()),
    }
