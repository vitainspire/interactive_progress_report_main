"""Rule-based answers for the "Know About Student" chat's five preset
starter questions (see parent_report._DEFAULT_CHAT_QUESTIONS) — same
philosophy as analysis.py/voice_script.py: these are fixed, predictable
questions whose answer is a deterministic function of the student's own
marks/grades/rank/attendance, so they're answered directly from that data
instead of spending an LLM call on them. Only a question that doesn't
match one of these five falls through to app/integrations/chat.py.
"""
from __future__ import annotations

from app.reports.numfmt import fmt_num

GRADE_POINTS = {"A1": 10, "A2": 9, "B1": 8, "B2": 7, "C1": 6, "C2": 5, "D1": 4, "D2": 3}


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _exam_keys(student: dict, exam_order: list[str]) -> list[str]:
    return [k for k in exam_order if k in student["exams"]]


def _subject_buckets(student: dict, ks: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Same bucketing rule as analysis.py/voice_script.py: a subject is
    "fail" if it ever hit D2, "low" if its average grade-point across exams
    is below a B2, "good" if it's B1 or above — kept in this file too
    (rather than imported) so each canned answer stays a pure function of
    its own inputs, same as the other report modules."""
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
    return good, fail, low


def _overall_progress(student: dict, exam_defs: list[dict], settings, ks: list[str]) -> str:
    is_fa_by_key = {e["key"]: e["is_fa"] for e in exam_defs}
    last_key = ks[-1]
    last = student["exams"][last_key]
    max_total = settings.fa_total if is_fa_by_key[last_key] else settings.sa_total
    sentence = f"{last_key}లో మొత్తం {fmt_num(last['total_marks'])}/{fmt_num(max_total)} మార్కులతో గ్రేడ్ {last['total_grade']}"
    if last.get("result"):
        sentence += f", ఫలితం {last['result']}."
    else:
        sentence += "."

    if len(ks) > 1:
        first_key, prev_key = ks[0], ks[-2]
        prev = student["exams"][prev_key]
        if prev["total_grade"] in GRADE_POINTS and last["total_grade"] in GRADE_POINTS:
            delta = GRADE_POINTS[last["total_grade"]] - GRADE_POINTS[prev["total_grade"]]
            if delta > 0:
                sentence += f" {prev_key} తో పోలిస్తే మెరుగుపడింది, శభాష్!"
            elif delta < 0:
                sentence += f" {prev_key} తో పోలిస్తే కొంచెం తగ్గింది; జాగ్రత్త అవసరం."
            else:
                sentence += f" {prev_key} నుండి నిలకడగా కొనసాగుతోంది."
        if first_key != prev_key:
            pass  # only the most recent comparison matters for a short answer
    return sentence


def _subjects_to_improve(student: dict, ks: list[str]) -> str:
    good, fail, low = _subject_buckets(student, ks)
    if fail:
        return f"{', '.join(fail)} సబ్జెక్టులలో ఫెయిల్ అయ్యారు — వీటిపై ఎక్కువ శ్రద్ధ అవసరం."
    if low:
        return f"{', '.join(low)} సబ్జెక్టులలో మార్కులు కొంచెం తక్కువగా ఉన్నాయి; కొద్ది కృషితో మెరుగుపడతాయి."
    if good:
        return f"ఏ సబ్జెక్టులోనూ పెద్ద ఇబ్బంది లేదు — {', '.join(good)} లో ముఖ్యంగా బాగా రాణిస్తున్నారు."
    return "ఇప్పటి వరకు గ్రేడ్‌లు నమోదు కాలేదు, కాబట్టి ఏ సబ్జెక్టు మెరుగుపడాలో చెప్పలేను."


def _rank_info(student: dict, ks: list[str], class_strength: int) -> str:
    ranked = [q for q in ks if _is_num(student["exams"][q]["rank"])]
    if not ranked:
        return "ర్యాంకు సమాచారం ఇంకా అందుబాటులో లేదు."
    last_key = ranked[-1]
    last_rank = student["exams"][last_key]["rank"]
    sentence = f"{last_key}లో {fmt_num(last_rank)} వ ర్యాంకు, మొత్తం {class_strength} మంది విద్యార్థులలో."
    if len(ranked) > 1:
        first_key = ranked[0]
        first_rank = student["exams"][first_key]["rank"]
        if last_rank < first_rank:
            sentence += f" {first_key}లో {fmt_num(first_rank)} నుండి మెరుగుపడింది."
        elif last_rank > first_rank:
            sentence += f" {first_key}లో {fmt_num(first_rank)} నుండి తగ్గింది."
    return sentence


def _attendance_info(student: dict) -> str:
    att = student.get("attendance")
    if not att or not att.get("total_working"):
        return "హాజరు వివరాలు అందుబాటులో లేవు."
    pct = round(att["total_present"] * 100 / att["total_working"])
    sentence = f"మొత్తం {fmt_num(att['total_working'])} పని దినాలలో {fmt_num(att['total_present'])} రోజులు ({pct}%) హాజరయ్యారు."
    if pct >= 90:
        sentence += " చాలా మంచి హాజరు!"
    elif pct >= 75:
        sentence += " హాజరు బాగానే ఉంది."
    else:
        sentence += " హాజరు తక్కువగా ఉంది; క్రమం తప్పకుండా బడికి పంపించండి."
    return sentence


def _study_tips(student: dict, ks: list[str]) -> str:
    _good, fail, low = _subject_buckets(student, ks)
    weak = fail + [s for s in low if s not in fail]
    base = "ప్రతిరోజూ సమయపట్టిక ప్రకారం చదివి, ఆ రోజు పాఠాలను అదే రోజు మళ్ళీ ఒకసారి చూసుకోండి."
    if weak:
        return f"{base} ముఖ్యంగా {', '.join(weak)} పై ఎక్కువ సమయం కేటాయించి, తెలియని విషయాలు ఉపాధ్యాయులను అడిగి తెలుసుకోమనండి."
    return f"{base} ఇప్పటి వరకు ప్రత్యేకంగా బలహీనమైన సబ్జెక్టు లేదు — ఇదే నిలకడను కొనసాగించమని ప్రోత్సహించండి."


# Keyed by the exact preset question text from parent_report._DEFAULT_CHAT_QUESTIONS.
_HANDLERS = {
    "మొత్తం ప్రగతి ఎలా ఉంది?": lambda student, exam_defs, settings, ks, class_strength: _overall_progress(student, exam_defs, settings, ks),
    "ఏ సబ్జెక్టులు మెరుగుపడాలి?": lambda student, exam_defs, settings, ks, class_strength: _subjects_to_improve(student, ks),
    "ర్యాంకు గురించి చెప్పండి": lambda student, exam_defs, settings, ks, class_strength: _rank_info(student, ks, class_strength),
    "హాజరు ఎలా ఉంది?": lambda student, exam_defs, settings, ks, class_strength: _attendance_info(student),
    "ఇంకా బాగా చదవాలంటే ఏం చేయాలి?": lambda student, exam_defs, settings, ks, class_strength: _study_tips(student, ks),
}


def answer_canned_question(question: str, student: dict, all_students: list[dict], exam_defs: list[dict], settings) -> str | None:
    """Returns a rule-based answer if `question` is (exactly) one of the
    five preset starter questions, else None — callers fall through to the
    LLM for anything else, including a parent's own free-typed question
    even if it's worded similarly to one of these."""
    handler = _HANDLERS.get(question.strip())
    if handler is None:
        return None
    ks = _exam_keys(student, [e["key"] for e in exam_defs])
    if not ks:
        return "ఇంకా పరీక్షల మార్కులు నమోదు కాలేదు."
    class_strength = settings.class_strength_override or len(all_students)
    return handler(student, exam_defs, settings, ks, class_strength)
