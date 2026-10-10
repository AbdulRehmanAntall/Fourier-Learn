"""The render engine's input and output (report §5.3.4, §5.4.4, §5.5).

Input: a `ModuleRenderRequest`, one module at one difficulty level, with validated parameters
and finished narration for each beat. Output: a rendered variant described by a
`ModuleManifest`, stored under its `variant_cache_key`.
"""

import hashlib
import json
import re
from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    model_validator,
)

from app.contracts.level import Level
from app.contracts.scene_plan import GlossaryTerm, NonEmptyStr

# Numbers enter the narration only through named slots filled after generation (§5.4.2).
_UNFILLED_SLOT = re.compile(r"\{[A-Za-z_]\w*\}")

# Times read from rendered media are rounded; allow this much slack when comparing them.
TIME_TOLERANCE_S = 0.05


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BeatRenderSpec(_Contract):
    """One beat to render: a primitive, its validated parameters and its narration."""

    primitive_id: NonEmptyStr
    params: dict[str, Any]
    """A parameter set that has passed the primitive's schema and validation predicates."""
    narration: list[NonEmptyStr] = Field(min_length=1)
    """One passage per animation step at the request's level, with every slot filled."""
    glossary_terms: list[GlossaryTerm] = []
    concept_ids: list[PositiveInt] = []
    """The concepts of the beat, to which interactions during it are attributed (§5.6.1)."""

    @model_validator(mode="after")
    def _slots_filled(self) -> Self:
        for passage in self.narration:
            if slot := _UNFILLED_SLOT.search(passage):
                raise ValueError(f"narration slot {slot.group()} has not been filled")
        return self


class ModuleRenderRequest(_Contract):
    """Render one module at one level (§5.3.4)."""

    module_id: PositiveInt
    level: Level
    voice: NonEmptyStr
    """The narration voice."""
    library_version: NonEmptyStr
    """The version of the primitive library the parameters were validated against."""
    beats: list[BeatRenderSpec] = Field(min_length=1)
    """Every beat of the module, in order. All variants share the same beats (§5.2.3)."""
    render_from_beat: NonNegativeInt = 0
    """After an "I'm Lost" press in beat j, only beats j onward are rendered at the lower level
    (§5.6.3). Earlier beats then only supply the state carried into beat j."""

    @model_validator(mode="after")
    def _render_from_in_range(self) -> Self:
        if self.render_from_beat >= len(self.beats):
            raise ValueError("render_from_beat must name one of the beats")
        return self


def variant_cache_key(request: ModuleRenderRequest) -> str:
    """The key a rendered variant is cached under (§4.2.3, §5.3.4, §6.1.7).

    It is a hash of exactly the primitive identifiers, parameter sets, difficulty level,
    narration voice and primitive library version. A later request that matches on all five
    reuses the variant, which saves narration, speech synthesis and rendering. `render_from_beat`
    is not part of it: a beat's video depends only on the beats up to it, so beats rendered
    after an "I'm Lost" press belong to the same variant.
    """
    identity = {
        "primitive_ids": [beat.primitive_id for beat in request.beats],
        "params": [beat.params for beat in request.beats],
        "level": int(request.level),
        "voice": request.voice,
        "library_version": request.library_version,
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class StepTiming(_Contract):
    """When a step runs within its beat, and the passage spoken over it."""

    start_s: NonNegativeFloat
    end_s: NonNegativeFloat
    narration: NonEmptyStr

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end_s < self.start_s:
            raise ValueError("a step cannot end before it starts")
        return self


class ChipInterval(_Contract):
    """When a concept chip is shown beside the video, within its beat (§5.6.2)."""

    term: GlossaryTerm
    start_s: NonNegativeFloat
    end_s: NonNegativeFloat

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end_s < self.start_s:
            raise ValueError("a chip cannot end before it starts")
        return self


class BeatManifest(_Contract):
    """One rendered beat. Times are seconds from the start of the beat's own video."""

    index: NonNegativeInt
    primitive_id: NonEmptyStr
    video: NonEmptyStr
    """Path of the beat's video (with its narration), relative to the variant's directory."""
    duration_s: PositiveFloat
    steps: list[StepTiming] = Field(min_length=1)
    chips: list[ChipInterval] = []
    concept_ids: list[PositiveInt] = []

    @model_validator(mode="after")
    def _times_inside_beat(self) -> Self:
        limit = self.duration_s + TIME_TOLERANCE_S
        previous_end = 0.0
        for step in self.steps:
            if step.start_s < previous_end - TIME_TOLERANCE_S:
                raise ValueError("steps must run in order without overlapping")
            if step.end_s > limit:
                raise ValueError("a step ends after the beat")
            previous_end = step.end_s
        if any(chip.end_s > limit for chip in self.chips):
            raise ValueError("a chip is shown after the beat ends")
        return self


class ModuleManifest(_Contract):
    """The segment manifest of one rendered variant (§5.4.4).

    The Interactive Playback Layer uses it to time the chips, locate beat boundaries, and
    attribute each interaction to the concepts of its beat. A variant is identified by its
    cache key, so the same manifest serves every module that reuses the variant.

    After an "I'm Lost" press a variant may hold only beats j onward; it is complete once all
    `beat_count` beats are present.
    """

    cache_key: NonEmptyStr
    level: Level
    voice: NonEmptyStr
    library_version: NonEmptyStr
    beat_count: PositiveInt
    beats: list[BeatManifest] = Field(min_length=1)
    """The beats rendered so far, in order and without gaps."""
    module_video: NonEmptyStr | None = None
    """The joined video of all beats (FFmpeg), present only when the variant is complete."""

    @model_validator(mode="after")
    def _beats_contiguous(self) -> Self:
        indices = [beat.index for beat in self.beats]
        if indices != list(range(indices[0], indices[0] + len(indices))):
            raise ValueError("beats must be in order without gaps")
        if indices[-1] >= self.beat_count:
            raise ValueError("a beat index is beyond beat_count")
        if self.module_video is not None and not self.is_complete:
            raise ValueError("module_video is only set when every beat is present")
        return self

    @property
    def is_complete(self) -> bool:
        return self.beats[0].index == 0 and len(self.beats) == self.beat_count

    def beat(self, index: int) -> BeatManifest:
        for beat in self.beats:
            if beat.index == index:
                return beat
        raise KeyError(f"beat {index} is not in this manifest")

    def beat_offsets_s(self) -> list[float]:
        """Start of each beat within the joined module video. Needs a complete variant."""
        if not self.is_complete:
            raise ValueError("offsets are only defined for a complete variant")
        offsets, total = [], 0.0
        for beat in self.beats:
            offsets.append(total)
            total += beat.duration_s
        return offsets

    @property
    def duration_s(self) -> float:
        """Length of the whole module. Needs a complete variant."""
        if not self.is_complete:
            raise ValueError("duration is only defined for a complete variant")
        return sum(beat.duration_s for beat in self.beats)
