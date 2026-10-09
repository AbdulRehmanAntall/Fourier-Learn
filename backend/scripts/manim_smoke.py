"""Render one tiny scene to check that Manim, LaTeX and FFmpeg work together.

Run from the repo root with `npm run manim:smoke`, or from backend/ with
`python scripts/manim_smoke.py`. Prints the path of the rendered video.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from manim import UR, Axes, Create, MathTex, Scene, Write, tempconfig  # noqa: E402

from app.core.config import get_settings  # noqa: E402


class SmokeScene(Scene):
    def construct(self):
        axes = Axes(x_range=[-3, 3], y_range=[0, 9], x_length=6, y_length=4)
        graph = axes.plot(lambda x: x**2, x_range=[-3, 3])
        label = MathTex("y = x^2").to_corner(UR)
        self.play(Create(axes), Create(graph), Write(label), run_time=1)


def main() -> int:
    media_dir = get_settings().media_dir / "smoke"
    options = {"quality": "low_quality", "media_dir": str(media_dir), "disable_caching": True}
    with tempconfig(options):
        scene = SmokeScene()
        scene.render()
        video = Path(scene.renderer.file_writer.movie_file_path)

    if not video.is_file():
        print("Render finished but no video file was found.", file=sys.stderr)
        return 1
    print(f"\nManim smoke test OK. Video: {video}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
