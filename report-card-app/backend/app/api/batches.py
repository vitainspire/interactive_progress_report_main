import hashlib
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.core.deps import get_current_user, get_current_user_from_header_or_query
from app.db import batches as repo
from app.db.database import session
from app.db.users import set_default_school_name
from app.integrations import sms, whatsapp
from app.integrations.google_sheets import GoogleSheetFetchError, fetch_google_sheet_as_xlsx
from app.integrations.phone import InvalidPhoneNumber, normalize_phone
from app.integrations.sharing import get_or_create_share_token, public_report_url
from app.parsing.sheet_parser import SheetParseError, parse_uploaded_file, parse_workbook_file
from app.reports.card_render import render_report_page
from app.reports.class_stats import compute_class_stats

router = APIRouter(prefix="/batches", tags=["batches"])


def _batch_out(row, student_count: int | None = None) -> dict:
    exam_defs = json.loads(row["exam_order"])
    return {
        "id": row["id"],
        "name": row["name"],
        "school_name": row["school_name"],
        "fa_total": row["fa_total"],
        "sa_total": row["sa_total"],
        "fa_marks_per_subject": row["fa_marks_per_subject"],
        "sa_marks_per_subject": row["sa_marks_per_subject"],
        "class_strength_override": row["class_strength_override"],
        "source_filename": row["source_filename"],
        "exam_codes": [e["key"] for e in exam_defs],
        "created_at": row["created_at"],
        "student_count": student_count if student_count is not None else (row["student_count"] if "student_count" in row.keys() else None),
    }


@router.post("/upload")
async def upload_batch(
    file: UploadFile | None = File(None),
    sheet_url: str | None = Form(None),
    name: str | None = Form(None),
    school_name: str | None = Form(None),
    current_user=Depends(get_current_user),
):
    has_file = file is not None and bool(file.filename)
    has_link = bool(sheet_url and sheet_url.strip())
    if not has_file and not has_link:
        raise HTTPException(422, "Choose a file or paste a Google Sheets link")
    if has_file and has_link:
        raise HTTPException(422, "Choose either a file or a Google Sheets link, not both")

    if has_file:
        assert file is not None
        if not file.filename.lower().endswith((".xlsx", ".csv")):
            raise HTTPException(422, "Only .xlsx and .csv files are supported")
        raw = await file.read()
        source_label = file.filename
        try:
            parsed = parse_uploaded_file(file.filename, raw)
        except SheetParseError as exc:
            raise HTTPException(422, str(exc))
        except Exception:
            raise HTTPException(422, "Could not read this file — make sure it's a valid Excel workbook or CSV export of the same layout.")
    else:
        assert sheet_url is not None
        try:
            raw = await run_in_threadpool(fetch_google_sheet_as_xlsx, sheet_url.strip())
        except GoogleSheetFetchError as exc:
            raise HTTPException(422, str(exc))
        source_label = "Google Sheet"
        try:
            parsed = parse_workbook_file(io.BytesIO(raw))
        except SheetParseError as exc:
            raise HTTPException(422, str(exc))
        except Exception:
            raise HTTPException(422, "Could not read that Google Sheet — check that it follows the expected layout.")

    effective_school_name = (school_name or "").strip() or current_user["default_school_name"] or ""
    default_name = source_label.rsplit(".", 1)[0] if has_file else "Google Sheet import"
    batch_name = (name or "").strip() or default_name

    with session() as conn:
        if school_name and school_name.strip():
            set_default_school_name(conn, current_user["id"], school_name.strip())
        batch_id = repo.create_batch(conn, current_user["id"], batch_name, effective_school_name, source_label, parsed)
        if has_link:
            # Recorded once, here, so the background poller (sheet_sync.py)
            # picks this batch up on its very next cycle — and so its first
            # comparison is against the content as of right now, not a
            # blank slate that would look like a "change" immediately.
            assert sheet_url is not None
            repo.set_batch_sheet_source(conn, batch_id, sheet_url.strip(), hashlib.sha256(raw).hexdigest())
        row = repo.get_batch(conn, current_user["id"], batch_id)
        return _batch_out(row, student_count=len(parsed["students"]))


@router.get("")
def list_batches(current_user=Depends(get_current_user)):
    with session() as conn:
        rows = repo.list_batches(conn, current_user["id"])
        return [_batch_out(r) for r in rows]


@router.get("/{batch_id}")
def get_batch(batch_id: int, current_user=Depends(get_current_user)):
    with session() as conn:
        row = repo.get_batch(conn, current_user["id"], batch_id)
        if not row:
            raise HTTPException(404, "Batch not found")
        students = repo.list_students_brief(conn, batch_id)
        out = _batch_out(row, student_count=len(students))
        out["students"] = [{"id": s["id"], "name": s["name"], "section": s["section"], "roll_no": s["roll_no"], "phone": s["phone"]} for s in students]
        return out


@router.get("/{batch_id}/stats")
def get_batch_stats(batch_id: int, exam: str | None = None, current_user=Depends(get_current_user)):
    with session() as conn:
        row = repo.get_batch(conn, current_user["id"], batch_id)
        if not row:
            raise HTTPException(404, "Batch not found")
        all_students = repo.load_batch_students(conn, batch_id)
        settings = repo.settings_from_row(row)
        return compute_class_stats(all_students, json.loads(row["exam_order"]), settings, selected_exam=exam)


class SettingsUpdate(BaseModel):
    name: str | None = None
    school_name: str | None = None
    fa_total: float | None = None
    sa_total: float | None = None
    fa_marks_per_subject: float | None = None
    sa_marks_per_subject: float | None = None
    class_strength_override: int | None = None
    clear_class_strength_override: bool = False


@router.put("/{batch_id}/settings")
def update_settings(batch_id: int, req: SettingsUpdate, current_user=Depends(get_current_user)):
    with session() as conn:
        row = repo.get_batch(conn, current_user["id"], batch_id)
        if not row:
            raise HTTPException(404, "Batch not found")
        fields = req.model_dump(exclude_unset=True, exclude={"clear_class_strength_override"})
        if req.clear_class_strength_override:
            fields["class_strength_override"] = None
        repo.update_batch_settings(conn, batch_id, fields)
        row = repo.get_batch(conn, current_user["id"], batch_id)
        students = repo.list_students_brief(conn, batch_id)
        return _batch_out(row, student_count=len(students))


@router.delete("/{batch_id}")
def delete_batch(batch_id: int, current_user=Depends(get_current_user)):
    with session() as conn:
        if not repo.delete_batch(conn, current_user["id"], batch_id):
            raise HTTPException(404, "Batch not found")
    return {"ok": True}


@router.get("/{batch_id}/report", response_class=HTMLResponse)
def get_report(batch_id: int, ids: str | None = None, current_user=Depends(get_current_user_from_header_or_query)):
    with session() as conn:
        row = repo.get_batch(conn, current_user["id"], batch_id)
        if not row:
            raise HTTPException(404, "Batch not found")
        all_students = repo.load_batch_students(conn, batch_id)
        if not all_students:
            raise HTTPException(404, "This batch has no students")
        if ids:
            try:
                wanted = {int(x) for x in ids.split(",") if x.strip()}
            except ValueError:
                raise HTTPException(422, "Invalid student id list")
            selected = [s for s in all_students if s["id"] in wanted]
        else:
            selected = all_students
        settings = repo.settings_from_row(row)
        html = render_report_page(selected, all_students, json.loads(row["exam_order"]), settings, row["school_name"], title=row["name"])
        return HTMLResponse(content=html)


class SendReportsRequest(BaseModel):
    student_ids: list[int] | None = None  # None = every student in the batch


def _log_send(conn, student_id: int, channel: str, status: str, detail: str) -> None:
    conn.execute(
        "INSERT INTO send_log (student_id, channel, status, detail, created_at) VALUES (%s, %s, %s, %s, %s)",
        (student_id, channel, status, detail, datetime.now(timezone.utc).isoformat()),
    )


def _send_one(conn, student_row) -> dict:
    student_id = student_row["id"]
    name = student_row["name"]
    out = {"student_id": student_id, "name": name, "report_url": None}

    raw_phone = (student_row["phone"] or "").strip()
    if not raw_phone:
        detail = "No phone number on file for this student."
        _log_send(conn, student_id, "none", "skipped", detail)
        return {**out, "channel": "none", "status": "skipped", "detail": detail}

    try:
        phone = normalize_phone(raw_phone)
    except InvalidPhoneNumber as exc:
        _log_send(conn, student_id, "none", "skipped", str(exc))
        return {**out, "channel": "none", "status": "skipped", "detail": str(exc)}

    token = get_or_create_share_token(conn, student_id)
    report_url = public_report_url(token)
    out = {**out, "report_url": report_url}

    whatsapp_error: str | None = None
    if whatsapp.is_configured():
        try:
            whatsapp.send_report_whatsapp(phone, name, token)
            _log_send(conn, student_id, "whatsapp", "sent", "")
            return {**out, "channel": "whatsapp", "status": "sent", "detail": ""}
        except whatsapp.WhatsAppSendError as exc:
            whatsapp_error = str(exc)
    else:
        whatsapp_error = "WhatsApp isn't configured on this server."

    if sms.is_configured():
        try:
            sms.send_report_sms(phone, name, report_url)
            detail = f"WhatsApp failed first ({whatsapp_error}); sent via SMS instead." if whatsapp.is_configured() else ""
            _log_send(conn, student_id, "sms", "sent", detail)
            return {**out, "channel": "sms", "status": "sent", "detail": detail}
        except sms.SmsSendError as exc:
            detail = f"WhatsApp: {whatsapp_error} | SMS: {exc}"
            _log_send(conn, student_id, "sms", "failed", detail)
            return {**out, "channel": "sms", "status": "failed", "detail": detail}

    detail = f"{whatsapp_error} SMS isn't configured on this server either."
    _log_send(conn, student_id, "none", "failed", detail)
    return {**out, "channel": "none", "status": "failed", "detail": detail}


@router.post("/{batch_id}/send-reports")
def send_reports(batch_id: int, req: SendReportsRequest, current_user=Depends(get_current_user)):
    """Sends each selected student's parent-safe report link over WhatsApp,
    falling back to SMS if WhatsApp isn't configured or that specific send
    fails. Returns a per-student outcome — there is no single overall
    pass/fail, since some students may have no phone on file."""
    with session() as conn:
        batch_row = repo.get_batch(conn, current_user["id"], batch_id)
        if not batch_row:
            raise HTTPException(404, "Batch not found")
        student_rows = repo.list_students_brief(conn, batch_id)
        if req.student_ids is not None:
            wanted = set(req.student_ids)
            student_rows = [s for s in student_rows if s["id"] in wanted]
        if not student_rows:
            raise HTTPException(422, "No students selected")

        results = [_send_one(conn, s) for s in student_rows]
        return {"results": results}
