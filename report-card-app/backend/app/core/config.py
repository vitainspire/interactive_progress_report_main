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

# Defaults for a freshly-uploaded batch — editable afterwards per batch,
# matching the original tool's "Settings" panel (class strength / FA & SA
# exam totals / marks-per-subject used for the Total column and the AI
# analysis' grade-point thresholds).
DEFAULT_FA_TOTAL = 350
DEFAULT_SA_TOTAL = 600
DEFAULT_FA_MARKS_PER_SUBJECT = 50
DEFAULT_SA_MARKS_PER_SUBJECT = 100

# The base URL this server itself is reachable at — used to build the
# parent-facing report links sent over WhatsApp/SMS. For those links to
# actually open on a parent's phone, this must be a real public URL (not
# localhost) once the app is deployed somewhere.
PUBLIC_APP_BASE_URL = os.environ.get("REPORTCARD_APP_PUBLIC_BASE_URL", "http://localhost:8010").rstrip("/")

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
WHATSAPP_TEMPLATE_NAME = os.environ.get("WHATSAPP_TEMPLATE_NAME", "report_card_ready")
WHATSAPP_TEMPLATE_LANG = os.environ.get("WHATSAPP_TEMPLATE_LANG", "en_US")

# SMS fallback via Twilio — used only when WhatsApp isn't configured, or a
# specific send to that number fails (e.g. no WhatsApp account on it).
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_SMS_FROM = os.environ.get("TWILIO_SMS_FROM", "")
