import json
import time
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from app.db import batches as repo
from app.db.database import session
from app.integrations import bhashini, chat, tts_audio
from app.integrations.sharing import get_student_id_for_token
from app.reports import card_render, study_plan
from app.reports.chat_canned import answer_canned_question
from app.reports.chat_context import build_student_context
from app.reports.parent_report import (
    get_speech_text,
    render_parent_report_page,
    render_report_about_page,
    render_report_landing_page,
)


class ChatTurn(BaseModel):
    # Deliberately not "system" — a parent-supplied history item can never
    # be allowed to masquerade as the system prompt that scopes the LLM to
    # this one student's own data.
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)

router = APIRouter(prefix="/public", tags=["public"])

# This endpoint feeds a child's full report (marks, attendance, rank) into
# an LLM on every call that isn't one of the canned starter questions, so
# it needs a hard ceiling against being hammered — scripted or just a
# confused double-tap — independent of the chat's own upstream retry. A
# simple in-memory per-token fixed window is enough for this app's
# single-process deployment; it resets on restart and never explicitly
# evicts old tokens, which is fine for an abuse guard rather than a
# strict quota at this app's scale.
_RATE_LIMIT_WINDOW_SECONDS = 600
_RATE_LIMIT_MAX_REQUESTS = 15
_rate_limit_state: dict[str, tuple[float, int]] = {}


def _check_rate_limit(token: str) -> None:
    now = time.monotonic()
    window_start, count = _rate_limit_state.get(token, (now, 0))
    if now - window_start > _RATE_LIMIT_WINDOW_SECONDS:
        window_start, count = now, 0
    count += 1
    _rate_limit_state[token] = (window_start, count)
    if count > _RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            429,
            "చాలా ప్రశ్నలు అడిగారు, కొంచెం సేపు తర్వాత మళ్ళీ ప్రయత్నించండి. / "
            "Too many questions — please wait a few minutes and try again.",
        )


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
    """The "Know About Student" chat — a parent can type a free-form
    question and get an answer grounded in this one student's own report
    data (see app/reports/chat_context.py and app/integrations/chat.py).
    Always serves the chat UI even if OPENROUTER_API_KEY isn't set; /ask
    below is what actually fails in that case, with a clear message rather
    than this page 404ing or silently offering a feature that can't work."""
    with session() as conn:
        student, all_students, batch_row = _resolve_report_context(conn, token)
        settings = repo.settings_from_row(batch_row)
        exam_defs = json.loads(batch_row["exam_order"])
        html = render_report_about_page(student, all_students, exam_defs, settings, batch_row["school_name"], token)
        return HTMLResponse(content=html)


@router.post("/report/{token}/ask")
def post_report_ask(token: str, req: AskRequest):
    """Answers one parent question for the "Know About Student" chat.
    Stateless like every other route here — the client resends the prior
    turns as `history` each time; nothing about the conversation is kept
    server-side. The student's report data is rebuilt fresh from the
    database on every call (never cached), so answers can't go stale if
    marks are corrected mid-conversation."""
    _check_rate_limit(token)
    question = req.question.strip()
    if not question:
        raise HTTPException(422, "Question can't be empty.")
    with session() as conn:
        student, all_students, batch_row = _resolve_report_context(conn, token)
        settings = repo.settings_from_row(batch_row)
        exam_defs = json.loads(batch_row["exam_order"])

        # The five preset starter chips ask fixed, predictable questions —
        # answered directly from this student's own data (same rule-based
        # approach as analysis.py/voice_script.py) rather than spending an
        # LLM call on them. Only a question that doesn't match one of those
        # five (including a parent's own free-typed question, even if
        # similarly worded) reaches the LLM below.
        canned = answer_canned_question(question, student, all_students, exam_defs, settings)
        if canned is not None:
            return {"answer": canned}

        context = build_student_context(student, all_students, exam_defs, settings, batch_row["school_name"])
    try:
        history = [turn.model_dump() for turn in req.history]
        answer = chat.ask_about_student(context, history, question)
    except chat.ChatNotConfigured as exc:
        raise HTTPException(503, str(exc))
    except chat.ChatSendError as exc:
        # The raw provider error (exc) is logged server-side via FastAPI's
        # own exception logging — never shown to a parent as-is, since it
        # can be a wall of upstream JSON (rate-limit bodies, stack-shaped
        # error objects) that's meaningless to them and breaks the chat
        # bubble's layout.
        print(f"[chat] ask_about_student failed: {exc}")
        if exc.status_code == 429:
            raise HTTPException(503, "చాలా మంది అడుగుతున్నారు, కొంచెం సేపు తర్వాత మళ్ళీ ప్రయత్నించండి. / Lots of people are asking right now — please try again in a moment.")
        raise HTTPException(502, "సమాధానం పొందలేకపోయాం. దయచేసి మళ్ళీ ప్రయత్నించండి. / Could not get an answer right now. Please try again.")
    return {"answer": answer}


@router.get("/report/{token}/study-plan")
def get_public_study_plan(token: str):
    """Lazily generates (and caches) a syllabus-aware study plan for this
    student's single weakest subject — fetched client-side after the report
    page has already rendered (see study_plan.py's module docstring for
    why), so a slow or unconfigured LLM never blocks the page load.
    Returns {"available": false} whenever there's nothing to show — no weak
    subject, no syllabus on file for it, or the LLM call failed — and the
    page simply doesn't display this card rather than erroring."""
    with session() as conn:
        student, all_students, batch_row = _resolve_report_context(conn, token)
        settings = repo.settings_from_row(batch_row)
        exam_defs = json.loads(batch_row["exam_order"])

        subject = study_plan.weakest_subject(student, exam_defs)
        if not subject:
            return {"available": False}

        weak_summary = answer_canned_question("ఏ సబ్జెక్టులు మెరుగుపడాలి?", student, all_students, exam_defs, settings) or ""
        plan = study_plan.generate_study_plan(conn, batch_row["user_id"], batch_row["class_level"], subject, weak_summary)
        if not plan:
            return {"available": False}
        return {"available": True, "subject": subject, "plan": plan}


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
    subject name, or the literal "conclusion"), generated via Bhashini on
    every call — not cached server-side, since the audio has the
    student's and parent's own name spoken in it and this app runs on a
    free-tier Postgres instance not worth spending on a disposable cache.
    The page's own READ_ALOUD_SCRIPT calls this first and only falls back
    to the browser's speechSynthesis if this 503s or 404s. Always
    regenerates the narration text server-side from the token — never
    trusts client-supplied text."""
    with session() as conn:
        student, all_students, batch_row = _resolve_report_context(conn, token)
        settings = repo.settings_from_row(batch_row)
        text = get_speech_text(student, all_students, json.loads(batch_row["exam_order"]), settings, batch_row["school_name"], page)
        if not text:
            raise HTTPException(404, "No narration available for this page.")
        try:
            audio_format, audio = tts_audio.synthesize(text)
        except (bhashini.BhashiniNotConfigured, bhashini.BhashiniSendError) as exc:
            raise HTTPException(503, f"Real voice narration isn't available right now: {exc}")
        # Lets the browser skip re-fetching on a repeat "Listen" tap within
        # the same visit, without this being a server-side cache.
        headers = {"Cache-Control": "private, max-age=3600"}
        media_type = "audio/mpeg" if audio_format == "mp3" else "audio/wav"
        return Response(content=audio, media_type=media_type, headers=headers)
