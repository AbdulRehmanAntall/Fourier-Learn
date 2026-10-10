"""Progress events sent to the browser over Server-Sent Events (report §6.4.12, Fig. 6.2).

The browser submits requests over REST and receives generation progress through one event
stream per lesson. If the stream disconnects, the browser retrieves the current lesson status
before resuming updates.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, PositiveInt

from app.contracts.level import Level


class StreamEventType(StrEnum):
    GENERATION_PROGRESS = "generation_progress"
    BEAT_READY = "beat_ready"
    MODULE_READY = "module_ready"
    MODULE_FAILED = "module_failed"


class _StreamEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lesson_id: PositiveInt
    module_id: PositiveInt


class GenerationProgress(_StreamEvent):
    """Which stage of generation a module has reached, so the interface can show progress."""

    type: Literal[StreamEventType.GENERATION_PROGRESS] = StreamEventType.GENERATION_PROGRESS
    stage: Literal["planning", "parameters", "narration", "rendering"]


class BeatReady(_StreamEvent):
    """A beat is stored and can be played. Playback starts when the first beat is ready."""

    type: Literal[StreamEventType.BEAT_READY] = StreamEventType.BEAT_READY
    level: Level
    beat_index: NonNegativeInt
    cache_key: str
    """Names the variant whose manifest describes the beat."""


class ModuleReady(_StreamEvent):
    """Every beat of the module is ready at this level."""

    type: Literal[StreamEventType.MODULE_READY] = StreamEventType.MODULE_READY
    level: Level
    cache_key: str


class ModuleFailed(_StreamEvent):
    """Generation failed after its retries (§6.4.6).

    A module whose plan cannot be validated is replaced by a cached variant of the same concept
    or, failing that, by the glossary definition; `fallback` says which, if either.
    """

    type: Literal[StreamEventType.MODULE_FAILED] = StreamEventType.MODULE_FAILED
    level: Level | None = None
    fallback: Literal["cached_variant", "glossary_definition"] | None = None
    message: str


StreamEvent = Annotated[
    GenerationProgress | BeatReady | ModuleReady | ModuleFailed,
    Field(discriminator="type"),
]


def encode_sse(event: GenerationProgress | BeatReady | ModuleReady | ModuleFailed) -> str:
    """Format an event as one Server-Sent Events message."""
    return f"event: {event.type.value}\ndata: {event.model_dump_json()}\n\n"
