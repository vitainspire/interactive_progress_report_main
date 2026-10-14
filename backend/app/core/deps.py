from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.db import repository as repo
from app.db.database import get_connection
from app.db.users import get_user_by_id

_bearer = HTTPBearer(auto_error=False)


def _load_user(user_id: int | None):
    if user_id is None:
        raise HTTPException(401, "Invalid or expired token")
    conn = get_connection()
    try:
        user = get_user_by_id(conn, user_id)
    finally:
        conn.close()
    if user is None:
        raise HTTPException(401, "User not found")
    return user


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)):
    if credentials is None:
        raise HTTPException(401, "Not authenticated")
    return _load_user(decode_access_token(credentials.credentials))


def get_current_user_from_header_or_query(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    token: str | None = None,
):
    """Same as get_current_user, but also accepts ?token= — needed for plain
    <a href> browser navigations (e.g. opening a report in a new tab), which
    can't attach an Authorization header."""
    raw = credentials.credentials if credentials else token
    if raw is None:
        raise HTTPException(401, "Not authenticated")
    return _load_user(decode_access_token(raw))


def require_not_demo(user) -> None:
    if user["is_demo"]:
        raise HTTPException(403, "This is the shared demo account and is read-only. Sign up for your own account to upload data.")


def tenant_id(user) -> int:
    """The school account id whose data this login can see: itself for an
    admin/headmaster row, or the admin it was created under for a
    teacher/student row."""
    return user["school_id"] or user["id"]


def require_role(*roles: str):
    """Dependency factory: 403s unless the caller's role is one of `roles`.
    Used explicitly on each route (default-deny) rather than inferred."""

    def _dep(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "Not allowed for this account type")
        return user

    return _dep


def resolve_section_scope(conn, user, class_id: int, requested_section: str | None):
    """What section filter a class/dashboard/student-list query should use,
    within one class (classes are never implicitly merged). Admins pass the
    requested section straight through (None = every section in that
    class). Teachers may only request one of their own assigned sections
    *within that class* (403 otherwise); if they didn't request one, the
    query is scoped to their full assigned set in that class instead of
    the whole class."""
    if user["role"] != "teacher":
        return requested_section
    allowed = repo.get_teacher_sections(conn, user["id"], class_id)
    if requested_section:
        if requested_section.upper() not in allowed:
            raise HTTPException(403, "You don't teach that section")
        return requested_section
    return allowed


def teacher_subject_filter(conn, user, class_id: int, section: str) -> list[str] | None:
    """The subjects a teacher may see marks for within one class+section —
    None means unrestricted (sees every subject), as it does for every
    teacher by default until an admin turns restriction on for that
    section."""
    assignments = repo.get_teacher_assignments(conn, user["id"], class_id)
    a = assignments.get(section.upper())
    if not a or not a["restricted"]:
        return None
    return a["subjects"]


def resolve_subject_section_scope(conn, user, class_id: int, requested_section: str | None, subject: str | None):
    """Like resolve_section_scope, but for a query that also names a
    subject (e.g. /classes/subject-stats): a teacher may only query a
    subject within a section where that subject is actually permitted —
    unrestricted sections permit everything, restricted ones only their
    listed subjects."""
    scope = resolve_section_scope(conn, user, class_id, requested_section)
    if user["role"] != "teacher" or not subject:
        return scope
    assignments = repo.get_teacher_assignments(conn, user["id"], class_id)
    if isinstance(scope, list):
        allowed = [s for s in scope if repo.teacher_allows_subject(assignments, s, subject)]
        if not allowed:
            raise HTTPException(403, "You don't teach that subject in any of your sections")
        return allowed
    if not repo.teacher_allows_subject(assignments, scope, subject):
        raise HTTPException(403, "You don't teach that subject in that section")
    return scope


def assert_can_view_student(conn, user, student_row) -> None:
    """Guards /students/{id} and its report: admins see anyone in their
    school, teachers only students in a class+section they teach, students
    only themselves. No separate class_id argument is needed — student_row
    already carries its own class_id, which is what matters (a teacher
    assigned to "Section A" in one class must not match a different
    class's "Section A")."""
    if user["role"] == "admin":
        return
    if user["role"] == "teacher":
        allowed = repo.get_teacher_sections(conn, user["id"], student_row["class_id"])
        if student_row["section"] not in allowed:
            raise HTTPException(403, "You don't teach that section")
        return
    if user["role"] == "student":
        if student_row["id"] != user["student_id"]:
            raise HTTPException(403, "You can only view your own report")
        return
    raise HTTPException(403, "Not allowed for this account type")
