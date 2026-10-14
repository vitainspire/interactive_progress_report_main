from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.db.database import session
from app.db.users import get_user_by_id

_bearer = HTTPBearer(auto_error=False)


def _load_user(user_id: int | None):
    if user_id is None:
        raise HTTPException(401, "Invalid or expired token")
    with session() as conn:
        user = get_user_by_id(conn, user_id)
    if user is None:
        raise HTTPException(401, "User not found")
    return user


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)):
    if credentials is None:
        raise HTTPException(401, "Not authenticated")
    return _load_user(decode_access_token(credentials.credentials))


def get_current_user_from_header_or_query(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    token: str | None = None,
):
    """Same as get_current_user, but also accepts ?token= — needed for plain
    <a href>/<iframe src> browser navigations (opening or embedding a report),
    which can't attach an Authorization header."""
    raw = credentials.credentials if credentials else token
    if raw is None:
        raise HTTPException(401, "Not authenticated")
    return _load_user(decode_access_token(raw))
