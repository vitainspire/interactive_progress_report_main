import json
import re
from datetime import date as date_cls
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.core.deps import get_current_user, get_current_user_from_header_or_query
from app.db import timetable as repo
from app.db.database import session
from app.integrations import sms
from app.integrations.phone import InvalidPhoneNumber, normalize_phone
from app.reports.substitution_sheet import render_substitution_sheet
from app.reports.timetable_print import render_class_timetable_print
from app.timetable.generator import ClassSpec, SubjectRequirement, generate_timetable

router = APIRouter(prefix="/timetable", tags=["timetable"])

_VALID_DAYS = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}


def _class_out(row: dict) -> dict:
    return {"id": row["id"], "grade": row["grade"], "section": row["section"]}


def _subject_out(row: dict) -> dict:
    return {"id": row["id"], "name": row["name"], "code": row["code"], "excluded_periods": json.loads(row["excluded_periods"])}


def _teacher_out(row: dict, subject_ids: list[int] | None = None) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "code": row["code"],
        "phone": row["phone"],
        "max_periods_per_day": row["max_periods_per_day"],
        "subject_ids": subject_ids if subject_ids is not None else [],
    }


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


class SubjectExcludedPeriodsUpdate(BaseModel):
    excluded_periods: list[int]


@router.put("/subjects/{subject_id}/excluded-periods")
def update_subject_excluded_periods(subject_id: int, req: SubjectExcludedPeriodsUpdate, current_user=Depends(get_current_user)):
    with session() as conn:
        row = repo.get_subject(conn, current_user["id"], subject_id)
        if not row:
            raise HTTPException(404, "Subject not found")
        periods = sorted({p for p in req.excluded_periods if p >= 1})
        repo.set_subject_excluded_periods(conn, subject_id, periods)
        return _subject_out(repo.get_subject(conn, current_user["id"], subject_id))


# ---- Teachers ----


class TeacherCreate(BaseModel):
    name: str
    code: str = ""
    phone: str = ""
    max_periods_per_day: int | None = None
    subject_ids: list[int] = []


class TeacherUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    phone: str | None = None
    max_periods_per_day: int | None = None


class TeacherSubjectsUpdate(BaseModel):
    subject_ids: list[int]


def _validate_subject_ids(conn, user_id: int, subject_ids: list[int]) -> list[int]:
    unique_ids = list(dict.fromkeys(subject_ids))  # de-dupe, keep order
    for sid in unique_ids:
        if not repo.get_subject(conn, user_id, sid):
            raise HTTPException(404, f"Subject {sid} not found")
    return unique_ids


def _normalize_optional_phone(phone: str) -> str:
    phone = phone.strip()
    if not phone:
        return ""
    try:
        return normalize_phone(phone)
    except InvalidPhoneNumber as exc:
        raise HTTPException(422, str(exc))


@router.get("/teachers")
def list_teachers(current_user=Depends(get_current_user)):
    with session() as conn:
        subject_ids_by_teacher = repo.subject_ids_by_teacher(conn, current_user["id"])
        return [_teacher_out(r, subject_ids_by_teacher.get(r["id"], [])) for r in repo.list_teachers(conn, current_user["id"])]


@router.post("/teachers")
def create_teacher(req: TeacherCreate, current_user=Depends(get_current_user)):
    name = req.name.strip()
    if not name:
        raise HTTPException(422, "Teacher name is required")
    phone = _normalize_optional_phone(req.phone)
    with session() as conn:
        subject_ids = _validate_subject_ids(conn, current_user["id"], req.subject_ids)
        teacher_id = repo.create_teacher(conn, current_user["id"], name, req.code.strip(), req.max_periods_per_day, phone)
        if subject_ids:
            repo.set_teacher_subjects(conn, teacher_id, subject_ids)
        return _teacher_out(repo.get_teacher(conn, current_user["id"], teacher_id), subject_ids)


@router.put("/teachers/{teacher_id}")
def update_teacher(teacher_id: int, req: TeacherUpdate, current_user=Depends(get_current_user)):
    with session() as conn:
        if not repo.get_teacher(conn, current_user["id"], teacher_id):
            raise HTTPException(404, "Teacher not found")
        fields = req.model_dump(exclude_unset=True)
        if "name" in fields:
            fields["name"] = fields["name"].strip() or None
            if fields["name"] is None:
                raise HTTPException(422, "Teacher name is required")
        if "code" in fields:
            fields["code"] = fields["code"].strip()
        if "phone" in fields:
            fields["phone"] = _normalize_optional_phone(fields["phone"])
        repo.update_teacher(conn, teacher_id, fields)
        subject_ids_by_teacher = repo.subject_ids_by_teacher(conn, current_user["id"])
        return _teacher_out(repo.get_teacher(conn, current_user["id"], teacher_id), subject_ids_by_teacher.get(teacher_id, []))


@router.delete("/teachers/{teacher_id}")
def delete_teacher(teacher_id: int, current_user=Depends(get_current_user)):
    with session() as conn:
        if not repo.delete_teacher(conn, current_user["id"], teacher_id):
            raise HTTPException(404, "Teacher not found")
    return {"ok": True}


@router.get("/teachers/{teacher_id}/timetable")
def get_teacher_timetable(teacher_id: int, current_user=Depends(get_current_user)):
    with session() as conn:
        if not repo.get_teacher(conn, current_user["id"], teacher_id):
            raise HTTPException(404, "Teacher not found")
        rows = repo.get_teacher_timetable(conn, current_user["id"], teacher_id)
        return [
            {
                "day": r["day"],
                "period": r["period"],
                "class_id": r["class_id"],
                "class_name": f'{r["grade"]} {r["section"]}'.strip(),
                "subject_id": r["subject_id"],
                "subject_name": r["subject_name"],
                "subject_code": r["subject_code"],
            }
            for r in rows
        ]


@router.put("/teachers/{teacher_id}/subjects")
def update_teacher_subjects(teacher_id: int, req: TeacherSubjectsUpdate, current_user=Depends(get_current_user)):
    with session() as conn:
        teacher_row = repo.get_teacher(conn, current_user["id"], teacher_id)
        if not teacher_row:
            raise HTTPException(404, "Teacher not found")
        subject_ids = _validate_subject_ids(conn, current_user["id"], req.subject_ids)
        repo.set_teacher_subjects(conn, teacher_id, subject_ids)
        return _teacher_out(teacher_row, subject_ids)


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


@router.get("/status")
def get_status(current_user=Depends(get_current_user)):
    """Whether this account has ever generated a timetable — the signal
    the frontend uses to decide between the first-time setup wizard and
    the day-to-day Timetable/Leave view."""
    with session() as conn:
        return {"has_timetable": repo.has_generated_timetable(conn, current_user["id"])}


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


# ---- Generated timetable ----


@router.post("/generate")
def generate(current_user=Depends(get_current_user)):
    with session() as conn:
        class_data = repo.list_all_class_subjects_for_generation(conn, current_user["id"])
        config = repo.get_school_config(conn, current_user["id"])

        classes = [
            ClassSpec(
                class_id=c["class_id"],
                class_name=c["class_name"],
                subjects=[
                    SubjectRequirement(
                        subject_id=s["subject_id"],
                        subject_name=s["subject_name"],
                        teacher_id=s["teacher_id"],
                        teacher_name=s["teacher_name"],
                        periods_per_week=s["periods_per_week"],
                        excluded_periods=json.loads(s["excluded_periods"]),
                    )
                    for s in c["subjects"]
                ],
            )
            for c in class_data
        ]

        total_requirements = sum(req.periods_per_week for c in classes for req in c.subjects)
        if not classes or total_requirements == 0:
            raise HTTPException(422, "Add classes, subjects, and periods/week under Assignments before generating a timetable")

        entries, issues = generate_timetable(classes, config["working_days"], config["periods_per_day"])

        rows = [(e.class_id, e.day, e.period, e.subject_id, e.teacher_id) for e in entries]
        repo.replace_timetable_entries(conn, current_user["id"], rows)

        return {
            "ok": not issues,
            "classes_generated": len({e.class_id for e in entries}),
            "total_periods_placed": len(entries),
            "issues": [{"class_name": i.class_name, "subject_name": i.subject_name, "reason": i.reason} for i in issues],
        }


@router.get("/classes/{class_id}/timetable")
def get_class_timetable(class_id: int, current_user=Depends(get_current_user)):
    with session() as conn:
        if not repo.get_class(conn, current_user["id"], class_id):
            raise HTTPException(404, "Class not found")
        rows = repo.get_timetable_entries(conn, class_id)
        return [
            {
                "day": r["day"],
                "period": r["period"],
                "subject_id": r["subject_id"],
                "subject_name": r["subject_name"],
                "subject_code": r["subject_code"],
                "teacher_id": r["teacher_id"],
                "teacher_name": r["teacher_name"],
                "teacher_code": r["teacher_code"],
            }
            for r in rows
        ]


class TimetableEntryUpdate(BaseModel):
    subject_id: int
    teacher_id: int | None = None


@router.put("/classes/{class_id}/timetable/{day}/{period}")
def update_timetable_entry(class_id: int, day: str, period: int, req: TimetableEntryUpdate, current_user=Depends(get_current_user)):
    _validate_day_period(day, period)
    with session() as conn:
        if not repo.get_class(conn, current_user["id"], class_id):
            raise HTTPException(404, "Class not found")
        if not repo.get_subject(conn, current_user["id"], req.subject_id):
            raise HTTPException(404, "Subject not found")
        class_subjects = repo.list_class_subjects(conn, class_id)
        if not any(cs["subject_id"] == req.subject_id for cs in class_subjects):
            raise HTTPException(422, "This subject isn't assigned to this class — add it under Assignments first")
        if req.teacher_id is not None:
            teacher = repo.get_teacher(conn, current_user["id"], req.teacher_id)
            if not teacher:
                raise HTTPException(404, "Teacher not found")
            conflict = repo.is_teacher_busy_elsewhere(conn, current_user["id"], req.teacher_id, day, period, class_id)
            if conflict:
                class_label = f'Grade {conflict["grade"]} · {conflict["section"]}' if conflict["section"] else f'Grade {conflict["grade"]}'
                raise HTTPException(422, f"{teacher['name']} already teaches {class_label} at this exact period")
        repo.set_timetable_entry(conn, class_id, day, period, req.subject_id, req.teacher_id)
        entry = repo.get_timetable_entry(conn, class_id, day, period)
        return {
            "day": day,
            "period": period,
            "subject_id": entry["subject_id"],
            "subject_name": entry["subject_name"],
            "teacher_id": entry["teacher_id"],
            "teacher_name": entry["teacher_name"],
            "teacher_code": entry["teacher_code"],
        }


@router.get("/classes/{class_id}/timetable/print", response_class=HTMLResponse)
def print_class_timetable(class_id: int, current_user=Depends(get_current_user_from_header_or_query)):
    with session() as conn:
        row = repo.get_class(conn, current_user["id"], class_id)
        if not row:
            raise HTTPException(404, "Class not found")
        entries = repo.get_timetable_entries(conn, class_id)
        config = repo.get_school_config(conn, current_user["id"])
        class_label = f'Grade {row["grade"]} · {row["section"]}' if row["section"] else f'Grade {row["grade"]}'
        html_out = render_class_timetable_print(current_user["default_school_name"] or "School Timetable", class_label, config, entries)
        return HTMLResponse(content=html_out)


# ---- Substitutions ----

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _candidate_out(c: dict) -> dict:
    return {"teacher_id": c["teacher_id"], "teacher_name": c["teacher_name"], "teacher_code": c["teacher_code"], "reason": c["reason"]}


def _validate_day_period(day: str, period: int):
    if day not in _VALID_DAYS:
        raise HTTPException(422, "Invalid day")
    if period < 1:
        raise HTTPException(422, "Invalid period")


@router.get("/classes/{class_id}/substitutes")
def get_substitutes(class_id: int, day: str, period: int, date: str, current_user=Depends(get_current_user)):
    _validate_day_period(day, period)
    if not _DATE_RE.match(date):
        raise HTTPException(422, "date must be in YYYY-MM-DD format")
    with session() as conn:
        if not repo.get_class(conn, current_user["id"], class_id):
            raise HTTPException(404, "Class not found")
        entry = repo.get_timetable_entry(conn, class_id, day, period)
        if not entry:
            raise HTTPException(404, "No class scheduled for this day/period")
        candidates = repo.find_substitute_candidates(conn, current_user["id"], class_id, day, period, date, entry["teacher_id"])
        return {
            "original": {
                "subject_id": entry["subject_id"],
                "subject_name": entry["subject_name"],
                "teacher_id": entry["teacher_id"],
                "teacher_name": entry["teacher_name"],
            },
            "candidates": [_candidate_out(c) for c in candidates],
        }


class SubstitutionCreate(BaseModel):
    date: str
    day: str
    period: int
    substitute_teacher_id: int


def _class_label(row: dict) -> str:
    return f'Grade {row["grade"]} · {row["section"]}' if row["section"] else f'Grade {row["grade"]}'


def _notify_substitute(current_user: dict, class_row: dict, entry: dict, date: str, substitute: dict) -> str:
    """Best-effort SMS to the substitute — never raises, since a failed
    notification shouldn't undo an otherwise-successful assignment. SMS
    only (not WhatsApp): the WhatsApp Cloud API requires a pre-approved
    message template per message shape, which this app doesn't have for
    substitution alerts — see app/integrations/whatsapp.py."""
    if not substitute["phone"]:
        return "not_sent_no_phone"
    if not sms.is_configured():
        return "not_sent_sms_unconfigured"
    try:
        phone = normalize_phone(substitute["phone"])
    except InvalidPhoneNumber:
        return "not_sent_invalid_phone"
    school = current_user["default_school_name"] or "your school"
    body = (
        f"{school}: you're covering {_class_label(class_row)}'s {entry['subject_name']} "
        f"(period {entry.get('period', '')}) on {date} for {entry['teacher_name'] or 'the regular teacher'}."
    )
    try:
        sms.send_plain_sms(phone, body)
        return "sent"
    except sms.SmsSendError:
        return "failed"


@router.post("/classes/{class_id}/substitutions")
def create_substitution(class_id: int, req: SubstitutionCreate, current_user=Depends(get_current_user)):
    _validate_day_period(req.day, req.period)
    if not _DATE_RE.match(req.date):
        raise HTTPException(422, "date must be in YYYY-MM-DD format")
    with session() as conn:
        class_row = repo.get_class(conn, current_user["id"], class_id)
        if not class_row:
            raise HTTPException(404, "Class not found")
        entry = repo.get_timetable_entry(conn, class_id, req.day, req.period)
        if not entry:
            raise HTTPException(404, "No class scheduled for this day/period")
        substitute = repo.get_teacher(conn, current_user["id"], req.substitute_teacher_id)
        if not substitute:
            raise HTTPException(404, "Substitute teacher not found")
        if req.substitute_teacher_id == entry["teacher_id"]:
            raise HTTPException(422, "A teacher can't substitute for their own class")
        if repo.teacher_is_busy_at_slot(conn, current_user["id"], req.substitute_teacher_id, req.day, req.period, req.date, class_id):
            raise HTTPException(409, f"{substitute['name']} is already teaching or covering another class at that exact day and period")
        repo.create_or_update_substitution(
            conn, class_id, req.date, req.day, req.period, entry["subject_id"], entry["teacher_id"], req.substitute_teacher_id
        )
        notify_status = _notify_substitute(current_user, class_row, {**entry, "period": req.period}, req.date, substitute)
        return {
            "date": req.date,
            "day": req.day,
            "period": req.period,
            "subject_id": entry["subject_id"],
            "subject_name": entry["subject_name"],
            "original_teacher_id": entry["teacher_id"],
            "original_teacher_name": entry["teacher_name"],
            "substitute_teacher_id": substitute["id"],
            "substitute_teacher_name": substitute["name"],
            "notify_status": notify_status,
        }


@router.get("/classes/{class_id}/substitutions")
def get_substitutions(class_id: int, date: str, current_user=Depends(get_current_user)):
    if not _DATE_RE.match(date):
        raise HTTPException(422, "date must be in YYYY-MM-DD format")
    with session() as conn:
        if not repo.get_class(conn, current_user["id"], class_id):
            raise HTTPException(404, "Class not found")
        rows = repo.list_substitutions(conn, class_id, date)
        return [
            {
                "day": r["day"],
                "period": r["period"],
                "subject_id": r["subject_id"],
                "subject_name": r["subject_name"],
                "original_teacher_id": r["original_teacher_id"],
                "original_teacher_name": r["original_teacher_name"],
                "substitute_teacher_id": r["substitute_teacher_id"],
                "substitute_teacher_name": r["substitute_teacher_name"],
            }
            for r in rows
        ]


@router.delete("/classes/{class_id}/substitutions")
def remove_substitution(class_id: int, date: str, period: int, current_user=Depends(get_current_user)):
    if not _DATE_RE.match(date):
        raise HTTPException(422, "date must be in YYYY-MM-DD format")
    with session() as conn:
        if not repo.get_class(conn, current_user["id"], class_id):
            raise HTTPException(404, "Class not found")
        if not repo.delete_substitution(conn, class_id, date, period):
            raise HTTPException(404, "No substitution found for this date/period")
    return {"ok": True}


@router.get("/substitutions/sheet", response_class=HTMLResponse)
def print_substitution_sheet(date: str, current_user=Depends(get_current_user_from_header_or_query)):
    """One printable page listing every confirmed substitution across the
    whole school for this date — for the staff noticeboard, not scoped
    to a single class like /classes/{id}/timetable/print."""
    if not _DATE_RE.match(date):
        raise HTTPException(422, "date must be in YYYY-MM-DD format")
    with session() as conn:
        rows = repo.list_substitutions_for_account(conn, current_user["id"], date)
        html_out = render_substitution_sheet(current_user["default_school_name"] or "School", date, rows)
        return HTMLResponse(content=html_out)


def _substitution_notify_out(r: dict, status: str) -> dict:
    return {
        "class_name": _class_label(r),
        "period": r["period"],
        "subject_name": r["subject_name"],
        "substitute_teacher_name": r["substitute_teacher_name"],
        "substitute_teacher_code": r["substitute_teacher_code"],
        "notify_status": status,
    }


@router.post("/substitutions/notify")
def notify_substitutes(date: str, current_user=Depends(get_current_user)):
    """(Re)sends the substitute-coverage SMS for every confirmed
    substitution on this date in one action — for when the automatic
    per-confirm send failed, wasn't configured yet at the time, or the
    admin just wants to be sure everyone's been told before the day
    starts."""
    if not _DATE_RE.match(date):
        raise HTTPException(422, "date must be in YYYY-MM-DD format")
    with session() as conn:
        rows = repo.list_substitutions_for_account(conn, current_user["id"], date)
        results = []
        for r in rows:
            class_row = {"grade": r["grade"], "section": r["section"]}
            entry = {"subject_name": r["subject_name"], "teacher_name": r["original_teacher_name"], "period": r["period"]}
            substitute = {"phone": r["substitute_teacher_phone"]}
            status = _notify_substitute(current_user, class_row, entry, date, substitute)
            results.append(_substitution_notify_out(r, status))
        return results


# ---- Planned leave ----

_WEEKDAY_CODES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
_MAX_LEAVE_DAYS = 31  # guards against an accidental 10-year range blowing up the pending-needs scan


def _leave_out(row: dict) -> dict:
    return {
        "id": row["id"],
        "teacher_id": row["teacher_id"],
        "teacher_name": row["teacher_name"],
        "teacher_code": row["teacher_code"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "reason": row["reason"],
    }


class LeaveCreate(BaseModel):
    teacher_id: int
    start_date: str
    end_date: str
    reason: str = ""


@router.get("/leaves")
def list_leaves(current_user=Depends(get_current_user)):
    with session() as conn:
        return [_leave_out(r) for r in repo.list_leaves(conn, current_user["id"])]


@router.post("/leaves")
def create_leave(req: LeaveCreate, current_user=Depends(get_current_user)):
    if not _DATE_RE.match(req.start_date) or not _DATE_RE.match(req.end_date):
        raise HTTPException(422, "Dates must be in YYYY-MM-DD format")
    if req.end_date < req.start_date:
        raise HTTPException(422, "End date must be on or after the start date")
    if (date_cls.fromisoformat(req.end_date) - date_cls.fromisoformat(req.start_date)).days + 1 > _MAX_LEAVE_DAYS:
        raise HTTPException(422, f"A single leave can span at most {_MAX_LEAVE_DAYS} days")
    with session() as conn:
        if not repo.get_teacher(conn, current_user["id"], req.teacher_id):
            raise HTTPException(404, "Teacher not found")
        leave_id = repo.create_leave(conn, req.teacher_id, req.start_date, req.end_date, req.reason.strip())
        return _leave_out(repo.get_leave(conn, leave_id))


@router.delete("/leaves/{leave_id}")
def delete_leave(leave_id: int, current_user=Depends(get_current_user)):
    with session() as conn:
        if not repo.delete_leave(conn, current_user["id"], leave_id):
            raise HTTPException(404, "Leave not found")
    return {"ok": True}


@router.get("/leaves/pending")
def get_pending_substitution_needs(current_user=Depends(get_current_user)):
    """Everything a planned leave will leave uncovered unless someone
    confirms a substitute — the review queue. Never assigns anyone by
    itself: each entry just carries the same ranked-candidate list the
    single-day absence flow uses, for the admin to confirm or override."""
    with session() as conn:
        leaves = repo.list_leaves(conn, current_user["id"])
        if not leaves:
            return []

        min_date = min(leave["start_date"] for leave in leaves)
        max_date = max(leave["end_date"] for leave in leaves)
        ctx = repo.pending_substitution_context(conn, current_user["id"], min_date, max_date)

        needs = []
        for leave in leaves:
            start = date_cls.fromisoformat(leave["start_date"])
            end = date_cls.fromisoformat(leave["end_date"])
            d = start
            while d <= end:
                date_str = d.isoformat()
                weekday = _WEEKDAY_CODES[d.weekday()]
                for entry in ctx["entries_by_teacher_day"].get((leave["teacher_id"], weekday), []):
                    if (entry["class_id"], date_str, entry["period"]) in ctx["existing_substitutions"]:
                        continue
                    busy = (
                        ctx["busy_by_day_period"].get((weekday, entry["period"]), set())
                        | ctx["busy_substituting_by_date_period"].get((date_str, entry["period"]), set())
                        | {leave["teacher_id"]}
                    )
                    candidates = repo.rank_candidates(
                        ctx["teachers"],
                        busy,
                        ctx["same_subject_by_subject"].get(entry["subject_id"], set()),
                        ctx["teachers_by_class"].get(entry["class_id"], set()),
                    )
                    class_label = f'Grade {entry["grade"]} · {entry["section"]}' if entry["section"] else f'Grade {entry["grade"]}'
                    needs.append(
                        {
                            "leave_id": leave["id"],
                            "teacher_id": leave["teacher_id"],
                            "teacher_name": leave["teacher_name"],
                            "date": date_str,
                            "day": weekday,
                            "period": entry["period"],
                            "class_id": entry["class_id"],
                            "class_name": class_label,
                            "subject_id": entry["subject_id"],
                            "subject_name": entry["subject_name"],
                            "candidates": [_candidate_out(c) for c in candidates],
                        }
                    )
                d += timedelta(days=1)
        needs.sort(key=lambda n: (n["date"], n["period"]))
        return needs
