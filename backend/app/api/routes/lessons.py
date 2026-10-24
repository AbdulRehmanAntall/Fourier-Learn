"""Lessons and their playback (UC 4.3–4.7, §5.5, §5.6, §6.4.12).

Two kinds of lesson play through these endpoints: the Phase 2 stub's (ids from 1,000,000) and
lessons stored in the database, made by POST /api/dev/render and rendered by the queue (Phase
3). The id says which serves the request; both return the same shapes.
"""

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import TypeAdapter

from app.api.database import in_database
from app.api.deps import CurrentUser, Store
from app.api.schemas.dev import DevLessonRequest
from app.api.schemas.lessons import (
    BranchRequest,
    CheckResponseRequest,
    CheckResponseResult,
    CreateLessonRequest,
    CreateLessonResponse,
    CurrentModule,
    ImLostRequest,
    ImLostResult,
    Lesson,
    LessonCreated,
    LessonSummary,
    ModuleEnd,
    Position,
)
from app.audio_pipeline.tts import get_provider
from app.contracts.stream import StreamEvent, encode_sse
from app.core.config import get_settings
from app.db.session import database_available
from app.lessons import service
from app.stub import is_stub_id

router = APIRouter(tags=["lessons"])

STREAM_POLL_S = 0.25
DATABASE_POLL_S = 0.5
KEEP_ALIVE_S = 15.0
NOT_YET = {
    "branch": "Branch points for generated lessons arrive in Phase 6.",
    "im-lost": '"I\'m Lost" for generated lessons arrives in Phase 6.',
}
_STREAM_EVENT: TypeAdapter = TypeAdapter(StreamEvent)


@router.post("/lessons", response_model=CreateLessonResponse)
async def create_lesson(
    body: CreateLessonRequest, user: CurrentUser, store: Store
) -> CreateLessonResponse:
    """Submit a topic query. Out-of-scope queries get the list of topics (UC 4.3)."""
    return store.create_lesson(user, body.query_text)


@router.post("/dev/render", response_model=LessonCreated, tags=["dev"])
async def create_dev_lesson(body: DevLessonRequest, user: CurrentUser) -> LessonCreated:
    """Development only: store a hand-written lesson (scene plans with render requests), check
    it (§5.2.3), and queue its renders. A running worker (npm run worker) renders it. The
    lesson then plays like any other; 422 lists every problem found."""
    settings = get_settings()
    tts_name = get_provider(settings.tts_provider).name
    lesson_id = await in_database(
        lambda db: service.create_dev_lesson(
            db, user, body, tts_name=tts_name, media_dir=settings.media_dir
        ),
        commit=True,
    )
    return LessonCreated(lesson_id=lesson_id)


@router.get("/lessons", response_model=list[LessonSummary])
async def list_lessons(user: CurrentUser, store: Store) -> list[LessonSummary]:
    """Lesson history, newest first."""
    lessons = store.lessons_of(user)
    if database_available():
        lessons += await in_database(lambda db: service.lessons_of(db, user), answers=False)
    return sorted(lessons, key=lambda lesson: lesson.started_at, reverse=True)


@router.get("/lessons/{lesson_id}", response_model=Lesson)
async def get_lesson(lesson_id: int, user: CurrentUser, store: Store) -> Lesson:
    if is_stub_id(lesson_id):
        return store.lesson_out(user, lesson_id)
    return await in_database(
        lambda db: service.lesson_out(db, service.find_lesson(db, user, lesson_id))
    )


@router.get("/lessons/{lesson_id}/current-module", response_model=CurrentModule)
async def current_module(lesson_id: int, user: CurrentUser, store: Store) -> CurrentModule:
    """What to play now: the first module not yet finished, and whether it is ready."""
    if is_stub_id(lesson_id):
        return store.current_module(user, lesson_id)
    media_dir = get_settings().media_dir
    return await in_database(
        lambda db: service.current_module(db, service.find_lesson(db, user, lesson_id), media_dir),
        commit=True,
    )


@router.get(
    "/lessons/{lesson_id}/events",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "StreamEvent messages"}},
)
async def lesson_events(
    lesson_id: int, request: Request, user: CurrentUser, store: Store
) -> StreamingResponse:
    """Server-Sent Events for one lesson (§6.4.12). The event names and payloads are the
    `StreamEvent` schemas. Only events after the connection opened are sent, so the browser
    fetches the lesson's state each time the stream (re)opens."""
    if is_stub_id(lesson_id):
        store.lesson_out(user, lesson_id)  # 404 unless the lesson is the student's
        stream = _stub_stream(lesson_id, request, store)
    else:
        start = await in_database(
            lambda db: (
                service.find_lesson(db, user, lesson_id) and service.latest_event_id(db, lesson_id)
            )
        )
        stream = _database_stream(lesson_id, request, start)
    headers = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}
    return StreamingResponse(stream, media_type="text/event-stream", headers=headers)


async def _stub_stream(lesson_id: int, request: Request, store) -> AsyncIterator[str]:
    sent_until = last_write = store.now()
    yield ": connected\n\n"
    while not await request.is_disconnected():
        now = store.now()
        for event in store.stream_events(lesson_id, sent_until, now):
            yield encode_sse(event)
            last_write = now
        sent_until = now
        if now - last_write >= KEEP_ALIVE_S:
            yield ": keep-alive\n\n"
            last_write = now
        await asyncio.sleep(STREAM_POLL_S)


async def _database_stream(lesson_id: int, request: Request, after: int) -> AsyncIterator[str]:
    """The events the workers write for this lesson, as they arrive."""
    loop = asyncio.get_running_loop()
    last_write = loop.time()
    yield ": connected\n\n"
    while not await request.is_disconnected():
        try:
            rows = await in_database(
                lambda db, after=after: service.events_after(db, lesson_id, after)
            )
        except HTTPException:  # the database went away; the browser reconnects and resyncs
            return
        for event_id, payload in rows:
            yield encode_sse(_STREAM_EVENT.validate_python(payload), event_id)
            after = event_id
            last_write = loop.time()
        if loop.time() - last_write >= KEEP_ALIVE_S:
            yield ": keep-alive\n\n"
            last_write = loop.time()
        await asyncio.sleep(DATABASE_POLL_S)


@router.post("/lessons/{lesson_id}/position", status_code=204)
async def save_position(lesson_id: int, body: Position, user: CurrentUser, store: Store) -> None:
    """Save where the student is, for resuming. POST, so `navigator.sendBeacon` can call it."""
    if is_stub_id(lesson_id):
        store.save_position(user, lesson_id, body)
        return
    await in_database(
        lambda db: service.save_position(db, service.find_lesson(db, user, lesson_id), body),
        commit=True,
    )


@router.post("/lessons/{lesson_id}/modules/{module_id}/finish", response_model=ModuleEnd)
async def finish_module(
    lesson_id: int, module_id: int, user: CurrentUser, store: Store
) -> ModuleEnd:
    """The module ended: returns its check items and branch point, if any."""
    if is_stub_id(lesson_id):
        return store.finish_module(user, lesson_id, module_id)
    return await in_database(
        lambda db: service.finish_module(db, service.find_lesson(db, user, lesson_id), module_id),
        commit=True,
    )


@router.post("/check-responses", response_model=CheckResponseResult)
async def answer_check(
    body: CheckResponseRequest, user: CurrentUser, store: Store
) -> CheckResponseResult:
    """An answer to a check item after a module (UC 4.6)."""
    if is_stub_id(body.module_id):
        return store.answer_check(user, body)
    return await in_database(lambda db: service.answer_check(db, user, body), commit=True)


@router.post("/lessons/{lesson_id}/branch", response_model=Lesson)
async def choose_branch(
    lesson_id: int, body: BranchRequest, user: CurrentUser, store: Store
) -> Lesson:
    """The option chosen at a branch point (UC 4.7). Records the branch_choice event."""
    if is_stub_id(lesson_id):
        return store.choose_branch(user, lesson_id, body)
    raise HTTPException(status_code=409, detail=NOT_YET["branch"])


@router.post("/lessons/{lesson_id}/im-lost", response_model=ImLostResult)
async def im_lost(
    lesson_id: int, body: ImLostRequest, user: CurrentUser, store: Store
) -> ImLostResult:
    """An "I'm Lost" press during a module (UC 4.4, §5.6.3). Records the im_lost event."""
    if is_stub_id(lesson_id):
        return store.im_lost(user, lesson_id, body)
    raise HTTPException(status_code=409, detail=NOT_YET["im-lost"])
