"""CRUD for subject_reference_document (a school's own uploaded syllabus/
exam-blueprint PDF or image, see schema.sql) plus the functions that write a
teacher-confirmed extraction into syllabus_chapter/subject_blueprint/
subject_exam_info scoped to that account. See
app/integrations/syllabus_extraction.py for how extracted_json is produced,
and app/api/reference_documents.py for the review/confirm endpoints that
call these."""
import json
from datetime import datetime, timezone

import psycopg


def create_reference_document(
    conn: psycopg.Connection,
    account_id: int,
    file_name: str,
    mime_type: str,
    file_bytes: bytes,
    source_drive_file_id: str | None,
    status: str,
    extracted_json: str | None,
    error: str | None,
) -> int:
    row = conn.execute(
        """INSERT INTO subject_reference_document
               (account_id, file_name, mime_type, file_bytes, source_drive_file_id, status, extracted_json, error, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING id""",
        (account_id, file_name, mime_type, file_bytes, source_drive_file_id, status, extracted_json, error, datetime.now(timezone.utc).isoformat()),
    ).fetchone()
    return row["id"]


def list_reference_documents(conn: psycopg.Connection, account_id: int, status: str | None = None) -> list[dict]:
    if status:
        return conn.execute(
            "SELECT id, file_name, mime_type, source_drive_file_id, status, extracted_json, error, created_at "
            "FROM subject_reference_document WHERE account_id = %s AND status = %s ORDER BY created_at DESC",
            (account_id, status),
        ).fetchall()
    return conn.execute(
        "SELECT id, file_name, mime_type, source_drive_file_id, status, extracted_json, error, created_at "
        "FROM subject_reference_document WHERE account_id = %s ORDER BY created_at DESC",
        (account_id,),
    ).fetchall()


def get_reference_document_by_drive_file_id(conn: psycopg.Connection, account_id: int, source_drive_file_id: str) -> dict | None:
    """Used to skip re-extracting (and re-billing the LLM for) a reference
    document already ingested from a prior import/sync of the same folder."""
    return conn.execute(
        "SELECT id, status FROM subject_reference_document WHERE account_id = %s AND source_drive_file_id = %s",
        (account_id, source_drive_file_id),
    ).fetchone()


def get_reference_document(conn: psycopg.Connection, account_id: int, doc_id: int) -> dict | None:
    return conn.execute(
        "SELECT id, file_name, mime_type, source_drive_file_id, status, extracted_json, error, created_at "
        "FROM subject_reference_document WHERE id = %s AND account_id = %s",
        (doc_id, account_id),
    ).fetchone()


def update_reference_document_review(conn: psycopg.Connection, account_id: int, doc_id: int, extracted_json: str) -> bool:
    """A teacher editing the extracted guess before confirming it."""
    cur = conn.execute(
        "UPDATE subject_reference_document SET extracted_json = %s WHERE id = %s AND account_id = %s",
        (extracted_json, doc_id, account_id),
    )
    return cur.rowcount > 0


def update_reference_document_result(
    conn: psycopg.Connection,
    account_id: int,
    doc_id: int,
    mime_type: str,
    file_bytes: bytes,
    status: str,
    extracted_json: str | None,
    error: str | None,
) -> None:
    """Re-processing a document that previously failed (e.g. a transient
    rate-limit, or a fixed version re-uploaded under the same Drive file id)
    updates its existing row in place, rather than inserting a duplicate —
    a retry would otherwise pile up a fresh failed row for the same file on
    every sync, since sync-folder gets called repeatedly until nothing's
    left to process (see continueReferenceDocumentSync on the frontend)."""
    conn.execute(
        """UPDATE subject_reference_document
               SET mime_type = %s, file_bytes = %s, status = %s, extracted_json = %s, error = %s
           WHERE id = %s AND account_id = %s""",
        (mime_type, file_bytes, status, extracted_json, error, doc_id, account_id),
    )


def set_reference_document_status(conn: psycopg.Connection, account_id: int, doc_id: int, status: str) -> bool:
    cur = conn.execute(
        "UPDATE subject_reference_document SET status = %s WHERE id = %s AND account_id = %s",
        (status, doc_id, account_id),
    )
    return cur.rowcount > 0


def count_syllabus_chapters_for_account(conn: psycopg.Connection, account_id: int, class_level: str, subject: str) -> int:
    row = conn.execute(
        "SELECT count(*) AS n FROM syllabus_chapter WHERE account_id = %s AND class_level = %s AND subject = %s",
        (account_id, class_level, subject),
    ).fetchone()
    return row["n"]


def count_subject_blueprint_for_account(conn: psycopg.Connection, account_id: int, class_level: str, subject: str) -> int:
    row = conn.execute(
        "SELECT count(*) AS n FROM subject_blueprint WHERE account_id = %s AND class_level = %s AND subject = %s",
        (account_id, class_level, subject),
    ).fetchone()
    return row["n"]


def replace_syllabus_chapters_for_account(
    conn: psycopg.Connection, account_id: int, class_level: str, subject: str, chapters: list[dict]
) -> None:
    """Confirming a syllabus document replaces whatever this account
    previously confirmed for this exact (class_level, subject) — "latest
    confirmed version wins" rather than accumulating duplicates across
    repeated uploads. Never touches the shared account_id IS NULL rows."""
    conn.execute(
        "DELETE FROM syllabus_chapter WHERE account_id = %s AND class_level = %s AND subject = %s",
        (account_id, class_level, subject),
    )
    for ch in chapters:
        conn.execute(
            """INSERT INTO syllabus_chapter
                   (class_level, subject, chapter_no, chapter_name, genre, theme, author, month, periods, page_range, account_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                class_level,
                subject,
                ch["chapter_no"],
                ch["chapter_name"],
                ch.get("genre"),
                ch.get("theme"),
                ch.get("author"),
                ch.get("month"),
                ch.get("periods"),
                ch.get("page_range"),
                account_id,
            ),
        )


def replace_subject_blueprint_for_account(
    conn: psycopg.Connection, account_id: int, class_level: str, subject: str, topics: list[dict]
) -> None:
    conn.execute(
        "DELETE FROM subject_blueprint WHERE account_id = %s AND class_level = %s AND subject = %s",
        (account_id, class_level, subject),
    )
    for order, topic in enumerate(topics):
        conn.execute(
            """INSERT INTO subject_blueprint (class_level, subject, topic_name, marks, choice_marks, sort_order, account_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (class_level, subject, topic["topic_name"], topic["marks"], topic.get("choice_marks"), order, account_id),
        )


def replace_subject_exam_info_for_account(
    conn: psycopg.Connection, account_id: int, class_level: str, subject: str, exam_format: str | None, tips: list[str]
) -> None:
    conn.execute(
        "DELETE FROM subject_exam_info WHERE account_id = %s AND class_level = %s AND subject = %s",
        (account_id, class_level, subject),
    )
    conn.execute(
        "INSERT INTO subject_exam_info (class_level, subject, exam_format, tips, account_id) VALUES (%s, %s, %s, %s, %s)",
        (class_level, subject, exam_format, json.dumps(tips), account_id),
    )
