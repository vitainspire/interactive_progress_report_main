"""Review/confirm endpoints for a school's own uploaded syllabus/exam-
blueprint documents (see app/integrations/syllabus_extraction.py for how
they're produced, app/db/reference_documents.py for the storage). An
extraction is never trusted automatically — it sits as `status='pending'`
until a teacher reviews it here and confirms it, at which point it's written
into syllabus_chapter/subject_blueprint/subject_exam_info scoped to their
account."""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.db import reference_documents as repo
from app.db.database import session
from app.reports.subject_analysis import classify_subject

router = APIRouter(prefix="/reference-documents", tags=["reference-documents"])

# Real Indian school documents often print the grade as a Roman numeral
# (e.g. "Class X") rather than "10" — the extraction prompt already asks
# the model to convert this itself, but normalizing it again here is a
# cheap defense-in-depth: this app's class_level is always the plain
# numeral everywhere else (schema.sql, syllabus_seed.py, the Upload page's
# class picker), and a mismatch here would silently break every lookup
# with no visible error, which a teacher skimming the review form could
# easily miss.
_ROMAN_CLASS_LEVELS = {"VI": "6", "VII": "7", "VIII": "8", "IX": "9", "X": "10"}


def _normalize_class_level(value: str) -> str:
    return _ROMAN_CLASS_LEVELS.get(value.strip().upper(), value.strip())


def _doc_out(row: dict) -> dict:
    return {
        "id": row["id"],
        "file_name": row["file_name"],
        "mime_type": row["mime_type"],
        "status": row["status"],
        "error": row["error"],
        "created_at": row["created_at"],
        "extracted": json.loads(row["extracted_json"]) if row["extracted_json"] else None,
    }


@router.get("")
def list_reference_documents(status: str | None = None, current_user=Depends(get_current_user)):
    with session() as conn:
        rows = repo.list_reference_documents(conn, current_user["id"], status)
        return [_doc_out(r) for r in rows]


class ReferenceDocumentUpdate(BaseModel):
    subject_guess: str | None = None
    class_level_guess: str | None = None
    document_type: str | None = None
    chapters: list[dict] | None = None
    topics: list[dict] | None = None
    exam_format: str | None = None
    tips: list[str] | None = None


@router.put("/{doc_id}")
def update_reference_document(doc_id: int, req: ReferenceDocumentUpdate, current_user=Depends(get_current_user)):
    """A teacher correcting the LLM's guess (wrong subject, a missed/garbled
    chapter, wrong marks) before confirming it — merges only the fields
    they sent into whatever's already stored, so a partial edit (e.g. just
    fixing the subject name) doesn't wipe the rest of the extraction."""
    with session() as conn:
        row = repo.get_reference_document(conn, current_user["id"], doc_id)
        if not row:
            raise HTTPException(404, "Reference document not found")
        extracted = json.loads(row["extracted_json"]) if row["extracted_json"] else {}
        for field, value in req.model_dump(exclude_unset=True).items():
            extracted[field] = value
        repo.update_reference_document_review(conn, current_user["id"], doc_id, json.dumps(extracted))
        updated = repo.get_reference_document(conn, current_user["id"], doc_id)
        return _doc_out(updated)


@router.post("/{doc_id}/confirm")
def confirm_reference_document(doc_id: int, force: bool = False, current_user=Depends(get_current_user)):
    """Writes the (possibly teacher-edited) extraction into the live
    syllabus_chapter/subject_blueprint/subject_exam_info tables, scoped to
    this account — the only place in the app that writes to those tables
    from an API route rather than a startup seed script. Confirming replaces
    whatever this account already confirmed for the same (class, subject) —
    e.g. two photos of the same syllabus chart — so without `force=true` a
    pre-existing confirmed set blocks with a 409 instead of silently
    disappearing."""
    with session() as conn:
        row = repo.get_reference_document(conn, current_user["id"], doc_id)
        if not row:
            raise HTTPException(404, "Reference document not found")
        if row["status"] == "confirmed":
            raise HTTPException(409, "This document has already been confirmed")
        if not row["extracted_json"]:
            raise HTTPException(422, "Nothing was extracted from this document to confirm")

        extracted = json.loads(row["extracted_json"])
        raw_subject = (extracted.get("subject_guess") or "").strip()
        class_level = _normalize_class_level(extracted.get("class_level_guess") or "")
        document_type = extracted.get("document_type")
        if not raw_subject or not class_level:
            raise HTTPException(422, "Set the subject and class level (via PUT) before confirming — they couldn't be read from the document.")

        # Canonicalize to the exact uppercase subject key the lookup
        # functions (get_chapters/get_blueprint/get_exam_info) query by —
        # storing the raw free-form guess here would silently make this
        # data unreachable later, since those always query the canonical form.
        subject = classify_subject(raw_subject)
        if not subject:
            raise HTTPException(
                422,
                f"Couldn't recognize '{raw_subject}' as one of this app's known subjects "
                "(Telugu/Hindi/English/Maths/Physical Science/Biology/Social) — edit the subject (via PUT) "
                "to one of those before confirming.",
            )

        if document_type == "syllabus":
            chapters = extracted.get("chapters") or []
            if not chapters:
                raise HTTPException(422, "No chapters to confirm — edit this document's chapters first.")
            for i, ch in enumerate(chapters, start=1):
                if ch.get("chapter_no") in (None, ""):
                    raise HTTPException(422, f"Chapter {i} ('{ch.get('chapter_name') or 'untitled'}') is missing a chapter number — fill it in before confirming.")
                if not (ch.get("chapter_name") or "").strip():
                    raise HTTPException(422, f"Chapter {i} (no. {ch.get('chapter_no')}) is missing a name — fill it in before confirming.")
            existing = repo.count_syllabus_chapters_for_account(conn, current_user["id"], class_level, subject)
            if existing and not force:
                raise HTTPException(
                    409,
                    f"Class {class_level} {subject} already has {existing} confirmed chapter(s) from an earlier document. "
                    "Confirming this one will replace them entirely, not merge. If that's what you want, confirm again to proceed.",
                )
            repo.replace_syllabus_chapters_for_account(conn, current_user["id"], class_level, subject, chapters)
        elif document_type == "blueprint":
            topics = extracted.get("topics") or []
            if not topics:
                raise HTTPException(422, "No topics to confirm — edit this document's topics first.")
            for i, t in enumerate(topics, start=1):
                if not (t.get("topic_name") or "").strip():
                    raise HTTPException(422, f"Topic {i} is missing a name — fill it in before confirming.")
                if t.get("marks") in (None, ""):
                    raise HTTPException(422, f"Topic {i} ('{t.get('topic_name')}') is missing marks — fill it in before confirming (use 0 if the blueprint really shows none).")
            existing = repo.count_subject_blueprint_for_account(conn, current_user["id"], class_level, subject)
            if existing and not force:
                raise HTTPException(
                    409,
                    f"Class {class_level} {subject} already has a confirmed blueprint ({existing} topic(s)) from an earlier document. "
                    "Confirming this one will replace it entirely, not merge. If that's what you want, confirm again to proceed.",
                )
            repo.replace_subject_blueprint_for_account(conn, current_user["id"], class_level, subject, topics)
            repo.replace_subject_exam_info_for_account(
                conn, current_user["id"], class_level, subject, extracted.get("exam_format"), extracted.get("tips") or []
            )
        else:
            raise HTTPException(422, "Set this document's type to 'syllabus' or 'blueprint' (via PUT) before confirming.")

        repo.set_reference_document_status(conn, current_user["id"], doc_id, "confirmed")
        return {"ok": True, "subject": subject, "class_level": class_level, "document_type": document_type}


@router.post("/{doc_id}/reject")
def reject_reference_document(doc_id: int, current_user=Depends(get_current_user)):
    with session() as conn:
        if not repo.set_reference_document_status(conn, current_user["id"], doc_id, "rejected"):
            raise HTTPException(404, "Reference document not found")
    return {"ok": True}
