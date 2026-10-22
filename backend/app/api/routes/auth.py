"""Register, log in, log out, and who is logged in (§4.2.1, UC 4.1)."""

from fastapi import APIRouter, Request, Response

from app.api.deps import (
    SESSION_COOKIE,
    CurrentUser,
    Store,
    clear_session_cookie,
    set_session_cookie,
)
from app.api.schemas.auth import LoginRequest, RegisterRequest, User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=User, status_code=201)
async def register(body: RegisterRequest, response: Response, store: Store) -> User:
    user = store.register(body.name, body.email, body.password)
    set_session_cookie(response, store.create_session(user))
    return store.user_out(user)


@router.post("/login", response_model=User)
async def login(body: LoginRequest, response: Response, store: Store) -> User:
    user = store.login(body.email, body.password)
    set_session_cookie(response, store.create_session(user))
    return store.user_out(user)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, store: Store) -> None:
    store.end_session(request.cookies.get(SESSION_COOKIE))
    clear_session_cookie(response)


@router.get("/me", response_model=User)
async def me(user: CurrentUser, store: Store) -> User:
    return store.user_out(user)
