import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.database import session
from app.db.repository import get_teacher_assignment_list
from app.db.users import create_user, get_admin_by_school_code, get_demo_user, get_student_login, get_user_by_email, get_user_by_id

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignupRequest(BaseModel):
    email: str
    password: str
    display_name: str
    school_name: str | None = None

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        if not EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address")
        return v

    @field_validator("password")
    @classmethod
    def valid_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("display_name")
    @classmethod
    def valid_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name is required")
        return v.strip()


class LoginRequest(BaseModel):
    email: str
    password: str


class StudentLoginRequest(BaseModel):
    school_code: str
    roll_no: str
    pin: str


def _user_out(conn, user) -> dict:
    out = {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "school_name": user["school_name"],
        "is_demo": bool(user["is_demo"]),
        "role": user["role"],
    }
    if user["role"] == "admin":
        out["school_code"] = user["school_code"]
    elif user["role"] == "teacher":
        assignments = get_teacher_assignment_list(conn, user["id"])
        out["assignments"] = assignments
        out["class_ids"] = sorted({a["class_id"] for a in assignments})
    elif user["role"] == "student":
        out["student_id"] = user["student_id"]
        out["roll_no"] = user["roll_no"]
    return out


@router.post("/signup")
def signup(req: SignupRequest):
    with session() as conn:
        if get_user_by_email(conn, req.email):
            raise HTTPException(409, "An account with this email already exists")
        user_id = create_user(conn, req.email, hash_password(req.password), req.display_name, req.school_name)
        token = create_access_token(user_id)
        return {"token": token, "user": _user_out(conn, get_user_by_id(conn, user_id))}


@router.post("/login")
def login(req: LoginRequest):
    with session() as conn:
        user = get_user_by_email(conn, req.email)
        # Students authenticate via /auth/student-login (roll number + PIN),
        # never through the generic email/password path — even if a
        # synthetic placeholder email were somehow guessed, it should not
        # be a usable login here.
        if not user or user["role"] == "student" or not verify_password(req.password, user["password_hash"]):
            raise HTTPException(401, "Incorrect email or password")
        token = create_access_token(user["id"])
        return {"token": token, "user": _user_out(conn, user)}


@router.post("/student-login")
def student_login(req: StudentLoginRequest):
    with session() as conn:
        admin = get_admin_by_school_code(conn, req.school_code)
        if not admin:
            raise HTTPException(401, "Incorrect school code, roll number, or PIN")
        student_user = get_student_login(conn, admin["id"], req.roll_no.strip().upper())
        if not student_user or not verify_password(req.pin, student_user["password_hash"]):
            raise HTTPException(401, "Incorrect school code, roll number, or PIN")
        token = create_access_token(student_user["id"])
        return {"token": token, "user": _user_out(conn, student_user)}


@router.post("/demo-login")
def demo_login():
    """One-click entry into the shared, read-only demo account — no signup required."""
    with session() as conn:
        demo_user = get_demo_user(conn)
        if not demo_user:
            raise HTTPException(503, "Demo account is not available right now")
        token = create_access_token(demo_user["id"])
        return {"token": token, "user": _user_out(conn, demo_user)}


@router.get("/me")
def me(current_user=Depends(get_current_user)):
    with session() as conn:
        return _user_out(conn, current_user)
