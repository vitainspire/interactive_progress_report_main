import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.db import batches as repo
from app.db.database import session
from app.integrations.sharing import get_student_id_for_token
from app.reports.card_render import render_report_page

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/report/{token}", response_class=HTMLResponse)
def get_public_report(token: str):
    """No login required — this is the link sent to parents over
    WhatsApp/SMS. It resolves to exactly one student via an opaque,
    unguessable token, and can never see any other student or batch-wide
    data, unlike the teacher-facing /batches/{id}/report route."""
    with session() as conn:
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
        settings = repo.settings_from_row(batch_row)
        html = render_report_page(selected, all_students, json.loads(batch_row["exam_order"]), settings, batch_row["school_name"], title=batch_row["name"])
        return HTMLResponse(content=html)
