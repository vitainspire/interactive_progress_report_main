import json
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.db import calendar as repo
from app.db import users as user_repo
from app.db.database import session

router = APIRouter(prefix="/calendar", tags=["calendar"])

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_VALID_TYPES = {"holiday", "exam"}
_VALID_WEEK_PATTERNS = {"5-day", "6-day"}


def _event_out(row: dict) -> dict:
    return {
        "id": row["id"],
        "event_type": row["event_type"],
        "label": row["label"],
        "exam_key": row["exam_key"],
        "plan_type": row["plan_type"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
    }


def _exam_type_out(row: dict) -> dict:
    return {"id": row["id"], "name": row["name"], "count_per_year": row["count_per_year"]}


@router.get("/events")
def list_events(current_user=Depends(get_current_user)):
    with session() as conn:
        return [_event_out(r) for r in repo.list_events(conn, current_user["id"])]


class EventCreate(BaseModel):
    event_type: str
    label: str
    exam_key: str | None = None
    plan_type: str | None = None
    start_date: str
    end_date: str


@router.post("/events")
def create_event(req: EventCreate, current_user=Depends(get_current_user)):
    if req.event_type not in _VALID_TYPES:
        raise HTTPException(422, "event_type must be 'holiday' or 'exam'")
    if not req.label.strip():
        raise HTTPException(422, "label is required")
    if not _DATE_RE.match(req.start_date) or not _DATE_RE.match(req.end_date):
        raise HTTPException(422, "Dates must be in YYYY-MM-DD format")
    if req.end_date < req.start_date:
        raise HTTPException(422, "End date must be on or after the start date")
    exam_key = req.exam_key.strip().upper() if (req.event_type == "exam" and req.exam_key) else None
    if req.event_type == "exam" and not exam_key:
        raise HTTPException(422, "exam_key is required for an exam date (e.g. 'FA-2')")
    plan_type = req.plan_type.strip() if (req.event_type == "exam" and req.plan_type) else None
    with session() as conn:
        row = repo.create_event(conn, current_user["id"], req.event_type, req.label.strip(), exam_key, req.start_date, req.end_date, plan_type)
        return _event_out(row)


@router.delete("/events/{event_id}")
def delete_event(event_id: int, current_user=Depends(get_current_user)):
    with session() as conn:
        if not repo.delete_event(conn, current_user["id"], event_id):
            raise HTTPException(404, "Calendar event not found")
    return {"ok": True}


# ---- Academic year ----


class AcademicYearUpdate(BaseModel):
    start_date: str
    end_date: str
    week_pattern: str


@router.put("/year")
def update_academic_year(req: AcademicYearUpdate, current_user=Depends(get_current_user)):
    if not _DATE_RE.match(req.start_date) or not _DATE_RE.match(req.end_date):
        raise HTTPException(422, "Dates must be in YYYY-MM-DD format")
    if req.end_date <= req.start_date:
        raise HTTPException(422, "End date must be after the start date")
    if req.week_pattern not in _VALID_WEEK_PATTERNS:
        raise HTTPException(422, "week_pattern must be '5-day' or '6-day'")
    with session() as conn:
        user_repo.set_academic_year(conn, current_user["id"], req.start_date, req.end_date, req.week_pattern)
        return repo.get_academic_year(conn, current_user["id"])


# ---- Exam plan (type + how many this year) ----


class ExamPlanTypeCreate(BaseModel):
    name: str
    count_per_year: int = 1


@router.get("/exam-types")
def list_exam_types(current_user=Depends(get_current_user)):
    with session() as conn:
        return [_exam_type_out(r) for r in repo.list_exam_plan_types(conn, current_user["id"])]


@router.post("/exam-types")
def create_exam_type(req: ExamPlanTypeCreate, current_user=Depends(get_current_user)):
    if not req.name.strip():
        raise HTTPException(422, "name is required")
    if req.count_per_year < 1:
        raise HTTPException(422, "count_per_year must be at least 1")
    with session() as conn:
        row = repo.create_exam_plan_type(conn, current_user["id"], req.name.strip(), req.count_per_year)
        return _exam_type_out(row)


@router.delete("/exam-types/{plan_type_id}")
def delete_exam_type(plan_type_id: int, current_user=Depends(get_current_user)):
    with session() as conn:
        if not repo.delete_exam_plan_type(conn, current_user["id"], plan_type_id):
            raise HTTPException(404, "Exam type not found")
    return {"ok": True}


# ---- Overview: everything the Academic Calendar page needs in one call ----


def _real_hours_per_day(conn, account_id: int) -> float | None:
    """Only a REAL number if this school has actually set its school-day
    times in Dynamic Timetable — never the silent defaults
    get_school_config() would otherwise fill in, since presenting those as
    this school's real day length would be a guess dressed up as a fact
    (same rule this app applies to syllabus data and school photos)."""
    row = conn.execute("SELECT start_time, end_time, breaks FROM tt_school_config WHERE user_id = %s", (account_id,)).fetchone()
    if not row:
        return None

    start = datetime.strptime(row["start_time"], "%H:%M")
    end = datetime.strptime(row["end_time"], "%H:%M")
    total_minutes = (end - start).total_seconds() / 60
    for b in json.loads(row["breaks"]):
        total_minutes -= b.get("duration_minutes", 0)
    return max(total_minutes, 0) / 60


@router.get("/overview")
def get_overview(current_user=Depends(get_current_user)):
    with session() as conn:
        year = repo.get_academic_year(conn, current_user["id"])
        events = [_event_out(r) for r in repo.list_events(conn, current_user["id"])]
        exam_types = [_exam_type_out(r) for r in repo.list_exam_plan_types(conn, current_user["id"])]

        working_capacity = None
        if year["start_date"] and year["end_date"]:
            holidays = [e for e in events if e["event_type"] == "holiday"]
            hours_per_day = _real_hours_per_day(conn, current_user["id"])
            working_capacity = repo.compute_working_capacity(year["start_date"], year["end_date"], year["week_pattern"], holidays, hours_per_day)

    return {
        "academic_year": year,
        "events": events,
        "exam_types": exam_types,
        "working_capacity": working_capacity,
    }
