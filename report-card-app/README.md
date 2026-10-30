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
- **Syllabus-aware study plan & exam focus** — if a school uploads its own
  syllabus/exam-blueprint documents (PDFs/images dropped in the same Drive
  folder), the app extracts chapters and marks-weightage via an LLM, a
  teacher reviews/confirms the extraction, and confirmed data powers a
  real, chapter-specific study plan and "what's likely in the next exam"
  guidance. **Scoped per school — a school that hasn't uploaded its own
  syllabus simply sees nothing here, never another school's curriculum.**
- **Subject Analysis & Timetable/Substitution tools** — printable per-subject
  analysis reports for teachers, and a separate timetable generator +
  substitute-finder module.

See [`docs/APPLICATION_PIPELINE.md`](docs/APPLICATION_PIPELINE.md) for the
full data-flow/engineering shape of all of the above, stage by stage.

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
nullable `account_id`: `NULL` rows are template/global defaults that were
never meant to be shown as if they were a specific school's real curriculum
— the lookup functions only ever return an account's **own** confirmed data,
falling through to nothing (not to someone else's data) when a school
hasn't uploaded and confirmed its own.

## Running locally

**Backend** (from `backend/`):
```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python -m uvicorn app.main:app --port 8000
```
Needs a `.env` file (gitignored) with at least `DATABASE_URL` pointing at a
Postgres instance; see
[`docs/AWS_LAMBDA_DEPLOYMENT.md`](docs/AWS_LAMBDA_DEPLOYMENT.md) for the
full environment-variable list (WhatsApp/SMS/OpenRouter/etc. are all
optional — each integration silently no-ops when its own env vars aren't
set).

Note: `uvicorn --reload` has been unreliable in this setup (the reloader
logs "Reloading..." without actually swapping the worker) — after changing
backend code, stop and restart the server manually.

**Frontend** (from `frontend/`):
```bash
npm install
npm run dev
```
Opens on `http://localhost:5173`; `/api/*` proxies to
`http://127.0.0.1:8000` (see `vite.config.ts`).

## Project layout

```
backend/app/
  api/            FastAPI routers (auth, batches, timetable, public parent-facing routes, ...)
  integrations/   WhatsApp, SMS (Twilio), Google Drive/Sheets, OpenRouter chat, Bhashini TTS, email
  reports/        Report/page rendering (parent report, subject analysis, study plan, exam focus)
  parsing/        Spreadsheet parsing
  timetable/      Timetable generation & substitute-finder
  db/             Repository layer + schema/migrations
  lambda_handler.py   Mangum entry point used only in the Lambda container

frontend/src/
  pages/          One file per route (Dashboard, Upload, Batch, Student, Timetable, ...)
  components/     Shared UI pieces
  api/client.ts   Typed fetch wrapper
```
