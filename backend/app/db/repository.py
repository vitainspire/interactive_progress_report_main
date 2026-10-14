from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app.db.school_classes import add_class_sections_if_missing
from app.parsing.xlsx_parser import ParseResult, subject_max_marks

SectionFilter = str | list[str] | None


def _section_filter(column: str, section: SectionFilter) -> tuple[str, list]:
    """Build an "AND <column> = ?" / "AND <column> IN (...)" clause for a
    single section (admin/teacher query param) or a list of sections (a
    teacher's full allowed set, when none was explicitly requested).

    The list check MUST come before the generic falsy check below — a bare
    `if not section` would treat an empty list the same as None ("no
    filter", i.e. every section), when an empty list from a teacher with
    zero assigned sections in this class must instead match nothing at
    all. Getting this backwards leaked a whole class's roster to a teacher
    who had no business seeing it."""
    if isinstance(section, (list, tuple, set)):
        sections = [s.upper() for s in section]
        if not sections:
            return " AND 1=0", []
        placeholders = ",".join("?" for _ in sections)
        return f" AND {column} IN ({placeholders})", sections
    if not section:
        return "", []
    return f" AND {column} = ?", [section.upper()]


def replace_dataset(conn: sqlite3.Connection, user_id: int, class_id: int, filename: str, parsed: ParseResult) -> int:
    """Wipe this ONE CLASS's current snapshot and load a freshly parsed
    workbook in its place — scoped to (user_id, class_id), so uploading one
    class's sheet never touches another class under the same school."""
    cur = conn.cursor()
    for table in ("exam_result", "exam_summary", "attendance_month", "attendance_summary", "staff", "phase", "student"):
        cur.execute(f"DELETE FROM {table} WHERE user_id = ? AND class_id = ?", (user_id, class_id))

    # The admin may have predefined fewer/different sections than the sheet
    # actually contains — grow the list rather than block the upload.
    add_class_sections_if_missing(conn, class_id, sorted({s.section for s in parsed.students if s.section}))

    cur.execute(
        "INSERT INTO import_batch (user_id, class_id, filename, imported_at, total_students) VALUES (?, ?, ?, ?, ?)",
        (user_id, class_id, filename, datetime.now(timezone.utc).isoformat(), len(parsed.students)),
    )
    batch_id = cur.lastrowid

    for phase in parsed.phases:
        cur.execute(
            "INSERT INTO phase (user_id, class_id, code, label, order_index) VALUES (?, ?, ?, ?, ?)",
            (user_id, class_id, phase.code, phase.label, phase.order_index),
        )

    for entry in parsed.staff:
        cur.execute(
            "INSERT INTO staff (user_id, class_id, section, subject, teacher_name) VALUES (?, ?, ?, ?, ?)",
            (user_id, class_id, entry.section, entry.subject, entry.teacher_name),
        )

    if parsed.headmaster_name:
        cur.execute(
            "INSERT INTO settings (user_id, key, value) VALUES (?, 'headmaster_name', ?) "
            "ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value",
            (user_id, parsed.headmaster_name),
        )

    for student in parsed.students:
        cur.execute(
            "INSERT INTO student (user_id, class_id, s_no, section, name, gender, father_name, mother_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, class_id, student.s_no, student.section, student.name, student.gender, student.father_name, student.mother_name),
        )
        student_id = cur.lastrowid

        for phase_code, exam in student.exams.items():
            for subj in exam.subjects:
                cur.execute(
                    "INSERT INTO exam_result (user_id, class_id, student_id, phase_code, subject, marks, max_marks, grade) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, class_id, student_id, phase_code, subj.subject, subj.marks, subject_max_marks(phase_code, subj.subject), subj.grade),
                )
            max_total = sum(subject_max_marks(phase_code, s.subject) for s in exam.subjects) or None
            cur.execute(
                "INSERT INTO exam_summary (user_id, class_id, student_id, phase_code, total_marks, max_total, total_grade, result, rank) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, class_id, student_id, phase_code, exam.total_marks, max_total, exam.total_grade, exam.result, exam.rank),
            )

        for month in student.attendance:
            cur.execute(
                "INSERT INTO attendance_month (user_id, class_id, student_id, month, days_present, working_days) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, class_id, student_id, month.month, month.days_present, month.working_days),
            )
        if student.total_present is not None or student.total_working_days is not None:
            cur.execute(
                "INSERT INTO attendance_summary (student_id, user_id, class_id, total_present, total_working_days) VALUES (?, ?, ?, ?, ?)",
                (student_id, user_id, class_id, student.total_present, student.total_working_days),
            )

    return batch_id


def get_setting(conn: sqlite3.Connection, user_id: int, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE user_id = ? AND key = ?", (user_id, key)).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, user_id: int, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (user_id, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value",
        (user_id, key, value),
    )


def list_phases(conn: sqlite3.Connection, user_id: int, class_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM phase WHERE user_id = ? AND class_id = ? ORDER BY order_index", (user_id, class_id)
    ).fetchall()


def total_student_count(conn: sqlite3.Connection, user_id: int, class_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) AS n FROM student WHERE user_id = ? AND class_id = ?", (user_id, class_id)
    ).fetchone()["n"]


def list_sections(conn: sqlite3.Connection, user_id: int, class_id: int) -> list[str]:
    """The admin-defined section list for this class (set at class creation,
    auto-grown by upload) — not derived from `student` rows, so sections
    exist (and can have teachers assigned) even before any data is
    uploaded. Joins through school_class to keep this scoped to the right
    school, since class_section itself has no user_id column."""
    rows = conn.execute(
        "SELECT cs.section FROM class_section cs JOIN school_class sc ON sc.id = cs.class_id "
        "WHERE sc.user_id = ? AND cs.class_id = ? ORDER BY cs.order_index",
        (user_id, class_id),
    ).fetchall()
    return [r["section"] for r in rows]


def list_students(conn: sqlite3.Connection, user_id: int, class_id: int, section: SectionFilter = None, search: str | None = None) -> list[sqlite3.Row]:
    """Students plus a glanceable status: latest phase's result and attendance %,
    so a list view can show a pass/fail/attention indicator without the viewer
    having to open each student or read any numbers."""
    query = """
        SELECT s.*,
               latest.phase_code AS latest_phase_code,
               latest.result AS latest_result,
               latest.total_marks AS latest_total_marks,
               latest.max_total AS latest_max_total,
               att.total_present,
               att.total_working_days
        FROM student s
        LEFT JOIN (
            SELECT es.student_id, es.phase_code, es.result, es.total_marks, es.max_total
            FROM exam_summary es
            JOIN phase p ON p.user_id = es.user_id AND p.class_id = es.class_id AND p.code = es.phase_code
            WHERE es.user_id = ? AND es.class_id = ? AND p.order_index = (
                SELECT MAX(p2.order_index) FROM exam_summary es2
                JOIN phase p2 ON p2.user_id = es2.user_id AND p2.class_id = es2.class_id AND p2.code = es2.phase_code
                WHERE es2.student_id = es.student_id
            )
        ) latest ON latest.student_id = s.id
        LEFT JOIN attendance_summary att ON att.student_id = s.id
        WHERE s.user_id = ? AND s.class_id = ?
    """
    params: list = [user_id, class_id, user_id, class_id]
    clause, clause_params = _section_filter("s.section", section)
    query += clause
    params.extend(clause_params)
    if search:
        query += " AND s.name LIKE ?"
        params.append(f"%{search.upper()}%")
    query += " ORDER BY s.section, s.s_no"
    return conn.execute(query, params).fetchall()


def get_student(conn: sqlite3.Connection, user_id: int, class_id: int, student_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM student WHERE id = ? AND user_id = ? AND class_id = ?", (student_id, user_id, class_id)
    ).fetchone()


def get_student_any_class(conn: sqlite3.Connection, user_id: int, student_id: int) -> sqlite3.Row | None:
    """Looks up a student without knowing its class ahead of time — used
    for the single-student routes (/students/{id}, its report), which
    derive the class from the student itself (every role: admin, a
    teacher whose assignment is then checked against that class, or the
    student viewing their own row) rather than requiring a class_id query
    param the way the "browse a whole class" endpoints do."""
    return conn.execute("SELECT * FROM student WHERE id = ? AND user_id = ?", (student_id, user_id)).fetchone()


def get_student_exam_results(conn: sqlite3.Connection, user_id: int, class_id: int, student_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM exam_result WHERE student_id = ? AND user_id = ? AND class_id = ? ORDER BY phase_code, subject",
        (student_id, user_id, class_id),
    ).fetchall()


def get_student_exam_summaries(conn: sqlite3.Connection, user_id: int, class_id: int, student_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT es.*, p.order_index FROM exam_summary es "
        "JOIN phase p ON p.user_id = es.user_id AND p.class_id = es.class_id AND p.code = es.phase_code "
        "WHERE es.student_id = ? AND es.user_id = ? AND es.class_id = ? ORDER BY p.order_index",
        (student_id, user_id, class_id),
    ).fetchall()


def get_student_attendance(conn: sqlite3.Connection, user_id: int, class_id: int, student_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM attendance_month WHERE student_id = ? AND user_id = ? AND class_id = ? ORDER BY id",
        (student_id, user_id, class_id),
    ).fetchall()


def get_student_attendance_summary(conn: sqlite3.Connection, user_id: int, class_id: int, student_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM attendance_summary WHERE student_id = ? AND user_id = ? AND class_id = ?",
        (student_id, user_id, class_id),
    ).fetchone()


def get_staff_for_section(conn: sqlite3.Connection, user_id: int, class_id: int, section: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM staff WHERE user_id = ? AND class_id = ? AND section = ? ORDER BY id",
        (user_id, class_id, section.upper()),
    ).fetchall()


def list_subjects(conn: sqlite3.Connection, user_id: int, class_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT subject FROM exam_result WHERE user_id = ? AND class_id = ? ORDER BY subject", (user_id, class_id)
    ).fetchall()
    return [r["subject"] for r in rows]


def class_summary(conn: sqlite3.Connection, user_id: int, class_id: int, phase_code: str, section: SectionFilter = None) -> dict:
    query = (
        "SELECT es.total_marks, es.max_total, es.result FROM exam_summary es "
        "JOIN student s ON s.id = es.student_id WHERE es.user_id = ? AND es.class_id = ? AND es.phase_code = ?"
    )
    params: list = [user_id, class_id, phase_code]
    clause, clause_params = _section_filter("s.section", section)
    query += clause
    params.extend(clause_params)
    rows = conn.execute(query, params).fetchall()
    totals = [r["total_marks"] for r in rows if r["total_marks"] is not None]
    passed = sum(1 for r in rows if (r["result"] or "").upper() == "PASS")
    failed = sum(1 for r in rows if (r["result"] or "").upper() == "FAIL")
    return {
        "phase_code": phase_code,
        "section": section,
        "student_count": len(rows),
        "average_total": (sum(totals) / len(totals)) if totals else None,
        "max_total": rows[0]["max_total"] if rows else None,
        "passed": passed,
        "failed": failed,
    }


def subject_stats(conn: sqlite3.Connection, user_id: int, class_id: int, phase_code: str, subject: str, section: SectionFilter = None) -> dict:
    query = (
        "SELECT er.marks, er.max_marks, er.grade, s.name, s.section FROM exam_result er "
        "JOIN student s ON s.id = er.student_id WHERE er.user_id = ? AND er.class_id = ? AND er.phase_code = ? AND er.subject = ?"
    )
    params: list = [user_id, class_id, phase_code, subject.upper()]
    clause, clause_params = _section_filter("s.section", section)
    query += clause
    params.extend(clause_params)
    rows = conn.execute(query, params).fetchall()
    marks = [r["marks"] for r in rows if r["marks"] is not None]
    if not marks:
        return {"phase_code": phase_code, "subject": subject, "section": section, "count": 0}
    best = max(rows, key=lambda r: (r["marks"] is not None, r["marks"]))
    worst = min(rows, key=lambda r: (r["marks"] is None, r["marks"] if r["marks"] is not None else 1e9))
    return {
        "phase_code": phase_code,
        "subject": subject,
        "section": section,
        "count": len(marks),
        "average": sum(marks) / len(marks),
        "max_marks": rows[0]["max_marks"],
        "highest": {"name": best["name"], "marks": best["marks"]},
        "lowest": {"name": worst["name"], "marks": worst["marks"]},
    }


def students_failed(conn: sqlite3.Connection, user_id: int, class_id: int, phase_code: str | None, subject: str | None, section: SectionFilter) -> list[sqlite3.Row]:
    query = (
        "SELECT er.*, s.name, s.section FROM exam_result er JOIN student s ON s.id = er.student_id "
        "WHERE er.user_id = ? AND er.class_id = ? AND UPPER(er.grade) IN ('D2', 'F', 'FAIL')"
    )
    params: list = [user_id, class_id]
    if phase_code:
        query += " AND er.phase_code = ?"
        params.append(phase_code)
    if subject:
        query += " AND er.subject = ?"
        params.append(subject.upper())
    clause, clause_params = _section_filter("s.section", section)
    query += clause
    params.extend(clause_params)
    query += " ORDER BY s.section, s.name"
    return conn.execute(query, params).fetchall()


def top_students(conn: sqlite3.Connection, user_id: int, class_id: int, phase_code: str, section: SectionFilter, limit: int) -> list[sqlite3.Row]:
    query = (
        "SELECT es.*, s.name, s.section FROM exam_summary es JOIN student s ON s.id = es.student_id "
        "WHERE es.user_id = ? AND es.class_id = ? AND es.phase_code = ? AND es.rank IS NOT NULL"
    )
    params: list = [user_id, class_id, phase_code]
    clause, clause_params = _section_filter("s.section", section)
    query += clause
    params.extend(clause_params)
    query += " ORDER BY es.rank LIMIT ?"
    params.append(limit)
    return conn.execute(query, params).fetchall()


def get_teacher_sections(conn: sqlite3.Connection, teacher_user_id: int, class_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT section FROM teacher_section WHERE user_id = ? AND class_id = ? ORDER BY section",
        (teacher_user_id, class_id),
    ).fetchall()
    return [r["section"] for r in rows]


def get_teacher_classes(conn: sqlite3.Connection, teacher_user_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT DISTINCT class_id FROM teacher_section WHERE user_id = ? ORDER BY class_id", (teacher_user_id,)
    ).fetchall()
    return [r["class_id"] for r in rows]


def get_teacher_assignments(conn: sqlite3.Connection, teacher_user_id: int, class_id: int) -> dict[str, dict]:
    """{section: {"restricted": bool, "subjects": [str, ...]}} for ONE class
    — "subjects" is always populated for display, but only acts as an
    access filter when "restricted" is true (set per section by the admin).
    A teacher spanning several classes has one such map per class; see
    get_teacher_classes for the list of classes they're assigned to at all."""
    sections = conn.execute(
        "SELECT section, subjects_restricted FROM teacher_section WHERE user_id = ? AND class_id = ? ORDER BY section",
        (teacher_user_id, class_id),
    ).fetchall()
    subject_rows = conn.execute(
        "SELECT section, subject FROM teacher_section_subject WHERE user_id = ? AND class_id = ? ORDER BY section, subject",
        (teacher_user_id, class_id),
    ).fetchall()
    subjects_by_section: dict[str, list[str]] = {}
    for r in subject_rows:
        subjects_by_section.setdefault(r["section"], []).append(r["subject"])
    return {
        s["section"]: {"restricted": bool(s["subjects_restricted"]), "subjects": subjects_by_section.get(s["section"], [])}
        for s in sections
    }


def get_teacher_assignment_list(conn: sqlite3.Connection, teacher_user_id: int) -> list[dict]:
    """Flat [{class_id, section, restricted, subjects}] across every class
    this teacher is assigned to — the shape used for display (the Accounts
    page, /auth/me), as opposed to get_teacher_assignments' per-class dict
    used by the authorization helpers in app/core/deps.py."""
    rows = conn.execute(
        "SELECT ts.class_id, ts.section, ts.subjects_restricted, GROUP_CONCAT(tss.subject) AS subjects "
        "FROM teacher_section ts LEFT JOIN teacher_section_subject tss "
        "ON tss.user_id = ts.user_id AND tss.class_id = ts.class_id AND tss.section = ts.section "
        "WHERE ts.user_id = ? GROUP BY ts.class_id, ts.section ORDER BY ts.class_id, ts.section",
        (teacher_user_id,),
    ).fetchall()
    return [
        {
            "class_id": r["class_id"],
            "section": r["section"],
            "restricted": bool(r["subjects_restricted"]),
            "subjects": r["subjects"].split(",") if r["subjects"] else [],
        }
        for r in rows
    ]


def teacher_allows_subject(assignments: dict[str, dict], sections, subject: str) -> bool:
    """True if, across the given sections (within whichever class
    `assignments` was already fetched for — see get_teacher_assignments),
    at least one of the teacher's assignments permits this subject
    (unrestricted sections always permit everything)."""
    subject = subject.upper()
    candidates = sections if isinstance(sections, (list, tuple, set)) else [sections]
    for sec in candidates:
        a = assignments.get(sec)
        if not a:
            continue
        if not a["restricted"] or subject in a["subjects"]:
            return True
    return False
