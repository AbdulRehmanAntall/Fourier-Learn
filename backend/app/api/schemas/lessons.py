"""Lessons and their playback (UC 4.3–4.7, §5.5, §5.6, Algorithm 1).

The frontend never decides which module comes next, at which level, or whether an answer is
right: these responses tell it (docs/frontend.md, rule 1).
"""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, NonNegativeFloat, NonNegativeInt, PositiveInt

from app.api.schemas.common import CheckItem, Concept, Schema, TopicArea
from app.contracts import LessonStatus, Level, ModuleStyle, RenderStatus

LessonMode = Literal["adaptive", "static"]
"""Static is the study's comparison condition: the L2 render with no interactive layer (§5.9.4)."""

BranchChoice = Literal["theory", "worked_example", "next_step"]


class CreateLessonRequest(Schema):
    query_text: str = Field(min_length=1, max_length=300)


class LessonCreated(Schema):
    status: Literal["created"] = "created"
    lesson_id: PositiveInt


class OutOfScope(Schema):
    """The query is outside the supported topics (UC 4.3, alternative flow)."""

    status: Literal["out_of_scope"] = "out_of_scope"
    message: str
    nearest_concepts: list[Concept]
    topics: list[TopicArea]


CreateLessonResponse = Annotated[LessonCreated | OutOfScope, Field(discriminator="status")]


class Position(Schema):
    """Where the student is in a lesson. `position_s` is seconds into the beat's own video."""

    module_id: PositiveInt
    beat_index: NonNegativeInt
    position_s: NonNegativeFloat


class ModuleSummary(Schema):
    id: PositiveInt
    sequence_no: PositiveInt
    title: str
    concept_id: PositiveInt
    style: ModuleStyle
    is_review: bool
    render_status: RenderStatus
    level: Level | None
    """The level the module is (or will be) played at; null until chosen."""
    completed: bool


class Lesson(Schema):
    id: PositiveInt
    title: str
    query_text: str
    status: LessonStatus
    mode: LessonMode
    started_at: AwareDatetime
    modules: list[ModuleSummary]
    position: Position | None
    """The saved playback position, used to resume; null before playback starts."""


class LessonSummary(Schema):
    id: PositiveInt
    title: str
    query_text: str
    status: LessonStatus
    started_at: AwareDatetime
    modules_total: NonNegativeInt
    modules_completed: NonNegativeInt


GenerationStage = Literal["planning", "parameters", "narration", "rendering"]


class ModuleFailure(Schema):
    """Why a module could not be prepared, and what replaces it (§6.4.6)."""

    fallback: Literal["cached_variant", "glossary_definition"] | None
    message: str
    definition: str | None
    """With the glossary fallback: the definition of the module's concept to show instead."""


class CurrentModule(Schema):
    """What the player should do now.

    - `ready`: play `module` from the variant `cache_key` (at least its first beat is ready).
    - `preparing`: wait for the stream; `stage` says how far generation has got.
    - `failed`: show `failure`, then call `finish` for the module to move on.
    - `complete`: the lesson is over.
    """

    status: Literal["ready", "preparing", "failed", "complete"]
    module: ModuleSummary | None
    level: Level | None
    cache_key: str | None
    stage: GenerationStage | None = None
    failure: ModuleFailure | None = None


class BranchOptionOut(Schema):
    choice: BranchChoice
    title: str
    description: str


class BranchPoint(Schema):
    """The choice after a module (§5.6.4, Fig. 4.5). With no answer in time, the default is
    taken."""

    options: list[BranchOptionOut] = Field(min_length=2, max_length=3)
    default_choice: Literal["next_step"] = "next_step"
    timeout_s: PositiveInt


class ModuleEnd(Schema):
    """Returned when a module ends: its check items (§5.7.3) and its branch point, if any."""

    check_items: list[CheckItem] = Field(max_length=2)
    branch: BranchPoint | None


class CheckResponseRequest(Schema):
    module_id: PositiveInt
    check_id: PositiveInt
    selected_option: str = Field(min_length=1, max_length=100)


class CheckResponseResult(Schema):
    is_correct: bool
    correct_option: str


class BranchRequest(Schema):
    module_id: PositiveInt
    choice: BranchChoice
    timed_out: bool = False
    """True when the countdown ran out and the default was taken (UC 4.7, alternative flow)."""


class ImLostRequest(Schema):
    module_id: PositiveInt
    beat_index: NonNegativeInt
    position_s: NonNegativeFloat


class ImLostSubstitute(Schema):
    """The module continues one level lower from the start of `resume_beat_index` (§5.6.3)."""

    action: Literal["substitute"] = "substitute"
    level: Level
    cache_key: str
    resume_beat_index: NonNegativeInt
    ready: bool
    """True if that beat can be played now; otherwise wait for its `beat_ready` event."""


class ImLostReplay(Schema):
    """At Level 1: replay the beat with its chips open (§5.6.3)."""

    action: Literal["replay"] = "replay"
    resume_beat_index: NonNegativeInt
    worked_example_added: bool
    """True if this press added a worked-example module after the current one."""


ImLostResult = Annotated[ImLostSubstitute | ImLostReplay, Field(discriminator="action")]
