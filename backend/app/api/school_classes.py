from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.core.deps import require_not_demo, require_role, tenant_id
from app.db import repository as repo
from app.db import school_classes as repo_classes
from app.db.database import session

router = APIRouter(prefix="/school-classes", tags=["school-classes"])

_admin_only = require_role("admin")

MAX_SECTIONS = 26


class CreateClassRequest(BaseModel):
    name: str
    short_code: str
    section_count: int = 1

    @field_validator("name")
    @classmethod
    def valid_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Class name is required")
        return v.strip()

    @field_validator("short_code")
    @classmethod
    def valid_short_code(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("Short code is required")
        if "-" in v:
            raise ValueError("Short code can't contain a dash")
        if len(v) > 12:
            raise ValueError("Short code must be 12 characters or fewer")
        return v

    @field_validator("section_count")
    @classmethod
    def valid_section_count(cls, v: int) -> int:
        if v < 1 or v > MAX_SECTIONS:
            raise ValueError(f"Number of sections must be between 1 and {MAX_SECTIONS}")
        return v


class UpdateClassRequest(BaseModel):
    name: str | None = None
    order_index: int | None = None


class UpdateSectionCountRequest(BaseModel):
    section_count: int

    @field_validator("section_count")
    @classmethod
    def valid_section_count(cls, v: int) -> int:
        if v < 1 or v > MAX_SECTIONS:
            raise ValueError(f"Number of sections must be between 1 and {MAX_SECTIONS}")
        return v


def _class_out(conn, row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "short_code": row["short_code"],
        "order_index": row["order_index"],
        "sections": repo_classes.list_class_sections(conn, row["id"]),
        "total_students": repo.total_student_count(conn, row["user_id"], row["id"]),
    }


@router.get("")
def list_classes(current_user=Depends(require_role("admin", "teacher"))):
    with session() as conn:
        user_id = tenant_id(current_user)
        classes = repo_classes.list_classes(conn, user_id)
        if current_user["role"] == "teacher":
            allowed = set(repo.get_teacher_classes(conn, current_user["id"]))
            classes = [c for c in classes if c["id"] in allowed]
        return [_class_out(conn, c) for c in classes]


@router.post("")
def create_class(req: CreateClassRequest, current_user=Depends(_admin_only)):
    require_not_demo(current_user)
    with session() as conn:
        user_id = tenant_id(current_user)
        if repo_classes.get_class_by_short_code(conn, user_id, req.short_code):
            raise HTTPException(409, f"Short code '{req.short_code}' is already used by another class")
        existing_names = {c["name"].lower() for c in repo_classes.list_classes(conn, user_id)}
        if req.name.lower() in existing_names:
            raise HTTPException(409, "A class with this name already exists")
        class_id = repo_classes.create_class(conn, user_id, req.name, req.short_code)
        repo_classes.set_class_sections(conn, class_id, repo_classes.generate_section_labels(req.section_count))
        return _class_out(conn, repo_classes.get_class(conn, user_id, class_id))


@router.put("/{class_id}")
def update_class(class_id: int, req: UpdateClassRequest, current_user=Depends(_admin_only)):
    require_not_demo(current_user)
    with session() as conn:
        user_id = tenant_id(current_user)
        ok = repo_classes.update_class(conn, user_id, class_id, name=req.name, order_index=req.order_index)
        if not ok:
            raise HTTPException(404, "Class not found")
        return _class_out(conn, repo_classes.get_class(conn, user_id, class_id))


@router.put("/{class_id}/sections")
def update_section_count(class_id: int, req: UpdateSectionCountRequest, current_user=Depends(_admin_only)):
    """Resizes a class's section list to A..req.section_count. Growing is
    always safe (pure addition); shrinking is blocked if any section that
    would be dropped already has students or a teacher assigned to it."""
    require_not_demo(current_user)
    with session() as conn:
        user_id = tenant_id(current_user)
        cls = repo_classes.get_class(conn, user_id, class_id)
        if not cls:
            raise HTTPException(404, "Class not found")
        current = repo_classes.list_class_sections(conn, class_id)
        target = repo_classes.generate_section_labels(req.section_count)
        dropped = [s for s in current if s not in target]
        in_use = [s for s in dropped if repo_classes.section_in_use(conn, class_id, s)]
        if in_use:
            raise HTTPException(409, f"Can't remove section(s) {', '.join(in_use)} — they already have students or a teacher assigned")
        repo_classes.set_class_sections(conn, class_id, target)
        return _class_out(conn, cls)


@router.delete("/{class_id}")
def delete_class(class_id: int, force: bool = False, current_user=Depends(_admin_only)):
    require_not_demo(current_user)
    with session() as conn:
        ok, error = repo_classes.delete_class(conn, tenant_id(current_user), class_id, force=force)
        if not ok:
            raise HTTPException(409 if error else 404, error or "Class not found")
        return {"ok": True}
