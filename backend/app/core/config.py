"""App-wide configuration.

Values here are deployment knobs (env-overridable) plus the fixed marking
scheme used by this school's exam template. The spreadsheet itself never
states a subject's maximum marks — only the phase name ("FA-1 (each
subject out of 50)") hints at it in the generated report text — so the
scheme is encoded here rather than guessed from data.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BACKEND_DIR / ".env")
DATA_DIR = Path(os.environ.get("PROGRESS_APP_DATA_DIR", BACKEND_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "progress.db"
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

CORS_ORIGINS = os.environ.get("PROGRESS_APP_CORS_ORIGINS", "http://localhost:5173").split(",")

# Marking scheme (AP/Telangana CCE pattern): FA phases are /50 per subject;
# SA / Pre-Final phases are /100 per subject except Physical Science and
# Biology which stay /50 (separate practical weighting).
FA_SUBJECT_MAX = 50
SA_SUBJECT_MAX_DEFAULT = 100
SA_SUBJECT_MAX_REDUCED = 50
REDUCED_MAX_SUBJECTS = {"PHYSICAL SCIENCE", "BIOLOGY"}

DEFAULT_SCHOOL_NAME = os.environ.get("PROGRESS_APP_SCHOOL_NAME", "")
DEFAULT_SCHOOL_UDISE = os.environ.get("PROGRESS_APP_SCHOOL_UDISE", "")

# LLM fallback for the Ask feature — only used when the regex engine can't
# match a question at all. Absent key = fallback silently stays disabled.
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "qwen/qwen3.8-flash")
