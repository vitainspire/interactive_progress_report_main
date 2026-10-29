import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BACKEND_DIR / ".env")

# A Postgres connection string — Supabase gives you this under Project
# Settings -> Database -> Connection string (use the "Session" pooler URI,
# or the direct connection string, either works for a single long-running
# backend process like this one). There is no local-file fallback: this
# app always talks to Postgres now, never a bundled SQLite file, so data
# survives redeploys/restarts on hosts with no persistent disk.
DATABASE_URL = os.environ.get("DATABASE_URL", "")

CORS_ORIGINS = os.environ.get("REPORTCARD_APP_CORS_ORIGINS", "http://localhost:5175").split(",")

# A Google API key (same one used by the frontend's Drive picker) — used
# server-side to read publicly-shared Google Sheets/Drive folders (the
# "paste a link" and "import a Drive folder" upload modes) without any
# per-user OAuth. Only works against files/folders shared "Anyone with the
# link can view"; this key has no access to anything else.
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

# Defaults for a freshly-uploaded batch — editable afterwards per batch,
# matching the original tool's "Settings" panel (class strength / FA & SA
# exam totals / marks-per-subject used for the Total column and the AI
# analysis' grade-point thresholds).
DEFAULT_FA_TOTAL = 350
DEFAULT_SA_TOTAL = 600
DEFAULT_FA_MARKS_PER_SUBJECT = 50
DEFAULT_SA_MARKS_PER_SUBJECT = 100
# How many FA/SA exams a school's year has, used to generate the "upcoming
# exam" sequence in app/reports/exam_focus.py — the common AP/Telangana
# SSC pattern, overridable per batch at upload time.
DEFAULT_TOTAL_FA_EXAMS = 4
DEFAULT_TOTAL_SA_EXAMS = 2

# The base URL this server itself is reachable at — used to build the
# parent-facing report links sent over WhatsApp/SMS. For those links to
# actually open on a parent's phone, this must be a real public URL (not
# localhost) once the app is deployed somewhere.
PUBLIC_APP_BASE_URL = os.environ.get("REPORTCARD_APP_PUBLIC_BASE_URL", "http://localhost:8010").rstrip("/")

# The teacher-facing React app's own URL (the Vercel deployment) — distinct
# from PUBLIC_APP_BASE_URL above, which is this backend's own URL used for
# server-rendered parent report pages. Needed to build a password-reset
# link that opens the frontend's /reset-password route.
FRONTEND_BASE_URL = os.environ.get("REPORTCARD_APP_FRONTEND_BASE_URL", "http://localhost:5175").rstrip("/")

# Phone numbers from the sheet may just be a plain 10-digit number with no
# country code — this is prefixed on when normalizing to E.164 for
# WhatsApp/SMS. Change via env if most of your schools aren't in India.
DEFAULT_PHONE_COUNTRY_CODE = os.environ.get("REPORTCARD_APP_DEFAULT_COUNTRY_CODE", "91")

# Meta WhatsApp Cloud API — requires a Meta Business account, a verified
# WhatsApp Business phone number, and an approved message template (Cloud
# API refuses to send free-form text to someone who hasn't messaged the
# business first). The template needs exactly one body variable (the
# student's name) and a URL button with one variable (the report link's
# token) — see app/integrations/whatsapp.py for the exact payload shape.
WHATSAPP_CLOUD_API_TOKEN = os.environ.get("WHATSAPP_CLOUD_API_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_TEMPLATE_NAME = os.environ.get("WHATSAPP_TEMPLATE_NAME", "student_progress_report")
WHATSAPP_TEMPLATE_LANG = os.environ.get("WHATSAPP_TEMPLATE_LANG", "en_US")

# SMS fallback via Twilio — used only when WhatsApp isn't configured, or a
# specific send to that number fails (e.g. no WhatsApp account on it).
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_SMS_FROM = os.environ.get("TWILIO_SMS_FROM", "")

# Bhashini (MeitY/Digital India's free Indian-language AI API) — used to
# generate real Telugu speech audio server-side for the parent report's
# "Listen" button, instead of relying on the browser's own speechSynthesis
# (which only speaks real Telugu if that specific device has a Telugu
# voice installed — many don't). See app/integrations/bhashini.py.
BHASHINI_USER_ID = os.environ.get("BHASHINI_USER_ID", "")
BHASHINI_ULCA_API_KEY = os.environ.get("BHASHINI_ULCA_API_KEY", "")

# OpenRouter — powers the "Know About Student" chat, where a parent can ask
# free-form questions about their child and get answers grounded in that
# student's own report data (see app/integrations/chat.py and
# app/reports/chat_context.py). Get a key at openrouter.ai/keys.
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "qwen/qwen3.8-flash")

# Resend — sends the password-reset email (see app/integrations/email.py).
# Get a key at resend.com/api-keys. RESEND_FROM_EMAIL must be an address at
# a domain verified in Resend (or their shared test sender while testing
# without your own domain, which can only send to the account's own signup
# address until a domain is verified).
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "")

# A vision/document-capable model for reading an uploaded syllabus/exam-
# blueprint PDF or image (see app/integrations/syllabus_extraction.py) —
# kept separate from OPENROUTER_MODEL since that one's text-only and a
# document-capable model is typically a different (often pricier) one.
# flash-lite over plain flash: ~3x cheaper input / ~6x cheaper output on
# OpenRouter, and side-by-side testing against real syllabus/blueprint
# documents from this app's actual schools came back identical — a
# reasonable tradeoff here regardless, since every extraction already
# lands as a pending row a teacher reviews before it's ever trusted.
OPENROUTER_DOCUMENT_MODEL = os.environ.get("OPENROUTER_DOCUMENT_MODEL", "google/gemini-2.5-flash-lite")
