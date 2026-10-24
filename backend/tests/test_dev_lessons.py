"""A hand-written lesson through the real path (Phase 3): POST /api/dev/render, the queue, a
worker, and the same lesson endpoints the stub's lessons use. Needs TEST_DATABASE_URL."""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.audio_pipeline.tts import FakeTTS
from app.content import content
from app.core.config import get_settings
from app.db.models import InteractionEvent, RenderJob
from app.db.seed import seed
from app.main import app
from app.stub import get_store
from app.stub.fixtures import load_fixture_variants
from app.stub.seed import STUB_PASSWORD
from app.stub.store import StubStore
from app.workers import render_worker
from tests.test_queue import fake_manifest

pytestmark = pytest.mark.db

LESSON = json.loads(
    (Path(__file__).resolve().parents[1] / "examples" / "gradient_of_line.lesson.json").read_text()
)


@pytest.fixture
def client(db, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "media_dir", tmp_path / "media")
    monkeypatch.setattr(get_settings(), "tts_provider", "fake")
    store = StubStore(load_fixture_variants())
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def login(client, email="student@fourierlearn.test"):
    response = client.post("/api/auth/login", json={"email": email, "password": STUB_PASSWORD})
    assert response.status_code == 200


def render_queued_jobs() -> int:
    """What `npm run worker` does, with a renderer that writes manifests instead of video."""
    from app.renderer.store import (
        MANIFEST_FILE,
        cache_key_for,
        variant_directory,
        write_atomically,
    )

    def fake_render(request, *, media_dir, tts, on_beat_ready, **_):
        key = cache_key_for(request, tts.name)
        manifest = fake_manifest(request, key)
        directory = variant_directory(media_dir, key)
        directory.mkdir(parents=True, exist_ok=True)
        write_atomically(directory / MANIFEST_FILE, manifest.model_dump_json())
        for beat in manifest.beats:
            on_beat_ready(beat)
        return type("Result", (), {"manifest": manifest})()

    done = 0
    while render_worker.run(
        render_worker.threading.Event(), once=True, render=fake_render, tts=FakeTTS()
    ):
        done += 1
    return done


def test_an_unseeded_database_is_explained(client):
    login(client)
    response = client.post("/api/dev/render", json=LESSON)
    assert response.status_code == 422
    assert "the database has no concepts yet: run npm run db:seed" in response.json()["detail"]


def test_plan_and_render_mismatches_are_listed(client, db):
    seed(db, content())
    db.commit()
    login(client)
    broken = copy.deepcopy(LESSON)
    broken["modules"][0]["plan"]["segments"][0]["primitive_id"] = "PieChart"
    broken["modules"][1]["renders"][0]["level"] = 3
    detail = client.post("/api/dev/render", json=broken).json()["detail"]
    assert "module 1, segment 0: there is no primitive named 'PieChart'" in detail
    assert any("module 1, Level 2: the beats" in problem for problem in detail)
    assert "module 2: no render request at Level 2" in detail


def test_a_dev_lesson_plays_through_the_lesson_endpoints(client, db):
    seed(db, content())
    db.commit()
    login(client)
    created = client.post("/api/dev/render", json=LESSON)
    assert created.status_code == 200
    assert "x-fourierlearn-stub" not in created.headers
    lesson_id = created.json()["lesson_id"]
    url = f"/api/lessons/{lesson_id}"

    lesson = client.get(url).json()
    assert lesson["title"] == "Gradient of a straight line"
    assert [m["render_status"] for m in lesson["modules"]] == ["queued", "queued"]
    current = client.get(f"{url}/current-module").json()
    assert current["status"] == "preparing" and current["stage"] == "rendering"
    assert len(db.scalars(select(RenderJob)).all()) == 2

    assert render_queued_jobs() == 2
    current = client.get(f"{url}/current-module").json()
    assert current["status"] == "ready" and current["level"] == 2
    first = current["module"]["id"]
    manifest = client.get(f"/api/variants/{current['cache_key']}/manifest").json()
    assert [beat["index"] for beat in manifest["beats"]] == [0, 1, 2]

    # Resume, events, checks: all stored in the database.
    position = {"module_id": first, "beat_index": 1, "position_s": 3.5}
    assert client.post(f"{url}/position", json=position).status_code == 204
    assert client.get(url).json()["position"] == position
    now = datetime.now(UTC).isoformat()
    pause = {"type": "pause", "module_id": first, "occurred_at": now, "beat_index": 1,
             "position_s": 3.5, "duration_s": 9.0}  # fmt: skip
    assert client.post("/api/events", json={"events": [pause]}).status_code == 202
    stored = db.scalar(select(InteractionEvent))
    assert (stored.event_type, stored.beat_index, stored.payload) == (
        "pause",
        1,
        {"duration_s": 9.0},
    )

    end = client.post(f"{url}/modules/{first}/finish").json()
    assert [item["id"] for item in end["check_items"]] == [2] and end["branch"] is None
    answer = {"module_id": first, "check_id": 2, "selected_option": "$2$"}
    assert client.post("/api/check-responses", json=answer).json()["is_correct"] is True
    assert client.get(url).json()["position"] is None

    second = client.get(f"{url}/current-module").json()["module"]["id"]
    lost = {"module_id": second, "beat_index": 0, "position_s": 1.0}
    assert client.post(f"{url}/im-lost", json=lost).status_code == 409
    client.post(f"{url}/modules/{second}/finish")
    assert client.get(f"{url}/current-module").json()["status"] == "complete"

    # The history shows the stub's lessons and this one together.
    history = client.get("/api/lessons").json()
    assert lesson_id in [entry["id"] for entry in history] and len(history) == 4

    # Another student cannot see it.
    client.post("/api/auth/logout")
    login(client, "new@fourierlearn.test")
    assert client.get(url).status_code == 404


def test_topics_and_glossary_come_from_the_database_once_seeded(client, db):
    assert client.get("/api/topics").headers.get("x-fourierlearn-stub") == "1"
    seed(db, content())
    db.commit()
    response = client.get("/api/topics")
    assert "x-fourierlearn-stub" not in response.headers
    assert [area["topic_area"] for area in response.json()] == content().taxonomy.topic_areas
    login(client)
    rise = client.get("/api/glossary/Rise")
    assert rise.json()["term"] == "rise" and "x-fourierlearn-stub" not in rise.headers
