"""Where rendered variants live on disk. Kept free of Manim imports, so the API can read
manifests on machines without Manim."""

import os
from pathlib import Path

from app.contracts import BeatManifest, ModuleManifest, ModuleRenderRequest, variant_cache_key

MANIFEST_FILE = "manifest.json"
MODULE_FILE = "module.mp4"


def voice_identity(tts_name: str, voice: str) -> str:
    """The narration voice as the cache key sees it: the speech engine and its voice, so that
    switching from espeak-ng to Kokoro never reuses a video narrated by the old engine."""
    return f"{tts_name}:{voice}"


def cache_key_for(request: ModuleRenderRequest, tts_name: str) -> str:
    """The variant cache key of `request` when it is narrated by the `tts_name` engine."""
    voiced = request.model_copy(update={"voice": voice_identity(tts_name, request.voice)})
    return variant_cache_key(voiced)


def variant_directory(media_dir: Path, cache_key: str) -> Path:
    return media_dir / "variants" / cache_key


def load_manifest(directory: Path) -> ModuleManifest | None:
    path = directory / MANIFEST_FILE
    if not path.is_file():
        return None
    return ModuleManifest.model_validate_json(path.read_text(encoding="utf-8"))


def write_atomically(path: Path, text: str) -> None:
    """Write `text` so that readers see either the old file or the new one, never half."""
    partial = path.with_name(f".{path.name}.{os.getpid()}.partial")
    partial.write_text(text, encoding="utf-8")
    partial.replace(path)


def playable_beats(beats: dict[int, BeatManifest], first: int) -> list[BeatManifest]:
    """The unbroken run of beats from `first`: what a player can play in order. Beats finish
    rendering in any order, but a manifest lists them in order without gaps."""
    run, index = [], first
    while index in beats:
        run.append(beats[index])
        index += 1
    return run
