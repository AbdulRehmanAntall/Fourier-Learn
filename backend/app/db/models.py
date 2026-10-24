"""Database tables: the entities and attributes of the data dictionary (report Table 4.8).

Each class maps to one entity of the ER diagram (Fig. 4.7) and the class diagram (Fig. 6.3).
Columns, types, lengths and nullability follow Table 4.8. Values that the table lists in words
are stored as the contract values in app/contracts (for example "Level 2", "worked_example").

Table 4.8 does not hold everything the design needs (docs/PLAN.md §13, gap 3). The additions
come after the data dictionary's own columns, and the extra tables after its entities; each
is marked "Addition" with the reason.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.contracts import InteractionType, LessonStatus, Level, ModuleStyle, RenderStatus
from app.db.base import Base


def _one_of(column: str, values) -> str:
    return f"{column} IN ({', '.join(repr(str(v)) for v in values)})"


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Student(Base):
    __tablename__ = "student"

    student_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    """Salted hash of the password (§4.4.5); never the password itself."""
    created_at: Mapped[datetime] = _now()


class Concept(Base):
    __tablename__ = "concept"

    concept_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    syllabus_code: Mapped[str] = mapped_column(String(20))
    topic_area: Mapped[str] = mapped_column(String(50))


class ConfidenceRecord(Base):
    """The learner model: one confidence record per student per concept (§4.9)."""

    __tablename__ = "confidence_record"
    __table_args__ = (
        UniqueConstraint("student_id", "concept_id"),
        CheckConstraint("score >= 0 AND score <= 1", name="score_between_0_and_1"),
    )

    record_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.student_id"), index=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concept.concept_id"))
    score: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    updated_at: Mapped[datetime] = _now()


LESSON_MODES = ("adaptive", "static")


class Lesson(Base):
    __tablename__ = "lesson"
    __table_args__ = (
        CheckConstraint(_one_of("status", LessonStatus), name="status_known"),
        CheckConstraint(_one_of("mode", LESSON_MODES), name="mode_known"),
    )

    lesson_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.student_id"), index=True)
    query_text: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = _now()
    status: Mapped[str] = mapped_column(String(20), default=LessonStatus.IN_PROGRESS.value)
    # Additions. The title shown in the player and the history; adaptive or the study's static
    # condition (§5.9.4); the saved playback position, so a lesson can be resumed (§4.4.3).
    title: Mapped[str] = mapped_column(String(200), default="", server_default="")
    mode: Mapped[str] = mapped_column(String(10), default="adaptive", server_default="adaptive")
    position: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Module(Base):
    __tablename__ = "module"
    __table_args__ = (
        CheckConstraint(
            _one_of("difficulty_level", (level.label for level in Level)),
            name="difficulty_level_known",
        ),
        CheckConstraint(_one_of("style", ModuleStyle), name="style_known"),
        CheckConstraint(_one_of("render_status", RenderStatus), name="render_status_known"),
    )

    module_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lesson.lesson_id"), index=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concept.concept_id"))
    sequence_no: Mapped[int] = mapped_column(Integer)
    difficulty_level: Mapped[str] = mapped_column(String(15))
    """Level 1, Level 2, or Level 3 (`Level.label`)."""
    style: Mapped[str] = mapped_column(String(20), default=ModuleStyle.DEFAULT.value)
    video_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    render_status: Mapped[str] = mapped_column(String(20), default=RenderStatus.QUEUED.value)
    # Additions. The title in the player; the scene plan and the render request of each level
    # (as JSON), so a variant at another level can be rendered later; the cache key of the
    # variant being played; when the module was finished, which moves the lesson on.
    title: Mapped[str] = mapped_column(String(200), default="", server_default="")
    scene_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    render_requests: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    """ModuleRenderRequest JSON by level number, e.g. {"2": {...}}."""
    cache_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InteractionEvent(Base):
    __tablename__ = "interaction_event"
    __table_args__ = (CheckConstraint(_one_of("event_type", InteractionType), name="type_known"),)

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("module.module_id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.student_id"), index=True)
    event_type: Mapped[str] = mapped_column(String(25))
    occurred_at: Mapped[datetime] = _now()
    # Additions. The beat playing and the position in it, which attribute the event to that
    # beat's concepts (§5.6.1), and the event's own fields (rates, durations, the term).
    beat_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)


ITEM_TYPES = ("mcq", "true_false")


class CheckQuestion(Base):
    """An item of the bank with its verified answer (§5.7.3)."""

    __tablename__ = "check_question"
    __table_args__ = (CheckConstraint(_one_of("item_type", ITEM_TYPES), name="item_type_known"),)

    check_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concept.concept_id"), index=True)
    question_text: Mapped[str] = mapped_column(Text)
    correct_option: Mapped[str] = mapped_column(String(100))
    # Additions. The wireframes show the options (Fig. 4.1, 4.4), which Table 4.8 does not store.
    item_type: Mapped[str] = mapped_column(String(10), default="mcq", server_default="mcq")
    """mcq (multiple choice) or true_false."""
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)


class CheckResponse(Base):
    __tablename__ = "check_response"

    response_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    check_id: Mapped[int] = mapped_column(ForeignKey("check_question.check_id"))
    module_id: Mapped[int] = mapped_column(ForeignKey("module.module_id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("student.student_id"), index=True)
    selected_option: Mapped[str] = mapped_column(String(100))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    answered_at: Mapped[datetime] = _now()


class GlossaryTerm(Base):
    """A term shown as a concept chip, with the definition shown in its overlay (§5.6.2)."""

    __tablename__ = "glossary_term"
    __table_args__ = (UniqueConstraint("concept_id", "term"),)

    term_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concept.concept_id"))
    term: Mapped[str] = mapped_column(String(60))
    definition: Mapped[str] = mapped_column(Text)


# Additions: tables the design needs that Table 4.8 does not list (docs/PLAN.md §13, gap 3).


class ConceptPrerequisite(Base):
    """Addition. A prerequisite edge of the concept taxonomy (§5.2.1): planning orders a
    lesson's concepts by these edges, and readiness takes the weakest prerequisite (Eq. 5.5)."""

    __tablename__ = "concept_prerequisite"
    __table_args__ = (
        CheckConstraint("concept_id <> prerequisite_id", name="not_its_own_prerequisite"),
    )

    concept_id: Mapped[int] = mapped_column(ForeignKey("concept.concept_id"), primary_key=True)
    prerequisite_id: Mapped[int] = mapped_column(ForeignKey("concept.concept_id"), primary_key=True)


class Variant(Base):
    """Addition. The variant cache index (Fig. 6.1): one rendered variant, by its cache key.
    The files live in media/variants/<cache_key>/; this row says they exist."""

    __tablename__ = "variant"

    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    level: Mapped[int] = mapped_column(SmallInteger)
    voice: Mapped[str] = mapped_column(String(100))
    library_version: Mapped[str] = mapped_column(String(20))
    beat_count: Mapped[int] = mapped_column(Integer)
    duration_s: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = _now()


RENDER_JOB_STATUSES = ("queued", "rendering", "ready", "failed")


class RenderJob(Base):
    """Addition. The render queue (§4.4.4, §5.5): a job renders one module at one level.

    Workers take the queued job with the best priority, oldest first, with
    SELECT ... FOR UPDATE SKIP LOCKED, so any number of workers share the queue without taking
    the same job. Priority 1 is the next module or an "I'm Lost" substitution; 2 is
    prefetching (the favoured branch, later modules).
    """

    __tablename__ = "render_job"
    __table_args__ = (
        CheckConstraint(_one_of("status", RENDER_JOB_STATUSES), name="status_known"),
        CheckConstraint("priority >= 1", name="priority_positive"),
        Index("ix_render_job_queue", "status", "priority", "created_at"),
    )

    job_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("module.module_id"), index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lesson.lesson_id"), index=True)
    cache_key: Mapped[str] = mapped_column(String(64), index=True)
    level: Mapped[int] = mapped_column(SmallInteger)
    priority: Mapped[int] = mapped_column(SmallInteger, default=1)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    request: Mapped[dict] = mapped_column(JSON)
    """The ModuleRenderRequest to render."""
    worker: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    log: Mapped[str] = mapped_column(Text, default="")
    """One line per event: claimed, beat ready, failed with the error, finished."""
    created_at: Mapped[datetime] = _now()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)


class StreamEventRecord(Base):
    """Addition. The events of a lesson's Server-Sent Events stream (§6.4.12), written by the
    workers and read by the API: the two run in different processes."""

    __tablename__ = "stream_event"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lesson.lesson_id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    """A stream contract (app/contracts/stream.py) as JSON."""
    created_at: Mapped[datetime] = _now()
