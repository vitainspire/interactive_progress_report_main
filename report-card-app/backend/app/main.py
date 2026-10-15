from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import auth, batches, integrations, public
from app.core.config import CORS_ORIGINS
from app.db.database import close_pool, init_db, session

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    close_pool()


app = FastAPI(title="Report Card Generator API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(batches.router, prefix="/api")
app.include_router(integrations.router, prefix="/api")
app.include_router(public.router, prefix="/api")

# Decorative, non-sensitive assets only (e.g. per-subject background images
# on the parent report) — never a path for anything that needs auth or
# could leak student data, since StaticFiles serves this directory as-is
# to anyone.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/health")
def health(response: Response):
    """Checks the server process AND that it can actually reach the
    database — a plain "server is up" check would stay green even if
    DATABASE_URL were wrong or Supabase were unreachable from wherever
    this is deployed, which is exactly the kind of thing that differs
    between local testing and a real deployment's network path."""
    try:
        with session() as conn:
            conn.execute("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        response.status_code = 503
        # Only the exception type is returned, never str(exc) — a
        # connection failure message can sometimes echo parts of the
        # connection string, which must never reach an API response.
        return {"status": "error", "database": "unreachable", "error_type": type(exc).__name__}
