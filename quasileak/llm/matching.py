"""Rank a probe's guesses against the true value."""

from __future__ import annotations

import re
import unicodedata

from ..confidence import is_closed_set, values_match

_EDUCATION_LEVELS: dict[str, list[str]] = {
    "masters": [
        "masters",
        "master",
        "ma",
        "m.a.",
        "msc",
        "m.sc.",
        "ms",
        "m.s.",
        "mj",
        "mfa",
        "m.f.a.",
        "mba",
        "m.b.a.",
        "mph",
        "m.p.h.",
        "msw",
        "m.s.w.",
        "med",
        "m.ed.",
        "llm",
        "ll.m.",
        "graduate degree",
        "graduate-level",
        "graduate level",
        "graduate program",
        "second-cycle",
        "second cycle",
        "postgraduate",
        "post-graduate",
        "post graduate",
        "grad school",
    ],
    "bachelors": [
        "bachelors",
        "bachelor",
        "ba",
        "b.a.",
        "bs",
        "b.s.",
        "bsc",
        "b.sc.",
        "beng",
        "b.eng.",
        "bfa",
        "b.f.a.",
        "llb",
        "ll.b.",
        "undergraduate",
        "undergrad",
        "first-cycle",
        "first cycle",
        "baccalaureate",
        "four-year degree",
    ],
    "phd": [
        "phd",
        "ph.d.",
        "ph.d",
        "doctorate",
        "doctoral",
        "doctor of philosophy",
        "third-cycle",
        "third cycle",
        "dphil",
        "d.phil.",
        "doctoral degree",
        "doctoral program",
    ],
    "associate": [
        "associate",
        "associates",
        "associate degree",
        "aa",
        "a.a.",
        "as",
        "a.s.",
        "two-year degree",
        "community college degree",
    ],
    "high_school": [
        "high school",
        "highschool",
        "high-school",
        "h.s.",
        "secondary school",
        "secondary education",
        "ged",
        "a-levels",
        "a level",
        "high school diploma",
        "secondary diploma",
        "high school graduate",
    ],
    "vocational": [
        "vocational",
        "trade school",
        "technical school",
        "vocational training",
        "apprenticeship",
        "certificate program",
        "tafe",
        "diploma",
    ],
}


def _education_parse(s: str) -> tuple[str | None, str]:
    raw = _normalize_for_match(s)
    if not raw:
        return None, ""
    matched_level: str | None = None
    matched_syn: str | None = None
    for key, syns in _EDUCATION_LEVELS.items():
        for syn in sorted(syns, key=len, reverse=True):
            syn_norm = _normalize_for_match(syn)
            if not syn_norm:
                continue
            if _word_match(syn_norm, raw):
                matched_level = key
                matched_syn = syn_norm
                break
        if matched_level:
            break
    residual = raw
    if matched_syn:
        for syn in sorted(_EDUCATION_LEVELS[matched_level], key=len, reverse=True):
            syn_norm = _normalize_for_match(syn)
            pat = re.compile(f"(?<![A-Za-z]){re.escape(syn_norm)}(?![A-Za-z])", re.IGNORECASE)
            residual = pat.sub(" ", residual)
    residual = re.sub(
        r"\b(in|of|the|a|an|degree|program|studies|major|track|concentration|field|with|focus|specialization)\b",
        " ",
        residual,
    )
    residual = re.sub(r"\s+", " ", residual).strip()
    return matched_level, residual


def _education_match(guess: str, truth: str) -> bool:
    g_level, g_field = _education_parse(guess)
    t_level, t_field = _education_parse(truth)
    if t_level and g_level and t_level != g_level:
        return False
    if not t_field:
        return bool(t_level and g_level and t_level == g_level)
    if not g_field:
        return False
    if t_field == g_field or t_field in g_field or g_field in t_field:
        return True
    t_words = set(t_field.split())
    g_words = set(g_field.split())
    if t_words and t_words.issubset(g_words):
        return True
    return False


_HEALTH_GROUPS: dict[str, list[str]] = {
    "high blood pressure": [
        "high blood pressure",
        "hypertension",
        "hypertensive",
        "raised blood pressure",
        "elevated blood pressure",
        "high bp",
    ],
    "seasonal allergies": [
        "seasonal allergies",
        "seasonal allergy",
        "hay fever",
        "pollen allergy",
        "pollen allergies",
        "allergic rhinitis",
        "pollen sensitivity",
        "spring allergies",
    ],
    "diabetes": [
        "diabetes",
        "diabetic",
        "type 1 diabetes",
        "type 2 diabetes",
        "type i diabetes",
        "type ii diabetes",
        "high blood sugar",
    ],
    "asthma": ["asthma", "asthmatic"],
    "depression": ["depression", "depressive", "major depressive disorder", "mdd"],
    "anxiety": [
        "anxiety",
        "anxious",
        "generalized anxiety",
        "panic disorder",
        "panic attack",
        "panic attacks",
        "panic episode",
        "panic episodes",
        "anxiety disorder",
        "ssri",
        "sertraline",
        "escitalopram",
    ],
    "arthritis": ["arthritis", "arthritic", "osteoarthritis", "rheumatoid arthritis", "joint inflammation"],
    "joint replacement": [
        "joint replacement",
        "hip replacement",
        "knee replacement",
        "orthopedic recovery",
        "orthopaedic recovery",
        "post-op mobility",
        "post operative mobility",
        "joint surgery recovery",
    ],
    "chronic pain": [
        "chronic pain",
        "back pain",
        "chronic back pain",
        "lower back pain",
        "lumbar pain",
        "musculoskeletal pain",
    ],
    "insomnia": ["insomnia", "sleep disorder", "sleep difficulty", "sleeplessness", "poor sleep", "sleep disturbance"],
    "migraine": ["migraine", "migraines", "headache disorder", "severe headaches"],
    "high cholesterol": [
        "high cholesterol",
        "cholesterol",
        "hyperlipidemia",
        "raised cholesterol",
        "elevated cholesterol",
    ],
    "pregnancy": ["pregnancy", "pregnant", "postpartum", "post-partum", "antenatal", "prenatal", "maternal health"],
}
_HEALTH_KEY_ORDER = [
    "joint replacement",
    "chronic pain",
    "high blood pressure",
    "seasonal allergies",
    "high cholesterol",
    "pregnancy",
    "diabetes",
    "asthma",
    "depression",
    "anxiety",
    "insomnia",
    "migraine",
    "arthritis",
]


def _digits_only(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())


def _is_numeric_truth(truth: str) -> bool:
    digits = _digits_only(truth)
    return bool(digits) and digits == truth.strip()


_DECADE_WORDS = ("s", "decade", "around", "mid", "early", "late")


def _age_match(guess: str, truth_age: int, tolerance: int = 3) -> bool:
    guess_lower = guess.lower().strip()
    if not guess_lower:
        return False

    nums = [int(n) for n in re.findall(r"\d+", guess_lower)]
    for n in nums:
        if abs(n - truth_age) <= tolerance:
            return True
        if n % 10 == 0 and 0 <= truth_age - n < 10 and any(w in guess_lower for w in _DECADE_WORDS):
            return True
    return False


_WORD_BOUND_CACHE: dict[str, re.Pattern[str]] = {}


def _word_match(needle: str, haystack: str) -> bool:
    pat = _WORD_BOUND_CACHE.get(needle)
    if pat is None:
        pat = re.compile(f"(?<![A-Za-z]){re.escape(needle)}(?![A-Za-z])", re.IGNORECASE)
        _WORD_BOUND_CACHE[needle] = pat
    return bool(pat.search(haystack))


_TRANSLITERATE: dict[str, str] = {
    "ø": "o",
    "æ": "ae",
    "å": "a",
    "ä": "a",
    "ö": "o",
    "ü": "u",
    "ß": "ss",
    "é": "e",
    "è": "e",
    "ê": "e",
    "ë": "e",
    "á": "a",
    "à": "a",
    "â": "a",
    "í": "i",
    "ì": "i",
    "î": "i",
    "ó": "o",
    "ò": "o",
    "ô": "o",
    "ú": "u",
    "ù": "u",
    "û": "u",
    "ñ": "n",
    "ç": "c",
}


def _normalize_for_match(s: str) -> str:
    lower = s.lower().strip()
    nfd = unicodedata.normalize("NFKD", lower)
    stripped = "".join(ch for ch in nfd if not unicodedata.combining(ch))
    for src, dst in _TRANSLITERATE.items():
        if src in stripped:
            stripped = stripped.replace(src, dst)
    for ap in ("'", "’", "‘", "ʼ"):
        if ap in stripped:
            stripped = stripped.replace(ap, "")
    return re.sub(r"\s+", " ", stripped).strip()


def _categorical_match(
    guess: str, truth: str, groups: dict[str, list[str]], key_order: list[str] | None = None
) -> bool | None:
    guess_lower = guess.lower().strip()
    truth_lower = truth.lower().strip()
    truth_key: str | None = None
    keys = key_order if key_order is not None else list(groups)
    for k in keys:
        if _word_match(k, truth_lower) or any(_word_match(syn, truth_lower) for syn in groups[k]):
            truth_key = k
            break
    if truth_key is None:
        return None
    if any(_word_match(syn, guess_lower) for syn in groups[truth_key]):
        return True
    return False


_OCCUPATION_ROLE_GROUPS: dict[str, list[str]] = {
    "software_engineer": [
        "software engineer",
        "software developer",
        "developer",
        "programmer",
        "coding",
        "backend",
        "front-end",
        "frontend",
        "full-stack",
        "full stack",
        "engineering role",
        "software role",
    ],
    "engineer": ["engineer", "engineering", "technical engineer"],
    "teacher": [
        "teacher",
        "teaching",
        "educator",
        "instructor",
        "schoolteacher",
        "school teacher",
        "classroom",
        "lecturer",
        "tutor",
    ],
    "nurse": ["nurse", "nursing", "clinical nursing", "ward", "scrub roster", "healthcare nursing"],
    "doctor": ["doctor", "physician", "medical doctor", "clinician", "surgeon", "gp", "general practitioner"],
    "manager": [
        "manager",
        "management",
        "managerial",
        "supervisor",
        "lead",
        "director",
        "head",
        "team lead",
        "people manager",
    ],
    "marketing": ["marketing", "brand", "campaign", "market research", "communications", "growth"],
    "finance": ["finance", "financial", "accountant", "accounting", "bookkeeper", "banking", "analyst", "payroll"],
    "law": ["lawyer", "legal", "solicitor", "barrister", "attorney", "paralegal"],
    "journalism": ["journalist", "journalism", "reporter", "editor", "newsroom", "writer"],
    "design": ["designer", "design", "ux", "ui", "graphic", "creative"],
    "research": ["researcher", "research", "scientist", "laboratory", "lab", "academic"],
    "retired": ["retired", "former", "pensioner", "post-career"],
}
_OCCUPATION_STOPWORDS = {
    "a",
    "an",
    "and",
    "at",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "the",
    "to",
    "with",
    "role",
    "worker",
    "job",
    "staff",
    "employee",
    "professional",
    "specialist",
    "senior",
    "junior",
    "assistant",
    "associate",
    "principal",
    "chief",
    "years",
    "year",
    "full",
    "time",
    "part",
    "remote",
    "hybrid",
    "office",
    "retired",
    "former",
}


def _occupation_role_keys(text: str) -> set[str]:
    norm = _normalize_for_match(text)
    keys: set[str] = set()
    for key, syns in _OCCUPATION_ROLE_GROUPS.items():
        if any(_word_match(_normalize_for_match(syn), norm) for syn in syns):
            keys.add(key)
    return keys


def _occupation_content_tokens(text: str) -> set[str]:
    norm = _normalize_for_match(text)
    tokens = set(re.findall("[a-z0-9]+", norm))
    return {t for t in tokens if len(t) >= 4 and t not in _OCCUPATION_STOPWORDS}


def _occupation_match(guess: str, truth: str) -> bool:
    gnorm = _normalize_for_match(guess)
    tnorm = _normalize_for_match(truth)
    if not gnorm or not tnorm:
        return False
    if tnorm == gnorm or tnorm in gnorm or gnorm in tnorm:
        return True
    g_roles = _occupation_role_keys(guess)
    t_roles = _occupation_role_keys(truth)
    if g_roles and t_roles and g_roles & t_roles:
        return True
    g_tokens = _occupation_content_tokens(guess)
    t_tokens = _occupation_content_tokens(truth)
    overlap = g_tokens & t_tokens
    if overlap and (g_roles or t_roles):
        return True
    return len(overlap) >= 2


def truth_in_top(top3: list[str], truth: str, attribute: str | None = None) -> int:
    truth_lower = truth.lower().strip()
    if not truth_lower:
        return 99
    tnorm = _normalize_for_match(truth)
    is_age = attribute == "age" and _is_numeric_truth(truth)
    truth_age = int(_digits_only(truth)) if is_age else None
    for i, g in enumerate(top3):
        guess_lower = str(g).lower().strip()
        if not guess_lower:
            continue
        if is_closed_set(attribute):
            if values_match(attribute, truth, g):
                return i + 1
            continue
        if truth_lower == guess_lower or truth_lower in guess_lower or guess_lower in truth_lower:
            return i + 1
        gnorm = _normalize_for_match(g)
        if tnorm and gnorm and (tnorm == gnorm or tnorm in gnorm or gnorm in tnorm):
            return i + 1
        if is_age and truth_age is not None and _age_match(guess_lower, truth_age):
            return i + 1
        if attribute == "health" and _categorical_match(guess_lower, truth_lower, _HEALTH_GROUPS, _HEALTH_KEY_ORDER):
            return i + 1
        if attribute == "education" and _education_match(g, truth):
            return i + 1
        if attribute == "occupation" and _occupation_match(g, truth):
            return i + 1
    return 99


_JOINT_PIN_DENIAL_PATTERNS = (
    "doesn't uniquely pin",
    "does not uniquely pin",
    "doesn't uniquely commit",
    "does not uniquely commit",
    "not uniquely commit",
    "doesn't pin",
    "does not pin",
    "doesn't commit",
    "does not commit",
    "without committing",
    "doesn't isolate",
    "does not isolate",
    "without isolating",
    "doesn't single out",
    "does not single out",
    "doesn't identify",
    "does not identify",
    "not uniquely identify",
    "not uniquely pin",
    "not enough to uniquely pin",
    "not sufficient to uniquely pin",
    "not pinned",
    "not enough to pin",
    "not sufficient to pin",
    "narrowed but not pinned",
    "only narrows",
    "merely narrows",
    "just narrows",
    "narrows but does not",
    "narrows but doesn't",
    "leans toward",
    "leans to",
    "suggests but",
    "admits several",
    "admits multiple",
    "too broad",
    "not diagnostic",
    "cannot distinguish",
    "can't distinguish",
    "doesn't distinguish",
    "does not distinguish",
    "span the full",
    "spans the full",
    "no mechanism to isolate",
    "without any axis",
    "no axis to isolate",
    "broadly rather than",
)
_PAIR_REDUNDANCY_PATTERNS = (
    "dominant identifier",
    "without narrowing further",
    "doesn't narrow further",
    "does not narrow further",
    "one cue is redundant",
    "redundant",
)
_JOINT_PIN_DENIAL_REGEXES = (
    re.compile(
        r"\b(?:not|cannot|can't|does not|doesn't)\b.{0,50}\buniquely\b.{0,40}\b(?:pin|commit|identify|isolate|distinguish)\b"
    ),
    re.compile(r"\b(?:not enough|not sufficient)\b.{0,50}\b(?:pin|commit|identify|isolate|distinguish)\b"),
    re.compile(
        r"\badmits?\b[^.]{0,60}?\b(?:equally|comparabl|similarly\s+(?:plausibl|likel|strong)|other\s+plausibl|another\s+plausibl|reasonable\s+alternativ|strong\s+alternativ|close\s+(?:second|call|competitor))"
    ),
)


def _reasoning_rejects_joint_pin(reasoning: str) -> bool:
    text = " ".join(str(reasoning or "").lower().split())
    if not text:
        return False
    return (
        any(p in text for p in _JOINT_PIN_DENIAL_PATTERNS)
        or any(p in text for p in _PAIR_REDUNDANCY_PATTERNS)
        or any(rx.search(text) for rx in _JOINT_PIN_DENIAL_REGEXES)
    )


def truth_in_top_nonpin(top: list[str], truth: str, *, attribute: str) -> int:
    rank = truth_in_top(top, truth, attribute=attribute)
    return 2 if rank == 1 else rank


def joint_rank(rec: dict, top3: list[str], truth: str, attribute: str, *, pair_threshold: float) -> int:
    """1 when the pair pins the truth at the threshold, otherwise the truth's rank in top3 (99 if absent)."""
    if _reasoning_rejects_joint_pin(rec["reasoning"]):
        return 99
    if (
        rec["top1_pins_truth"]
        and truth_in_top(top3, truth, attribute=attribute) == 1
        and rec["confidence"] >= pair_threshold
    ):
        return 1
    return truth_in_top_nonpin(top3, truth, attribute=attribute)
