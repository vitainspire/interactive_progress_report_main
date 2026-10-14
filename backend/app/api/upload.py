import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.core.deps import require_not_demo, require_role, tenant_id
from app.db.database import session
from app.db.repository import replace_dataset
from app.db.school_classes import get_class
from app.parsing.xlsx_parser import parse_workbook

router = APIRouter(tags=["upload"])

ALLOWED_EXTENSIONS = {".xlsx", ".xlsm"}


@router.post("/upload")
async def upload_workbook(class_id: int, file: UploadFile, current_user=Depends(require_role("admin"))):
    require_not_demo(current_user)
    with session() as conn:
        if not get_class(conn, tenant_id(current_user), class_id):
            raise HTTPException(404, "Class not found")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{suffix}'. Upload an .xlsx file.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        parsed = parse_workbook(tmp_path)
    except Exception as exc:
        raise HTTPException(422, f"Could not parse workbook: {exc}") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not parsed.students:
        raise HTTPException(422, "No student rows were found in this workbook. Check it matches the expected template.")

    with session() as conn:
        replace_dataset(conn, tenant_id(current_user), class_id, file.filename or "upload.xlsx", parsed)

    return {
        "filename": file.filename,
        "student_count": len(parsed.students),
        "phases": [p.code for p in parsed.phases],
        "sections": sorted({s.section for s in parsed.students}),
        "staff_entries": len(parsed.staff),
    }
