CREATE TABLE IF NOT EXISTS app_user (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    default_school_name TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

-- One upload = one batch: a class/section's sheet at a point in time, with
-- its own editable display settings (totals / marks-per-subject / class
-- strength), matching the original tool's "Settings" panel.
CREATE TABLE IF NOT EXISTS batch (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    school_name TEXT NOT NULL DEFAULT '',
    fa_total REAL NOT NULL DEFAULT 350,
    sa_total REAL NOT NULL DEFAULT 600,
    fa_marks_per_subject REAL NOT NULL DEFAULT 50,
    sa_marks_per_subject REAL NOT NULL DEFAULT 100,
    class_strength_override INTEGER,
    source_filename TEXT,
    exam_order TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_batch_user ON batch(user_id);

CREATE TABLE IF NOT EXISTS student (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES batch(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    section TEXT NOT NULL DEFAULT '',
    roll_no TEXT NOT NULL DEFAULT '',
    father_name TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    order_index INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_student_batch ON student(batch_id);

-- A parent-safe, no-login link for one student's report (never the whole
-- batch) — what gets sent over WhatsApp/SMS. The token is an opaque random
-- string, not the student's numeric id, so it can't be guessed/enumerated.
CREATE TABLE IF NOT EXISTS student_share (
    student_id INTEGER PRIMARY KEY REFERENCES student(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

-- One row per send attempt, so the teacher can see what happened per
-- student (sent via WhatsApp, fell back to SMS, skipped for no phone, or
-- failed with a reason) rather than a single pass/fail for the whole batch.
CREATE TABLE IF NOT EXISTS send_log (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES student(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_send_log_student ON send_log(student_id);

CREATE TABLE IF NOT EXISTS exam_subject_result (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES student(id) ON DELETE CASCADE,
    exam_code TEXT NOT NULL,
    subject TEXT NOT NULL,
    marks REAL,
    marks_text TEXT NOT NULL DEFAULT '-',
    grade TEXT NOT NULL DEFAULT '-',
    order_index INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_esr_student ON exam_subject_result(student_id);

CREATE TABLE IF NOT EXISTS exam_summary (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES student(id) ON DELETE CASCADE,
    exam_code TEXT NOT NULL,
    total_marks REAL,
    total_marks_text TEXT NOT NULL DEFAULT '-',
    total_grade TEXT NOT NULL DEFAULT '-',
    result TEXT NOT NULL DEFAULT '',
    rank INTEGER,
    UNIQUE (student_id, exam_code)
);
CREATE INDEX IF NOT EXISTS idx_esum_student ON exam_summary(student_id);

CREATE TABLE IF NOT EXISTS attendance_month (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES student(id) ON DELETE CASCADE,
    month TEXT NOT NULL,
    working_days REAL,
    days_present REAL,
    order_index INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_att_student ON attendance_month(student_id);

CREATE TABLE IF NOT EXISTS attendance_total (
    student_id INTEGER PRIMARY KEY REFERENCES student(id) ON DELETE CASCADE,
    total_working_days REAL,
    total_present REAL
);
