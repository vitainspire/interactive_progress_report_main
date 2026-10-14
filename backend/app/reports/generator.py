from __future__ import annotations

import sqlite3
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.db import repository as repo
from app.db import school_classes as repo_classes
from app.db import textbooks as repo_tb
from app.reports import grading, insights, telugu_text

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=select_autoescape(["html", "jinja"]))

SUBJECT_EN = {
    "TELUGU": "Telugu",
    "HINDI": "Hindi",
    "ENGLISH": "English",
    "MATHS": "Maths",
    "PHYSICAL SCIENCE": "Physical Science",
    "BIOLOGY": "Biology",
    "SOCIAL": "Social",
}

MONTH_TE = {
    "JUNE": "జూన్", "JULY": "జూలై", "AUGUST": "ఆగస్టు", "SEPTEMBER": "సెప్టెంబర్",
    "OCTOBER": "అక్టోబర్", "NOVEMBER": "నవంబర్", "DECEMBER": "డిసెంబర్",
    "JANUARY": "జనవరి", "FEBRUARY": "ఫిబ్రవరి", "MARCH": "మార్చి", "APRIL": "ఏప్రిల్", "MAY": "మే",
}


def phase_label_te(code: str, raw_label: str) -> str:
    if code.startswith("FA"):
        return f"FA-{code[2:]} (ప్రతి సబ్జెక్టు 50కి)"
    if code.startswith("SA"):
        return f"SA-{code[2:]} (5 సబ్జెక్టులు 100కి, PS & BS 50కి)"
    if code == "PREFINAL":
        return "Pre-Final (5 సబ్జెక్టులు 100కి, PS & BS 50కి)"
    return raw_label


def generate_report_html(conn: sqlite3.Connection, user_id: int, class_id: int, student_id: int, subject_filter: list[str] | None = None) -> str:
    student = repo.get_student(conn, user_id, class_id, student_id)
    if not student:
        raise ValueError("student not found")

    phases_meta = repo.list_phases(conn, user_id, class_id)
    phase_order = [p["code"] for p in phases_meta]
    exam_rows = repo.get_student_exam_results(conn, user_id, class_id, student_id)
    if subject_filter is not None:
        exam_rows = [r for r in exam_rows if r["subject"] in subject_filter]
    exam_summaries = {r["phase_code"]: r for r in repo.get_student_exam_summaries(conn, user_id, class_id, student_id)}
    total_students = repo.total_student_count(conn, user_id, class_id)

    phases_ctx = []
    any_data = False
    for p in phases_meta:
        code = p["code"]
        summary = exam_summaries.get(code)
        subject_rows = [r for r in exam_rows if r["phase_code"] == code]
        if not subject_rows and not summary:
            continue
        any_data = True
        rows_ctx = []
        for r in subject_rows:
            is_p = grading.is_pass(r["grade"])
            if r["marks"] is None:
                marks_display = "-"
            elif code.startswith("FA"):
                marks_display = f"{r['marks']:g}"
            else:
                marks_display = f"{r['marks']:g}/{int(r['max_marks'])}"
            rows_ctx.append(
                {
                    "subject_en": SUBJECT_EN.get(r["subject"], r["subject"].title()),
                    "marks_display": marks_display,
                    "grade": r["grade"],
                    "result_class": "p" if is_p else ("f" if is_p is False else ""),
                    "result_text": "PASS" if is_p else ("FAIL" if is_p is False else "-"),
                }
            )
        total_result_class = "p" if (summary and (summary["result"] or "").upper() == "PASS") else (
            "f" if summary and (summary["result"] or "").upper() == "FAIL" else ""
        )
        result_text = (summary["result"] if summary and summary["result"] else "-")
        if summary and summary["rank"]:
            result_text = f"{result_text} (Rank {summary['rank']}/{total_students})"
        max_total = summary["max_total"] if summary and summary["max_total"] else sum((r["max_marks"] or 0) for r in subject_rows)
        total_marks_val = summary["total_marks"] if summary else None
        phases_ctx.append(
            {
                "code": code,
                "label_te": phase_label_te(code, p["label"]),
                "subject_rows": rows_ctx,
                "total_marks": f"{total_marks_val:g}" if total_marks_val is not None else "-",
                "max_total": max_total,
                "total_grade": summary["total_grade"] if summary else None,
                "result_class": total_result_class,
                "result_text": result_text,
            }
        )

    subject_series = insights.build_subject_series(exam_rows, phase_order)
    rank_insight = insights.build_rank_insight(list(exam_summaries.values()), phase_order)
    fail_rows = [
        {"subject": r["subject"], "phase_code": r["phase_code"], "marks": r["marks"], "max_marks": r["max_marks"], "grade": r["grade"]}
        for r in exam_rows
        if grading.is_pass(r["grade"]) is False
    ]
    analysis_html = telugu_text.build_analysis_html(student["name"], subject_series, rank_insight, bool(fail_rows), total_students)

    staff_rows = repo.get_staff_for_section(conn, user_id, class_id, student["section"])
    declining_subjects = {s.subject for s in subject_series if s.direction == "declining"}
    staff_by_section = {r["subject"]: r["teacher_name"].title() for r in staff_rows if r["subject"] in declining_subjects}
    fail_html = telugu_text.build_fail_html(fail_rows, staff_by_section, any_data)

    focus_topics = []
    for s in subject_series:
        if not s.points or grading.is_pass(s.points[-1].grade) is not False:
            continue
        topics = repo_tb.get_textbook_topics(conn, user_id, class_id, s.subject)
        if topics:
            focus_topics.append({"subject": s.subject, "topics": [{"title": t["title"]} for t in topics]})
    focus_html = telugu_text.build_focus_html(focus_topics)

    att_rows = repo.get_student_attendance(conn, user_id, class_id, student_id)
    att_summary = repo.get_student_attendance_summary(conn, user_id, class_id, student_id)
    attendance_months = [
        {"month_te": MONTH_TE.get(r["month"], r["month"].title()), "days_present": r["days_present"], "working_days": r["working_days"]}
        for r in att_rows
    ]
    att_insight = insights.build_attendance_insight(
        att_summary["total_present"] if att_summary else None,
        att_summary["total_working_days"] if att_summary else None,
    )
    attendance_remark_html = telugu_text.build_attendance_remark(att_insight)

    class_row = repo_classes.get_class(conn, user_id, class_id)
    class_label = class_row["name"] if class_row else repo.get_setting(conn, user_id, "class_label", "తరగతి")
    school_name = repo.get_setting(conn, user_id, "school_name", "")
    school_udise = repo.get_setting(conn, user_id, "school_udise", "")

    contacts = []
    headmaster_name = repo.get_setting(conn, user_id, "headmaster_name")
    if headmaster_name:
        contacts.append({"role_te": "హెడ్మాస్టర్", "name": headmaster_name.title(), "phone": repo.get_setting(conn, user_id, "headmaster_phone")})
    for r in staff_rows:
        contacts.append(
            {
                "role_te": f"{telugu_text.subject_te(r['subject'])} టీచర్",
                "name": r["teacher_name"].title(),
                "phone": repo.get_setting(conn, user_id, f"teacher_phone_{class_id}_{r['section']}_{r['subject']}"),
            }
        )

    ctx = {
        "student": dict(student),
        "class_label": class_label,
        "school": {"name": school_name, "udise": school_udise},
        "phases": phases_ctx,
        "analysis_html": analysis_html,
        "fail_html": fail_html,
        "focus_html": focus_html,
        "attendance_months": attendance_months,
        "attendance_remark_html": attendance_remark_html,
        "home_advice_html": telugu_text.HOME_ADVICE,
        "contacts": contacts,
    }
    template = _env.get_template("progress_card.html.jinja")
    return template.render(**ctx)
