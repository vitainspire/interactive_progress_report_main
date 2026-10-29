"""Deterministic (no LLM, no extra API cost) exam-focus guidance — distinct
from study_plan.py's AI-generated plan. A subject's confirmed syllabus
chapters and its exam blueprint (see app/api/reference_documents.py) are
both already real, trusted data once a teacher's confirmed them; this just
does arithmetic over them:

1. Splits the full-year chapter list across however many FA exams are
   actually on this student's sheet, assuming chapters are taught roughly
   in the order they're numbered (the only ordering signal a syllabus
   reliably gives). An FA exam gets its own slice; an SA exam (half-
   yearly/summative) gets every chapter from the FA slices up to and
   including its position, since it's cumulative by nature, not a new
   slice of content.
2. Separately, pulls the highest-marks topics straight from the exam
   blueprint — this describes the final public exam's overall weightage
   across the whole syllabus, not any one internal exam, so it's shown
   as its own thing rather than forced to line up chapter-for-chapter
   with #1 (a blueprint topic's wording and a syllabus chapter's wording
   don't always match closely enough to safely auto-pair them).

Returns None whenever there's nothing confirmed to build this from, same
"hide rather than show something empty/wrong" rule as the rest of this
app's optional report sections.
"""
from __future__ import annotations

import math


def chapters_by_exam(chapters: list[dict], exam_defs: list[dict]) -> dict[str, list[dict]]:
    chapters_sorted = sorted(chapters, key=lambda c: c["chapter_no"])
    fa_keys = [e["key"] for e in exam_defs if e["is_fa"]]
    if not fa_keys or not chapters_sorted:
        return {}
    chunk_size = math.ceil(len(chapters_sorted) / len(fa_keys))
    fa_chunks: dict[str, list[dict]] = {}
    for i, key in enumerate(fa_keys):
        fa_chunks[key] = chapters_sorted[i * chunk_size : (i + 1) * chunk_size]

    result = dict(fa_chunks)
    cumulative: list[dict] = []
    for e in exam_defs:
        if e["is_fa"]:
            cumulative = cumulative + fa_chunks.get(e["key"], [])
        else:
            result[e["key"]] = list(cumulative)
    return result


def top_weighted_topics(topics: list[dict], limit: int = 3) -> list[dict]:
    return sorted(topics, key=lambda t: -(t["marks"] + (t.get("choice_marks") or 0)))[:limit]


def build_exam_focus(chapters: list[dict], topics: list[dict], exam_defs: list[dict], latest_exam_key: str) -> dict | None:
    """`chapters`/`topics` are this subject's confirmed syllabus_chapter/
    subject_blueprint rows (as plain dicts). `latest_exam_key` is whichever
    exam this guidance is being shown for — typically the student's most
    recent exam in that subject. Needs a confirmed blueprint at minimum
    (the "what's worth the most marks" half); the chapter split is only
    added on top of that when a syllabus also happens to be on file."""
    if not topics:
        return None
    by_exam = chapters_by_exam(chapters, exam_defs)
    covered = by_exam.get(latest_exam_key, [])
    top_topics = top_weighted_topics(topics)
    return {
        "exam": latest_exam_key,
        "covered_chapters": [c["chapter_name"] for c in covered],
        "top_topics": [
            {"name": t["topic_name"], "marks": t["marks"], "choice_marks": t.get("choice_marks") or 0}
            for t in top_topics
        ],
    }


def format_exam_focus_text(result: dict, subject: str) -> str:
    """Plain-language Telugu rendering of build_exam_focus's result, in the
    same "fixed template around real data" style as chat_canned.py's other
    deterministic answers — so this card needs no LLM call and nothing to
    cache."""
    def _topic_label(t: dict) -> str:
        extra = f"+{t['choice_marks']}" if t["choice_marks"] else ""
        return f"{t['name']} ({t['marks']}{extra} మార్కులు)"

    parts = []
    if result["covered_chapters"]:
        chapter_list = ", ".join(result["covered_chapters"])
        parts.append(f"{result['exam']} పరీక్షలో ఈ పాఠాలు ఉండవచ్చు: {chapter_list}.")
    topic_bits = ", ".join(_topic_label(t) for t in result["top_topics"])
    parts.append(f"{subject}లో మొత్తం పరీక్ష బ్లూప్రింట్ ప్రకారం ఎక్కువ మార్కులు ఉన్న టాపిక్స్: {topic_bits} — వీటిపై ఎక్కువ దృష్టి పెడితే మార్కులు పెరుగుతాయి.")
    return " ".join(parts)
