"""LLM fallback for the Ask feature, used only when the regex engine
(app.nlq.engine) can't match a question at all.

Safety model: the LLM never invents numbers. It can only answer by calling
the tools below, each of which is a thin wrapper around the same repository
functions the regex engine itself uses — so every number in its answer came
from a real SQL query, scoped to the caller's own account. The LLM's job is
purely to understand the question, pick the right tool(s), and phrase the
final answer in plain English.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections import Counter

import httpx

from app.core.config import OPENROUTER_API_KEY, OPENROUTER_MODEL
from app.db import repository as repo
from app.db import textbooks as repo_tb
from app.nlq.entities import extract_phase, extract_section, extract_subject, extract_students
from app.nlq.vocab import Vocab, load_vocab
from app.reports import insights

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOOL_ROUNDS = 4
REQUEST_TIMEOUT = 20.0

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_student_summary",
            "description": "Get a student's full profile: latest result, rank, attendance, every exam phase's totals, and which subjects are improving/declining/steady. Use for any question about one named student.",
            "parameters": {
                "type": "object",
                "properties": {"student_name": {"type": "string", "description": "The student's name (or part of it) as mentioned by the user"}},
                "required": ["student_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_subject_stats",
            "description": "Average/highest/lowest marks for one subject in one exam phase, optionally filtered to one section.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phase_code": {"type": "string", "description": "e.g. FA1, SA2, PREFINAL"},
                    "subject": {"type": "string"},
                    "section": {"type": "string"},
                },
                "required": ["phase_code", "subject"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_class_summary",
            "description": "Student count, average total marks, pass count and fail count for one exam phase, optionally filtered to one section.",
            "parameters": {
                "type": "object",
                "properties": {"phase_code": {"type": "string"}, "section": {"type": "string"}},
                "required": ["phase_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_students",
            "description": "The top-ranked students by total marks in an exam phase, optionally filtered to one section.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phase_code": {"type": "string"},
                    "section": {"type": "string"},
                    "limit": {"type": "integer", "description": "How many students to return, default 5"},
                },
                "required": ["phase_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_failing_students",
            "description": "Students who failed (grade D2 or lower), optionally filtered by exam phase, subject, and/or section. Omit filters to get all failures.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phase_code": {"type": "string"},
                    "subject": {"type": "string"},
                    "section": {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_sections",
            "description": "Compare every section's average performance in an exam phase — overall total, or one specific subject if given.",
            "parameters": {
                "type": "object",
                "properties": {"phase_code": {"type": "string"}, "subject": {"type": "string"}},
                "required": ["phase_code"],
            },
        },
    },
]


def _resolve_phase(vocab: Vocab, raw: str | None) -> str | None:
    if not raw:
        return None
    code = extract_phase(raw.lower(), vocab.phase_codes)
    return code or raw.upper().replace("-", "").replace(" ", "")


def _resolve_subject(vocab: Vocab, raw: str | None) -> str | None:
    if not raw:
        return None
    return extract_subject(raw.lower(), vocab.subjects) or raw.upper()


def _resolve_section(vocab: Vocab, raw: str | None) -> str | None:
    if not raw:
        return None
    return extract_section(raw.lower(), vocab.sections) or raw.upper().replace("SECTION", "").strip()


def _tool_get_student_summary(conn: sqlite3.Connection, user_id: int, class_id: int, vocab: Vocab, args: dict) -> dict:
    ids, names = extract_students(args.get("student_name", ""), vocab)
    if not ids:
        return {"error": f"No student found matching '{args.get('student_name')}'"}
    if len(ids) > 1:
        return {"error": "Ambiguous name, matches multiple students", "candidates": names[:8]}
    sid = ids[0]
    student = repo.get_student(conn, user_id, class_id, sid)
    summaries = repo.get_student_exam_summaries(conn, user_id, class_id, sid)
    att = repo.get_student_attendance_summary(conn, user_id, class_id, sid)
    exam_results = repo.get_student_exam_results(conn, user_id, class_id, sid)
    phase_order = [p["code"] for p in repo.list_phases(conn, user_id, class_id)]
    trends = insights.build_subject_series(exam_results, phase_order)
    return {
        "name": student["name"],
        "section": student["section"],
        "exam_history": [
            {"phase": r["phase_code"], "total_marks": r["total_marks"], "max_total": r["max_total"], "grade": r["total_grade"], "result": r["result"], "rank": r["rank"]}
            for r in summaries
        ],
        "attendance": {
            "present": att["total_present"] if att else None,
            "working_days": att["total_working_days"] if att else None,
        },
        "subject_trends": [{"subject": s.subject, "direction": s.direction, "percentages": [p.pct for p in s.points]} for s in trends],
    }


def _tool_get_subject_stats(conn: sqlite3.Connection, user_id: int, class_id: int, vocab: Vocab, args: dict) -> dict:
    phase = _resolve_phase(vocab, args.get("phase_code"))
    subject = _resolve_subject(vocab, args.get("subject"))
    section = _resolve_section(vocab, args.get("section"))
    result = repo.subject_stats(conn, user_id, class_id, phase, subject, section)
    topics = repo_tb.get_textbook_topics(conn, user_id, class_id, subject) if subject else []
    if topics:
        result["textbook_chapters"] = [t["title"] for t in topics]
    return result


def _tool_get_class_summary(conn: sqlite3.Connection, user_id: int, class_id: int, vocab: Vocab, args: dict) -> dict:
    phase = _resolve_phase(vocab, args.get("phase_code"))
    section = _resolve_section(vocab, args.get("section"))
    return repo.class_summary(conn, user_id, class_id, phase, section)


def _tool_get_top_students(conn: sqlite3.Connection, user_id: int, class_id: int, vocab: Vocab, args: dict) -> dict:
    phase = _resolve_phase(vocab, args.get("phase_code"))
    section = _resolve_section(vocab, args.get("section"))
    limit = int(args.get("limit") or 5)
    rows = repo.top_students(conn, user_id, class_id, phase, section, limit)
    return {"students": [{"name": r["name"], "section": r["section"], "rank": r["rank"], "total_marks": r["total_marks"], "max_total": r["max_total"]} for r in rows]}


def _tool_get_failing_students(conn: sqlite3.Connection, user_id: int, class_id: int, vocab: Vocab, args: dict) -> dict:
    phase = _resolve_phase(vocab, args.get("phase_code")) if args.get("phase_code") else None
    subject = _resolve_subject(vocab, args.get("subject")) if args.get("subject") else None
    section = _resolve_section(vocab, args.get("section")) if args.get("section") else None
    rows = repo.students_failed(conn, user_id, class_id, phase, subject, section)
    by_subject = Counter(r["subject"] for r in rows)
    return {
        "count": len(rows),
        "by_subject": [{"subject": s, "count": c} for s, c in by_subject.most_common()],
        "students": [{"name": r["name"], "section": r["section"], "subject": r["subject"], "phase": r["phase_code"], "marks": r["marks"], "max_marks": r["max_marks"], "grade": r["grade"]} for r in rows[:30]],
    }


def _tool_compare_sections(conn: sqlite3.Connection, user_id: int, class_id: int, vocab: Vocab, args: dict) -> dict:
    phase = _resolve_phase(vocab, args.get("phase_code"))
    subject = _resolve_subject(vocab, args.get("subject")) if args.get("subject") else None
    results = []
    for sec in vocab.sections:
        if subject:
            stats = repo.subject_stats(conn, user_id, class_id, phase, subject, sec)
            results.append({"section": sec, "average": stats.get("average")})
        else:
            summary = repo.class_summary(conn, user_id, class_id, phase, sec)
            results.append({"section": sec, "average_total": summary.get("average_total"), "passed": summary["passed"], "failed": summary["failed"]})
    return {"comparison": results}


TOOL_DISPATCH = {
    "get_student_summary": _tool_get_student_summary,
    "get_subject_stats": _tool_get_subject_stats,
    "get_class_summary": _tool_get_class_summary,
    "get_top_students": _tool_get_top_students,
    "get_failing_students": _tool_get_failing_students,
    "compare_sections": _tool_compare_sections,
}


def _system_prompt(vocab: Vocab) -> str:
    return (
        "You are a helpful assistant answering a teacher's questions about their class's exam and attendance data. "
        "You MUST use the provided tools to fetch real numbers — never guess or invent a statistic. "
        "If a tool call returns an error or no data, say so plainly instead of making something up. "
        "Be efficient: call at most 2-3 tools total, then give your final answer — don't call a tool "
        "separately for every individual student unless the user explicitly asked you to list each one. "
        "For broad/open-ended questions (e.g. 'what should I focus on'), one or two well-chosen tool calls "
        "(like the class summary and the failing-students list) are enough to answer well. "
        "If a subject-stats result includes textbook_chapters, name a couple of the actual chapters when "
        "suggesting what to focus on, instead of just repeating the subject name. "
        "Keep answers concise and factual (2-4 sentences), in plain English.\n\n"
        f"Valid sections in this dataset: {', '.join(vocab.sections) or 'none'}\n"
        f"Valid subjects: {', '.join(vocab.subjects) or 'none'}\n"
        f"Valid exam phase codes: {', '.join(vocab.phase_codes) or 'none'}"
    )


def try_llm_fallback(conn: sqlite3.Connection, user_id: int, class_id: int, question: str):
    """Returns a QueryAnswer-shaped dict, or None if the LLM fallback isn't
    configured (caller should then show its own generic fallback message)."""
    if not OPENROUTER_API_KEY:
        return None

    vocab = load_vocab(conn, user_id, class_id)
    messages = [
        {"role": "system", "content": _system_prompt(vocab)},
        {"role": "user", "content": question},
    ]

    chart = None
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            for _ in range(MAX_TOOL_ROUNDS):
                resp = client.post(
                    OPENROUTER_URL,
                    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                    json={"model": OPENROUTER_MODEL, "messages": messages, "tools": TOOLS, "reasoning": {"enabled": False}},
                )
                resp.raise_for_status()
                message = resp.json()["choices"][0]["message"]
                tool_calls = message.get("tool_calls")

                if not tool_calls:
                    answer = (message.get("content") or "").strip()
                    if not answer:
                        return {"answer": "I wasn't able to work out an answer to that.", "intent": "LLM_FALLBACK"}
                    return {"answer": answer, "intent": "LLM_FALLBACK", "chart": chart}

                messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": tool_calls})
                for call in tool_calls:
                    name = call["function"]["name"]
                    try:
                        args = json.loads(call["function"].get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    handler = TOOL_DISPATCH.get(name)
                    if handler is None:
                        result = {"error": f"Unknown tool '{name}'"}
                    else:
                        try:
                            result = handler(conn, user_id, class_id, vocab, args)
                        except Exception as exc:  # noqa: BLE001 - surface to the model, don't crash the request
                            logger.warning("LLM tool %s failed: %s", name, exc)
                            result = {"error": str(exc)}
                    if name == "get_failing_students" and not args.get("subject") and result.get("by_subject"):
                        phase_label = _resolve_phase(vocab, args.get("phase_code")) if args.get("phase_code") else None
                        chart = {
                            "type": "bar",
                            "title": "Failures by subject" + (f" — {phase_label}" if phase_label else " — all phases"),
                            "data": [{"name": b["subject"].title(), "value": b["count"]} for b in result["by_subject"][:10]],
                        }
                    messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, default=str)})

            return {"answer": "That question needed more lookups than I could do right now — try breaking it into smaller questions.", "intent": "LLM_FALLBACK"}
    except httpx.HTTPError as exc:
        logger.warning("OpenRouter request failed: %s", exc)
        return {"answer": "The AI assistant is temporarily unavailable — try rephrasing your question, or ask it in a simpler way.", "intent": "LLM_ERROR"}
