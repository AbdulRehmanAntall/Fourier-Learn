"""Render a module from a JSON request file.

    python -m app.renderer examples/gradient_of_line.L2.render.json
    npm run render -- backend/examples/gradient_of_line.L2.render.json   (from the repo root)

Options: --tts espeak|fake, --quality 480p30|720p30|1080p30, --workers N, --force (ignore the
cache). Prints where the module was stored and how long each stage took.
"""

import argparse
import sys
from pathlib import Path

from app.audio_pipeline.tts import get_provider
from app.core.config import get_settings
from app.primitives.library import LIBRARY_VERSION
from app.renderer.beat import QUALITIES
from app.renderer.engine import render_module, request_from_file
from app.renderer.errors import RenderError


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="python -m app.renderer", description=__doc__)
    parser.add_argument("request", type=Path, help="ModuleRenderRequest JSON file")
    parser.add_argument("--tts", default=settings.tts_provider)
    parser.add_argument("--quality", default=settings.render_quality, choices=sorted(QUALITIES))
    parser.add_argument("--workers", type=int, default=settings.render_workers)
    parser.add_argument("--force", action="store_true", help="render even if cached")
    args = parser.parse_args(argv)

    try:
        request = request_from_file(args.request)
        result = render_module(
            request,
            media_dir=settings.media_dir,
            tts=get_provider(args.tts),
            library_version=LIBRARY_VERSION,
            quality=args.quality,
            workers=args.workers,
            force=args.force,
            on_beat_ready=lambda beat: print(
                f"  beat {beat.index} ready ({beat.duration_s:.1f} s)"
            ),
        )
    except (RenderError, ValueError, OSError) as error:
        print(f"Render failed: {error}", file=sys.stderr)
        return 1

    manifest = result.manifest
    print(f"{'Cached' if result.cache_hit else 'Rendered'} {request.level.label} variant")
    print(f"  directory: {result.directory}")
    if manifest.is_complete:
        print(
            f"  module:    {result.directory / manifest.module_video} ({manifest.duration_s:.1f} s)"
        )
    for name, seconds in result.timings.items():
        print(f"  {name:<10} {seconds:6.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
