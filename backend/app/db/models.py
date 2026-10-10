"""Database tables: the entities and attributes of the data dictionary (report Table 4.8).

Each class maps to one entity of the ER diagram (Fig. 4.7) and the class diagram (Fig. 6.3).
Columns, types, lengths and nullability follow Table 4.8. Values that the table lists in words
are stored as the contract values in app/contracts (for example "Level 2", "worked_example").
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
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


class Lesson(Base):
    __tablename__ = "lesson"
    __table_args__ = (CheckConstraint(_one_of("status", LessonStatus), name="status_known"),)

    lesson_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.student_id"), index=True)
    query_text: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = _now()
    status: Mapped[str] = mapped_column(String(20), default=LessonStatus.IN_PROGRESS.value)


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


class InteractionEvent(Base):
    __tablename__ = "interaction_event"
    __table_args__ = (CheckConstraint(_one_of("event_type", InteractionType), name="type_known"),)

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("module.module_id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.student_id"), index=True)
    event_type: Mapped[str] = mapped_column(String(25))
    occurred_at: Mapped[datetime] = _now()


class CheckQuestion(Base):
    """An item of the bank with its verified answer (§5.7.3)."""

    __tablename__ = "check_question"

    check_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concept.concept_id"), index=True)
    question_text: Mapped[str] = mapped_column(Text)
    correct_option: Mapped[str] = mapped_column(String(100))


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
