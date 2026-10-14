"""Parser for the school's AutoCrat-style progress-tracking workbook.

Layout (verified against PROGRESS 1.xlsx):
  Row 1: top-level section headers, merged horizontally across each block
         (student-info columns are merged vertically rows 1-3 instead).
  Row 2: subject / month names within each block (merged vertically with
         row 3 for single-column fields like RESULT, RANK, TOTAL WORKING DAYS).
  Row 3: "MARKS "/"GRADE" sub-labels for subject pairs, or per-month
         "WORKING DAYS=N" sub-labels in the attendance block.
  Row 4+: one row per student, until S.No stops being numeric / name is blank.

The STAFF PARTICULARS block is not row-aligned data — it's a vertical
legend (per-section subject-teacher list + one headmaster name) living in
the same two right-hand columns, so it's scanned separately.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import openpyxl
from openpyxl.utils import range_boundaries
from openpyxl.worksheet.worksheet import Worksheet

from app.core.config import (
    FA_SUBJECT_MAX,
    REDUCED_MAX_SUBJECTS,
    SA_SUBJECT_MAX_DEFAULT,
    SA_SUBJECT_MAX_REDUCED,
)

HEADER_ROWS = 3
FIRST_DATA_ROW = HEADER_ROWS + 1

FA_RE = re.compile(r"FORMATIVE\s+ASSESSMENT.*?(\d+)", re.I)
SA_RE = re.compile(r"SUMMATIVE\s+ASSESSMENT.*?(\d+)", re.I)
PREFINAL_RE = re.compile(r"PRE[\s\-]?FINAL", re.I)
ATTENDANCE_RE = re.compile(r"ATTENDANCE", re.I)
STAFF_RE = re.compile(r"STAFF\s+PARTICULARS", re.I)
SECTION_LEGEND_RE = re.compile(r"^SECTION[\s\-]*([A-Za-z0-9]+)", re.I)
HEADMASTER_RE = re.compile(r"HEADMASTER\s*[-:]?\s*(.+)", re.I)
WORKING_DAYS_RE = re.compile(r"WORKING\s+DAYS\s*=\s*(\d+)", re.I)


@dataclass
class Phase:
    code: str
    label: str
    order_index: int
    start_col: int
    end_col: int


@dataclass
class SubjectResult:
    subject: str
    marks: float | None
    grade: str | None


@dataclass
class ExamBlockResult:
    phase_code: str
    subjects: list[SubjectResult]
    total_marks: float | None
    total_grade: str | None
    result: str | None
    rank: int | None


@dataclass
class MonthAttendance:
    month: str
    days_present: float | None
    working_days: float | None


@dataclass
class StudentRecord:
    s_no: int | None
    section: str
    name: str
    gender: str | None
    father_name: str | None
    mother_name: str | None
    exams: dict[str, ExamBlockResult] = field(default_factory=dict)
    attendance: list[MonthAttendance] = field(default_factory=list)
    total_present: float | None = None
    total_working_days: float | None = None


@dataclass
class StaffEntry:
    section: str
    subject: str
    teacher_name: str


@dataclass
class ParseResult:
    phases: list[Phase]
    students: list[StudentRecord]
    staff: list[StaffEntry]
    headmaster_name: str | None


def _merge_map_for_row(ws: Worksheet, row: int, *, exclusive_of_row: int | None = None) -> dict[int, int]:
    """Map start_col -> end_col for merges that cover `row` (and not `exclusive_of_row`)."""
    out: dict[int, int] = {}
    for rng in ws.merged_cells.ranges:
        min_col, min_row, max_col, max_row = range_boundaries(str(rng))
        if min_row <= row <= max_row:
            if exclusive_of_row is not None and min_row <= exclusive_of_row <= max_row:
                continue
            out[min_col] = max_col
    return out


def _normalize_subject(name: str) -> str:
    name = name.strip().upper()
    name = re.sub(r"\s+STUDIES$", "", name)  # "SOCIAL STUDIES" -> "SOCIAL"
    return name


def _subject_max_marks(phase_code: str, subject: str) -> float:
    if phase_code.startswith("FA"):
        return FA_SUBJECT_MAX
    if subject in REDUCED_MAX_SUBJECTS:
        return SA_SUBJECT_MAX_REDUCED
    return SA_SUBJECT_MAX_DEFAULT


def _detect_phases(ws: Worksheet) -> list[Phase]:
    merges = _merge_map_for_row(ws, 1)
    phases: list[Phase] = []
    order = 0
    for col in sorted(merges):
        label = ws.cell(row=1, column=col).value
        if not label or not isinstance(label, str):
            continue
        label = label.strip()
        end_col = merges[col]
        m = FA_RE.search(label)
        if m:
            phases.append(Phase(f"FA{m.group(1)}", label, order, col, end_col))
            order += 1
            continue
        m = SA_RE.search(label)
        if m:
            phases.append(Phase(f"SA{m.group(1)}", label, order, col, end_col))
            order += 1
            continue
        if PREFINAL_RE.search(label):
            phases.append(Phase("PREFINAL", label, order, col, end_col))
            order += 1
    return phases


def _find_block(ws: Worksheet, pattern: re.Pattern) -> tuple[int, int] | None:
    merges = _merge_map_for_row(ws, 1)
    for col, end_col in merges.items():
        label = ws.cell(row=1, column=col).value
        if isinstance(label, str) and pattern.search(label):
            return col, end_col
    return None


def _row2_fields(ws: Worksheet, start_col: int, end_col: int) -> list[tuple[str, int, int]]:
    """Return (label, col_start, col_end) triples for a block, reading row-2 merges."""
    merges = _merge_map_for_row(ws, 2, exclusive_of_row=1)
    fields: list[tuple[str, int, int]] = []
    col = start_col
    while col <= end_col:
        label = ws.cell(row=2, column=col).value
        width_end = merges.get(col, col)
        if label is not None and str(label).strip():
            fields.append((str(label).strip(), col, width_end))
        col = width_end + 1
    return fields


def _parse_exam_block(ws: Worksheet, row: int, phase: Phase) -> ExamBlockResult:
    fields = _row2_fields(ws, phase.start_col, phase.end_col)
    subjects: list[SubjectResult] = []
    total_marks = total_grade = result = None
    rank: int | None = None
    for label, c0, c1 in fields:
        label_u = label.upper()
        if label_u == "TOTAL MARKS":
            total_marks = ws.cell(row=row, column=c0).value
            total_grade = ws.cell(row=row, column=c1).value if c1 != c0 else None
        elif label_u.startswith("RESULT"):
            result = ws.cell(row=row, column=c0).value
        elif label_u.startswith("RANK"):
            raw = ws.cell(row=row, column=c0).value
            rank = int(raw) if isinstance(raw, (int, float)) else None
        else:
            marks = ws.cell(row=row, column=c0).value
            grade = ws.cell(row=row, column=c1).value if c1 != c0 else None
            subjects.append(
                SubjectResult(
                    subject=_normalize_subject(label),
                    marks=float(marks) if isinstance(marks, (int, float)) else None,
                    grade=str(grade).strip() if grade else None,
                )
            )
    return ExamBlockResult(
        phase_code=phase.code,
        subjects=subjects,
        total_marks=float(total_marks) if isinstance(total_marks, (int, float)) else None,
        total_grade=str(total_grade).strip() if total_grade else None,
        result=str(result).strip() if result else None,
        rank=rank,
    )


def _parse_attendance_block(ws: Worksheet, row: int, start_col: int, end_col: int) -> tuple[list[MonthAttendance], float | None, float | None]:
    months: list[MonthAttendance] = []
    total_present = total_working = None
    col = start_col
    while col <= end_col:
        month_label = ws.cell(row=2, column=col).value
        sub_label = ws.cell(row=3, column=col).value
        if isinstance(month_label, str) and WORKING_DAYS_RE.search(str(sub_label or "")):
            wd = WORKING_DAYS_RE.search(str(sub_label))
            present = ws.cell(row=row, column=col).value
            months.append(
                MonthAttendance(
                    month=month_label.strip(),
                    days_present=float(present) if isinstance(present, (int, float)) else None,
                    working_days=float(wd.group(1)) if wd else None,
                )
            )
        elif isinstance(month_label, str) and WORKING_DAYS_RE.search(str(month_label)):
            # "TOTAL WORKING DAYS=120" merged cell: value column holds total days present.
            total_m = WORKING_DAYS_RE.search(month_label)
            total_working = float(total_m.group(1)) if total_m else None
            present = ws.cell(row=row, column=col).value
            total_present = float(present) if isinstance(present, (int, float)) else None
        col += 1
    return months, total_present, total_working


def _parse_staff_block(ws: Worksheet, start_col: int, end_col: int) -> tuple[list[StaffEntry], str | None]:
    label_col, teacher_col = start_col, end_col
    entries: list[StaffEntry] = []
    headmaster = None
    current_section: str | None = None
    for row in range(1, ws.max_row + 1):
        a = ws.cell(row=row, column=label_col).value
        b = ws.cell(row=row, column=teacher_col).value
        if a is None and b is None:
            if current_section is not None and row > 3:
                # one blank row after a section's subject list ends the block
                pass
            continue
        a_str = str(a).strip() if a else ""
        m = HEADMASTER_RE.search(a_str)
        if m:
            headmaster = m.group(1).strip()
            continue
        m = SECTION_LEGEND_RE.match(a_str)
        if m:
            current_section = m.group(1).strip().upper()
            continue
        if a_str.upper() == "SUBJECT TEACHERS" or a_str.upper() == "STAFF PARTICULARS":
            continue
        if current_section and a_str and b:
            entries.append(StaffEntry(section=current_section, subject=_normalize_subject(a_str), teacher_name=str(b).strip()))
    return entries, headmaster


def parse_workbook(path: str) -> ParseResult:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.worksheets[0]
    for sheet in wb.worksheets:
        if sheet.cell(row=1, column=3).value and "STUDENT" in str(sheet.cell(row=1, column=3).value).upper():
            ws = sheet
            break

    phases = _detect_phases(ws)
    attendance_span = _find_block(ws, ATTENDANCE_RE)
    staff_span = _find_block(ws, STAFF_RE)

    staff_entries: list[StaffEntry] = []
    headmaster = None
    if staff_span:
        staff_entries, headmaster = _parse_staff_block(ws, *staff_span)

    students: list[StudentRecord] = []
    row = FIRST_DATA_ROW
    blank_streak = 0
    while row <= ws.max_row and blank_streak < 25:
        s_no = ws.cell(row=row, column=1).value
        name = ws.cell(row=row, column=3).value
        if isinstance(s_no, (int, float)) and name and str(name).strip():
            blank_streak = 0
            section = ws.cell(row=row, column=2).value
            rec = StudentRecord(
                s_no=int(s_no),
                section=str(section).strip().upper() if section else "",
                name=str(name).strip(),
                gender=(str(ws.cell(row=row, column=4).value).strip() if ws.cell(row=row, column=4).value else None),
                father_name=(str(ws.cell(row=row, column=5).value).strip() if ws.cell(row=row, column=5).value else None),
                mother_name=(str(ws.cell(row=row, column=6).value).strip() if ws.cell(row=row, column=6).value else None),
            )
            for phase in phases:
                rec.exams[phase.code] = _parse_exam_block(ws, row, phase)
                for s in rec.exams[phase.code].subjects:
                    if s.marks is not None:
                        pass  # max marks computed on demand via _subject_max_marks
            if attendance_span:
                months, total_present, total_working = _parse_attendance_block(ws, row, *attendance_span)
                rec.attendance = months
                rec.total_present = total_present
                rec.total_working_days = total_working
            students.append(rec)
        else:
            blank_streak += 1
        row += 1

    return ParseResult(phases=phases, students=students, staff=staff_entries, headmaster_name=headmaster)


def subject_max_marks(phase_code: str, subject: str) -> float:
    return _subject_max_marks(phase_code, subject)
