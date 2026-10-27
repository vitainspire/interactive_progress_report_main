import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.core.deps import get_current_user
from app.core.security import create_access_token, verify_password
from app.db.database import session
from app.db.users import create_user, get_user_by_email, get_user_by_id, set_default_school_name, set_school_address

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignupRequest(BaseModel):
    email: str
    password: str
    display_name: str
    school_name: str

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

    @field_validator("school_name")
    @classmethod
    def valid_school_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("School name is required")
        return v.strip()


class SchoolNameRequest(BaseModel):
    school_name: str

    @field_validator("school_name")
    @classmethod
    def valid_school_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("School name is required")
        return v.strip()


class SchoolAddressRequest(BaseModel):
    school_address: str


class LoginRequest(BaseModel):
    email: str
    password: str


def _user_out(user) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "default_school_name": user["default_school_name"],
        "school_address": user["school_address"],
    }


@router.post("/signup")
def signup(req: SignupRequest):
    with session() as conn:
        if get_user_by_email(conn, req.email):
            raise HTTPException(409, "An account with this email already exists")
        user_id = create_user(conn, req.email, req.password, req.display_name, req.school_name)
        token = create_access_token(user_id)
        return {"token": token, "user": _user_out(get_user_by_id(conn, user_id))}


@router.post("/login")
def login(req: LoginRequest):
    with session() as conn:
        user = get_user_by_email(conn, req.email)
        if not user or not verify_password(req.password, user["password_hash"]):
            raise HTTPException(401, "Incorrect email or password")
        token = create_access_token(user["id"])
        return {"token": token, "user": _user_out(user)}


@router.get("/me")
def me(current_user=Depends(get_current_user)):
    return _user_out(current_user)


@router.put("/school-name")
def update_school_name(req: SchoolNameRequest, current_user=Depends(get_current_user)):
    """Used by the mandatory first-run "set up your school" screen — mainly
    matters for an account that predates school_name being collected at
    signup, since a fresh signup already has it set from registration."""
    with session() as conn:
        set_default_school_name(conn, current_user["id"], req.school_name)
        return _user_out(get_user_by_id(conn, current_user["id"]))


@router.put("/school-address")
def update_school_address(req: SchoolAddressRequest, current_user=Depends(get_current_user)):
    """Optional — shown under the school name on the printed substitution
    sheet (see app/reports/substitution_sheet.py) when set; the sheet
    simply omits that line otherwise."""
    with session() as conn:
        set_school_address(conn, current_user["id"], req.school_address)
        return _user_out(get_user_by_id(conn, current_user["id"]))
