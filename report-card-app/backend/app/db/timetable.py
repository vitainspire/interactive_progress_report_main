import json
from datetime import datetime, timezone

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


def set_subject_excluded_periods(conn: psycopg.Connection, subject_id: int, excluded_periods: list[int]) -> None:
    conn.execute("UPDATE tt_subject SET excluded_periods = %s WHERE id = %s", (json.dumps(excluded_periods), subject_id))


# ---- Teachers ----


def create_teacher(conn: psycopg.Connection, user_id: int, name: str, code: str, max_periods_per_day: int | None, phone: str = "") -> int:
    sort_order = _next_sort_order(conn, "tt_teacher", user_id)
    row = conn.execute(
        "INSERT INTO tt_teacher (user_id, name, code, phone, max_periods_per_day, sort_order) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (user_id, name, code, phone, max_periods_per_day, sort_order),
    ).fetchone()
    return row["id"]


def list_teachers(conn: psycopg.Connection, user_id: int) -> list[dict]:
    return conn.execute("SELECT * FROM tt_teacher WHERE user_id = %s ORDER BY sort_order", (user_id,)).fetchall()


def get_teacher(conn: psycopg.Connection, user_id: int, teacher_id: int) -> dict | None:
    return conn.execute("SELECT * FROM tt_teacher WHERE id = %s AND user_id = %s", (teacher_id, user_id)).fetchone()


def update_teacher(conn: psycopg.Connection, teacher_id: int, fields: dict) -> None:
    cols = []
    values = []
    for key in ("name", "code", "phone", "max_periods_per_day"):
        if key in fields:
            cols.append(f"{key} = %s")
            values.append(fields[key])
    if not cols:
        return
    values.append(teacher_id)
    conn.execute(f"UPDATE tt_teacher SET {', '.join(cols)} WHERE id = %s", values)


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


# ---- Generated timetable ----


def list_all_class_subjects_for_generation(conn: psycopg.Connection, user_id: int) -> list[dict]:
    """Every class belonging to this user, each with its full list of
    (subject, teacher, periods_per_week) requirements — everything the
    generator needs, in one query per table instead of one per class."""
    classes = list_classes(conn, user_id)
    rows = conn.execute(
        """SELECT cs.class_id, cs.subject_id, cs.teacher_id, cs.periods_per_week,
                  s.name AS subject_name, s.excluded_periods, t.name AS teacher_name
           FROM tt_class_subject cs
           JOIN tt_class c ON c.id = cs.class_id
           JOIN tt_subject s ON s.id = cs.subject_id
           LEFT JOIN tt_teacher t ON t.id = cs.teacher_id
           WHERE c.user_id = %s""",
        (user_id,),
    ).fetchall()
    by_class: dict[int, list[dict]] = {}
    for row in rows:
        by_class.setdefault(row["class_id"], []).append(row)
    return [
        {"class_id": c["id"], "class_name": f'{c["grade"]} {c["section"]}'.strip(), "subjects": by_class.get(c["id"], [])}
        for c in classes
    ]


def replace_timetable_entries(conn: psycopg.Connection, user_id: int, entries: list[tuple[int, str, int, int, int | None]]) -> None:
    """Wipes every existing generated entry for this user's classes and
    inserts the freshly generated set — a generation run always replaces
    the previous one wholesale rather than being merged with it."""
    conn.execute("DELETE FROM tt_timetable_entry WHERE class_id IN (SELECT id FROM tt_class WHERE user_id = %s)", (user_id,))
    if not entries:
        return
    placeholders = ", ".join(["(%s, %s, %s, %s, %s)"] * len(entries))
    params = [v for e in entries for v in e]
    conn.execute(f"INSERT INTO tt_timetable_entry (class_id, day, period, subject_id, teacher_id) VALUES {placeholders}", params)


def get_timetable_entries(conn: psycopg.Connection, class_id: int) -> list[dict]:
    return conn.execute(
        """SELECT te.day, te.period, te.subject_id, s.name AS subject_name, s.code AS subject_code,
                  te.teacher_id, t.name AS teacher_name, t.code AS teacher_code
           FROM tt_timetable_entry te
           JOIN tt_subject s ON s.id = te.subject_id
           LEFT JOIN tt_teacher t ON t.id = te.teacher_id
           WHERE te.class_id = %s
           ORDER BY te.day, te.period""",
        (class_id,),
    ).fetchall()


def has_generated_timetable(conn: psycopg.Connection, user_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM tt_timetable_entry te JOIN tt_class c ON c.id = te.class_id WHERE c.user_id = %s LIMIT 1", (user_id,)
    ).fetchone()
    return row is not None


def get_timetable_entry(conn: psycopg.Connection, class_id: int, day: str, period: int) -> dict | None:
    return conn.execute(
        """SELECT te.subject_id, s.name AS subject_name, te.teacher_id, t.name AS teacher_name, t.code AS teacher_code
           FROM tt_timetable_entry te
           JOIN tt_subject s ON s.id = te.subject_id
           LEFT JOIN tt_teacher t ON t.id = te.teacher_id
           WHERE te.class_id = %s AND te.day = %s AND te.period = %s""",
        (class_id, day, period),
    ).fetchone()


def set_timetable_entry(conn: psycopg.Connection, class_id: int, day: str, period: int, subject_id: int, teacher_id: int | None) -> None:
    """Manually overrides one slot of the generated timetable — a
    permanent change to the weekly template, distinct from a dated
    tt_substitution (which only covers one specific day's absence)."""
    conn.execute(
        """INSERT INTO tt_timetable_entry (class_id, day, period, subject_id, teacher_id)
           VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (class_id, day, period) DO UPDATE SET subject_id = EXCLUDED.subject_id, teacher_id = EXCLUDED.teacher_id""",
        (class_id, day, period, subject_id, teacher_id),
    )


def is_teacher_busy_elsewhere(
    conn: psycopg.Connection, user_id: int, teacher_id: int, day: str, period: int, exclude_class_id: int
) -> dict | None:
    """Whether `teacher_id` already teaches a *different* class at this
    exact day/period — used to block a manual edit from creating the same
    double-booking the generator itself would never produce."""
    return conn.execute(
        """SELECT te.class_id, c.grade, c.section FROM tt_timetable_entry te
           JOIN tt_class c ON c.id = te.class_id
           WHERE c.user_id = %s AND te.teacher_id = %s AND te.day = %s AND te.period = %s AND te.class_id != %s""",
        (user_id, teacher_id, day, period, exclude_class_id),
    ).fetchone()


# ---- Substitutions ----


def rank_candidates(
    teachers: list[dict], busy: set[int], same_subject_ids: set[int], this_class_teacher_ids: set[int]
) -> list[dict]:
    """Shared ranking step behind find_substitute_candidates and the
    bulk-computed pending-leave queue: teaches the same subject first,
    then anyone who already teaches this class some other subject (a
    familiar face), then everyone else not already busy."""
    candidates = []
    for t in teachers:
        if t["id"] in busy:
            continue
        if t["id"] in same_subject_ids:
            reason = "subject"
        elif t["id"] in this_class_teacher_ids:
            reason = "class"
        else:
            reason = "other"
        candidates.append({"teacher_id": t["id"], "teacher_name": t["name"], "teacher_code": t["code"], "reason": reason})

    order = {"subject": 0, "class": 1, "other": 2}
    candidates.sort(key=lambda c: (order[c["reason"]], c["teacher_name"]))
    return candidates


def find_substitute_candidates(
    conn: psycopg.Connection, user_id: int, class_id: int, day: str, period: int, date: str, exclude_teacher_id: int | None
) -> list[dict]:
    """Every teacher for this account who could cover a (class, day,
    period) slot, ranked — excluding whoever's already busy at that exact
    day/period in the generated timetable, or already covering a
    different substitution at that same date/period. For a single slot
    at a time (the day/period absence flow); see
    pending_substitution_needs() for the batched equivalent used by the
    planned-leave queue, which avoids repeating these queries per slot."""
    entry = get_timetable_entry(conn, class_id, day, period)
    subject_id = entry["subject_id"] if entry else None

    teachers = list_teachers(conn, user_id)

    busy_teaching = {
        r["teacher_id"]
        for r in conn.execute(
            """SELECT DISTINCT te.teacher_id FROM tt_timetable_entry te
               JOIN tt_class c ON c.id = te.class_id
               WHERE c.user_id = %s AND te.day = %s AND te.period = %s AND te.teacher_id IS NOT NULL""",
            (user_id, day, period),
        ).fetchall()
    }
    busy_substituting = {
        r["substitute_teacher_id"]
        for r in conn.execute(
            """SELECT DISTINCT sub.substitute_teacher_id FROM tt_substitution sub
               JOIN tt_class c ON c.id = sub.class_id
               WHERE c.user_id = %s AND sub.date = %s AND sub.period = %s""",
            (user_id, date, period),
        ).fetchall()
    }
    busy = busy_teaching | busy_substituting
    if exclude_teacher_id is not None:
        busy.add(exclude_teacher_id)

    same_subject_ids: set[int] = set()
    if subject_id is not None:
        same_subject_ids = {
            r["teacher_id"] for r in conn.execute("SELECT teacher_id FROM tt_teacher_subject WHERE subject_id = %s", (subject_id,)).fetchall()
        }
    this_class_teacher_ids = {
        r["teacher_id"]
        for r in conn.execute(
            "SELECT DISTINCT teacher_id FROM tt_timetable_entry WHERE class_id = %s AND teacher_id IS NOT NULL", (class_id,)
        ).fetchall()
    }

    return rank_candidates(teachers, busy, same_subject_ids, this_class_teacher_ids)


def teacher_is_busy_at_slot(
    conn: psycopg.Connection, user_id: int, teacher_id: int, day: str, period: int, date: str, exclude_class_id: int
) -> bool:
    """True if this teacher is already teaching another class at this
    exact day/period in the generated timetable, or already covering a
    different substitution at this same date/period — the same
    exclusion find_substitute_candidates applies when ranking, enforced
    here too so a stale or direct API request can't double-book a
    teacher into two places at once."""
    busy_teaching = conn.execute(
        """SELECT 1 FROM tt_timetable_entry te JOIN tt_class c ON c.id = te.class_id
           WHERE c.user_id = %s AND te.day = %s AND te.period = %s AND te.teacher_id = %s""",
        (user_id, day, period, teacher_id),
    ).fetchone()
    if busy_teaching:
        return True
    busy_substituting = conn.execute(
        """SELECT 1 FROM tt_substitution sub JOIN tt_class c ON c.id = sub.class_id
           WHERE c.user_id = %s AND sub.date = %s AND sub.period = %s
             AND sub.substitute_teacher_id = %s AND sub.class_id != %s""",
        (user_id, date, period, teacher_id, exclude_class_id),
    ).fetchone()
    return busy_substituting is not None


def create_or_update_substitution(
    conn: psycopg.Connection,
    class_id: int,
    date: str,
    day: str,
    period: int,
    subject_id: int | None,
    original_teacher_id: int | None,
    substitute_teacher_id: int,
) -> int:
    row = conn.execute(
        """INSERT INTO tt_substitution (class_id, date, day, period, subject_id, original_teacher_id, substitute_teacher_id, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (class_id, date, period) DO UPDATE SET
               substitute_teacher_id = EXCLUDED.substitute_teacher_id,
               subject_id = EXCLUDED.subject_id,
               original_teacher_id = EXCLUDED.original_teacher_id,
               created_at = EXCLUDED.created_at
           RETURNING id""",
        (class_id, date, day, period, subject_id, original_teacher_id, substitute_teacher_id, datetime.now(timezone.utc).isoformat()),
    ).fetchone()
    return row["id"]


def list_substitutions_for_account(conn: psycopg.Connection, user_id: int, date: str) -> list[dict]:
    """Every confirmed substitution across the whole school for one date —
    powers the printable staff-noticeboard sheet and the batch "notify
    substitutes" action, so neither has to loop class by class."""
    return conn.execute(
        """SELECT sub.class_id, c.grade, c.section, sub.day, sub.period,
                  sub.subject_id, s.name AS subject_name,
                  sub.original_teacher_id, ot.name AS original_teacher_name,
                  sub.substitute_teacher_id, st.name AS substitute_teacher_name,
                  st.code AS substitute_teacher_code, st.phone AS substitute_teacher_phone
           FROM tt_substitution sub
           JOIN tt_class c ON c.id = sub.class_id
           LEFT JOIN tt_subject s ON s.id = sub.subject_id
           LEFT JOIN tt_teacher ot ON ot.id = sub.original_teacher_id
           JOIN tt_teacher st ON st.id = sub.substitute_teacher_id
           WHERE c.user_id = %s AND sub.date = %s
           ORDER BY sub.period, c.grade, c.section""",
        (user_id, date),
    ).fetchall()


def list_substitutions(conn: psycopg.Connection, class_id: int, date: str) -> list[dict]:
    return conn.execute(
        """SELECT sub.period, sub.day, sub.subject_id, s.name AS subject_name,
                  sub.original_teacher_id, ot.name AS original_teacher_name,
                  sub.substitute_teacher_id, st.name AS substitute_teacher_name, st.code AS substitute_teacher_code
           FROM tt_substitution sub
           LEFT JOIN tt_subject s ON s.id = sub.subject_id
           LEFT JOIN tt_teacher ot ON ot.id = sub.original_teacher_id
           JOIN tt_teacher st ON st.id = sub.substitute_teacher_id
           WHERE sub.class_id = %s AND sub.date = %s
           ORDER BY sub.period""",
        (class_id, date),
    ).fetchall()


def delete_substitution(conn: psycopg.Connection, class_id: int, date: str, period: int) -> bool:
    cur = conn.execute("DELETE FROM tt_substitution WHERE class_id = %s AND date = %s AND period = %s", (class_id, date, period))
    return cur.rowcount > 0


def get_teacher_timetable(conn: psycopg.Connection, user_id: int, teacher_id: int) -> list[dict]:
    """One teacher's own week — every class they're in, period by period —
    the same underlying generated data as a class's timetable, just
    re-grouped by teacher instead of by class."""
    return conn.execute(
        """SELECT te.day, te.period, te.class_id, c.grade, c.section,
                  te.subject_id, s.name AS subject_name, s.code AS subject_code
           FROM tt_timetable_entry te
           JOIN tt_class c ON c.id = te.class_id
           JOIN tt_subject s ON s.id = te.subject_id
           WHERE te.teacher_id = %s AND c.user_id = %s
           ORDER BY te.day, te.period""",
        (teacher_id, user_id),
    ).fetchall()


def list_teacher_substitutions(conn: psycopg.Connection, user_id: int, teacher_id: int, date: str) -> list[dict]:
    """Every class this teacher is covering as a substitute on one
    specific date — overlaid on their own weekly timetable so they can
    see at a glance where they actually need to be that day, not just
    their regular schedule."""
    return conn.execute(
        """SELECT sub.day, sub.period, sub.class_id, c.grade, c.section,
                  sub.subject_id, s.name AS subject_name
           FROM tt_substitution sub
           JOIN tt_class c ON c.id = sub.class_id
           LEFT JOIN tt_subject s ON s.id = sub.subject_id
           WHERE sub.substitute_teacher_id = %s AND c.user_id = %s AND sub.date = %s""",
        (teacher_id, user_id, date),
    ).fetchall()


# ---- Planned leave ----


def create_leave(conn: psycopg.Connection, teacher_id: int, start_date: str, end_date: str, reason: str) -> int:
    row = conn.execute(
        "INSERT INTO tt_leave (teacher_id, start_date, end_date, reason, created_at) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (teacher_id, start_date, end_date, reason, datetime.now(timezone.utc).isoformat()),
    ).fetchone()
    return row["id"]


def list_leaves(conn: psycopg.Connection, user_id: int) -> list[dict]:
    return conn.execute(
        """SELECT l.id, l.teacher_id, t.name AS teacher_name, t.code AS teacher_code, l.start_date, l.end_date, l.reason
           FROM tt_leave l JOIN tt_teacher t ON t.id = l.teacher_id
           WHERE t.user_id = %s ORDER BY l.start_date""",
        (user_id,),
    ).fetchall()


def get_leave(conn: psycopg.Connection, leave_id: int) -> dict | None:
    return conn.execute(
        """SELECT l.id, l.teacher_id, t.name AS teacher_name, t.code AS teacher_code, l.start_date, l.end_date, l.reason
           FROM tt_leave l JOIN tt_teacher t ON t.id = l.teacher_id WHERE l.id = %s""",
        (leave_id,),
    ).fetchone()


def delete_leave(conn: psycopg.Connection, user_id: int, leave_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM tt_leave WHERE id = %s AND teacher_id IN (SELECT id FROM tt_teacher WHERE user_id = %s)", (leave_id, user_id)
    )
    return cur.rowcount > 0


def pending_substitution_context(conn: psycopg.Connection, user_id: int, start_date: str, end_date: str) -> dict:
    """Everything pending_substitution_needs() needs to rank a substitute
    for every (leave teacher, weekday, period) slot a batch of leaves
    touches, fetched as a handful of account-wide queries instead of one
    round trip per slot — the naive per-slot version took over a minute
    against a remote Postgres pooler once a leave spanned more than a
    couple of days."""
    teachers = list_teachers(conn, user_id)

    entries_by_teacher_day: dict[tuple[int, str], list[dict]] = {}
    busy_by_day_period: dict[tuple[str, int], set[int]] = {}
    teachers_by_class: dict[int, set[int]] = {}
    for r in conn.execute(
        """SELECT te.teacher_id, te.day, te.period, te.class_id, c.grade, c.section, te.subject_id, s.name AS subject_name
           FROM tt_timetable_entry te
           JOIN tt_class c ON c.id = te.class_id
           JOIN tt_subject s ON s.id = te.subject_id
           WHERE c.user_id = %s""",
        (user_id,),
    ).fetchall():
        if r["teacher_id"] is not None:
            entries_by_teacher_day.setdefault((r["teacher_id"], r["day"]), []).append(r)
            busy_by_day_period.setdefault((r["day"], r["period"]), set()).add(r["teacher_id"])
            teachers_by_class.setdefault(r["class_id"], set()).add(r["teacher_id"])

    existing_substitutions: set[tuple[int, str, int]] = set()
    busy_substituting_by_date_period: dict[tuple[str, int], set[int]] = {}
    for r in conn.execute(
        """SELECT sub.class_id, sub.date, sub.period, sub.substitute_teacher_id
           FROM tt_substitution sub
           JOIN tt_class c ON c.id = sub.class_id
           WHERE c.user_id = %s AND sub.date BETWEEN %s AND %s""",
        (user_id, start_date, end_date),
    ).fetchall():
        existing_substitutions.add((r["class_id"], r["date"], r["period"]))
        busy_substituting_by_date_period.setdefault((r["date"], r["period"]), set()).add(r["substitute_teacher_id"])

    same_subject_by_subject: dict[int, set[int]] = {}
    for r in conn.execute(
        """SELECT ts.subject_id, ts.teacher_id FROM tt_teacher_subject ts
           JOIN tt_teacher t ON t.id = ts.teacher_id WHERE t.user_id = %s""",
        (user_id,),
    ).fetchall():
        same_subject_by_subject.setdefault(r["subject_id"], set()).add(r["teacher_id"])

    return {
        "teachers": teachers,
        "entries_by_teacher_day": entries_by_teacher_day,
        "busy_by_day_period": busy_by_day_period,
        "teachers_by_class": teachers_by_class,
        "existing_substitutions": existing_substitutions,
        "busy_substituting_by_date_period": busy_substituting_by_date_period,
        "same_subject_by_subject": same_subject_by_subject,
    }
