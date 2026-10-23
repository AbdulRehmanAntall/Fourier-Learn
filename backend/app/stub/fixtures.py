"""The fixture variants the stub's lessons play.

`backend/fixtures/variants/` holds the example module "gradient of a straight line"
(backend/examples/gradient_of_line.L*.render.json) rendered at Level 1, 2 and 3, at 480p30
with the Kokoro voice. The files are committed so the frontend team can play real videos
without Manim, LaTeX or a voice model. To re-render them:

    npm run render -- examples/gradient_of_line.L2.render.json --quality 480p30

then copy the variant directory from backend/media/variants/ into backend/fixtures/variants/.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path

from app.contracts import Level
from app.core.config import BACKEND_DIR
from app.renderer.store import load_manifest

FIXTURES_DIR = BACKEND_DIR / "fixtures" / "variants"


@dataclass(frozen=True)
class FixtureVariant:
    level: Level
    cache_key: str
    beat_count: int


def load_fixture_variants(directory: Path = FIXTURES_DIR) -> dict[Level, FixtureVariant]:
    variants = {}
    for path in sorted(directory.iterdir()) if directory.is_dir() else []:
        manifest = load_manifest(path)
        if manifest is not None and manifest.is_complete:
            variants[manifest.level] = FixtureVariant(
                manifest.level, manifest.cache_key, manifest.beat_count
            )
    missing = [level.label for level in Level if level not in variants]
    if missing:
        raise RuntimeError(f"fixture variants missing in {directory}: {', '.join(missing)}")
    return variants


def install_fixture_variants(media_dir: Path, directory: Path = FIXTURES_DIR) -> None:
    """Copy the fixture variants into the media folder, where /media serves them."""
    for path in directory.iterdir() if directory.is_dir() else []:
        target = media_dir / "variants" / path.name
        if path.is_dir() and not (target / "manifest.json").is_file():
            shutil.copytree(path, target, dirs_exist_ok=True)
