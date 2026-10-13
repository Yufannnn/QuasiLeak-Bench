"""Singleton and pair probes."""

from __future__ import annotations

from dataclasses import asdict

from .. import confidence
from ..config import ATTRIBUTES
from ..groups.candidates import Candidate, candidate_pairs
from ..llm.matching import joint_rank, truth_in_top, truth_in_top_nonpin
from ..llm.parsing import probe_rows, request_object
from ..prompts import probing as prompt
from ..prompts.granularity import target_granularity_note, truth_block


def cross_attribute_bar(attribute):
    return min(confidence.leak_bar(a) for a in ATTRIBUTES if a != attribute)


def probe_attribute(attribute, candidates, profile, client, config):
    truth = profile[attribute]
    cues = [Candidate(**{k: c[k] for k in ("cue", "hints_at", "also_fits", "mechanism")}) for c in candidates]
    threshold = confidence.leak_bar(attribute)
    if cues:
        user = prompt.ALONE_TEMPLATE.format(
            attribute=attribute,
            truth=truth,
            target_granularity_note=target_granularity_note(attribute, truth),
            other_truths_block=truth_block(profile, exclude=attribute),
            singleton_threshold=threshold,
            cross_leak_threshold=cross_attribute_bar(attribute),
            cue_lines="\n".join(f"  {i + 1}. {c.cue!r}" for i, c in enumerate(cues)),
        )
        obj = request_object(
            client,
            system=prompt.ALONE_SYSTEM,
            user=user,
            validate=lambda o: probe_rows(o, [str(i + 1) for i in range(len(cues))], singleton=True),
        )
        for i, cue in enumerate(cues):
            rec = obj[str(i + 1)]
            cue.alone_top3 = confidence.sanitize_ranked(attribute, rec["top3"])[:3]
            if not cue.alone_top3:
                raise ValueError("Singleton returned no valid ranked values")
            cue.alone_confidence, cue.alone_reasoning = rec["confidence"], rec["reasoning"]
            cue.alone_rank = (
                1
                if rec["top1_pins_truth"]
                and rec["confidence"] >= threshold
                and truth_in_top(cue.alone_top3, truth, attribute=attribute) == 1
                else truth_in_top_nonpin(cue.alone_top3, truth, attribute=attribute)
            )
            cue.also_leaks = rec["also_leaks"]
            if any(leak["attribute"] not in profile or leak["attribute"] == attribute for leak in cue.also_leaks):
                raise ValueError("Invalid secondary attribute in singleton response")
            cross = any(leak["confidence"] >= confidence.leak_bar(leak["attribute"]) for leak in cue.also_leaks)
            if cross:
                cue.singleton_drop_reason = "cross_attr_leak"
            elif rec["confidence"] >= threshold:
                cue.singleton_drop_reason = "target_singleton"
            elif confidence.lift(rec["confidence"], attribute) <= 0:
                cue.singleton_drop_reason = "target_at_chance"
            cue.drops_at_singleton = bool(cue.singleton_drop_reason)
    surviving = [c for c in cues if not c.drops_at_singleton]
    pairs = candidate_pairs(surviving, truth=truth, max_pairs=config.max_pairs)
    results = []
    pair_bar = confidence.reveal_bar(attribute)
    if pairs:
        user = prompt.PAIR_TEMPLATE.format(
            attribute=attribute,
            truth=truth,
            target_granularity_note=target_granularity_note(attribute, truth),
            threshold=pair_bar,
            pair_lines="\n".join(f"  {i + 1}. A: {a.cue!r}    B: {b.cue!r}" for i, (a, b) in enumerate(pairs)),
        )
        obj = request_object(
            client,
            system=prompt.PAIR_SYSTEM,
            user=user,
            validate=lambda o: probe_rows(o, [str(i + 1) for i in range(len(pairs))]),
            attempts=4,
        )
        for i, (a, b) in enumerate(pairs):
            rec = obj[str(i + 1)]
            ranked = confidence.sanitize_ranked(attribute, rec["top3"])[:3]
            rank = joint_rank(rec, ranked, truth, attribute, pair_threshold=pair_bar)
            results.append(
                dict(
                    cue_a=a.cue,
                    cue_b=b.cue,
                    top3=ranked,
                    reasoning=rec["reasoning"],
                    joint_rank=rank,
                    joint_confidence=rec["confidence"],
                )
            )
    viable = [p for p in results if p["joint_rank"] == 1 and p["joint_confidence"] >= pair_bar]
    ranks = {c.cue: c.alone_rank for c in surviving}
    best = max(viable, key=lambda p: ranks[p["cue_a"]] + ranks[p["cue_b"]]) if viable else None
    serialized = [asdict(c) for c in cues]
    return dict(
        attribute=attribute,
        truth=truth,
        candidates=serialized,
        pairs=results,
        surviving_alone=len(surviving),
        winner_pair=[best["cue_a"], best["cue_b"]] if best else None,
        winner_reasoning=best["reasoning"] if best else "",
    )


def replacement_feedback(diagnostics):
    blocks = []
    for d in diagnostics:
        candidates = d["candidates"]
        wrong = [
            c
            for c in candidates
            if c["alone_top3"] and truth_in_top(c["alone_top3"], d["truth"], attribute=d["attribute"]) == 99
        ]
        survivors = [c for c in candidates if not c["drops_at_singleton"]]
        dropped = [c for c in candidates if c["drops_at_singleton"]]
        if d["surviving_alone"] <= 1:
            mode, rejected = "not enough singleton cues", (dropped or candidates) + survivors
        elif wrong and len(wrong) >= max(1, len(candidates) // 2):
            mode, rejected = "wrong neighborhood", wrong
        else:
            mode, rejected = "pair never pinned", survivors
        blocks.append(
            dict(
                attribute=d["attribute"],
                truth=d["truth"],
                failure_mode=mode,
                rejected_cues=[
                    dict(cue=c["cue"], mechanism=c["mechanism"], reviewer_guessed=c["alone_top3"][:3])
                    for c in rejected[-12:]
                ],
                failed_pairs=[
                    dict(
                        pair=[p["cue_a"], p["cue_b"]],
                        top3=p["top3"][:3],
                        confidence=round(p["joint_confidence"], 3),
                        reason=p["reasoning"][:180],
                    )
                    for p in sorted(d["pairs"], key=lambda p: -p["joint_confidence"])[:6]
                ],
            )
        )
    return blocks
