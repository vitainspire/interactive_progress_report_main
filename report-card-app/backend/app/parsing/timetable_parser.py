"""Parses a school's already-built weekly timetable out of a single
"master sheet" style Excel layout — the real format many schools already
maintain (one sheet: a day-by-day, period-by-period grid with every class
as a row-pair, "subject code" row then "TEACHER" row below it) before
adopting this app's own Timetable Creator. A school in their first year on
this app shouldn't have to recreate a timetable they've already built —
this reads that existing file into the exact same shape POST
/timetable/generate would otherwise produce (a filled tt_timetable_entry
grid), so the daily substitute-finding features work immediately.

Only ever produces short *codes* for subjects/teachers (whatever the
sheet actually used, e.g. "PS", "KSVL") — never guesses a real subject
name or a teacher's full name/phone from those codes. A wrong guess there
is a real safety issue (a substitute alert texting the wrong person), so
that mapping is always a human decision made during review, confirmed via
POST /timetable/import/confirm — same "extract now, human confirms before
anything becomes live" shape as the syllabus/blueprint Drive import.
"""
from __future__ import annotations

import re

import openpyxl

_DAY_CODES = {
    "MONDAY": "MON",
    "TUESDAY": "TUE",
    "WEDNESDAY": "WED",
    "THURSDAY": "THU",
    "FRIDAY": "FRI",
    "SATURDAY": "SAT",
    "SUNDAY": "SUN",
}
_CLASS_LABEL_RE = re.compile(r"^(\d{1,2})\s*-?\s*([A-Za-z]*)$")


class TimetableParseError(ValueError):
    pass


def _cl(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r"\s+", " ", str(v)).strip()


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _find_day_columns(rows: list[list], max_col: int) -> tuple[int | None, dict[str, dict[int, int]]]:
    """Finds the first row naming at least 3 days (MONDAY, TUESDAY, ...),
    then reads the row right below it for each day block's actual period-
    number columns (1, 2, 3, ...) — a day's block width isn't assumed to
    be fixed, since a real sheet's columns don't line up perfectly evenly.
    Returns (that header row's index, {day_code: {period_number: col}})."""
    for r, row in enumerate(rows):
        label_cols: dict[int, str] = {}
        for c in range(max_col):
            v = _cl(row[c] if c < len(row) else None).upper()
            if v in _DAY_CODES:
                label_cols[c] = _DAY_CODES[v]
        if len(label_cols) < 3:
            continue
        period_row = rows[r + 1] if r + 1 < len(rows) else []
        starts = sorted(label_cols.keys())
        day_cols: dict[str, dict[int, int]] = {code: {} for code in label_cols.values()}
        for i, start_col in enumerate(starts):
            end_col = starts[i + 1] if i + 1 < len(starts) else max_col
            code = label_cols[start_col]
            for c in range(start_col, end_col):
                pv = period_row[c] if c < len(period_row) else None
                if _is_num(pv):
                    day_cols[code][int(pv)] = c
        return r, day_cols
    return None, {}


def parse_master_sheet(ws) -> dict:
    """`ws` is one openpyxl worksheet. Returns {"classes": {label: grid}}
    where `grid` is {day_code: {period: {"subject_code": str, "teacher_code": str}}}
    — only for classes that actually had at least one period filled in
    (an empty/not-yet-assigned class row is silently skipped, same as a
    sheet_parser student row with no usable marks)."""
    rows = [[cell.value for cell in row] for row in ws.iter_rows()]
    max_col = max((len(r) for r in rows), default=0)
    header_idx, day_cols = _find_day_columns(rows, max_col)
    if header_idx is None:
        raise TimetableParseError(
            'Could not find day headers (MONDAY, TUESDAY, ...) in this sheet. '
            "Make sure it's the master weekly timetable grid, not a per-class printout."
        )

    classes: dict[str, dict] = {}
    r = header_idx + 2  # skip the day-name row and the period-number row
    while r < len(rows) - 1:
        label = _cl(rows[r][0] if rows[r] else None)
        next_label = _cl(rows[r + 1][0] if len(rows) > r + 1 and rows[r + 1] else None)
        if not label or next_label.upper() != "TEACHER" or not _CLASS_LABEL_RE.match(label):
            r += 1
            continue
        subject_row, teacher_row = rows[r], rows[r + 1]
        grid: dict[str, dict[int, dict]] = {day: {} for day in day_cols}
        for day, periods in day_cols.items():
            for period, col in periods.items():
                subject_code = _cl(subject_row[col] if col < len(subject_row) else None)
                if not subject_code:
                    continue
                teacher_code = _cl(teacher_row[col] if col < len(teacher_row) else None)
                grid[day][period] = {"subject_code": subject_code, "teacher_code": teacher_code}
        if any(grid[day] for day in grid):
            classes[label] = grid
        r += 2

    if not classes:
        raise TimetableParseError("Found day headers, but no class rows with an actual schedule underneath them.")
    return {"classes": classes}


def parse_timetable_file(source) -> dict:
    """Opens an .xlsx workbook (a path or file-like object) and tries each
    sheet in turn until one parses as a master timetable grid — same
    fall-through-sheets approach as sheet_parser.parse_workbook_file."""
    wb = openpyxl.load_workbook(source, data_only=True)
    last_error: TimetableParseError | None = None
    for ws in wb.worksheets:
        try:
            return parse_master_sheet(ws)
        except TimetableParseError as exc:
            last_error = exc
    raise last_error or TimetableParseError("No usable sheet found.")


def class_label_to_grade_section(label: str) -> tuple[str, str]:
    m = _CLASS_LABEL_RE.match(label)
    if not m:
        raise TimetableParseError(f"'{label}' doesn't look like a class label (expected e.g. '10A', '6-B').")
    return m.group(1), m.group(2).upper()


def extract_codes(classes: dict) -> tuple[list[str], list[str]]:
    """Every distinct subject/teacher code actually used anywhere in the
    parsed grid, for the review step to ask a teacher to name."""
    subject_codes: set[str] = set()
    teacher_codes: set[str] = set()
    for grid in classes.values():
        for periods in grid.values():
            for cell in periods.values():
                subject_codes.add(cell["subject_code"])
                if cell["teacher_code"]:
                    teacher_codes.add(cell["teacher_code"])
    return sorted(subject_codes), sorted(teacher_codes)
