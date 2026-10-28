"""Computes the teacher-facing "Student analytics" page's numbers — one
student's own marks/rank/attendance trend across every exam on file, with
each subject's marks also compared against that same exam's class
average. Distinct from analysis.py (a templated Telugu narrative meant
for the student/parent) and from class_stats.py (whole-class aggregates
for one selected exam): this is one student, across every exam, as plain
numbers a teacher can scan quickly — no narrative text, no LLM call.
"""
from __future__ import annotations

GRADE_POINTS = {"A1": 10, "A2": 9, "B1": 8, "B2": 7, "C1": 6, "C2": 5, "D1": 4, "D2": 3}


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def build_student_analytics(student: dict, all_students: list[dict], exam_defs: list[dict], settings) -> dict:
    """`student`/`all_students`/`exam_defs`/`settings` match
    card_render.render_card's params exactly (see sheet_parser/
    batches.load_batch_students for the student dict's shape)."""
    exam_order = [e["key"] for e in exam_defs]
    is_fa_by_key = {e["key"]: e["is_fa"] for e in exam_defs}
    exams_present = [k for k in exam_order if k in student["exams"]]
    class_strength = settings.class_strength_override or len(all_students)

    subject_names: list[str] = []
    subject_rows: dict[str, list[dict]] = {}
    for key in exams_present:
        max_marks = settings.fa_marks_per_subject if is_fa_by_key[key] else settings.sa_marks_per_subject
        # This exam's class average per subject, computed fresh per exam —
        # class_stats.compute_class_stats only covers one selected exam at
        # a time, but a trend needs every exam this student has.
        class_vals: dict[str, list[float]] = {}
        for s in all_students:
            e = s["exams"].get(key)
            if not e:
                continue
            for x in e["subjects"]:
                if _is_num(x["marks"]):
                    class_vals.setdefault(x["name"], []).append(x["marks"])

        for x in student["exams"][key]["subjects"]:
            name = x["name"]
            if name not in subject_rows:
                subject_rows[name] = []
                subject_names.append(name)
            vals = class_vals.get(name, [])
            class_avg = round(sum(vals) / len(vals), 1) if vals else None
            subject_rows[name].append({
                "exam": key,
                "marks": x["marks"] if _is_num(x["marks"]) else None,
                "grade": x["grade"],
                "max_marks": max_marks,
                "class_avg": class_avg,
            })

    subjects = []
    strengths: list[str] = []
    weak_subjects: list[str] = []
    failing_subjects: list[str] = []
    for name in subject_names:
        rows = subject_rows[name]
        graded = [r for r in rows if r["grade"] in GRADE_POINTS]
        trend = None
        if len(graded) >= 2:
            first_gp, last_gp = GRADE_POINTS[graded[0]["grade"]], GRADE_POINTS[graded[-1]["grade"]]
            trend = "up" if last_gp > first_gp else "down" if last_gp < first_gp else "flat"
        if graded:
            avg_gp = sum(GRADE_POINTS[r["grade"]] for r in graded) / len(graded)
            if any(r["grade"] == "D2" for r in graded):
                failing_subjects.append(name)
            elif avg_gp < 6:
                weak_subjects.append(name)
            elif avg_gp >= 8:
                strengths.append(name)
        subjects.append({"name": name, "per_exam": rows, "trend": trend})

    rank_trend = []
    for key in exams_present:
        e = student["exams"][key]
        if _is_num(e.get("rank")):
            rank_trend.append({
                "exam": key,
                "rank": e["rank"],
                "class_strength": class_strength,
                "total_marks": e["total_marks"] if _is_num(e["total_marks"]) else None,
                "grade": e["total_grade"],
            })

    attendance_trend = []
    attendance_total = None
    att = student.get("attendance")
    if att:
        attendance_trend = [{"month": m["month"], "attended": m["attended"], "working_days": m["working_days"]} for m in att["months"]]
        attendance_total = {"present": att["total_present"], "working": att["total_working"]}

    return {
        "exams": exams_present,
        "subjects": subjects,
        "rank_trend": rank_trend,
        "attendance_trend": attendance_trend,
        "attendance_total": attendance_total,
        "strengths": strengths,
        "weak_subjects": weak_subjects,
        "failing_subjects": failing_subjects,
    }
