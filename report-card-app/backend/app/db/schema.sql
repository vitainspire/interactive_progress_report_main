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
    -- Which class's syllabus applies to this batch (see syllabus_chapter) —
    -- defaults to '10' since every syllabus seeded so far is SSC/10th.
    -- A teacher uploading another class's marks sets this explicitly.
    class_level TEXT NOT NULL DEFAULT '10',
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

-- Caches generated Bhashini TTS audio by a hash of (language, voice, text),
-- so repeated "Listen" taps for the same report page don't re-call a free
-- government API every time, and a slow/down Bhashini doesn't block a
-- parent who already generated this exact audio once before. content_key
-- identifies "this student's this page" independent of the exam text, so
-- the stale row left behind when a new exam changes that page's wording
-- can be found and deleted instead of accumulating forever.
CREATE TABLE IF NOT EXISTS tts_audio_cache (
    text_hash TEXT PRIMARY KEY,
    content_key TEXT,
    audio_format TEXT NOT NULL,
    audio_bytes BYTEA NOT NULL,
    created_at TEXT NOT NULL
);

-- Real AP syllabus chapters, one row per chapter per (class, subject) —
-- reference data shared by every batch/user (not tied to a user_id or
-- batch_id), since a given class+subject's syllabus is the same regardless
-- of which school uploaded marks. Seeded once from app/db/syllabus_seed.py,
-- not hand-entered per teacher. Powers the syllabus-aware study plan (see
-- app/reports/study_plan.py) instead of a generic "study more" tip — only
-- for whichever (class_level, subject) pairs have actually been seeded.
CREATE TABLE IF NOT EXISTS syllabus_chapter (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    class_level TEXT NOT NULL DEFAULT '10',
    subject TEXT NOT NULL,
    chapter_no INTEGER NOT NULL,
    chapter_name TEXT NOT NULL,
    genre TEXT,
    theme TEXT,
    author TEXT,
    month TEXT,
    periods INTEGER,
    page_range TEXT
);
-- Index created in _migrate_class_level (database.py), not here — this
-- table already existed before class_level did, so on an upgrade this
-- CREATE TABLE is a no-op and the column/index only appear via that
-- migration, which must run after this statement, not before it.

-- Caches one generated study plan per (subject, weak-subject summary) pair
-- so reloading the same student's report doesn't re-call the LLM every
-- time — same reasoning as tts_audio_cache, just for text instead of audio.
CREATE TABLE IF NOT EXISTS study_plan_cache (
    cache_key TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    plan_text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- The official SSC exam BLUEPRINT's marks-weightage per topic — distinct
-- from syllabus_chapter's textbook table-of-contents (periods/month/page):
-- the blueprint groups topics differently (e.g. one "Light: Reflection and
-- Refraction" exam topic spans several syllabus_chapter rows) and carries
-- how many marks that topic is actually worth in the public exam, which
-- the textbook TOC doesn't have. Powers the teacher-facing Subject
-- Analysis report's "study these chapters first" ranking.
CREATE TABLE IF NOT EXISTS subject_blueprint (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    class_level TEXT NOT NULL DEFAULT '10',
    subject TEXT NOT NULL,
    topic_name TEXT NOT NULL,
    marks INTEGER NOT NULL,
    choice_marks INTEGER,
    sort_order INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_subject_blueprint_lookup ON subject_blueprint(class_level, subject);

-- Per-subject exam format (marks/time/question count) and a curated list of
-- "easy marks" exam-technique tips — also feeds the Subject Analysis
-- report. One row per (class_level, subject). `tips` is a JSON-encoded
-- array of strings (same TEXT-holding-JSON convention as batch.exam_order).
CREATE TABLE IF NOT EXISTS subject_exam_info (
    class_level TEXT NOT NULL DEFAULT '10',
    subject TEXT NOT NULL,
    exam_format TEXT,
    tips TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (class_level, subject)
);

-- Timetable Creator module — a second tool under the same login, scoped to
-- user_id exactly like batch is (one account = one school, see ToolsHubPage).
-- tt_teacher is declared before tt_class_subject below since that junction
-- table references it.
CREATE TABLE IF NOT EXISTS tt_teacher (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT NOT NULL DEFAULT '',
    max_periods_per_day INTEGER,
    sort_order INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tt_teacher_user ON tt_teacher(user_id);

-- Which subjects a teacher is qualified to teach at all — distinct from
-- tt_class_subject, which says who actually teaches a given class. This
-- is what lets the Assignments picker put likely-correct teachers first,
-- and later lets the substitute finder look for someone who can actually
-- cover the subject, not just anyone free that period.
CREATE TABLE IF NOT EXISTS tt_teacher_subject (
    teacher_id INTEGER NOT NULL REFERENCES tt_teacher(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES tt_subject(id) ON DELETE CASCADE,
    PRIMARY KEY (teacher_id, subject_id)
);

CREATE TABLE IF NOT EXISTS tt_class (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    grade TEXT NOT NULL,
    section TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL,
    UNIQUE (user_id, grade, section)
);
CREATE INDEX IF NOT EXISTS idx_tt_class_user ON tt_class(user_id);

CREATE TABLE IF NOT EXISTS tt_subject (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL,
    UNIQUE (user_id, name)
);
CREATE INDEX IF NOT EXISTS idx_tt_subject_user ON tt_subject(user_id);

-- One row per (class, subject) actually taught: how many periods/week it
-- gets for that class, and which teacher is responsible for it. Fixed by
-- the school up front, same as every real timetable sheet we've seen — a
-- subject for a given class always has one assigned teacher. What's still
-- to be solved (by the generator, not here) is WHEN each period falls.
CREATE TABLE IF NOT EXISTS tt_class_subject (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    class_id INTEGER NOT NULL REFERENCES tt_class(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES tt_subject(id) ON DELETE CASCADE,
    teacher_id INTEGER REFERENCES tt_teacher(id) ON DELETE SET NULL,
    periods_per_week INTEGER NOT NULL DEFAULT 0,
    UNIQUE (class_id, subject_id)
);
CREATE INDEX IF NOT EXISTS idx_tt_class_subject_class ON tt_class_subject(class_id);

-- The school's weekly structure: which days run classes and how many
-- periods each day has. One row per account. Needed so the generator can
-- later check requested periods_per_week against actual weekly capacity.
-- `breaks` is a JSON-encoded array of {after_period, duration_minutes,
-- label} — a short break or lunch break slotted in immediately after a
-- given period number, used to compute the actual clock-time template
-- (see the frontend's buildDaySchedule) the same way the real timetable
-- sheets we've seen interleave breaks between periods.
CREATE TABLE IF NOT EXISTS tt_school_config (
    user_id INTEGER PRIMARY KEY REFERENCES app_user(id) ON DELETE CASCADE,
    working_days TEXT NOT NULL DEFAULT '["MON","TUE","WED","THU","FRI","SAT"]',
    periods_per_day INTEGER NOT NULL DEFAULT 8,
    start_time TEXT NOT NULL DEFAULT '09:15',
    end_time TEXT NOT NULL DEFAULT '16:00',
    breaks TEXT NOT NULL DEFAULT '[]'
);
