import os

from fastapi.testclient import TestClient

from app import __version__
from app.main import app


def test_health_works_without_database():
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert set(body["checks"]) == {"database", "ffmpeg", "latex", "manim"}
    assert all(isinstance(value, bool) for value in body["checks"].values())
    # conftest.py points DATABASE_URL at the test database if there is one, and otherwise at a
    # port where nothing listens; health reports which, and works either way.
    assert body["checks"]["database"] is ("TEST_DATABASE_URL" in os.environ)
