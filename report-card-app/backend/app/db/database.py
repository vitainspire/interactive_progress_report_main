from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import DATABASE_URL

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# A small pool of persistent connections to Supabase, reused across
# requests — opening a brand-new TCP+TLS+auth connection per request (as a
# single `psycopg.connect()` per call would) adds seconds of latency to
# every API call once the database isn't on localhost anymore.
_pool: ConnectionPool | None = None

# prepare_threshold=None disables psycopg's server-side prepared-statement
# caching — required when connecting through a transaction-mode pooler
# (Supabase's Supavisor, PgBouncer, etc.), since a prepared statement from
# one query can silently land on a different backend connection than the
# one that created it, causing intermittent "prepared statement does not
# exist" errors under real traffic.
_CONNECT_KWARGS = {"row_factory": dict_row, "prepare_threshold": None}


def _require_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. This app stores its data in Postgres (e.g. a Supabase project) — "
            "set DATABASE_URL to that project's connection string before starting the backend."
        )
    return DATABASE_URL


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            _require_database_url(),
            min_size=1,
            max_size=5,
            kwargs=_CONNECT_KWARGS,
            open=True,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_connection() -> psycopg.Connection:
    """A standalone, non-pooled connection — used for one-off scripts and
    schema setup (init_db), not the per-request path (see session())."""
    return psycopg.connect(_require_database_url(), **_CONNECT_KWARGS)


def _migrate_student_phone(conn: psycopg.Connection) -> None:
    """Adds the `phone` column to a pre-existing `student` table. Postgres'
    own ADD COLUMN IF NOT EXISTS makes this a one-liner — no need for the
    PRAGMA table_info-style existence check SQLite required."""
    conn.execute("ALTER TABLE student ADD COLUMN IF NOT EXISTS phone TEXT NOT NULL DEFAULT ''")


def init_db() -> None:
    with get_connection() as conn:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        for statement in schema_sql.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(statement)
        _migrate_student_phone(conn)
        conn.commit()


@contextmanager
def session():
    """Borrows a connection from the pool for the duration of one request.
    Commits on a clean exit, rolls back on any exception — same contract
    the rest of the app already relies on, just backed by a reused
    connection instead of a fresh one each time."""
    with get_pool().connection() as conn:
        yield conn
