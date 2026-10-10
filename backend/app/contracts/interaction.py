"""Interaction events sent by the player (report §5.6.1, Table 4.8, Table 5.4).

The event types are those of INTERACTION_EVENT.event_type: rewind, speed change, pause, chip
view, I'm Lost, and branch choice. Each event names the beat playing when it happened, so the
Learner State Module can attribute it to that beat's concepts through the manifest. Check
answers are not interaction events; they are CHECK_RESPONSE records.

The student is taken from the session, never from the event.
"""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveInt,
    model_validator,
)

from app.contracts.scene_plan import GlossaryTerm
from app.contracts.status import ModuleStyle

# The playback rates the player offers.
MIN_PLAYBACK_RATE = 0.25
MAX_PLAYBACK_RATE = 4.0

PlaybackRate = Annotated[float, Field(ge=MIN_PLAYBACK_RATE, le=MAX_PLAYBACK_RATE)]


class InteractionType(StrEnum):
    REWIND = "rewind"
    SPEED_CHANGE = "speed_change"
    PAUSE = "pause"
    CHIP_VIEW = "chip_view"
    IM_LOST = "im_lost"
    BRANCH_CHOICE = "branch_choice"


class _Event(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    module_id: PositiveInt
    occurred_at: AwareDatetime


class _DuringPlayback(_Event):
    beat_index: NonNegativeInt
    """The beat playing when the event happened."""
    position_s: NonNegativeFloat
    """Seconds from the start of that beat's video."""


class RewindEvent(_DuringPlayback):
    """Seeking back to an earlier point. Evidence for the concepts of the beat returned to."""

    type: Literal[InteractionType.REWIND] = InteractionType.REWIND
    to_beat_index: NonNegativeInt
    to_position_s: NonNegativeFloat

    @model_validator(mode="after")
    def _goes_back(self) -> Self:
        if (self.to_beat_index, self.to_position_s) >= (self.beat_index, self.position_s):
            raise ValueError("a rewind must seek to an earlier point")
        return self


class SpeedChangeEvent(_DuringPlayback):
    """Lowering or raising the playback speed (Table 5.4: slowed is difficulty, sped up is ease)."""

    type: Literal[InteractionType.SPEED_CHANGE] = InteractionType.SPEED_CHANGE
    from_rate: PlaybackRate
    to_rate: PlaybackRate

    @model_validator(mode="after")
    def _changes(self) -> Self:
        if self.from_rate == self.to_rate:
            raise ValueError("a speed change must change the rate")
        return self

    @property
    def slowed(self) -> bool:
        return self.to_rate < self.from_rate


class PauseEvent(_DuringPlayback):
    """A pause, sent when playback resumes. A dwell longer than a set threshold is evidence of
    difficulty (Table 5.4); the threshold belongs to the Learner State Module."""

    type: Literal[InteractionType.PAUSE] = InteractionType.PAUSE
    duration_s: NonNegativeFloat


class ChipViewEvent(_DuringPlayback):
    """Selecting a concept chip to read its definition (§5.6.2)."""

    type: Literal[InteractionType.CHIP_VIEW] = InteractionType.CHIP_VIEW
    term: GlossaryTerm


class ImLostEvent(_DuringPlayback):
    """Pressing the "I'm Lost" control (§5.6.3)."""

    type: Literal[InteractionType.IM_LOST] = InteractionType.IM_LOST


class BranchChoiceEvent(_Event):
    """The option selected at a branch point after the module (§5.6.4)."""

    type: Literal[InteractionType.BRANCH_CHOICE] = InteractionType.BRANCH_CHOICE
    option: Literal[ModuleStyle.THEORY, ModuleStyle.WORKED_EXAMPLE, "next_step"]


InteractionEvent = Annotated[
    RewindEvent | SpeedChangeEvent | PauseEvent | ChipViewEvent | ImLostEvent | BranchChoiceEvent,
    Field(discriminator="type"),
]


class InteractionEventBatch(BaseModel):
    """The body of one request from the player's event logger."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    events: list[InteractionEvent] = Field(min_length=1, max_length=100)
