from datetime import datetime, timezone

import psycopg

from app.core.security import hash_password


def get_user_by_email(conn: psycopg.Connection, email: str) -> dict | None:
    return conn.execute("SELECT * FROM app_user WHERE email = %s", (email.lower().strip(),)).fetchone()


def get_user_by_id(conn: psycopg.Connection, user_id: int) -> dict | None:
    return conn.execute("SELECT * FROM app_user WHERE id = %s", (user_id,)).fetchone()


def create_user(conn: psycopg.Connection, email: str, password: str, display_name: str, school_name: str = "") -> int:
    row = conn.execute(
        "INSERT INTO app_user (email, password_hash, display_name, default_school_name, created_at) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (email.lower().strip(), hash_password(password), display_name.strip(), school_name.strip(), datetime.now(timezone.utc).isoformat()),
    ).fetchone()
    return row["id"]


def set_default_school_name(conn: psycopg.Connection, user_id: int, school_name: str) -> None:
    conn.execute("UPDATE app_user SET default_school_name = %s WHERE id = %s", (school_name.strip(), user_id))


def set_school_address(conn: psycopg.Connection, user_id: int, address: str) -> None:
    conn.execute("UPDATE app_user SET school_address = %s WHERE id = %s", (address.strip(), user_id))
