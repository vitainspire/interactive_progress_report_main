"""Storage for the "forgot password" flow's single-use tokens (see
password_reset_token in schema.sql) — kept separate from app/db/users.py
since nothing else touches this table. See app/api/auth.py for the
/forgot-password and /reset-password endpoints that call these."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import psycopg

_TOKEN_LIFETIME = timedelta(minutes=60)


def _hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_reset_token(conn: psycopg.Connection, user_id: int) -> str:
    """Generates a new single-use token for this user, stores only its
    hash, and returns the raw token — the only time the raw value exists
    outside the requester's inbox. Doesn't invalidate any token already
    issued for this user; an old, unused one simply expires on its own."""
    raw_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    conn.execute(
        "INSERT INTO password_reset_token (user_id, token_hash, created_at, expires_at) VALUES (%s, %s, %s, %s)",
        (user_id, _hash(raw_token), now.isoformat(), (now + _TOKEN_LIFETIME).isoformat()),
    )
    return raw_token


def get_valid_reset_token(conn: psycopg.Connection, raw_token: str) -> dict | None:
    """None for a token that's wrong, already used, or past its 60-minute
    lifetime — callers show the same "invalid or expired" message for all
    three, so a requester can't learn which case applies."""
    row = conn.execute(
        "SELECT id, user_id, expires_at, used_at FROM password_reset_token WHERE token_hash = %s",
        (_hash(raw_token),),
    ).fetchone()
    if not row or row["used_at"] is not None:
        return None
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        return None
    return row


def mark_reset_token_used(conn: psycopg.Connection, token_id: int) -> None:
    conn.execute(
        "UPDATE password_reset_token SET used_at = %s WHERE id = %s",
        (datetime.now(timezone.utc).isoformat(), token_id),
    )
