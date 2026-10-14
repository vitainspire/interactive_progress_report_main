import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.deps import require_not_demo, require_role, tenant_id
from app.db import textbooks as repo_tb
from app.db.database import session
from app.parsing.textbook_parser import parse_toc

router = APIRouter(prefix="/textbooks", tags=["textbooks"])

_admin_only = require_role("admin")


class TopicIn(BaseModel):
    chapter_no: str | None = None
    title: str
    page: int | None = None


class TopicsUpdate(BaseModel):
    topics: list[TopicIn]


def _textbook_out(tb, topics) -> dict:
    return {
        "subject": tb["subject"],
        "filename": tb["filename"],
        "uploaded_at": tb["uploaded_at"],
        "topics": [{"chapter_no": t["chapter_no"], "title": t["title"], "page": t["page"]} for t in topics],
    }


@router.get("")
def list_textbooks(class_id: int, current_user=Depends(_admin_only)):
    with session() as conn:
        user_id = tenant_id(current_user)
        books = repo_tb.list_textbooks(conn, user_id, class_id)
        return [_textbook_out(b, repo_tb.get_textbook_topics(conn, user_id, class_id, b["subject"])) for b in books]


@router.post("")
async def upload_textbook(class_id: int, subject: str, file: UploadFile, current_user=Depends(_admin_only)):
    require_not_demo(current_user)
    if Path(file.filename or "").suffix.lower() != ".pdf":
        raise HTTPException(400, "Upload a .pdf file")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        entries = parse_toc(tmp_path)
    except Exception as exc:
        raise HTTPException(422, f"Could not read PDF: {exc}") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    with session() as conn:
        user_id = tenant_id(current_user)
        repo_tb.replace_textbook(
            conn, user_id, class_id, subject, file.filename or "textbook.pdf", [(e.chapter_no, e.title, e.page) for e in entries]
        )
        tb = repo_tb.get_textbook(conn, user_id, class_id, subject)
        topics = repo_tb.get_textbook_topics(conn, user_id, class_id, subject)
        return _textbook_out(tb, topics)


@router.put("/{subject}/topics")
def update_topics(subject: str, class_id: int, body: TopicsUpdate, current_user=Depends(_admin_only)):
    require_not_demo(current_user)
    with session() as conn:
        user_id = tenant_id(current_user)
        ok = repo_tb.set_topics(conn, user_id, class_id, subject, [(t.chapter_no, t.title, t.page) for t in body.topics])
        if not ok:
            raise HTTPException(404, "Textbook not found — upload a PDF for this subject first")
        tb = repo_tb.get_textbook(conn, user_id, class_id, subject)
        topics = repo_tb.get_textbook_topics(conn, user_id, class_id, subject)
        return _textbook_out(tb, topics)


@router.delete("/{subject}")
def remove_textbook(subject: str, class_id: int, current_user=Depends(_admin_only)):
    require_not_demo(current_user)
    with session() as conn:
        ok = repo_tb.delete_textbook(conn, tenant_id(current_user), class_id, subject)
        if not ok:
            raise HTTPException(404, "Textbook not found")
        return {"ok": True}
