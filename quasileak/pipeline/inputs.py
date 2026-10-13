"""Inputs: the profile census, profile-context compatibility scores, and the assignment."""

from __future__ import annotations

import json

from ..config import ATTRIBUTES
from ..prompts.inputs import (
    CENSUS_SYSTEM,
    COMPATIBILITY_INTRO,
    COMPATIBILITY_RULES_TAIL,
    COMPATIBILITY_SYSTEM,
    PROFILE_RULES,
    RUBRIC_RULES,
)

RULE_IDS = [r["id"] for r in PROFILE_RULES]
HARD = [r["id"] for r in PROFILE_RULES if r["gate"] == "hard"]
SOFT = [r["id"] for r in PROFILE_RULES if r["gate"] == "soft"]
RUBRIC_IDS = [r["id"] for r in RUBRIC_RULES]


# ------------------------------------------------------------------- census
def census_prompt(profile: dict) -> str:
    lines = ["Profile under review:"]
    lines += [f"- {a}: {profile.get(a, '')}" for a in ATTRIBUTES]
    notes = str(profile.get("persona_notes") or "").strip()
    lines.append(f"- persona notes: {notes if notes else '(none)'}")
    return "\n".join(lines)


def parse_census(text: str) -> dict | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        depth += ch == "{"
        depth -= ch == "}"
        if depth == 0:
            try:
                obj = json.loads(text[start:i + 1])
            except json.JSONDecodeError:
                return None
            break
    else:
        return None
    verdicts = {k: obj.get(k) for k in RULE_IDS}
    if any(v not in ("PASS", "FAIL") for v in verdicts.values()):
        return None
    return verdicts


def route(verdicts: list[dict | None]) -> str:
    """Accept when every judge passes the hard rules, reject when all fail the same one,
    and send anything else to human review."""
    ok = [v for v in verdicts if v is not None]
    if len(ok) < len(verdicts) or not ok:
        return "human_review"
    if any(all(v[h] == "FAIL" for v in ok) for h in HARD):
        return "reject"
    if any(v[h] == "FAIL" for v in ok for h in HARD):
        return "human_review"
    return "accept"


def census(profiles: list[dict], judges: list) -> list[dict]:
    rows = []
    for row in profiles:
        verdicts = [parse_census(j.generate(system=CENSUS_SYSTEM, user=census_prompt(row["profile"]))) for j in judges]
        rows.append({"profile_id": row["profile_id"], "verdicts": verdicts, "decision": route(verdicts)})
    return rows


# ------------------------------------------------------------ compatibility
def compatibility_prompt(profile: dict, contexts: list[dict]) -> str:
    lines = ["A synthetic person:"]
    lines += [f"  {a}: {profile[a]}" for a in ATTRIBUTES if profile.get(a)]
    lines += ["", COMPATIBILITY_INTRO]
    lines += [f"  {r['id']} {r['text']}" for r in RUBRIC_RULES]
    lines.append(COMPATIBILITY_RULES_TAIL)
    for c in contexts:
        parts = [f"  {c['context_id']}: {c.get('name', '')}"]
        if c.get("recipient"):
            parts.append(f"to {c['recipient']}")
        if c.get("purpose"):
            parts.append(f"purpose: {c['purpose']}")
        description = str(c.get("description") or "").strip()
        if description and description != str(c.get("name") or "").strip():
            parts.append(f"description: {description}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def parse_compatibility(text: str) -> dict[str, int]:
    """context_id -> score 0-10, the number of rubric criteria met."""
    start, end = text.find("{"), text.rfind("}") + 1
    if start < 0 or end == 0:
        raise ValueError("no JSON object in response")
    scores = {}
    for context_id, value in json.loads(text[start:end]).items():
        if not isinstance(value, dict):
            continue
        rubric = {k: (v.get("met", v.get("score")) if isinstance(v, dict) else v)
                  for k, v in (value.get("rubric") or {}).items()}
        if all(k in rubric for k in RUBRIC_IDS):
            scores[context_id] = sum(1 if int(float(rubric[k])) else 0 for k in RUBRIC_IDS)
        elif value.get("score") is not None:
            scores[context_id] = max(0, min(10, round(float(value["score"]))))
    return scores


def score_pairs(profiles: list[dict], contexts: list[dict], judges: list) -> dict[tuple[str, str], float]:
    """Consensus compatibility on a 0-100 scale: the judges' mean score times ten."""
    totals: dict[tuple[str, str], list[int]] = {}
    for row in profiles:
        prompt = compatibility_prompt(row["profile"], contexts)
        for judge in judges:
            for context_id, score in parse_compatibility(judge.generate(system=COMPATIBILITY_SYSTEM, user=prompt)).items():
                totals.setdefault((row["profile_id"], context_id), []).append(score)
    return {key: 10 * sum(v) / len(v) for key, v in totals.items() if len(v) == len(judges)}


# --------------------------------------------------------------- assignment
def assign(scores: dict[tuple[str, str], float], profile_ids: list[str], context_ids: list[str],
           per_profile: int, slack: int) -> list[dict]:
    """Exact max-weight b-matching: every profile gets `per_profile` contexts and every
    context receives within `slack` of an even share. The constraint matrix is totally
    unimodular, so the linear program's optimum is integral."""
    import numpy as np
    from scipy.optimize import linprog
    from scipy.sparse import csr_matrix, vstack

    P, C = len(profile_ids), len(context_ids)
    S = np.array([[scores.get((p, c), 0.0) for c in context_ids] for p in profile_ids])
    n = P * C
    rows = [p for p in range(P) for _ in range(C)]
    A_eq = csr_matrix((np.ones(n), (rows, range(n))), shape=(P, n))
    COL = csr_matrix((np.ones(n), ([c for _ in range(P) for c in range(C)], range(n))), shape=(C, n))
    fair = P * per_profile // C
    low, high = max(0, fair - slack), min(P, fair + slack)
    result = linprog(-S.reshape(-1), A_ub=vstack([COL, -COL]).tocsr(),
                     b_ub=np.concatenate([np.full(C, high), -np.full(C, low)]),
                     A_eq=A_eq, b_eq=np.full(P, per_profile), bounds=[(0.0, 1.0)] * n, method="highs")
    if not result.success:
        raise ValueError(f"no feasible assignment: {result.message}")
    x = np.round(result.x).astype(int).reshape(P, C)
    return [{"profile_id": profile_ids[p], "context_id": context_ids[c]}
            for p in range(P) for c in range(C) if x[p, c]]
