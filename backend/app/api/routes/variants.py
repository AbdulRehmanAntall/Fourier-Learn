"""Rendered variants: their manifests, and a listing for the developer viewer.

GET /api/variants/{cache_key}/manifest is the endpoint of the API sketch (docs/contracts.md).
GET /api/dev/variants lists what is in the media folder; it exists for /dev/modules in the
frontend and is not part of the student-facing API.
"""

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.contracts import Level, ModuleManifest
from app.core.config import get_settings
from app.renderer.store import load_manifest, variant_directory

router = APIRouter(tags=["variants"])

_CACHE_KEY = re.compile(r"[0-9a-f]{64}")


class VariantSummary(BaseModel):
    cache_key: str
    level: Level
    beat_count: int
    beats_ready: int
    complete: bool
    duration_s: float | None
    primitives: list[str]


@router.get("/variants/{cache_key}/manifest", response_model=ModuleManifest)
def get_manifest(cache_key: str) -> ModuleManifest:
    # The key names a directory, so only accept the shape a real key has.
    if not _CACHE_KEY.fullmatch(cache_key):
        raise HTTPException(status_code=404, detail="No such variant")
    manifest = load_manifest(variant_directory(get_settings().media_dir, cache_key))
    if manifest is None:
        raise HTTPException(status_code=404, detail="No such variant")
    return manifest


@router.get("/dev/variants", response_model=list[VariantSummary])
def list_variants() -> list[VariantSummary]:
    root: Path = get_settings().media_dir / "variants"
    summaries = []
    directories = sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for directory in directories if root.is_dir() else []:
        manifest = load_manifest(directory)
        if manifest is None:
            continue
        summaries.append(
            VariantSummary(
                cache_key=manifest.cache_key,
                level=manifest.level,
                beat_count=manifest.beat_count,
                beats_ready=len(manifest.beats),
                complete=manifest.is_complete,
                duration_s=manifest.duration_s if manifest.is_complete else None,
                primitives=[beat.primitive_id for beat in manifest.beats],
            )
        )
    return summaries
