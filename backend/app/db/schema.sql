CREATE TABLE IF NOT EXISTS app_user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    school_name TEXT,
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

-- A school account (app_user with role='admin') can have several classes
-- (Class 9, Class 10, ...), each with its own upload, sections, students,
-- exam data, staff list and textbooks. short_code is a short admin-chosen
-- token used to keep student roll numbers readable; see app/db/users.py
-- for why it must never be NULL except on an auto-migrated legacy class.
CREATE TABLE IF NOT EXISTS school_class (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    short_code TEXT,
    order_index INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (user_id, name)
);
CREATE INDEX IF NOT EXISTS idx_school_class_user ON school_class(user_id);

-- The admin-defined list of sections in a class, set when the class is
-- created (so teachers/students can be set up before any data exists) and
-- auto-grown by upload if the sheet contains a section not listed yet.
CREATE TABLE IF NOT EXISTS class_section (
    class_id INTEGER NOT NULL REFERENCES school_class(id) ON DELETE CASCADE,
    section TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    PRIMARY KEY (class_id, section)
);

CREATE TABLE IF NOT EXISTS import_batch (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES school_class(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    total_students INTEGER NOT NULL
);
-- idx_batch_class created in Python after migrations (see database.py) —
-- an unconditional CREATE INDEX here would fail on a pre-existing
-- import_batch table that doesn't have class_id yet.

CREATE TABLE IF NOT EXISTS phase (
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES school_class(id) ON DELETE CASCADE,
    code TEXT NOT NULL,          -- FA1, FA2, SA1, SA2, PREFINAL
    label TEXT NOT NULL,         -- raw header text from the sheet
    order_index INTEGER NOT NULL,
    PRIMARY KEY (user_id, class_id, code)
);

CREATE TABLE IF NOT EXISTS student (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES school_class(id) ON DELETE CASCADE,
    s_no INTEGER,
    section TEXT NOT NULL,
    name TEXT NOT NULL,
    gender TEXT,
    father_name TEXT,
    mother_name TEXT
);
CREATE INDEX IF NOT EXISTS idx_student_user ON student(user_id);
CREATE INDEX IF NOT EXISTS idx_student_name ON student(user_id, name);
-- idx_student_class_section created in Python after migrations.

CREATE TABLE IF NOT EXISTS exam_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES school_class(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES student(id) ON DELETE CASCADE,
    phase_code TEXT NOT NULL,
    subject TEXT NOT NULL,
    marks REAL,
    max_marks REAL,
    grade TEXT
);
CREATE INDEX IF NOT EXISTS idx_result_student ON exam_result(student_id);
-- idx_result_lookup_v2 created in Python after migrations (superseding the
-- old idx_result_lookup, which was keyed by user_id only).

CREATE TABLE IF NOT EXISTS exam_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES school_class(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES student(id) ON DELETE CASCADE,
    phase_code TEXT NOT NULL,
    total_marks REAL,
    max_total REAL,
    total_grade TEXT,
    result TEXT,
    rank INTEGER
);
CREATE INDEX IF NOT EXISTS idx_summary_student ON exam_summary(student_id);
-- idx_summary_phase_v2 created in Python after migrations (superseding the
-- old idx_summary_phase, which was keyed by user_id only).

CREATE TABLE IF NOT EXISTS attendance_month (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES school_class(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES student(id) ON DELETE CASCADE,
    month TEXT NOT NULL,
    days_present REAL,
    working_days REAL
);
CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance_month(student_id);

CREATE TABLE IF NOT EXISTS attendance_summary (
    student_id INTEGER PRIMARY KEY REFERENCES student(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES school_class(id) ON DELETE CASCADE,
    total_present REAL,
    total_working_days REAL
);

CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES school_class(id) ON DELETE CASCADE,
    section TEXT NOT NULL,
    subject TEXT NOT NULL,
    teacher_name TEXT NOT NULL
);
-- idx_staff_class created in Python after migrations.

CREATE TABLE IF NOT EXISTS teacher_section (
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES school_class(id) ON DELETE CASCADE,
    section TEXT NOT NULL,
    subjects_restricted INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, class_id, section)
);

-- Which subjects a teacher teaches in a given class+section. Always
-- recorded for display regardless of subjects_restricted; only enforced
-- as an access filter when that section's subjects_restricted = 1.
CREATE TABLE IF NOT EXISTS teacher_section_subject (
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES school_class(id) ON DELETE CASCADE,
    section TEXT NOT NULL,
    subject TEXT NOT NULL,
    PRIMARY KEY (user_id, class_id, section, subject)
);
-- idx_tss_lookup created in Python after migrations (teacher_section_subject
-- is one of the tables rebuilt outright for a pre-existing database).

CREATE TABLE IF NOT EXISTS textbook (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES school_class(id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    filename TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    UNIQUE (user_id, class_id, subject)
);

CREATE TABLE IF NOT EXISTS textbook_topic (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    textbook_id INTEGER NOT NULL REFERENCES textbook(id) ON DELETE CASCADE,
    order_index INTEGER NOT NULL,
    chapter_no TEXT,
    title TEXT NOT NULL,
    page INTEGER
);
CREATE INDEX IF NOT EXISTS idx_textbook_topic_textbook ON textbook_topic(textbook_id);

CREATE TABLE IF NOT EXISTS settings (
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY (user_id, key)
);
