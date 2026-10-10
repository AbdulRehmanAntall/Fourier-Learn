"""Contracts: the data shapes the components exchange (report §4.3.5, §6.2.2).

The Prompt Interpreter, Code Generator, Audio Pipeline, render engine, scheduler, Learner State
Module and the player all talk through these models. Changing one affects every lane, so a
change needs a PR reviewed by the whole team. See docs/contracts.md.
"""

from app.contracts.interaction import (
    BranchChoiceEvent,
    ChipViewEvent,
    ImLostEvent,
    InteractionEvent,
    InteractionEventBatch,
    InteractionType,
    PauseEvent,
    RewindEvent,
    SpeedChangeEvent,
)
from app.contracts.level import Level
from app.contracts.primitive import (
    LayoutContract,
    PredicateFailure,
    Primitive,
    PrimitiveParams,
    Region,
    StepSpec,
)
from app.contracts.render import (
    BeatManifest,
    BeatRenderSpec,
    ChipInterval,
    ModuleManifest,
    ModuleRenderRequest,
    StepTiming,
    variant_cache_key,
)
from app.contracts.scene_plan import (
    BranchOption,
    LessonPlan,
    QueryInterpretation,
    ScenePlan,
    Segment,
)
from app.contracts.status import LessonStatus, ModuleStyle, RenderStatus
from app.contracts.stream import (
    BeatReady,
    GenerationProgress,
    ModuleFailed,
    ModuleReady,
    StreamEvent,
    StreamEventType,
    encode_sse,
)

__all__ = [
    "BeatManifest",
    "BeatReady",
    "BeatRenderSpec",
    "BranchChoiceEvent",
    "BranchOption",
    "ChipInterval",
    "ChipViewEvent",
    "GenerationProgress",
    "ImLostEvent",
    "InteractionEvent",
    "InteractionEventBatch",
    "InteractionType",
    "LayoutContract",
    "LessonPlan",
    "LessonStatus",
    "Level",
    "ModuleFailed",
    "ModuleManifest",
    "ModuleReady",
    "ModuleRenderRequest",
    "ModuleStyle",
    "PauseEvent",
    "PredicateFailure",
    "Primitive",
    "PrimitiveParams",
    "QueryInterpretation",
    "Region",
    "RenderStatus",
    "RewindEvent",
    "ScenePlan",
    "Segment",
    "SpeedChangeEvent",
    "StepSpec",
    "StepTiming",
    "StreamEvent",
    "StreamEventType",
    "encode_sse",
    "variant_cache_key",
]
