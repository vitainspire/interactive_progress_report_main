"""Generates the phone-call-style script used by the report page's "Read
aloud" button — deliberately NOT the same text as the on-screen "AI
Analysis" card (see analysis.py). This script is never shown on the page;
it only exists as spoken audio, in a fixed order a parent can follow
without ever looking at the report itself: a greeting, who's calling, who
it's about, then the results.

Two versions are generated from the same underlying facts:
  - `build_voice_script_telugu`: native Telugu script, for devices with a
    Telugu text-to-speech voice installed.
  - `build_voice_script_romanized`: the same script spelled phonetically in
    plain Latin letters (e.g. "Shubhodayam" for "శుభోదయం"), for devices with
    no Telugu voice — an English voice reading this out loud is far closer
    to intelligible Telugu than the same English voice trying (and failing)
    to read actual Telugu Unicode text.
Which one actually gets spoken is decided client-side at playback time,
based on whether the browser reports a Telugu voice — see card_render.py's
READ_ALOUD_SCRIPT. Both are entirely rule-based (grade tables, thresholds),
same philosophy as the rest of this app's "AI" text — no LLM call.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.reports.numfmt import fmt_num

GRADE_POINTS = {"A1": 10, "A2": 9, "B1": 8, "B2": 7, "C1": 6, "C2": 5, "D1": 4, "D2": 3}
IST = timezone(timedelta(hours=5, minutes=30))


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


@dataclass
class _Facts:
    student_name: str
    parent_name: str
    school: str
    last_key: str
    total: object
    grade: str
    result_text: str
    good: list[str] = field(default_factory=list)
    fail: list[str] = field(default_factory=list)
    low: list[str] = field(default_factory=list)
    last_rank: object = None
    class_strength: int = 0
    attendance_pct: int | None = None


def _compute_facts(student: dict, exam_order: list[str], class_strength: int, school_name: str) -> _Facts | None:
    ks = [k for k in exam_order if k in student["exams"]]
    if not ks:
        return None
    last_key = ks[-1]
    last_exam = student["exams"][last_key]

    subject_history: dict[str, list[str]] = {}
    for q in ks:
        for x in student["exams"][q]["subjects"]:
            subject_history.setdefault(x["name"], []).append(x["grade"])
    good, fail, low = [], [], []
    for name, grades in subject_history.items():
        graded = [g for g in grades if g in GRADE_POINTS]
        if not graded:
            continue
        if "D2" in graded:
            fail.append(name)
        else:
            avg = sum(GRADE_POINTS[g] for g in graded) / len(graded)
            if avg < 6:
                low.append(name)
            elif avg >= 8:
                good.append(name)

    ranked = [q for q in ks if _is_num(student["exams"][q]["rank"])]
    last_rank = student["exams"][ranked[-1]]["rank"] if ranked else None

    pct = None
    att = student.get("attendance")
    if att and att.get("total_working"):
        pct = round(att["total_present"] * 100 / att["total_working"])

    return _Facts(
        student_name=student["name"],
        parent_name=(student.get("father") or "").strip(),
        school=(school_name or "").strip(),
        last_key=last_key,
        total=last_exam["total_marks"],
        grade=last_exam["total_grade"],
        result_text=last_exam.get("result", ""),
        good=good,
        fail=fail,
        low=low,
        last_rank=last_rank,
        class_strength=class_strength or 0,
        attendance_pct=pct,
    )


def build_voice_script_telugu(student: dict, exam_order: list[str], class_strength: int, school_name: str) -> str:
    f = _compute_facts(student, exam_order, class_strength, school_name)
    if f is None:
        return ""
    school = f.school or "పాఠశాల"

    hour = datetime.now(IST).hour
    if 5 <= hour < 12:
        greeting = "శుభోదయం!"
    elif 12 <= hour < 17:
        greeting = "శుభ మధ్యాహ్నం!"
    elif 17 <= hour < 21:
        greeting = "శుభ సాయంత్రం!"
    else:
        greeting = "నమస్కారం!"

    lines = [greeting, f"ఇది {school} నుండి ఫోన్ కాల్."]
    if f.parent_name:
        lines.append(f"{f.parent_name} గారు, నమస్కారం.")
    lines.append(f"{f.student_name} యొక్క పరీక్షా ఫలితాల గురించి మీకు తెలియజేయడానికి ఈ కాల్ చేస్తున్నాము.")

    if _is_num(f.total):
        lines.append(f"{f.last_key} పరీక్షలో, {f.student_name} మొత్తం {fmt_num(f.total)} మార్కులు సాధించారు, గ్రేడ్ {f.grade}.")
    else:
        lines.append(f"{f.last_key} పరీక్షలో {f.student_name} గ్రేడ్ {f.grade} సాధించారు.")

    if f.grade == "D2" or "FAIL" in f.result_text.upper():
        lines.append("ఈ పరీక్షలో ఉత్తీర్ణత సాధించలేదు.")
    elif f.grade != "-" or "PASS" in f.result_text.upper():
        lines.append("ఈ పరీక్షలో ఉత్తీర్ణత సాధించారు.")

    if f.good:
        lines.append(f"{', '.join(f.good)} సబ్జెక్టులలో మంచి మార్కులు సాధించారు.")
    if f.fail:
        lines.append(f"అయితే {', '.join(f.fail)} సబ్జెక్టులలో ఫెయిల్ అయ్యారు; వీటిపై ప్రత్యేక శ్రద్ధ అవసరం.")
    elif f.low:
        lines.append(f"{', '.join(f.low)} సబ్జెక్టులలో మార్కులు కొంచెం తక్కువగా ఉన్నాయి; మరింత శ్రద్ధ అవసరం.")

    if f.last_rank is not None:
        lines.append(f"తరగతిలో మొత్తం {f.class_strength} మంది విద్యార్థులలో {fmt_num(f.last_rank)} వ ర్యాంకు సాధించారు.")

    if f.attendance_pct is not None:
        lines.append(f"హాజరు శాతం {f.attendance_pct} శాతంగా ఉంది.")
        if f.attendance_pct < 75:
            lines.append("హాజరు తక్కువగా ఉంది; దయచేసి మీ పిల్లలను ప్రతిరోజూ పాఠశాలకు పంపించండి.")

    lines.append("పూర్తి వివరాల కోసం పంపిన లింక్‌లో రిపోర్ట్ కార్డ్ చూడగలరు.")
    lines.append("ధన్యవాదాలు.")
    return " ".join(lines)


def build_voice_script_romanized(student: dict, exam_order: list[str], class_strength: int, school_name: str) -> str:
    """Same script as build_voice_script_telugu, spelled phonetically in
    plain Latin letters — for playback on a device with no Telugu voice."""
    f = _compute_facts(student, exam_order, class_strength, school_name)
    if f is None:
        return ""
    school = f.school or "school"

    hour = datetime.now(IST).hour
    if 5 <= hour < 12:
        greeting = "Shubhodayam!"
    elif 12 <= hour < 17:
        greeting = "Shubha madhyahnam!"
    elif 17 <= hour < 21:
        greeting = "Shubha sayantram!"
    else:
        greeting = "Namaskaram!"

    lines = [greeting, f"Idhi {school} nundi phone call."]
    if f.parent_name:
        lines.append(f"{f.parent_name} garu, namaskaram.")
    lines.append(f"{f.student_name} yokka pariksha phalithala gurinchi meeku teliyajeyadaniki ee call chesthunnamu.")

    if _is_num(f.total):
        lines.append(f"{f.last_key} parikshalo, {f.student_name} mottham {fmt_num(f.total)} marks sadhinchaaru, grade {f.grade}.")
    else:
        lines.append(f"{f.last_key} parikshalo {f.student_name} grade {f.grade} sadhinchaaru.")

    if f.grade == "D2" or "FAIL" in f.result_text.upper():
        lines.append("Ee parikshalo uttheernatha sadhinchaledu.")
    elif f.grade != "-" or "PASS" in f.result_text.upper():
        lines.append("Ee parikshalo uttheernatha sadhinchaaru.")

    if f.good:
        lines.append(f"{', '.join(f.good)} subjectullo manchi marks sadhinchaaru.")
    if f.fail:
        lines.append(f"ayithe {', '.join(f.fail)} subjectullo fail ayyaru; vatipai pratyeka shraddha avasaram.")
    elif f.low:
        lines.append(f"{', '.join(f.low)} subjectullo marks konchem thakkuvaga unnayi; marinta shraddha avasaram.")

    if f.last_rank is not None:
        lines.append(f"tharagathilo mottham {f.class_strength} mandi vidyarthullo {fmt_num(f.last_rank)} va rank sadhinchaaru.")

    if f.attendance_pct is not None:
        lines.append(f"hajaru shatam {f.attendance_pct} shatamga undi.")
        if f.attendance_pct < 75:
            lines.append("hajaru thakkuvaga undi; dayachesi mee pillalani prathirojuu pathashalaki pampinchandi.")

    lines.append("poorthi vivaralu kosam pampina link lo report card chudagalaru.")
    lines.append("dhanyavadalu.")
    return " ".join(lines)
