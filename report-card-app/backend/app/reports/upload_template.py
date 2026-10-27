"""Builds a downloadable .xlsx template matching the exact shape
app/parsing/sheet_parser.py expects: three header rows (exam name -> subject
name -> "Marks"/"Grade" sub-labels) above the student rows, with a couple of
sample students already filled in so a school can see exactly how to adapt
it rather than start from a blank grid. Generated on the fly rather than
stored as a static file — it's a handful of cells, not worth maintaining a
binary asset in the repo for.
"""
from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

_HEADER_FILL = PatternFill(start_color="1D2F7A", end_color="1D2F7A", fill_type="solid")
_HEADER_FONT = Font(color="FFFFFF", bold=True)
_SUBHEADER_FILL = PatternFill(start_color="E8ECFB", end_color="E8ECFB", fill_type="solid")
_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)

_BASE_COLUMNS = ["S.No", "Student Name", "Section", "Father Name", "Mother Name", "Phone"]
_SUBJECTS = ["Telugu", "English", "Maths"]
_EXAMS = ["FORMATIVE ASSESSMENT - 1 (FA-1)", "SUMMATIVE ASSESSMENT - 1 (SA-1)"]
_MONTHS = ["June", "July"]

# One realistic-looking sample row per student, matching column order:
# per-subject (marks, grade) for FA-1, then SA-1, then attendance months.
_SAMPLE_STUDENTS = [
    {
        "base": ["1", "Sample Student One", "A", "Father Name", "Mother Name", "9000000001"],
        "fa": [(45, "A1"), (42, "A2"), (48, "A1")],
        "sa": [(78, "A1"), (72, "A2"), (85, "A1")],
        "attendance": [24, 25],
    },
    {
        "base": ["2", "Sample Student Two", "A", "Father Name", "Mother Name", "9000000002"],
        "fa": [(38, "B1"), (35, "B2"), (40, "B1")],
        "sa": [(65, "B1"), (60, "B2"), (70, "B1")],
        "attendance": [22, 23],
    },
]


def _write_exam_block(ws, start_col: int, exam_label: str) -> int:
    """Writes one exam block (subjects + Total + Result + Rank) starting at
    `start_col` across the three header rows. Returns the column just past
    the block, for the next block to start at."""
    col = start_col
    ws.cell(row=1, column=col, value=exam_label)
    for subject in _SUBJECTS:
        ws.cell(row=2, column=col, value=subject)
        ws.cell(row=3, column=col, value="Marks")
        ws.cell(row=3, column=col + 1, value="Grade")
        col += 2
    ws.cell(row=2, column=col, value="Total")
    ws.cell(row=3, column=col, value="Marks")
    ws.cell(row=3, column=col + 1, value="Grade")
    col += 2
    ws.cell(row=2, column=col, value="Result")
    col += 1
    ws.cell(row=2, column=col, value="Rank")
    col += 1
    return col


def _write_attendance_block(ws, start_col: int) -> int:
    total_working = len(_MONTHS) * 26  # a plausible per-month working-day count for the example
    ws.cell(row=1, column=start_col, value=f"ATTENDANCE (Total Working Days={total_working})")
    col = start_col
    for month in _MONTHS:
        ws.cell(row=2, column=col, value=month)
        ws.cell(row=3, column=col, value="Working Days=26")
        col += 1
    ws.cell(row=2, column=col, value="Total")
    return col + 1


def build_upload_template() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Class Marks"

    for i, label in enumerate(_BASE_COLUMNS, start=1):
        ws.cell(row=1, column=i, value=label)

    col = len(_BASE_COLUMNS) + 1
    exam_start_cols = []
    for exam_label in _EXAMS:
        exam_start_cols.append(col)
        col = _write_exam_block(ws, col, exam_label)
    attendance_start_col = col
    col = _write_attendance_block(ws, col)
    last_col = col - 1

    # Style the three header rows and merge each block's label across its
    # own columns, purely cosmetic — the parser only cares which cells are
    # non-empty, not merges (a CSV export of this sheet parses identically).
    for row in (1, 2, 3):
        for c in range(1, last_col + 1):
            cell = ws.cell(row=row, column=c)
            if row == 1:
                cell.fill = _HEADER_FILL
                cell.font = _HEADER_FONT
            else:
                cell.fill = _SUBHEADER_FILL
                cell.font = Font(bold=(row == 2))
            cell.alignment = _CENTER
    for i in range(1, len(_BASE_COLUMNS) + 1):
        ws.merge_cells(start_row=1, start_column=i, end_row=3, end_column=i)
    block_bounds = exam_start_cols + [attendance_start_col, last_col + 1]
    for start, end in zip(block_bounds, block_bounds[1:]):
        ws.merge_cells(start_row=1, start_column=start, end_row=1, end_column=end - 1)

    row_idx = 4
    for student in _SAMPLE_STUDENTS:
        for i, value in enumerate(student["base"], start=1):
            ws.cell(row=row_idx, column=i, value=value)
        c = len(_BASE_COLUMNS) + 1
        for marks, grade in student["fa"]:
            ws.cell(row=row_idx, column=c, value=marks)
            ws.cell(row=row_idx, column=c + 1, value=grade)
            c += 2
        fa_total = sum(m for m, _ in student["fa"])
        ws.cell(row=row_idx, column=c, value=fa_total)
        ws.cell(row=row_idx, column=c + 1, value="A1" if fa_total >= len(student["fa"]) * 45 else "B1")
        c += 2
        ws.cell(row=row_idx, column=c, value="PASS")
        c += 1
        # Rank column left blank on purpose — the app computes it
        # automatically from total marks if you don't fill it in.
        c += 1
        for marks, grade in student["sa"]:
            ws.cell(row=row_idx, column=c, value=marks)
            ws.cell(row=row_idx, column=c + 1, value=grade)
            c += 2
        sa_total = sum(m for m, _ in student["sa"])
        ws.cell(row=row_idx, column=c, value=sa_total)
        ws.cell(row=row_idx, column=c + 1, value="A1" if sa_total >= len(student["sa"]) * 70 else "B1")
        c += 2
        ws.cell(row=row_idx, column=c, value="PASS")
        c += 2  # skip Rank, same as above
        for attended in student["attendance"]:
            ws.cell(row=row_idx, column=c, value=attended)
            c += 1
        ws.cell(row=row_idx, column=c, value=sum(student["attendance"]))
        row_idx += 1

    ws.freeze_panes = ws.cell(row=4, column=len(_BASE_COLUMNS) + 1)
    ws.column_dimensions[get_column_letter(2)].width = 22
    for i in (3, 4, 5, 6):
        ws.column_dimensions[get_column_letter(i)].width = 14
    for c in range(len(_BASE_COLUMNS) + 1, last_col + 1):
        ws.column_dimensions[get_column_letter(c)].width = 9

    notes = wb.create_sheet("Read me")
    notes["A1"] = "How to use this template"
    notes["A1"].font = Font(bold=True, size=14)
    for i, line in enumerate(
        [
            "Keep exactly 3 header rows above your students: exam name, then subject name, then \"Marks\"/\"Grade\".",
            "Replace the 2 sample students on the 'Class Marks' sheet with your real class — keep S.No numeric.",
            "Add or remove exam blocks (e.g. SA-2) or subjects by copying an existing block's 3-row pattern.",
            "The Rank column can be left blank — it's calculated automatically from Total marks.",
            "Mark an absent student with \"AB\" instead of a number.",
            "The Attendance block is optional — delete it if you don't track attendance in this sheet.",
        ],
        start=2,
    ):
        notes[f"A{i}"] = f"{i - 1}. {line}"
    notes.column_dimensions["A"].width = 100

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
