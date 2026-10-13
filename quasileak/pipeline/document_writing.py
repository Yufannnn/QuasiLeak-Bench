"""Stage 3, document writing: write around the plan and locate every required phrase once."""

from __future__ import annotations

import copy

from ..prompts.document_writer import SYSTEM, build_writer_prompt, span_roles
from ..schemas import validate_documents, validate_grouped
from .spans import occurrences, place, short_cue_sentences


def write_documents(records, writer, config):
    validate_grouped(records, config)
    rows = []
    for record in records:
        sid = record["sample_id"]
        groups = copy.deepcopy(record["groups"])
        decoys = list(record["decoys"]["selected_spans"])
        plan = dict(sets=groups, decoys=decoys, roles=span_roles(sid, groups, decoys))
        cues = [c for group in groups for c in group["cues"]]
        required = cues + decoys
        if len(set(required)) != len(required):
            raise ValueError(f"{sid}: repeated required spans")
        target = int(record["context"]["length"] * config.length_multiplier)
        feedback, short, document, bad, spans = None, [], "", list(required), []
        for attempt in range(config.writer_attempts):
            user = build_writer_prompt(record, plan, target, missing=feedback, blurted=short)
            document = writer.generate(system=SYSTEM, user=user, temperature=config.temperatures["writer" if attempt == 0 else "writer_retry"])
            spans, bad = place(document, required)
            if bad:
                feedback = [
                    f"{s} (you used it more than once, keep exactly one)" if len(occurrences(document, s)) > 1 else s
                    for s in bad
                ]
                short = []
                continue
            feedback = None
            short = short_cue_sentences(document, cues)
            if not short:
                break
        if not document or bad:
            raise ValueError(f"{sid}: writer failed required-span validation after {config.writer_attempts} attempts")
        row = {
            k: copy.deepcopy(record[k])
            for k in ("sample_id", "profile_id", "context_id", "profile", "context", "policy")
        }
        row.update(
            stage="document_writing",
            plan=plan,
            document=document,
            spans=spans,
            target_words=target,
            word_count=len(document.split()),
            short_cue_sentences=len(short),
            writer_attempts=attempt + 1,
        )
        rows.append(row)
    validate_documents(rows, records)
    return rows
