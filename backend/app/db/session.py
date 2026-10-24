"""SQLAlchemy engine and session factory.

The engine is created lazily, so the app starts even when Postgres is not running.
"""

import time
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        # Fail fast when the database is down instead of hanging requests.
        connect_args={"connect_timeout": 2},
    )


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a database session."""
    with get_sessionmaker()() as session:
        yield session


def database_is_reachable() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


_AVAILABILITY_TTL_S = 30.0
_availability: tuple[float, bool] | None = None


def database_available() -> bool:
    """Whether the database answers, remembered for 30 s.

    Code that can do without the database (the Phase 2 stub falls back to its own data) asks
    this, so that without Postgres each request does not wait for a connection to time out.
    """
    global _availability
    now = time.monotonic()
    if _availability is None or now - _availability[0] > _AVAILABILITY_TTL_S:
        _availability = (now, database_is_reachable())
    return _availability[1]


def forget_database_availability() -> None:
    global _availability
    _availability = None
