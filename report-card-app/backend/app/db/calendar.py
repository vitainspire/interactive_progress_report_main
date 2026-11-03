"""Repository functions for academic_calendar_event (see schema.sql) — a
school's own holidays and real exam dates. Scoped to the whole account, not
per batch/class: a school's holidays and public-exam windows are the same
across every class it runs."""
from __future__ import annotations

from datetime import datetime, timezone

import psycopg


def list_events(conn: psycopg.Connection, account_id: int) -> list[dict]:
    return list(
        conn.execute(
            "SELECT * FROM academic_calendar_event WHERE account_id = %s ORDER BY start_date",
            (account_id,),
        ).fetchall()
    )


def create_event(
    conn: psycopg.Connection, account_id: int, event_type: str, label: str,
    exam_key: str | None, start_date: str, end_date: str,
) -> dict:
    row = conn.execute(
        "INSERT INTO academic_calendar_event (account_id, event_type, label, exam_key, start_date, end_date, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
        (account_id, event_type, label, exam_key, start_date, end_date, datetime.now(timezone.utc).isoformat()),
    ).fetchone()
    return row


def delete_event(conn: psycopg.Connection, account_id: int, event_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM academic_calendar_event WHERE id = %s AND account_id = %s",
        (event_id, account_id),
    )
    return cur.rowcount > 0


def get_holiday_on(conn: psycopg.Connection, account_id: int, date_str: str) -> dict | None:
    """The holiday covering this one date, if any — used to make the
    substitute-finder skip a date the school isn't actually in session,
    which the weekly working-days pattern alone can't express (e.g. a
    festival falling on an otherwise-normal Monday)."""
    return conn.execute(
        "SELECT * FROM academic_calendar_event WHERE account_id = %s AND event_type = 'holiday' "
        "AND start_date <= %s AND end_date >= %s LIMIT 1",
        (account_id, date_str, date_str),
    ).fetchone()


def get_exam_date(conn: psycopg.Connection, account_id: int, exam_key: str) -> dict | None:
    """This account's own real date for one exam key (e.g. "SA-1"), if
    they've set one — used to show a real date on the parent report
    instead of just the exam's name."""
    return conn.execute(
        "SELECT * FROM academic_calendar_event WHERE account_id = %s AND event_type = 'exam' AND exam_key = %s LIMIT 1",
        (account_id, exam_key),
    ).fetchone()
