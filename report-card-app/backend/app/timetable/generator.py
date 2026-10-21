import random
from dataclasses import dataclass


@dataclass
class SubjectRequirement:
    subject_id: int
    subject_name: str
    teacher_id: int | None
    teacher_name: str | None
    periods_per_week: int


@dataclass
class ClassSpec:
    class_id: int
    class_name: str
    subjects: list[SubjectRequirement]


@dataclass
class TimetableEntry:
    class_id: int
    day: str
    period: int
    subject_id: int
    teacher_id: int | None


@dataclass
class GenerationIssue:
    class_name: str
    subject_name: str
    reason: str


def _try_generate(
    classes: list[ClassSpec], working_days: list[str], periods_per_day: int, seed: int
) -> tuple[list[TimetableEntry], list[GenerationIssue]]:
    rng = random.Random(seed)
    all_slots = [(d, p) for d in working_days for p in range(1, periods_per_day + 1)]

    teacher_busy: set[tuple[int, str, int]] = set()
    class_slot_used: dict[int, set[tuple[str, int]]] = {c.class_id: set() for c in classes}
    subject_day_count: dict[tuple[int, int, str], int] = {}
    entries: list[TimetableEntry] = []
    issues: list[GenerationIssue] = []

    tasks: list[tuple[ClassSpec, SubjectRequirement]] = [(c, req) for c in classes for req in c.subjects]
    # Hardest-to-place first (most periods/week needed) gets first pick of slots,
    # so a lightly-scheduled subject is the one left scrambling for leftovers.
    tasks.sort(key=lambda t: -t[1].periods_per_week)

    for c, req in tasks:
        if req.periods_per_week <= 0:
            continue
        if req.teacher_id is None:
            issues.append(GenerationIssue(c.class_name, req.subject_name, "No teacher assigned — set one under Assignments"))
            continue

        shuffled_slots = all_slots[:]
        rng.shuffle(shuffled_slots)
        placed = 0
        # Widening passes: first try to put this subject's periods on days that
        # don't have it yet at all (spreads it across the week), then allow up
        # to 1/day, then 2/day, then no limit — so a subject only repeats on a
        # day if the week genuinely doesn't have enough other days to use.
        for max_per_day in sorted({0, 1, 2, periods_per_day}):
            if placed >= req.periods_per_week:
                break
            for day, period in shuffled_slots:
                if placed >= req.periods_per_week:
                    break
                if (day, period) in class_slot_used[c.class_id]:
                    continue
                if (req.teacher_id, day, period) in teacher_busy:
                    continue
                key = (c.class_id, req.subject_id, day)
                if subject_day_count.get(key, 0) > max_per_day:
                    continue
                class_slot_used[c.class_id].add((day, period))
                teacher_busy.add((req.teacher_id, day, period))
                subject_day_count[key] = subject_day_count.get(key, 0) + 1
                entries.append(TimetableEntry(c.class_id, day, period, req.subject_id, req.teacher_id))
                placed += 1

        if placed < req.periods_per_week:
            issues.append(
                GenerationIssue(
                    c.class_name,
                    req.subject_name,
                    f"Only placed {placed} of {req.periods_per_week} periods/week — {req.teacher_name or 'the assigned teacher'} "
                    "is likely double-booked elsewhere, or the week doesn't have enough free slots left for this class",
                )
            )

    return entries, issues


def generate_timetable(
    classes: list[ClassSpec], working_days: list[str], periods_per_day: int, max_attempts: int = 25
) -> tuple[list[TimetableEntry], list[GenerationIssue]]:
    """Greedy, randomized-retry scheduler: tries up to `max_attempts` random
    slot orderings and keeps whichever placed every required period; if none
    fully succeed, returns the attempt with the fewest unplaced periods so
    the admin sees exactly what's left to fix rather than nothing at all."""
    if not working_days or periods_per_day < 1:
        return [], [GenerationIssue("", "", "Set up the weekly schedule (working days and periods/day) first")]

    best_entries: list[TimetableEntry] = []
    best_issues: list[GenerationIssue] = []
    for attempt in range(max_attempts):
        entries, issues = _try_generate(classes, working_days, periods_per_day, seed=attempt)
        if not issues:
            return entries, []
        if not best_entries or len(issues) < len(best_issues):
            best_entries, best_issues = entries, issues
    return best_entries, best_issues
