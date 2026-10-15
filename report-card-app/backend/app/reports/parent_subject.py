"""Per-subject facts + voice narration for the parent-facing paginated
report (see parent_report.py). The parent link shows one page per subject
plus a final conclusion page, instead of the teacher's single dense table —
this module computes, for one subject at a time, the marks/grade history,
a plain classification (good/mid/low/fail), and a trend, then turns that
into both a short on-screen commentary line and a full spoken narration
(Telugu + Romanized, same phonetic-fallback approach as voice_script.py).

The spoken narration across all pages is written to read as ONE continuous
phone call, not independent clips: the greeting/school/"this is your
child's progress card" opening is spoken only once, on the first subject's
page — every later page just transitions naturally ("Next, Maths...")
instead of repeating who's calling and who it's about. The final
conclusion page (build_conclusion_voice_*) is deliberately brief — it
doesn't re-list every subject's detail again, since that was already
covered page by page — and explicitly ends the call.

Entirely rule-based, no LLM call — same philosophy as the rest of the app.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.reports.greeting import time_greeting_romanized, time_greeting_telugu
from app.reports.numfmt import fmt_num
from app.reports.voice_script import _compute_facts

GRADE_POINTS = {"A1": 10, "A2": 9, "B1": 8, "B2": 7, "C1": 6, "C2": 5, "D1": 4, "D2": 3}


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


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


def build_subject_voice_telugu(
    facts: SubjectFacts,
    student_name: str,
    index: int = 0,
    total: int = 1,
    is_last: bool = True,
    school_name: str = "",
    parent_name: str = "",
) -> str:
    """Only the FIRST subject page (index 0) opens with the greeting/school/
    "this is a call about your child's progress card" framing — every later
    page just transitions straight into the next subject, so listening
    through the whole sequence sounds like one call, not eight repeats of
    the same intro."""
    if not facts.history:
        return ""

    lines: list[str] = []
    if index == 0:
        school = (school_name or "").strip() or "పాఠశాల"
        lines.append(time_greeting_telugu())
        lines.append(f"ఇది {school} నుండి ఫోన్ కాల్.")
        if parent_name:
            lines.append(f"{parent_name} గారు, నమస్కారం.")
        lines.append(f"ఇది {student_name} యొక్క ప్రోగ్రెస్ కార్డ్.")
    lines.append(f"ఇప్పుడు {facts.name} సబ్జెక్టు.")

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


def build_subject_voice_romanized(
    facts: SubjectFacts,
    student_name: str,
    index: int = 0,
    total: int = 1,
    is_last: bool = True,
    school_name: str = "",
    parent_name: str = "",
) -> str:
    if not facts.history:
        return ""

    lines: list[str] = []
    if index == 0:
        school = (school_name or "").strip() or "school"
        lines.append(time_greeting_romanized())
        lines.append(f"Idhi {school} nundi phone call.")
        if parent_name:
            lines.append(f"{parent_name} garu, namaskaram.")
        lines.append(f"Idhi {student_name} yokka progress card.")
    lines.append(f"Ippudu {facts.name} subject.")

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


def build_conclusion_voice_telugu(student: dict, exam_order: list[str], class_strength: int, school_name: str) -> str:
    """Deliberately brief and distinct from the per-subject pages' own
    narration — every subject's own good/weak detail was already spoken on
    its own page, so this only restates the overall total/grade/result/
    rank/attendance, then explicitly ends the call."""
    f = _compute_facts(student, exam_order, class_strength, school_name)
    if f is None:
        return ""

    lines = ["ఇప్పుడు క్లుప్తంగా మొత్తం ఫలితం చెప్తాను."]
    if _is_num(f.total):
        lines.append(f"{f.student_name} మొత్తం {fmt_num(f.total)} మార్కులు సాధించారు, గ్రేడ్ {f.grade}.")
    else:
        lines.append(f"{f.student_name} గ్రేడ్ {f.grade} సాధించారు.")

    if f.grade == "D2" or "FAIL" in f.result_text.upper():
        lines.append("ఫలితం: ఫెయిల్; ముందు చెప్పిన సబ్జెక్టులపై ప్రత్యేక శ్రద్ధ అవసరం.")
    else:
        lines.append("ఫలితం: పాస్.")

    if f.last_rank is not None:
        lines.append(f"తరగతిలో మొత్తం {f.class_strength} మందిలో {fmt_num(f.last_rank)} వ ర్యాంకు.")

    if f.attendance_pct is not None:
        lines.append(f"హాజరు శాతం {f.attendance_pct} శాతం.")
        if f.attendance_pct < 75:
            lines.append("దయచేసి మీ పిల్లలను ప్రతిరోజూ పాఠశాలకు పంపించండి.")

    lines.append("ఈ కాల్ ముగిస్తున్నాము. పూర్తి వివరాల కోసం పైన కనిపించే వివరాలు చూడగలరు. ధన్యవాదాలు, శుభాకాంక్షలు!")
    return " ".join(lines)


def build_conclusion_voice_romanized(student: dict, exam_order: list[str], class_strength: int, school_name: str) -> str:
    f = _compute_facts(student, exam_order, class_strength, school_name)
    if f is None:
        return ""

    lines = ["Ippudu klupthamga mottham phalitham cheptanu."]
    if _is_num(f.total):
        lines.append(f"{f.student_name} mottham {fmt_num(f.total)} marks sadhinchaaru, grade {f.grade}.")
    else:
        lines.append(f"{f.student_name} grade {f.grade} sadhinchaaru.")

    if f.grade == "D2" or "FAIL" in f.result_text.upper():
        lines.append("Phalitham: fail; mundu cheppina subjectulapai pratyeka shraddha avasaram.")
    else:
        lines.append("Phalitham: pass.")

    if f.last_rank is not None:
        lines.append(f"tharagathilo mottham {f.class_strength} mandilo {fmt_num(f.last_rank)} va rank.")

    if f.attendance_pct is not None:
        lines.append(f"hajaru shatam {f.attendance_pct} shatam.")
        if f.attendance_pct < 75:
            lines.append("dayachesi mee pillalani prathirojuu pathashalaki pampinchandi.")

    lines.append("Ee call mugistunnamu. Poorthi vivaralu kosam paina kanipinche vivaralu chudagalaru. Dhanyavadalu, shubhakankshalu!")
    return " ".join(lines)
