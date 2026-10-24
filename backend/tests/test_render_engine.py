import shutil

import pytest

from app.audio_pipeline.tts import FakeTTS
from app.contracts import ModuleRenderRequest
from app.primitives.library import LIBRARY_VERSION
from app.renderer import media
from app.renderer.engine import render_module
from app.renderer.errors import (
    InvalidParameters,
    LayoutViolation,
    NarrationMismatch,
    RenderError,
)
from app.renderer.store import load_manifest, variant_directory


def request(**overrides):
    return ModuleRenderRequest.model_validate(
        {
            "module_id": 1,
            "level": 3,
            "voice": "default",
            "library_version": LIBRARY_VERSION,
            "beats": [
                {
                    "primitive_id": "GradientTriangle",
                    "params": {"point_a": [1, 2], "point_b": [4, 8]},
                    "narration": ["The line through two points.", "The gradient is 2."],
                    "glossary_terms": ["gradient"],
                    "concept_ids": [12],
                },
                {
                    "primitive_id": "EquationTransform",
                    "params": {"expressions": ["(8 - 2)/(4 - 1)", "6/3", "2"]},
                    "narration": ["Eight minus two over four minus one.", "Which is 2."],
                    "concept_ids": [12],
                },
            ],
        }
        | overrides
    )


def render(req, tmp_path, **kwargs):
    return render_module(
        req,
        media_dir=tmp_path,
        tts=FakeTTS(),
        library_version=LIBRARY_VERSION,
        quality="480p30",
        **kwargs,
    )


def test_invalid_beats_are_refused_before_anything_renders(tmp_path):
    bad_maths = request().model_dump()
    bad_maths["beats"][1]["params"]["expressions"][1] = "6/4"
    with pytest.raises(InvalidParameters, match="line 2 is not equivalent"):
        render(ModuleRenderRequest.model_validate(bad_maths), tmp_path)

    unknown = request().model_dump()
    unknown["beats"][0]["primitive_id"] = "TangentSlide"
    with pytest.raises(InvalidParameters, match="TangentSlide"):
        render(ModuleRenderRequest.model_validate(unknown), tmp_path)

    short = request().model_dump()
    short["beats"][0]["narration"] = ["Only one passage."]
    with pytest.raises(NarrationMismatch, match="2 steps at Level 3 but 1 narration"):
        render(ModuleRenderRequest.model_validate(short), tmp_path)

    with pytest.raises(RenderError, match="primitive library"):
        render(request(library_version="0.0.1"), tmp_path)
    assert not (tmp_path / "variants").exists()


needs_renderer = pytest.mark.skipif(
    not all(shutil.which(tool) for tool in ("ffmpeg", "ffprobe", "latex", "dvisvgm")),
    reason="needs FFmpeg and LaTeX (they are in the Docker image)",
)


@pytest.mark.render
@needs_renderer
def test_partial_render_after_im_lost_then_full_module_then_cache(tmp_path):
    ready = []
    partial = render(request(render_from_beat=1), tmp_path, on_beat_ready=ready.append)
    assert [beat.index for beat in partial.manifest.beats] == [1]
    assert not partial.manifest.is_complete
    assert partial.manifest.module_video is None
    assert [beat.index for beat in ready] == [1]

    # While the rest renders, the manifest on disk always lists beats a player can play in order.
    published = []

    def check_published(beat):
        directory = variant_directory(tmp_path, partial.manifest.cache_key)
        published.append([b.index for b in load_manifest(directory).beats])

    full = render(request(), tmp_path, on_beat_ready=check_published)
    assert published == [[0, 1]]
    assert full.rendered_beats == [0]  # beat 1 was already in the variant
    manifest = full.manifest
    assert manifest.is_complete
    assert full.directory == variant_directory(tmp_path, manifest.cache_key)

    for beat in manifest.beats:
        video = full.directory / beat.video
        assert media.probe_duration(video) == pytest.approx(beat.duration_s, abs=0.05)
        assert beat.steps[0].start_s == 0
        assert beat.steps[-1].end_s <= beat.duration_s
    module_video = full.directory / manifest.module_video
    assert media.probe_duration(module_video) == pytest.approx(manifest.duration_s, abs=0.1)

    again = render(request(), tmp_path)
    assert again.cache_hit
    assert again.manifest == manifest

    # Forcing a re-render from beat 1 replaces beat 1 only and keeps the module complete.
    forced = render(request(render_from_beat=1), tmp_path, force=True)
    assert forced.rendered_beats == [1]
    assert forced.manifest.is_complete


@pytest.mark.render
@needs_renderer
def test_layout_violation_names_the_objects(tmp_path):
    crowded = request().model_dump()
    crowded["beats"] = [
        {
            "primitive_id": "FunctionGraph",
            "params": {"expression": "2*x", "x_min": -1, "x_max": 5, "marked_x": [1, 1.1]},
            "narration": ["The graph.", "Two points very close together."],
        }
    ]
    with pytest.raises(LayoutViolation, match="point_1 overlaps point_2"):
        render(ModuleRenderRequest.model_validate(crowded), tmp_path)
    assert list((tmp_path / "variants").iterdir()) == []  # nothing half-rendered is kept
