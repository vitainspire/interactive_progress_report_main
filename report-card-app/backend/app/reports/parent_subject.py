"""Per-subject facts + voice narration for the parent-facing paginated
report (see parent_report.py). The parent link shows one page per subject
plus a final conclusion page, instead of the teacher's single dense table —
this module computes, for one subject at a time, the marks/grade history,
a plain classification (good/mid/low/fail), and a trend, then turns that
into both a short on-screen commentary line and a full spoken narration
(Telugu + Romanized, same phonetic-fallback approach as voice_script.py).
Entirely rule-based, no LLM call — same philosophy as the rest of the app.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.reports.numfmt import fmt_num

GRADE_POINTS = {"A1": 10, "A2": 9, "B1": 8, "B2": 7, "C1": 6, "C2": 5, "D1": 4, "D2": 3}


@dataclass
class SubjectExamMark:
    exam_key: str
    marks: object
    max_marks: float
    grade: str


@dataclass
class SubjectFacts:
    name: str
    history: list[SubjectExamMark] = field(default_factory=list)
    classification: str = "mid"  # "good" | "mid" | "low" | "fail"
    trend: str | None = None  # "up" | "down" | "flat" | None (only one exam)


def compute_subject_facts(student: dict, exam_order: list[str], subject_name: str, max_marks_fn) -> SubjectFacts:
    """`max_marks_fn(exam_key) -> float` mirrors card_render.render_card's
    `max_marks` helper, since the max for a subject's cell depends on
    whether that exam is an FA or SA round (settings.fa/sa_marks_per_subject)."""
    ks = [k for k in exam_order if k in student["exams"]]
    history: list[SubjectExamMark] = []
    for key in ks:
        for x in student["exams"][key]["subjects"]:
            if x["name"] == subject_name:
                history.append(SubjectExamMark(exam_key=key, marks=x["marks"], max_marks=max_marks_fn(key), grade=x["grade"]))
                break

    graded = [h.grade for h in history if h.grade in GRADE_POINTS]
    if "D2" in graded:
        classification = "fail"
    elif graded:
        avg = sum(GRADE_POINTS[g] for g in graded) / len(graded)
        if avg >= 8:
            classification = "good"
        elif avg < 6:
            classification = "low"
        else:
            classification = "mid"
    else:
        classification = "mid"

    trend = None
    if len(graded) >= 2:
        first_gp, last_gp = GRADE_POINTS[graded[0]], GRADE_POINTS[graded[-1]]
        trend = "up" if last_gp > first_gp else "down" if last_gp < first_gp else "flat"

    return SubjectFacts(name=subject_name, history=history, classification=classification, trend=trend)


_COMMENTARY_TE = {
    "fail": "ఈ సబ్జెక్టులో ఫెయిల్ అయ్యారు; దీనిపై ప్రత్యేక శ్రద్ధ అవసరం.",
    "low": "మార్కులు కొంచెం తక్కువగా ఉన్నాయి; మరింత సాధన అవసరం.",
    "good": "చాలా బాగా చేస్తున్నారు! ఇదే తీరును కొనసాగించండి.",
    "mid": "మోస్తరుగా చేస్తున్నారు; ఇంకొంచెం కృషితో మెరుగుపడగలరు.",
}
_COMMENTARY_ROMAN = {
    "fail": "Ee subjectlo fail ayyaru; dీpai pratyeka shraddha avasaram.",
    "low": "Marks konchem thakkuvaga unnayi; marinta sadhana avasaram.",
    "good": "Chala baaga chesthunnaru! Idhe teerunu konasaginchandi.",
    "mid": "Mostharuga chesthunnaru; inkonchem krushitho merugupadagalaru.",
}
_TREND_TE = {
    "up": "మునుపటి పరీక్షతో పోలిస్తే మెరుగుపడింది.",
    "down": "మునుపటి పరీక్షతో పోలిస్తే తగ్గింది; జాగ్రత్త అవసరం.",
    "flat": "మునుపటి పరీక్షతో పోలిస్తే స్థిరంగా ఉంది.",
}
_TREND_ROMAN = {
    "up": "Munupati parikshatho polisthe merugupadindi.",
    "down": "Munupati parikshatho polisthe thaggindi; jagratha avasaram.",
    "flat": "Munupati parikshatho polisthe sthiramga undi.",
}


def subject_commentary_telugu(facts: SubjectFacts) -> str:
    line = _COMMENTARY_TE[facts.classification]
    if facts.trend:
        line += " " + _TREND_TE[facts.trend]
    return line


def subject_commentary_romanized(facts: SubjectFacts) -> str:
    line = _COMMENTARY_ROMAN[facts.classification]
    if facts.trend:
        line += " " + _TREND_ROMAN[facts.trend]
    return line


_ORDINAL_TE = ["మొదటి", "రెండవ", "మూడవ", "నాలుగవ", "ఐదవ", "ఆరవ", "ఏడవ", "ఎనిమిదవ", "తొమ్మిదవ", "పదవ"]
_ORDINAL_ROMAN = ["modati", "rendava", "moodava", "naalugava", "aidava", "aarava", "edava", "enimidava", "thommidava", "padava"]

_GRADE_QUALITY_TE = {
    "A1": "అద్భుతం", "A2": "అద్భుతం",
    "B1": "చాలా బాగుంది", "B2": "చాలా బాగుంది",
    "C1": "బాగుంది", "C2": "మోస్తరుగా ఉంది",
    "D1": "తక్కువగా ఉంది, మెరుగుపరచుకోవాలి",
    "D2": "ఫెయిల్ అయ్యారు",
}
_GRADE_QUALITY_ROMAN = {
    "A1": "adbhutham", "A2": "adbhutham",
    "B1": "chala baagundi", "B2": "chala baagundi",
    "C1": "baagundi", "C2": "mostharuga undi",
    "D1": "thakkuvaga undi, merugupadhukovaali",
    "D2": "fail ayyaru",
}


def _ordinal(i: int, words: list[str]) -> str:
    return words[i] if 0 <= i < len(words) else str(i + 1)


def build_subject_voice_telugu(facts: SubjectFacts, student_name: str, index: int = 0, total: int = 1, is_last: bool = True) -> str:
    """Self-contained on purpose: a parent may listen to just this one page
    without having heard any other, so it restates who/which subject/how
    many subjects remain every time, rather than assuming prior context."""
    if not facts.history:
        return ""
    lines = [
        f"ఇది {student_name} యొక్క {facts.name} సబ్జెక్టు ఫలితం, మొత్తం {total} సబ్జెక్టులలో {_ordinal(index, _ORDINAL_TE)}ది."
    ]
    for i, h in enumerate(facts.history):
        exam_label = f"{_ordinal(i, _ORDINAL_TE)} పరీక్ష {h.exam_key}"
        if isinstance(h.marks, (int, float)):
            quality = _GRADE_QUALITY_TE.get(h.grade, "")
            lines.append(
                f"{exam_label} లో, {fmt_num(h.max_marks)} మార్కులకు {fmt_num(h.marks)} మార్కులు సాధించారు, గ్రేడ్ {h.grade} - అంటే {quality}."
            )
        else:
            lines.append(f"{exam_label} లో గ్రేడ్ {h.grade}.")
    lines.append(subject_commentary_telugu(facts))
    if is_last:
        lines.append("తరువాత పేజీలో మొత్తం ఫలితం ఉంది, చూడటానికి పైకి స్వైప్ చేయండి.")
    else:
        lines.append("తదుపరి సబ్జెక్టు కోసం పైకి స్వైప్ చేయండి.")
    return " ".join(lines)


def build_subject_voice_romanized(facts: SubjectFacts, student_name: str, index: int = 0, total: int = 1, is_last: bool = True) -> str:
    if not facts.history:
        return ""
    lines = [
        f"Idhi {student_name} yokka {facts.name} subject phalitham, mottham {total} subjectullo {_ordinal(index, _ORDINAL_ROMAN)}di."
    ]
    for i, h in enumerate(facts.history):
        exam_label = f"{_ordinal(i, _ORDINAL_ROMAN)} pariksha {h.exam_key}"
        if isinstance(h.marks, (int, float)):
            quality = _GRADE_QUALITY_ROMAN.get(h.grade, "")
            lines.append(
                f"{exam_label} lo, {fmt_num(h.max_marks)} marks ki {fmt_num(h.marks)} marks sadhinchaaru, grade {h.grade} - ante {quality}."
            )
        else:
            lines.append(f"{exam_label} lo grade {h.grade}.")
    lines.append(subject_commentary_romanized(facts))
    if is_last:
        lines.append("Tharuvatha page lo mottham phalitham undi, chudataniki paiki swipe cheyandi.")
    else:
        lines.append("Thadupari subject kosam paiki swipe cheyandi.")
    return " ".join(lines)
