"""Fallback for reading a school's already-built timetable when the
deterministic "master sheet" parser (app/parsing/timetable_parser.py) can't
make sense of the layout — a real school's own sheet often doesn't match
that one exact shape (days running down rows instead of across columns, a
different word than "TEACHER", a per-class printout, etc.). Only ever
engaged when the deterministic parser finds nothing usable on any sheet in
the workbook; never replaces it, since the deterministic path is free,
instant, and already correct for the layout it targets.

Sends the sheet's raw cell grid as plain text — no need for a vision model
here (app/integrations/syllabus_extraction.py's OPENROUTER_DOCUMENT_MODEL),
since this is already a real spreadsheet's cell values, not a scanned
document — and asks a text LLM (OPENROUTER_MODEL) to reconstruct the exact
same {"classes": {...}} shape app/parsing/timetable_parser.parse_rows
produces, so the rest of the import pipeline doesn't need to know which
path produced it.

The result is never trusted blindly: unlike the deterministic parser (whose
grid position is always exactly right, only the subject/teacher *codes*
need a human to name), an LLM reconstruction could misplace which day/
period/class a cell belongs to. app/api/timetable.py reports back
`source: "llm"` so the review screen can show the reconstructed grid itself
for a teacher to check, not just the code-naming step."""
from __future__ import annotations

import json

import httpx
from langsmith import traceable

from app.core.config import OPENROUTER_API_KEY, OPENROUTER_MODEL

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_VALID_DAYS = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}

# Characters, not tokens — keeps a huge or mostly-blank sheet from paying for
# (and potentially truncating badly on) a pointlessly large prompt.
_MAX_GRID_TEXT = 20_000

EXTRACTION_SYSTEM_PROMPT = """You read the raw cell contents of one sheet from a school's weekly timetable workbook, dumped below as plain text (one line per non-empty row, "column=value" pairs, empty cells omitted). It's some kind of day-by-day, period-by-period grid, but the exact layout varies by school: days might run across columns or down rows, periods might be numbered or use start times, and each class's teacher row might be labeled "TEACHER", "FACULTY", "STAFF", or sit next to the subject row instead of below it.

Reconstruct it into strict JSON, nothing else: no markdown, no commentary, no code fences.

Output exactly this shape:
{
  "classes": {
    "<class label>": {
      "<DAY>": {
        "<period number as a string>": {"subject_code": "<string>", "teacher_code": "<string>"}
      }
    }
  }
}

Rules:
- Day keys must be exactly one of: MON, TUE, WED, THU, FRI, SAT, SUN.
- Class labels must be normalized to <grade digits><optional section letter>, e.g. "Class X - A" -> "10A", "VIII B" -> "8B", "6" -> "6" (omit the letter if there isn't a section). Skip any row you can't confidently map to a real class this way.
- subject_code/teacher_code are exactly whatever short code or text the sheet actually uses in that cell — never invent, expand, or guess a real subject/teacher name.
- Only include a period if the sheet actually has a subject filled in for it. Skip free periods, breaks, lunch, and assembly rows entirely.
- If you cannot make sense of this sheet as a timetable grid at all, return {"classes": {}} rather than guessing."""


class TimetableExtractionNotConfigured(RuntimeError):
    pass


class TimetableExtractionError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(OPENROUTER_API_KEY)


def _dump_grid(rows: list[list]) -> str:
    lines = []
    for r, row in enumerate(rows):
        cells = [f"{c}={v}" for c, v in enumerate(row) if v not in (None, "")]
        if cells:
            lines.append(f"row {r}: " + ", ".join(cells))
    return "\n".join(lines)[:_MAX_GRID_TEXT]


def _sanitize_classes(raw) -> dict:
    """Defensively filters the LLM's output down to exactly the shape the
    rest of the pipeline (extract_codes, the review UI, /import/confirm)
    expects — a malformed day/period/cell is silently dropped rather than
    raising, same "skip what doesn't fit" philosophy as the deterministic
    parser, since the alternative is a 500 from a slightly-off LLM response
    instead of just a smaller (but still useful) result."""
    classes: dict[str, dict] = {}
    if not isinstance(raw, dict):
        return classes
    for label, grid in raw.items():
        if not isinstance(label, str) or not label.strip() or not isinstance(grid, dict):
            continue
        clean_grid: dict[str, dict[int, dict]] = {}
        for day, periods in grid.items():
            day = str(day).strip().upper()
            if day not in _VALID_DAYS or not isinstance(periods, dict):
                continue
            clean_periods: dict[int, dict] = {}
            for period, cell in periods.items():
                try:
                    period_num = int(period)
                except (TypeError, ValueError):
                    continue
                if not isinstance(cell, dict):
                    continue
                subject_code = str(cell.get("subject_code") or "").strip()
                if not subject_code:
                    continue
                teacher_code = str(cell.get("teacher_code") or "").strip()
                clean_periods[period_num] = {"subject_code": subject_code, "teacher_code": teacher_code}
            if clean_periods:
                clean_grid[day] = clean_periods
        if clean_grid:
            classes[label.strip()] = clean_grid
    return classes


@traceable(run_type="llm", name="timetable_extraction")
def extract_timetable(rows: list[list]) -> dict:
    """`rows` is one sheet's cell values as `[[cell.value, ...], ...]` (see
    app/parsing/timetable_parser.load_sheet_rows). Returns {"classes": {...}}
    in the same shape parse_rows produces, or raises
    TimetableExtractionError when nothing usable comes back."""
    if not is_configured():
        raise TimetableExtractionNotConfigured("AI-assisted timetable reading isn't configured on this server (missing OPENROUTER_API_KEY).")

    grid_text = _dump_grid(rows)
    if not grid_text.strip():
        raise TimetableExtractionError("This sheet looks empty.")

    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": grid_text},
    ]

    try:
        response = httpx.post(
            OPENROUTER_URL,
            json={
                "model": OPENROUTER_MODEL,
                "messages": messages,
                "max_tokens": 4000,
                "response_format": {"type": "json_object"},
                "provider": {"data_collection": "deny"},
            },
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            timeout=60,
        )
    except httpx.HTTPError as exc:
        raise TimetableExtractionError(f"Could not reach the timetable-reading service: {exc}") from exc

    if response.status_code == 429:
        raise TimetableExtractionError("The timetable-reading service is busy right now. Please try again in a few minutes.")
    if response.status_code >= 400:
        raise TimetableExtractionError(f"The timetable-reading service couldn't process this file (error {response.status_code}).")

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise TimetableExtractionError(f"Unexpected response shape from timetable-reading service: {data}") from exc

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise TimetableExtractionError(f"Timetable-reading service did not return valid JSON: {content[:500]}") from exc

    classes = _sanitize_classes(parsed.get("classes"))
    if not classes:
        raise TimetableExtractionError("Couldn't make sense of this sheet as a timetable grid.")
    return {"classes": classes}
