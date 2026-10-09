"""GET /api/health: reports whether the app and its external dependencies are available."""

import importlib
import shutil
from functools import lru_cache

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__
from app.db.session import database_is_reachable

router = APIRouter(tags=["health"])


class HealthChecks(BaseModel):
    database: bool
    ffmpeg: bool
    latex: bool
    manim: bool


class HealthResponse(BaseModel):
    status: str
    version: str
    checks: HealthChecks


def _safe(check) -> bool:
    try:
        return bool(check())
    except Exception:
        return False


def _ffmpeg_found() -> bool:
    return shutil.which("ffmpeg") is not None


def _latex_found() -> bool:
    # Manim's MathTex needs both `latex` and `dvisvgm`.
    return shutil.which("latex") is not None and shutil.which("dvisvgm") is not None


@lru_cache
def _manim_importable() -> bool:
    # Importing manim is slow, so do it once per process.
    return _safe(lambda: importlib.import_module("manim"))


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=__version__,
        checks=HealthChecks(
            database=_safe(database_is_reachable),
            ffmpeg=_safe(_ffmpeg_found),
            latex=_safe(_latex_found),
            manim=_safe(_manim_importable),
        ),
    )
