"""Rule-based (no-LLM) trend analysis used to drive the Telugu report text."""
from __future__ import annotations

from dataclasses import dataclass, field

STABLE_BAND = 5.0  # percentage points of swing that still counts as "steady"
SIGNIFICANT_IMPROVEMENT = 8.0
SIGNIFICANT_DECLINE = 8.0


@dataclass
class SubjectPoint:
    phase_code: str
    marks: float
    max_marks: float
    pct: float
    grade: str | None


@dataclass
class SubjectSeries:
    subject: str
    points: list[SubjectPoint]
    direction: str  # improving | declining | stable | fluctuating | single | no_data


def classify_direction(pcts: list[float]) -> str:
    if len(pcts) == 0:
        return "no_data"
    if len(pcts) == 1:
        return "single"
    diffs = [pcts[i + 1] - pcts[i] for i in range(len(pcts) - 1)]
    net = pcts[-1] - pcts[0]
    if all(abs(d) <= STABLE_BAND for d in diffs):
        return "stable"
    rising = all(d >= -0.01 for d in diffs)
    falling = all(d <= 0.01 for d in diffs)
    if rising and net >= SIGNIFICANT_IMPROVEMENT:
        return "improving"
    if falling and net <= -SIGNIFICANT_DECLINE:
        return "declining"
    if net >= SIGNIFICANT_IMPROVEMENT:
        return "improving"
    if net <= -SIGNIFICANT_DECLINE:
        return "declining"
    return "fluctuating"


def build_subject_series(exam_result_rows, phase_order: list[str]) -> list[SubjectSeries]:
    by_subject: dict[str, dict[str, object]] = {}
    for r in exam_result_rows:
        by_subject.setdefault(r["subject"], {})[r["phase_code"]] = r

    series: list[SubjectSeries] = []
    for subject, by_phase in by_subject.items():
        points: list[SubjectPoint] = []
        for code in phase_order:
            r = by_phase.get(code)
            if r and r["marks"] is not None and r["max_marks"]:
                pct = round(r["marks"] / r["max_marks"] * 100, 1)
                points.append(SubjectPoint(code, r["marks"], r["max_marks"], pct, r["grade"]))
        direction = classify_direction([p.pct for p in points])
        series.append(SubjectSeries(subject=subject, points=points, direction=direction))
    # keep a stable, readable order: Telugu/Hindi/English/Maths/Science/Bio/Social if present, else alpha
    preferred = ["TELUGU", "HINDI", "ENGLISH", "MATHS", "PHYSICAL SCIENCE", "BIOLOGY", "SOCIAL"]
    series.sort(key=lambda s: (preferred.index(s.subject) if s.subject in preferred else 99, s.subject))
    return series


@dataclass
class AttendanceInsight:
    total_present: float | None
    total_working: float | None
    pct: float | None
    band: str  # excellent | good | concern | no_data


def build_attendance_insight(total_present, total_working) -> AttendanceInsight:
    if not total_present or not total_working:
        return AttendanceInsight(total_present, total_working, None, "no_data")
    pct = round(total_present / total_working * 100, 1)
    if pct >= 95:
        band = "excellent"
    elif pct >= 85:
        band = "good"
    else:
        band = "concern"
    return AttendanceInsight(total_present, total_working, pct, band)


@dataclass
class RankInsight:
    points: list[tuple[str, int]]  # phase_code, rank
    direction: str  # improving | declining | stable | single | no_data


def build_rank_insight(exam_summaries, phase_order: list[str]) -> RankInsight:
    by_phase = {r["phase_code"]: r["rank"] for r in exam_summaries if r["rank"] is not None}
    points = [(code, by_phase[code]) for code in phase_order if code in by_phase]
    if len(points) <= 1:
        return RankInsight(points, "single" if points else "no_data")
    diffs = [points[i + 1][1] - points[i][1] for i in range(len(points) - 1)]  # lower rank number = better
    if all(d <= 0 for d in diffs) and any(d < 0 for d in diffs):
        direction = "improving"
    elif all(d >= 0 for d in diffs) and any(d > 0 for d in diffs):
        direction = "declining"
    else:
        direction = "stable"
    return RankInsight(points, direction)
