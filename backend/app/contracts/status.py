"""Status and style values from the data dictionary (report Table 4.8)."""

from enum import StrEnum


class LessonStatus(StrEnum):
    """LESSON.status: in progress, completed, or abandoned."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class RenderStatus(StrEnum):
    """MODULE.render_status: queued, rendering, ready, or failed."""

    QUEUED = "queued"
    RENDERING = "rendering"
    READY = "ready"
    FAILED = "failed"


class ModuleStyle(StrEnum):
    """MODULE.style: theory, worked example, or default.

    Theory and worked example are the two branch options a scene plan can offer (§5.6.4).
    """

    DEFAULT = "default"
    THEORY = "theory"
    WORKED_EXAMPLE = "worked_example"
