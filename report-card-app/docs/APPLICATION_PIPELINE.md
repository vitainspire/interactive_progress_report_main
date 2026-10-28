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
(pure data render)                       │
                              ┌───────────┴────────────┐
                              ▼                        ▼
                     CASE: one of 5          CASE: free-form question
                     preset questions                  │
                              │                         ▼
                              ▼              chat.py → OpenRouter (OPENROUTER_MODEL)
                     answered instantly,     — grounded only in chat_context.py's
                     chat_canned.py,            build of this one student's data
                     no LLM call                       │
                                                        ▼
                                              traced via langsmith (@traceable,
                                              tagged with account_id)

  Separately, lazy-loaded 6th card:
                              │
                              ▼
                     study_plan.py: weakest_subject()
                              │
                     ├─ CASE: none found           → card stays hidden
                     ├─ CASE: found, but no         → card stays hidden
                     │   syllabus_chapter rows
                     └─ CASE: found + syllabus exists → chat.generate_text()
                                                         → OpenRouter, names real
                                                           chapters, cached in
                                                           study_plan_cache
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
              written into syllabus_chapter / subject_blueprint
              (live tables) → feeds C's study plan + the Subject
              Analysis report's blueprint action plan
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

## The common thread

Nothing AI-touched is ever auto-trusted into production data — document
extraction, timetable imports, and the study plan are all either
reviewed-before-confirmed, grounded strictly in one student's own data, or
simply hidden when there's nothing real to say.
