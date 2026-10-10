"""Rendering one beat as its own Manim scene (report §5.3.4).

Each beat of a module is rendered as a separate scene, so the beats can render in parallel
worker processes. A beat does not inherit the objects of the beat before it, so the scene first
replays the earlier beats in a skipped section: their objects are added without being rendered,
and the beat's video starts from exactly the picture the previous beat ended on.

`render_beat` runs in a worker process, so its input and output are plain picklable data.
"""

import time
from dataclasses import dataclass, field
from pathlib import Path

from manim import Scene, tempconfig

from app.contracts import Level
from app.primitives.library import get_primitive
from app.renderer.errors import LayoutViolation, RenderError
from app.renderer.layout import layout_problems
from app.renderer.tex_cache import use_shared_tex_cache

# Pixel size and frame rate of each render quality.
QUALITIES: dict[str, tuple[int, int, int]] = {
    "480p30": (854, 480, 30),
    "720p30": (1280, 720, 30),
    "1080p30": (1920, 1080, 30),
}

# Level 1 adds a short pause after each step (§5.4.4).
LEVEL_1_STEP_PAUSE_S = 0.6


@dataclass(frozen=True)
class BeatJob:
    index: int
    level: int
    primitive_id: str
    params: dict
    run_times: list[float]
    previous: list[tuple[str, dict]]
    """The primitive id and parameters of every earlier beat, replayed to rebuild the screen."""
    work_dir: str
    tex_dir: str
    quality: str = "720p30"


@dataclass
class BeatResult:
    index: int
    video: str
    duration_s: float
    step_times: list[tuple[float, float]] = field(default_factory=list)
    """Start and end of each step, in seconds from the start of the beat's video."""
    render_seconds: float = 0.0


class BeatScene(Scene):
    def __init__(self, job: BeatJob, **kwargs):
        super().__init__(**kwargs)
        self.job = job
        self.step_times: list[tuple[float, float]] = []
        self.beat_start = 0.0

    def construct(self) -> None:
        job, level = self.job, Level(self.job.level)

        self.next_section("previous beats", skip_animations=True)
        carried: dict = {}
        for primitive_id, raw in job.previous:
            primitive = get_primitive(primitive_id)
            params = primitive.parse_params(raw)
            run_times = [step.min_run_time_s for step in primitive.steps(params, level)]
            last = carried
            for visible in primitive.animate(self, params, level, run_times, carried):
                last = visible
            carried = dict(last)

        self.next_section("beat")
        self.beat_start = self.time
        primitive = get_primitive(job.primitive_id)
        params = primitive.parse_params(job.params)
        start = 0.0
        for step, visible in enumerate(
            primitive.animate(self, params, level, job.run_times, carried)
        ):
            end = self.time - self.beat_start
            self.step_times.append((start, end))
            problems = layout_problems(visible, primitive.layout, carried=carried.keys())
            if problems:
                raise LayoutViolation(
                    f"{job.primitive_id}, beat {job.index}, step {step + 1}: " + "; ".join(problems)
                )
            if level is Level.SUPPORTED:
                self.wait(LEVEL_1_STEP_PAUSE_S)
            start = self.time - self.beat_start
        if len(self.step_times) != len(job.run_times):
            raise RenderError(
                f"{job.primitive_id} played {len(self.step_times)} steps, "
                f"expected {len(job.run_times)}"
            )


def render_beat(job: BeatJob) -> BeatResult:
    """Render one beat to a silent video. Runs in a worker process."""
    width, height, fps = QUALITIES[job.quality]
    use_shared_tex_cache(Path(job.tex_dir))
    options = {
        "media_dir": job.work_dir,
        "tex_dir": str(Path(job.work_dir) / "tex"),
        "disable_caching": True,
        "pixel_width": width,
        "pixel_height": height,
        "frame_rate": fps,
        "verbosity": "ERROR",
        "progress_bar": "none",
        "output_file": f"beat_{job.index}",
    }
    started = time.perf_counter()
    with tempconfig(options):
        scene = BeatScene(job)
        scene.render()
        video = Path(scene.renderer.file_writer.movie_file_path)
        duration = scene.time - scene.beat_start
    if not video.is_file():
        raise RenderError(f"Manim produced no video for beat {job.index}")
    return BeatResult(
        index=job.index,
        video=str(video),
        duration_s=duration,
        step_times=scene.step_times,
        render_seconds=time.perf_counter() - started,
    )
