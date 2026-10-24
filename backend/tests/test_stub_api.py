"""The Phase 2 stub API: every endpoint the frontend uses, through HTTP (docs/frontend.md §7–8).

The stub's clock is replaced by one the tests move forward, so simulated rendering, prefetching
and "I'm Lost" re-rendering can be stepped through without waiting.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.contracts import BeatReady, GenerationProgress, Level, ModuleFailed, ModuleReady
from app.main import app
from app.stub import get_store
from app.stub.fixtures import load_fixture_variants
from app.stub.seed import STUB_PASSWORD
from app.stub.store import StubStore

VARIANTS = load_fixture_variants()
KEY = {level: VARIANTS[level].cache_key for level in Level}


class Clock:
    def __init__(self) -> None:
        self.t = 10_000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def store(clock):
    store = StubStore(VARIANTS, clock=clock)
    app.dependency_overrides[get_store] = lambda: store
    yield store
    app.dependency_overrides.clear()


@pytest.fixture
def client(store):
    with TestClient(app) as client:
        yield client


def login(client, email="student@fourierlearn.test", password=STUB_PASSWORD):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def now():
    return datetime.now(UTC).isoformat()


# ------------------------------------------------------------------ accounts


def test_register_login_logout(client):
    assert client.get("/api/auth/me").status_code == 401
    created = client.post(
        "/api/auth/register",
        json={"name": "Sana", "email": "Sana@Example.com", "password": "longenough"},
    )
    assert created.status_code == 201
    assert created.json()["email"] == "sana@example.com"
    assert created.json()["diagnostic_complete"] is False
    assert created.headers["x-fourierlearn-stub"] == "1"
    assert "httponly" in created.headers["set-cookie"].lower()
    assert client.get("/api/auth/me").json()["name"] == "Sana"

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401

    again = client.post(
        "/api/auth/register",
        json={"name": "Sana", "email": "sana@example.com", "password": "longenough"},
    )
    assert again.status_code == 409


def test_login_errors(client):
    wrong = client.post(
        "/api/auth/login", json={"email": "student@fourierlearn.test", "password": "nope"}
    )
    assert wrong.status_code == 401
    assert wrong.json()["detail"] == "Incorrect email or password."
    short = client.post(
        "/api/auth/register", json={"name": "A", "email": "a@b.co", "password": "short"}
    )
    assert short.status_code == 422


def test_diagnostic_resumes_and_completes(client):
    login(client, "new@fourierlearn.test")
    state = client.get("/api/diagnostic").json()
    assert state["complete"] is False and state["total"] == 5 and state["answered"] == 0
    assert "correct_option" not in state["item"]

    first = state["item"]
    out_of_order = client.post(
        "/api/diagnostic/answers", json={"check_id": 999, "selected_option": "x"}
    )
    assert out_of_order.status_code == 409
    state = client.post(
        "/api/diagnostic/answers",
        json={"check_id": first["id"], "selected_option": first["options"][0]},
    ).json()
    assert state["answered"] == 1

    # Leaving and coming back resumes at the next question.
    client.post("/api/auth/logout")
    login(client, "new@fourierlearn.test")
    state = client.get("/api/diagnostic").json()
    assert state["answered"] == 1
    while not state["complete"]:
        item = state["item"]
        state = client.post(
            "/api/diagnostic/answers",
            json={"check_id": item["id"], "selected_option": item["options"][1]},
        ).json()
    assert state["item"] is None
    assert client.get("/api/auth/me").json()["diagnostic_complete"] is True
    scored = [c for c in client.get("/api/progress").json()["concepts"] if c["updated_at"]]
    assert len(scored) == 5


# ------------------------------------------------------------------ lessons


def test_topics_glossary_and_progress(client):
    topics = client.get("/api/topics").json()
    assert [t["topic_area"] for t in topics][0] == "Functions and graphs"
    login(client)
    gradient = client.get("/api/glossary/Gradient").json()
    assert gradient["term"] == "gradient" and "$" in gradient["definition"]
    assert client.get("/api/glossary/no-such-term").status_code == 404
    # Every chip in the fixture manifests has a definition.
    for level in Level:
        manifest = client.get(f"/api/variants/{KEY[level]}/manifest").json()
        for beat in manifest["beats"]:
            for chip in beat["chips"]:
                assert client.get(f"/api/glossary/{chip['term']}").status_code == 200
    progress = client.get("/api/progress").json()["concepts"]
    assert len(progress) == 15 and all(0 <= c["score"] <= 1 for c in progress)


def test_out_of_scope_query(client):
    login(client)
    reply = client.post("/api/lessons", json={"query_text": "explain photosynthesis"}).json()
    assert reply["status"] == "out_of_scope"
    assert len(reply["nearest_concepts"]) == 2 and len(reply["topics"]) == 5


def test_seeded_lessons_and_resume(client):
    login(client)
    lessons = client.get("/api/lessons").json()
    assert {lesson["status"] for lesson in lessons} == {"in_progress", "completed"}
    in_progress = next(
        lesson
        for lesson in lessons
        if lesson["status"] == "in_progress" and lesson["modules_completed"] == 1
    )
    lesson = client.get(f"/api/lessons/{in_progress['id']}").json()
    assert lesson["position"]["module_id"] == lesson["modules"][1]["id"]
    current = client.get(f"/api/lessons/{in_progress['id']}/current-module").json()
    assert current["status"] == "ready" and current["module"]["id"] == lesson["modules"][1]["id"]
    assert current["cache_key"] == KEY[Level.CONCISE]


def test_a_whole_lesson(client, clock, store):
    login(client)
    lesson_id = client.post("/api/lessons", json={"query_text": "explain the gradient"}).json()[
        "lesson_id"
    ]
    url = f"/api/lessons/{lesson_id}"
    start = clock.t

    current = client.get(f"{url}/current-module").json()
    assert current["status"] == "preparing" and current["stage"] == "planning"
    clock.advance(4.5)
    assert client.get(f"{url}/current-module").json()["stage"] == "narration"
    clock.advance(3)
    current = client.get(f"{url}/current-module").json()
    assert current["status"] == "ready" and current["level"] == 2
    assert current["cache_key"] == KEY[Level.STANDARD]
    first = current["module"]

    # The stream announced the stages, then each beat, then the module.
    events = list(store.stream_events(lesson_id, start - 1, clock.t + 100))
    assert [type(e) for e in events[:4]] == [GenerationProgress] * 4
    assert [e.beat_index for e in events if isinstance(e, BeatReady)][:3] == [0, 1, 2]
    assert any(isinstance(e, ModuleReady) for e in events)

    # Playing module 1 prefetches module 2.
    lesson = client.get(url).json()
    assert lesson["modules"][1]["render_status"] == "rendering"

    position = {"module_id": first["id"], "beat_index": 2, "position_s": 3.5}
    assert client.post(f"{url}/position", json=position).status_code == 204
    assert client.get(url).json()["position"] == position

    # Module 1 ends: two check items and a branch point.
    end = client.post(f"{url}/modules/{first['id']}/finish").json()
    assert len(end["check_items"]) == 2
    assert [o["choice"] for o in end["branch"]["options"]] == [
        "theory",
        "worked_example",
        "next_step",
    ]
    item = end["check_items"][0]
    result = client.post(
        "/api/check-responses",
        json={"module_id": first["id"], "check_id": item["id"], "selected_option": "False"},
    ).json()
    assert result == {"is_correct": False, "correct_option": "True"}

    # Choosing the worked example inserts a module after module 1.
    lesson = client.post(
        f"{url}/branch", json={"module_id": first["id"], "choice": "worked_example"}
    ).json()
    assert [m["style"] for m in lesson["modules"]] == [
        "default",
        "worked_example",
        "default",
        "default",
    ]
    assert (
        client.post(
            f"{url}/branch", json={"module_id": first["id"], "choice": "theory"}
        ).status_code
        == 409
    )
    current = client.get(f"{url}/current-module").json()
    assert current["status"] == "preparing" and current["module"]["style"] == "worked_example"
    clock.advance(6)
    inserted = client.get(f"{url}/current-module").json()
    assert inserted["status"] == "ready"
    client.post(f"{url}/modules/{inserted['module']['id']}/finish")

    # Module 2 plays at Level 3; "I'm Lost" in beat 1 re-renders it at Level 2 from beat 1.
    clock.advance(10)
    current = client.get(f"{url}/current-module").json()
    assert current["status"] == "ready" and current["level"] == 3
    second = current["module"]["id"]
    before = clock.t
    lost = client.post(
        f"{url}/im-lost", json={"module_id": second, "beat_index": 1, "position_s": 2.0}
    ).json()
    assert lost == {
        "action": "substitute",
        "level": 2,
        "cache_key": KEY[Level.STANDARD],
        "resume_beat_index": 1,
        "ready": False,
    }
    ready = [
        e
        for e in store.stream_events(lesson_id, before, before + 60)
        if isinstance(e, BeatReady) and e.module_id == second
    ]
    assert [(e.beat_index, e.level) for e in ready] == [(1, 2), (2, 2)]
    assert client.get(url).json()["modules"][2]["level"] == 2

    client.post(f"{url}/modules/{second}/finish")
    clock.advance(20)
    last = client.get(f"{url}/current-module").json()
    client.post(f"{url}/modules/{last['module']['id']}/finish")
    assert client.get(f"{url}/current-module").json()["status"] == "complete"
    assert client.get(url).json()["status"] == "completed"

    # "I'm Lost" was recorded by its endpoint, the branch choice by its own.
    logged = [e["event"]["type"] for e in client.get("/api/dev/events").json()]
    assert logged == ["branch_choice", "im_lost"]


def test_im_lost_at_level_1_replays(client, clock, store):
    login(client)
    lesson_id = client.post("/api/lessons", json={"query_text": "slope"}).json()["lesson_id"]
    url = f"/api/lessons/{lesson_id}"
    clock.advance(8)
    module = client.get(f"{url}/current-module").json()["module"]
    body = {"module_id": module["id"], "beat_index": 0, "position_s": 1.0}
    client.post(f"{url}/im-lost", json=body)  # Level 2 → Level 1
    replay = client.post(f"{url}/im-lost", json=body).json()
    assert replay == {"action": "replay", "resume_beat_index": 0, "worked_example_added": True}
    again = client.post(f"{url}/im-lost", json=body).json()
    assert again["worked_example_added"] is False
    styles = [m["style"] for m in client.get(url).json()["modules"]]
    assert styles.count("worked_example") == 1


def test_failed_module_and_slow_start(client, clock, store):
    login(client)
    lesson_id = client.post("/api/lessons", json={"query_text": "gradient test:fail"}).json()[
        "lesson_id"
    ]
    url = f"/api/lessons/{lesson_id}"
    clock.advance(8)
    first = client.get(f"{url}/current-module").json()["module"]
    client.post(f"{url}/modules/{first['id']}/finish")
    client.post(f"{url}/branch", json={"module_id": first["id"], "choice": "next_step"})
    clock.advance(20)
    failed = client.get(f"{url}/current-module").json()
    assert failed["status"] == "failed"
    assert failed["failure"]["fallback"] == "glossary_definition"
    assert failed["failure"]["definition"]
    assert any(isinstance(e, ModuleFailed) for _, e in store.lessons[lesson_id].stream)
    end = client.post(f"{url}/modules/{failed['module']['id']}/finish").json()
    assert end == {"check_items": [], "branch": None}

    slow = client.post("/api/lessons", json={"query_text": "test:slow"}).json()["lesson_id"]
    clock.advance(30)
    assert client.get(f"/api/lessons/{slow}/current-module").json()["status"] == "preparing"
    clock.advance(30)
    assert client.get(f"/api/lessons/{slow}/current-module").json()["status"] == "ready"


def test_static_lesson_has_no_interactive_layer(client, clock):
    login(client)
    lesson_id = client.post("/api/lessons", json={"query_text": "test:static"}).json()["lesson_id"]
    url = f"/api/lessons/{lesson_id}"
    assert client.get(url).json()["mode"] == "static"
    clock.advance(8)
    module = client.get(f"{url}/current-module").json()["module"]
    assert module["level"] == 2
    lost = client.post(
        f"{url}/im-lost", json={"module_id": module["id"], "beat_index": 0, "position_s": 0}
    )
    assert lost.status_code == 409
    end = client.post(f"{url}/modules/{module['id']}/finish").json()
    assert end == {"check_items": [], "branch": None}


def test_other_students_lessons_are_hidden(client):
    login(client)
    lesson_id = client.get("/api/lessons").json()[0]["id"]
    client.post("/api/auth/logout")
    login(client, "new@fourierlearn.test")
    assert client.get(f"/api/lessons/{lesson_id}").status_code == 404


# ------------------------------------------------------------------ interaction events


def test_event_batches(client):
    login(client)
    lesson = client.get(f"/api/lessons/{client.get('/api/lessons').json()[0]['id']}").json()
    module_id = lesson["modules"][0]["id"]
    events = [
        {"type": "pause", "module_id": module_id, "occurred_at": now(), "beat_index": 0,
         "position_s": 4.0, "duration_s": 12.5},
        {"type": "speed_change", "module_id": module_id, "occurred_at": now(), "beat_index": 1,
         "position_s": 2.0, "from_rate": 1.0, "to_rate": 0.75},
        {"type": "rewind", "module_id": module_id, "occurred_at": now(), "beat_index": 1,
         "position_s": 2.0, "to_beat_index": 0, "to_position_s": 8.0},
        {"type": "chip_view", "module_id": module_id, "occurred_at": now(), "beat_index": 1,
         "position_s": 3.0, "term": "gradient"},
    ]  # fmt: skip
    assert client.post("/api/events", json={"events": events}).status_code == 202
    logged = client.get("/api/dev/events").json()
    assert [e["event"]["type"] for e in logged] == ["pause", "speed_change", "rewind", "chip_view"]

    im_lost = {"type": "im_lost", "module_id": module_id, "occurred_at": now(), "beat_index": 0,
               "position_s": 1.0}  # fmt: skip
    assert client.post("/api/events", json={"events": [im_lost]}).status_code == 422
    forward = dict(events[2], to_beat_index=2)
    assert client.post("/api/events", json={"events": [forward]}).status_code == 422
    foreign = dict(events[0], module_id=2_000_000_000)
    assert client.post("/api/events", json={"events": [foreign]}).status_code == 404
    assert client.post("/api/events", json={"events": []}).status_code == 422


# ------------------------------------------------------------------ admin


def test_admin_needs_an_admin(client):
    assert client.get("/api/admin/summary").status_code == 401
    login(client)
    assert client.get("/api/admin/summary").status_code == 403


def test_admin_pages(client):
    login(client, "admin@fourierlearn.test")
    summary = client.get("/api/admin/summary").json()
    assert summary["students"] == 12 and summary["renders_failed_24h"] >= 0

    primitives = client.get("/api/admin/primitives").json()
    assert {p["id"] for p in primitives} == {
        "FunctionGraph",
        "GradientTriangle",
        "TangentSlide",
        "SecantToTangent",
        "TravelGraph",
        "AreaUnderCurve",
        "EquationTransform",
    }
    retired = client.patch("/api/admin/primitives/FunctionGraph", json={"status": "retired"})
    assert retired.json()["status"] == "retired"

    page = client.get("/api/admin/glossary", params={"search": "rad", "page_size": 5}).json()
    assert page["items"][0]["term"] == "gradient" and page["page_size"] == 5
    term = client.post(
        "/api/admin/glossary",
        json={"concept_id": 12, "term": "steepness", "definition": "How steep a line is."},
    )
    assert term.status_code == 201
    term_id = term.json()["id"]
    duplicate = client.post(
        "/api/admin/glossary", json={"concept_id": 12, "term": "Gradient", "definition": "x"}
    )
    assert duplicate.status_code == 409
    edited = client.patch(f"/api/admin/glossary/{term_id}", json={"definition": "Changed."})
    assert edited.json()["definition"] == "Changed."
    assert client.delete(f"/api/admin/glossary/{term_id}").status_code == 204
    assert client.delete(f"/api/admin/glossary/{term_id}").status_code == 404

    question = {
        "concept_id": 12,
        "item_type": "mcq",
        "question_text": "Gradient of $y = 4x$?",
        "options": ["$4$", "$1$"],
        "correct_option": "$4$",
    }
    created = client.post("/api/admin/check-questions", json=question)
    assert created.status_code == 201
    bad = client.post("/api/admin/check-questions", json=dict(question, correct_option="$5$"))
    assert bad.status_code == 422
    bad_tf = dict(question, item_type="true_false")
    assert client.post("/api/admin/check-questions", json=bad_tf).status_code == 422
    item_id = created.json()["id"]
    broken = client.patch(f"/api/admin/check-questions/{item_id}", json={"options": ["$1$", "$2$"]})
    assert broken.status_code == 422
    fixed = client.patch(
        f"/api/admin/check-questions/{item_id}",
        json={"options": ["$1$", "$4$"], "correct_option": "$4$"},
    )
    assert fixed.status_code == 200

    failed = client.get("/api/admin/render-jobs", params={"status": "failed"}).json()
    assert failed["total"] == 3 and all(job["error"] for job in failed["items"])
    detail = client.get(f"/api/admin/render-jobs/{failed['items'][0]['id']}").json()
    assert "attempt 3" in detail["log"]

    students = client.get("/api/admin/students", params={"search": "test student"}).json()
    student_id = students["items"][0]["id"]
    disabled = client.patch(f"/api/admin/students/{student_id}", json={"disabled": True})
    assert disabled.json()["disabled"] is True
    client.post("/api/auth/logout")
    blocked = client.post(
        "/api/auth/login",
        json={"email": "student@fourierlearn.test", "password": STUB_PASSWORD},
    )
    assert blocked.status_code == 403


def test_real_endpoints_are_not_marked_as_stub(client):
    assert "x-fourierlearn-stub" not in client.get("/api/health").headers
