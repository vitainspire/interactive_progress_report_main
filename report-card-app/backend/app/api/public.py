import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

from app.db import batches as repo
from app.db.database import session
from app.integrations import bhashini, tts_cache
from app.integrations.sharing import get_student_id_for_token
from app.reports import card_render
from app.reports.parent_report import (
    get_speech_text,
    render_parent_report_page,
    render_report_about_placeholder,
    render_report_landing_page,
)

router = APIRouter(prefix="/public", tags=["public"])


def _resolve_report_context(conn, token: str):
    """Shared by both the HTML report and the per-page voice route — token
    -> exactly one student, their batch, and every student in that batch
    (needed for class-strength/rank context), or a 404 if anything in that
    chain is missing/stale."""
    student_id = get_student_id_for_token(conn, token)
    if student_id is None:
        raise HTTPException(404, "This report link is invalid or has expired.")
    student_row = repo.get_student(conn, student_id)
    if not student_row:
        raise HTTPException(404, "This report link is invalid or has expired.")
    batch_row = conn.execute("SELECT * FROM batch WHERE id = %s", (student_row["batch_id"],)).fetchone()
    if not batch_row:
        raise HTTPException(404, "This report link is invalid or has expired.")
    all_students = repo.load_batch_students(conn, batch_row["id"])
    selected = [s for s in all_students if s["id"] == student_id]
    if not selected:
        raise HTTPException(404, "This report link is invalid or has expired.")
    return selected[0], all_students, batch_row


@router.get("/report/{token}", response_class=HTMLResponse)
def get_public_report_landing(token: str):
    """No login required — this is the link sent to parents over
    WhatsApp/SMS. Shows a choice between the full report (/view) and the
    not-yet-built "know about student" page (/about), rather than dropping
    straight into the swipeable report."""
    with session() as conn:
        student, _all_students, batch_row = _resolve_report_context(conn, token)
        html = render_report_landing_page(student["name"], batch_row["school_name"], token)
        return HTMLResponse(content=html)


@router.get("/report/{token}/view", response_class=HTMLResponse)
def get_public_report(token: str):
    """The actual (number of subjects + 2)-page swipeable report — reached
    via the "View Report" card on the landing page above. Resolves to
    exactly one student via an opaque, unguessable token, and can never see
    any other student or batch-wide data, unlike the teacher-facing
    /batches/{id}/report route."""
    with session() as conn:
        student, all_students, batch_row = _resolve_report_context(conn, token)
        settings = repo.settings_from_row(batch_row)
        html = render_parent_report_page(student, all_students, json.loads(batch_row["exam_order"]), settings, batch_row["school_name"], title=batch_row["name"], token=token)
        return HTMLResponse(content=html)


@router.get("/report/{token}/about", response_class=HTMLResponse)
def get_public_report_about(token: str):
    """Placeholder for the "Know About Student" card on the landing page —
    not built yet, deliberately a real page rather than a 404 so the link
    stays honest about what's coming."""
    with session() as conn:
        student, _all_students, batch_row = _resolve_report_context(conn, token)
        html = render_report_about_placeholder(student["name"], batch_row["school_name"], token)
        return HTMLResponse(content=html)


@router.get("/report/{token}/full", response_class=HTMLResponse)
def get_public_report_full(token: str):
    """The exact same dense, printable card the teacher sees in the app
    (card_render.render_report_page) for this one student only — embedded
    as the final page of the parent-facing swipeable report (see
    parent_report._render_full_report_page) behind an <iframe>, so a parent
    who wants the complete picture isn't limited to the simplified
    per-subject pages. Resolves via the same opaque token as the rest of
    this router, so it carries no more access than the parent report itself."""
    with session() as conn:
        student, all_students, batch_row = _resolve_report_context(conn, token)
        settings = repo.settings_from_row(batch_row)
        exam_defs = json.loads(batch_row["exam_order"])
        html = card_render.render_report_page([student], all_students, exam_defs, settings, batch_row["school_name"], title=batch_row["name"])
        return HTMLResponse(content=html)


@router.get("/report/{token}/voice/{page}")
def get_public_report_voice(token: str, page: str):
    """Real Telugu audio for one page of the parent report (page is a
    subject name, or the literal "conclusion"), generated via Bhashini and
    cached in Postgres. The page's own READ_ALOUD_SCRIPT calls this first
    and only falls back to the browser's speechSynthesis if this 503s or
    404s. Always regenerates the narration text server-side from the
    token — never trusts client-supplied text."""
    with session() as conn:
        student, all_students, batch_row = _resolve_report_context(conn, token)
        settings = repo.settings_from_row(batch_row)
        text = get_speech_text(student, all_students, json.loads(batch_row["exam_order"]), settings, batch_row["school_name"], page)
        if not text:
            raise HTTPException(404, "No narration available for this page.")
        content_key = f"{student['id']}:{page}"
        try:
            audio_format, audio = tts_cache.get_or_synthesize(conn, content_key, text)
        except (bhashini.BhashiniNotConfigured, bhashini.BhashiniSendError) as exc:
            raise HTTPException(503, f"Real voice narration isn't available right now: {exc}")
        # The audio itself is cached server-side forever (keyed by the exact
        # text), but fetching even a compressed blob from Postgres still
        # costs a real round trip — this lets the browser skip that
        # entirely for a repeat "Listen" tap within the same visit, without
        # risking a permanently stale cache if marks are later corrected.
        headers = {"Cache-Control": "private, max-age=3600"}
        media_type = "audio/mpeg" if audio_format == "mp3" else "audio/wav"
        return Response(content=audio, media_type=media_type, headers=headers)
