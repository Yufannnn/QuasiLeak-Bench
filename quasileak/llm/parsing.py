"""Parse structured replies and require complete, bounded probe evidence."""

from __future__ import annotations

import json
import math
import re

from ..io import reject_constant


def parse_object(raw: str) -> dict:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Empty model response")
    text = raw.strip()
    if text.startswith("```"):
        match = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?```", text, flags=re.S | re.I)
        if not match:
            raise ValueError("Unclosed JSON code fence")
        text = match.group(1)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    obj = json.loads(text, object_pairs_hook=unique, parse_constant=reject_constant)
    if not isinstance(obj, dict):
        raise ValueError("Expected a JSON object")
    return obj


def probability(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Probe confidence must be a finite number in [0, 1]")
    return float(value)


def probe_rows(obj, keys, flag="top1_pins_truth", *, singleton=False):
    if set(obj) != set(keys):
        raise ValueError("Probe response does not cover the requested IDs exactly")
    for row in obj.values():
        if not isinstance(row, dict) or type(row.get(flag)) is not bool:
            raise ValueError(f"Probe verdict requires boolean {flag}")
        probability(row.get("confidence"))
        top = row.get("top3")
        if (
            not isinstance(top, list)
            or not 1 <= len(top) <= 3
            or any(not isinstance(v, str) or not v.strip() for v in top)
        ):
            raise ValueError("Probe verdict requires one to three ranked values")
        if not isinstance(row.get("reasoning"), str) or not row["reasoning"].strip():
            raise ValueError("Probe verdict requires its reasoning")
        if singleton:
            leaks = row.get("also_leaks")
            if not isinstance(leaks, list):
                raise ValueError("Singleton verdict requires an also_leaks list")
            for leak in leaks:
                if not isinstance(leak, dict) or not isinstance(leak.get("attribute"), str):
                    raise ValueError("Invalid cross-attribute verdict")
                probability(leak.get("confidence"))
    return obj


def request_object(client, *, system, user, temperature=0.0, validate=lambda x: x, attempts=2):
    """Retry incomplete structured replies with explicit format feedback."""
    feedback, error = "", None
    for _ in range(attempts):
        raw = client.generate(system=system, user=user + feedback, temperature=temperature)
        try:
            return validate(parse_object(raw))
        except (ValueError, TypeError, KeyError) as exc:
            error = exc
            feedback = "\nReturn the complete requested JSON object, including every requested ID and field."
    raise ValueError(f"Invalid structured model response: {error}") from error
