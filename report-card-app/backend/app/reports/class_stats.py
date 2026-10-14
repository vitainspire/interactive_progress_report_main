"""Computes class-wide aggregate statistics from a batch's full student
list — the numbers behind the teacher-facing "Class overview" dashboard
(grade distribution, subject averages, pass/fail, attendance, who needs
attention), as opposed to analysis.py/voice_script.py which describe one
student at a time. Entirely rule-based arithmetic over data already loaded
by batches.load_batch_students(), no LLM call.
"""
from __future__ import annotations

GRADE_POINTS = {"A1": 10, "A2": 9, "B1": 8, "B2": 7, "C1": 6, "C2": 5, "D1": 4, "D2": 3}
GRADE_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2"]


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def compute_class_stats(all_students: list[dict], exam_defs: list[dict], settings) -> dict:
    exam_order = [e["key"] for e in exam_defs]
    is_fa_by_key = {e["key"]: e["is_fa"] for e in exam_defs}
    present_exams = [k for k in exam_order if any(k in s["exams"] for s in all_students)]
    latest_key = present_exams[-1] if present_exams else None

    total = len(all_students)
    class_strength = settings.class_strength_override or total

    grade_counts = {g: 0 for g in GRADE_ORDER}
    pass_count = 0
    fail_count = 0
    graded_count = 0
    for s in all_students:
        e = s["exams"].get(latest_key) if latest_key else None
        if not e:
            continue
        g = e["total_grade"]
        if g not in GRADE_POINTS:
            continue
        graded_count += 1
        grade_counts[g] += 1
        if g == "D2":
            fail_count += 1
        else:
            pass_count += 1
    grade_distribution = [{"grade": g, "count": c} for g, c in grade_counts.items() if c > 0]

    subject_marks: dict[str, list[float]] = {}
    subject_order: list[str] = []
    subject_max = settings.fa_marks_per_subject if (latest_key and is_fa_by_key.get(latest_key)) else settings.sa_marks_per_subject
    if latest_key:
        for s in all_students:
            e = s["exams"].get(latest_key)
            if not e:
                continue
            for x in e["subjects"]:
                if not _is_num(x["marks"]):
                    continue
                if x["name"] not in subject_marks:
                    subject_marks[x["name"]] = []
                    subject_order.append(x["name"])
                subject_marks[x["name"]].append(x["marks"])
    subject_averages = []
    for name in subject_order:
        vals = subject_marks[name]
        avg_marks = sum(vals) / len(vals)
        subject_averages.append({
            "subject": name,
            "avg_marks": round(avg_marks, 1),
            "max_marks": subject_max,
            "avg_pct": round(avg_marks * 100 / subject_max, 1) if subject_max else 0,
        })

    ranked = []
    for s in all_students:
        e = s["exams"].get(latest_key) if latest_key else None
        if not e or not _is_num(e.get("rank")):
            continue
        ranked.append({"id": s["id"], "name": s["name"], "rank": e["rank"], "total_marks": e["total_marks"], "grade": e["total_grade"]})
    ranked.sort(key=lambda r: r["rank"])
    top_students = [r for r in ranked if r["grade"] != "D2"][:5]

    attention_students = []
    seen_ids: set[int] = set()
    for s in all_students:
        e = s["exams"].get(latest_key) if latest_key else None
        if e and e["total_grade"] == "D2":
            attention_students.append({"id": s["id"], "name": s["name"], "rank": e.get("rank") if _is_num(e.get("rank")) else None, "total_marks": e["total_marks"], "grade": e["total_grade"], "reason": "fail"})
            seen_ids.add(s["id"])
    weak_grades = {"C1", "C2", "D1"}
    low_candidates = [r for r in ranked if r["id"] not in seen_ids and r["grade"] in weak_grades]
    for r in sorted(low_candidates, key=lambda r: -r["rank"]):
        if len(attention_students) >= 5:
            break
        attention_students.append({**r, "reason": "low"})
        seen_ids.add(r["id"])
    attention_students = attention_students[:5]

    att_pcts = []
    for s in all_students:
        att = s.get("attendance")
        if att and att.get("total_working"):
            att_pcts.append(att["total_present"] * 100 / att["total_working"])
    avg_attendance_pct = round(sum(att_pcts) / len(att_pcts), 1) if att_pcts else None

    exam_trend = []
    for key in present_exams:
        totals = [s["exams"][key]["total_marks"] for s in all_students if key in s["exams"] and _is_num(s["exams"][key]["total_marks"])]
        exam_total_max = settings.fa_total if is_fa_by_key.get(key) else settings.sa_total
        avg_pct = round(sum(totals) * 100 / (len(totals) * exam_total_max), 1) if totals and exam_total_max else None
        exam_trend.append({"exam": key, "avg_pct": avg_pct})

    return {
        "latest_exam": latest_key,
        "total_students": total,
        "class_strength": class_strength,
        "graded_count": graded_count,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "grade_distribution": grade_distribution,
        "subject_averages": subject_averages,
        "top_students": top_students,
        "attention_students": attention_students,
        "avg_attendance_pct": avg_attendance_pct,
        "exam_trend": exam_trend,
    }
