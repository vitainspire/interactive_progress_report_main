import io
import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from app.core.deps import get_current_user, get_current_user_from_header_or_query
from app.db import batches as repo
from app.db.database import session
from app.db.users import set_default_school_name
from app.integrations import sms, whatsapp
from app.db import reference_documents as refdocs_repo
from app.integrations.google_drive_folder import (
    GoogleDriveFetchError,
    extract_folder_id,
    fetch_drive_file_bytes,
    filename_for,
    list_folder_reference_files,
    list_folder_spreadsheet_files,
)
from app.integrations.google_sheets import GoogleSheetFetchError, fetch_google_sheet_as_xlsx
from app.integrations.phone import InvalidPhoneNumber, normalize_phone
from app.integrations.sharing import get_or_create_share_token, public_report_url
from app.integrations.syllabus_extraction import ExtractionError, ExtractionNotConfigured, extract_document
from app.parsing.sheet_parser import SheetParseError, parse_uploaded_file, parse_workbook_file
from app.reports.card_render import render_report_page
from app.reports.class_stats import compute_class_stats
from app.reports.student_analytics import build_student_analytics
from app.reports.subject_analysis import discover_subjects, render_subject_analysis
from app.reports.upload_template import build_upload_template

router = APIRouter(prefix="/batches", tags=["batches"])


@router.get("/upload-template")
def download_upload_template():
    """A ready-made .xlsx matching the exact layout parse_uploaded_file
    expects, with two sample students already filled in — for a school
    confused by (or about to hit) a SheetParseError on their own sheet.
    No auth: it's a generic example with no real data in it, and a
    confused admin shouldn't need to be logged in just to see the expected
    shape. Registered before any /{batch_id} route in this file so it can
    never be shadowed by a dynamic path."""
    data = build_upload_template()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="report_card_upload_template.xlsx"'},
    )

# Classes with a syllabus actually seeded (see app/db/syllabus_seed.py) —
# an unrecognized value just falls back to "10" rather than erroring, since
# a wrong class_level only means the study-plan feature won't find a match,
# never a broken upload.
_KNOWN_CLASS_LEVELS = {"6", "7", "8", "9", "10"}


def _normalize_class_level(value: str | None) -> str:
    v = (value or "").strip()
    return v if v in _KNOWN_CLASS_LEVELS else "10"


# A class number in a filename, optionally with an ordinal suffix — "Grade
# 7.xlsx", "9th Class.xlsx", "10-A.xlsx", "6B Section.xlsx" all match.
# Lookaround keeps it from matching inside an unrelated bigger number like
# "Batch16.xlsx" or a year like "2024".
_CLASS_LEVEL_IN_FILENAME_RE = re.compile(r"(?<![0-9])(10|[6-9])(?:st|nd|rd|th)?(?![0-9])", re.IGNORECASE)


def _guess_class_level_from_filename(filename: str) -> str | None:
    """Best-effort class detection for a Drive-folder import, so a folder
    of per-class files ("Grade 6.xlsx", "Grade 7.xlsx", ...) doesn't need
    every file tagged with the same class by hand. Returns None when
    nothing in the name looks like a class number — the caller falls back
    to whatever class was picked in the upload form."""
    m = _CLASS_LEVEL_IN_FILENAME_RE.search(filename)
    return m.group(1) if m else None


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
        "class_level": row["class_level"],
        "source_filename": row["source_filename"],
        "source_type": row["source_type"],
        "source_folder_id": row["source_folder_id"],
        "last_synced_at": row["last_synced_at"],
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
    class_level: str | None = Form(None),
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
        batch_id = repo.create_batch(
            conn,
            current_user["id"],
            batch_name,
            effective_school_name,
            source_label,
            parsed,
            _normalize_class_level(class_level),
            source_type="sheet_link" if has_link else "file",
            source_ref=sheet_url.strip() if has_link else None,
        )
        row = repo.get_batch(conn, current_user["id"], batch_id)
        return _batch_out(row, student_count=len(parsed["students"]))


class ImportFolderRequest(BaseModel):
    folder_url: str
    school_name: str | None = None
    class_level: str | None = None


async def _ingest_reference_documents(account_id: int, folder_url_or_id: str) -> list[dict]:
    """Picks up any PDF/image reference document (syllabus or exam
    blueprint) sitting in the same Drive folder as the class mark sheets,
    runs it through the document-extraction LLM, and stores it as a
    *pending* subject_reference_document row for a teacher to review (see
    app/api/reference_documents.py) — never written into the live
    syllabus_chapter/subject_blueprint tables directly. A bad or
    unreadable document is recorded with status 'failed' rather than
    aborting the rest of the import, same error-isolation style as the
    spreadsheet-file loop above."""
    try:
        files = await run_in_threadpool(list_folder_reference_files, folder_url_or_id)
    except GoogleDriveFetchError:
        return []  # optional step — a folder-access problem is already surfaced by the spreadsheet fetch above

    results = []
    for f in files:
        with session() as conn:
            already = refdocs_repo.get_reference_document_by_drive_file_id(conn, account_id, f["id"])
        if already and already["status"] != "failed":
            continue  # already ingested (or already pending review) from a prior import/sync of this folder

        try:
            raw = await run_in_threadpool(fetch_drive_file_bytes, f["id"], f["mime_type"])
        except GoogleDriveFetchError as exc:
            results.append({"file_name": f["name"], "status": "failed", "error": str(exc)})
            continue

        status, extracted_json, error = "pending", None, None
        try:
            extracted = await run_in_threadpool(extract_document, raw, f["mime_type"], f["name"])
            extracted_json = json.dumps(extracted)
        except (ExtractionNotConfigured, ExtractionError) as exc:
            status, error = "failed", str(exc)

        with session() as conn:
            doc_id = refdocs_repo.create_reference_document(
                conn, account_id, f["name"], f["mime_type"], raw, f["id"], status, extracted_json, error
            )
        results.append({"file_name": f["name"], "status": status, "reference_document_id": doc_id})
    return results


def _duplicate_out(f: dict, dup: dict, folder_id: str | None, new_student_count: int) -> dict:
    """A file whose roster looks like an already-imported class (see
    repo.find_duplicate_candidate) — carries everything the frontend needs
    to either re-fetch and fold it into that class or force-create it as a
    separate one, via POST /batches/resolve-drive-duplicate, without this
    account having to re-paste the folder link."""
    return {
        "file_name": f["name"],
        "status": "possible_duplicate",
        "file_id": f["id"],
        "mime_type": f["mime_type"],
        "folder_id": folder_id,
        "candidate_batch_id": dup["id"],
        "candidate_batch_name": dup["name"],
        "overlap_count": dup["overlap_count"],
        "existing_student_count": dup["existing_student_count"],
        "new_student_count": new_student_count,
    }


@router.post("/import-folder")
async def import_drive_folder(req: ImportFolderRequest, current_user=Depends(get_current_user)):
    """One batch per spreadsheet file found directly inside a publicly-
    shared Drive folder — e.g. a school keeps "Grade 6.xlsx", "Grade
    7.xlsx", etc. in one folder and imports all of them in one go. A
    failure on one file (bad layout, deleted mid-import) is reported per
    file rather than aborting the whole import."""
    try:
        files = await run_in_threadpool(list_folder_spreadsheet_files, req.folder_url.strip())
    except GoogleDriveFetchError as exc:
        raise HTTPException(422, str(exc))

    folder_id = extract_folder_id(req.folder_url)
    effective_school_name = (req.school_name or "").strip() or current_user["default_school_name"] or ""
    fallback_class_level = _normalize_class_level(req.class_level)

    if req.school_name and req.school_name.strip():
        with session() as conn:
            set_default_school_name(conn, current_user["id"], req.school_name.strip())

    results = []
    for f in files:
        try:
            raw = await run_in_threadpool(fetch_drive_file_bytes, f["id"], f["mime_type"])
            parsed = parse_uploaded_file(filename_for(f["name"], f["mime_type"]), raw)
        except (GoogleDriveFetchError, SheetParseError) as exc:
            results.append({"file_name": f["name"], "status": "failed", "error": str(exc)})
            continue
        except Exception:
            results.append({"file_name": f["name"], "status": "failed", "error": "Could not read this file — check it follows the expected layout."})
            continue

        with session() as conn:
            dup = repo.find_duplicate_candidate(conn, current_user["id"], parsed["students"])
        if dup:
            results.append(_duplicate_out(f, dup, folder_id, len(parsed["students"])))
            continue

        batch_name = f["name"].rsplit(".", 1)[0]
        class_level = _guess_class_level_from_filename(f["name"]) or fallback_class_level
        with session() as conn:
            batch_id = repo.create_batch(
                conn,
                current_user["id"],
                batch_name,
                effective_school_name,
                f["name"],
                parsed,
                class_level,
                source_type="drive_folder_item",
                source_ref=f["id"],
                source_mime_type=f["mime_type"],
                source_folder_id=folder_id,
            )
        results.append({"file_name": f["name"], "status": "created", "batch_id": batch_id, "student_count": len(parsed["students"])})

    reference_results = await _ingest_reference_documents(current_user["id"], req.folder_url.strip())
    return {"folder_id": folder_id, "results": results, "reference_documents": reference_results}


class SyncFolderRequest(BaseModel):
    folder_id: str


@router.post("/sync-folder")
async def sync_drive_folder(req: SyncFolderRequest, current_user=Depends(get_current_user)):
    """Re-syncs every batch previously imported from one Drive folder, and
    also picks up any class file added to the folder since the last
    import. A file removed from the folder isn't deleted automatically —
    its batch is left alone and listed under `missing_batches` so you can
    decide whether to remove it yourself."""
    with session() as conn:
        existing_batches = repo.list_batches_by_folder(conn, current_user["id"], req.folder_id)
    if not existing_batches:
        raise HTTPException(404, "No batches were imported from that folder yet.")
    by_file_id = {b["source_ref"]: b for b in existing_batches}

    try:
        files = await run_in_threadpool(list_folder_spreadsheet_files, req.folder_id)
    except GoogleDriveFetchError as exc:
        raise HTTPException(422, str(exc))

    results = []
    seen_file_ids = set()
    for f in files:
        seen_file_ids.add(f["id"])
        try:
            raw = await run_in_threadpool(fetch_drive_file_bytes, f["id"], f["mime_type"])
            parsed = parse_uploaded_file(filename_for(f["name"], f["mime_type"]), raw)
        except (GoogleDriveFetchError, SheetParseError) as exc:
            results.append({"file_name": f["name"], "status": "failed", "error": str(exc)})
            continue
        except Exception:
            results.append({"file_name": f["name"], "status": "failed", "error": "Could not read this file."})
            continue

        existing = by_file_id.get(f["id"])
        if existing:
            with session() as conn:
                sync_result = repo.resync_batch(conn, existing["id"], parsed)
            results.append({"file_name": f["name"], "status": "synced", "batch_id": existing["id"], **sync_result})
            continue

        with session() as conn:
            dup = repo.find_duplicate_candidate(conn, current_user["id"], parsed["students"])
        if dup:
            results.append(_duplicate_out(f, dup, req.folder_id, len(parsed["students"])))
            continue

        with session() as conn:
            batch_id = repo.create_batch(
                conn,
                current_user["id"],
                f["name"].rsplit(".", 1)[0],
                existing_batches[0]["school_name"],
                f["name"],
                parsed,
                _guess_class_level_from_filename(f["name"]) or existing_batches[0]["class_level"],
                source_type="drive_folder_item",
                source_ref=f["id"],
                source_mime_type=f["mime_type"],
                source_folder_id=req.folder_id,
            )
        results.append({"file_name": f["name"], "status": "created", "batch_id": batch_id})

    missing = [b for b in existing_batches if b["source_ref"] not in seen_file_ids]
    reference_results = await _ingest_reference_documents(current_user["id"], req.folder_id)
    return {
        "results": results,
        "missing_batches": [{"id": b["id"], "name": b["name"]} for b in missing],
        "reference_documents": reference_results,
    }


class ResolveDuplicateRequest(BaseModel):
    file_id: str
    mime_type: str
    file_name: str
    folder_id: str | None = None
    action: str  # "replace" | "create_separate"
    target_batch_id: int | None = None  # required for "replace"
    class_level: str | None = None  # used for "create_separate"


@router.post("/resolve-drive-duplicate")
async def resolve_drive_duplicate(req: ResolveDuplicateRequest, current_user=Depends(get_current_user)):
    """Carries out whichever choice a teacher made for a file flagged as a
    likely duplicate during import/sync (see repo.find_duplicate_candidate
    and _duplicate_out) — either folds it into the existing class it looks
    like a re-upload of ("replace"), or creates it as a genuinely separate
    class despite the roster overlap ("create_separate"). Re-fetches and
    re-parses the file itself rather than trusting anything from the
    original scan, since nothing's been read from Drive since the teacher
    was shown the choice."""
    try:
        raw = await run_in_threadpool(fetch_drive_file_bytes, req.file_id, req.mime_type)
        parsed = parse_uploaded_file(filename_for(req.file_name, req.mime_type), raw)
    except (GoogleDriveFetchError, SheetParseError) as exc:
        raise HTTPException(422, str(exc))

    with session() as conn:
        if req.action == "replace":
            if not req.target_batch_id:
                raise HTTPException(422, "target_batch_id is required to replace an existing class")
            target = repo.get_batch(conn, current_user["id"], req.target_batch_id)
            if not target:
                raise HTTPException(404, "Target batch not found")
            sync_result = repo.resync_batch(conn, req.target_batch_id, parsed)
            repo.rebind_batch_source(conn, req.target_batch_id, "drive_folder_item", req.file_id, req.mime_type, req.folder_id)
            return {"status": "replaced", "batch_id": req.target_batch_id, "batch_name": target["name"], **sync_result}
        if req.action == "create_separate":
            batch_id = repo.create_batch(
                conn,
                current_user["id"],
                req.file_name.rsplit(".", 1)[0],
                current_user["default_school_name"] or "",
                req.file_name,
                parsed,
                _normalize_class_level(req.class_level),
                source_type="drive_folder_item",
                source_ref=req.file_id,
                source_mime_type=req.mime_type,
                source_folder_id=req.folder_id,
            )
            return {"status": "created", "batch_id": batch_id, "student_count": len(parsed["students"])}
        raise HTTPException(422, "action must be 'replace' or 'create_separate'")


@router.post("/{batch_id}/sync")
async def sync_batch(batch_id: int, current_user=Depends(get_current_user)):
    """Re-fetches this batch's data from its original Google Sheet/Drive
    file and replaces its students/marks in place — see
    repo.resync_batch for how existing students (and their already-sent
    parent report links) are preserved across the sync."""
    with session() as conn:
        row = repo.get_batch(conn, current_user["id"], batch_id)
        if not row:
            raise HTTPException(404, "Batch not found")
        if row["source_type"] == "file" or not row["source_ref"]:
            raise HTTPException(422, "This batch wasn't imported from a Google Sheet or Drive folder, so there's nothing to sync it from.")
        source_type, source_ref, mime_type = row["source_type"], row["source_ref"], row["source_mime_type"]
        source_filename = row["source_filename"]

    try:
        if source_type == "sheet_link":
            raw = await run_in_threadpool(fetch_google_sheet_as_xlsx, source_ref)
        else:
            raw = await run_in_threadpool(fetch_drive_file_bytes, source_ref, mime_type or "")
    except (GoogleSheetFetchError, GoogleDriveFetchError) as exc:
        raise HTTPException(422, str(exc))

    try:
        # A Google Sheets export is always .xlsx regardless of the source
        # sheet's own format, but a drive_folder_item could be a plain
        # .csv file in the folder — dispatch on its remembered filename
        # the same way a fresh upload of that file would.
        parsed = parse_workbook_file(io.BytesIO(raw)) if source_type == "sheet_link" else parse_uploaded_file(filename_for(source_filename or "", mime_type or ""), raw)
    except SheetParseError as exc:
        raise HTTPException(422, str(exc))
    except Exception:
        raise HTTPException(422, "Could not read the refreshed sheet — check that it still follows the expected layout.")

    with session() as conn:
        sync_result = repo.resync_batch(conn, batch_id, parsed)
        row = repo.get_batch(conn, current_user["id"], batch_id)
        return {
            "batch": _batch_out(row, student_count=sync_result["student_count"]),
            "added": sync_result["added"],
            "updated": sync_result["updated"],
            "removed": sync_result["removed"],
        }


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


@router.get("/{batch_id}/students/{student_id}/analytics")
def get_student_analytics(batch_id: int, student_id: int, current_user=Depends(get_current_user)):
    """The teacher-facing "Student analytics" page's data — one student's
    own marks/rank/attendance trend across every exam, each subject also
    compared against that exam's class average. Distinct from the report
    card (parent-facing) and from this batch's class-wide stats (every
    student, one exam) — see app/reports/student_analytics.py."""
    with session() as conn:
        row = repo.get_batch(conn, current_user["id"], batch_id)
        if not row:
            raise HTTPException(404, "Batch not found")
        all_students = repo.load_batch_students(conn, batch_id)
        student = next((s for s in all_students if s["id"] == student_id), None)
        if not student:
            raise HTTPException(404, "Student not found in this batch")
        settings = repo.settings_from_row(row)
        analytics = build_student_analytics(student, all_students, json.loads(row["exam_order"]), settings)
        return {
            "id": student["id"],
            "name": student["name"],
            "section": student.get("section") or "",
            "roll_no": student.get("roll") or "",
            **analytics,
        }


class SettingsUpdate(BaseModel):
    name: str | None = None
    school_name: str | None = None
    fa_total: float | None = None
    sa_total: float | None = None
    fa_marks_per_subject: float | None = None
    sa_marks_per_subject: float | None = None
    class_strength_override: int | None = None
    clear_class_strength_override: bool = False
    class_level: str | None = None


@router.put("/{batch_id}/settings")
def update_settings(batch_id: int, req: SettingsUpdate, current_user=Depends(get_current_user)):
    with session() as conn:
        row = repo.get_batch(conn, current_user["id"], batch_id)
        if not row:
            raise HTTPException(404, "Batch not found")
        fields = req.model_dump(exclude_unset=True, exclude={"clear_class_strength_override"})
        if req.clear_class_strength_override:
            fields["class_strength_override"] = None
        if "class_level" in fields:
            fields["class_level"] = _normalize_class_level(fields["class_level"])
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


@router.get("/{batch_id}/subjects")
def get_batch_subjects(batch_id: int, current_user=Depends(get_current_user)):
    """Every subject name appearing anywhere in this batch, in the same
    display order as the rest of the app — powers the Subject Analysis
    picker without needing to recompute stats just to list subjects."""
    with session() as conn:
        row = repo.get_batch(conn, current_user["id"], batch_id)
        if not row:
            raise HTTPException(404, "Batch not found")
        all_students = repo.load_batch_students(conn, batch_id)
        return {"subjects": discover_subjects(all_students)}


@router.get("/{batch_id}/subject-analysis", response_class=HTMLResponse)
def get_subject_analysis(batch_id: int, subject: str, current_user=Depends(get_current_user_from_header_or_query)):
    """The teacher-facing, whole-class, per-subject analysis report (donuts,
    Shining/Rising Stars, exam-to-exam comparison, SSC blueprint action
    plan) — see app/reports/subject_analysis.py. Opened in a new tab the
    same way /report already is, with the auth token passed as a query
    param since this is a plain navigation, not a fetch() call."""
    with session() as conn:
        row = repo.get_batch(conn, current_user["id"], batch_id)
        if not row:
            raise HTTPException(404, "Batch not found")
        all_students = repo.load_batch_students(conn, batch_id)
        if not all_students:
            raise HTTPException(404, "This batch has no students")
        settings = repo.settings_from_row(row)
        html = render_subject_analysis(
            conn, current_user["id"], all_students, json.loads(row["exam_order"]), settings,
            row["class_level"], row["school_name"], row["name"], subject,
        )
        if html is None:
            raise HTTPException(404, "No marks recorded for this subject yet")
        return HTMLResponse(content=html)


class SendReportsRequest(BaseModel):
    student_ids: list[int] | None = None  # None = every student in the batch


def _log_send(conn, student_id: int, channel: str, status: str, detail: str) -> None:
    conn.execute(
        "INSERT INTO send_log (student_id, channel, status, detail, created_at) VALUES (%s, %s, %s, %s, %s)",
        (student_id, channel, status, detail, datetime.now(timezone.utc).isoformat()),
    )


def _send_one(conn, student_row, language: str, channel_mode: str, country_code: str) -> dict:
    student_id = student_row["id"]
    name = student_row["name"]
    out = {"student_id": student_id, "name": name, "report_url": None}

    raw_phone = (student_row["phone"] or "").strip()
    if not raw_phone:
        detail = "No phone number on file for this student."
        _log_send(conn, student_id, "none", "skipped", detail)
        return {**out, "channel": "none", "status": "skipped", "detail": detail}

    try:
        phone = normalize_phone(raw_phone, country_code)
    except InvalidPhoneNumber as exc:
        _log_send(conn, student_id, "none", "skipped", str(exc))
        return {**out, "channel": "none", "status": "skipped", "detail": str(exc)}

    token = get_or_create_share_token(conn, student_id)
    report_url = public_report_url(token)
    out = {**out, "report_url": report_url}

    # channel_mode is this school's own choice (app_user.whatsapp_channel_mode,
    # see PUT /auth/whatsapp-settings) — 'whatsapp_only'/'sms_only' skip the
    # other channel entirely rather than falling back to it.
    try_whatsapp = channel_mode != "sms_only"
    try_sms = channel_mode != "whatsapp_only"

    whatsapp_error: str | None = None
    if try_whatsapp:
        if whatsapp.is_configured():
            try:
                whatsapp.send_report_whatsapp(phone, name, token, language=language)
                _log_send(conn, student_id, "whatsapp", "sent", "")
                return {**out, "channel": "whatsapp", "status": "sent", "detail": ""}
            except whatsapp.WhatsAppSendError as exc:
                whatsapp_error = str(exc)
        else:
            whatsapp_error = "WhatsApp isn't configured on this server."

    if try_sms and sms.is_configured():
        try:
            sms.send_report_sms(phone, name, report_url)
            detail = f"WhatsApp failed first ({whatsapp_error}); sent via SMS instead." if whatsapp_error else ""
            _log_send(conn, student_id, "sms", "sent", detail)
            return {**out, "channel": "sms", "status": "sent", "detail": detail}
        except sms.SmsSendError as exc:
            detail = f"WhatsApp: {whatsapp_error} | SMS: {exc}" if whatsapp_error else f"SMS: {exc}"
            _log_send(conn, student_id, "sms", "failed", detail)
            return {**out, "channel": "sms", "status": "failed", "detail": detail}

    if try_whatsapp and try_sms:
        detail = f"{whatsapp_error} SMS isn't configured on this server either."
    elif try_whatsapp:
        detail = whatsapp_error or "WhatsApp isn't configured on this server."
    else:
        detail = "SMS isn't configured on this server."
    _log_send(conn, student_id, "none", "failed", detail)
    return {**out, "channel": "none", "status": "failed", "detail": detail}


@router.get("/{batch_id}/students/{student_id}/link")
def get_student_link(batch_id: int, student_id: int, current_user=Depends(get_current_user)):
    """The same private parent-report link send-reports generates, for one
    student — but just handed back, never attempted to send and never
    logged to send_log. Used by the per-student action row (preview link /
    open-in-WhatsApp icons) so a teacher can look at or share a link
    without that counting as a real send attempt in the history."""
    with session() as conn:
        batch_row = repo.get_batch(conn, current_user["id"], batch_id)
        if not batch_row:
            raise HTTPException(404, "Batch not found")
        student_rows = [s for s in repo.list_students_brief(conn, batch_id) if s["id"] == student_id]
        if not student_rows:
            raise HTTPException(404, "Student not found in this batch")
        student_row = student_rows[0]

        token = get_or_create_share_token(conn, student_id)
        report_url = public_report_url(token)

        whatsapp_phone = None
        raw_phone = (student_row["phone"] or "").strip()
        if raw_phone:
            try:
                whatsapp_phone = normalize_phone(raw_phone, current_user["default_country_code"]).lstrip("+")
            except InvalidPhoneNumber:
                whatsapp_phone = None

        return {"report_url": report_url, "whatsapp_phone": whatsapp_phone, "father_name": student_row["father_name"] or ""}


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

        results = [
            _send_one(conn, s, current_user["whatsapp_language"], current_user["whatsapp_channel_mode"], current_user["default_country_code"])
            for s in student_rows
        ]
        return {"results": results}
