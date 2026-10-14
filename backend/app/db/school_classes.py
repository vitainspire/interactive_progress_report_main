from __future__ import annotations

import sqlite3
import string
from datetime import datetime, timezone


def generate_section_labels(count: int) -> list[str]:
    """A, B, C, ... Z — schools don't realistically run past 26 sections in
    one class, so this intentionally doesn't bother with AA/AB beyond that."""
    return list(string.ascii_uppercase[:count])


def list_class_sections(conn: sqlite3.Connection, class_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT section FROM class_section WHERE class_id = ? ORDER BY order_index", (class_id,)
    ).fetchall()
    return [r["section"] for r in rows]


def set_class_sections(conn: sqlite3.Connection, class_id: int, sections: list[str]) -> None:
    """Replaces the full section list for a class — used at creation time
    and when growing/shrinking the count later."""
    conn.execute("DELETE FROM class_section WHERE class_id = ?", (class_id,))
    for i, section in enumerate(sections):
        conn.execute(
            "INSERT INTO class_section (class_id, section, order_index) VALUES (?, ?, ?)", (class_id, section.upper(), i)
        )


def add_class_sections_if_missing(conn: sqlite3.Connection, class_id: int, sections: list[str]) -> None:
    """Grows a class's section list to include any of these not already
    present — used when an upload's sheet contains a section the admin
    didn't predefine, so the upload is never blocked by an incomplete list."""
    existing = set(list_class_sections(conn, class_id))
    next_index = conn.execute(
        "SELECT COALESCE(MAX(order_index), -1) + 1 AS n FROM class_section WHERE class_id = ?", (class_id,)
    ).fetchone()["n"]
    for section in sections:
        section = section.upper()
        if section in existing:
            continue
        conn.execute(
            "INSERT INTO class_section (class_id, section, order_index) VALUES (?, ?, ?)", (class_id, section, next_index)
        )
        existing.add(section)
        next_index += 1


def section_in_use(conn: sqlite3.Connection, class_id: int, section: str) -> bool:
    """True if a section has students or a teacher assignment — used to
    stop an admin from shrinking the section count out from under data."""
    section = section.upper()
    has_students = conn.execute(
        "SELECT 1 FROM student WHERE class_id = ? AND section = ? LIMIT 1", (class_id, section)
    ).fetchone()
    if has_students:
        return True
    has_teacher = conn.execute(
        "SELECT 1 FROM teacher_section WHERE class_id = ? AND section = ? LIMIT 1", (class_id, section)
    ).fetchone()
    return bool(has_teacher)


def list_classes(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM school_class WHERE user_id = ? ORDER BY order_index, id", (user_id,)
    ).fetchall()


def get_class(conn: sqlite3.Connection, user_id: int, class_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM school_class WHERE id = ? AND user_id = ?", (class_id, user_id)).fetchone()


def get_class_by_short_code(conn: sqlite3.Connection, user_id: int, short_code: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM school_class WHERE user_id = ? AND short_code = ?", (user_id, short_code)
    ).fetchone()


def create_class(conn: sqlite3.Connection, user_id: int, name: str, short_code: str) -> int:
    order_index = conn.execute(
        "SELECT COALESCE(MAX(order_index), -1) + 1 AS n FROM school_class WHERE user_id = ?", (user_id,)
    ).fetchone()["n"]
    cur = conn.execute(
        "INSERT INTO school_class (user_id, name, short_code, order_index, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, name, short_code, order_index, datetime.now(timezone.utc).isoformat()),
    )
    return cur.lastrowid


def update_class(conn: sqlite3.Connection, user_id: int, class_id: int, name: str | None = None, order_index: int | None = None) -> bool:
    """short_code is intentionally not editable here — it's baked into
    already-issued student roll numbers, so changing it after the fact
    would make those numbers inconsistent with the class's current code."""
    cls = get_class(conn, user_id, class_id)
    if not cls:
        return False
    conn.execute(
        "UPDATE school_class SET name = ?, order_index = ? WHERE id = ?",
        (name if name is not None else cls["name"], order_index if order_index is not None else cls["order_index"], class_id),
    )
    return True


def class_has_data(conn: sqlite3.Connection, class_id: int) -> bool:
    return bool(conn.execute("SELECT 1 FROM student WHERE class_id = ? LIMIT 1", (class_id,)).fetchone())


def delete_class(conn: sqlite3.Connection, user_id: int, class_id: int, force: bool = False) -> tuple[bool, str | None]:
    """Without force, refuses to delete a class that still has students —
    the caller should offer a force-delete path with a strong confirmation
    instead of silently wiping data. With force, every row scoped to this
    class cascades on delete (ON DELETE CASCADE from school_class) EXCEPT
    student-role app_user logins, whose student_id FK has no cascade —
    those are cleaned up explicitly here first, or they'd be left pointing
    at a student_id that no longer exists."""
    cls = get_class(conn, user_id, class_id)
    if not cls:
        return False, None
    if not force and class_has_data(conn, class_id):
        return False, "This class still has students — it can't be deleted while it has data. Use force delete to remove it and everything in it."
    if force:
        conn.execute(
            "DELETE FROM app_user WHERE role = 'student' AND student_id IN (SELECT id FROM student WHERE class_id = ?)",
            (class_id,),
        )
    conn.execute("DELETE FROM school_class WHERE id = ?", (class_id,))
    return True, None
