# Application pipeline

How data actually moves through this app, stage by stage — what file/module
handles each step, and the real branch cases (fallbacks, "nothing to show"
states, review-before-confirm gates). Not a user-journey walkthrough; this
is the engineering shape.

## A. Data goes in

```
Teacher
  │
  ├─ Path 1: Upload a file (.xlsx/.csv)         ──► openpyxl parses it
  ├─ Path 2: Paste a Google Sheet link          ──► fetched via Sheets export URL (public, no OAuth)
  └─ Path 3: Point at a Google Drive folder     ──► Drive API v3 (API key, no OAuth)
                                                      • finds every spreadsheet file  → one batch per class
                                                      • finds every PDF/image too      → CASE: fed to the
                                                        (by file TYPE, not filename)      reference-doc pipeline (see D)
           │
           ▼
  sheet_parser.py (deterministic Python parser — no AI here at all)
           │
           ├─ CASE: layout unrecognized / malformed → error shown to teacher, nothing stored
           └─ CASE: looks right → normalized into student/exam/attendance rows
           │
           ▼
     Supabase Postgres (psycopg) — one row set per student, scoped to that school's account
```

## B. Report generation & delivery

```
POST /batches/{id}/send-reports
           │
           ▼
  For each student, one at a time (sequential, inside one Lambda call):
           │
           ├─ CASE: no phone number on file     → skipped, logged "skipped"
           │
           ▼
  card_render.py builds the report HTML (pure Python/arithmetic, no AI)
  sharing.py generates (or reuses) a private share token
           │
           ▼
      whatsapp.py → Meta WhatsApp Cloud API
           │
           ├─ CASE: sent successfully                → logged "sent via whatsapp"
           └─ CASE: not configured / send fails       → fall through
           │
           ▼
      sms.py → Twilio (only if this school's channel setting allows it)
           │
           ├─ CASE: sent successfully                → logged "sent via sms"
           └─ CASE: also fails/not configured         → logged "failed"
```

## C. Parent opens the link

```
GET /report/{token}   (token resolved via sharing.py, no login)
           │
           ▼
   landing page → "View Report" or "Know About Student"
           │
   ┌───────┴─────────────────────────────┐
   ▼                                     ▼
parent_report.py                 chat_canned.py / chat.py
(pure data render,                       │
 one card per subject)        ┌───────────┴────────────┐
           │                  ▼                        ▼
           │         CASE: one of 5          CASE: free-form question
           │         preset questions                  │
           │                  │                         ▼
           │                  ▼              chat.py → OpenRouter (OPENROUTER_MODEL)
           │         answered instantly,     — grounded only in chat_context.py's
           │         chat_canned.py,            build of this one student's data
           │         no LLM call                       │
           │                                            ▼
           │                                  traced via langsmith (@traceable,
           │                                  tagged with account_id)
           │
           │  Separately, lazy-loaded 6th card on the main view:
           │                  │
           │                  ▼
           │         study_plan.py: weakest_subject()
           │                  │
           │         ├─ CASE: no weak subject found  → card stays hidden
           │         └─ CASE: found                   → chat.generate_text()
           │                                            → OpenRouter, names real
           │                                              chapters (from D's data,
           │                                              global default if this
           │                                              account hasn't confirmed
           │                                              its own), cached in
           │                                              study_plan_cache
           ▼
  "📘 View prep plan" link on each subject card
           │
           ▼
  GET /report/{token}/subject/{subject}/plan
           │
           ▼
  exam_focus.build_exam_focus() — pure arithmetic, no AI:
  which chapters the student's NEXT exam likely covers (D's chapter data,
  global default if unconfirmed) + the exam blueprint's highest-marks topics
           │
           ├─ CASE: subject == Physical Science
           │          │
           │          ▼
           │   science_lab.find_chapter_by_title() for each covered chapter
           │   (or every cataloged chapter if this student is "low"/"fail"
           │   in the subject — real classification, not a guess)
           │          │
           │          ├─ CASE: chapter not in the external catalog → nothing added
           │          └─ CASE: found → "Try the lab" / "Play games" buttons,
           │                            opening interactive-labs.onrender.com
           │
           └─ CASE: calendar_repo.get_exam_date() finds a real date for this
                      exam (see F) → lazily fetches one more card:
                       │
                       ▼
              GET /report/{token}/subject/{subject}/day-plan
                       │
              ├─ CASE: no exam date set in F        → {"available": false}
              ├─ CASE: no study days left            → {"available": false}
              └─ CASE: date set, days remain          → calendar.working_dates_between()
                                                          (Sundays/holidays excluded)
                                                          → study_plan.generate_exam_day_plan()
                                                          → OpenRouter, assigns real
                                                            chapters per real date,
                                                            cached in
                                                            exam_day_plan_cache keyed
                                                            on the exact date list (so
                                                            it regenerates once a day)
```

## D. Reference-document pipeline (syllabus/blueprint)

```
PDF/image from the Drive folder (see A)
           │
           ▼
  syllabus_extraction.py → OpenRouter (OPENROUTER_DOCUMENT_MODEL,
  Gemini 2.5 Flash-Lite)
           │
           ├─ CASE: extraction fails          → stored status='failed'
           └─ CASE: extracted OK              → stored status='pending'
                       │
                       ▼
              reference_documents.py — teacher reviews/edits
                       │
                       ▼
              teacher clicks Confirm
                       │
                       ▼
              written into syllabus_chapter / subject_blueprint, THIS
              account's own account_id (live tables, never account_id
              NULL) → feeds C's study plan + exam_focus, and G's Exam
              Readiness — all three try this account's own rows first,
              falling back to the account_id IS NULL global default
              dataset only when nothing of its own has been confirmed
```

## E. Timetable & substitution

```
            ┌──────────────────────┐     ┌───────────────────────────┐
            │ generator.py          │     │ timetable_parser.py        │
            │ (POST /generate,      │     │ (POST /import — reads an   │
            │  fills periods from   │     │  already-existing Excel    │
            │  assignments)          │     │  "master sheet" layout)    │
            │                        │     │  CASE: codes like "PS",   │
            │                        │     │  "KSVL" never auto-named  │
            │                        │     │  → POST /import/confirm   │
            │                        │     │    only after a teacher    │
            │                        │     │    names them              │
            └───────────┬────────────┘     └─────────────┬─────────────┘
                         └──────────────┬──────────────────┘
                                        ▼
                     tt_timetable_entry (Postgres) — same table either way

  POST /leaves (a teacher records a date range)
                         │
                         ▼
          GET /leaves/pending — cross-references leave × tt_timetable_entry
                         │
                         ├─ CASE: calendar_repo.get_holiday_on() finds a
                         │   holiday on this date (see F) → day skipped
                         │   entirely, no substitutions generated
                         ▼
          find_substitute_candidates() — ranks by free-at-that-period
          AND qualified-for-that-subject
                         │
                         ▼
          POST /classes/{id}/substitutions — confirm
                         │
                ┌────────┴─────────┐
                ▼                  ▼
       notify via whatsapp.py/sms.py    substitution_sheet.py
       to the substitute teacher         → printable noticeboard PDF/HTML
```

## F. Academic Calendar

```
PUT /calendar/year          (academic year start/end, 5-day/6-day week)
POST /calendar/exam-types   (e.g. "Unit Test" ×4 this year)
POST /calendar/events       (a holiday, or a dated exam occurrence —
                              optionally tagged with a plan_type)
           │
           ▼
  academic_calendar_event / exam_plan_type (Postgres, account-scoped)
           │
           ├─ feeds C: calendar_repo.get_exam_date() shows a real date next
           │   to the exam name on the prep-plan page, and gates whether the
           │   AI day-by-day plan has anything to build from
           ├─ feeds E: calendar_repo.get_holiday_on() skips substitute
           │   generation on a declared holiday
           └─ feeds GET /calendar/overview: calendar.compute_working_capacity()
               — pure arithmetic over the academic year range, the weekly
               pattern, and declared holidays. working_hours is only ever a
               real number when this account has also set a real school-day
               length in the Timetable tool — never a guessed default.

  Clicking a date on the frontend's month grid (CalendarPage.tsx) opens an
  editor for everything on that date — same POST/PUT/DELETE /calendar/events
  endpoints, scoped to that one date.
```

## G. Teacher-facing Exam Readiness (Subject Analysis report)

```
GET /batches/{id}/subject-analysis?subject={name}
           │
           ▼
  subject_analysis.render_subject_analysis() — same report as before
  (donuts, Shining/Rising Stars, grade distribution, blueprint action plan)
           │
           ▼
  NEW: exam_focus.build_exam_focus() using this batch's own exam_order as
  "completed exams" (same convention as C — a batch's exam_order only ever
  contains exams with marks already entered, so it stands in for the WHOLE
  CLASS's position in the exam sequence, not just one student's)
           │
           ├─ CASE: nothing confirmed/next exam already finished → nothing
           │    added, no change from before
           └─ CASE: real chapters found → "📅 Next exam" callout inserted
                above the existing Rising Stars action plan, with a real
                date from F if one's been set — deliberately does NOT
                re-derive a weak-student list (Rising Stars already is one)
```

## The common thread

Nothing AI-touched is ever auto-trusted into production data — document
extraction, timetable imports, the study plan, and the day-by-day exam plan
are all either reviewed-before-confirmed, grounded strictly in one student's
(or one class's) own real data, or simply hidden when there's nothing real
to say. The same rule applies to deterministic data too, not just AI: the
Academic Calendar's working-hours figure is `null` rather than a guessed
default, and the Smart Science Lab link is omitted rather than shown
against the wrong chapter when this app's own chapter numbering doesn't
match the external catalog's.
