"""Generate distractors and confirm blind-audit guesses against the profile."""

from __future__ import annotations

from ..groups.distractors import DISTRACTOR_KINDS
from ..groups.keys import content_tokens, reuse_key
from ..llm.distractor_audit import collect_complete_verdicts
from ..llm.parsing import parse_object, probability, request_object
from ..llm.recovery import recovered_pure
from ..prompts import distractors as prompt
from ..schemas import require

PROPOSALS_PER_ROUND = 22
AUDIT_CONFIDENCE = 0.5  # a blind guess counts only at or above this confidence
CLEAN_ENOUGH = 4  # stop proposing once this many candidates pass the audit


def overlaps(a: set[str], b: set[str]) -> bool:
    """Content-word overlap: one set contains the other, or they share 60% of the smaller one."""
    return bool(a and b) and (a <= b or b <= a or len(a & b) / min(len(a), len(b)) >= 0.6)


def generate_distractors(record, cues_by_attr, generator, probe, config, prior_use=None):
    profile, context = record["profile"], record["context"]
    span_attr = {s: a for a, cues in cues_by_attr.items() for s in cues}
    policy_class = {a: cls for cls, attrs in record["policy"].items() for a in attrs}
    real_labeled = "\n".join(f"[{policy_class[a].upper()} {a}] {s}" for s, a in span_attr.items()) or "(none)"
    real_plain = "\n".join(f"- {s}" for s in span_attr) or "(none)"
    real_tokens = [content_tokens(s) for s in span_attr]
    seen, candidates = set(), []
    prior_use = prior_use or {}
    for round_index in range(config.distractor_rounds):
        user = prompt.DECOY_TEMPLATE.format(
            n=PROPOSALS_PER_ROUND,
            ctx=context["context_id"],
            recipient=context["recipient"],
            context_description=context["description"],
            truths="\n".join(f"  {a}: {v}" for a, v in profile.items()),
            realcues=real_labeled,
        )
        obj = request_object(generator, system=prompt.DECOY_SYSTEM, user=user, temperature=config.temperatures["distractors"])
        require(isinstance(obj.get("decoys"), list), "Distractor response requires decoys")
        batch = []
        for i, decoy in enumerate(obj["decoys"]):
            require(isinstance(decoy, dict), "Invalid distractor")
            span = decoy.get("span")
            require(isinstance(span, str) and bool(span.strip()), "Distractor requires a span")
            require(decoy.get("kind") in DISTRACTOR_KINDS, "Unknown distractor kind")
            probability(decoy.get("tempting_score"))
            tokens = content_tokens(span)
            if (
                any(overlaps(tokens, t) for t in real_tokens)
                or span.lower() in seen
                or prior_use.get(reuse_key(span), 0) >= config.distractor_reuse_cap
            ):
                continue
            seen.add(span.lower())
            batch.append(
                dict(
                    decoy_id=f"d{round_index + 1}-{i + 1}",
                    spans=[span],
                    kind=decoy["kind"],
                    tempting_score=decoy["tempting_score"],
                    why_tempting=decoy.get("why_tempting", ""),
                    why_nonleaking_cold=decoy.get("why_nonleaking_cold", ""),
                )
            )
        if not batch:
            continue

        def audit(pending, attempt):
            user = prompt.DECOY_AUDIT_TEMPLATE.format(
                ctx=context["context_id"],
                realcues=real_plain,
                decoys="\n".join(f"  {c['decoy_id']}: spans={c['spans']}" for c in pending),
            )
            if attempt > 1:
                user += "\n\nReturn the complete requested JSON object, with a verdict for every decoy_id listed."
            return parse_object(probe.generate(system=prompt.DECOY_AUDIT_SYSTEM, user=user, temperature=0.0))

        verdicts, missing = collect_complete_verdicts(batch, audit, max_attempts=2)
        for decoy in batch:
            cid = decoy["decoy_id"]
            leaks = []
            if cid in missing:
                leaks.append({"case": "missing_verdict"})
            for leak in verdicts.get(cid, {}).get("leak_candidates", []):
                attr, guess = leak.get("attribute"), leak.get("guess", "")
                conf = probability(leak.get("confidence"))
                require(
                    attr in profile and leak.get("case") in {"singleton", "decoy_realcue"},
                    "Invalid blind-audit evidence",
                )
                if conf < AUDIT_CONFIDENCE or not guess:
                    continue
                if leak["case"] == "decoy_realcue":
                    realcue = leak.get("realcue_span", "")
                    own = span_attr.get(realcue)
                    if own is None:
                        rc = content_tokens(realcue)
                        own = next((a for span, a in span_attr.items() if overlaps(rc, content_tokens(span))), None)
                    cue_tokens = set().union(*(content_tokens(s) for s, a in span_attr.items() if a == attr))
                    if own == attr and not (content_tokens(decoy["spans"][0]) & cue_tokens):
                        continue
                truth = profile[attr]
                recovered = recovered_pure(attr, truth, guess)
                if recovered is True or (
                    recovered is None and (truth.lower() in guess.lower() or guess.lower() in truth.lower())
                ):
                    leaks.append(leak)
            decoy["cold_audit"] = verdicts.get(cid)
            decoy["cold_leaks"] = leaks
            candidates.append(decoy)
        if sum(not c["cold_leaks"] for c in candidates) >= CLEAN_ENOUGH:
            break
    return candidates
