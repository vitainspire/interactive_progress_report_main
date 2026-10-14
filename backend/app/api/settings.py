from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.deps import require_not_demo, require_role, tenant_id
from app.db.database import session
from app.db import repository as repo

router = APIRouter(tags=["settings"])

SETTING_KEYS = [
    "school_name",
    "school_udise",
    "headmaster_name",
    "headmaster_phone",
]


@router.get("/settings")
def get_settings(current_user=Depends(require_role("admin"))):
    user_id = tenant_id(current_user)
    with session() as conn:
        return {key: repo.get_setting(conn, user_id, key, "") for key in SETTING_KEYS}


class SettingsUpdate(BaseModel):
    school_name: str | None = None
    school_udise: str | None = None
    headmaster_name: str | None = None
    headmaster_phone: str | None = None


@router.put("/settings")
def update_settings(body: SettingsUpdate, current_user=Depends(require_role("admin"))):
    require_not_demo(current_user)
    user_id = tenant_id(current_user)
    with session() as conn:
        for key, value in body.model_dump(exclude_none=True).items():
            repo.set_setting(conn, user_id, key, value)
        return {key: repo.get_setting(conn, user_id, key, "") for key in SETTING_KEYS}
