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


def set_school_photo(conn: psycopg.Connection, user_id: int, photo_bytes: bytes, mime: str) -> None:
    conn.execute("UPDATE app_user SET school_photo = %s, school_photo_mime = %s WHERE id = %s", (photo_bytes, mime, user_id))


def clear_school_photo(conn: psycopg.Connection, user_id: int) -> None:
    conn.execute("UPDATE app_user SET school_photo = NULL, school_photo_mime = NULL WHERE id = %s", (user_id,))


def get_school_photo(conn: psycopg.Connection, user_id: int) -> tuple[bytes, str] | None:
    row = conn.execute("SELECT school_photo, school_photo_mime FROM app_user WHERE id = %s", (user_id,)).fetchone()
    if not row or row["school_photo"] is None:
        return None
    return bytes(row["school_photo"]), row["school_photo_mime"] or "image/jpeg"


def set_whatsapp_settings(conn: psycopg.Connection, user_id: int, language: str, channel_mode: str, default_country_code: str) -> None:
    conn.execute(
        "UPDATE app_user SET whatsapp_language = %s, whatsapp_channel_mode = %s, default_country_code = %s WHERE id = %s",
        (language, channel_mode, default_country_code.strip(), user_id),
    )
