from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

Topic = tuple[str | None, str, int | None]  # (chapter_no, title, page)


def _insert_topics(conn: sqlite3.Connection, textbook_id: int, topics: list[Topic]) -> None:
    for i, (chapter_no, title, page) in enumerate(topics):
        conn.execute(
            "INSERT INTO textbook_topic (textbook_id, order_index, chapter_no, title, page) VALUES (?, ?, ?, ?, ?)",
            (textbook_id, i, chapter_no, title, page),
        )


def replace_textbook(conn: sqlite3.Connection, user_id: int, class_id: int, subject: str, filename: str, topics: list[Topic]) -> int:
    """Uploading again for the same class+subject replaces its topic list,
    same way a fresh workbook upload replaces the whole dataset."""
    subject = subject.upper()
    existing = conn.execute(
        "SELECT id FROM textbook WHERE user_id = ? AND class_id = ? AND subject = ?", (user_id, class_id, subject)
    ).fetchone()
    if existing:
        textbook_id = existing["id"]
        conn.execute("DELETE FROM textbook_topic WHERE textbook_id = ?", (textbook_id,))
        conn.execute(
            "UPDATE textbook SET filename = ?, uploaded_at = ? WHERE id = ?",
            (filename, datetime.now(timezone.utc).isoformat(), textbook_id),
        )
    else:
        cur = conn.execute(
            "INSERT INTO textbook (user_id, class_id, subject, filename, uploaded_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, class_id, subject, filename, datetime.now(timezone.utc).isoformat()),
        )
        textbook_id = cur.lastrowid
    _insert_topics(conn, textbook_id, topics)
    return textbook_id


def list_textbooks(conn: sqlite3.Connection, user_id: int, class_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM textbook WHERE user_id = ? AND class_id = ? ORDER BY subject", (user_id, class_id)
    ).fetchall()


def get_textbook(conn: sqlite3.Connection, user_id: int, class_id: int, subject: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM textbook WHERE user_id = ? AND class_id = ? AND subject = ?", (user_id, class_id, subject.upper())
    ).fetchone()


def get_textbook_topics(conn: sqlite3.Connection, user_id: int, class_id: int, subject: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT tt.* FROM textbook_topic tt JOIN textbook t ON t.id = tt.textbook_id "
        "WHERE t.user_id = ? AND t.class_id = ? AND t.subject = ? ORDER BY tt.order_index",
        (user_id, class_id, subject.upper()),
    ).fetchall()


def set_topics(conn: sqlite3.Connection, user_id: int, class_id: int, subject: str, topics: list[Topic]) -> bool:
    tb = get_textbook(conn, user_id, class_id, subject)
    if not tb:
        return False
    conn.execute("DELETE FROM textbook_topic WHERE textbook_id = ?", (tb["id"],))
    _insert_topics(conn, tb["id"], topics)
    return True


def delete_textbook(conn: sqlite3.Connection, user_id: int, class_id: int, subject: str) -> bool:
    cur = conn.execute(
        "DELETE FROM textbook WHERE user_id = ? AND class_id = ? AND subject = ?", (user_id, class_id, subject.upper())
    )
    return cur.rowcount > 0
