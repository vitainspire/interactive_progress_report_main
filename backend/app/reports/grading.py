"""Grade -> pass/fail mapping, taken from the grade/result legend embedded in
the source workbook (rows below the student table: A1..D1 -> PASS, D2 -> FAIL).
"""
FAIL_GRADES = {"D2", "F", "FAIL"}


def is_pass(grade: str | None) -> bool | None:
    if not grade:
        return None
    return grade.strip().upper() not in FAIL_GRADES
