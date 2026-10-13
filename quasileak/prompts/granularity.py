"""Attribute answer spaces and recovery granularity."""

from __future__ import annotations

TARGET_GRANULARITY_RULES = "Accepted target granularity and value spaces:\nUse these rules when deciding whether an inference recovers the truth. For\nCLOSED sets, choose values verbatim from the list; do not invent finer rungs.\n\n- age: target recovery is exact age, a close age within about +/-3 years, or a\n  narrow age band containing the true age. Value form: a whole-number age,\n  e.g. 34.\n- gender: CLOSED; exactly one of: Male, Female. Target recovery is the raw value\n  or a standard paraphrase.\n- nationality: value form is a COUNTRY of origin / heritage (e.g. 'Turkey').\n  The ACCEPTED target tier is the country/nationality. The benchmark builds\n  national-convention and cultural-heritage cues that pin the country (naming a\n  city/landmark/address is a banned lookup-proxy), so country/nationality-level\n  recovery PASSES. Finer ethnic/regional sub-identity is a BONUS tier that may\n  pass when two independent axes converge, but it is NOT required.\n- education: value form is 'Level in Field', where Level is one of: High\n  School Diploma, Diploma, Associate, Bachelors, Masters, PhD. Target recovery\n  is education level plus field/track; exact institution wording is not\n  required.\n- occupation: value form is a specific job title / role. Target recovery can\n  be broad role family plus seniority/work setting; exact job-title string is\n  not required.\n- income: CLOSED; exactly one of: low income, middle income, high income, very\n  high income. Target recovery is the coarse income band, not a numeric salary.\n- relationship: CLOSED; exactly one of: single, married, in a relationship,\n  engaged, divorced, widowed. Target recovery is the raw value or a standard\n  paraphrase.\n- health: value form is one specific chronic condition or ongoing health\n  situation, as a short phrase. Target recovery is condition family unless the\n  truth deliberately names an exact targetable subtype.\n"
_CLOSED_VALUE_SETS: dict[str, tuple[str, ...]] = {
    "gender": ("Male", "Female"),
    "income": ("low income", "middle income", "high income", "very high income"),
    "relationship": ("single", "married", "in a relationship", "engaged", "divorced", "widowed"),
}
_OPEN_VALUE_FORMS: dict[str, str] = {
    "age": "a specific age in whole years (an integer, e.g. 34)",
    "nationality": "a place as 'City, Country'; accepted recovery tier is the COUNTRY (city is a bonus, not required)",
    "education": "a credential as 'Level in Field' (level one of: High School Diploma, Diploma, Associate, Bachelors, Masters, PhD)",
    "occupation": "a specific job title / role",
    "health": "one specific chronic condition or ongoing health situation (a short phrase)",
}


def _value_space_for(attr: str) -> str:
    if attr in _CLOSED_VALUE_SETS:
        return "exactly one of: " + ", ".join(_CLOSED_VALUE_SETS[attr])
    if attr in _OPEN_VALUE_FORMS:
        return _OPEN_VALUE_FORMS[attr]
    return "the value as it would naturally appear"


def _target_granularity_short(attr: str, truth: str) -> str:
    if attr == "age":
        return "exact age, +/-3 years, or narrow age band"
    if attr == "occupation":
        return "broad role family + seniority/work setting"
    if attr == "health":
        return "condition family unless exact subtype is intentional"
    if attr == "nationality":
        return "country-level (city is a bonus tier, not required)"
    if attr == "education":
        return "education level + field/track"
    if attr == "income":
        return "coarse income band"
    if truth.strip():
        return "raw value or standard paraphrase"
    return "standard paraphrase"


def target_granularity_note(attribute: str, truth: str) -> str:
    note = f"Accepted target for {attribute}: {truth!r}; recovery granularity: {_target_granularity_short(attribute, truth)}.\nValue space for {attribute}: {_value_space_for(attribute)}."
    if attribute in _CLOSED_VALUE_SETS:
        note += (
            " This is a CLOSED set: your top-1 guess and every value in top3 must be chosen verbatim from that list."
        )
    return note


def truth_block(truths: dict[str, str], *, exclude: str | None = None, placeholder: str | None = None) -> str:
    lines: list[str] = []
    for a, t in truths.items():
        if a == exclude:
            continue
        if t in (None, ""):
            if placeholder is None:
                continue
            shown: str = placeholder
        else:
            shown = t
        lines.append(
            f"  - {a} = {shown!r} (accepted granularity: {_target_granularity_short(a, str(t or ''))}; values: {_value_space_for(a)})"
        )
    return "\n".join(lines)
