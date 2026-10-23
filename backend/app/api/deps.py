"""Dependencies shared by the routes: the session, the signed-in user, admin access."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response

from app.core.config import get_settings
from app.stub import get_store
from app.stub.store import StubStore, UserRecord

SESSION_COOKIE = "fl_session"

Store = Annotated[StubStore, Depends(get_store)]


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=get_settings().session_cookie_secure,
        path="/",
        max_age=60 * 60 * 24 * 30,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def current_user(request: Request, store: Store) -> UserRecord:
    user = store.user_for_session(request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in.")
    return user


def admin_user(user: Annotated[UserRecord, Depends(current_user)]) -> UserRecord:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="You don't have access to this page.")
    return user


CurrentUser = Annotated[UserRecord, Depends(current_user)]
AdminUser = Annotated[UserRecord, Depends(admin_user)]
