"""Document-writing prompts and deterministic discourse roles."""

import hashlib
import random

SYSTEM = 'You write realistic first-person communications for a privacy research benchmark. Output ONLY the message body -- no commentary, markdown, labels, or meta-talk about phrases/cues/the audit -- in the author\'s first-person voice from the first word. English only.\n\nREQUIRED PHRASES \n- Embed every required phrase given in the task character-for-character: preserve spelling, capitalization, hyphens, apostrophes, contractions, and word order; keep each contiguous and unaltered; never paraphrase. Prefer each exactly once. \n\nATTRIBUTE CONTAINMENT \n- The task gives the author\'s full profile and a SURFACE PLAN marking which attributes are SURFACED (encoded by required cue phrases in this document) and which are not. A SURFACED attribute must be inferable ONLY from its cue phrases; a NON-SURFACED attribute must not appear or be inferable at all. The profile values are shown ONLY so you can avoid leaking them -- never state any of them directly; a surfaced value reaches the reader solely through its cue phrases.\n- The surrounding prose stays NEUTRAL on every attribute -- framing, tone, word choice, and incidental detail must not reveal any attribute beyond what the required cue phrases carry. Removing the required phrases should leave a reader unable to recover any attribute.\n- Concretely: don\'t portray the writer as visibly broke or wealthy (income); add no nationality/locale tells (country-specific spelling, agencies, schemes, holidays, conventions); don\'t signal age, relationship status, or health through the general framing; write the context itself neutrally (a second-hand sale is routine decluttering; a refund is a normal return).\n- Do not state any attribute value outside the required phrases; add no extra family roles, diagnoses, salaries, employers, birthplace claims, identity labels, or causal explanations unless already part of a required phrase; create no new links between attributes; add no bridge phrase that explains what a cue refers to, why it matters, whose it is, or how two cues connect.\n- Avoid using these direct framings for a surfaced value: "I\'m from / based in / here in <nationality>"; "I work as a / I am a <occupation>"; "I am studying / my <education> degree"; "I have / diagnosed with <health>"; "I am <relationship status>"; "I am <N> years old / I\'m <N>" (unless that exact phrase is required).\n\nCUES vs DECOYS\n- The REAL cue phrases describe the AUTHOR: weave each as the author\'s own life, first-person and self-attributed (my / I / we). This is what tells a reader the evidence is about the writer -- do not detach a real cue by attributing it to someone else or turning it into a general observation.\n- The DECOY phrases (labeled DECOY) are the opposite: weave each as something external or incidental -- someone else\'s, a passing mention, or ambient detail -- NEVER as the author\'s own attribute. A decoy should tempt a detector yet a cold reader must not be able to attach its value to the writer; do not neutralize it, explain it away, or make it read as the author\'s own value.\n- "Neutral" means value-neutral, not empty: keep ordinary first-person texture and the decoys so the message reads like a real person wrote it -- only the author\'s true attribute VALUES must stay unstated outside the required phrases.\n\nNATURAL DOCUMENT\n- One coherent first-person message appropriate to the context type; weave the required phrases in naturally (not a checklist), each in the semantic role its cue plan describes; avoid bullet lists unless the genre demands them.\n- Pair placement: each QUASI-COMBO pair in the cue plan carries a placement target -- NEAR, MEDIUM, or FAR. Follow these concretely, counting paragraphs:\n  - NEAR: the two halves sit in the SAME sentence or two ADJACENT sentences (zero paragraphs between them).\n  - MEDIUM: put the two halves exactly 2 or 3 paragraphs apart -- one half in some paragraph, the other 2-3 paragraphs later, with a couple of ordinary paragraphs in between. Both halves must stay within the BODY of the message; the gap must NOT reach from the opening to the closing. A MEDIUM pair is "a bit later in the same message," clearly not adjacent yet clearly not end-to-end.\n  - FAR: one half in the opening paragraph(s) and the other in the closing paragraph(s) -- as near to the two ends as the message allows.\n  The ordering of distances must be strict: NEAR < MEDIUM < FAR, and MEDIUM must be visibly closer than FAR (never push a MEDIUM pair toward the two ends). Honor each pair\'s target so pair distances span the full range instead of all landing far apart. Interleave cues from different attributes, and even a NEAR pair must read as ordinary prose -- never a mini-list or an explicit "these two go together" unit that spells out the connection.\n\nBefore returning, silently verify: every required phrase appears exactly and unaltered; the message reads naturally; each pair sits at roughly its target proximity (NEAR/MEDIUM/FAR) while still reading naturally; no surfaced value is disclosed outside the required phrases.'
PROMPT_TEMPLATE = "Task: write {task}, about {length} words -- a natural first-person message that includes every required phrase below VERBATIM and keeps all surrounding prose attribute-neutral. (Full writing, containment, and output rules are in the system prompt.)\n\nAuthor persona:\n{persona_notes}\n\nRequired phrases to include VERBATIM:\n{span_lines}\n\nSuggested placement order:\n{placement_order_lines}\n\nCue plan (use each phrase in its stated role):\n{cue_plan_lines}\n\nAuthor profile (reference ONLY -- never state these values directly; a surfaced value reaches the reader solely through its cue phrases):\n{profile_lines}\n\nSurface plan -- attributes SURFACED via cue phrases in this document (encode only these; every other attribute must stay fully absent):\n{surfaced_lines}\n\nReminder (most-missed): (1) required phrases character-for-character, each once; (2) surrounding prose neutral about the PERSON but thick with invented detail about the SITUATION, never vague; (3) place each QUASI-COMBO pair at its stated proximity target (NEAR/MEDIUM/FAR) so pair distances vary; (4) cue phrases are true of the author and decoy phrases are not -- and nothing about how a sentence is built may betray which kind it carries.\n\nReturn only the final document."
PROFILE_ORDER = ("age", "gender", "nationality", "income", "relationship", "health", "education", "occupation")
ORDER_NAME = {2: "PAIR", 3: "TRIPLE", 4: "QUAD"}
RUN_ALLOW = "One place in this message may open three consecutive sentences with I/My/We if it reads naturally; elsewhere vary the openings. "
RUN_AVOID = "Avoid opening three consecutive sentences with I/My/We. "
VOICE = 'WHO IS WRITING: someone who overshares. They mention their own life, routine and paperwork as they go, the way people do when they are catching up on things. Work every required phrase in exactly as given, let it have its moment, and carry on. Never explain why you are mentioning something, and never call a detail unrelated, irrelevant or a tangent. Do NOT write: "I also finished employer dental enrollment. I know that is not relevant, but I\'m catching up on loose ends."  Write: "I also finished employer dental enrollment while I was clearing out this week\'s paperwork." This document tests whether a privacy system can find the required phrase combos by REASONING about what they mean, so it must not be able to find them by shape alone. Sentences carrying required phrases must be indistinguishable from the rest of the message, and from each other: not systematically longer or shorter, not simpler or more complex, not more often first-person, and never introduced by a recurring frame. Watch the short sentences especially. Do not drop a required phrase into a blurted one-liner such as "I have an annual fee lounge pass." Give it a sentence of ordinary length doing ordinary work. Short sentences are natural and you should still write them, around required phrases no more and no less often than anywhere else. Place the phrases according to the distance plan for each attribute combo. '


# Fixed md5 seeds make the roles and openings reproducible.
def persona_lines(rec, recipient):
    allow = int(hashlib.md5(((rec.get("sample_id") or "x") + "|run3").encode()).hexdigest(), 16) % 5 == 0
    return (
        f"Write in the author's natural first-person voice, addressing a {recipient}. "
        + (RUN_ALLOW if allow else RUN_AVOID)
        + VOICE
    )


ROLE_TEXT = {
    "topic": "ROLE topic -- this phrase may be what its sentence is ABOUT; the request or question can centre on it",
    "support": "ROLE supporting context -- put it in a sentence whose main point is something else; it supplies context in passing, never the sentence's purpose",
    "passing": "ROLE passing background -- a bare, brief self-attributed mention in a SHORT sentence; nothing is built around it",
}
DECOY_RULE = '- DECOY "{ph}": a false lead, not true of the author, and nothing real about them may follow from it. Its whole job is that noticing a planted-looking detail tells a reader nothing, so it has to sit in this message exactly as naturally as the cue phrases do.'
NO_BUNDLE = "Do NOT list several required phrases together as items 'in the same folder', 'also attached', 'nearby', or 'in the same batch' -- they must never arrive as a bundle. "
RULES_TAIL = "NEVER frame any detail as form fields, sample/example/placeholder text, 'automated examples', on-screen prompts, booking screens, templates, dropdowns, or app/system interface content -- write only natural real-world human prose. CONTAINMENT: some contexts (travel, shopping, renting, services) naturally invite a BUDGET or price/affordability level, which reveals INCOME. Do NOT state or imply any budget, spending tier, price range, or affordability -- e.g. 'mid-range budget', 'nothing too expensive', 'happy to splurge', 'on a tight budget', a dollar range -- unless a required phrase above already carries it; give concrete preferences (place, features, timing, dates) instead of a spending level. The same caution applies to any incidental detail that would reveal a NON-surfaced attribute. DENSITY: revealing nothing is not the same as saying nothing. Anything that could plausibly happen in this setting is fair game and wanted, so describe it freely and at length -- what prompted this, what has already happened, what went wrong, what is still unresolved -- and tell it in your own voice, first person, as readily here as anywhere else. Invent plausible specifics for the situation itself: names of forms, reference numbers, product or venue names, dates, clerks and departments, error messages, whatever this setting would really involve. Every other sentence should carry as much concrete detail as the sentences holding required phrases, so that no sentence stands out for being the specific one. The ONLY thing held back is a new fact about who the author IS. If the required phrases are the only places the writing gets specific, or the only places that sound personal, it is too thin. Write a complete message reaching about the requested length."
RETRY_MISSING = " Your previous attempt left out {spans}. Every required phrase has to appear in the message word-for-word, exactly as spelled above -- no rewording, no singular/plural change, no synonym. If one feels awkward for this message, remember the author overshares; give it an offhand moment and keep going."
RETRY_BLURTED = " Your previous attempt dropped a required phrase into a blurted short sentence: {sents}. Keep every required phrase word-for-word, but give each of those a sentence of ordinary length doing ordinary work in the message."


def span_roles(sample_id, sets, decoys=()):
    roles = {}
    groups = [list(s.get("cues") or []) for s in sets]
    if decoys:
        groups.append(list(decoys))
    for gi, spans in enumerate(groups):
        if not spans:
            continue
        rng = random.Random(int(hashlib.md5(f"{sample_id}|role|{gi}".encode()).hexdigest(), 16))
        topical = rng.randrange(len(spans) + 1)
        for si, sp in enumerate(spans):
            roles[sp] = "topic" if si == topical else rng.choice(["support", "passing"])
    return roles


def build_writer_prompt(rec, plan, target_words, missing=None, blurted=None):
    prof = rec.get("profile") or {}
    ctx = rec.get("context") or {}
    recipient = ctx.get("recipient") or "(unspecified recipient)"
    title = ctx.get("name") or rec.get("context_id") or "a message"
    purpose = ctx.get("purpose") or ""
    desc = ctx.get("description") or "a message"
    span_lines, cue_plan, place_lines, surf_lines = [], [], [], []
    roles = plan.get("roles") or {}
    for p in plan["sets"]:
        a, k, dist, cues = p["attr"], p["k"], p["dist"], p["cues"]
        for c in cues:
            role = roles.get(c)
            span_lines.append(f'- "{c}"' + (f"   [{ROLE_TEXT[role]}]" if role else ""))
        place_lines.append(f"- {a}: {dist}")
        surf_lines.append(f"- {a} = {prof.get(a)} (surfaced ONLY via its {k} cue phrase(s))")
        joined = " + ".join(f'"{c}"' for c in cues)
        cue_plan.append(
            f"- {a} QUASI-{ORDER_NAME.get(k, 'COMBO')} (distance {dist}): weave {joined} ALL as the author's own life, spread {dist} apart across the message (never adjacent, none explaining another) -- each weak alone, only together do they reveal {a}."
        )
    for ph in plan["decoys"]:
        role = roles.get(ph)
        span_lines.append(f'- DECOY: "{ph}"' + (f"   [{ROLE_TEXT[role]}]" if role else ""))
        cue_plan.append(DECOY_RULE.format(ph=ph))
    profile_lines = "\n".join(f"- {a}: {prof.get(a)}" for a in PROFILE_ORDER if prof.get(a))
    persona = (
        persona_lines(rec, recipient)
        + "Keep tone/register natural for that recipient and all surrounding prose attribute-neutral. "
        + NO_BUNDLE
        + RULES_TAIL
    )
    if missing:
        persona += RETRY_MISSING.format(spans=", ".join(f'"{m}"' for m in missing))
    if blurted:
        persona += RETRY_BLURTED.format(sents="; ".join(f'"{s}"' for s in blurted))
    task_str = f'a "{title}" message'
    if purpose:
        task_str += f" whose goal is to {purpose}"
    task_str += f". CONTEXT (write the message to fit this exact setting; the setting itself must stay attribute-neutral per the rules above): {desc}"
    return PROMPT_TEMPLATE.format(
        task=task_str,
        length=target_words,
        persona_notes=persona,
        span_lines="\n".join(span_lines) or "(none)",
        placement_order_lines="\n".join(place_lines) or "(no surfaced attributes)",
        cue_plan_lines="\n".join(cue_plan) or "(no cues)",
        profile_lines=profile_lines,
        surfaced_lines="\n".join(surf_lines) or "(NONE -- every attribute stays absent)",
    )
