import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.db import timetable as repo
from app.db.database import session

router = APIRouter(prefix="/timetable", tags=["timetable"])

_VALID_DAYS = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}


def _class_out(row: dict) -> dict:
    return {"id": row["id"], "grade": row["grade"], "section": row["section"]}


def _subject_out(row: dict) -> dict:
    return {"id": row["id"], "name": row["name"], "code": row["code"]}


def _teacher_out(row: dict) -> dict:
    return {"id": row["id"], "name": row["name"], "code": row["code"], "max_periods_per_day": row["max_periods_per_day"]}


def _class_subject_out(row: dict) -> dict:
    return {
        "subject_id": row["subject_id"],
        "subject_name": row["subject_name"],
        "subject_code": row["subject_code"],
        "teacher_id": row["teacher_id"],
        "teacher_name": row["teacher_name"],
        "teacher_code": row["teacher_code"],
        "periods_per_week": row["periods_per_week"],
    }


# ---- Classes ----


class ClassCreate(BaseModel):
    grade: str
    section: str = ""


@router.get("/classes")
def list_classes(current_user=Depends(get_current_user)):
    with session() as conn:
        return [_class_out(r) for r in repo.list_classes(conn, current_user["id"])]


@router.post("/classes")
def create_class(req: ClassCreate, current_user=Depends(get_current_user)):
    grade = req.grade.strip()
    section = req.section.strip()
    if not grade:
        raise HTTPException(422, "Grade is required")
    with session() as conn:
        if repo.get_class_by_name(conn, current_user["id"], grade, section):
            raise HTTPException(409, f"{grade} {section}".strip() + " already exists")
        class_id = repo.create_class(conn, current_user["id"], grade, section)
        return _class_out(repo.get_class(conn, current_user["id"], class_id))


@router.delete("/classes/{class_id}")
def delete_class(class_id: int, current_user=Depends(get_current_user)):
    with session() as conn:
        if not repo.delete_class(conn, current_user["id"], class_id):
            raise HTTPException(404, "Class not found")
    return {"ok": True}


# ---- Subjects ----


class SubjectCreate(BaseModel):
    name: str
    code: str = ""


@router.get("/subjects")
def list_subjects(current_user=Depends(get_current_user)):
    with session() as conn:
        return [_subject_out(r) for r in repo.list_subjects(conn, current_user["id"])]


@router.post("/subjects")
def create_subject(req: SubjectCreate, current_user=Depends(get_current_user)):
    name = req.name.strip()
    if not name:
        raise HTTPException(422, "Subject name is required")
    with session() as conn:
        if repo.get_subject_by_name(conn, current_user["id"], name):
            raise HTTPException(409, f"{name} already exists")
        subject_id = repo.create_subject(conn, current_user["id"], name, req.code.strip())
        return _subject_out(repo.get_subject(conn, current_user["id"], subject_id))


@router.delete("/subjects/{subject_id}")
def delete_subject(subject_id: int, current_user=Depends(get_current_user)):
    with session() as conn:
        if not repo.delete_subject(conn, current_user["id"], subject_id):
            raise HTTPException(404, "Subject not found")
    return {"ok": True}


# ---- Teachers ----


class TeacherCreate(BaseModel):
    name: str
    code: str = ""
    max_periods_per_day: int | None = None


@router.get("/teachers")
def list_teachers(current_user=Depends(get_current_user)):
    with session() as conn:
        return [_teacher_out(r) for r in repo.list_teachers(conn, current_user["id"])]


@router.post("/teachers")
def create_teacher(req: TeacherCreate, current_user=Depends(get_current_user)):
    name = req.name.strip()
    if not name:
        raise HTTPException(422, "Teacher name is required")
    with session() as conn:
        teacher_id = repo.create_teacher(conn, current_user["id"], name, req.code.strip(), req.max_periods_per_day)
        return _teacher_out(repo.get_teacher(conn, current_user["id"], teacher_id))


@router.delete("/teachers/{teacher_id}")
def delete_teacher(teacher_id: int, current_user=Depends(get_current_user)):
    with session() as conn:
        if not repo.delete_teacher(conn, current_user["id"], teacher_id):
            raise HTTPException(404, "Teacher not found")
    return {"ok": True}


# ---- Class <-> subject assignments ----


class ClassSubjectUpsert(BaseModel):
    subject_id: int
    teacher_id: int | None = None
    periods_per_week: int = 0


@router.get("/classes/{class_id}/subjects")
def list_class_subjects(class_id: int, current_user=Depends(get_current_user)):
    with session() as conn:
        if not repo.get_class(conn, current_user["id"], class_id):
            raise HTTPException(404, "Class not found")
        return [_class_subject_out(r) for r in repo.list_class_subjects(conn, class_id)]


@router.put("/classes/{class_id}/subjects")
def upsert_class_subject(class_id: int, req: ClassSubjectUpsert, current_user=Depends(get_current_user)):
    if req.periods_per_week < 0:
        raise HTTPException(422, "Periods per week can't be negative")
    with session() as conn:
        if not repo.get_class(conn, current_user["id"], class_id):
            raise HTTPException(404, "Class not found")
        if not repo.get_subject(conn, current_user["id"], req.subject_id):
            raise HTTPException(404, "Subject not found")
        if req.teacher_id is not None and not repo.get_teacher(conn, current_user["id"], req.teacher_id):
            raise HTTPException(404, "Teacher not found")
        repo.upsert_class_subject(conn, class_id, req.subject_id, req.teacher_id, req.periods_per_week)
        row = next(r for r in repo.list_class_subjects(conn, class_id) if r["subject_id"] == req.subject_id)
        return _class_subject_out(row)


@router.delete("/classes/{class_id}/subjects/{subject_id}")
def delete_class_subject(class_id: int, subject_id: int, current_user=Depends(get_current_user)):
    with session() as conn:
        if not repo.get_class(conn, current_user["id"], class_id):
            raise HTTPException(404, "Class not found")
        if not repo.delete_class_subject(conn, class_id, subject_id):
            raise HTTPException(404, "Assignment not found")
    return {"ok": True}


# ---- School weekly structure ----


_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


class BreakIn(BaseModel):
    after_period: int
    duration_minutes: int
    label: str = "Break"


class SchoolConfigUpdate(BaseModel):
    working_days: list[str]
    periods_per_day: int
    start_time: str
    end_time: str
    breaks: list[BreakIn] = []


@router.get("/config")
def get_config(current_user=Depends(get_current_user)):
    with session() as conn:
        return repo.get_school_config(conn, current_user["id"])


@router.put("/config")
def update_config(req: SchoolConfigUpdate, current_user=Depends(get_current_user)):
    days = [d.strip().upper() for d in req.working_days if d.strip()]
    if not days or any(d not in _VALID_DAYS for d in days):
        raise HTTPException(422, "Invalid working days")
    if not (1 <= req.periods_per_day <= 12):
        raise HTTPException(422, "Periods per day must be between 1 and 12")
    if not _TIME_RE.match(req.start_time) or not _TIME_RE.match(req.end_time):
        raise HTTPException(422, "Start and end time must be in HH:MM (24-hour) format")
    if req.start_time >= req.end_time:
        raise HTTPException(422, "End time must be after start time")

    seen_positions: set[int] = set()
    breaks: list[dict] = []
    for b in req.breaks:
        if not (1 <= b.after_period <= req.periods_per_day - 1):
            raise HTTPException(422, f"A break must fall after period 1 through {req.periods_per_day - 1}")
        if b.after_period in seen_positions:
            raise HTTPException(422, f"Only one break can follow period {b.after_period}")
        seen_positions.add(b.after_period)
        if not (1 <= b.duration_minutes <= 180):
            raise HTTPException(422, "A break must be between 1 and 180 minutes")
        breaks.append({"after_period": b.after_period, "duration_minutes": b.duration_minutes, "label": b.label.strip() or "Break"})
    breaks.sort(key=lambda b: b["after_period"])

    total_minutes = _minutes(req.end_time) - _minutes(req.start_time)
    break_minutes = sum(b["duration_minutes"] for b in breaks)
    if total_minutes - break_minutes < req.periods_per_day:
        raise HTTPException(422, "The breaks don't leave enough time in the day for every period")

    with session() as conn:
        repo.set_school_config(conn, current_user["id"], days, req.periods_per_day, req.start_time, req.end_time, breaks)
    return {
        "working_days": days,
        "periods_per_day": req.periods_per_day,
        "start_time": req.start_time,
        "end_time": req.end_time,
        "breaks": breaks,
    }
