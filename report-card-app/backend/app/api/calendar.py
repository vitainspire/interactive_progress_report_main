import re
from datetime import date as date_cls

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.db import calendar as repo
from app.db.database import session

router = APIRouter(prefix="/calendar", tags=["calendar"])

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_VALID_TYPES = {"holiday", "exam"}


def _event_out(row: dict) -> dict:
    return {
        "id": row["id"],
        "event_type": row["event_type"],
        "label": row["label"],
        "exam_key": row["exam_key"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
    }


@router.get("/events")
def list_events(current_user=Depends(get_current_user)):
    with session() as conn:
        return [_event_out(r) for r in repo.list_events(conn, current_user["id"])]


class EventCreate(BaseModel):
    event_type: str
    label: str
    exam_key: str | None = None
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
    with session() as conn:
        row = repo.create_event(conn, current_user["id"], req.event_type, req.label.strip(), exam_key, req.start_date, req.end_date)
        return _event_out(row)


@router.delete("/events/{event_id}")
def delete_event(event_id: int, current_user=Depends(get_current_user)):
    with session() as conn:
        if not repo.delete_event(conn, current_user["id"], event_id):
            raise HTTPException(404, "Calendar event not found")
    return {"ok": True}
