import json

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user
from app.db import batches as repo
from app.db.database import session
from app.integrations import science_lab
from app.reports import exam_focus, study_plan
from app.reports.subject_analysis import get_blueprint

router = APIRouter(prefix="/science-lab", tags=["science-lab"])


@router.get("/chapter/{chapter}")
def get_chapter(chapter: int, class_level: int = 10, subject: str = "Physical Science", current_user=Depends(get_current_user)):
    """One chapter's lab/game links, looked up by its NUMBER in the Smart
    Science Lab catalog's own (NCERT) numbering — only meaningful for a
    caller that already knows its chapter numbers match NCERT's. Most
    callers in this app don't (see GET /for-subject-plan below), so this
    exists mainly for direct/manual lookups."""
    result = science_lab.get_chapter_activities(chapter, class_level, subject)
    if result is None:
        raise HTTPException(404, f"No Smart Science Lab content for chapter {chapter}.")
    return result


@router.get("/for-subject-plan")
def get_for_subject_plan(subject: str, batch_id: int, current_user=Depends(get_current_user)):
    """Smart Science Lab links for whichever chapters this class is
    currently estimated to be on in `subject` — the same deterministic
    "likely current chapters" computation already used by the parent-facing
    subject prep-plan page (app/reports/parent_report.py's
    render_subject_plan_page: study_plan.get_chapters + get_blueprint +
    exam_focus.build_exam_focus), just re-run here against the batch's own
    exam_order (every student in a batch is given the same exams, so this
    doesn't need a specific student to estimate from).

    Looks each resulting chapter NAME up in the Smart Science Lab catalog by
    title (see app/integrations/science_lab.py for why — the catalog's own
    chapter numbering doesn't match this app's). Chapters with no Science
    Lab content (e.g. Biology) are silently skipped, same "hide rather than
    show nothing" rule as the rest of this app's optional sections — this
    route never 404s just because nothing matched."""
    with session() as conn:
        batch_row = repo.get_batch(conn, current_user["id"], batch_id)
        if not batch_row:
            raise HTTPException(404, "Batch not found")
        settings = repo.settings_from_row(batch_row)
        completed_exam_keys = [e["key"] for e in json.loads(batch_row["exam_order"])]

        chapters = study_plan.get_chapters(conn, current_user["id"], batch_row["class_level"], subject)
        topics = get_blueprint(conn, current_user["id"], batch_row["class_level"], subject)
        focus = exam_focus.build_exam_focus(chapters, topics, completed_exam_keys, settings.total_fa_exams, settings.total_sa_exams)

    if not focus:
        return {"chapters": []}

    matches = [science_lab.find_chapter_by_title(name) for name in focus["covered_chapters"]]
    return {"chapters": [m for m in matches if m]}
