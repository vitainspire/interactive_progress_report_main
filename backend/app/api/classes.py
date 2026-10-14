from fastapi import APIRouter, Depends

from app.core.deps import require_role, resolve_section_scope, resolve_subject_section_scope, tenant_id
from app.db.database import session
from app.db import repository as repo

router = APIRouter(tags=["classes"])

_admin_or_teacher = require_role("admin", "teacher")


@router.get("/meta")
def get_meta(class_id: int, current_user=Depends(_admin_or_teacher)):
    user_id = tenant_id(current_user)
    with session() as conn:
        sections = repo.list_sections(conn, user_id, class_id)
        if current_user["role"] == "teacher":
            allowed = set(repo.get_teacher_sections(conn, current_user["id"], class_id))
            sections = [s for s in sections if s in allowed]
        return {
            "sections": sections,
            "subjects": repo.list_subjects(conn, user_id, class_id),
            "phases": [dict(p) for p in repo.list_phases(conn, user_id, class_id)],
            "total_students": repo.total_student_count(conn, user_id, class_id),
        }


@router.get("/classes/summary")
def get_class_summary(class_id: int, phase: str, section: str | None = None, current_user=Depends(_admin_or_teacher)):
    with session() as conn:
        scope = resolve_section_scope(conn, current_user, class_id, section)
        result = repo.class_summary(conn, tenant_id(current_user), class_id, phase, scope)
        result["section"] = section
        return result


@router.get("/classes/subject-stats")
def get_subject_stats(class_id: int, phase: str, subject: str, section: str | None = None, current_user=Depends(_admin_or_teacher)):
    with session() as conn:
        scope = resolve_subject_section_scope(conn, current_user, class_id, section, subject)
        result = repo.subject_stats(conn, tenant_id(current_user), class_id, phase, subject, scope)
        result["section"] = section
        return result


@router.get("/classes/top")
def get_top(class_id: int, phase: str, section: str | None = None, limit: int = 10, current_user=Depends(_admin_or_teacher)):
    with session() as conn:
        scope = resolve_section_scope(conn, current_user, class_id, section)
        return [dict(r) for r in repo.top_students(conn, tenant_id(current_user), class_id, phase, scope, limit)]


@router.get("/classes/failures")
def get_failures(class_id: int, phase: str | None = None, subject: str | None = None, section: str | None = None, current_user=Depends(_admin_or_teacher)):
    with session() as conn:
        if subject:
            scope = resolve_subject_section_scope(conn, current_user, class_id, section, subject)
            rows = repo.students_failed(conn, tenant_id(current_user), class_id, phase, subject, scope)
        else:
            scope = resolve_section_scope(conn, current_user, class_id, section)
            rows = repo.students_failed(conn, tenant_id(current_user), class_id, phase, subject, scope)
            if current_user["role"] == "teacher":
                assignments = repo.get_teacher_assignments(conn, current_user["id"], class_id)
                rows = [r for r in rows if repo.teacher_allows_subject(assignments, r["section"], r["subject"])]
        return [dict(r) for r in rows]
