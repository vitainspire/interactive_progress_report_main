import json
from dataclasses import dataclass
from datetime import datetime, timezone

import psycopg

from app.core.config import (
    DEFAULT_FA_MARKS_PER_SUBJECT,
    DEFAULT_FA_TOTAL,
    DEFAULT_SA_MARKS_PER_SUBJECT,
    DEFAULT_SA_TOTAL,
)

# Rows are inserted in chunks of this size rather than one row per round
# trip — against a local SQLite file the difference was invisible, but a
# 62-student sheet is ~2,000+ rows across its child tables, and one round
# trip per row to a remote database (even a fast one) adds up to minutes.
_INSERT_CHUNK_SIZE = 500


@dataclass
class BatchSettings:
    fa_total: float
    sa_total: float
    fa_marks_per_subject: float
    sa_marks_per_subject: float
    class_strength_override: int | None


def settings_from_row(row: dict) -> BatchSettings:
    return BatchSettings(
        fa_total=row["fa_total"],
        sa_total=row["sa_total"],
        fa_marks_per_subject=row["fa_marks_per_subject"],
        sa_marks_per_subject=row["sa_marks_per_subject"],
        class_strength_override=row["class_strength_override"],
    )


def _marks_value(marks_text: str, marks: float | None):
    if marks_text in ("AB", "-"):
        return marks_text
    return marks


def _chunks(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def _batch_insert(conn: psycopg.Connection, table: str, columns: list[str], rows: list[tuple]) -> None:
    """INSERTs `rows` in chunked multi-row statements instead of one
    statement per row."""
    if not rows:
        return
    col_list = ", ".join(columns)
    for chunk in _chunks(rows, _INSERT_CHUNK_SIZE):
        placeholders = ", ".join("(" + ", ".join(["%s"] * len(columns)) + ")" for _ in chunk)
        flat_params = [v for row in chunk for v in row]
        conn.execute(f"INSERT INTO {table} ({col_list}) VALUES {placeholders}", flat_params)


def _batch_insert_returning_ids(conn: psycopg.Connection, table: str, columns: list[str], rows: list[tuple]) -> list[int]:
    """Like _batch_insert, but returns the new id of each row, in the same
    order the rows were given — Postgres preserves VALUES-list order in a
    single-statement multi-row INSERT ... RETURNING."""
    if not rows:
        return []
    col_list = ", ".join(columns)
    ids: list[int] = []
    for chunk in _chunks(rows, _INSERT_CHUNK_SIZE):
        placeholders = ", ".join("(" + ", ".join(["%s"] * len(columns)) + ")" for _ in chunk)
        flat_params = [v for row in chunk for v in row]
        cur = conn.execute(f"INSERT INTO {table} ({col_list}) VALUES {placeholders} RETURNING id", flat_params)
        ids.extend(r["id"] for r in cur.fetchall())
    return ids


def create_batch(
    conn: psycopg.Connection,
    user_id: int,
    name: str,
    school_name: str,
    source_filename: str | None,
    parsed: dict,
    class_level: str = "10",
) -> int:
    """Persists a freshly-parsed sheet (see sheet_parser.parse_worksheet)
    as a new batch, normalized across student/exam_subject_result/
    exam_summary/attendance_month/attendance_total. All child rows are
    collected first and sent in a handful of batched statements rather
    than one round trip per row. `class_level` picks which class's syllabus
    (see syllabus_chapter) the study plan feature looks up for this batch —
    defaults to "10" since that's the only syllabus seeded so far."""
    exam_order = [e["key"] for e in parsed["exams"]]
    row = conn.execute(
        """INSERT INTO batch
           (user_id, name, school_name, fa_total, sa_total, fa_marks_per_subject, sa_marks_per_subject,
            class_strength_override, class_level, source_filename, exam_order, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s) RETURNING id""",
        (
            user_id,
            name,
            school_name,
            DEFAULT_FA_TOTAL,
            DEFAULT_SA_TOTAL,
            DEFAULT_FA_MARKS_PER_SUBJECT,
            DEFAULT_SA_MARKS_PER_SUBJECT,
            class_level,
            source_filename,
            json.dumps(parsed["exams"]),
            datetime.now(timezone.utc).isoformat(),
        ),
    ).fetchone()
    batch_id = row["id"]

    students = parsed["students"]
    student_rows = [(batch_id, s["name"], s["section"], s["roll"], s["father"], s.get("phone", ""), i) for i, s in enumerate(students)]
    student_ids = _batch_insert_returning_ids(
        conn, "student", ["batch_id", "name", "section", "roll_no", "father_name", "phone", "order_index"], student_rows
    )

    subject_rows: list[tuple] = []
    summary_rows: list[tuple] = []
    month_rows: list[tuple] = []
    total_rows: list[tuple] = []

    for student_id, s in zip(student_ids, students):
        for exam_key in exam_order:
            e = s["exams"].get(exam_key)
            if not e:
                continue
            for sub_index, x in enumerate(e["subjects"]):
                marks = x["marks"] if isinstance(x["marks"], (int, float)) else None
                marks_text = str(x["marks"]) if not isinstance(x["marks"], (int, float)) else ""
                subject_rows.append((student_id, exam_key, x["name"], marks, marks_text, x["grade"], sub_index))

            total_marks = e["total_marks"] if isinstance(e["total_marks"], (int, float)) else None
            total_marks_text = str(e["total_marks"]) if not isinstance(e["total_marks"], (int, float)) else ""
            rank = int(e["rank"]) if isinstance(e["rank"], (int, float)) else None
            summary_rows.append((student_id, exam_key, total_marks, total_marks_text, e["total_grade"], e["result"], rank))

        att = s.get("attendance")
        if att:
            for order_index2, m in enumerate(att["months"]):
                month_rows.append((student_id, m["month"], m["working_days"], m["attended"], order_index2))
            total_rows.append((student_id, att["total_working"], att["total_present"]))

    _batch_insert(conn, "exam_subject_result", ["student_id", "exam_code", "subject", "marks", "marks_text", "grade", "order_index"], subject_rows)
    _batch_insert(conn, "exam_summary", ["student_id", "exam_code", "total_marks", "total_marks_text", "total_grade", "result", "rank"], summary_rows)
    _batch_insert(conn, "attendance_month", ["student_id", "month", "working_days", "days_present", "order_index"], month_rows)
    _batch_insert(conn, "attendance_total", ["student_id", "total_working_days", "total_present"], total_rows)

    return batch_id


def list_batches(conn: psycopg.Connection, user_id: int) -> list[dict]:
    return conn.execute(
        """SELECT b.*, (SELECT COUNT(*) FROM student WHERE batch_id = b.id) AS student_count
           FROM batch b WHERE b.user_id = %s ORDER BY b.created_at DESC""",
        (user_id,),
    ).fetchall()


def get_batch(conn: psycopg.Connection, user_id: int, batch_id: int) -> dict | None:
    return conn.execute("SELECT * FROM batch WHERE id = %s AND user_id = %s", (batch_id, user_id)).fetchone()


def update_batch_settings(conn: psycopg.Connection, batch_id: int, fields: dict) -> None:
    cols = []
    values = []
    for key in ("name", "school_name", "fa_total", "sa_total", "fa_marks_per_subject", "sa_marks_per_subject", "class_strength_override", "class_level"):
        if key in fields:
            cols.append(f"{key} = %s")
            values.append(fields[key])
    if not cols:
        return
    values.append(batch_id)
    conn.execute(f"UPDATE batch SET {', '.join(cols)} WHERE id = %s", values)


def delete_batch(conn: psycopg.Connection, user_id: int, batch_id: int) -> bool:
    cur = conn.execute("DELETE FROM batch WHERE id = %s AND user_id = %s", (batch_id, user_id))
    return cur.rowcount > 0


def list_students_brief(conn: psycopg.Connection, batch_id: int) -> list[dict]:
    return conn.execute("SELECT id, name, section, roll_no, phone FROM student WHERE batch_id = %s ORDER BY order_index", (batch_id,)).fetchall()


def get_student(conn: psycopg.Connection, student_id: int) -> dict | None:
    return conn.execute("SELECT * FROM student WHERE id = %s", (student_id,)).fetchone()


def get_student_in_batch(conn: psycopg.Connection, batch_id: int, student_id: int) -> dict | None:
    return conn.execute("SELECT * FROM student WHERE id = %s AND batch_id = %s", (student_id, batch_id)).fetchone()


def load_batch_students(conn: psycopg.Connection, batch_id: int, student_ids: list[int] | None = None) -> list[dict]:
    """Reconstructs the parsed-sheet student shape (see sheet_parser) from
    the normalized tables, for the report renderer / analysis function."""
    student_rows = conn.execute("SELECT * FROM student WHERE batch_id = %s ORDER BY order_index", (batch_id,)).fetchall()
    if student_ids is not None:
        wanted = set(student_ids)
        student_rows = [r for r in student_rows if r["id"] in wanted]
    if not student_rows:
        return []
    ids = [r["id"] for r in student_rows]
    placeholders = ",".join(["%s"] * len(ids))

    subjects_by_student: dict[int, list[dict]] = {}
    for row in conn.execute(
        f"SELECT * FROM exam_subject_result WHERE student_id IN ({placeholders}) ORDER BY student_id, exam_code, order_index", ids
    ):
        subjects_by_student.setdefault(row["student_id"], []).append(row)

    summaries_by_student: dict[int, list[dict]] = {}
    for row in conn.execute(f"SELECT * FROM exam_summary WHERE student_id IN ({placeholders})", ids):
        summaries_by_student.setdefault(row["student_id"], []).append(row)

    months_by_student: dict[int, list[dict]] = {}
    for row in conn.execute(f"SELECT * FROM attendance_month WHERE student_id IN ({placeholders}) ORDER BY student_id, order_index", ids):
        months_by_student.setdefault(row["student_id"], []).append(row)

    totals_by_student: dict[int, dict] = {}
    for row in conn.execute(f"SELECT * FROM attendance_total WHERE student_id IN ({placeholders})", ids):
        totals_by_student[row["student_id"]] = row

    out = []
    for srow in student_rows:
        sid = srow["id"]
        exams: dict[str, dict] = {}
        for sum_row in summaries_by_student.get(sid, []):
            exams[sum_row["exam_code"]] = {
                "subjects": [],
                "total_marks": _marks_value(sum_row["total_marks_text"], sum_row["total_marks"]),
                "total_grade": sum_row["total_grade"],
                "result": sum_row["result"],
                "rank": sum_row["rank"] if sum_row["rank"] is not None else "-",
            }
        for sub_row in subjects_by_student.get(sid, []):
            exam = exams.setdefault(
                sub_row["exam_code"], {"subjects": [], "total_marks": "-", "total_grade": "-", "result": "", "rank": "-"}
            )
            exam["subjects"].append({"name": sub_row["subject"], "marks": _marks_value(sub_row["marks_text"], sub_row["marks"]), "grade": sub_row["grade"]})

        student = {
            "id": sid,
            "name": srow["name"],
            "section": srow["section"],
            "roll": srow["roll_no"],
            "father": srow["father_name"],
            "exams": exams,
        }
        months = months_by_student.get(sid)
        if months:
            total_row = totals_by_student.get(sid)
            student["attendance"] = {
                "months": [{"month": m["month"], "working_days": m["working_days"], "attended": m["days_present"]} for m in months],
                "total_present": total_row["total_present"] if total_row else sum(m["days_present"] or 0 for m in months),
                "total_working": total_row["total_working_days"] if total_row else sum(m["working_days"] or 0 for m in months),
            }
        out.append(student)
    return out
