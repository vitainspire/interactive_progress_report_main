# Interactive Progress Report

A multi-tenant SaaS-style app: any teacher can sign up and upload their own
school's progress-tracking workbook (the AutoCrat/Apps-Script export format
used by `PROGRESS 1.xlsx`), privately scoped to their account. They get a
dashboard, per-student pages, a natural-language query bar (regex-first, with
an optional LLM fallback — see below), and an auto-generated Telugu "AI
Powered Student Comprehensive Digital Progress Card" per student, matching
the style of the original hand-made sample report. A shared, read-only
**demo account** (seeded from `PROGRESS 1.xlsx`) is reachable with one click
from the login page, with no signup required, so a prospective user can see
what the app does first.

## Stack

- **Backend**: Python 3.13 + FastAPI + SQLite (stdlib `sqlite3`) + openpyxl (parsing) + Jinja2 (report templates). Auth is email/password (`bcrypt` hashing)
  + JWT bearer tokens (`PyJWT`), checked on every API route. The NL query
  engine and the report's trend analysis are rule-based (regex entity
  extraction + percentage-trend classification) by default; an optional
  tool-calling LLM fallback (see below) handles questions regex can't match.
- **Frontend**: React + TypeScript + Vite + Tailwind CSS v4 + Recharts. Voice
  input/output uses the browser's native Web Speech API (`SpeechRecognition` /
  `speechSynthesis`) — no cloud speech service.

## Accounts & data isolation

Every table in the database carries a `user_id`, and every repository
function and API route is scoped to the authenticated caller — one teacher's
upload, students, settings, and report never appear in another's session.
There are three ways into the app:

- **Sign up** (`/signup`): email + password (bcrypt-hashed) + display name +
  optional school name. Creates an empty account — upload a workbook to
  populate it.
- **Log in** (`/login`): returns a JWT (30-day expiry) stored in
  `localStorage` and sent as `Authorization: Bearer <token>` on every request.
- **Try the demo** (one click, no credentials): logs into a single shared
  account seeded on first server startup from the bundled `PROGRESS 1.xlsx`.
  That account is flagged `is_demo` and the backend rejects any upload or
  settings change against it (403) so the shared demo data can't be
  overwritten by a visitor.

**Known simplifications** (fine for a demo/MVP, worth hardening before a real
public launch): no password-reset or email-verification flow; a single
long-lived JWT with no refresh/rotation; `PROGRESS_APP_JWT_SECRET` defaults to
an insecure placeholder — **set it to a real random secret via environment
variable before deploying anywhere other people can reach.**

## The Ask feature's LLM fallback

`app/nlq/engine.py` tries every regex rule first — free, instant, and covers
the common phrasings. If none match, it calls `app/nlq/llm_fallback.py`,
which gives an LLM (via [OpenRouter](https://openrouter.ai), configurable
model) a fixed set of **tools** that are thin wrappers around the same
repository functions the regex engine uses (`get_subject_stats`,
`get_class_summary`, `get_top_students`, `get_failing_students`,
`get_student_summary`, `compare_sections`). The model can only answer by
calling these — it never invents a number itself — so every fact in its
answer traces back to a real, account-scoped SQL query.

Configure it in `backend/.env` (gitignored, never commit it):
```
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=qwen/qwen3.8-flash   # optional, this is the default
```
Without a key set, this fallback is a silent no-op — Ask behaves exactly as
it did before, just without the extra fallback for questions regex can't
parse. Reasoning mode is explicitly disabled in the request (`qwen3.8-flash`
is a reasoning model) — with it on, a multi-tool-call answer took 50+
seconds; off, the same answer takes ~10s, since reasoning tokens were being
spent on every intermediate tool-call round, not just the final answer.

## Running locally

**Backend** (from `backend/`):
```
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python -m uvicorn app.main:app --port 8000
```
Note: `uvicorn --reload` was unreliable in this Windows setup (the reloader
logged "Reloading..." but didn't actually swap the worker process) — after
changing backend code, stop and restart the server manually rather than
trusting `--reload`.

**Frontend** (from `frontend/`):
```
npm install
npm run dev
```
Opens on `http://localhost:5173`; `/api/*` is proxied to `http://127.0.0.1:8000`
(see `vite.config.ts`). From the login page, either click **"Try the demo"**
(instant, pre-loaded with `PROGRESS 1.xlsx`) or sign up for your own account
and upload a workbook from the Upload page.

## Deploying later

Both halves read their configuration from environment variables so the same
code works locally and once deployed:

- Backend: `PROGRESS_APP_DATA_DIR` (where `progress.db` and uploads live — mount
  a persistent volume here), `PROGRESS_APP_CORS_ORIGINS` (comma-separated
  frontend origin(s)), `PROGRESS_APP_JWT_SECRET` (**required** to set to a real
  secret before any non-local deployment — see Accounts section above).
- Frontend: `VITE_API_BASE` (defaults to `/api`; point it at the backend's
  public URL, or serve both behind the same reverse-proxy path).

**Known limitation**: the backend keeps its one current dataset in a SQLite
file on local disk (each upload replaces the previous snapshot). That's fine
on a regular server/VM/Docker container with a persistent disk, but it will
**not** work on a stateless/serverless host (e.g. Vercel functions) without
swapping SQLite for a hosted database — the repository layer
(`app/db/repository.py`) is the one place that would need to change.

## How the data model works

The workbook layout is template-specific (verified against `PROGRESS 1.xlsx`):
row 1 has merged section headers (FA-1, FA-2, SA-1, Attendance, Staff
Particulars), row 2 has subject/month names, row 3 has Marks/Grade or
"WORKING DAYS=N" sub-labels, and student rows start at row 4. The parser
(`backend/app/parsing/xlsx_parser.py`) detects phase blocks (FA*, SA*,
Pre-Final) dynamically from the row-1 merges, so a future upload with extra
columns (e.g. an SA-2 block added mid-year) is picked up automatically without
code changes. The Staff Particulars block is a vertical legend (per-section
subject-teacher list + one headmaster name), not row-aligned student data, so
it's parsed separately.

Marking scheme (FA = /50 per subject, SA = /100 except Physical Science and
Biology at /50) isn't stored in the sheet — it's the standard AP/Telangana CCE
convention and is hardcoded in `backend/app/core/config.py`. The grade→pass/fail
rule (only grade `D2` fails) comes from a legend embedded in the sheet itself,
encoded in `backend/app/reports/grading.py`.

School name, UDISE code, class label, and headmaster contact phone aren't in
the spreadsheet either — set them once on the Settings page.

## Not built yet

- **Google Drive folder connector**: deferred per original scope discussion —
  local file upload is fully working; Drive needs a Google Cloud OAuth client
  to be created first.
- **Non-English NL queries**: the query engine's entity/keyword matching is
  English-only (though it reads Telugu names fine, since matching works on the
  Latin-script names as entered in the sheet).
