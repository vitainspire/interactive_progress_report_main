# Report Card App

A multi-tenant SaaS app for Indian government school teachers: upload a
class's marks spreadsheet (or just point it at a Google Drive folder) and it
generates a digital progress card per student, delivered straight to a
parent's WhatsApp or SMS as a private link — no app install, no login,
built for parents with low digital literacy and patchy connectivity.

Every account (school) is fully isolated: its students, uploads, syllabus
data, and settings never appear in another school's session.

## What it does

- **Marks & attendance tracking** — upload an Excel/CSV sheet, paste a
  Google Sheet link, or point at a Google Drive folder (one spreadsheet per
  class, auto-detected by file type).
- **Parent delivery over WhatsApp/SMS** — one click sends every student in a
  class a private link to their own report (WhatsApp Cloud API first, SMS
  via Twilio as a fallback per the school's own channel setting).
- **Digital Progress Card** — a mobile-first report page (no login) with
  marks, grade, rank, class-average comparison, attendance, and a
  text-to-speech "listen to the analysis" option (Bhashini).
- **"Know About Student" chat** — a parent can ask free-form questions about
  their child; five common questions are answered instantly with no AI call,
  anything else is answered by an LLM grounded strictly in that one
  student's own data (never any other student's).
- **Syllabus-aware study plan & exam focus** — a dedicated "prep plan" page
  per subject shows which real syllabus chapters the student's next exam is
  likely to cover and the highest-weightage topics from the official exam
  blueprint (`app/reports/exam_focus.py`, pure arithmetic, no AI). If a
  school uploads its own syllabus/exam-blueprint documents (PDFs/images
  dropped in the same Drive folder), the app extracts chapters and
  marks-weightage via an LLM, a teacher reviews/confirms the extraction, and
  confirmed data takes over from the built-in global default. **Scoped per
  school — a school's own confirmed upload always wins; one that hasn't
  uploaded anything still gets a real, working prep plan from the built-in
  default dataset, never another school's actual uploaded curriculum.**
- **AI-generated day-by-day exam revision plan** — once a school sets a real
  date for a student's upcoming exam in the Academic Calendar (see below),
  the prep-plan page adds a day-by-day schedule spanning every real working
  date between today and the exam (Sundays/holidays already excluded),
  assigning real syllabus chapters by how much class time each took to
  teach, closing on a revision day naming the highest-marks topic
  (`study_plan.py:generate_exam_day_plan`, cached per account+subject+exam+
  exact date list so it naturally regenerates once a day).
- **Academic Calendar** — each school sets its own academic year, weekly
  working pattern (5-day/6-day), holidays, and real dates for its exams
  (`app/db/calendar.py`). This single source of truth feeds three other
  features: the exam date shown on a subject's prep-plan page, the
  substitute-finder's holiday-skipping (see Timetable below), and the
  day-by-day revision plan above. A month-grid view lets a teacher click any
  date to add/edit what's on it; a Working Capacity panel computes real
  working days/hours for the year from the same data.
- **Smart Science Lab** — for Physical Science, the prep-plan page links out
  to a shared interactive-labs microservice's digital lab simulations and
  quiz games for each relevant chapter (`app/integrations/science_lab.py`),
  matched by chapter **title** (never by number — this app's own seeded
  chapter numbering doesn't match that service's NCERT numbering).
  Personalized by the student's own real performance: a student struggling
  in the subject sees every cataloged chapter for extra practice, not just
  the narrow current-exam slice.
- **Subject Analysis & Timetable/Substitution tools** — printable per-subject
  analysis reports for teachers (with a class-wide "Exam Readiness" callout
  showing the next exam's real chapters, reusing the same `exam_focus.py`
  logic as the parent-facing page), and a separate timetable generator +
  substitute-finder module that skips declared holidays automatically.

See [`docs/APPLICATION_PIPELINE.md`](docs/APPLICATION_PIPELINE.md) for the
full data-flow/engineering shape of all of the above, stage by stage.

## Architecture

```
                         ┌─────────────────────────┐
                         │   Teacher's browser      │
                         │   React + Vite + TS      │
                         │   (Vercel, static build)  │
                         └────────────┬─────────────┘
                                      │ HTTPS, JWT bearer token
                                      ▼
                         ┌─────────────────────────┐
                         │   FastAPI backend         │
                         │   (AWS Lambda, container   │
                         │    image, via Mangum)      │
                         │                            │
                         │  api/        routers        │
                         │  reports/    page rendering  │
                         │  integrations/  external APIs │
                         │  parsing/    spreadsheet/     │
                         │              timetable parse  │
                         │  db/         repository layer │
                         └──┬──────────┬───────────┬───┘
                            │          │           │
                 psycopg3,  │          │           │ opaque share
                 pooled     │          │           │ token, no auth
                            ▼          │           ▼
                 ┌────────────────┐    │   ┌─────────────────────┐
                 │ Supabase        │    │   │  Parent's phone       │
                 │ Postgres        │    │   │  (no app, no login)   │
                 │ (ap-southeast-2) │    │   │  — opens the report    │
                 └────────────────┘    │   │    link in a browser    │
                                        │   └─────────────────────┘
                                        ▼
                  ┌─────────────────────────────────────────────┐
                  │  External integrations (each optional —       │
                  │  silently no-ops if its own env vars unset)    │
                  │                                                │
                  │  WhatsApp Cloud API   Twilio SMS   Resend       │
                  │  Google Drive/Sheets  OpenRouter (LLM)           │
                  │  Bhashini (Telugu TTS)                            │
                  │  interactive-labs.onrender.com (Smart Science Lab) │
                  └─────────────────────────────────────────────┘
```

**Core design principles a new developer should internalize before changing
anything:**

- **Every table that holds school-specific data is scoped by `account_id` /
  `user_id`, and every repository function and route enforces that scope.**
  Never add a query that reads another account's rows, even implicitly.
- **Real data only — hide rather than fabricate.** All over this codebase,
  a feature that has nothing real to show renders nothing (or falls back to
  an explicit, clearly-labeled default) instead of guessing. Examples:
  the Academic Calendar's Working Capacity panel shows `null` working hours
  rather than assuming a default school-day length; the syllabus/blueprint
  lookups fall back to a global default dataset, never to borrowing a
  *different specific school's* uploaded data; a subject card's prep-plan
  link simply doesn't render when there's nothing confirmed to show.
- **AI is used sparingly and is never auto-trusted into production data.**
  Document extraction, the study plan, and the day-by-day revision plan are
  all either reviewed-before-confirmed by a teacher, grounded strictly in
  real data already in Postgres, or simply hidden when the LLM call fails —
  see [`docs/APPLICATION_PIPELINE.md`](docs/APPLICATION_PIPELINE.md)'s "The
  common thread" section.
- **Deterministic logic is preferred over an LLM call wherever the two would
  produce the same answer.** `exam_focus.py`'s chapter/topic guidance, the
  entire Subject Analysis report, and the Academic Calendar's working-day
  math are all pure arithmetic — no AI call, no cost, no hallucination risk.

## Stack

- **Backend**: Python 3.13, FastAPI, [psycopg 3](https://www.psycopg.org/psycopg3/)
  (connection-pooled) against Postgres. Auth is email/password (`bcrypt`) +
  JWT bearer tokens (`PyJWT`), checked on every route. Parsing is a
  deterministic Python parser (no AI) for spreadsheets; AI is used only for
  the parent chat, the study plan, and syllabus-document extraction — all
  three go through [LangSmith](https://smith.langchain.com) tracing when
  configured, tagged per `account_id`.
- **Frontend**: React 19 + TypeScript + Vite + Tailwind CSS v4.
- **Database**: Postgres, hosted on [Supabase](https://supabase.com).
- **Integrations**: WhatsApp Cloud API (Meta), Twilio (SMS fallback),
  Google Drive API v3 / Sheets export (API key, no OAuth needed for reading
  a shared folder), OpenRouter (LLM calls — chat, study plan, document
  extraction), Bhashini (Telugu text-to-speech), Resend (password-reset
  email).

## Hosting

| | |
|---|---|
| **Backend** | AWS Lambda, container image, region `ap-southeast-2` (Sydney — matched to the Supabase pooler region), function `report-card-backend`, image repo `reprot-card-backend` in ECR. Invoked via a public Function URL; FastAPI's own `CORSMiddleware` handles CORS (not the Function URL's own CORS config). |
| **Frontend** | [Vercel](https://vercel.com), static Vite build. `VITE_API_BASE` points at the Lambda Function URL + `/api`, baked in at build time — changing it requires a redeploy, not just an env-var edit. **Note: this Vercel project does not auto-deploy from GitHub pushes** — trigger a redeploy manually from the Vercel dashboard after pushing backend-independent frontend changes. |
| **Database** | Supabase Postgres, same region as Lambda. |
| **Rollback** | The backend's previous Render deployment is left running, unused, as an instant fallback (flip `VITE_API_BASE` back and redeploy frontend) until Lambda has proven solid under real use. |

Full deployment runbook — env vars, the Mangum Lambda entry point, the
`--provenance=false` Docker gotcha, measured cold-start numbers — lives in
[`docs/AWS_LAMBDA_DEPLOYMENT.md`](docs/AWS_LAMBDA_DEPLOYMENT.md).

### Redeploying the backend

```bash
cd backend
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin 717827130588.dkr.ecr.ap-southeast-2.amazonaws.com
docker build --provenance=false -f Dockerfile.lambda -t reprot-card-backend .
docker tag reprot-card-backend:latest 717827130588.dkr.ecr.ap-southeast-2.amazonaws.com/reprot-card-backend:latest
docker push 717827130588.dkr.ecr.ap-southeast-2.amazonaws.com/reprot-card-backend:latest
```
Then in the Lambda console: **Image** tab → **Deploy new image** → select the
newly-pushed digest → Save.

### Redeploying the frontend

Push to `master`, then manually trigger a redeploy from the Vercel
dashboard (GitHub pushes do not auto-deploy on this project).

## Multi-tenancy & data isolation

Every table that holds school-specific data carries an `account_id` /
`user_id`, and every repository function and route is scoped to the
authenticated caller. Syllabus/blueprint data additionally supports a
nullable `account_id`: `NULL` rows are the built-in global default dataset,
never a specific school's real curriculum. The lookup functions
(`study_plan.get_chapters`, `subject_analysis.get_blueprint`/
`get_exam_info`) always try an account's **own** confirmed rows first and
fall back to the global default — **never to a different specific school's
uploaded data** — when the account hasn't uploaded and confirmed anything of
its own.

## Running locally

**Backend** (from `backend/`):
```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python -m uvicorn app.main:app --port 8010
```
Needs a `.env` file (gitignored) with at least `DATABASE_URL` pointing at a
Postgres instance; see
[`docs/AWS_LAMBDA_DEPLOYMENT.md`](docs/AWS_LAMBDA_DEPLOYMENT.md) for the
full environment-variable list (WhatsApp/SMS/OpenRouter/etc. are all
optional — each integration silently no-ops when its own env vars aren't
set).

Note: `uvicorn --reload` has been unreliable in this setup (the reloader
logs "Reloading..." without actually swapping the worker) — after changing
backend code, stop and restart the server manually. On Windows, a killed
`uvicorn` process can leave the port bound for a few seconds (or, rarely, a
stray child process keeps holding it) — if the next start fails with
"only one usage of each socket address," find and kill the PID actually
holding port 8010 (`netstat -ano | grep :8010`, or
`Get-NetTCPConnection -LocalPort 8010` in PowerShell, which is more
reliable than `netstat` for this) before retrying.

**Known footgun**: `init_db()` (`app/db/database.py`) splits `schema.sql` on
every literal `;` to run each statement — including any `;` that appears
inside a `--` SQL comment, not just inside real statements. A sentence like
`-- against a batch's own exam_order; 'holiday' rows don't need one.` will
break startup with a cryptic `psycopg.errors.SyntaxError`. Before editing a
comment in `schema.sql`, check for stray semicolons:
`grep -n "^--.*;" app/db/schema.sql`.

**Frontend** (from `frontend/`):
```bash
npm install
npm run dev
```
Opens on `http://localhost:5173` (or the next free port — Vite tries 5174,
5175, etc. if 5173 is already taken by a stale process); `/api/*` proxies to
`http://127.0.0.1:8010` (see `vite.config.ts`) — **the backend must be
started on port 8010, not FastAPI's default 8000**, or every API call
through the proxy fails with a bad-gateway error that looks like a backend
crash but is just a port mismatch.

## Project layout

```
backend/app/
  api/              FastAPI routers — one file per feature area:
                      auth.py, batches.py (upload/report/send/subject-analysis),
                      calendar.py (Academic Calendar), timetable.py,
                      science_lab.py, reference_documents.py (syllabus review),
                      integrations.py (WhatsApp/SMS settings), public.py (every
                      unauthenticated parent-facing route, keyed by share token)
  integrations/     One file per external service — WhatsApp (whatsapp.py), SMS
                      (sms.py, Twilio), Google Drive/Sheets, OpenRouter chat
                      (chat.py), syllabus-document extraction
                      (syllabus_extraction.py), Bhashini TTS, Resend email,
                      Smart Science Lab client (science_lab.py), share-token
                      issuing (sharing.py)
  reports/          Pure rendering/computation, mostly no DB writes:
                      parent_report.py (the parent-facing page + prep-plan
                      page), card_render.py (teacher's printable card),
                      subject_analysis.py (teacher's per-subject report, incl.
                      Exam Readiness), exam_focus.py + study_plan.py (syllabus-
                      aware guidance, deterministic + AI respectively),
                      class_stats.py / student_analytics.py (Dashboard
                      aggregates), chat_canned.py / chat_context.py (the 5
                      instant chat answers + LLM grounding), voice_script.py /
                      parent_subject.py (text-to-speech narration),
                      substitution_sheet.py / timetable_print.py (printable
                      timetable output)
  parsing/          Deterministic parsers — sheet_parser.py (marks/attendance
                      spreadsheets), timetable_parser.py (an existing
                      "master sheet" timetable layout)
  timetable/        generator.py — fills a timetable from class/teacher/
                      subject assignments
  db/               Repository layer (one query module per concern) +
                      schema.sql + the migration functions in database.py +
                      the two seed files (syllabus_seed.py,
                      subject_blueprint_seed.py) that populate the global
                      default dataset
  core/             config.py (every env var), security.py (JWT + password
                      hashing), deps.py (auth dependency used on every
                      protected route)
  lambda_handler.py Mangum entry point used only in the Lambda container —
                      see docs/AWS_LAMBDA_DEPLOYMENT.md for why lifespan="off"
                      matters here

frontend/src/
  pages/            One file per route — Dashboard, Upload, Batch, Student,
                      Timetable, CalendarPage (Academic Calendar),
                      ReferenceDocumentsPage (syllabus review),
                      SchoolProfilePage, IntegrationsPage (WhatsApp settings),
                      ToolsHubPage, auth pages (Login/Signup/
                      Forgot-/Reset-Password, SchoolSetup)
  components/       Shared UI — Layout.tsx (the shell + account-menu
                      navigation), Icons.tsx, ReportPreview.tsx,
                      TimetableImportPanel.tsx, DriveDuplicateResolver.tsx,
                      ReferenceDocumentReview.tsx, StudentActionList.tsx
  api/client.ts     Typed fetch wrapper (auth token header, cold-start retry)
  types.ts          Every API response shape, hand-kept in sync with the
                      backend (no codegen) — update this whenever a backend
                      response shape changes
```
