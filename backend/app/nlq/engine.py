"""Natural-language query engine for "Ask anything about the class".

Question -> extract entities (student/section/subject/phase/number) via
app.nlq.entities -> match against an ordered list of regex-based intent
rules -> run the matching repository query -> format a plain-English answer
plus optional table/chart payloads the frontend can render and the voice
layer can read.

If no regex rule matches, and an LLM API key is configured, the question
falls through to app.nlq.llm_fallback — a tool-calling LLM that can only
answer by calling the same repository functions above (never inventing
numbers). Without a key configured, this fallback is a no-op and the
original "I couldn't understand" message is shown instead, so behavior is
unchanged for anyone who hasn't set one up.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from app.db import repository as repo
from app.nlq.entities import ExtractedEntities, extract_all
from app.nlq.llm_fallback import try_llm_fallback
from app.nlq.vocab import load_vocab
from app.reports import grading, insights


@dataclass
class QueryAnswer:
    answer: str
    intent: str
    table: dict | None = None
    chart: dict | None = None
    suggestions: list[str] = field(default_factory=list)


def _pct(marks, max_marks) -> float | None:
    if marks is None or not max_marks:
        return None
    return round(marks / max_marks * 100, 1)


def _phase_word(code: str) -> str:
    return code


def _fmt_name(name: str) -> str:
    return name.title()


def answer_question(conn: sqlite3.Connection, user_id: int, class_id: int, question: str) -> QueryAnswer:
    vocab = load_vocab(conn, user_id, class_id)
    if not vocab.students:
        return QueryAnswer(
            answer="No data has been uploaded yet. Upload a progress sheet first.",
            intent="NO_DATA",
        )
    q = question.lower().strip()
    ent = extract_all(question, vocab)

    handlers = [
        _try_student_attendance,
        _try_student_rank,
        _try_student_trend,
        _try_student_subject_marks,
        _try_student_profile,
        _try_top_n,
        _try_fail_list,
        _try_compare_sections,
        _try_subject_aggregate,
        _try_count_pass_fail,
        _try_class_summary,
    ]
    for handler in handlers:
        result = handler(conn, user_id, class_id, q, ent, vocab)
        if result is not None:
            return result

    llm_result = try_llm_fallback(conn, user_id, class_id, question)
    if llm_result is not None:
        return QueryAnswer(answer=llm_result["answer"], intent=llm_result["intent"], chart=llm_result.get("chart"))

    return QueryAnswer(
        answer=(
            "I couldn't quite match that to a question I understand. Try things like: "
            "\"How did Section B do in SA-1 Maths?\", \"Tell me about Abhishek Kumar\", "
            "\"Top 5 students in FA-2\", \"Who failed in Biology?\", or \"What is Abhishek's attendance?\""
        ),
        intent="FALLBACK",
    )


def _try_student_attendance(conn, user_id, class_id, q, ent: ExtractedEntities, vocab) -> QueryAnswer | None:
    if not ent.student_ids or "attend" not in q:
        return None
    if len(ent.student_ids) > 1:
        return _ambiguous_student(ent)
    sid = ent.student_ids[0]
    student = repo.get_student(conn, user_id, class_id, sid)
    summary = repo.get_student_attendance_summary(conn, user_id, class_id, sid)
    insight = insights.build_attendance_insight(
        summary["total_present"] if summary else None, summary["total_working_days"] if summary else None
    )
    if insight.band == "no_data":
        return QueryAnswer(f"No attendance data found for {_fmt_name(student['name'])}.", "STUDENT_ATTENDANCE")
    answer = f"{_fmt_name(student['name'])} has attended {insight.total_present:g} out of {insight.total_working:g} working days ({insight.pct:g}%)."
    months = repo.get_student_attendance(conn, user_id, class_id, sid)
    chart = {
        "type": "bar",
        "title": f"{_fmt_name(student['name'])} — monthly attendance %",
        "data": [
            {"name": m["month"].title(), "value": round(m["days_present"] / m["working_days"] * 100, 1)}
            for m in months
            if m["working_days"]
        ],
    }
    return QueryAnswer(answer, "STUDENT_ATTENDANCE", chart=chart)


def _try_student_rank(conn, user_id, class_id, q, ent: ExtractedEntities, vocab) -> QueryAnswer | None:
    if not ent.student_ids or "rank" not in q:
        return None
    if len(ent.student_ids) > 1:
        return _ambiguous_student(ent)
    sid = ent.student_ids[0]
    student = repo.get_student(conn, user_id, class_id, sid)
    summaries = repo.get_student_exam_summaries(conn, user_id, class_id, sid)
    total = repo.total_student_count(conn, user_id, class_id)
    if ent.phase_code:
        row = next((r for r in summaries if r["phase_code"] == ent.phase_code), None)
        if not row or row["rank"] is None:
            return QueryAnswer(f"No rank found for {_fmt_name(student['name'])} in {ent.phase_code}.", "STUDENT_RANK")
        return QueryAnswer(f"{_fmt_name(student['name'])} ranked {row['rank']} out of {total} in {ent.phase_code}.", "STUDENT_RANK")
    if not summaries:
        return QueryAnswer(f"No exam results found for {_fmt_name(student['name'])}.", "STUDENT_RANK")
    parts = [f"{r['phase_code']}: {r['rank']}" for r in summaries if r["rank"] is not None]
    chart = {
        "type": "line",
        "title": f"{_fmt_name(student['name'])} — rank over time (lower is better)",
        "data": [{"name": r["phase_code"], "value": r["rank"]} for r in summaries if r["rank"] is not None],
    }
    return QueryAnswer(f"{_fmt_name(student['name'])}'s rank over time — " + ", ".join(parts) + f" (out of {total}).", "STUDENT_RANK", chart=chart)


def _try_student_subject_marks(conn, user_id, class_id, q, ent: ExtractedEntities, vocab) -> QueryAnswer | None:
    if not ent.student_ids or not ent.subject:
        return None
    if len(ent.student_ids) > 1:
        return _ambiguous_student(ent)
    sid = ent.student_ids[0]
    student = repo.get_student(conn, user_id, class_id, sid)
    rows = [r for r in repo.get_student_exam_results(conn, user_id, class_id, sid) if r["subject"] == ent.subject]
    if ent.phase_code:
        rows = [r for r in rows if r["phase_code"] == ent.phase_code]
    if not rows:
        return QueryAnswer(f"No {ent.subject.title()} marks found for {_fmt_name(student['name'])}.", "STUDENT_SUBJECT_MARKS")
    if len(rows) == 1:
        r = rows[0]
        return QueryAnswer(
            f"{_fmt_name(student['name'])} scored {r['marks']:g}/{int(r['max_marks'])} ({r['grade']}) in {ent.subject.title()} ({r['phase_code']}).",
            "STUDENT_SUBJECT_MARKS",
        )
    parts = [f"{r['phase_code']}: {r['marks']:g}/{int(r['max_marks'])} ({r['grade']})" for r in rows]
    chart = {
        "type": "line",
        "title": f"{_fmt_name(student['name'])} — {ent.subject.title()} %",
        "data": [{"name": r["phase_code"], "value": _pct(r["marks"], r["max_marks"])} for r in rows],
    }
    return QueryAnswer(f"{_fmt_name(student['name'])}'s {ent.subject.title()} marks — " + "; ".join(parts) + ".", "STUDENT_SUBJECT_MARKS", chart=chart)


def _try_student_trend(conn, user_id, class_id, q, ent: ExtractedEntities, vocab) -> QueryAnswer | None:
    if not ent.student_ids or not any(k in q for k in ("trend", "progress", "improv", "declin", "doing")):
        return None
    if len(ent.student_ids) > 1:
        return _ambiguous_student(ent)
    sid = ent.student_ids[0]
    student = repo.get_student(conn, user_id, class_id, sid)
    exam_rows = repo.get_student_exam_results(conn, user_id, class_id, sid)
    phase_order = [p["code"] for p in repo.list_phases(conn, user_id, class_id)]
    series = insights.build_subject_series(exam_rows, phase_order)
    if ent.subject:
        series = [s for s in series if s.subject == ent.subject]
    if not series:
        return QueryAnswer(f"Not enough data to describe a trend for {_fmt_name(student['name'])}.", "STUDENT_TREND")
    lines = []
    for s in series:
        trail = " → ".join(f"{p.pct:g}%" for p in s.points)
        lines.append(f"{s.subject.title()}: {trail} ({s.direction})")
    return QueryAnswer(f"{_fmt_name(student['name'])}'s trend — " + "; ".join(lines) + ".", "STUDENT_TREND")


def _try_student_profile(conn, user_id, class_id, q, ent: ExtractedEntities, vocab) -> QueryAnswer | None:
    if not ent.student_ids:
        return None
    if len(ent.student_ids) > 1:
        return _ambiguous_student(ent)
    sid = ent.student_ids[0]
    student = repo.get_student(conn, user_id, class_id, sid)
    summaries = repo.get_student_exam_summaries(conn, user_id, class_id, sid)
    att = repo.get_student_attendance_summary(conn, user_id, class_id, sid)
    parts = [f"{_fmt_name(student['name'])} (Section {student['section']})."]
    if summaries:
        latest = summaries[-1]
        parts.append(
            f"Latest result: {latest['phase_code']} — {latest['total_marks']:g}/{int(latest['max_total'])} "
            f"({latest['total_grade']}, {latest['result']}, rank {latest['rank']})."
        )
    if att and att["total_present"] and att["total_working_days"]:
        pct = round(att["total_present"] / att["total_working_days"] * 100, 1)
        parts.append(f"Attendance: {att['total_present']:g}/{att['total_working_days']:g} ({pct:g}%).")
    chart = None
    if summaries:
        chart = {
            "type": "line",
            "title": f"{_fmt_name(student['name'])} — total marks %",
            "data": [{"name": r["phase_code"], "value": _pct(r["total_marks"], r["max_total"])} for r in summaries],
        }
    return QueryAnswer(" ".join(parts), "STUDENT_PROFILE", chart=chart)


def _try_top_n(conn, user_id, class_id, q, ent: ExtractedEntities, vocab) -> QueryAnswer | None:
    if "top" not in q:
        return None
    n = ent.number or 5
    phase_code = ent.phase_code or (vocab.phase_codes[-1] if vocab.phase_codes else None)
    if not phase_code:
        return QueryAnswer("No exam phases found in the uploaded data yet.", "TOP_N")
    rows = repo.top_students(conn, user_id, class_id, phase_code, ent.section, n)
    if not rows:
        return QueryAnswer(f"No ranked results found for {phase_code}" + (f" in Section {ent.section}" if ent.section else "") + ".", "TOP_N")
    lines = [f"{r['rank']}. {_fmt_name(r['name'])} ({r['section']}) — {r['total_marks']:g}/{int(r['max_total'])}" for r in rows]
    table = {"columns": ["Rank", "Name", "Section", "Total"], "rows": [[r["rank"], _fmt_name(r["name"]), r["section"], f"{r['total_marks']:g}/{int(r['max_total'])}"] for r in rows]}
    chart = {"type": "bar", "title": f"Top {len(rows)} — {phase_code}", "data": [{"name": _fmt_name(r["name"]), "value": r["total_marks"]} for r in rows]}
    scope = f" in Section {ent.section}" if ent.section else ""
    return QueryAnswer(f"Top {len(rows)} students in {phase_code}{scope}: " + "; ".join(lines) + ".", "TOP_N", table=table, chart=chart)


def _try_fail_list(conn, user_id, class_id, q, ent: ExtractedEntities, vocab) -> QueryAnswer | None:
    if "fail" not in q:
        return None
    rows = repo.students_failed(conn, user_id, class_id, ent.phase_code, ent.subject, ent.section)
    if not rows:
        scope = " ".join(filter(None, [ent.subject.title() if ent.subject else None, ent.phase_code, f"Section {ent.section}" if ent.section else None]))
        return QueryAnswer(f"No failures found{(' in ' + scope) if scope else ''}. 🎉", "FAIL_LIST")
    lines = [f"{_fmt_name(r['name'])} ({r['section']}) — {r['subject'].title()} {r['phase_code']}: {r['marks']:g}/{int(r['max_marks'])} ({r['grade']})" for r in rows]
    table = {
        "columns": ["Name", "Section", "Subject", "Phase", "Marks", "Grade"],
        "rows": [[_fmt_name(r["name"]), r["section"], r["subject"].title(), r["phase_code"], f"{r['marks']:g}/{int(r['max_marks'])}", r["grade"]] for r in rows],
    }
    return QueryAnswer(f"{len(rows)} failing result(s) found: " + "; ".join(lines[:15]) + ("..." if len(lines) > 15 else ""), "FAIL_LIST", table=table)


def _try_compare_sections(conn, user_id, class_id, q, ent: ExtractedEntities, vocab) -> QueryAnswer | None:
    if "compare" not in q or len(vocab.sections) < 2:
        return None
    phase_code = ent.phase_code or (vocab.phase_codes[-1] if vocab.phase_codes else None)
    if not phase_code:
        return QueryAnswer("No exam phases found yet to compare.", "COMPARE_SECTIONS")
    results = []
    for sec in vocab.sections:
        if ent.subject:
            stats = repo.subject_stats(conn, user_id, class_id, phase_code, ent.subject, sec)
            results.append((sec, stats.get("average")))
        else:
            summary = repo.class_summary(conn, user_id, class_id, phase_code, sec)
            results.append((sec, summary.get("average_total")))
    label = ent.subject.title() if ent.subject else "overall total"
    lines = [f"Section {sec}: {avg:.1f}" if avg is not None else f"Section {sec}: no data" for sec, avg in results]
    chart = {"type": "bar", "title": f"Section comparison — {label} ({phase_code})", "data": [{"name": f"Section {sec}", "value": avg} for sec, avg in results if avg is not None]}
    return QueryAnswer(f"Average {label} in {phase_code} — " + "; ".join(lines) + ".", "COMPARE_SECTIONS", chart=chart)


def _try_subject_aggregate(conn, user_id, class_id, q, ent: ExtractedEntities, vocab) -> QueryAnswer | None:
    if not ent.subject:
        return None
    phase_code = ent.phase_code or (vocab.phase_codes[-1] if vocab.phase_codes else None)
    if not phase_code:
        return QueryAnswer("No exam phases found in the uploaded data yet.", "SUBJECT_AGGREGATE")
    stats = repo.subject_stats(conn, user_id, class_id, phase_code, ent.subject, ent.section)
    if not stats.get("count"):
        scope = f" in Section {ent.section}" if ent.section else ""
        return QueryAnswer(f"No {ent.subject.title()} marks found for {phase_code}{scope}.", "SUBJECT_AGGREGATE")
    scope = f" in Section {ent.section}" if ent.section else ""
    answer = (
        f"{ent.subject.title()} ({phase_code}{scope}): average {stats['average']:.1f}/{int(stats['max_marks'])}, "
        f"highest {_fmt_name(stats['highest']['name'])} ({stats['highest']['marks']:g}), "
        f"lowest {_fmt_name(stats['lowest']['name'])} ({stats['lowest']['marks']:g})."
    )
    return QueryAnswer(answer, "SUBJECT_AGGREGATE")


def _try_count_pass_fail(conn, user_id, class_id, q, ent: ExtractedEntities, vocab) -> QueryAnswer | None:
    if "how many" not in q and "count" not in q:
        return None
    phase_code = ent.phase_code or (vocab.phase_codes[-1] if vocab.phase_codes else None)
    if not phase_code:
        return QueryAnswer("No exam phases found in the uploaded data yet.", "COUNT")
    summary = repo.class_summary(conn, user_id, class_id, phase_code, ent.section)
    scope = f" in Section {ent.section}" if ent.section else ""
    return QueryAnswer(
        f"{phase_code}{scope}: {summary['student_count']} students, {summary['passed']} passed, {summary['failed']} failed overall result.",
        "COUNT",
    )


def _try_class_summary(conn, user_id, class_id, q, ent: ExtractedEntities, vocab) -> QueryAnswer | None:
    phase_code = ent.phase_code
    if not phase_code and not ent.section:
        return None
    phase_code = phase_code or (vocab.phase_codes[-1] if vocab.phase_codes else None)
    if not phase_code:
        return QueryAnswer("No exam phases found in the uploaded data yet.", "CLASS_SUMMARY")
    summary = repo.class_summary(conn, user_id, class_id, phase_code, ent.section)
    scope = f"Section {ent.section}" if ent.section else "The whole class"
    if summary["average_total"] is None:
        return QueryAnswer(f"No results found for {scope} in {phase_code}.", "CLASS_SUMMARY")
    answer = (
        f"{scope} in {phase_code}: {summary['student_count']} students, average total {summary['average_total']:.1f}/"
        f"{int(summary['max_total'])}, {summary['passed']} passed, {summary['failed']} failed."
    )
    return QueryAnswer(answer, "CLASS_SUMMARY")


def _ambiguous_student(ent: ExtractedEntities) -> QueryAnswer:
    names = ", ".join(_fmt_name(n) for n in ent.student_names[:8])
    return QueryAnswer(
        f"That could match more than one student: {names}. Could you be more specific?",
        "AMBIGUOUS_STUDENT",
        suggestions=ent.student_names[:8],
    )
