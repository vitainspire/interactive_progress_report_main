"""Seeds a shared, read-only demo account on first startup, loaded with the
sample workbook bundled in the project root — so a visitor can explore the
whole app before creating their own account."""
import logging

from app.core.config import BACKEND_DIR
from app.core.security import hash_password
from app.db.database import session
from app.db.repository import replace_dataset, set_setting
from app.db.school_classes import create_class
from app.db.users import create_user, get_demo_user
from app.parsing.xlsx_parser import parse_workbook

logger = logging.getLogger(__name__)

DEMO_EMAIL = "demo@example.com"
DEMO_XLSX_PATH = BACKEND_DIR.parent / "PROGRESS 1.xlsx"


def ensure_demo_account() -> None:
    with session() as conn:
        demo_user = get_demo_user(conn)
        if demo_user is not None:
            return
        if not DEMO_XLSX_PATH.exists():
            logger.warning("Demo workbook not found at %s — skipping demo account seed.", DEMO_XLSX_PATH)
            return

        user_id = create_user(
            conn,
            email=DEMO_EMAIL,
            password_hash=hash_password("not-a-real-login"),
            display_name="Demo School",
            school_name="S.P.P.Z.P.P. High School, Gurajanapalli",
            is_demo=True,
        )
        class_id = create_class(conn, user_id, "10వ తరగతి", "10")
        parsed = parse_workbook(str(DEMO_XLSX_PATH))
        replace_dataset(conn, user_id, class_id, "PROGRESS 1.xlsx", parsed)
        set_setting(conn, user_id, "school_name", "S.P.P.Z.P.P. High School, Gurajanapalli")
        set_setting(conn, user_id, "school_udise", "28143601909")
        logger.info("Seeded demo account with %d students.", len(parsed.students))
