from fastapi import APIRouter, Depends

from app.core.deps import require_role, tenant_id
from app.db.database import session
from app.db import repository as repo

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def get_dashboard(class_id: int, current_user=Depends(require_role("admin", "teacher"))):
    user_id = tenant_id(current_user)
    is_teacher = current_user["role"] == "teacher"
    with session() as conn:
        phases = repo.list_phases(conn, user_id, class_id)
        sections = repo.list_sections(conn, user_id, class_id)
        if is_teacher:
            allowed = set(repo.get_teacher_sections(conn, current_user["id"], class_id))
            sections = [s for s in sections if s in allowed]
        subjects = repo.list_subjects(conn, user_id, class_id)

        # A teacher's "overall" row aggregates just their own sections
        # (not the whole class) — the SQL filter can be a list, but the
        # section field in the response is still reset to None below so it
        # reads the same as the admin's whole-class "overall" row.
        overall_scope = sections if is_teacher else None

        phase_section_summary = []
        for p in phases:
            for sec in sections:
                s = repo.class_summary(conn, user_id, class_id, p["code"], sec)
                phase_section_summary.append(s)
            overall = repo.class_summary(conn, user_id, class_id, p["code"], overall_scope)
            overall["section"] = None
            phase_section_summary.append(overall)

        subject_averages = []
        if phases:
            latest_phase = phases[-1]["code"]
            assignments = repo.get_teacher_assignments(conn, current_user["id"], class_id) if is_teacher else {}
            for subj in subjects:
                if is_teacher:
                    # Only average this subject over the sections where the
                    # teacher is actually permitted to see it — a section
                    # restricted to other subjects shouldn't leak into the
                    # average just because it's one of their sections.
                    subj_scope = [s for s in sections if repo.teacher_allows_subject(assignments, s, subj)]
                    if not subj_scope:
                        continue
                else:
                    subj_scope = overall_scope
                stats = repo.subject_stats(conn, user_id, class_id, latest_phase, subj, subj_scope)
                if stats.get("count"):
                    subject_averages.append(
                        {"subject": subj, "average": round(stats["average"], 1), "max_marks": stats["max_marks"]}
                    )

        total_students = (
            len(repo.list_students(conn, user_id, class_id, section=sections)) if is_teacher else repo.total_student_count(conn, user_id, class_id)
        )

        return {
            "total_students": total_students,
            "sections": sections,
            "phases": [dict(p) for p in phases],
            "phase_section_summary": phase_section_summary,
            "latest_phase_subject_averages": subject_averages,
        }
