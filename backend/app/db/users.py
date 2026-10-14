from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from app.core.codes import generate_code
from app.db.repository import get_teacher_assignment_list


def _unique_school_code(conn: sqlite3.Connection) -> str:
    while True:
        code = generate_code()
        if not conn.execute("SELECT 1 FROM app_user WHERE school_code = ?", (code,)).fetchone():
            return code


def create_user(
    conn: sqlite3.Connection,
    email: str,
    password_hash: str,
    display_name: str,
    school_name: str | None = None,
    is_demo: bool = False,
    role: str = "admin",
    school_id: int | None = None,
    roll_no: str | None = None,
    student_id: int | None = None,
) -> int:
    school_code = _unique_school_code(conn) if role == "admin" else None
    cur = conn.execute(
        "INSERT INTO app_user (email, password_hash, display_name, school_name, is_demo, created_at, "
        "role, school_id, school_code, roll_no, student_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            email.lower().strip(),
            password_hash,
            display_name,
            school_name,
            int(is_demo),
            datetime.now(timezone.utc).isoformat(),
            role,
            school_id,
            school_code,
            roll_no,
            student_id,
        ),
    )
    return cur.lastrowid


def get_user_by_email(conn: sqlite3.Connection, email: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM app_user WHERE email = ?", (email.lower().strip(),)).fetchone()


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM app_user WHERE id = ?", (user_id,)).fetchone()


def get_demo_user(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM app_user WHERE is_demo = 1 LIMIT 1").fetchone()


def get_admin_by_school_code(conn: sqlite3.Connection, school_code: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM app_user WHERE role = 'admin' AND school_code = ?", (school_code.strip().upper(),)
    ).fetchone()


def get_student_login(conn: sqlite3.Connection, school_id: int, roll_no: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM app_user WHERE role = 'student' AND school_id = ? AND roll_no = ?", (school_id, roll_no)
    ).fetchone()


def list_school_accounts(conn: sqlite3.Connection, school_id: int) -> dict:
    teacher_rows = conn.execute(
        "SELECT id, email, display_name FROM app_user WHERE school_id = ? AND role = 'teacher' ORDER BY display_name",
        (school_id,),
    ).fetchall()
    teachers = [
        {
            "id": t["id"],
            "email": t["email"],
            "display_name": t["display_name"],
            "assignments": get_teacher_assignment_list(conn, t["id"]),
        }
        for t in teacher_rows
    ]
    students = conn.execute(
        "SELECT u.id, u.display_name, u.roll_no, u.student_id, s.section, s.class_id "
        "FROM app_user u JOIN student s ON s.id = u.student_id "
        "WHERE u.school_id = ? AND u.role = 'student' ORDER BY s.class_id, s.section, s.s_no",
        (school_id,),
    ).fetchall()
    return {"teachers": teachers, "students": students}


def create_teacher(
    conn: sqlite3.Connection, school_id: int, email: str, password_hash: str, display_name: str, assignments: list[dict]
) -> int:
    user_id = create_user(conn, email, password_hash, display_name, role="teacher", school_id=school_id)
    set_teacher_assignments(conn, user_id, assignments)
    return user_id


def set_teacher_assignments(conn: sqlite3.Connection, teacher_user_id: int, assignments: list[dict]) -> None:
    """assignments: [{"class_id": int, "section": str, "subjects": [str, ...], "restricted": bool}].
    A teacher can span several classes, each with its own sections. "subjects"
    is recorded for every section regardless of "restricted" (so it always
    shows up in the Accounts list); it only acts as an access filter for
    sections where "restricted" is true."""
    conn.execute("DELETE FROM teacher_section WHERE user_id = ?", (teacher_user_id,))
    conn.execute("DELETE FROM teacher_section_subject WHERE user_id = ?", (teacher_user_id,))
    for a in assignments:
        class_id = a["class_id"]
        section = a["section"].upper()
        conn.execute(
            "INSERT OR IGNORE INTO teacher_section (user_id, class_id, section, subjects_restricted) VALUES (?, ?, ?, ?)",
            (teacher_user_id, class_id, section, int(bool(a.get("restricted")))),
        )
        for subject in a.get("subjects", []):
            conn.execute(
                "INSERT OR IGNORE INTO teacher_section_subject (user_id, class_id, section, subject) VALUES (?, ?, ?, ?)",
                (teacher_user_id, class_id, section, subject.upper()),
            )


def create_student_login(
    conn: sqlite3.Connection, school_id: int, student_row: sqlite3.Row, password_hash: str
) -> tuple[int, str]:
    # Roll numbers must stay unique across every class in the school, not
    # just within one — a class gets its short_code folded in, EXCEPT the
    # one auto-migrated legacy class (short_code is deliberately left NULL
    # for it forever), which keeps the original 2-part format so old and
    # new-format rolls can never collide.
    class_row = conn.execute("SELECT short_code FROM school_class WHERE id = ?", (student_row["class_id"],)).fetchone()
    short_code = class_row["short_code"] if class_row else None
    if short_code:
        roll_no = f"{short_code}-{student_row['section']}-{student_row['s_no']}"
    else:
        roll_no = f"{student_row['section']}-{student_row['s_no']}"
    synthetic_email = f"student-{uuid.uuid4().hex}@local.invalid"
    user_id = create_user(
        conn,
        synthetic_email,
        password_hash,
        student_row["name"],
        role="student",
        school_id=school_id,
        roll_no=roll_no,
        student_id=student_row["id"],
    )
    return user_id, roll_no


def delete_account(conn: sqlite3.Connection, school_id: int, account_id: int) -> bool:
    """Removes a teacher/student login that belongs to this school. Returns
    False (no-op) if it doesn't, so the route can 404 instead of letting one
    school delete another's login."""
    row = conn.execute(
        "SELECT id FROM app_user WHERE id = ? AND school_id = ? AND role IN ('teacher', 'student')",
        (account_id, school_id),
    ).fetchone()
    if not row:
        return False
    conn.execute("DELETE FROM app_user WHERE id = ?", (account_id,))
    return True


def reset_password(conn: sqlite3.Connection, school_id: int, account_id: int, password_hash: str) -> bool:
    cur = conn.execute(
        "UPDATE app_user SET password_hash = ? WHERE id = ? AND school_id = ? AND role IN ('teacher', 'student')",
        (password_hash, account_id, school_id),
    )
    return cur.rowcount > 0
