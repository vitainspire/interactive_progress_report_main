"""Parent-safe share links: one opaque token per student, resolving to
that single student's report only — never the whole batch, never anything
a teacher's own login would see. This is what gets sent over WhatsApp/SMS
and opened directly from the message, with no login required."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

import psycopg

from app.core.config import PUBLIC_APP_BASE_URL


def get_or_create_share_token(conn: psycopg.Connection, student_id: int) -> str:
    row = conn.execute("SELECT token FROM student_share WHERE student_id = %s", (student_id,)).fetchone()
    if row:
        return row["token"]
    token = secrets.token_urlsafe(24)
    conn.execute(
        "INSERT INTO student_share (student_id, token, created_at) VALUES (%s, %s, %s)",
        (student_id, token, datetime.now(timezone.utc).isoformat()),
    )
    return token


def get_student_id_for_token(conn: psycopg.Connection, token: str) -> int | None:
    row = conn.execute("SELECT student_id FROM student_share WHERE token = %s", (token,)).fetchone()
    return row["student_id"] if row else None


def public_report_url(token: str) -> str:
    return f"{PUBLIC_APP_BASE_URL}/api/public/report/{token}"
