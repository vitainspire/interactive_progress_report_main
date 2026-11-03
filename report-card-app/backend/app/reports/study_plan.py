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
from app.reports.subject_analysis import normalize_subject_key as _normalize_subject


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


def get_chapters(conn: psycopg.Connection, account_id: int, class_level: str, subject: str) -> list[dict]:
    """This account's own confirmed syllabus (see app/db/reference_documents.py)
    when it has one, otherwise the built-in global default (account_id IS
    NULL, seeded by app/db/syllabus_seed.py) — so every school gets a real
    prep plan by default, and a school's own upload only ever replaces that
    default rather than needing one before this feature works at all."""
    class_level = (class_level or "").strip()
    normalized_subject = _normalize_subject(subject)
    own = list(
        conn.execute(
            "SELECT chapter_no, chapter_name, genre, theme, month, periods FROM syllabus_chapter "
            "WHERE account_id = %s AND class_level = %s AND subject = %s ORDER BY chapter_no",
            (account_id, class_level, normalized_subject),
        ).fetchall()
    )
    if own:
        return own
    return list(
        conn.execute(
            "SELECT chapter_no, chapter_name, genre, theme, month, periods FROM syllabus_chapter "
            "WHERE account_id IS NULL AND class_level = %s AND subject = %s ORDER BY chapter_no",
            (class_level, normalized_subject),
        ).fetchall()
    )


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


def _cache_key(account_id: int, class_level: str, subject: str, weak_summary: str) -> str:
    # account_id is folded in because syllabus content is no longer
    # identical for every school — without it, two different accounts with
    # the same subject name and a similarly-worded weak_summary would
    # collide and get served each other's cached (and possibly
    # wrong-curriculum) plan.
    return hashlib.sha256(
        f"{account_id}:{(class_level or '').strip()}:{_normalize_subject(subject)}:{weak_summary}".encode("utf-8")
    ).hexdigest()


_SYSTEM_PROMPT = (
    "You write a short, specific study plan in Telugu for a parent whose child is weak in one school "
    "subject. You're given that subject's real syllabus (its actual chapter list, with how many class "
    "periods and which month each chapter was taught). Name 2-3 real chapters from that list worth "
    "focusing on first, and briefly say why (e.g. it carries more teaching periods, or it was taught "
    "recently so it's fresher to revise). Never invent a chapter that isn't in the list given to you. "
    "Keep it to 3-4 short sentences, warm and encouraging, plain conversational Telugu — no markdown, "
    "no bullet points, no headings."
)


def generate_study_plan(conn: psycopg.Connection, account_id: int, class_level: str, subject: str, weak_summary: str) -> str | None:
    """Returns a cached or freshly-generated syllabus-aware plan, or None if
    there's no syllabus on file for this class+subject (caller shows
    nothing) or the LLM call isn't configured/fails (same silent-fallback
    shape as the rest of this app's optional AI features)."""
    chapters = get_chapters(conn, account_id, class_level, subject)
    if not chapters:
        return None

    key = _cache_key(account_id, class_level, subject, weak_summary)
    row = conn.execute("SELECT plan_text FROM study_plan_cache WHERE cache_key = %s", (key,)).fetchone()
    if row:
        return row["plan_text"]

    user_prompt = (
        f"Class: {class_level}\n"
        f"Weak subject: {subject}\n"
        f"What we already know about this weakness: {weak_summary}\n\n"
        f"Real syllabus chapters for {subject}:\n{_format_chapters(chapters)}"
    )
    try:
        plan = chat.generate_text(_SYSTEM_PROMPT, user_prompt, langsmith_extra={"metadata": {"account_id": account_id}})
    except (chat.ChatNotConfigured, chat.ChatSendError) as exc:
        print(f"[study_plan] generate_study_plan failed: {exc}")
        return None

    conn.execute(
        "INSERT INTO study_plan_cache (cache_key, subject, plan_text, created_at) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (cache_key) DO NOTHING",
        (key, _normalize_subject(subject), plan, datetime.now(timezone.utc).isoformat()),
    )
    return plan


def _format_topics(topics: list[dict]) -> str:
    lines = []
    for t in topics:
        marks = t["marks"] + (t.get("choice_marks") or 0)
        lines.append(f"{t['topic_name']} ({marks} marks)")
    return "\n".join(lines)


def _format_date_with_weekday(iso_date: str) -> str:
    # %-d (no leading zero) is Unix-only and raises on Windows, so the day
    # number is built separately rather than via a single strftime format.
    d = datetime.fromisoformat(iso_date)
    return f"{d.strftime('%B')} {d.day} ({d.strftime('%A')})"


def _day_plan_cache_key(account_id: int, class_level: str, subject: str, exam_key: str, study_dates: list[str]) -> str:
    # study_dates is folded in whole (not just its length) because it's a
    # different list every single day — today drops off the front as it
    # becomes the past — so caching busts itself once a day with no extra
    # bookkeeping, and a parent never sees a cached plan with dates that
    # have already gone by.
    dates_blob = ",".join(study_dates)
    return hashlib.sha256(
        f"{account_id}:{(class_level or '').strip()}:{_normalize_subject(subject)}:{exam_key}:{dates_blob}".encode("utf-8")
    ).hexdigest()


_DAY_PLAN_SYSTEM_PROMPT = (
    "You write a short, specific day-by-day exam revision schedule in Telugu for a parent. You're given a "
    "child's real syllabus chapters likely in their next exam (with how many real class periods each took "
    "to teach), the highest-marks topics from the official exam blueprint, and the exact list of usable "
    "study dates between today and the exam (weekly off-days and holidays are already excluded from this "
    "list). Assign the chapters across those dates — a chapter that took more class periods to teach should "
    "get more days — and reserve the LAST date in the list purely for revision, explicitly naming the "
    "single highest-marks topic to prioritize then. You MUST write exactly one line per date given to you, "
    "covering every date in the list with nothing skipped, in the format 'Month Day (Weekday): what to "
    "study'. Never invent a chapter, topic, or date that wasn't given to you, and never use a date outside "
    "the list you were given. Plain conversational Telugu, one short sentence per line, no markdown, no "
    "headings, no extra commentary before or after the day list."
)

# A day-by-day plan more than this many working days out gets capped to the
# final stretch before the exam (the actual revision-critical window) —
# both to keep the LLM call's token cost bounded and because a granular
# daily chapter assignment 2+ months ahead of an exam isn't realistically
# useful; a school that sets an exam date far in advance still gets a real
# plan, just scoped to the weeks that matter most.
_MAX_PLAN_DAYS = 25


def generate_exam_day_plan(
    conn: psycopg.Connection, account_id: int, class_level: str, subject: str,
    exam_key: str, chapters: list[dict], topics: list[dict], study_dates: list[str],
) -> str | None:
    """A day-by-day revision schedule for this subject's next exam, spanning
    `study_dates` (already computed by the caller from this account's own
    Academic Calendar — see app/db/calendar.py's working_dates_between — so
    weekends/holidays are never assigned a chapter), capped to the final
    _MAX_PLAN_DAYS of it when the exam is still far off. Returns None if
    there's nothing to schedule (no chapters, no study days left) or the
    LLM call isn't configured/fails, same silent-fallback shape as
    generate_study_plan."""
    if not chapters or not study_dates:
        return None
    plan_dates = study_dates[-_MAX_PLAN_DAYS:]

    key = _day_plan_cache_key(account_id, class_level, subject, exam_key, plan_dates)
    row = conn.execute("SELECT plan_text FROM exam_day_plan_cache WHERE cache_key = %s", (key,)).fetchone()
    if row:
        return row["plan_text"]

    user_prompt = (
        f"Class: {class_level}\n"
        f"Subject: {subject}\n"
        f"Upcoming exam: {exam_key}\n\n"
        f"Real syllabus chapters likely in this exam:\n{_format_chapters(chapters)}\n\n"
        f"Highest-weightage topics from the exam blueprint:\n{_format_topics(topics)}\n\n"
        f"Usable study dates before the exam (Sundays/holidays already excluded):\n"
        + "\n".join(_format_date_with_weekday(d) for d in plan_dates)
    )
    try:
        plan = chat.generate_text(
            _DAY_PLAN_SYSTEM_PROMPT, user_prompt, max_tokens=3000,
            langsmith_extra={"metadata": {"account_id": account_id}},
        )
    except (chat.ChatNotConfigured, chat.ChatSendError) as exc:
        print(f"[study_plan] generate_exam_day_plan failed: {exc}")
        return None

    conn.execute(
        "INSERT INTO exam_day_plan_cache (cache_key, plan_text, created_at) VALUES (%s, %s, %s) "
        "ON CONFLICT (cache_key) DO NOTHING",
        (key, plan, datetime.now(timezone.utc).isoformat()),
    )
    return plan
