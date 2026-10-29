"""Deterministic (no LLM, no extra API cost) exam-focus guidance — distinct
from study_plan.py's AI-generated plan. A subject's confirmed syllabus
chapters and its exam blueprint (see app/api/reference_documents.py) are
both already real, trusted data once a teacher's confirmed them; this just
does arithmetic over them:

1. Works out which exam is coming up NEXT for this student (not the one
   they just took — a parent already knows how that one went) and which
   chapters that exam is likely to cover, assuming chapters are taught
   roughly in the order they're numbered (the only ordering signal a
   syllabus reliably gives).
2. Separately, pulls the highest-marks topics straight from the exam
   blueprint — this describes the final public exam's overall weightage
   across the whole syllabus, not any one internal exam, so it's shown
   as its own thing rather than forced to line up chapter-for-chapter
   with #1 (a blueprint topic's wording and a syllabus chapter's wording
   don't always match closely enough to safely auto-pair them).

The chapter split assumes the general FA/SA academic-year shape common to
Indian state boards — some number of Formative exams interleaved evenly
between some number of Summative checkpoints (4 FA + 2 SA, the AP/Telangana
pattern, by default) — regardless of how many of those a particular batch's
sheet has been synced with so far (a batch's exam_order only ever contains
exams that already have marks entered, so "what's upcoming" is almost
always NOT in exam_order yet). `total_fa`/`total_sa` come from that batch's
own settings (see app/db/batches.py's BatchSettings, set at upload time),
not a hardcoded constant, so a school running a different exam count still
gets a correctly-shaped sequence.

Returns None whenever there's nothing confirmed to build this from, same
"hide rather than show something empty/wrong" rule as the rest of this
app's optional report sections.
"""
from __future__ import annotations

import math
import re

_EXAM_KEY_RE = re.compile(r"^(FA|SA)-?(\d+)$", re.I)


def build_exam_sequence(total_fa: int, total_sa: int) -> list[str]:
    """The full school-year exam order implied by this batch's own FA/SA
    counts — FAs split as evenly as possible across that many SA
    checkpoints, each checkpoint ending in that SA. 4 FA + 2 SA (the
    default) produces FA-1, FA-2, SA-1, FA-3, FA-4, SA-2; other counts
    generalize the same shape instead of assuming that exact split."""
    if total_fa <= 0:
        return [f"SA-{i}" for i in range(1, total_sa + 1)]
    if total_sa <= 0:
        return [f"FA-{i}" for i in range(1, total_fa + 1)]
    base, extra = divmod(total_fa, total_sa)
    sequence: list[str] = []
    fa_num = 1
    for sa_num in range(1, total_sa + 1):
        bucket_size = base + (1 if sa_num <= extra else 0)
        for _ in range(bucket_size):
            sequence.append(f"FA-{fa_num}")
            fa_num += 1
        sequence.append(f"SA-{sa_num}")
    return sequence


def next_exam_slot(completed_exam_keys: list[str], total_fa: int = 4, total_sa: int = 2) -> str | None:
    """The next exam in this batch's own sequence that this student hasn't
    taken yet — typically not yet in the batch's own exam_order, since that
    only lists exams with marks already entered. None once every slot in
    the sequence is behind them (end of the school year)."""
    done = {k.strip().upper() for k in completed_exam_keys}
    for slot in build_exam_sequence(total_fa, total_sa):
        if slot not in done:
            return slot
    return None


def chapters_for_slot(chapters: list[dict], slot_key: str, total_fa: int = 4, total_sa: int = 2) -> list[dict]:
    """`chapters` need not be sorted. An FA slot gets its own even slice of
    the full chapter list (by chapter_no order); an SA slot is cumulative
    — every chapter from the FA slots that would have happened by then."""
    chapters_sorted = sorted(chapters, key=lambda c: c["chapter_no"])
    match = _EXAM_KEY_RE.match(slot_key or "")
    if not match or not chapters_sorted or total_fa <= 0:
        return []
    kind, num = match.group(1).upper(), int(match.group(2))
    chunk_size = math.ceil(len(chapters_sorted) / total_fa)
    if kind == "FA":
        start = (num - 1) * chunk_size
        return chapters_sorted[start : start + chunk_size]
    fa_chunks_covered = round(num * total_fa / total_sa) if total_sa else total_fa
    return chapters_sorted[: fa_chunks_covered * chunk_size]


def top_weighted_topics(topics: list[dict], limit: int = 3) -> list[dict]:
    return sorted(topics, key=lambda t: -(t["marks"] + (t.get("choice_marks") or 0)))[:limit]


def build_exam_focus(
    chapters: list[dict], topics: list[dict], completed_exam_keys: list[str],
    total_fa: int = 4, total_sa: int = 2,
) -> dict | None:
    """`chapters`/`topics` are this subject's confirmed syllabus_chapter/
    subject_blueprint rows (as plain dicts). `completed_exam_keys` is every
    exam key this student already has a result for (in this subject, or
    for the student overall if a per-subject list isn't available) — used
    only to work out what's next, never to look backward. `total_fa`/
    `total_sa` should come from this batch's own BatchSettings. Needs a
    confirmed blueprint at minimum (the "what's worth the most marks"
    half); the chapter split is only added on top of that when a syllabus
    also happens to be on file, and only when there IS a next exam (the
    sequence isn't already finished)."""
    if not topics:
        return None
    slot = next_exam_slot(completed_exam_keys, total_fa, total_sa)
    covered = chapters_for_slot(chapters, slot, total_fa, total_sa) if (slot and chapters) else []
    top_topics = top_weighted_topics(topics)
    return {
        "exam": slot,
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
        parts.append(f"రాబోయే {result['exam']} పరీక్షలో ఈ పాఠాలు ఉండవచ్చు: {chapter_list}.")
    topic_bits = ", ".join(_topic_label(t) for t in result["top_topics"])
    parts.append(f"{subject}లో మొత్తం పరీక్ష బ్లూప్రింట్ ప్రకారం ఎక్కువ మార్కులు ఉన్న టాపిక్స్: {topic_bits} — వీటిపై ఎక్కువ దృష్టి పెడితే మార్కులు పెరుగుతాయి.")
    return " ".join(parts)
