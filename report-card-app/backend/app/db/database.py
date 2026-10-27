from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import DATABASE_URL
from app.db.subject_blueprint_seed import seed as seed_subject_blueprint
from app.db.syllabus_seed import seed as seed_syllabus

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


def _migrate_tts_audio_cache(conn: psycopg.Connection) -> None:
    """Adds `content_key` to a pre-existing `tts_audio_cache` table (see
    schema.sql for what it's for). Rows written before this migration keep
    a NULL content_key and are simply never cleaned up — harmless, since
    they're still valid cached audio for whatever text hashed into them."""
    conn.execute("ALTER TABLE tts_audio_cache ADD COLUMN IF NOT EXISTS content_key TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tts_audio_cache_content_key ON tts_audio_cache (content_key)")


def _migrate_class_level(conn: psycopg.Connection) -> None:
    """Adds `class_level` to pre-existing `batch` and `syllabus_chapter`
    tables (see schema.sql). Defaulting both to '10' means every batch and
    syllabus row seeded before this migration — all of which really are
    SSC/10th — keeps working with the syllabus-aware study plan without
    needing a manual fix."""
    conn.execute("ALTER TABLE batch ADD COLUMN IF NOT EXISTS class_level TEXT NOT NULL DEFAULT '10'")
    conn.execute("ALTER TABLE syllabus_chapter ADD COLUMN IF NOT EXISTS class_level TEXT NOT NULL DEFAULT '10'")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_syllabus_chapter_lookup ON syllabus_chapter(class_level, subject)")


def _migrate_tt_school_config(conn: psycopg.Connection) -> None:
    """Adds `start_time`/`end_time`/`breaks` to a pre-existing
    `tt_school_config` table (see schema.sql) — added after the Timetable
    Creator's first deploy, which only had working_days/periods_per_day."""
    conn.execute("ALTER TABLE tt_school_config ADD COLUMN IF NOT EXISTS start_time TEXT NOT NULL DEFAULT '09:15'")
    conn.execute("ALTER TABLE tt_school_config ADD COLUMN IF NOT EXISTS end_time TEXT NOT NULL DEFAULT '16:00'")
    conn.execute("ALTER TABLE tt_school_config ADD COLUMN IF NOT EXISTS breaks TEXT NOT NULL DEFAULT '[]'")


def _migrate_tt_phone_and_excluded_periods(conn: psycopg.Connection) -> None:
    """Adds `tt_teacher.phone` (for substitute-assignment SMS alerts) and
    `tt_subject.excluded_periods` (e.g. "Games never in period 1") to
    tables that pre-date both features."""
    conn.execute("ALTER TABLE tt_teacher ADD COLUMN IF NOT EXISTS phone TEXT NOT NULL DEFAULT ''")
    conn.execute("ALTER TABLE tt_subject ADD COLUMN IF NOT EXISTS excluded_periods TEXT NOT NULL DEFAULT '[]'")


def _migrate_batch_source_sync(conn: psycopg.Connection) -> None:
    """Adds the columns "Sync now" / Drive-folder import need to a
    pre-existing `batch` table (see schema.sql) — every batch created
    before this migration defaults to source_type='file', which is
    correct: there's nothing to re-fetch for a plain upload."""
    conn.execute("ALTER TABLE batch ADD COLUMN IF NOT EXISTS source_type TEXT NOT NULL DEFAULT 'file'")
    conn.execute("ALTER TABLE batch ADD COLUMN IF NOT EXISTS source_ref TEXT")
    conn.execute("ALTER TABLE batch ADD COLUMN IF NOT EXISTS source_mime_type TEXT")
    conn.execute("ALTER TABLE batch ADD COLUMN IF NOT EXISTS source_folder_id TEXT")
    conn.execute("ALTER TABLE batch ADD COLUMN IF NOT EXISTS last_synced_at TEXT")


def init_db() -> None:
    with get_connection() as conn:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        for statement in schema_sql.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(statement)
        _migrate_student_phone(conn)
        _migrate_tts_audio_cache(conn)
        _migrate_class_level(conn)
        _migrate_tt_school_config(conn)
        _migrate_tt_phone_and_excluded_periods(conn)
        _migrate_batch_source_sync(conn)
        seed_syllabus(conn)
        seed_subject_blueprint(conn)
        conn.commit()


@contextmanager
def session():
    """Borrows a connection from the pool for the duration of one request.
    Commits on a clean exit, rolls back on any exception — same contract
    the rest of the app already relies on, just backed by a reused
    connection instead of a fresh one each time."""
    with get_pool().connection() as conn:
        yield conn
