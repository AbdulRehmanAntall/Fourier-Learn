"""Render a module: narration first, animation fitted to it, beats in parallel, then joined.

For one `ModuleRenderRequest` (report §5.3.4, §5.4.4, §5.5):

1. Check every beat's parameters against its primitive (schema and SymPy predicates).
2. Synthesise each step's passage at the level's speech rate and measure it.
3. Give each step the larger of its passage's duration and its minimum time at the level.
4. Render every beat as its own Manim scene, in parallel worker processes; each beat is
   reported through `on_beat_ready` as soon as it is stored, so playback can start on it.
5. Lay each beat's passages on an audio track at the steps' actual start times and mux it in.
6. Join the beats with FFmpeg once all are present, and write the manifest.

The result is stored under media/variants/<cache key>/. A later request with the same key is
served from there without rendering. After an "I'm Lost" press, `render_from_beat` renders
only the beats from the current one onward; they join the same variant.
"""

import json
import multiprocessing
import os
import shutil
import tempfile
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from app.audio_pipeline.tts import Clip, TTSProvider, synthesize
from app.contracts import (
    BeatManifest,
    ChipInterval,
    ModuleManifest,
    ModuleRenderRequest,
    StepTiming,
    variant_cache_key,
)
from app.primitives.library import UnknownPrimitiveError, get_primitive
from app.renderer import media
from app.renderer.beat import QUALITIES, BeatJob, BeatResult, render_beat
from app.renderer.errors import InvalidParameters, NarrationMismatch, RenderError
from app.renderer.store import (
    MANIFEST_FILE,
    MODULE_FILE,
    load_manifest,
    variant_directory,
    write_atomically,
)


@dataclass
class RenderResult:
    manifest: ModuleManifest
    directory: Path
    """The variant's directory; manifest paths are relative to it."""
    cache_hit: bool
    rendered_beats: list[int] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    """Seconds spent: tts, render (wall clock), first_beat (until the first beat was stored),
    total, and beat_<i> for each beat's own render."""


def render_module(
    request: ModuleRenderRequest,
    *,
    media_dir: Path,
    tts: TTSProvider,
    library_version: str,
    quality: str = "720p30",
    workers: int = 0,
    on_beat_ready: Callable[[BeatManifest], None] | None = None,
    force: bool = False,
) -> RenderResult:
    started = time.perf_counter()
    if quality not in QUALITIES:
        raise RenderError(f"unknown quality {quality!r}; choose from {sorted(QUALITIES)}")
    if request.library_version != library_version:
        raise RenderError(
            f"request was validated against primitive library {request.library_version}, "
            f"but this is {library_version}"
        )

    key = variant_cache_key(request)
    directory = variant_directory(media_dir, key)
    existing = load_manifest(directory)
    stored = {beat.index: beat for beat in existing.beats} if existing else {}
    if force:
        # Re-render the requested beats; earlier beats stay valid, since a beat's video
        # depends only on the beats up to it.
        stored = {i: beat for i, beat in stored.items() if i < request.render_from_beat}
    todo = [i for i in range(request.render_from_beat, len(request.beats)) if i not in stored]
    if not todo and existing is not None:
        timings = {"total": time.perf_counter() - started}
        return RenderResult(existing, directory, cache_hit=True, timings=timings)

    steps = _check_beats(request, todo)

    tts_started = time.perf_counter()
    clips = {
        i: [
            synthesize(tts, passage, request.voice, request.level, media_dir / "tts")
            for passage in request.beats[i].narration
        ]
        for i in todo
    }
    timings = {"tts": time.perf_counter() - tts_started}

    (directory / "beats").mkdir(parents=True, exist_ok=True)
    (media_dir / "tmp").mkdir(parents=True, exist_ok=True)
    new_beats: dict[int, BeatManifest] = {}
    render_started = time.perf_counter()

    def finish(result: BeatResult) -> None:
        beat = _store_beat(request, result, clips[result.index], directory)
        new_beats[result.index] = beat
        timings[f"beat_{result.index}"] = result.render_seconds
        if result.index == todo[0]:
            timings["first_beat"] = time.perf_counter() - started
        if on_beat_ready is not None:
            on_beat_ready(beat)

    try:
        with tempfile.TemporaryDirectory(dir=media_dir / "tmp") as work:
            jobs = [
                BeatJob(
                    index=i,
                    level=int(request.level),
                    primitive_id=request.beats[i].primitive_id,
                    params=request.beats[i].params,
                    run_times=[
                        max(clip.duration_s, step.min_run_time_s)
                        for clip, step in zip(clips[i], steps[i], strict=True)
                    ],
                    previous=[(beat.primitive_id, beat.params) for beat in request.beats[:i]],
                    work_dir=str(Path(work) / f"beat_{i}"),
                    tex_dir=str(media_dir / "tex"),
                    quality=quality,
                )
                for i in todo
            ]
            _render_in_parallel(jobs, workers, finish)
    except BaseException:
        # Leave no half-rendered variant behind: drop this call's beats, and the directory
        # itself unless an earlier render already stored a manifest there.
        for beat in new_beats.values():
            (directory / beat.video).unlink(missing_ok=True)
        if not (directory / MANIFEST_FILE).exists():
            shutil.rmtree(directory, ignore_errors=True)
        raise
    timings["render"] = time.perf_counter() - render_started

    beats = sorted([*stored.values(), *new_beats.values()], key=lambda beat: beat.index)
    complete = beats[0].index == 0 and len(beats) == len(request.beats)
    if complete:
        _join_beats(directory, beats)
    manifest = ModuleManifest(
        cache_key=key,
        level=request.level,
        voice=request.voice,
        library_version=request.library_version,
        beat_count=len(request.beats),
        beats=beats,
        module_video=MODULE_FILE if complete else None,
    )
    write_atomically(directory / MANIFEST_FILE, manifest.model_dump_json(indent=2))
    timings["total"] = time.perf_counter() - started
    return RenderResult(manifest, directory, cache_hit=False, rendered_beats=todo, timings=timings)


def _check_beats(request: ModuleRenderRequest, todo: Sequence[int]) -> dict[int, list]:
    """Validate every beat (earlier beats are replayed, so they must be valid too), and check
    that each beat to render has one narration passage per step. Returns those steps."""
    steps = {}
    for i, beat in enumerate(request.beats):
        try:
            primitive = get_primitive(beat.primitive_id)
            params = primitive.parse_params(beat.params)
        except (UnknownPrimitiveError, ValueError) as error:
            raise InvalidParameters(f"beat {i}: {error}") from error
        failures = primitive.validate(params)
        if failures:
            details = "; ".join(f"{f.predicate}: {f.message}" for f in failures)
            raise InvalidParameters(f"beat {i} ({beat.primitive_id}): {details}")
        if i in todo:
            steps[i] = primitive.steps(params, request.level)
            if len(steps[i]) != len(beat.narration):
                raise NarrationMismatch(
                    f"beat {i} ({beat.primitive_id}) has {len(steps[i])} steps at "
                    f"{request.level.label} but {len(beat.narration)} narration passages"
                )
    return steps


def _render_in_parallel(
    jobs: list[BeatJob], workers: int, on_result: Callable[[BeatResult], None]
) -> None:
    workers = min(workers or os.cpu_count() or 1, len(jobs))
    # "spawn" starts each worker fresh, which Manim's global configuration needs, and behaves
    # the same on Windows, macOS and Linux.
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
        futures = [pool.submit(render_beat, job) for job in jobs]
        try:
            for future in as_completed(futures):
                on_result(future.result())
        except BaseException:
            for future in futures:
                future.cancel()
            raise


def _store_beat(
    request: ModuleRenderRequest, result: BeatResult, clips: list[Clip], directory: Path
) -> BeatManifest:
    spec = request.beats[result.index]
    video = directory / "beats" / f"{result.index}.mp4"
    audio = video.with_suffix(".wav")
    media.build_audio_track(
        clips, [start for start, _ in result.step_times], result.duration_s, audio
    )
    media.run(media.mux_command(Path(result.video), audio, video))
    audio.unlink()
    return BeatManifest(
        index=result.index,
        primitive_id=spec.primitive_id,
        video=f"beats/{result.index}.mp4",
        duration_s=round(result.duration_s, 3),
        steps=[
            StepTiming(start_s=round(start, 3), end_s=round(end, 3), narration=passage)
            for (start, end), passage in zip(result.step_times, spec.narration, strict=True)
        ],
        chips=[
            ChipInterval(term=term, start_s=0.0, end_s=round(result.duration_s, 3))
            for term in spec.glossary_terms
        ],
        concept_ids=spec.concept_ids,
    )


def _join_beats(directory: Path, beats: Sequence[BeatManifest]) -> None:
    list_file = directory / "beats.txt"
    list_file.write_text(media.concat_list([directory / beat.video for beat in beats]))
    media.run(media.concat_command(list_file, directory / MODULE_FILE))
    list_file.unlink()


def request_from_file(path: Path) -> ModuleRenderRequest:
    return ModuleRenderRequest.model_validate(json.loads(path.read_text(encoding="utf-8")))
