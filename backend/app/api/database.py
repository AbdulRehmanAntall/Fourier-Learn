"""Running database work from the async routes."""

from collections.abc import Callable
from contextvars import ContextVar

from fastapi import HTTPException
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.db.session import get_sessionmaker

UNAVAILABLE = (
    "The database is not available. Start Postgres (npm run dev starts it with Docker) and run "
    "npm run db:migrate."
)


_SOURCE: ContextVar[dict | None] = ContextVar("response_source", default=None)


def track_source() -> dict:
    """Start noting, for the current request, whether the database served it. The middleware
    calls this; the flag is a shared dict because the route runs in a copy of the context."""
    source: dict = {"database": False}
    _SOURCE.set(source)
    return source


def served_by_database() -> None:
    """Note that the database's answer is the one this request returns."""
    source = _SOURCE.get()
    if source is not None:
        source["database"] = True


async def in_database[T](
    work: Callable[[Session], T], *, commit: bool = False, answers: bool = True
) -> T:
    """Run `work` with a session in a worker thread, so the event loop never waits on the
    database, and commit if asked. A database that cannot be reached is a 503.

    `answers=False` is for a lookup whose result may go unused, the route falling back to the
    stub; the route then calls `served_by_database` itself if it uses the result."""
    if answers:
        served_by_database()

    def run() -> T:
        with get_sessionmaker()() as db:
            try:
                result = work(db)
                if commit:
                    db.commit()
                return result
            except OperationalError as error:
                raise HTTPException(status_code=503, detail=UNAVAILABLE) from error

    return await run_in_threadpool(run)
