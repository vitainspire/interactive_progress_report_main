"""Reads one uploaded syllabus/exam-blueprint document (a PDF or image from
a school's Drive folder — see app/integrations/google_drive_folder.py) and
asks a vision/document-capable LLM to turn it into the same structured shape
syllabus_chapter/subject_blueprint/subject_exam_info already use, so a
teacher's later confirmation can insert it directly. Deliberately a
*separate* integration from chat.py: that one talks to a text-only model
(OPENROUTER_MODEL) for the parent chat/study-plan features, this one needs a
document-capable model (OPENROUTER_DOCUMENT_MODEL), which is typically a
different, pricier one — conflating the two would make every chat message
pay that cost.

The result is never trusted blindly: a scanned textbook index or a
government blueprint PDF extracts imperfectly (OCR-like failure modes), so
this only ever produces a *pending* row for a teacher to confirm/correct —
see app/api/reference_documents.py.
"""
from __future__ import annotations

import base64
import json

import httpx

from app.core.config import OPENROUTER_API_KEY, OPENROUTER_DOCUMENT_MODEL

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_IMAGE_MIME_PREFIXES = ("image/",)

EXTRACTION_SYSTEM_PROMPT = """You read one page (or a few pages) of an Indian school document — either a textbook's syllabus/table-of-contents, or an official exam blueprint/model-paper that lists how many marks each topic is worth. You turn it into strict JSON, nothing else: no markdown, no commentary, no code fences.

Output exactly this shape:
{
  "subject_guess": "<subject name as written in the document, e.g. 'Physical Science', 'Telugu'>",
  "class_level_guess": "<grade/class as a plain Arabic numeral string, e.g. '10' — convert a Roman numeral if that's how it's written (Class X -> '10', Class IX -> '9'), or null if not determinable>",
  "document_type": "syllabus" | "blueprint" | "unknown",
  "chapters": [
    {"chapter_no": <int>, "chapter_name": "<string>", "genre": null, "theme": null, "author": null, "month": null, "periods": null, "page_range": null}
  ],
  "topics": [
    {"topic_name": "<string>", "marks": <int>, "choice_marks": <int or null>}
  ],
  "exam_format": "<a short description of the exam's structure/timing/total marks if stated, else null>",
  "tips": ["<short exam-technique tip>", ...]
}

Rules:
- If this is a syllabus/table-of-contents page, fill "chapters" with every chapter you can actually read, in order, and leave "topics"/"exam_format"/"tips" as empty/null. Only fill in genre/theme/author/month/periods/page_range when the document actually states them — never invent values.
- If this is an exam blueprint/model paper, fill "topics" with each topic and its real marks weightage, and "exam_format"/"tips" if stated, leaving "chapters" empty.
- Never invent a chapter or topic that isn't actually in the document. If you can't read it confidently, leave the list empty rather than guessing.
- If you cannot determine the subject or document type at all, set them to null/"unknown" rather than guessing."""


class ExtractionNotConfigured(RuntimeError):
    pass


class ExtractionError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(OPENROUTER_API_KEY)


def _content_part(file_bytes: bytes, mime_type: str, file_name: str) -> dict:
    data_url = f"data:{mime_type};base64,{base64.b64encode(file_bytes).decode('ascii')}"
    if mime_type.startswith(_IMAGE_MIME_PREFIXES):
        return {"type": "image_url", "image_url": {"url": data_url}}
    # application/pdf — OpenRouter's "file" content part, supported by
    # document-capable models (including the default OPENROUTER_DOCUMENT_MODEL).
    return {"type": "file", "file": {"filename": file_name, "file_data": data_url}}


def extract_document(file_bytes: bytes, mime_type: str, file_name: str) -> dict:
    """Returns the parsed JSON dict described in EXTRACTION_SYSTEM_PROMPT.
    Raises ExtractionError on anything that isn't a clean, parseable JSON
    response — callers (see app/api/batches.py's import flow) catch this
    per-document and record it as a failed subject_reference_document row,
    the same error-isolation style already used for a bad spreadsheet file
    in that same import loop."""
    if not is_configured():
        raise ExtractionNotConfigured("Syllabus extraction isn't configured on this server (missing OPENROUTER_API_KEY).")

    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"File name: {file_name}"},
                _content_part(file_bytes, mime_type, file_name),
            ],
        },
    ]

    try:
        response = httpx.post(
            OPENROUTER_URL,
            json={
                "model": OPENROUTER_DOCUMENT_MODEL,
                "messages": messages,
                "max_tokens": 4000,
                "response_format": {"type": "json_object"},
                "provider": {"data_collection": "deny"},
            },
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            timeout=90,
        )
    except httpx.HTTPError as exc:
        raise ExtractionError(f"Could not reach the document-reading service: {exc}") from exc

    if response.status_code >= 400:
        raise ExtractionError(f"Document-reading service error ({response.status_code}): {response.text}")

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ExtractionError(f"Unexpected response shape from document-reading service: {data}") from exc

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"Document-reading service did not return valid JSON: {content[:500]}") from exc

    parsed.setdefault("subject_guess", None)
    parsed.setdefault("class_level_guess", None)
    parsed.setdefault("document_type", "unknown")
    parsed.setdefault("chapters", [])
    parsed.setdefault("topics", [])
    parsed.setdefault("exam_format", None)
    parsed.setdefault("tips", [])
    return parsed
