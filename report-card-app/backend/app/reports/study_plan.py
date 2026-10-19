"""The syllabus-aware study plan: instead of chat_canned.py's generic
"study more" tip for a weak subject, this names actual chapters from that
subject's real SSC syllabus (app/db/syllabus_seed.py), so a parent sees
something genuinely specific — e.g. "Electricity and Carbon Compounds carry
the most marks in Physical Science, focus there first" rather than "study
harder."

Deliberately NOT wired into chat_canned.py's instant, pure-function answers:
this makes a real LLM call (and a cache write), so it's reached via its own
lazily-fetched route (see api/public.py's /study-plan) the same way the
chat's /ask already is — the report page itself renders instantly, and the
study plan fills in afterward once it's ready, instead of blocking the page
load on a multi-second LLM call.

Only ever produces a plan when syllabus data exists for the student's
weakest subject; returns None otherwise so the caller can simply show
nothing (the existing generic tip elsewhere already covers that case).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import psycopg

from app.integrations import chat
from app.reports.chat_canned import _exam_keys, _subject_buckets

# Alternate spellings a teacher's own sheet might use for a subject already
# seeded under a different canonical name (see app/db/syllabus_seed.py).
_SUBJECT_ALIASES = {
    "MATHEMATICS": "MATHS",
    "SOCIAL STUDIES": "SOCIAL",
    "PHYSICS": "PHYSICAL SCIENCE",
    "SCIENCE": "PHYSICAL SCIENCE",
}


def _normalize_subject(name: str) -> str:
    n = (name or "").strip().upper()
    return _SUBJECT_ALIASES.get(n, n)


def weakest_subject(student: dict, exam_defs: list[dict]) -> str | None:
    """The single subject most worth a study plan: a failed subject first,
    else the lowest-average one, else None if nothing stands out (student
    doing fine everywhere, or no exams recorded yet)."""
    ks = _exam_keys(student, [e["key"] for e in exam_defs])
    if not ks:
        return None
    _good, fail, low = _subject_buckets(student, ks)
    if fail:
        return fail[0]
    if low:
        return low[0]
    return None


def get_chapters(conn: psycopg.Connection, subject: str) -> list[dict]:
    rows = conn.execute(
        "SELECT chapter_no, chapter_name, genre, theme, month, periods FROM syllabus_chapter "
        "WHERE subject = %s ORDER BY chapter_no",
        (_normalize_subject(subject),),
    ).fetchall()
    return list(rows)


def _format_chapters(chapters: list[dict]) -> str:
    lines = []
    for c in chapters:
        bits = [f"{c['chapter_no']}. {c['chapter_name']}"]
        if c.get("genre"):
            bits.append(f"({c['genre']})")
        if c.get("periods"):
            bits.append(f"- {c['periods']} class periods")
        if c.get("month"):
            bits.append(f"- taught in {c['month']}")
        lines.append(" ".join(bits))
    return "\n".join(lines)


def _cache_key(subject: str, weak_summary: str) -> str:
    return hashlib.sha256(f"{_normalize_subject(subject)}:{weak_summary}".encode("utf-8")).hexdigest()


_SYSTEM_PROMPT = (
    "You write a short, specific study plan in Telugu for a parent whose child is weak in one school "
    "subject. You're given that subject's real syllabus (its actual chapter list, with how many class "
    "periods and which month each chapter was taught). Name 2-3 real chapters from that list worth "
    "focusing on first, and briefly say why (e.g. it carries more teaching periods, or it was taught "
    "recently so it's fresher to revise). Never invent a chapter that isn't in the list given to you. "
    "Keep it to 3-4 short sentences, warm and encouraging, plain conversational Telugu — no markdown, "
    "no bullet points, no headings."
)


def generate_study_plan(conn: psycopg.Connection, subject: str, student_name: str, weak_summary: str) -> str | None:
    """Returns a cached or freshly-generated syllabus-aware plan, or None if
    there's no syllabus on file for this subject (caller shows nothing) or
    the LLM call isn't configured/fails (same silent-fallback shape as the
    rest of this app's optional AI features)."""
    chapters = get_chapters(conn, subject)
    if not chapters:
        return None

    key = _cache_key(subject, weak_summary)
    row = conn.execute("SELECT plan_text FROM study_plan_cache WHERE cache_key = %s", (key,)).fetchone()
    if row:
        return row["plan_text"]

    user_prompt = (
        f"Student: {student_name}\n"
        f"Weak subject: {subject}\n"
        f"What we already know about this weakness: {weak_summary}\n\n"
        f"Real syllabus chapters for {subject}:\n{_format_chapters(chapters)}"
    )
    try:
        plan = chat.generate_text(_SYSTEM_PROMPT, user_prompt)
    except (chat.ChatNotConfigured, chat.ChatSendError) as exc:
        print(f"[study_plan] generate_study_plan failed: {exc}")
        return None

    conn.execute(
        "INSERT INTO study_plan_cache (cache_key, subject, plan_text, created_at) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (cache_key) DO NOTHING",
        (key, _normalize_subject(subject), plan, datetime.now(timezone.utc).isoformat()),
    )
    return plan
