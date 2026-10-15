import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

from app.db import batches as repo
from app.db.database import session
from app.integrations import bhashini, tts_cache
from app.integrations.sharing import get_student_id_for_token
from app.reports.parent_report import get_speech_text, render_parent_report_page

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
def get_public_report(token: str):
    """No login required — this is the link sent to parents over
    WhatsApp/SMS. It resolves to exactly one student via an opaque,
    unguessable token, and can never see any other student or batch-wide
    data, unlike the teacher-facing /batches/{id}/report route."""
    with session() as conn:
        student, all_students, batch_row = _resolve_report_context(conn, token)
        settings = repo.settings_from_row(batch_row)
        html = render_parent_report_page(student, all_students, json.loads(batch_row["exam_order"]), settings, batch_row["school_name"], title=batch_row["name"], token=token)
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
        try:
            audio = tts_cache.get_or_synthesize(conn, text)
        except (bhashini.BhashiniNotConfigured, bhashini.BhashiniSendError) as exc:
            raise HTTPException(503, f"Real voice narration isn't available right now: {exc}")
        # The audio itself is cached server-side forever (keyed by the exact
        # text), but fetching a multi-MB blob from Postgres still costs a
        # real round trip — this lets the browser skip that entirely for a
        # repeat "Listen" tap within the same visit, without risking a
        # permanently stale cache if marks are later corrected.
        headers = {"Cache-Control": "private, max-age=3600"}
        return Response(content=audio, media_type="audio/wav", headers=headers)
