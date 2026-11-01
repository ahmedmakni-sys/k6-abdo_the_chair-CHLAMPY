"""Safety layer around the coach.

Input side: spots requests for medical judgement, signs of serious distress, personal
data and attempts to override instructions. Output side: blocks clinical vocabulary,
claims of certainty about the future, and numbers that are not in the evidence.
"""

import re

CLINICAL_TERMS = [
    r"adhd", r"autis\w*", r"asperger\w*", r"dementia", r"alzheimer\w*", r"parkinson\w*",
    r"dyslexi\w*", r"dyscalculi\w*", r"depress\w*", r"bipolar", r"schizo\w*", r"anxiety", r"ocd\b", r"ptsd",
    r"disorder\w*", r"diagnos\w*", r"symptom\w*", r"patient\w*", r"therap\w*", r"treatment\w*", r"medication\w*",
    r"impair\w*", r"deficit\w*", r"disease\w*", r"illness\w*", r"patholog\w*", r"clinical\w*", r"syndrome\w*",
    r"cognitive decline", r"brain damage", r"neurodegenerat\w*", r"prognos\w*", r"disabilit\w*", r"\biq\b",
]
_CLINICAL_RE = re.compile(r"\b(" + "|".join(CLINICAL_TERMS) + r")", re.IGNORECASE)

CERTAINTY_PATTERNS = [
    r"\byou will (reach|improve|achieve|get|be|become|score|hit)\b",
    r"\bguarantee\w*\b", r"\bdefinitely will\b", r"\bcertainly will\b", r"\bwithout (a )?doubt\b",
    r"\bproven to\b", r"\bpermanently\b",
]
_CERTAINTY_RE = re.compile("|".join(CERTAINTY_PATTERNS), re.IGNORECASE)

_MEDICAL_ASK_RE = re.compile(
    r"\b(do i have|have i got|am i|is this|could (this|it) be|signs? of|test(ing)? for|tell me if i('m| am)?|"
    r"should i (take|stop|start)|diagnos\w*)\b.{0,60}\b(" + "|".join(CLINICAL_TERMS) + r"|sick|ill|mentally|medic\w*|pill\w*|dose)",
    re.IGNORECASE,
)
_ANY_CLINICAL_RE = _CLINICAL_RE

_DISTRESS_RE = re.compile(
    r"\b(kill myself|suicid\w*|end my life|hurt myself|self[- ]harm\w*|want to die|don'?t want to (be alive|live)|"
    r"no reason to live)\b",
    re.IGNORECASE,
)

_INJECTION_RE = re.compile(
    r"(ignore (all |any |your |the )?(previous|prior|above|earlier)|disregard (your|the|all) (instructions|rules|system)|"
    r"system prompt|you are now|act as (a )?(doctor|psychiatrist|psychologist|neurologist)|pretend (to be|you are)|"
    r"reveal your (prompt|instructions)|jailbreak|developer mode)",
    re.IGNORECASE,
)

_PII_PATTERNS = {
    "email address": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone number": re.compile(r"(?<!\d)(\+?\d[\d\s().-]{7,}\d)(?!\d)"),
    "identity or card number": re.compile(r"(?<!\d)\d{8,19}(?!\d)"),
}

DISTRESS_REPLY = (
    "I'm really glad you told me. I'm a practice coach and I'm not the right support for this, but you deserve "
    "real support right now. Please contact your local emergency number or a crisis line, or reach out to someone "
    "you trust and tell them what you just told me. Your exercises can wait; you matter more than any of them."
)

MEDICAL_REPLY = (
    "I can't answer questions about health conditions, and nothing here can tell you that. These exercises only "
    "show how you did on practice tasks, with a range around each estimate. If something about your memory, focus "
    "or mood worries you, a qualified health professional is the right person to ask. I'm happy to talk about what "
    "the practice results show, or how to plan your next sessions."
)

INJECTION_REPLY = (
    "I'll stay in my role as a practice coach and keep working from your session results. "
    "Ask me about a score, why it moved, or what to practise next."
)


def classify_input(text):
    """Return a list of labels for the user's message, most serious first."""
    text = text or ""
    labels = []
    if _DISTRESS_RE.search(text):
        labels.append("distress")
    if _MEDICAL_ASK_RE.search(text) or _ANY_CLINICAL_RE.search(text):
        labels.append("medical")
    if _INJECTION_RE.search(text):
        labels.append("injection")
    if find_personal_data(text):
        labels.append("personal_data")
    return labels


def find_personal_data(text):
    return [name for name, pat in _PII_PATTERNS.items() if pat.search(text or "")]


def redact_personal_data(text):
    out = text or ""
    for name, pat in _PII_PATTERNS.items():
        out = pat.sub(f"[{name} removed]", out)
    return out


def _allowed_numbers(evidence_text, extra=()):
    numbers = {float(n) for n in re.findall(r"\d+(?:\.\d+)?", evidence_text)}
    numbers.update(float(x) for x in extra)
    return numbers


def ungrounded_numbers(text, evidence_text):
    """Numbers in text that do not appear in the evidence, within rounding distance."""
    allowed = _allowed_numbers(evidence_text)
    bad = []
    for match in re.findall(r"\d+(?:\.\d+)?", text or ""):
        value = float(match)
        # Small counts such as "two or three more sessions" are ordinary speech.
        if value <= 12:
            continue
        if not any(abs(value - a) <= 1.0 for a in allowed):
            bad.append(match)
    return bad


def check_output(text, evidence_text=None):
    """Validate coach output. Returns dict(passed, problems)."""
    problems = []
    clinical = sorted({m.group(0).lower() for m in _CLINICAL_RE.finditer(text or "")})
    if clinical:
        problems.append("clinical language: " + ", ".join(clinical))
    certain = [m.group(0).lower() for m in _CERTAINTY_RE.finditer(text or "")]
    if certain:
        problems.append("claims certainty: " + ", ".join(sorted(set(certain))))
    if evidence_text is not None:
        bad = ungrounded_numbers(text, evidence_text)
        if bad:
            problems.append("numbers not in the evidence: " + ", ".join(bad))
    return dict(passed=not problems, problems=problems)
