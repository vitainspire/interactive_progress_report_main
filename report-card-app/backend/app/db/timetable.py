import json

import psycopg


def _next_sort_order(conn: psycopg.Connection, table: str, user_id: int) -> int:
    row = conn.execute(f"SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM {table} WHERE user_id = %s", (user_id,)).fetchone()
    return row["n"]


# ---- Classes (grade + section, e.g. "10" / "A") ----


def create_class(conn: psycopg.Connection, user_id: int, grade: str, section: str) -> int:
    sort_order = _next_sort_order(conn, "tt_class", user_id)
    row = conn.execute(
        "INSERT INTO tt_class (user_id, grade, section, sort_order) VALUES (%s, %s, %s, %s) RETURNING id",
        (user_id, grade, section, sort_order),
    ).fetchone()
    return row["id"]


def list_classes(conn: psycopg.Connection, user_id: int) -> list[dict]:
    return conn.execute("SELECT * FROM tt_class WHERE user_id = %s ORDER BY sort_order", (user_id,)).fetchall()


def get_class(conn: psycopg.Connection, user_id: int, class_id: int) -> dict | None:
    return conn.execute("SELECT * FROM tt_class WHERE id = %s AND user_id = %s", (class_id, user_id)).fetchone()


def get_class_by_name(conn: psycopg.Connection, user_id: int, grade: str, section: str) -> dict | None:
    return conn.execute(
        "SELECT * FROM tt_class WHERE user_id = %s AND grade = %s AND section = %s", (user_id, grade, section)
    ).fetchone()


def delete_class(conn: psycopg.Connection, user_id: int, class_id: int) -> bool:
    cur = conn.execute("DELETE FROM tt_class WHERE id = %s AND user_id = %s", (class_id, user_id))
    return cur.rowcount > 0


# ---- Subjects ----


def create_subject(conn: psycopg.Connection, user_id: int, name: str, code: str) -> int:
    sort_order = _next_sort_order(conn, "tt_subject", user_id)
    row = conn.execute(
        "INSERT INTO tt_subject (user_id, name, code, sort_order) VALUES (%s, %s, %s, %s) RETURNING id",
        (user_id, name, code, sort_order),
    ).fetchone()
    return row["id"]


def list_subjects(conn: psycopg.Connection, user_id: int) -> list[dict]:
    return conn.execute("SELECT * FROM tt_subject WHERE user_id = %s ORDER BY sort_order", (user_id,)).fetchall()


def get_subject(conn: psycopg.Connection, user_id: int, subject_id: int) -> dict | None:
    return conn.execute("SELECT * FROM tt_subject WHERE id = %s AND user_id = %s", (subject_id, user_id)).fetchone()


def get_subject_by_name(conn: psycopg.Connection, user_id: int, name: str) -> dict | None:
    return conn.execute("SELECT * FROM tt_subject WHERE user_id = %s AND name = %s", (user_id, name)).fetchone()


def delete_subject(conn: psycopg.Connection, user_id: int, subject_id: int) -> bool:
    cur = conn.execute("DELETE FROM tt_subject WHERE id = %s AND user_id = %s", (subject_id, user_id))
    return cur.rowcount > 0


# ---- Teachers ----


def create_teacher(conn: psycopg.Connection, user_id: int, name: str, code: str, max_periods_per_day: int | None) -> int:
    sort_order = _next_sort_order(conn, "tt_teacher", user_id)
    row = conn.execute(
        "INSERT INTO tt_teacher (user_id, name, code, max_periods_per_day, sort_order) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (user_id, name, code, max_periods_per_day, sort_order),
    ).fetchone()
    return row["id"]


def list_teachers(conn: psycopg.Connection, user_id: int) -> list[dict]:
    return conn.execute("SELECT * FROM tt_teacher WHERE user_id = %s ORDER BY sort_order", (user_id,)).fetchall()


def get_teacher(conn: psycopg.Connection, user_id: int, teacher_id: int) -> dict | None:
    return conn.execute("SELECT * FROM tt_teacher WHERE id = %s AND user_id = %s", (teacher_id, user_id)).fetchone()


def delete_teacher(conn: psycopg.Connection, user_id: int, teacher_id: int) -> bool:
    cur = conn.execute("DELETE FROM tt_teacher WHERE id = %s AND user_id = %s", (teacher_id, user_id))
    return cur.rowcount > 0


def subject_ids_by_teacher(conn: psycopg.Connection, user_id: int) -> dict[int, list[int]]:
    """Every teacher's taught-subject ids, grouped by teacher_id, in one
    query — used to assemble the teacher list response without an N+1."""
    rows = conn.execute(
        """SELECT ts.teacher_id, ts.subject_id
           FROM tt_teacher_subject ts
           JOIN tt_teacher t ON t.id = ts.teacher_id
           WHERE t.user_id = %s""",
        (user_id,),
    ).fetchall()
    out: dict[int, list[int]] = {}
    for row in rows:
        out.setdefault(row["teacher_id"], []).append(row["subject_id"])
    return out


def set_teacher_subjects(conn: psycopg.Connection, teacher_id: int, subject_ids: list[int]) -> None:
    """Replaces the full set of subjects this teacher is tagged as
    teaching — simpler and race-free compared to incremental add/remove
    calls, since the frontend always sends the complete desired set."""
    conn.execute("DELETE FROM tt_teacher_subject WHERE teacher_id = %s", (teacher_id,))
    if subject_ids:
        placeholders = ", ".join(["(%s, %s)"] * len(subject_ids))
        params = [v for sid in subject_ids for v in (teacher_id, sid)]
        conn.execute(f"INSERT INTO tt_teacher_subject (teacher_id, subject_id) VALUES {placeholders}", params)


# ---- Class <-> subject assignments (who teaches what, how often) ----


def list_class_subjects(conn: psycopg.Connection, class_id: int) -> list[dict]:
    return conn.execute(
        """SELECT cs.subject_id, cs.teacher_id, cs.periods_per_week,
                  s.name AS subject_name, s.code AS subject_code,
                  t.name AS teacher_name, t.code AS teacher_code
           FROM tt_class_subject cs
           JOIN tt_subject s ON s.id = cs.subject_id
           LEFT JOIN tt_teacher t ON t.id = cs.teacher_id
           WHERE cs.class_id = %s
           ORDER BY s.sort_order""",
        (class_id,),
    ).fetchall()


def upsert_class_subject(conn: psycopg.Connection, class_id: int, subject_id: int, teacher_id: int | None, periods_per_week: int) -> None:
    conn.execute(
        """INSERT INTO tt_class_subject (class_id, subject_id, teacher_id, periods_per_week)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (class_id, subject_id)
           DO UPDATE SET teacher_id = EXCLUDED.teacher_id, periods_per_week = EXCLUDED.periods_per_week""",
        (class_id, subject_id, teacher_id, periods_per_week),
    )


def delete_class_subject(conn: psycopg.Connection, class_id: int, subject_id: int) -> bool:
    cur = conn.execute("DELETE FROM tt_class_subject WHERE class_id = %s AND subject_id = %s", (class_id, subject_id))
    return cur.rowcount > 0


# ---- School weekly structure ----

_DEFAULT_WORKING_DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]
_DEFAULT_START_TIME = "09:15"
_DEFAULT_END_TIME = "16:00"


def get_school_config(conn: psycopg.Connection, user_id: int) -> dict:
    row = conn.execute("SELECT * FROM tt_school_config WHERE user_id = %s", (user_id,)).fetchone()
    if row:
        return {
            "working_days": json.loads(row["working_days"]),
            "periods_per_day": row["periods_per_day"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "breaks": json.loads(row["breaks"]),
        }
    return {
        "working_days": _DEFAULT_WORKING_DAYS,
        "periods_per_day": 8,
        "start_time": _DEFAULT_START_TIME,
        "end_time": _DEFAULT_END_TIME,
        "breaks": [],
    }


def set_school_config(
    conn: psycopg.Connection,
    user_id: int,
    working_days: list[str],
    periods_per_day: int,
    start_time: str,
    end_time: str,
    breaks: list[dict],
) -> None:
    conn.execute(
        """INSERT INTO tt_school_config (user_id, working_days, periods_per_day, start_time, end_time, breaks)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT (user_id) DO UPDATE SET
               working_days = EXCLUDED.working_days,
               periods_per_day = EXCLUDED.periods_per_day,
               start_time = EXCLUDED.start_time,
               end_time = EXCLUDED.end_time,
               breaks = EXCLUDED.breaks""",
        (user_id, json.dumps(working_days), periods_per_day, start_time, end_time, json.dumps(breaks)),
    )
