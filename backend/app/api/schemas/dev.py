"""The development endpoint that turns a hand-written lesson into a real one (Phase 3).

Until the planner and the Code Generator exist (Phase 4), a person writes each module's scene
plan and its render requests: the parameters and narration at one or more levels. POST
/api/dev/render checks them, stores the lesson, and queues the renders; the lesson then plays
through the same endpoints as any other.
"""

from typing import Self

from pydantic import Field, model_validator

from app.api.schemas.common import Schema
from app.contracts import Level, ModuleRenderRequest, ScenePlan


class DevModule(Schema):
    title: str = Field(min_length=1, max_length=200)
    plan: ScenePlan
    renders: list[ModuleRenderRequest] = Field(min_length=1, max_length=3)
    """The module rendered at one or more levels; its module_id is replaced when stored."""

    @model_validator(mode="after")
    def _one_render_per_level(self) -> Self:
        levels = [render.level for render in self.renders]
        if len(set(levels)) != len(levels):
            raise ValueError("give at most one render request per level")
        return self


class DevLessonRequest(Schema):
    title: str = Field(min_length=1, max_length=200)
    query_text: str = Field(default="development lesson", min_length=1, max_length=300)
    level: Level = Level.STANDARD
    """The level every module is played at. In Phase 5 the learner model chooses it per
    module."""
    modules: list[DevModule] = Field(min_length=1, max_length=10)
