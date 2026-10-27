import importlib.util
import os
import tempfile
from pathlib import Path

# Tests must not touch the real media folder or the development database. The tests marked
# `db` use the Postgres database named by TEST_DATABASE_URL, which they empty, and are skipped
# without one. Set these before the app (and its cached settings) is imported.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1:1/test"
)
os.environ["MEDIA_DIR"] = str(Path(tempfile.gettempdir()) / "fourierlearn-test-media")
# No artificial delay on stub responses in tests.
os.environ["STUB_LATENCY_MS"] = "0"

# `npm run setup` installs everything except Manim on machines without Cairo/Pango. The app
# still runs there, so skip the tests that need Manim instead of failing them.
if importlib.util.find_spec("manim") is None:
    collect_ignore = [
        "test_layout.py",
        "test_primitive_library.py",
        "test_primitives.py",
        "test_render_engine.py",
    ]


import pytest  # noqa: E402


@pytest.fixture(scope="session")
def migrated_database():
    """The test database at the newest migration, built once per run from an empty schema, so
    the migrations themselves are tested too."""
    if "TEST_DATABASE_URL" not in os.environ:
        pytest.skip("set TEST_DATABASE_URL to a Postgres database to run the database tests")
    from alembic.config import Config

    from alembic import command
    from app.db.session import database_is_reachable

    if not database_is_reachable():
        pytest.skip("TEST_DATABASE_URL is set but the database does not answer")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture
def db(migrated_database):
    """A session on an emptied test database. Everything is removed again afterwards, so the
    tests that run without the database see none of it."""
    from sqlalchemy import text

    from app.db import Base
    from app.db.session import forget_database_availability, get_sessionmaker

    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)

    def empty() -> None:
        with get_sessionmaker()() as session:
            session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
            session.commit()

    empty()
    forget_database_availability()
    with get_sessionmaker()() as session:
        yield session
    empty()
