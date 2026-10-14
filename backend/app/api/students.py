from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from app.core.deps import (
    assert_can_view_student,
    get_current_user,
    get_current_user_from_header_or_query,
    require_role,
    resolve_section_scope,
    teacher_subject_filter,
    tenant_id,
)
from app.db.database import session
from app.db import repository as repo
from app.db import textbooks as repo_tb
from app.reports import grading, insights
from app.reports.generator import generate_report_html

router = APIRouter(tags=["students"])


@router.get("/students")
def list_students(class_id: int, section: str | None = None, search: str | None = None, current_user=Depends(require_role("admin", "teacher"))):
    with session() as conn:
        scope = resolve_section_scope(conn, current_user, class_id, section)
        rows = repo.list_students(conn, tenant_id(current_user), class_id, section=scope, search=search)
        return [dict(r) for r in rows]


@router.get("/students/{student_id}")
def get_student(student_id: int, all_subjects: bool = False, current_user=Depends(get_current_user)):
    user_id = tenant_id(current_user)
    with session() as conn:
        student = repo.get_student_any_class(conn, user_id, student_id)
        if not student:
            raise HTTPException(404, "Student not found")
        assert_can_view_student(conn, current_user, student)
        class_id = student["class_id"]
        subject_filter = teacher_subject_filter(conn, current_user, class_id, student["section"]) if current_user["role"] == "teacher" else None
        # A restricted teacher already has legitimate access to this one
        # student (they teach their section) — the subject restriction is
        # meant to keep their day-to-day/class-wide views focused on their
        # own subject(s), not to hide the rest of a specific student's
        # record from them forever. ?all_subjects=true is an explicit,
        # conscious opt-in to see everything for this student; the default
        # stays filtered to their own subject(s).
        subject_restricted = subject_filter is not None
        own_subjects = subject_filter or []
        if all_subjects:
            subject_filter = None
        phases = [p["code"] for p in repo.list_phases(conn, user_id, class_id)]
        exam_results = repo.get_student_exam_results(conn, user_id, class_id, student_id)
        if subject_filter is not None:
            exam_results = [r for r in exam_results if r["subject"] in subject_filter]
        exam_summaries = repo.get_student_exam_summaries(conn, user_id, class_id, student_id)
        attendance = repo.get_student_attendance(conn, user_id, class_id, student_id)
        att_summary = repo.get_student_attendance_summary(conn, user_id, class_id, student_id)
        series = insights.build_subject_series(exam_results, phases)
        total_students = repo.total_student_count(conn, user_id, class_id)

        # Subjects the student is currently failing (latest phase), matched
        # against any textbook chapters the headmaster has uploaded for that
        # subject — a stand-in "what to focus on" until topic-level marks
        # exist to pinpoint exactly which chapter is the problem.
        focus_topics = []
        for s in series:
            if not s.points or grading.is_pass(s.points[-1].grade) is not False:
                continue
            topics = repo_tb.get_textbook_topics(conn, user_id, class_id, s.subject)
            if topics:
                focus_topics.append(
                    {
                        "subject": s.subject,
                        "topics": [{"chapter_no": t["chapter_no"], "title": t["title"], "page": t["page"]} for t in topics],
                    }
                )

        return {
            "student": dict(student),
            "total_students_in_class": total_students,
            "exam_summaries": [dict(r) for r in exam_summaries],
            "exam_results": [dict(r) | {"is_pass": grading.is_pass(r["grade"])} for r in exam_results],
            "subject_trends": [
                {
                    "subject": s.subject,
                    "direction": s.direction,
                    "points": [{"phase_code": p.phase_code, "marks": p.marks, "max_marks": p.max_marks, "pct": p.pct, "grade": p.grade} for p in s.points],
                }
                for s in series
            ],
            "attendance_months": [dict(r) for r in attendance],
            "attendance_summary": dict(att_summary) if att_summary else None,
            "focus_topics": focus_topics,
            "subject_restricted": subject_restricted,
            "own_subjects": own_subjects,
            "showing_all_subjects": all_subjects,
        }


@router.get("/students/{student_id}/report", response_class=HTMLResponse)
def get_student_report(student_id: int, all_subjects: bool = False, current_user=Depends(get_current_user_from_header_or_query)):
    user_id = tenant_id(current_user)
    with session() as conn:
        student = repo.get_student_any_class(conn, user_id, student_id)
        if not student:
            raise HTTPException(404, "Student not found")
        assert_can_view_student(conn, current_user, student)
        class_id = student["class_id"]
        subject_filter = teacher_subject_filter(conn, current_user, class_id, student["section"]) if current_user["role"] == "teacher" else None
        if all_subjects:
            subject_filter = None
        try:
            html = generate_report_html(conn, user_id, class_id, student_id, subject_filter=subject_filter)
        except ValueError:
            raise HTTPException(404, "Student not found")
        return HTMLResponse(content=html)
