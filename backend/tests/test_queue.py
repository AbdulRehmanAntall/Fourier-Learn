"""The render queue, the worker and the content seed, on a real Postgres (TEST_DATABASE_URL)."""

import json
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.audio_pipeline.tts import FakeTTS
from app.content import content
from app.contracts import (
    BeatManifest,
    ModuleManifest,
    ModuleRenderRequest,
    StepTiming,
)
from app.core.config import get_settings
from app.db.models import (
    ConceptPrerequisite,
    GlossaryTerm,
    Lesson,
    Module,
    RenderJob,
    StreamEventRecord,
    Student,
    Variant,
)
from app.db.seed import seed
from app.db.session import get_sessionmaker
from app.renderer.store import MANIFEST_FILE, cache_key_for, variant_directory, write_atomically
from app.scheduler import queue
from app.workers import render_worker

pytestmark = pytest.mark.db

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
TTS = "fake"


def example(level: int = 2) -> ModuleRenderRequest:
    text = (EXAMPLES / f"gradient_of_line.L{level}.render.json").read_text()
    return ModuleRenderRequest.model_validate(json.loads(text))


def new_module(db, title: str = "m") -> Module:
    student = db.scalar(select(Student).limit(1))
    if student is None:
        student = Student(name="S", email="s@example.com", password_hash="!")
        db.add(student)
        db.flush()
    lesson = Lesson(student_id=student.student_id, query_text="q", title=title)
    db.add(lesson)
    db.flush()
    module = Module(
        lesson_id=lesson.lesson_id,
        concept_id=12,
        sequence_no=1,
        difficulty_level="Level 2",
        title=title,
    )
    db.add(module)
    db.flush()
    return module


def events(db, lesson_id: int) -> list[str]:
    rows = db.scalars(
        select(StreamEventRecord.payload)
        .where(StreamEventRecord.lesson_id == lesson_id)
        .order_by(StreamEventRecord.event_id)
    )
    return [payload["type"] for payload in rows]


def fake_manifest(request: ModuleRenderRequest, key: str, beats=None) -> ModuleManifest:
    count = len(request.beats)
    indices = range(count) if beats is None else beats
    return ModuleManifest(
        cache_key=key,
        level=request.level,
        voice="fake:default",
        library_version=request.library_version,
        beat_count=count,
        beats=[
            BeatManifest(
                index=i,
                primitive_id=request.beats[i].primitive_id,
                video=f"beats/{i}.mp4",
                duration_s=10.0,
                steps=[StepTiming(start_s=0, end_s=10, narration=request.beats[i].narration[0])],
            )
            for i in indices
        ],
        module_video="module.mp4" if beats is None else None,
    )


@pytest.fixture(autouse=True)
def own_media_folder(tmp_path, monkeypatch):
    # Each test starts with an empty variant cache.
    monkeypatch.setattr(get_settings(), "media_dir", tmp_path / "media")


@pytest.fixture
def seeded(db):
    seed(db, content())
    db.commit()
    return db


def test_seed_is_idempotent_and_follows_the_content(seeded):
    db = seeded
    edges = db.scalar(select(func.count()).select_from(ConceptPrerequisite))
    counts = seed(db, content())
    db.commit()
    assert counts["concepts"] == len(content().taxonomy.concepts)
    assert counts["prerequisite edges"] == edges == 16
    # Rows added later without an id do not collide with the seeded ones.
    db.add(GlossaryTerm(concept_id=12, term="steepness", definition="How steep a line is."))
    db.commit()


def test_enqueue_shares_a_variant_and_claims_by_priority(seeded):
    db = seeded
    first, second, third = new_module(db, "a"), new_module(db, "b"), new_module(db, "c")
    media = get_settings().media_dir
    job = queue.enqueue(db, first, example(2), priority=2, tts_name=TTS, media_dir=media)
    shared = queue.enqueue(db, second, example(2), priority=1, tts_name=TTS, media_dir=media)
    other = queue.enqueue(db, third, example(3), priority=2, tts_name=TTS, media_dir=media)
    db.commit()
    assert shared is job and other is not job
    assert job.priority == 1  # a more urgent wait raised the shared job
    assert first.cache_key == second.cache_key == cache_key_for(example(2), TTS)

    # Priority first: the shared job, although it was queued as priority 2 first.
    claimed = queue.claim(db, "w1", lease_s=60)
    db.commit()
    assert claimed.job_id == job.job_id and claimed.attempts == 1
    assert events(db, first.lesson_id) == ["generation_progress"]
    assert events(db, second.lesson_id) == ["generation_progress"]


def test_workers_never_take_the_same_job(seeded):
    db = seeded
    media = get_settings().media_dir
    for level in (1, 2):
        queue.enqueue(db, new_module(db), example(level), priority=1, tts_name=TTS, media_dir=media)
    db.commit()
    maker = get_sessionmaker()
    with maker() as a, maker() as b:
        job_a = queue.claim(a, "a", lease_s=60)  # holds its row lock until commit
        job_b = queue.claim(b, "b", lease_s=60)  # skips the locked row
        assert job_a.job_id != job_b.job_id
        a.commit()
        b.commit()
    with maker() as c:
        assert queue.claim(c, "c", lease_s=60) is None


def test_a_job_whose_worker_died_is_taken_over(seeded):
    db = seeded
    media = get_settings().media_dir
    job = queue.enqueue(db, new_module(db), example(), priority=1, tts_name=TTS, media_dir=media)
    db.commit()
    queue.claim(db, "dead", lease_s=60)
    db.commit()
    assert queue.claim(db, "alive", lease_s=60) is None
    job.started_at = job.started_at - timedelta(seconds=120)
    db.commit()
    taken = queue.claim(db, "alive", lease_s=60)
    assert taken.job_id == job.job_id and taken.worker == "alive" and taken.attempts == 2


def test_a_failing_job_is_retried_then_reported(seeded):
    db = seeded
    media = get_settings().media_dir
    module = new_module(db)
    job = queue.enqueue(db, module, example(), priority=1, tts_name=TTS, media_dir=media)
    db.commit()
    for attempt in (1, 2, 3):
        claimed = queue.claim(db, "w", lease_s=60)
        assert claimed.attempts == attempt
        queue.fail(db, claimed, "LayoutViolation: label overlaps line", max_attempts=3)
        db.commit()
    assert job.status == "failed" and module.render_status == "failed"
    assert job.log.count("failed: LayoutViolation") == 3 and "gave up" in job.log
    assert events(db, module.lesson_id)[-1] == "module_failed"


def test_the_worker_renders_a_job_and_releases_its_modules(seeded):
    db = seeded
    media = get_settings().media_dir
    module = new_module(db)
    request = example()
    queue.enqueue(db, module, request, priority=1, tts_name=TTS, media_dir=media)
    db.commit()

    def fake_render(request, *, media_dir, tts, on_beat_ready, **_):
        key = cache_key_for(request, tts.name)
        manifest = fake_manifest(request, key)
        for beat in manifest.beats:
            on_beat_ready(beat)
        directory = variant_directory(media_dir, key)
        directory.mkdir(parents=True, exist_ok=True)
        write_atomically(directory / MANIFEST_FILE, manifest.model_dump_json())

        class Result:
            pass

        result = Result()
        result.manifest = manifest
        return result

    stopped = render_worker.threading.Event()
    assert render_worker.run(stopped, once=True, render=fake_render, tts=FakeTTS()) == 1
    db.expire_all()
    job = db.scalar(select(RenderJob))
    assert job.status == "ready" and job.duration_s is not None
    assert module.render_status == "ready"
    assert db.get(Variant, module.cache_key).beat_count == len(request.beats)
    assert events(db, module.lesson_id) == [
        "generation_progress",
        "beat_ready",
        "beat_ready",
        "beat_ready",
        "module_ready",
    ]

    # The same variant again is a cache hit: no job, the module is ready at once.
    again = new_module(db, "again")
    assert queue.enqueue(db, again, request, priority=1, tts_name=TTS, media_dir=media) is None
    db.commit()
    assert again.render_status == "ready"
    assert db.scalar(select(func.count()).select_from(RenderJob)) == 1
