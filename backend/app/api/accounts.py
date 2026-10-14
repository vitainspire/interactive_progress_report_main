from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.core.deps import require_not_demo, require_role, tenant_id
from app.core.security import hash_password
from app.db.database import session
from app.db import repository as repo
from app.db import school_classes as repo_classes
from app.db.users import (
    create_student_login,
    create_teacher,
    delete_account,
    get_user_by_email,
    list_school_accounts,
    reset_password,
    set_teacher_assignments,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])

_admin_only = require_role("admin")


class AssignmentIn(BaseModel):
    class_id: int
    section: str
    subjects: list[str] = []
    restricted: bool = False


def _validate_assignments(conn, school_id: int, assignments: list[AssignmentIn]) -> list[dict]:
    out = []
    for a in assignments:
        if not repo_classes.get_class(conn, school_id, a.class_id):
            raise HTTPException(422, "Not a class in this school")
        valid_sections = set(repo.list_sections(conn, school_id, a.class_id))
        valid_subjects = set(repo.list_subjects(conn, school_id, a.class_id))
        section = a.section.upper()
        if section not in valid_sections:
            raise HTTPException(422, f"Not a section in that class: {section}")
        subjects = [s.upper() for s in a.subjects]
        bad = [s for s in subjects if s not in valid_subjects]
        if bad:
            raise HTTPException(422, f"Not a subject in that class: {', '.join(bad)}")
        if a.restricted and not subjects:
            raise HTTPException(422, f"Section {section} is marked restricted but has no subjects selected")
        out.append({"class_id": a.class_id, "section": section, "subjects": subjects, "restricted": a.restricted})
    return out


class CreateTeacherRequest(BaseModel):
    email: str
    password: str
    display_name: str
    assignments: list[AssignmentIn]

    @field_validator("password")
    @classmethod
    def valid_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UpdateTeacherAssignmentsRequest(BaseModel):
    assignments: list[AssignmentIn]


class ResetPasswordRequest(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def valid_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class CreateStudentLoginRequest(BaseModel):
    student_id: int
    pin: str

    @field_validator("pin")
    @classmethod
    def valid_pin(cls, v: str) -> str:
        if len(v) < 4:
            raise ValueError("PIN must be at least 4 characters")
        return v


class ResetPinRequest(BaseModel):
    pin: str

    @field_validator("pin")
    @classmethod
    def valid_pin(cls, v: str) -> str:
        if len(v) < 4:
            raise ValueError("PIN must be at least 4 characters")
        return v


def _teacher_out(row) -> dict:
    return {"id": row["id"], "email": row["email"], "display_name": row["display_name"], "assignments": row["assignments"]}


def _student_out(row) -> dict:
    return {
        "id": row["id"],
        "display_name": row["display_name"],
        "roll_no": row["roll_no"],
        "student_id": row["student_id"],
        "section": row["section"],
        "class_id": row["class_id"],
    }


@router.get("")
def list_accounts(current_user=Depends(_admin_only)):
    with session() as conn:
        accounts = list_school_accounts(conn, tenant_id(current_user))
        return {
            "teachers": [_teacher_out(r) for r in accounts["teachers"]],
            "students": [_student_out(r) for r in accounts["students"]],
        }


@router.post("/teachers")
def add_teacher(req: CreateTeacherRequest, current_user=Depends(_admin_only)):
    require_not_demo(current_user)
    with session() as conn:
        if get_user_by_email(conn, req.email):
            raise HTTPException(409, "An account with this email already exists")
        school_id = tenant_id(current_user)
        assignments = _validate_assignments(conn, school_id, req.assignments)
        user_id = create_teacher(conn, school_id, req.email, hash_password(req.password), req.display_name, assignments)
        return {"id": user_id, "email": req.email, "display_name": req.display_name, "assignments": assignments}


@router.put("/teachers/{teacher_id}/assignments")
def update_teacher_assignments(teacher_id: int, req: UpdateTeacherAssignmentsRequest, current_user=Depends(_admin_only)):
    require_not_demo(current_user)
    with session() as conn:
        school_id = tenant_id(current_user)
        owns = conn.execute(
            "SELECT 1 FROM app_user WHERE id = ? AND school_id = ? AND role = 'teacher'", (teacher_id, school_id)
        ).fetchone()
        if not owns:
            raise HTTPException(404, "Teacher not found")
        assignments = _validate_assignments(conn, school_id, req.assignments)
        set_teacher_assignments(conn, teacher_id, assignments)
        return {"id": teacher_id, "assignments": assignments}


@router.post("/teachers/{teacher_id}/reset-password")
def reset_teacher_password(teacher_id: int, req: ResetPasswordRequest, current_user=Depends(_admin_only)):
    require_not_demo(current_user)
    with session() as conn:
        ok = reset_password(conn, tenant_id(current_user), teacher_id, hash_password(req.password))
        if not ok:
            raise HTTPException(404, "Teacher not found")
        return {"ok": True}


@router.delete("/teachers/{teacher_id}")
def remove_teacher(teacher_id: int, current_user=Depends(_admin_only)):
    require_not_demo(current_user)
    with session() as conn:
        ok = delete_account(conn, tenant_id(current_user), teacher_id)
        if not ok:
            raise HTTPException(404, "Teacher not found")
        return {"ok": True}


@router.post("/students")
def add_student_login(req: CreateStudentLoginRequest, current_user=Depends(_admin_only)):
    require_not_demo(current_user)
    with session() as conn:
        school_id = tenant_id(current_user)
        student = repo.get_student_any_class(conn, school_id, req.student_id)
        if not student:
            raise HTTPException(404, "Student not found")
        existing = conn.execute(
            "SELECT 1 FROM app_user WHERE school_id = ? AND student_id = ? AND role = 'student'",
            (school_id, req.student_id),
        ).fetchone()
        if existing:
            raise HTTPException(409, "This student already has a login")
        user_id, roll_no = create_student_login(conn, school_id, student, hash_password(req.pin))
        return {"id": user_id, "student_id": req.student_id, "roll_no": roll_no, "display_name": student["name"]}


@router.post("/students/{account_id}/reset-pin")
def reset_student_pin(account_id: int, req: ResetPinRequest, current_user=Depends(_admin_only)):
    require_not_demo(current_user)
    with session() as conn:
        ok = reset_password(conn, tenant_id(current_user), account_id, hash_password(req.pin))
        if not ok:
            raise HTTPException(404, "Student login not found")
        return {"ok": True}


@router.delete("/students/{account_id}")
def remove_student_login(account_id: int, current_user=Depends(_admin_only)):
    require_not_demo(current_user)
    with session() as conn:
        ok = delete_account(conn, tenant_id(current_user), account_id)
        if not ok:
            raise HTTPException(404, "Student login not found")
        return {"ok": True}
