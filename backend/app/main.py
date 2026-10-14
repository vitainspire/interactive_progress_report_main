from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import accounts, auth, classes, dashboard, query, school_classes, settings, students, textbooks, upload
from app.core.config import CORS_ORIGINS
from app.core.seed_demo import ensure_demo_account
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_demo_account()
    yield


app = FastAPI(title="Interactive Progress Report API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(accounts.router, prefix="/api")
app.include_router(school_classes.router, prefix="/api")
app.include_router(textbooks.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(students.router, prefix="/api")
app.include_router(classes.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(query.router, prefix="/api")
app.include_router(settings.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
