"""Blind-audit verdicts for proposed distractors."""

from __future__ import annotations

from typing import Any, Callable


def collect_complete_verdicts(
    candidates: list[dict[str, Any]],
    audit_call: Callable[[list[dict[str, Any]], int], dict],
    *,
    max_attempts: int = 2,
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    """Ask again for any distractor the audit skipped; return verdicts and the ids still missing."""
    pending = {c["decoy_id"]: c for c in candidates}
    verdicts: dict[str, dict[str, Any]] = {}
    for attempt in range(1, max_attempts + 1):
        if not pending:
            break
        try:
            raw = audit_call(list(pending.values()), attempt)
        except ValueError:
            raw = {}
        for decoy_id in list(pending):
            verdict = raw.get(decoy_id)
            if isinstance(verdict, dict) and isinstance(verdict.get("leak_candidates"), list):
                verdicts[decoy_id] = verdict
                del pending[decoy_id]
    return verdicts, set(pending)
