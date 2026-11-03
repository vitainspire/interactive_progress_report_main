"""Repository functions for academic_calendar_event / exam_plan_type (see
schema.sql) — a school's own holidays and real exam dates, plus the exam
plan (which types of exam it runs and how many this year). Scoped to the
whole account, not per batch/class: a school's holidays and public-exam
windows are the same across every class it runs."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

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
    exam_key: str | None, start_date: str, end_date: str, plan_type: str | None = None,
) -> dict:
    row = conn.execute(
        "INSERT INTO academic_calendar_event (account_id, event_type, label, exam_key, plan_type, start_date, end_date, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
        (account_id, event_type, label, exam_key, plan_type, start_date, end_date, datetime.now(timezone.utc).isoformat()),
    ).fetchone()
    return row


def update_event(
    conn: psycopg.Connection, account_id: int, event_id: int, label: str,
    exam_key: str | None, start_date: str, end_date: str, plan_type: str | None,
) -> dict | None:
    return conn.execute(
        "UPDATE academic_calendar_event SET label = %s, exam_key = %s, plan_type = %s, start_date = %s, end_date = %s "
        "WHERE id = %s AND account_id = %s RETURNING *",
        (label, exam_key, plan_type, start_date, end_date, event_id, account_id),
    ).fetchone()


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


# ---- Academic year ----


def get_academic_year(conn: psycopg.Connection, account_id: int) -> dict:
    row = conn.execute(
        "SELECT academic_year_start, academic_year_end, academic_week_pattern FROM app_user WHERE id = %s",
        (account_id,),
    ).fetchone()
    return {
        "start_date": row["academic_year_start"],
        "end_date": row["academic_year_end"],
        "week_pattern": row["academic_week_pattern"],
    }


# ---- Exam plan (type + how many this year) ----


def list_exam_plan_types(conn: psycopg.Connection, account_id: int) -> list[dict]:
    return list(
        conn.execute(
            "SELECT * FROM exam_plan_type WHERE account_id = %s ORDER BY created_at",
            (account_id,),
        ).fetchall()
    )


def create_exam_plan_type(conn: psycopg.Connection, account_id: int, name: str, count_per_year: int) -> dict:
    return conn.execute(
        "INSERT INTO exam_plan_type (account_id, name, count_per_year, created_at) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (account_id, name) DO UPDATE SET count_per_year = EXCLUDED.count_per_year "
        "RETURNING *",
        (account_id, name, count_per_year, datetime.now(timezone.utc).isoformat()),
    ).fetchone()


def delete_exam_plan_type(conn: psycopg.Connection, account_id: int, plan_type_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM exam_plan_type WHERE id = %s AND account_id = %s",
        (plan_type_id, account_id),
    )
    return cur.rowcount > 0


# ---- Working-capacity calculation ----


def compute_working_capacity(
    start_date: str, end_date: str, week_pattern: str, holidays: list[dict], hours_per_day: float | None,
) -> dict:
    """Pure arithmetic over the academic year range: how many days the
    school is actually in session, given the weekly pattern (which
    weekdays run classes at all) and real holidays (which subtract from an
    otherwise-working day). `hours_per_day` is only ever a real number —
    the caller passes None when this school hasn't actually set a school
    day length in Dynamic Timetable, and this function then returns
    working_hours=None rather than guessing at a default school-day length
    and presenting it as if it were this school's real one."""
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    # Python's date.weekday(): Monday=0 ... Sunday=6.
    working_weekdays = set(range(6)) if week_pattern == "6-day" else set(range(5))

    holiday_dates: set[date] = set()
    for h in holidays:
        d = date.fromisoformat(h["start_date"])
        e = date.fromisoformat(h["end_date"])
        cur = d
        while cur <= e:
            holiday_dates.add(cur)
            cur += timedelta(days=1)

    total_days = (end - start).days + 1
    working_days = 0
    cur = start
    while cur <= end:
        if cur.weekday() in working_weekdays and cur not in holiday_dates:
            working_days += 1
        cur += timedelta(days=1)

    return {
        "working_days": working_days,
        "non_working_days": total_days - working_days,
        "working_hours": round(working_days * hours_per_day) if hours_per_day else None,
    }
