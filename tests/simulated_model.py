"""Offline stand-in for the proposer, verifier, and writer."""

from __future__ import annotations

import ast
import hashlib
import json
import re

from quasileak import confidence

ATTRIBUTES = ("age", "gender", "nationality", "education", "occupation", "income", "relationship", "health")
_WORDS = {
    "age": "pension letter grandchild visit school reunion retirement party knee brace reading glasses mortgage payoff".split(),
    "gender": "barber appointment razor refill shaving kit gym locker suit fitting tie clip boot polish".split(),
    "nationality": "tea ritual holiday bakery ferry timetable lantern festival market stall river crossing".split(),
    "education": "thesis binder lab notebook seminar badge exam timetable library carrel lecture slides".split(),
    "occupation": "linen invoice tax folder guest billing shift roster supply tally ledger sleeve".split(),
    "income": "payroll slip shared rent budget planner coupon folder premium tier bulk groceries".split(),
    "relationship": "joint account spare key anniversary card wedding album couple booking partner calendar".split(),
    "health": "inhaler refill clinic slot pill organizer glucose strip physio session sleep study".split(),
}
_DISTRACTOR_WORDS = (
    "parcel ribbon receipt envelope waiting ticket packing foam cardboard insert "
    "service number blue lanyard window seat umbrella stand coat hook desk bell "
    "printer tray paper clip visitor pass elevator note hallway sign weekly memo "
    "spare charger folding chair parking stub copy request door code front counter "
    "reply slip archive box meeting room status board delivery van tape roll"
).split()
_NOUNS = (
    "letter note folder slip form card log sheet receipt booklet schedule reminder notice "
    "voucher file packet summary checklist record ticket pass envelope binder statement "
    "invoice report memo calendar entry request copy box tag label list plan update"
).split()
_KINDS = ("near-miss", "near-miss", "admin-artifact", "mundane", "object", "jargon", "wrong-direction")


def _unit(*parts) -> float:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return int(digest[:12], 16) / float(16**12)


def _phrase(words, *parts) -> str:
    a = int(_unit("w1", *parts) * len(words))
    b = int(_unit("w2", *parts) * len(words))
    if a == b:
        b = (b + 1) % len(words)
    return f"{words[a]} {words[b]}"


class SimulatedModel:
    def __init__(self, seed: int = 0, faults: bool = True):
        self.seed = seed
        self.faults = faults
        self.calls = 0
        self.owner: dict[str, str] = {}  # cue text -> attribute it was proposed for

    def generate(self, *, system, user, temperature=0.0):
        self.calls += 1
        # Sampling above temperature 0.5 gives a fresh draw per call, as a sampled model does.
        self.draw = self.calls if temperature > 0.5 else 0
        retrying = "Return the complete requested JSON" in user
        if "You write realistic" in system:
            return self._write(user)
        if "You design QUASI-EVIDENCE" in system:
            reply = self._propose(user)
        elif "SINGLE cues" in system:
            reply = self._singletons(user)
        elif "cue PAIRS" in system:
            reply = self._pairs(user)
        elif "RATIONAL attacker" in system:
            reply = self._joint(user)
        elif "You craft red-herring" in system:
            reply = self._distractors(user)
        elif "cold interaction auditor" in system:
            reply = self._audit(user)
        else:
            raise AssertionError("unrecognised prompt")
        return self._serialize(reply, user, retrying)

    def _serialize(self, reply, user, retrying):
        text = json.dumps(reply, ensure_ascii=False)
        if not self.faults or retrying:
            return text
        roll = _unit(self.seed, "format", user)
        if roll < 0.02:
            return text[:-1]  # truncated JSON
        if roll < 0.05:
            return "```json\n" + text + "\n```"  # fenced JSON
        return text

    def _propose(self, user):
        listed = re.findall(r"^  - (\w+)\s*$", user, flags=re.M) or re.findall(r'"attribute": "(\w+)"', user)
        attributes = list(dict.fromkeys(a for a in listed if a in ATTRIBUTES))
        n = int(re.search(r"exactly (\d+)", user).group(1)) if re.search(r"exactly (\d+)", user) else 8
        retry = "Repair pass" in user
        rejected = set(re.findall(r'"cue": "([^"]+)"', user)) if retry else set()
        salt = _unit(self.seed, "proposal", user, self.draw)
        reply = {}
        for attr in attributes:
            cues, i = [], 0
            while len(cues) < n and i < 200:
                word = _WORDS[attr][
                    int(_unit("head", self.seed, attr, salt if retry else 0, i, user) * len(_WORDS[attr]))
                ]
                noun = _NOUNS[int(_unit("noun", self.seed, attr, salt if retry else 0, i, user) * len(_NOUNS))]
                cue = f"{word} {noun}"
                i += 1
                if self.faults and _unit("variant", cue, i) < 0.05:
                    cue = cue.replace(" ", "-", 1)  # spelling variant of the same cue
                if cue in cues or cue.replace("-", " ") in [c.replace("-", " ") for c in cues]:
                    continue
                if retry and cue in rejected and not (self.faults and _unit("repeat", user) < 0.3):
                    continue
                cues.append(cue)
            for cue in cues:
                self.owner[cue] = attr
            reply[attr] = [
                dict(cue=c, hints_at=f"{attr} signal", mechanism=f"axis {j % 4}", also_fits=["other value"])
                for j, c in enumerate(cues)
            ]
        return reply

    @staticmethod
    def _key(user):
        attribute = re.search(r"- attribute: (\w+)", user).group(1)
        truth = re.search(r"- truth: (.+)", user).group(1).strip()
        return attribute, truth

    def _singletons(self, user):
        attr, truth = self._key(user)
        reply = {}
        for number, raw in re.findall(r"^\s+(\d+)\. (.+)$", user, flags=re.M):
            cue = ast.literal_eval(raw.strip())
            u = _unit(self.seed, "single", attr, cue)
            bar = confidence.leak_bar(attr)
            score = (
                bar + (1 - bar) * 0.5 * u
                if u > 0.85
                else confidence.base(attr) * 0.6 + (bar - confidence.base(attr) * 0.6) * u * 0.9
            )
            leaks = []
            if _unit(self.seed, "cross", cue) < 0.06:
                other = ATTRIBUTES[int(_unit("which", cue) * 8)]
                if other != attr:
                    leaks.append(dict(attribute=other, confidence=0.9, guess="some value"))
            reply[number] = dict(
                top1_pins_truth=score >= bar,
                confidence=round(score, 3),
                top3=[truth, "alternative one", "alternative two"]
                if score >= bar
                else ["alternative one", truth, "alternative two"],
                reasoning="The phrase alone fits several values.",
                also_leaks=leaks,
            )
        return reply

    def _pairs(self, user):
        attr, truth = self._key(user)
        reply = {}
        for number, a, b in re.findall(r"^\s+(\d+)\. A: (.+?)    B: (.+)$", user, flags=re.M):
            cues = sorted([ast.literal_eval(a), ast.literal_eval(b)])
            u = _unit(self.seed, "pair", attr, *cues)
            bar, base = confidence.reveal_bar(attr), confidence.base(attr)
            if u < 0.35:
                score, pins = bar + (1 - bar) * 0.6 * _unit("hi", u), True
            elif u < 0.75:
                score, pins = base + (bar - base) * _unit("mid", u) * 0.98, False
            else:
                score, pins = base * _unit("lo", u), False
            reply[number] = dict(
                top1_pins_truth=pins,
                confidence=round(score, 3),
                top3=[truth, "alternative one", "alternative two"]
                if pins
                else ["alternative one", truth, "alternative two"],
                reasoning="The two details combine along separate lines of evidence.",
            )
        return reply

    def _joint(self, user):
        attr, truth = self._key(user)
        cues = sorted(re.findall(r'"([^"]+)"', user.split("Combos to evaluate", 1)[1].split("Return JSON", 1)[0]))
        own = all(self.owner.get(c) == attr for c in cues)
        u = _unit(self.seed, "joint", attr, *cues)
        bar, base = confidence.reveal_bar(attr), confidence.base(attr)
        if own:
            verified = u < 0.30 + 0.12 * (len(cues) - 2)
        else:
            verified = u < 0.001  # a rare verified secondary reading
        score = (
            bar + (1 - bar) * 0.5 * _unit("v", u)
            if verified
            else (base + (bar - base) * 0.97 * _unit("p", u) if own else base * _unit("s", u))
        )
        return {
            "1": dict(
                reveals=verified,
                confidence=round(score, 3),
                top3=[truth, "alternative one", "alternative two"]
                if verified
                else ["alternative one", truth, "alternative two"],
                reasoning="The cues are read together.",
            )
        }

    def _distractors(self, user):
        n = int(re.search(r"write (\d+) diverse", user).group(1))
        real = re.findall(r"^\[\w+ \w+\] (.+)$", user, flags=re.M)
        salt = _unit(self.seed, "distractors", user, self.draw)
        spans, i = [], 0
        while len(spans) < n and i < 400:
            span = _phrase(_DISTRACTOR_WORDS, self.seed, salt, i)
            i += 1
            if self.faults and real and _unit("overlap", span) < 0.05:
                span = real[0].split()[0] + " " + span.split()[1]  # shares a word with a real cue
            if span not in spans:
                spans.append(span)
        return {
            "decoys": [
                dict(
                    decoy_id=f"d{j + 1}",
                    span=s,
                    kind=_KINDS[int(_unit("kind", s) * len(_KINDS))],
                    tempting_score=round(_unit("tempt", s), 3),
                    why_tempting="Specific detail.",
                    why_nonleaking_cold="Fits almost anyone.",
                )
                for j, s in enumerate(spans)
            ]
        }

    def _audit(self, user):
        ids = re.findall(r"^  (d\d+-\d+):", user, flags=re.M)
        reply = {}
        for i in ids:
            if self.faults and _unit(self.seed, "drop", user, i) < 0.03:
                continue  # incomplete audit
            leaks = []
            if _unit(self.seed, "leak", i, user) < 0.08:
                leaks.append(
                    dict(case="singleton", attribute="gender", guess="Female", confidence=0.8, evidence=i, realcue_span="")
                )
            reply[i] = dict(leak_candidates=leaks, reason="Checked alone and with each real cue.")
        return reply

    def _write(self, user):
        phrases = re.findall(r'^- (?:DECOY: )?"([^"]+)"', user, flags=re.M)
        u = _unit(self.seed, "draft", user, self.draw)
        faulty = self.faults and "previous attempt" not in user
        if faulty and u < 0.10 and phrases:
            phrases = phrases[1:]  # leaves one phrase out
        elif faulty and u < 0.15 and phrases:
            phrases = phrases + phrases[:1]  # repeats one phrase
        sentences = []
        for j, phrase in enumerate(phrases):
            roll = _unit("style", phrase, self.draw) if self.faults else 1.0
            if roll < 0.10:  # sentence-initial capital, which is allowed
                sentences.append(
                    f"{phrase[0].upper() + phrase[1:]} came up again while I was sorting out the details for this week."
                )
            elif faulty and roll < 0.13:  # glued to a suffix, so the phrase is not placed
                sentences.append(
                    f"While sorting out the details for this week I noticed the {phrase}s again on the table."
                )
            elif faulty and roll < 0.16:  # capitalized mid-sentence, which is not allowed
                sentences.append(
                    f"While sorting out the details for this week I noticed the {phrase[0].upper() + phrase[1:]} again."
                )
            else:
                sentences.append(
                    f"While sorting out the details for this week I noticed the {phrase} again on the table."
                )
        paragraphs = [" ".join(sentences[i : i + 3]) for i in range(0, len(sentences), 3)] or [
            "Thank you for your help with this."
        ]
        return "Hello,\n\n" + "\n\n".join(paragraphs) + "\n\nThank you for your help with this request.\n\nBest regards"
