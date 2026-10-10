"""Where rendered variants live on disk. Kept free of Manim imports, so the API can read
manifests on machines without Manim."""

import os
from pathlib import Path

from app.contracts import ModuleManifest

MANIFEST_FILE = "manifest.json"
MODULE_FILE = "module.mp4"


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
