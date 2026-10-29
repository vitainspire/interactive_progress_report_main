"""Builds the plain-text "ground truth" a parent's question gets answered
against — everything about one student that's already on their report card,
laid out so an LLM can read it directly rather than needing tool calls or a
database connection of its own. Nothing here is fetched specially for chat;
it's the same parsed-sheet student row and exam_defs/settings already used
by card_render.py and analysis.py, just rendered as text instead of HTML.
"""
from __future__ import annotations

import psycopg

from app.reports import exam_focus, study_plan
from app.reports.analysis import build_analysis
from app.reports.numfmt import fmt_num
from app.reports.subject_analysis import get_blueprint


def _fmt(v) -> str:
    return fmt_num(v) if isinstance(v, (int, float)) else str(v)


def build_student_context(
    student: dict, all_students: list[dict], exam_defs: list[dict], settings, school_name: str,
    conn: psycopg.Connection, account_id: int, class_level: str,
) -> str:
    """`student`/`all_students`/`exam_defs`/`settings` match card_render.render_card's
    params exactly. Returns one text block meant to go in the chat's system
    prompt — every exam's marks/grades, class rank, attendance, and the
    same rule-based "AI analysis" points already shown on the printed card."""
    is_fa_by_key = {e["key"]: e["is_fa"] for e in exam_defs}
    exams_present = [e["key"] for e in exam_defs if e["key"] in student["exams"]]
    class_strength = settings.class_strength_override or len(all_students)

    lines: list[str] = []
    lines.append(f"School: {school_name or 'Unknown'}")
    lines.append(f"Student: {student['name']}")
    lines.append(f"Class/Section: {student.get('section') or '-'}")
    lines.append(f"Roll No: {student.get('roll') or '-'}")
    lines.append(f"Class strength: {class_strength} students")
    lines.append("")

    if not exams_present:
        lines.append("No exam marks are on file for this student.")
    for key in exams_present:
        exam = student["exams"][key]
        max_marks = settings.fa_marks_per_subject if is_fa_by_key[key] else settings.sa_marks_per_subject
        exam_total = settings.fa_total if is_fa_by_key[key] else settings.sa_total
        lines.append(f"Exam {key} (out of {_fmt(max_marks)} per subject, {_fmt(exam_total)} total):")
        for subj in exam["subjects"]:
            lines.append(f"  - {subj['name']}: {_fmt(subj['marks'])}/{_fmt(max_marks)} marks, grade {subj['grade']}")
        lines.append(f"  Total: {_fmt(exam['total_marks'])}/{_fmt(exam_total)}, grade {exam['total_grade']}, result: {exam['result'] or '-'}")
        rank = exam.get("rank")
        if isinstance(rank, (int, float)):
            lines.append(f"  Class rank in {key}: {_fmt(rank)} out of {class_strength}")
        lines.append("")

    attendance = student.get("attendance")
    if attendance:
        lines.append(f"Attendance: present {_fmt(attendance['total_present'])} of {_fmt(attendance['total_working'])} working days so far.")
        for m in attendance["months"]:
            lines.append(f"  - {m['month']}: {_fmt(m['attended'])}/{_fmt(m['working_days']) if m['working_days'] else '-'} days")
        lines.append("")

    analysis = build_analysis(student, [e["key"] for e in exam_defs], class_strength)
    if analysis["points"]:
        lines.append("Existing analysis already shown on this student's report card:")
        lines.append(analysis["intro"])
        for point in analysis["points"]:
            lines.append(f"  - {point}")

    # Same deterministic engine as the report's per-subject "Exam Focus"
    # notes (see app/reports/exam_focus.py) — gives the LLM real chapter and
    # topic names to answer with instead of only marks/grades, so a question
    # like "which chapters should he focus on?" can get a real answer
    # instead of the model either refusing or inventing chapter names. Only
    # ever this account's own confirmed data (or the shared default);
    # silently skips a subject with nothing confirmed for it.
    if exams_present:
        subject_names: list[str] = []
        for key in exams_present:
            for x in student["exams"][key]["subjects"]:
                if x["name"] not in subject_names:
                    subject_names.append(x["name"])
        focus_lines = []
        for name in subject_names:
            chapters = study_plan.get_chapters(conn, account_id, class_level, name)
            topics = get_blueprint(conn, account_id, class_level, name)
            focus = exam_focus.build_exam_focus(chapters, topics, exams_present, settings.total_fa_exams, settings.total_sa_exams)
            if not focus:
                continue
            focus_lines.append(f"{name}:")
            if focus["covered_chapters"]:
                focus_lines.append(f"  - Chapters likely covered in the upcoming {focus['exam']} exam: {', '.join(focus['covered_chapters'])}")
            topic_bits = ", ".join(
                f"{t['name']} ({t['marks']}{'+' + str(t['choice_marks']) if t['choice_marks'] else ''} marks)"
                for t in focus["top_topics"]
            )
            focus_lines.append(f"  - Highest-weightage topics in the exam blueprint: {topic_bits}")
        if focus_lines:
            lines.append("")
            lines.append("Syllabus and exam blueprint (real data, for answering questions about specific chapters/topics):")
            lines.extend(focus_lines)

    return "\n".join(lines)
