"""Errors raised while rendering a module. They cross process boundaries, so they keep their
details in plain strings."""


class RenderError(RuntimeError):
    """Rendering a module failed."""


class InvalidParameters(RenderError):
    """A beat's parameters fail its primitive's schema or validation predicates (§5.3.3)."""


class NarrationMismatch(RenderError):
    """A beat does not have exactly one narration passage per animation step."""


class LayoutViolation(RenderError):
    """A beat drew objects outside the frame or region, or overlapping (§5.3.4).

    The message names the conflicting objects, so it can go back to the parameter model.
    """


class MediaError(RenderError):
    """FFmpeg failed to build the beat or module video."""
