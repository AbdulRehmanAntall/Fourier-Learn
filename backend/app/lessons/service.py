"""Lessons stored in the database: the real path behind the lesson endpoints (Phase 3).

A lesson made with POST /api/dev/render is stored here, rendered by the queue and workers, and
played through the same endpoints as the stub's lessons. Each function returns the API schema
of its endpoint, as the stub does, so the routes do not care which one answered.

Until real accounts arrive (Phase 5), the signed-in user is a stub account. The lesson belongs
to a student row with the same email, created on first use; it has no usable password.

Not yet here, and refused with 409 for these lessons: "I'm Lost" re-rendering and branch
insertion (Phase 6). The check items after a module come from the item bank.
"""

from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas.common import CheckItem
from app.api.schemas.dev import DevLessonRequest
from app.api.schemas.lessons import (
    CheckResponseRequest,
    CheckResponseResult,
    CurrentModule,
    Lesson,
    LessonSummary,
    ModuleEnd,
    ModuleFailure,
    ModuleSummary,
    Position,
)
from app.contracts import (
    InteractionEventBatch,
    InteractionType,
    LessonStatus,
    Level,
    ModuleRenderRequest,
    ModuleStyle,
    RenderStatus,
    ScenePlan,
)
from app.db.models import (
    CheckQuestion,
    CheckResponse,
    Concept,
    GlossaryTerm,
    RenderJob,
    StreamEventRecord,
    Student,
)
from app.db.models import InteractionEvent as InteractionEventRow
from app.db.models import Lesson as LessonRow
from app.db.models import Module as ModuleRow
from app.primitives.catalog import LIBRARY_VERSION, PRIMITIVE_IDS
from app.prompt_interpreter.plan_checks import References, reference_problems
from app.renderer.store import load_manifest, variant_directory
from app.scheduler import queue
from app.stub.store import UserRecord

UNUSABLE_PASSWORD = "!"
"""Never a valid hash: the row cannot be logged into until real accounts replace the stub."""


def student_for(db: Session, user: UserRecord) -> Student:
    student = db.scalar(select(Student).where(Student.email == user.email))
    if student is None:
        student = Student(name=user.name, email=user.email, password_hash=UNUSABLE_PASSWORD)
        db.add(student)
        db.flush()
    return student


def find_lesson(db: Session, user: UserRecord, lesson_id: int) -> LessonRow:
    lesson = db.get(LessonRow, lesson_id)
    if lesson is None or db.get(Student, lesson.student_id).email != user.email:
        raise HTTPException(status_code=404, detail="No such lesson")
    return lesson


# ------------------------------------------------------------------ creating a lesson


def references(db: Session) -> References:
    return References(
        primitive_ids=PRIMITIVE_IDS,
        concept_ids=set(db.scalars(select(Concept.concept_id))),
        glossary_terms={term.lower() for term in db.scalars(select(GlossaryTerm.term))},
        check_ids=set(db.scalars(select(CheckQuestion.check_id))),
    )


def lesson_problems(db: Session, body: DevLessonRequest) -> list[str]:
    """Everything wrong with a hand-written lesson: the reference check of each plan (§5.2.3),
    and whether each render request matches its plan."""
    refs = references(db)
    problems = []
    if not refs.concept_ids:
        problems.append("the database has no concepts yet: run npm run db:seed")
    for number, module in enumerate(body.modules, start=1):
        where = f"module {number}"
        problems += reference_problems(module.plan, refs, where)
        if body.level not in {render.level for render in module.renders}:
            problems.append(f"{where}: no render request at {body.level.label}")
        segments = [segment.primitive_id for segment in module.plan.segments]
        for render in module.renders:
            beats = [beat.primitive_id for beat in render.beats]
            if beats != segments:
                problems.append(
                    f"{where}, {render.level.label}: the beats {beats} do not match the "
                    f"plan's segments {segments}; every variant has the plan's segments, in "
                    "order (§5.2.3)"
                )
            if render.library_version != LIBRARY_VERSION:
                problems.append(
                    f"{where}, {render.level.label}: written for primitive library "
                    f"{render.library_version}, but this is {LIBRARY_VERSION}"
                )
    return problems


def create_dev_lesson(
    db: Session, user: UserRecord, body: DevLessonRequest, *, tts_name: str, media_dir: Path
) -> int:
    problems = lesson_problems(db, body)
    if problems:
        raise HTTPException(status_code=422, detail=problems)
    student = student_for(db, user)
    lesson = LessonRow(
        student_id=student.student_id,
        query_text=body.query_text,
        title=body.title,
        status=LessonStatus.IN_PROGRESS.value,
        mode="adaptive",
    )
    db.add(lesson)
    db.flush()
    for number, module in enumerate(body.modules, start=1):
        render = next(r for r in module.renders if r.level == body.level)
        row = ModuleRow(
            lesson_id=lesson.lesson_id,
            concept_id=module.plan.concept_id,
            sequence_no=number,
            difficulty_level=body.level.label,
            style=ModuleStyle.DEFAULT.value,
            render_status=RenderStatus.QUEUED.value,
            title=module.title,
            scene_plan=module.plan.model_dump(mode="json"),
            render_requests={str(int(r.level)): r.model_dump(mode="json") for r in module.renders},
        )
        db.add(row)
        db.flush()
        # The first module is needed now; later ones render behind it (prefetching, §5.5).
        queue.enqueue(
            db,
            row,
            render,
            priority=1 if number == 1 else 2,
            tts_name=tts_name,
            media_dir=media_dir,
        )
    return lesson.lesson_id


# ------------------------------------------------------------------ reading a lesson


def _modules(db: Session, lesson: LessonRow) -> list[ModuleRow]:
    return list(
        db.scalars(
            select(ModuleRow)
            .where(ModuleRow.lesson_id == lesson.lesson_id)
            .order_by(ModuleRow.sequence_no)
        )
    )


def _level(module: ModuleRow) -> Level:
    return Level(int(module.difficulty_level.split()[-1]))


def _module_out(module: ModuleRow) -> ModuleSummary:
    return ModuleSummary(
        id=module.module_id,
        sequence_no=module.sequence_no,
        title=module.title,
        concept_id=module.concept_id,
        style=ModuleStyle(module.style),
        is_review=False,
        render_status=RenderStatus(module.render_status),
        level=_level(module),
        completed=module.completed_at is not None,
    )


def lesson_out(db: Session, lesson: LessonRow) -> Lesson:
    return Lesson(
        id=lesson.lesson_id,
        title=lesson.title,
        query_text=lesson.query_text,
        status=LessonStatus(lesson.status),
        mode=lesson.mode,
        started_at=lesson.started_at,
        modules=[_module_out(m) for m in _modules(db, lesson)],
        position=Position(**lesson.position) if lesson.position else None,
    )


def lessons_of(db: Session, user: UserRecord) -> list[LessonSummary]:
    student = db.scalar(select(Student).where(Student.email == user.email))
    if student is None:
        return []
    summaries = []
    lessons = db.scalars(select(LessonRow).where(LessonRow.student_id == student.student_id))
    for lesson in lessons:
        modules = _modules(db, lesson)
        summaries.append(
            LessonSummary(
                id=lesson.lesson_id,
                title=lesson.title,
                query_text=lesson.query_text,
                status=LessonStatus(lesson.status),
                started_at=lesson.started_at,
                modules_total=len(modules),
                modules_completed=sum(m.completed_at is not None for m in modules),
            )
        )
    return summaries


def current_module(db: Session, lesson: LessonRow, media_dir: Path) -> CurrentModule:
    module = next((m for m in _modules(db, lesson) if m.completed_at is None), None)
    if module is None:
        lesson.status = LessonStatus.COMPLETED.value
        return CurrentModule(status="complete", module=None, level=None, cache_key=None)
    summary = _module_out(module)
    if module.render_status == RenderStatus.FAILED.value:
        error = db.scalar(
            select(RenderJob.error)
            .where(RenderJob.cache_key == module.cache_key)
            .order_by(RenderJob.job_id.desc())
            .limit(1)
        )
        failure = ModuleFailure(
            fallback=None,
            message="This part of the lesson could not be prepared."
            + (f" ({error})" if error else ""),
            definition=None,
        )
        return CurrentModule(
            status="failed", module=summary, level=None, cache_key=None, failure=failure
        )
    manifest = load_manifest(variant_directory(media_dir, module.cache_key or "none"))
    if manifest is not None and any(beat.index == 0 for beat in manifest.beats):
        return CurrentModule(
            status="ready", module=summary, level=manifest.level, cache_key=manifest.cache_key
        )
    return CurrentModule(
        status="preparing", module=summary, level=None, cache_key=None, stage="rendering"
    )


def save_position(db: Session, lesson: LessonRow, position: Position) -> None:
    module = db.get(ModuleRow, position.module_id)
    if module is None or module.lesson_id != lesson.lesson_id:
        raise HTTPException(status_code=404, detail="No such module in this lesson")
    beats = len(ModuleRenderRequest.model_validate(_request(module)).beats)
    if position.beat_index >= beats:
        raise HTTPException(status_code=422, detail="beat_index is past the module's last beat")
    lesson.position = position.model_dump(mode="json")


def _request(module: ModuleRow) -> dict:
    return module.render_requests[str(int(_level(module)))]


# ------------------------------------------------------------------ between modules


def finish_module(db: Session, lesson: LessonRow, module_id: int) -> ModuleEnd:
    current = next((m for m in _modules(db, lesson) if m.completed_at is None), None)
    if current is None or current.module_id != module_id:
        raise HTTPException(status_code=409, detail="Only the module being played can be finished.")
    current.completed_at = datetime.now(UTC)
    if lesson.position and lesson.position.get("module_id") == module_id:
        lesson.position = None
    if all(m.completed_at is not None for m in _modules(db, lesson)):
        lesson.status = LessonStatus.COMPLETED.value
    if current.render_status == RenderStatus.FAILED.value or not current.scene_plan:
        return ModuleEnd(check_items=[], branch=None)
    plan = ScenePlan.model_validate(current.scene_plan)
    items = [_check_item(q) for i in plan.check_items if (q := db.get(CheckQuestion, i))]
    # Branch points arrive with branch insertion in Phase 6.
    return ModuleEnd(check_items=items[:2], branch=None)


def _check_item(question: CheckQuestion) -> CheckItem:
    return CheckItem(
        id=question.check_id,
        concept_id=question.concept_id,
        item_type=question.item_type,
        question_text=question.question_text,
        options=question.options or [question.correct_option],
    )


def answer_check(db: Session, user: UserRecord, body: CheckResponseRequest) -> CheckResponseResult:
    module = db.get(ModuleRow, body.module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="No such module")
    find_lesson(db, user, module.lesson_id)
    plan = ScenePlan.model_validate(module.scene_plan) if module.scene_plan else None
    if plan is None or body.check_id not in plan.check_items:
        raise HTTPException(status_code=422, detail="That item is not asked after this module.")
    question = db.get(CheckQuestion, body.check_id)
    if question is None:
        raise HTTPException(status_code=404, detail="No such check item")
    if question.options and body.selected_option not in question.options:
        raise HTTPException(status_code=422, detail="That is not one of the options.")
    correct = body.selected_option == question.correct_option
    db.add(
        CheckResponse(
            check_id=question.check_id,
            module_id=module.module_id,
            student_id=student_for(db, user).student_id,
            selected_option=body.selected_option,
            is_correct=correct,
        )
    )
    # The learner model applies the answer to the concept's estimate in Phase 5 (Eqs. 5.1, 5.2).
    return CheckResponseResult(is_correct=correct, correct_option=question.correct_option)


# ------------------------------------------------------------------ events


def log_events(db: Session, user: UserRecord, batch: InteractionEventBatch) -> None:
    """Store the player's events as INTERACTION_EVENT rows (§5.6.1)."""
    student = student_for(db, user)
    for event in batch.events:
        if event.type in (InteractionType.IM_LOST, InteractionType.BRANCH_CHOICE):
            raise HTTPException(
                status_code=422,
                detail=f"Don't send {event.type.value} events here; its own endpoint records it.",
            )
        module = db.get(ModuleRow, event.module_id)
        if module is None:
            raise HTTPException(
                status_code=404, detail=f"Module {event.module_id} is not in your lessons"
            )
        find_lesson(db, user, module.lesson_id)
        payload = event.model_dump(
            mode="json",
            exclude={"type", "module_id", "occurred_at", "beat_index", "position_s"},
        )
        db.add(
            InteractionEventRow(
                module_id=event.module_id,
                student_id=student.student_id,
                event_type=event.type.value,
                occurred_at=event.occurred_at,
                beat_index=getattr(event, "beat_index", None),
                position_s=getattr(event, "position_s", None),
                payload=payload or None,
            )
        )


# ------------------------------------------------------------------ the event stream


def latest_event_id(db: Session, lesson_id: int) -> int:
    return db.scalar(
        select(func.coalesce(func.max(StreamEventRecord.event_id), 0)).where(
            StreamEventRecord.lesson_id == lesson_id
        )
    )


def events_after(db: Session, lesson_id: int, after_id: int) -> list[tuple[int, dict]]:
    rows = db.execute(
        select(StreamEventRecord.event_id, StreamEventRecord.payload)
        .where(StreamEventRecord.lesson_id == lesson_id, StreamEventRecord.event_id > after_id)
        .order_by(StreamEventRecord.event_id)
    )
    return [(event_id, payload) for event_id, payload in rows]
