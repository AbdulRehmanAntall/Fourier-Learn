"""The stub behind the API during Phase 2 (docs/frontend.md §8).

An in-memory store that answers every endpoint with realistic behaviour, so the frontend can be
built before the planner, render queue and learner model exist:

- Lessons play the committed fixture variants of the example module at all three levels.
- Generation, prefetching and "I'm Lost" re-rendering are simulated on a clock, and announced on
  each lesson's event stream as the real pipeline will announce them.
- Checks, the diagnostic and "I'm Lost" nudge the stub's confidence scores, so the progress
  screen changes. These numbers are not BKT; Phase 5 brings the learner model.

Everything is lost when the server restarts. Each method returns the API schema of its endpoint,
so replacing the stub later does not change the routes.
"""

import hashlib
import re
import secrets
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

from app.api.schemas.admin import (
    AdminSummary,
    CheckQuestion,
    CheckQuestionCreate,
    CheckQuestionFields,
    CheckQuestionPage,
    CheckQuestionPatch,
    GlossaryCreate,
    GlossaryEntry,
    GlossaryPage,
    GlossaryPatch,
    PrimitiveAdmin,
    PrimitivePatch,
    RenderJob,
    RenderJobDetail,
    RenderJobPage,
    StudentAdmin,
    StudentPage,
)
from app.api.schemas.auth import User
from app.api.schemas.common import CheckItem, Concept, TopicArea
from app.api.schemas.events import LoggedEvent
from app.api.schemas.learner import (
    ConceptConfidence,
    DiagnosticState,
    GlossaryDefinition,
    Progress,
)
from app.api.schemas.lessons import (
    BranchOptionOut,
    BranchPoint,
    BranchRequest,
    CheckResponseRequest,
    CheckResponseResult,
    CreateLessonResponse,
    CurrentModule,
    GenerationStage,
    ImLostReplay,
    ImLostRequest,
    ImLostResult,
    ImLostSubstitute,
    Lesson,
    LessonCreated,
    LessonMode,
    LessonSummary,
    ModuleEnd,
    ModuleFailure,
    ModuleSummary,
    OutOfScope,
    Position,
)
from app.contracts import (
    BeatReady,
    BranchChoiceEvent,
    GenerationProgress,
    ImLostEvent,
    InteractionEventBatch,
    InteractionType,
    LessonStatus,
    Level,
    ModuleFailed,
    ModuleReady,
    ModuleStyle,
    RenderStatus,
)
from app.contracts.stream import StreamEvent
from app.stub import seed
from app.stub.fixtures import FixtureVariant

BRANCH_TIMEOUT_S = 20
MAX_LOGGED_EVENTS = 1000

# Seconds from the start of generation. The first module goes through every stage; later
# modules are prefetched while the student watches (§5.5), so the student rarely waits.
FIRST_MODULE = {"stages": [0, 2, 4, 6], "beats": [7, 8, 9]}
SLOW_FIRST_MODULE = {"stages": [0, 15, 30, 45], "beats": [58, 59, 60]}
PREFETCH_BEATS = [8, 9, 10]
INSERTED_BEATS = [6, 7, 8]
IM_LOST_DELAY_S = 5
FAILURE_MESSAGE = "This part of the lesson couldn't be prepared, so here is the definition instead."
STAGES: list[GenerationStage] = ["planning", "parameters", "narration", "rendering"]

# The three modules of a stub lesson: (title, concept, level, check items, offers a branch).
STANDARD_MODULES = [
    ("What a gradient is", 12, Level.STANDARD, [1, 2], True),
    ("Rise over run", 12, Level.CONCISE, [3, 4], False),
    ("Gradient in y = mx + c", 13, Level.STANDARD, [6], False),
]
RECOGNISED = re.compile(r"gradient|slope|\blines?\b|straight|test:")


def _hash(password: str, salt: bytes) -> bytes:
    # Stub only. The real accounts (Phase 5) use argon2 or bcrypt.
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 1000)


@dataclass
class UserRecord:
    id: int
    name: str
    email: str
    role: str
    created_at: datetime
    salt: bytes
    password_hash: bytes
    disabled: bool = False
    last_active_at: datetime | None = None
    diagnostic_answers: dict[int, str] = field(default_factory=dict)
    scores: dict[int, tuple[float, datetime]] = field(default_factory=dict)
    extra_lessons: int = 0
    """Lessons the admin pages count for sample students, who have no real lessons."""

    def check_password(self, password: str) -> bool:
        return secrets.compare_digest(_hash(password, self.salt), self.password_hash)


@dataclass
class ModuleRecord:
    id: int
    title: str
    concept_id: int
    style: ModuleStyle
    level: Level
    check_ids: list[int]
    is_review: bool = False
    offers_branch: bool = False
    branch_resolved: bool = False
    completed: bool = False
    started: bool = False
    will_fail: bool = False
    worked_example_added: bool = False
    scheduled_at: float | None = None
    beat_times: list[float] | None = None
    """Clock time at which each beat of the current level is ready."""
    fail_at: float | None = None


@dataclass
class LessonRecord:
    id: int
    student_id: int
    title: str
    query_text: str
    mode: LessonMode
    started_at: datetime
    modules: list[ModuleRecord]
    status: LessonStatus = LessonStatus.IN_PROGRESS
    position: Position | None = None
    stream: list[tuple[float, StreamEvent]] = field(default_factory=list)
    stage_times: list[tuple[float, GenerationStage]] = field(default_factory=list)
    answered: dict[tuple[int, int], bool] = field(default_factory=dict)
    """(module id, check id) → whether the answer was correct."""

    def current(self) -> ModuleRecord | None:
        return next((m for m in self.modules if not m.completed), None)

    def module(self, module_id: int) -> ModuleRecord:
        for module in self.modules:
            if module.id == module_id:
                return module
        raise HTTPException(status_code=404, detail="No such module in this lesson")


@dataclass
class RenderJobRecord:
    job: RenderJob
    log: str


class StubStore:
    def __init__(
        self,
        variants: dict[Level, FixtureVariant],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.variants = variants
        self.clock = clock
        self.concepts = {c.id: c for c in seed.CONCEPTS}
        self.items = {
            i.id: CheckQuestion(
                id=i.id,
                concept_id=i.concept_id,
                item_type=i.item_type,
                question_text=i.question_text,
                options=list(i.options),
                correct_option=i.correct_option,
            )
            for i in seed.ITEMS
        }
        self.glossary = {
            g[0]: GlossaryEntry(id=g[0], concept_id=g[1], term=g[2], definition=g[3])
            for g in seed.GLOSSARY
        }
        self.primitives = {
            p[0]: PrimitiveAdmin(
                id=p[0], topic=p[1], version=p[2], status="enabled", description=p[3]
            )
            for p in seed.PRIMITIVES
        }
        self.users: dict[int, UserRecord] = {}
        self.sessions: dict[str, int] = {}
        self.lessons: dict[int, LessonRecord] = {}
        self.render_jobs: dict[int, RenderJobRecord] = {}
        self.events: list[LoggedEvent] = []
        self._ids: dict[str, int] = {}
        self._seed()

    # ---------------------------------------------------------------- helpers

    def now(self) -> float:
        return self.clock()

    @staticmethod
    def wall() -> datetime:
        return datetime.now(UTC)

    def _next_id(self, kind: str, start: int = 1) -> int:
        self._ids[kind] = max(self._ids.get(kind, start - 1) + 1, start)
        return self._ids[kind]

    def _concept(self, concept_id: int) -> Concept:
        c = self.concepts[concept_id]
        return Concept(id=c.id, name=c.name, syllabus_code=c.syllabus_code, topic_area=c.topic_area)

    def _beat_count(self, level: Level) -> int:
        return self.variants[level].beat_count

    def _check_item(self, item_id: int) -> CheckItem | None:
        item = self.items.get(item_id)
        if item is None:
            return None
        return CheckItem(
            id=item.id,
            concept_id=item.concept_id,
            item_type=item.item_type,
            question_text=item.question_text,
            options=item.options,
        )

    def _nudge(self, user: UserRecord, concept_id: int, delta: float) -> None:
        score, _ = user.scores.get(concept_id, (seed.DEFAULT_PRIOR, None))
        user.scores[concept_id] = (min(0.98, max(0.02, score + delta)), self.wall())

    # ---------------------------------------------------------------- seed

    def _add_user(self, email: str, name: str, role: str, created_at: datetime) -> UserRecord:
        salt = secrets.token_bytes(16)
        user = UserRecord(
            id=self._next_id("user"),
            name=name,
            email=email,
            role=role,
            created_at=created_at,
            salt=salt,
            password_hash=_hash(seed.STUB_PASSWORD, salt),
        )
        self.users[user.id] = user
        return user

    def _seed(self) -> None:
        now, wall = self.now(), self.wall()
        accounts = {}
        for email, name, role in seed.ACCOUNTS:
            accounts[email] = self._add_user(email, name, role, wall - timedelta(days=60))

        student = accounts["student@fourierlearn.test"]
        student.diagnostic_answers = {
            i: self.items[i].correct_option for i in seed.DIAGNOSTIC_ITEMS
        }
        for offset, concept in enumerate(seed.CONCEPTS):
            area = seed.SEEDED_AREA_SCORES[concept.topic_area]
            score = round(area + (0.04 if offset % 2 else -0.04), 2)
            student.scores[concept.id] = (score, wall - timedelta(days=1))
        student.last_active_at = wall - timedelta(hours=20)

        for name, days, lessons, disabled in seed.SAMPLE_STUDENTS:
            email = name.lower().replace(" ", ".") + "@fourierlearn.test"
            user = self._add_user(email, name, "student", wall - timedelta(days=days))
            user.extra_lessons = lessons
            user.disabled = disabled
            user.diagnostic_answers = {i: "" for i in seed.DIAGNOSTIC_ITEMS}
            if lessons:
                user.last_active_at = wall - timedelta(hours=days * 5)

        # The seeded student's lessons: one in progress, one completed, one in study mode.
        in_progress = self._new_lesson(
            student, "explain the gradient of a straight line", "adaptive", wall - timedelta(days=1)
        )
        completed = self._new_lesson(
            student, "how do I find the slope of a line", "adaptive", wall - timedelta(days=3)
        )
        static = self._new_lesson(
            student, "gradient of a line (study mode)", "static", wall - timedelta(hours=2)
        )
        for lesson in (in_progress, completed, static):
            for module in lesson.modules:
                # Rendered long ago: every beat is ready.
                module.scheduled_at = now - 600
                module.beat_times = [now - 590] * self._beat_count(module.level)
                module.started = lesson is not static
        in_progress.modules[0].completed = True
        in_progress.modules[0].branch_resolved = True
        in_progress.position = Position(
            module_id=in_progress.modules[1].id, beat_index=1, position_s=2.0
        )
        for module in completed.modules:
            module.completed = module.branch_resolved = True
        completed.status = LessonStatus.COMPLETED

        self._seed_render_jobs(wall)

    def _seed_render_jobs(self, wall: datetime) -> None:
        lesson_ids = sorted(self.lessons)
        for n in range(14):
            created = wall - timedelta(hours=n * 9 + 1)
            failed = n in (2, 7, 11)
            queued = n == 0
            module_ids = [m.id for lesson in self.lessons.values() for m in lesson.modules]
            error = seed.RENDER_ERRORS[n % len(seed.RENDER_ERRORS)] if failed else None
            duration = None if queued else round(18.5 + (n * 7.3) % 30, 1)
            job = RenderJob(
                id=self._next_id("job"),
                lesson_id=lesson_ids[n % len(lesson_ids)],
                module_id=module_ids[n % len(module_ids)],
                level=Level(n % 3 + 1),
                priority=2 if n % 4 == 3 else 1,
                status="queued" if queued else "failed" if failed else "ready",
                attempts=3 if failed else 0 if queued else 1,
                created_at=created,
                finished_at=None if queued else created + timedelta(seconds=duration or 0),
                duration_s=duration,
                error=error,
            )
            lines = [f"job {job.id}: level {int(job.level)}, priority {job.priority}"]
            if not queued:
                attempts = job.attempts if failed else 1
                for attempt in range(1, attempts + 1):
                    lines.append(f"attempt {attempt}: rendering 3 beats")
                    lines.append(f"attempt {attempt}: {error}" if failed else "beats 0-2 ready")
            self.render_jobs[job.id] = RenderJobRecord(job=job, log="\n".join(lines))

    # ---------------------------------------------------------------- auth

    def create_session(self, user: UserRecord) -> str:
        token = secrets.token_urlsafe(32)
        self.sessions[token] = user.id
        user.last_active_at = self.wall()
        return token

    def user_for_session(self, token: str | None) -> UserRecord | None:
        user = self.users.get(self.sessions.get(token or "", 0))
        if user is None or user.disabled:
            return None
        return user

    def end_session(self, token: str | None) -> None:
        self.sessions.pop(token or "", None)

    def user_out(self, user: UserRecord) -> User:
        return User(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            diagnostic_complete=user.role == "admin"
            or len(user.diagnostic_answers) >= len(seed.DIAGNOSTIC_ITEMS),
            created_at=user.created_at,
        )

    def _by_email(self, email: str) -> UserRecord | None:
        return next((u for u in self.users.values() if u.email == email.lower()), None)

    def register(self, name: str, email: str, password: str) -> UserRecord:
        if self._by_email(email):
            raise HTTPException(
                status_code=409, detail="An account with this email already exists."
            )
        user = self._add_user(email.lower(), name, "student", self.wall())
        user.salt = secrets.token_bytes(16)
        user.password_hash = _hash(password, user.salt)
        return user

    def login(self, email: str, password: str) -> UserRecord:
        user = self._by_email(email)
        if user is None or not user.check_password(password):
            raise HTTPException(status_code=401, detail="Incorrect email or password.")
        if user.disabled:
            raise HTTPException(status_code=403, detail="This account has been disabled.")
        return user

    # ---------------------------------------------------------------- topics and glossary

    def topics(self) -> list[TopicArea]:
        return [
            TopicArea(
                topic_area=area,
                concepts=[self._concept(c.id) for c in seed.CONCEPTS if c.topic_area == area],
            )
            for area in seed.TOPIC_AREAS
        ]

    def definition(self, term: str) -> GlossaryDefinition:
        for entry in self.glossary.values():
            if entry.term.lower() == term.strip().lower():
                return GlossaryDefinition(
                    term=entry.term, definition=entry.definition, concept_id=entry.concept_id
                )
        raise HTTPException(status_code=404, detail="No such glossary term")

    def _concept_definition(self, concept_id: int) -> str:
        entry = next((g for g in self.glossary.values() if g.concept_id == concept_id), None)
        return entry.definition if entry else self.concepts[concept_id].name

    # ---------------------------------------------------------------- diagnostic and progress

    def diagnostic(self, user: UserRecord) -> DiagnosticState:
        answered = [i for i in seed.DIAGNOSTIC_ITEMS if i in user.diagnostic_answers]
        pending = [i for i in seed.DIAGNOSTIC_ITEMS if i not in user.diagnostic_answers]
        return DiagnosticState(
            complete=not pending,
            total=len(seed.DIAGNOSTIC_ITEMS),
            answered=len(answered),
            item=self._check_item(pending[0]) if pending else None,
        )

    def answer_diagnostic(self, user: UserRecord, check_id: int, selected: str) -> DiagnosticState:
        state = self.diagnostic(user)
        if state.item is None:
            raise HTTPException(status_code=409, detail="The diagnostic is already complete.")
        if check_id != state.item.id:
            raise HTTPException(status_code=409, detail="Answer the current question first.")
        item = self.items[check_id]
        if selected not in item.options:
            raise HTTPException(status_code=422, detail="That is not one of the options.")
        user.diagnostic_answers[check_id] = selected
        # No learning transition: no instruction has happened yet (§5.7.2).
        score = 0.6 if selected == item.correct_option else 0.2
        user.scores[item.concept_id] = (score, self.wall())
        return self.diagnostic(user)

    def progress(self, user: UserRecord) -> Progress:
        concepts = []
        for c in seed.CONCEPTS:
            score, updated = user.scores.get(c.id, (seed.DEFAULT_PRIOR, None))
            concepts.append(
                ConceptConfidence(
                    concept_id=c.id,
                    name=c.name,
                    topic_area=c.topic_area,
                    syllabus_code=c.syllabus_code,
                    score=score,
                    updated_at=updated,
                )
            )
        return Progress(concepts=concepts)

    # ---------------------------------------------------------------- lessons

    def _new_lesson(
        self, user: UserRecord, query: str, mode: LessonMode, started_at: datetime
    ) -> LessonRecord:
        modules = [
            ModuleRecord(
                id=self._next_id("module"),
                title=title,
                concept_id=concept,
                style=ModuleStyle.DEFAULT,
                level=Level.STANDARD if mode == "static" else level,
                check_ids=checks,
                offers_branch=offers_branch and mode == "adaptive",
            )
            for title, concept, level, checks, offers_branch in STANDARD_MODULES
        ]
        title = "Gradient of a straight line" + (" (study mode)" if mode == "static" else "")
        lesson = LessonRecord(
            id=self._next_id("lesson"),
            student_id=user.id,
            title=title,
            query_text=query,
            mode=mode,
            started_at=started_at,
            modules=modules,
        )
        self.lessons[lesson.id] = lesson
        return lesson

    def _lesson(self, user: UserRecord, lesson_id: int) -> LessonRecord:
        lesson = self.lessons.get(lesson_id)
        if lesson is None or lesson.student_id != user.id:
            raise HTTPException(status_code=404, detail="No such lesson")
        return lesson

    def _lesson_of_module(self, user: UserRecord, module_id: int) -> LessonRecord:
        for lesson in self.lessons.values():
            if lesson.student_id == user.id and any(m.id == module_id for m in lesson.modules):
                return lesson
        raise HTTPException(status_code=404, detail=f"Module {module_id} is not in your lessons")

    def create_lesson(self, user: UserRecord, query: str) -> CreateLessonResponse:
        q = query.lower()
        if not RECOGNISED.search(q):
            words = set(re.findall(r"[a-z]+", q))
            ranked = sorted(
                seed.CONCEPTS,
                key=lambda c: -len(words & set(re.findall(r"[a-z]+", c.name.lower()))),
            )
            nearest = [c.id for c in ranked[:2]] if words & _concept_words() else [30, 12]
            return OutOfScope(
                message="FourierLearn doesn't cover that topic yet. These are the topics it "
                "teaches.",
                nearest_concepts=[self._concept(i) for i in nearest],
                topics=self.topics(),
            )
        mode: LessonMode = "static" if "test:static" in q else "adaptive"
        lesson = self._new_lesson(user, query.strip(), mode, self.wall())
        if "test:fail" in q:
            lesson.modules[1].will_fail = True
        timing = SLOW_FIRST_MODULE if "test:slow" in q else FIRST_MODULE
        start = self.now()
        lesson.stage_times = [(start + t, s) for t, s in zip(timing["stages"], STAGES, strict=True)]
        for at, stage in lesson.stage_times:
            event = GenerationProgress(
                lesson_id=lesson.id, module_id=lesson.modules[0].id, stage=stage
            )
            lesson.stream.append((at, event))
        self._schedule(lesson, lesson.modules[0], start, timing["beats"])
        user.last_active_at = self.wall()
        return LessonCreated(lesson_id=lesson.id)

    def _schedule(
        self, lesson: LessonRecord, module: ModuleRecord, start: float, offsets: list[float]
    ) -> None:
        """Simulate rendering `module` at its level, announcing each step on the stream."""
        variant = self.variants[module.level]
        module.scheduled_at = start
        if module.will_fail:
            module.fail_at = start + offsets[-1]
            failed = ModuleFailed(
                lesson_id=lesson.id,
                module_id=module.id,
                level=module.level,
                fallback="glossary_definition",
                message=FAILURE_MESSAGE,
            )
            lesson.stream.append((module.fail_at, failed))
            return
        # One beat per offset; any beats beyond the offsets follow a second apart.
        last = len(offsets) - 1
        module.beat_times = [
            start + offsets[min(i, last)] + max(0, i - last) for i in range(variant.beat_count)
        ]
        self._announce(lesson, module, range(variant.beat_count))

    def _announce(self, lesson: LessonRecord, module: ModuleRecord, beats: range) -> None:
        variant = self.variants[module.level]
        assert module.beat_times is not None
        for i in beats:
            ready = BeatReady(
                lesson_id=lesson.id,
                module_id=module.id,
                level=module.level,
                beat_index=i,
                cache_key=variant.cache_key,
            )
            lesson.stream.append((module.beat_times[i], ready))
        done = ModuleReady(
            lesson_id=lesson.id,
            module_id=module.id,
            level=module.level,
            cache_key=variant.cache_key,
        )
        lesson.stream.append((module.beat_times[-1], done))
        lesson.stream.sort(key=lambda entry: entry[0])

    def _render_status(self, module: ModuleRecord, now: float) -> RenderStatus:
        if module.fail_at is not None and now >= module.fail_at:
            return RenderStatus.FAILED
        if module.scheduled_at is None or now < module.scheduled_at:
            return RenderStatus.QUEUED
        if module.beat_times and now >= module.beat_times[-1]:
            return RenderStatus.READY
        return RenderStatus.RENDERING

    def _module_out(self, lesson: LessonRecord, module: ModuleRecord, now: float) -> ModuleSummary:
        return ModuleSummary(
            id=module.id,
            sequence_no=lesson.modules.index(module) + 1,
            title=module.title,
            concept_id=module.concept_id,
            style=module.style,
            is_review=module.is_review,
            render_status=self._render_status(module, now),
            level=module.level,
            completed=module.completed,
        )

    def lesson_out(self, user: UserRecord, lesson_id: int) -> Lesson:
        lesson = self._lesson(user, lesson_id)
        now = self.now()
        return Lesson(
            id=lesson.id,
            title=lesson.title,
            query_text=lesson.query_text,
            status=lesson.status,
            mode=lesson.mode,
            started_at=lesson.started_at,
            modules=[self._module_out(lesson, m, now) for m in lesson.modules],
            position=lesson.position,
        )

    def lessons_of(self, user: UserRecord) -> list[LessonSummary]:
        mine = [lesson for lesson in self.lessons.values() if lesson.student_id == user.id]
        return [
            LessonSummary(
                id=lesson.id,
                title=lesson.title,
                query_text=lesson.query_text,
                status=lesson.status,
                started_at=lesson.started_at,
                modules_total=len(lesson.modules),
                modules_completed=sum(m.completed for m in lesson.modules),
            )
            for lesson in sorted(mine, key=lambda lesson: lesson.started_at, reverse=True)
        ]

    def current_module(self, user: UserRecord, lesson_id: int) -> CurrentModule:
        lesson = self._lesson(user, lesson_id)
        now = self.now()
        module = lesson.current()
        if module is None:
            lesson.status = LessonStatus.COMPLETED
            return CurrentModule(status="complete", module=None, level=None, cache_key=None)
        summary = self._module_out(lesson, module, now)
        if module.will_fail:
            if module.fail_at is None:
                self._schedule(lesson, module, now, PREFETCH_BEATS)
            assert module.fail_at is not None
            if now >= module.fail_at:
                self._prefetch_after(lesson, module, now)
                failure = ModuleFailure(
                    fallback="glossary_definition",
                    message=FAILURE_MESSAGE,
                    definition=self._concept_definition(module.concept_id),
                )
                return CurrentModule(
                    status="failed", module=summary, level=None, cache_key=None, failure=failure
                )
            return CurrentModule(
                status="preparing", module=summary, level=None, cache_key=None, stage="rendering"
            )
        if module.beat_times is None:
            self._schedule(lesson, module, now, PREFETCH_BEATS)
            summary = self._module_out(lesson, module, now)
        assert module.beat_times is not None
        if now >= module.beat_times[0]:
            if not module.started:
                module.started = True
                self._prefetch_after(lesson, module, now)
            return CurrentModule(
                status="ready",
                module=summary,
                level=module.level,
                cache_key=self.variants[module.level].cache_key,
            )
        # Only the first module goes through every stage; later ones are already rendering.
        reached = [s for at, s in lesson.stage_times if at <= now]
        stage = reached[-1] if module is lesson.modules[0] and reached else "rendering"
        return CurrentModule(
            status="preparing", module=summary, level=None, cache_key=None, stage=stage
        )

    def _prefetch_after(self, lesson: LessonRecord, module: ModuleRecord, now: float) -> None:
        index = lesson.modules.index(module)
        if index + 1 < len(lesson.modules):
            following = lesson.modules[index + 1]
            if following.scheduled_at is None:
                self._schedule(lesson, following, now, PREFETCH_BEATS)

    def save_position(self, user: UserRecord, lesson_id: int, position: Position) -> None:
        lesson = self._lesson(user, lesson_id)
        module = lesson.module(position.module_id)
        if position.beat_index >= self._beat_count(module.level):
            raise HTTPException(status_code=422, detail="beat_index is past the module's last beat")
        lesson.position = position
        user.last_active_at = self.wall()

    def stream_events(self, lesson_id: int, after: float, until: float) -> Iterator[StreamEvent]:
        lesson = self.lessons.get(lesson_id)
        for at, event in lesson.stream if lesson else []:
            if after < at <= until:
                yield event

    # ---------------------------------------------------------------- between modules

    def finish_module(self, user: UserRecord, lesson_id: int, module_id: int) -> ModuleEnd:
        lesson = self._lesson(user, lesson_id)
        module = lesson.module(module_id)
        if module is not lesson.current():
            raise HTTPException(
                status_code=409, detail="Only the module being played can be finished."
            )
        module.completed = True
        if lesson.position and lesson.position.module_id == module.id:
            lesson.position = None
        if lesson.current() is None:
            lesson.status = LessonStatus.COMPLETED
        if lesson.mode == "static" or module.will_fail:
            return ModuleEnd(check_items=[], branch=None)
        # The learning transition when a module ends (Eq. 5.3), in miniature.
        self._nudge(user, module.concept_id, 0.03)
        items = [item for i in module.check_ids if (item := self._check_item(i))]
        branch = None
        if module.offers_branch and not module.branch_resolved:
            following = lesson.current()
            next_title = following.title if following else "the end of the lesson"
            branch = BranchPoint(
                options=[
                    BranchOptionOut(
                        choice="theory",
                        title="Explain the theory further",
                        description="Why a straight line has the same gradient everywhere",
                    ),
                    BranchOptionOut(
                        choice="worked_example",
                        title="Show me a worked example",
                        description="An exam-style question solved step by step",
                    ),
                    BranchOptionOut(
                        choice="next_step",
                        title="Continue to the next step",
                        description=f"Move on to: {next_title}",
                    ),
                ],
                timeout_s=BRANCH_TIMEOUT_S,
            )
        return ModuleEnd(check_items=items, branch=branch)

    def answer_check(self, user: UserRecord, request: CheckResponseRequest) -> CheckResponseResult:
        lesson = self._lesson_of_module(user, request.module_id)
        module = lesson.module(request.module_id)
        if request.check_id not in module.check_ids:
            raise HTTPException(status_code=422, detail="That item is not asked after this module.")
        item = self.items.get(request.check_id)
        if item is None:
            raise HTTPException(status_code=404, detail="No such check item")
        if request.selected_option not in item.options:
            raise HTTPException(status_code=422, detail="That is not one of the options.")
        correct = request.selected_option == item.correct_option
        key = (module.id, item.id)
        if key not in lesson.answered:
            lesson.answered[key] = correct
            self._nudge(user, item.concept_id, 0.06 if correct else -0.08)
        return CheckResponseResult(is_correct=correct, correct_option=item.correct_option)

    def _unused_item(self, lesson: LessonRecord, concept_ids: tuple[int, ...]) -> list[int]:
        used = {i for m in lesson.modules for i in m.check_ids}
        for item in self.items.values():
            if item.concept_id in concept_ids and item.id not in used:
                return [item.id]
        return []

    def _insert_after(
        self, lesson: LessonRecord, parent: ModuleRecord, style: ModuleStyle, level: Level
    ) -> ModuleRecord:
        title = {
            ModuleStyle.THEORY: "Why a line's gradient is the same everywhere",
            ModuleStyle.WORKED_EXAMPLE: "Worked example: finding a gradient",
        }[style]
        module = ModuleRecord(
            id=self._next_id("module"),
            title=title,
            concept_id=parent.concept_id,
            style=style,
            level=level,
            check_ids=self._unused_item(lesson, (parent.concept_id, 13)),
        )
        lesson.modules.insert(lesson.modules.index(parent) + 1, module)
        self._schedule(lesson, module, self.now(), INSERTED_BEATS)
        return module

    def choose_branch(self, user: UserRecord, lesson_id: int, request: BranchRequest) -> Lesson:
        lesson = self._lesson(user, lesson_id)
        module = lesson.module(request.module_id)
        if not module.offers_branch or not module.completed or module.branch_resolved:
            raise HTTPException(status_code=409, detail="There is no open branch point here.")
        module.branch_resolved = True
        option = request.choice if request.choice == "next_step" else ModuleStyle(request.choice)
        self._log(
            user, BranchChoiceEvent(module_id=module.id, occurred_at=self.wall(), option=option)
        )
        if request.choice != "next_step":
            self._insert_after(lesson, module, ModuleStyle(request.choice), module.level)
        return self.lesson_out(user, lesson_id)

    def im_lost(self, user: UserRecord, lesson_id: int, request: ImLostRequest) -> ImLostResult:
        lesson = self._lesson(user, lesson_id)
        module = lesson.module(request.module_id)
        if lesson.mode == "static":
            raise HTTPException(status_code=409, detail='Study mode has no "I\'m Lost" control.')
        if module is not lesson.current() or not module.started:
            raise HTTPException(status_code=409, detail="That module is not playing.")
        if request.beat_index >= self._beat_count(module.level):
            raise HTTPException(status_code=422, detail="beat_index is past the module's last beat")
        self._log(
            user,
            ImLostEvent(
                module_id=module.id,
                occurred_at=self.wall(),
                beat_index=request.beat_index,
                position_s=request.position_s,
            ),
        )
        # Strong evidence of non-mastery for the beat's concepts (Table 5.4).
        self._nudge(user, module.concept_id, -0.12)
        lower = module.level.lower()
        if lower is None:
            added = not module.worked_example_added
            if added:
                module.worked_example_added = True
                self._insert_after(lesson, module, ModuleStyle.WORKED_EXAMPLE, Level.SUPPORTED)
            return ImLostReplay(resume_beat_index=request.beat_index, worked_example_added=added)
        # Re-render beats j onward at the level below (§5.6.3); earlier beats are not needed.
        module.level = lower
        now = self.now()
        count = self._beat_count(lower)
        module.beat_times = [
            now if i < request.beat_index else now + IM_LOST_DELAY_S + i - request.beat_index
            for i in range(count)
        ]
        self._announce(lesson, module, range(request.beat_index, count))
        return ImLostSubstitute(
            level=lower,
            cache_key=self.variants[lower].cache_key,
            resume_beat_index=request.beat_index,
            ready=False,
        )

    # ---------------------------------------------------------------- interaction events

    def _log(self, user: UserRecord, event) -> None:
        self.events.append(LoggedEvent(student_id=user.id, received_at=self.wall(), event=event))
        del self.events[:-MAX_LOGGED_EVENTS]

    def log_events(self, user: UserRecord, batch: InteractionEventBatch) -> None:
        for event in batch.events:
            if event.type in (InteractionType.IM_LOST, InteractionType.BRANCH_CHOICE):
                raise HTTPException(
                    status_code=422,
                    detail=f"Don't send {event.type.value} events here; its own endpoint "
                    "records it.",
                )
            self._lesson_of_module(user, event.module_id)
        for event in batch.events:
            self._log(user, event)
        user.last_active_at = self.wall()

    def events_of(self, user: UserRecord, limit: int) -> list[LoggedEvent]:
        return [e for e in self.events if e.student_id == user.id][-limit:]

    # ---------------------------------------------------------------- admin

    def admin_summary(self) -> AdminSummary:
        wall = self.wall()
        jobs = [r.job for r in self.render_jobs.values()]
        week = [j for j in jobs if j.finished_at and j.created_at >= wall - timedelta(days=7)]
        return AdminSummary(
            students=sum(u.role == "student" for u in self.users.values()),
            lessons_today=sum(
                lesson.started_at.date() == wall.date() for lesson in self.lessons.values()
            ),
            renders_failed_24h=sum(
                j.status == "failed" and j.created_at >= wall - timedelta(days=1) for j in jobs
            ),
            render_success_rate_7d=round(sum(j.status == "ready" for j in week) / len(week), 3)
            if week
            else None,
        )

    def list_primitives(self) -> list[PrimitiveAdmin]:
        return list(self.primitives.values())

    def patch_primitive(self, primitive_id: str, patch: PrimitivePatch) -> PrimitiveAdmin:
        primitive = self.primitives.get(primitive_id)
        if primitive is None:
            raise HTTPException(status_code=404, detail="No such primitive")
        updated = primitive.model_copy(update=patch.model_dump(exclude_none=True))
        self.primitives[primitive_id] = updated
        return updated

    @staticmethod
    def _page(items: list, page: int, page_size: int) -> dict:
        start = (page - 1) * page_size
        return {
            "items": items[start : start + page_size],
            "total": len(items),
            "page": page,
            "page_size": page_size,
        }

    def _require_concept(self, concept_id: int | None) -> None:
        if concept_id is not None and concept_id not in self.concepts:
            raise HTTPException(status_code=422, detail=f"No concept with id {concept_id}")

    def list_glossary(
        self, search: str | None, concept_id: int | None, page: int, page_size: int
    ) -> GlossaryPage:
        entries = sorted(self.glossary.values(), key=lambda g: g.term.lower())
        if search:
            entries = [g for g in entries if search.lower() in g.term.lower()]
        if concept_id:
            entries = [g for g in entries if g.concept_id == concept_id]
        return GlossaryPage(**self._page(entries, page, page_size))

    def _check_term_free(self, term: str, own_id: int | None = None) -> None:
        for entry in self.glossary.values():
            if entry.term.lower() == term.lower() and entry.id != own_id:
                raise HTTPException(status_code=409, detail=f'The term "{term}" already exists.')

    def create_glossary(self, body: GlossaryCreate) -> GlossaryEntry:
        self._require_concept(body.concept_id)
        self._check_term_free(body.term)
        entry = GlossaryEntry(id=self._next_id("term", start=100), **body.model_dump())
        self.glossary[entry.id] = entry
        return entry

    def patch_glossary(self, term_id: int, patch: GlossaryPatch) -> GlossaryEntry:
        entry = self.glossary.get(term_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="No such glossary term")
        self._require_concept(patch.concept_id)
        if patch.term is not None:
            self._check_term_free(patch.term, own_id=term_id)
        updated = entry.model_copy(update=patch.model_dump(exclude_none=True))
        self.glossary[term_id] = updated
        return updated

    def delete_glossary(self, term_id: int) -> None:
        if self.glossary.pop(term_id, None) is None:
            raise HTTPException(status_code=404, detail="No such glossary term")

    def list_items(self, concept_id: int | None, page: int, page_size: int) -> CheckQuestionPage:
        items = sorted(self.items.values(), key=lambda i: i.id)
        if concept_id:
            items = [i for i in items if i.concept_id == concept_id]
        return CheckQuestionPage(**self._page(items, page, page_size))

    def create_item(self, body: CheckQuestionCreate) -> CheckQuestion:
        self._require_concept(body.concept_id)
        item = CheckQuestion(id=self._next_id("item", start=100), **body.model_dump())
        self.items[item.id] = item
        return item

    def patch_item(self, item_id: int, patch: CheckQuestionPatch) -> CheckQuestion:
        item = self.items.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="No such check question")
        self._require_concept(patch.concept_id)
        merged = item.model_dump() | patch.model_dump(exclude_none=True)
        merged.pop("id")
        try:
            CheckQuestionFields.model_validate(merged)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        updated = CheckQuestion(id=item_id, **merged)
        self.items[item_id] = updated
        return updated

    def delete_item(self, item_id: int) -> None:
        if self.items.pop(item_id, None) is None:
            raise HTTPException(status_code=404, detail="No such check question")

    def list_render_jobs(self, status: str | None, page: int, page_size: int) -> RenderJobPage:
        jobs = sorted(
            (r.job for r in self.render_jobs.values()), key=lambda j: j.created_at, reverse=True
        )
        if status:
            jobs = [j for j in jobs if j.status == status]
        return RenderJobPage(**self._page(jobs, page, page_size))

    def render_job(self, job_id: int) -> RenderJobDetail:
        record = self.render_jobs.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="No such render job")
        return RenderJobDetail(**record.job.model_dump(), log=record.log)

    def _student(self, student_id: int) -> UserRecord:
        user = self.users.get(student_id)
        if user is None or user.role != "student":
            raise HTTPException(status_code=404, detail="No such student")
        return user

    def student_out(self, user: UserRecord) -> StudentAdmin:
        lessons = sum(lesson.student_id == user.id for lesson in self.lessons.values())
        return StudentAdmin(
            id=user.id,
            name=user.name,
            email=user.email,
            created_at=user.created_at,
            last_active_at=user.last_active_at,
            lessons=lessons + user.extra_lessons,
            diagnostic_complete=self.user_out(user).diagnostic_complete,
            disabled=user.disabled,
        )

    def list_students(self, search: str | None, page: int, page_size: int) -> StudentPage:
        students = sorted(
            (u for u in self.users.values() if u.role == "student"),
            key=lambda u: u.created_at,
            reverse=True,
        )
        if search:
            needle = search.lower()
            students = [u for u in students if needle in u.name.lower() or needle in u.email]
        return StudentPage(**self._page([self.student_out(u) for u in students], page, page_size))

    def student(self, student_id: int) -> StudentAdmin:
        return self.student_out(self._student(student_id))

    def set_disabled(self, student_id: int, disabled: bool) -> StudentAdmin:
        user = self._student(student_id)
        user.disabled = disabled
        if disabled:
            self.sessions = {t: uid for t, uid in self.sessions.items() if uid != user.id}
        return self.student_out(user)

    def delete_student(self, student_id: int) -> None:
        user = self._student(student_id)
        del self.users[user.id]
        self.sessions = {t: uid for t, uid in self.sessions.items() if uid != user.id}
        self.lessons = {i: les for i, les in self.lessons.items() if les.student_id != user.id}
        self.events = [e for e in self.events if e.student_id != user.id]


def _concept_words() -> set[str]:
    return {w for c in seed.CONCEPTS for w in re.findall(r"[a-z]+", c.name.lower()) if len(w) > 3}
