"""Lessons and their playback (UC 4.3–4.7, §5.5, §5.6, §6.4.12)."""

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, Store
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
    LessonSummary,
    ModuleEnd,
    Position,
)
from app.contracts.stream import encode_sse

router = APIRouter(tags=["lessons"])

STREAM_POLL_S = 0.25
KEEP_ALIVE_S = 15.0


@router.post("/lessons", response_model=CreateLessonResponse)
async def create_lesson(
    body: CreateLessonRequest, user: CurrentUser, store: Store
) -> CreateLessonResponse:
    """Submit a topic query. Out-of-scope queries get the list of topics (UC 4.3)."""
    return store.create_lesson(user, body.query_text)


@router.get("/lessons", response_model=list[LessonSummary])
async def list_lessons(user: CurrentUser, store: Store) -> list[LessonSummary]:
    """Lesson history, newest first."""
    return store.lessons_of(user)


@router.get("/lessons/{lesson_id}", response_model=Lesson)
async def get_lesson(lesson_id: int, user: CurrentUser, store: Store) -> Lesson:
    return store.lesson_out(user, lesson_id)


@router.get("/lessons/{lesson_id}/current-module", response_model=CurrentModule)
async def current_module(lesson_id: int, user: CurrentUser, store: Store) -> CurrentModule:
    """What to play now: the first module not yet finished, and whether it is ready."""
    return store.current_module(user, lesson_id)


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
    store.lesson_out(user, lesson_id)  # 404 unless the lesson is the student's

    async def stream() -> AsyncIterator[str]:
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

    headers = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}
    return StreamingResponse(stream(), media_type="text/event-stream", headers=headers)


@router.post("/lessons/{lesson_id}/position", status_code=204)
async def save_position(lesson_id: int, body: Position, user: CurrentUser, store: Store) -> None:
    """Save where the student is, for resuming. POST, so `navigator.sendBeacon` can call it."""
    store.save_position(user, lesson_id, body)


@router.post("/lessons/{lesson_id}/modules/{module_id}/finish", response_model=ModuleEnd)
async def finish_module(
    lesson_id: int, module_id: int, user: CurrentUser, store: Store
) -> ModuleEnd:
    """The module ended: returns its check items and branch point, if any."""
    return store.finish_module(user, lesson_id, module_id)


@router.post("/check-responses", response_model=CheckResponseResult)
async def answer_check(
    body: CheckResponseRequest, user: CurrentUser, store: Store
) -> CheckResponseResult:
    """An answer to a check item after a module (UC 4.6)."""
    return store.answer_check(user, body)


@router.post("/lessons/{lesson_id}/branch", response_model=Lesson)
async def choose_branch(
    lesson_id: int, body: BranchRequest, user: CurrentUser, store: Store
) -> Lesson:
    """The option chosen at a branch point (UC 4.7). Records the branch_choice event."""
    return store.choose_branch(user, lesson_id, body)


@router.post("/lessons/{lesson_id}/im-lost", response_model=ImLostResult)
async def im_lost(
    lesson_id: int, body: ImLostRequest, user: CurrentUser, store: Store
) -> ImLostResult:
    """An "I'm Lost" press during a module (UC 4.4, §5.6.3). Records the im_lost event."""
    return store.im_lost(user, lesson_id, body)
