"""Strict JSONL input and atomic output."""

from __future__ import annotations

import gzip
import json
import os
import tempfile
from pathlib import Path


def reject_constant(name):
    raise ValueError(f"{name} is not valid JSON")


def read_jsonl(path):
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    rows = []
    with opener(path, "rt", encoding="utf-8-sig") as source:
        for number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line, parse_constant=reject_constant)
            except ValueError as exc:
                raise ValueError(f"Invalid JSON on line {number} of {path.name}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Line {number} of {path.name} must be an object")
            rows.append(row)
    return rows


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
            for row in rows:
                output.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
