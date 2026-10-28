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


def _migrate_drop_tts_audio_cache(conn: psycopg.Connection) -> None:
    """Drops `tts_audio_cache` (see app/integrations/tts_audio.py) — the
    app no longer caches TTS audio server-side at all: it ran on a
    free-tier Postgres instance not worth spending on a disposable cache
    that also held spoken PII (the student's/parent's name)."""
    conn.execute("DROP TABLE IF EXISTS tts_audio_cache")


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


def _migrate_school_address(conn: psycopg.Connection) -> None:
    """Adds an optional `school_address` to the pre-existing `app_user`
    table (see schema.sql) — used on the printed substitution sheet below
    the school name. Blank by default, and the sheet simply omits the line
    rather than forcing every account to fill it in before this feature
    can be used."""
    conn.execute("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS school_address TEXT NOT NULL DEFAULT ''")


def _migrate_school_photo(conn: psycopg.Connection) -> None:
    """Adds an optional `school_photo`/`school_photo_mime` to the
    pre-existing `app_user` table (see schema.sql) — the parent report's
    hero banner photo (app/reports/parent_report.py), uploaded once per
    account instead of every school sharing the same generic photo. NULL
    until a school uploads one, in which case the public report falls back
    to the shared default photo rather than a broken image."""
    conn.execute("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS school_photo BYTEA")
    conn.execute("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS school_photo_mime TEXT")


def _migrate_whatsapp_settings(conn: psycopg.Connection) -> None:
    """Adds per-school messaging settings to the pre-existing `app_user`
    table (see schema.sql) — this app's WhatsApp Business API account/
    phone number stays one shared platform-level credential (set via env
    vars, see app/core/config.py), but which approved template *language*
    to send in, whether to fall back to SMS at all, and which country code
    to assume for a bare 10-digit number are each school's own choice.
    whatsapp_channel_mode is 'whatsapp_then_sms' (today's existing
    behavior), 'whatsapp_only', or 'sms_only' — enforced at the Pydantic
    layer (app/api/auth.py), not here."""
    conn.execute("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS whatsapp_language TEXT NOT NULL DEFAULT 'te'")
    conn.execute("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS whatsapp_channel_mode TEXT NOT NULL DEFAULT 'whatsapp_then_sms'")
    conn.execute("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS default_country_code TEXT NOT NULL DEFAULT '91'")


def _migrate_subject_exam_info_pk(conn: psycopg.Connection) -> None:
    """subject_exam_info originally keyed on PRIMARY KEY (class_level,
    subject) — fine while every row was global, but it only allows one row
    per class+subject ever, which breaks the moment a school's own row needs
    to coexist with the shared default for that same class+subject. Replaces
    it with a surrogate id, matching syllabus_chapter/subject_blueprint's
    shape. Safe to run every startup: after the DROP there's guaranteed to
    be no primary key left (a table has at most one), so the ADD always
    succeeds."""
    conn.execute("ALTER TABLE subject_exam_info ADD COLUMN IF NOT EXISTS id INTEGER GENERATED ALWAYS AS IDENTITY")
    conn.execute("ALTER TABLE subject_exam_info DROP CONSTRAINT IF EXISTS subject_exam_info_pkey")
    conn.execute("ALTER TABLE subject_exam_info ADD PRIMARY KEY (id)")


def _migrate_syllabus_account_scope(conn: psycopg.Connection) -> None:
    """Adds an optional `account_id` to the three previously-global
    reference-data tables (see schema.sql) so a school can have its own
    syllabus/blueprint instead of everyone sharing the one hardcoded AP SSC
    dataset. Existing rows keep account_id NULL, which the lookup functions
    treat as "the shared default" — nothing already seeded changes meaning."""
    conn.execute("ALTER TABLE syllabus_chapter ADD COLUMN IF NOT EXISTS account_id INTEGER REFERENCES app_user(id) ON DELETE CASCADE")
    conn.execute("ALTER TABLE subject_blueprint ADD COLUMN IF NOT EXISTS account_id INTEGER REFERENCES app_user(id) ON DELETE CASCADE")
    conn.execute("ALTER TABLE subject_exam_info ADD COLUMN IF NOT EXISTS account_id INTEGER REFERENCES app_user(id) ON DELETE CASCADE")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_syllabus_chapter_account ON syllabus_chapter(account_id, class_level, subject)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subject_blueprint_account ON subject_blueprint(account_id, class_level, subject)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subject_exam_info_account ON subject_exam_info(account_id, class_level, subject)")


def init_db() -> None:
    with get_connection() as conn:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        for statement in schema_sql.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(statement)
        _migrate_student_phone(conn)
        _migrate_drop_tts_audio_cache(conn)
        _migrate_class_level(conn)
        _migrate_tt_school_config(conn)
        _migrate_tt_phone_and_excluded_periods(conn)
        _migrate_batch_source_sync(conn)
        _migrate_school_address(conn)
        _migrate_subject_exam_info_pk(conn)
        _migrate_syllabus_account_scope(conn)
        _migrate_school_photo(conn)
        _migrate_whatsapp_settings(conn)
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
