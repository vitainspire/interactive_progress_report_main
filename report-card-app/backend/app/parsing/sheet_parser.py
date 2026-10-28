"""Port of the original "Student Report Card Generator" tool's spreadsheet
parser (its in-browser `parse(rows)` function) to Python.

Nothing here is specific to any one school's sheet — there are no hardcoded
subject names, exam counts, or student counts anywhere below. The parser
only looks for a *shape*: three header rows (exam name -> subject name ->
"Marks"/"Grade" sub-labels), with one row per student underneath. Whatever
exam names, subjects, and students are actually in a given file is what
comes out; a different school's sheet with different subjects/exams/years
parses exactly the same way as long as it follows that same header shape.
An ATTENDANCE block (month columns with a "WORKING DAYS=N" sub-label, plus
a "TOTAL WORKING DAYS=N" column) is optional. Any other block (e.g. "STAFF
PARTICULARS") is ignored.

The whole parser works off a plain 2D grid of cell values (`parse_grid`),
not an Excel-specific API — `.xlsx` and `.csv` uploads both get converted
to that same grid and run through the identical logic, which is also why
a merged Excel header and a CSV export of the same sheet (blank cells
where a merge would have been) parse identically: the algorithm already
only checks "is this cell non-empty", not "is this cell merged".

This mirrors the original tool's logic column-for-column rather than
reusing this repo's other spreadsheet parser, because the two tools make
different assumptions the teacher's output already depends on: exam keys
here come from whatever is in parentheses in the header (e.g. "FA-1"), not
a normalized code, and "is this an FA-style exam" is decided generically
by whether that key starts with "F" — not a fixed marking scheme.
"""
from __future__ import annotations

import csv
import io
import re

import openpyxl

_NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")
_AB_RE = re.compile(r"^(ab|absent)$", re.I)
_TRAILING_NUM_RE = re.compile(r"(\d+)\s*$")
_ANY_NUM_RE = re.compile(r"\d+")


class SheetParseError(ValueError):
    pass


def _cl(v) -> str:
    """Trim + collapse whitespace, like the original's `cl()` — and, since
    openpyxl hands back whole numbers as floats (1.0) where the browser's
    SheetJS gave plain integers (1), normalize integral floats first so
    S.No/roll/marks text matches what the teacher's tool used to show."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r"\s+", " ", str(v)).strip()


def _is_number(text: str) -> bool:
    return bool(_NUM_RE.match(text))


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _mk(v):
    """A mark cell's value: pass numbers through, map "AB"/"Absent" to the
    literal string "AB", anything else numeric-looking to a float, else '-'."""
    if _is_num(v):
        return float(v)
    t = _cl(v)
    if _AB_RE.match(t):
        return "AB"
    if t != "" and _is_number(t):
        return float(t)
    return "-"


def _gr(v) -> str:
    return _cl(v).upper() or "-"


def parse_grid(rows: list[list]) -> dict:
    """Core parser: `rows` is a plain 0-indexed list of rows, each a list of
    cell values (numbers, strings, or None/missing — ragged rows are fine).
    Returns {"students": [...], "exams": [{"key": str, "is_fa": bool}, ...]}.
    No part of this function is specific to a particular sheet's content."""

    def cell(r0: int, c0: int):
        if r0 < 0 or r0 >= len(rows):
            return None
        row = rows[r0]
        if c0 < 0 or c0 >= len(row):
            return None
        return row[c0]

    max_row = len(rows)
    max_col = max((len(r) for r in rows), default=0)

    h = None
    for r in range(max_row):
        for c in range(max_col):
            if re.search(r"student\s*name", _cl(cell(r, c)), re.I):
                h = r
                break
        if h is not None:
            break
    if h is None:
        raise SheetParseError('Required column "STUDENT NAME" was not found. Check that the header rows are intact.')

    W = max_col

    def find_col(pattern: str) -> int:
        for c in range(W):
            if re.search(pattern, _cl(cell(h, c)), re.I):
                return c
        return -1

    c_name = find_col(r"student\s*name")
    c_section = find_col(r"section|class")
    c_roll = find_col(r"^s\.?\s*no|roll")
    c_father = find_col(r"father")
    c_mother_gender = find_col(r"mother|gender")
    c_phone = find_col(r"mobile|whatsapp|phone|contact|(parent|guardian)s?.*number")
    base = max(c_name, c_father, c_mother_gender, c_phone)

    block_starts = [i for i in range(base + 1, W) if _cl(cell(h, i))]

    exam_blocks: list[dict] = []
    attendance = None

    for k, s in enumerate(block_starts):
        e = block_starts[k + 1] if k + 1 < len(block_starts) else W
        label = _cl(cell(h, s))
        if re.search(r"attend", label, re.I):
            months = []
            total_col = -1
            m = _TRAILING_NUM_RE.search(label)
            total_working = float(m.group(1)) if m else 0.0
            for j in range(s, e):
                t = _cl(cell(h + 1, j))
                if re.search(r"total", t, re.I):
                    total_col = j
                    if not total_working:
                        m2 = _TRAILING_NUM_RE.search(t)
                        total_working = float(m2.group(1)) if m2 else total_working
                elif t:
                    wd_match = _ANY_NUM_RE.search(_cl(cell(h + 2, j)))
                    months.append({"label": t, "col": j, "working_days": float(wd_match.group()) if wd_match else 0.0})
            attendance = {"months": months, "total_col": total_col if total_col >= 0 else e - 1, "total_working": total_working}
            continue
        if re.search(r"staff\s+particulars", label, re.I):
            continue
        paren = re.search(r"\(([^)]+)\)", label)
        key = (paren.group(1) if paren else label).strip().upper()
        block = {"key": key, "subjects": [], "total_col": -1, "result_col": -1, "rank_col": -1}
        for j in range(s, e):
            t = _cl(cell(h + 1, j))
            if re.match(r"^total", t, re.I):
                block["total_col"] = j
            elif re.search(r"result", t, re.I):
                block["result_col"] = j
            elif re.search(r"rank", t, re.I):
                block["rank_col"] = j
            elif re.fullmatch(r"grade", t, re.I):
                # Some schools' sheets label the grade column next to each
                # subject's marks column with the literal word "Grade"
                # (instead of leaving it blank, which is what this parser
                # otherwise expects there). It's already read as col+1 of
                # the subject right before it (see "grade": _gr(cell(r, j
                # + 1)) below) — without this, it was wrongly read as its
                # own subject named "GRADE", with that subject's own
                # neighboring column misread as its marks/grade.
                continue
            elif t:
                block["subjects"].append({"name": t, "col": j})
        if block["subjects"]:
            block["is_fa"] = bool(re.match(r"^f", key, re.I))
            exam_blocks.append(block)

    if not exam_blocks:
        raise SheetParseError("No exam columns found. Exam names (e.g. FA-1, SA-1) must be in the first header row above the subject names.")

    students: list[dict] = []
    for r in range(h + 3, max_row):
        name = _cl(cell(r, c_name)) if c_name >= 0 else ""
        if not name:
            continue
        if c_roll >= 0:
            roll_text = _cl(cell(r, c_roll))
            if roll_text == "" or not _is_number(roll_text):
                continue
        row = {
            "name": name,
            "section": _cl(cell(r, c_section)) if c_section >= 0 else "",
            "roll": _cl(cell(r, c_roll)) if c_roll >= 0 else "",
            "father": _cl(cell(r, c_father)) if c_father >= 0 else "",
            "phone": _cl(cell(r, c_phone)) if c_phone >= 0 else "",
            "exams": {},
        }
        for b in exam_blocks:
            subs = []
            for subj in b["subjects"]:
                j = subj["col"]
                subs.append({"name": subj["name"], "marks": _mk(cell(r, j)), "grade": _gr(cell(r, j + 1))})
            if not any(x["marks"] != "-" for x in subs):
                continue
            total_marks = _mk(cell(r, b["total_col"])) if b["total_col"] >= 0 else "-"
            if not _is_num(total_marks):
                numeric = [x["marks"] for x in subs if _is_num(x["marks"])]
                if numeric:
                    total_marks = sum(numeric)
                elif all(x["marks"] == "AB" for x in subs):
                    total_marks = "AB"
                else:
                    total_marks = "-"
            total_grade = _gr(cell(r, b["total_col"] + 1)) if b["total_col"] >= 0 else "-"
            result = _cl(cell(r, b["result_col"])).upper() if b["result_col"] >= 0 else ""
            rank = _mk(cell(r, b["rank_col"])) if b["rank_col"] >= 0 else "-"
            row["exams"][b["key"]] = {
                "subjects": subs,
                "total_marks": total_marks,
                "total_grade": total_grade,
                "result": result,
                "rank": rank,
            }
        if attendance:
            months_out = []
            for m in attendance["months"]:
                at = _mk(cell(r, m["col"]))
                if _is_num(at):
                    months_out.append({"month": m["label"], "working_days": m["working_days"], "attended": at})
            if months_out:
                ta = _mk(cell(r, attendance["total_col"]))
                total_col_is_month = any(m["col"] == attendance["total_col"] for m in attendance["months"])
                if not _is_num(ta) or total_col_is_month:
                    ta = sum(m["attended"] for m in months_out)
                tw = attendance["total_working"] or sum(m["working_days"] for m in months_out)
                row["attendance"] = {"months": months_out, "total_present": ta, "total_working": tw}
        students.append(row)

    if not students:
        raise SheetParseError("No student rows found below the header.")

    for b in exam_blocks:
        key = b["key"]
        for s in students:
            entry = s["exams"].get(key)
            if entry and not _is_num(entry["rank"]) and _is_num(entry["total_marks"]):
                entry["rank"] = 1 + sum(
                    1
                    for o in students
                    if key in o["exams"] and _is_num(o["exams"][key]["total_marks"]) and o["exams"][key]["total_marks"] > entry["total_marks"]
                )

    used_exams = [{"key": b["key"], "is_fa": b["is_fa"]} for b in exam_blocks if any(b["key"] in s["exams"] for s in students)]

    if not used_exams:
        # Columns existed where exam blocks were expected, but not one
        # student actually had usable marks in them — a sign this sheet
        # doesn't really follow the 3-header-row template (e.g. only one
        # header row, so what we read as "subject"/"marks" labels were
        # really the first two students' data) rather than a batch with
        # every student legitimately blank.
        raise SheetParseError(
            "This doesn't look like the expected report card layout — no exam marks were found under any column. "
            "Check that there are exactly three header rows (exam name, subject, then Marks/Grade) before the student rows."
        )

    return {"students": students, "exams": used_exams}


def _grid_from_worksheet(ws) -> list[list]:
    return [list(row) for row in ws.iter_rows(values_only=True)]


def parse_workbook_file(source) -> dict:
    """Opens an .xlsx workbook (a path or a file-like object) and tries
    each sheet in turn until one parses, same as the original tool falling
    through sheets until it finds the one with the expected layout."""
    wb = openpyxl.load_workbook(source, data_only=True)
    last_error: SheetParseError | None = None
    for ws in wb.worksheets:
        try:
            return parse_grid(_grid_from_worksheet(ws))
        except SheetParseError as exc:
            last_error = exc
    raise last_error or SheetParseError("No usable sheet found.")


def _decode_csv_bytes(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_csv_file(raw: bytes) -> dict:
    """Parses a CSV export of the same template. A CSV has no merged
    cells, but an export of a sheet with merged header cells already
    leaves the non-anchor cells blank — exactly what `parse_grid` already
    expects, so no separate logic is needed here beyond turning the bytes
    into a grid of strings."""
    text = _decode_csv_bytes(raw)
    sniffed_dialect = None
    try:
        sniffed_dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        pass
    reader = csv.reader(io.StringIO(text), dialect=sniffed_dialect) if sniffed_dialect else csv.reader(io.StringIO(text))
    rows = [row for row in reader]
    return parse_grid(rows)


def parse_uploaded_file(filename: str, raw: bytes) -> dict:
    """Dispatches by extension — the only thing that differs between an
    .xlsx and a .csv upload is how the raw bytes become a 2D grid; the
    actual parsing (`parse_grid`) is identical either way."""
    lower = (filename or "").lower()
    if lower.endswith(".csv"):
        return parse_csv_file(raw)
    if lower.endswith(".xlsx"):
        return parse_workbook_file(io.BytesIO(raw))
    raise SheetParseError("Only .xlsx and .csv files are supported")
