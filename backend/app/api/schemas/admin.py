"""The administrator's functions (report §4.2.2)."""

from typing import Literal, Self

from pydantic import AwareDatetime, Field, NonNegativeInt, PositiveInt, model_validator

from app.api.schemas.common import TRUE_FALSE_OPTIONS, ItemType, Schema
from app.contracts import Level
from app.contracts.scene_plan import GlossaryTerm


class AdminSummary(Schema):
    students: NonNegativeInt
    lessons_today: NonNegativeInt
    renders_failed_24h: NonNegativeInt
    render_success_rate_7d: float | None = Field(ge=0, le=1)
    """Share of finished render jobs in the last 7 days that succeeded; null with none."""


PrimitiveStatus = Literal["enabled", "retired"]


class PrimitiveAdmin(Schema):
    """A primitive's metadata. Its code arrives by pull request and must pass the validation
    harness (§5.3.2), so the admin manages only status and description."""

    id: str
    topic: str
    version: str
    status: PrimitiveStatus
    description: str


class PrimitivePatch(Schema):
    status: PrimitiveStatus | None = None
    description: str | None = Field(default=None, max_length=500)


class GlossaryEntry(Schema):
    id: PositiveInt
    concept_id: PositiveInt
    term: GlossaryTerm
    definition: str


class GlossaryCreate(Schema):
    concept_id: PositiveInt
    term: GlossaryTerm
    definition: str = Field(min_length=1, max_length=2000)


class GlossaryPatch(Schema):
    concept_id: PositiveInt | None = None
    term: GlossaryTerm | None = None
    definition: str | None = Field(default=None, min_length=1, max_length=2000)


class GlossaryPage(Schema):
    items: list[GlossaryEntry]
    total: NonNegativeInt
    page: PositiveInt
    page_size: PositiveInt


class CheckQuestionFields(Schema):
    concept_id: PositiveInt
    item_type: ItemType
    question_text: str = Field(min_length=1, max_length=1000)
    options: list[str] = Field(min_length=2, max_length=4)
    correct_option: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if any(not option.strip() or len(option) > 100 for option in self.options):
            raise ValueError("options must be non-empty and at most 100 characters")
        if len(set(self.options)) != len(self.options):
            raise ValueError("options must not repeat")
        if self.item_type == "true_false" and self.options != TRUE_FALSE_OPTIONS:
            raise ValueError('a true/false item has exactly the options ["True", "False"]')
        if self.correct_option not in self.options:
            raise ValueError("correct_option must be one of the options")
        return self


class CheckQuestion(CheckQuestionFields):
    id: PositiveInt


class CheckQuestionCreate(CheckQuestionFields):
    pass


class CheckQuestionPatch(Schema):
    """Changed fields only. The item is checked again as a whole after the change."""

    concept_id: PositiveInt | None = None
    item_type: ItemType | None = None
    question_text: str | None = None
    options: list[str] | None = None
    correct_option: str | None = None


class CheckQuestionPage(Schema):
    items: list[CheckQuestion]
    total: NonNegativeInt
    page: PositiveInt
    page_size: PositiveInt


RenderJobStatus = Literal["queued", "rendering", "ready", "failed"]


class RenderJob(Schema):
    id: PositiveInt
    lesson_id: PositiveInt
    module_id: PositiveInt
    level: Level
    priority: Literal[1, 2]
    """1: the next module (or an "I'm Lost" substitution); 2: the favoured branch (§5.5)."""
    status: RenderJobStatus
    attempts: NonNegativeInt
    created_at: AwareDatetime
    finished_at: AwareDatetime | None
    duration_s: float | None
    error: str | None


class RenderJobDetail(RenderJob):
    log: str


class RenderJobPage(Schema):
    items: list[RenderJob]
    total: NonNegativeInt
    page: PositiveInt
    page_size: PositiveInt


class StudentAdmin(Schema):
    id: PositiveInt
    name: str
    email: str
    created_at: AwareDatetime
    last_active_at: AwareDatetime | None
    lessons: NonNegativeInt
    diagnostic_complete: bool
    disabled: bool


class StudentPatch(Schema):
    disabled: bool


class StudentPage(Schema):
    items: list[StudentAdmin]
    total: NonNegativeInt
    page: PositiveInt
    page_size: PositiveInt
