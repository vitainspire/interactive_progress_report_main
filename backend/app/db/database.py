import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.core.codes import generate_code
from app.core.config import DB_PATH

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate_app_user_roles(conn: sqlite3.Connection) -> None:
    """Adds the role/school_id/school_code/roll_no/student_id columns to a
    pre-existing app_user table. schema.sql's CREATE TABLE IF NOT EXISTS
    can't retrofit columns onto a table that already exists, so this runs
    its own idempotent ALTER TABLE statements instead. Order matters: the
    columns must exist before they're backfilled, and must be backfilled
    before the unique indexes on them are created."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(app_user)").fetchall()}

    if "role" not in existing:
        conn.execute("ALTER TABLE app_user ADD COLUMN role TEXT NOT NULL DEFAULT 'admin'")
    if "school_id" not in existing:
        conn.execute("ALTER TABLE app_user ADD COLUMN school_id INTEGER REFERENCES app_user(id)")
    if "school_code" not in existing:
        conn.execute("ALTER TABLE app_user ADD COLUMN school_code TEXT")
    if "roll_no" not in existing:
        conn.execute("ALTER TABLE app_user ADD COLUMN roll_no TEXT")
    if "student_id" not in existing:
        conn.execute("ALTER TABLE app_user ADD COLUMN student_id INTEGER REFERENCES student(id)")

    codeless_admins = conn.execute(
        "SELECT id FROM app_user WHERE role = 'admin' AND (school_code IS NULL OR school_code = '')"
    ).fetchall()
    for row in codeless_admins:
        while True:
            code = generate_code()
            clash = conn.execute("SELECT 1 FROM app_user WHERE school_code = ?", (code,)).fetchone()
            if not clash:
                break
        conn.execute("UPDATE app_user SET school_code = ? WHERE id = ?", (code, row["id"]))

    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_school_code ON app_user(school_code) WHERE school_code IS NOT NULL"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_school_rollno ON app_user(school_id, roll_no) WHERE roll_no IS NOT NULL"
    )


def _migrate_teacher_section(conn: sqlite3.Connection) -> None:
    """Adds subjects_restricted to a pre-existing teacher_section table."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(teacher_section)").fetchall()}
    if "subjects_restricted" not in existing:
        conn.execute("ALTER TABLE teacher_section ADD COLUMN subjects_restricted INTEGER NOT NULL DEFAULT 0")


# --- Multi-class migration -------------------------------------------------
#
# The app used to assume one class/grade per school account, with sections
# as the only subdivision. Making classes real means every class-scoped
# table needs a class_id. schema.sql already gives a FRESH install the
# final shape (class_id folded into phase/textbook/teacher_section's
# PK/UNIQUE, since two classes will always reuse the same phase codes like
# "FA1" and the same subject/section names). For an EXISTING database,
# schema.sql's CREATE TABLE IF NOT EXISTS can't retrofit a table that
# already exists under the old shape, so the functions below do it by hand,
# in dependency order:
#   1. _migrate_school_class — create exactly one legacy class per admin
#      account that already has data, named from their old class_label
#      setting, so upgrading preserves their existing single class exactly
#      as it was (they can rename it or add more classes afterward).
#   2. _migrate_class_scope_columns — simple nullable ADD COLUMN on tables
#      with a surrogate id PK (no rebuild needed), backfilled to each
#      admin's legacy class.
#   3. _migrate_phase_rebuild / _migrate_textbook_rebuild /
#      _migrate_teacher_section_class_rebuild — full table rebuilds for the
#      tables whose PK/UNIQUE would otherwise let two classes collide the
#      moment they share a phase code / subject / section (which they
#      always will). Needs the legacy class from step 1 to assign rebuilt
#      rows to.


def _migrate_school_class(conn: sqlite3.Connection) -> None:
    admins = conn.execute(
        "SELECT id FROM app_user WHERE role = 'admin' "
        "AND id NOT IN (SELECT DISTINCT user_id FROM school_class)"
    ).fetchall()
    for row in admins:
        user_id = row["id"]
        has_data = conn.execute("SELECT 1 FROM student WHERE user_id = ? LIMIT 1", (user_id,)).fetchone()
        if not has_data:
            continue  # nothing to migrate — they'll create their first class through the UI
        label_row = conn.execute(
            "SELECT value FROM settings WHERE user_id = ? AND key = 'class_label'", (user_id,)
        ).fetchone()
        name = (label_row["value"].strip() if label_row and label_row["value"] else "") or "Class 1"
        conn.execute(
            "INSERT INTO school_class (user_id, name, short_code, order_index, created_at) VALUES (?, ?, NULL, 0, ?)",
            (user_id, name, datetime.now(timezone.utc).isoformat()),
        )


def _migrate_class_scope_columns(conn: sqlite3.Connection) -> None:
    for table in ("student", "staff", "import_batch", "exam_result", "exam_summary", "attendance_month", "attendance_summary"):
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if "class_id" not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN class_id INTEGER REFERENCES school_class(id)")
        conn.execute(
            f"UPDATE {table} SET class_id = (SELECT id FROM school_class WHERE school_class.user_id = {table}.user_id LIMIT 1) "
            f"WHERE class_id IS NULL AND EXISTS (SELECT 1 FROM school_class WHERE school_class.user_id = {table}.user_id)"
        )


def _migrate_class_sections(conn: sqlite3.Connection) -> None:
    """Backfills class_section for classes that existed before admin-defined
    sections were introduced — seeded from whatever sections already appear
    in their uploaded data (if any). Classes created after this feature
    shipped get their sections explicitly at creation time instead, via
    app.db.school_classes.set_class_sections."""
    classes_without_sections = conn.execute(
        "SELECT id FROM school_class WHERE id NOT IN (SELECT DISTINCT class_id FROM class_section)"
    ).fetchall()
    for row in classes_without_sections:
        class_id = row["id"]
        sections = conn.execute(
            "SELECT DISTINCT section FROM student WHERE class_id = ? ORDER BY section", (class_id,)
        ).fetchall()
        for i, s in enumerate(sections):
            conn.execute(
                "INSERT OR IGNORE INTO class_section (class_id, section, order_index) VALUES (?, ?, ?)",
                (class_id, s["section"], i),
            )


def _migrate_phase_rebuild(conn: sqlite3.Connection) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(phase)").fetchall()}
    if "class_id" in existing:
        return
    conn.execute(
        "CREATE TABLE phase_new (user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE, "
        "class_id INTEGER NOT NULL REFERENCES school_class(id) ON DELETE CASCADE, "
        "code TEXT NOT NULL, label TEXT NOT NULL, order_index INTEGER NOT NULL, "
        "PRIMARY KEY (user_id, class_id, code))"
    )
    conn.execute(
        "INSERT INTO phase_new (user_id, class_id, code, label, order_index) "
        "SELECT p.user_id, sc.id, p.code, p.label, p.order_index FROM phase p "
        "JOIN school_class sc ON sc.user_id = p.user_id"
    )
    conn.execute("DROP TABLE phase")
    conn.execute("ALTER TABLE phase_new RENAME TO phase")


def _migrate_textbook_rebuild(conn: sqlite3.Connection) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(textbook)").fetchall()}
    if "class_id" in existing:
        return
    conn.execute(
        "CREATE TABLE textbook_new (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE, "
        "class_id INTEGER NOT NULL REFERENCES school_class(id) ON DELETE CASCADE, "
        "subject TEXT NOT NULL, filename TEXT NOT NULL, uploaded_at TEXT NOT NULL, "
        "UNIQUE (user_id, class_id, subject))"
    )
    conn.execute(
        "INSERT INTO textbook_new (id, user_id, class_id, subject, filename, uploaded_at) "
        "SELECT t.id, t.user_id, sc.id, t.subject, t.filename, t.uploaded_at FROM textbook t "
        "JOIN school_class sc ON sc.user_id = t.user_id"
    )
    conn.execute("DROP TABLE textbook")
    conn.execute("ALTER TABLE textbook_new RENAME TO textbook")


def _migrate_teacher_section_class_rebuild(conn: sqlite3.Connection) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(teacher_section)").fetchall()}
    if "class_id" not in existing:
        conn.execute(
            "CREATE TABLE teacher_section_new (user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE, "
            "class_id INTEGER NOT NULL REFERENCES school_class(id) ON DELETE CASCADE, "
            "section TEXT NOT NULL, subjects_restricted INTEGER NOT NULL DEFAULT 0, "
            "PRIMARY KEY (user_id, class_id, section))"
        )
        # teacher_section.user_id is the TEACHER's login id — their class is
        # found via their school (app_user.school_id), not their own id.
        conn.execute(
            "INSERT INTO teacher_section_new (user_id, class_id, section, subjects_restricted) "
            "SELECT ts.user_id, sc.id, ts.section, ts.subjects_restricted FROM teacher_section ts "
            "JOIN app_user teacher ON teacher.id = ts.user_id "
            "JOIN school_class sc ON sc.user_id = teacher.school_id"
        )
        conn.execute("DROP TABLE teacher_section")
        conn.execute("ALTER TABLE teacher_section_new RENAME TO teacher_section")

    existing2 = {row["name"] for row in conn.execute("PRAGMA table_info(teacher_section_subject)").fetchall()}
    if "class_id" not in existing2:
        conn.execute(
            "CREATE TABLE teacher_section_subject_new (user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE, "
            "class_id INTEGER NOT NULL REFERENCES school_class(id) ON DELETE CASCADE, "
            "section TEXT NOT NULL, subject TEXT NOT NULL, "
            "PRIMARY KEY (user_id, class_id, section, subject))"
        )
        conn.execute(
            "INSERT INTO teacher_section_subject_new (user_id, class_id, section, subject) "
            "SELECT tss.user_id, sc.id, tss.section, tss.subject FROM teacher_section_subject tss "
            "JOIN app_user teacher ON teacher.id = tss.user_id "
            "JOIN school_class sc ON sc.user_id = teacher.school_id"
        )
        conn.execute("DROP TABLE teacher_section_subject")
        conn.execute("ALTER TABLE teacher_section_subject_new RENAME TO teacher_section_subject")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tss_lookup ON teacher_section_subject(user_id, class_id, section)")


def _ensure_class_scope_indexes(conn: sqlite3.Connection) -> None:
    """Indexes on columns the multi-class migration adds. Created here
    rather than in schema.sql because CREATE INDEX IF NOT EXISTS still
    errors if the referenced column doesn't exist yet on a pre-existing
    table — schema.sql's unconditional executescript runs before the
    migrations above have had a chance to add those columns. Safe to run
    on every boot once the columns are guaranteed to exist (fresh installs
    get them straight from schema.sql; migrated ones from the steps above)."""
    conn.execute("CREATE INDEX IF NOT EXISTS idx_batch_class ON import_batch(class_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_student_class_section ON student(class_id, section)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_staff_class ON staff(class_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_result_lookup_v2 ON exam_result(class_id, phase_code, subject)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_summary_phase_v2 ON exam_summary(class_id, phase_code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tss_lookup ON teacher_section_subject(user_id, class_id, section)")


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _migrate_app_user_roles(conn)
        _migrate_teacher_section(conn)
        _migrate_school_class(conn)
        conn.execute("PRAGMA foreign_keys = OFF")
        _migrate_class_scope_columns(conn)
        _migrate_class_sections(conn)
        _migrate_phase_rebuild(conn)
        _migrate_textbook_rebuild(conn)
        _migrate_teacher_section_class_rebuild(conn)
        conn.execute("PRAGMA foreign_keys = ON")
        _ensure_class_scope_indexes(conn)
        conn.commit()


@contextmanager
def session():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
