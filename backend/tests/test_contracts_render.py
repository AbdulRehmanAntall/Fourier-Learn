import pytest
from pydantic import ValidationError

from app.contracts import Level, ModuleManifest, ModuleRenderRequest, variant_cache_key


def beat(**overrides):
    return {
        "primitive_id": "FunctionGraph",
        "params": {"f": "x**2", "x_min": -3, "x_max": 3},
        "narration": ["Here is the graph of x squared."],
    } | overrides


def request(**overrides):
    return ModuleRenderRequest.model_validate(
        {
            "module_id": 1,
            "level": 2,
            "voice": "default",
            "library_version": "0.1.0",
            "beats": [beat(), beat(primitive_id="TangentSlide")],
        }
        | overrides
    )


def test_level_is_read_from_its_number():
    assert request().level is Level.STANDARD


def test_narration_slots_must_be_filled_before_rendering():
    with pytest.raises(ValidationError, match=r"\{gradient\}"):
        request(beats=[beat(narration=["The gradient here is {gradient}."])])


def test_render_from_beat_must_name_a_beat():
    assert request(render_from_beat=1).render_from_beat == 1
    with pytest.raises(ValidationError):
        request(render_from_beat=2)


def test_cache_key_depends_on_exactly_the_five_fields_of_the_report():
    key = variant_cache_key(request())
    assert len(key) == 64

    # Same primitives, parameters, level, voice and library version: same variant.
    assert variant_cache_key(request(module_id=9)) == key
    assert variant_cache_key(request(render_from_beat=1)) == key
    reworded = [beat(narration=["Another sentence."]), beat(primitive_id="TangentSlide")]
    assert variant_cache_key(request(beats=reworded)) == key
    reordered = [
        beat(params={"x_max": 3, "x_min": -3, "f": "x**2"}),
        beat(primitive_id="TangentSlide"),
    ]
    assert variant_cache_key(request(beats=reordered)) == key

    # Any of the five changing gives a different variant.
    assert variant_cache_key(request(level=1)) != key
    assert variant_cache_key(request(voice="other")) != key
    assert variant_cache_key(request(library_version="0.2.0")) != key
    assert variant_cache_key(request(beats=[beat(), beat()])) != key
    changed = [
        beat(params={"f": "x**3", "x_min": -3, "x_max": 3}),
        beat(primitive_id="TangentSlide"),
    ]
    assert variant_cache_key(request(beats=changed)) != key


def beat_manifest(index, duration=20.0, **overrides):
    return {
        "index": index,
        "primitive_id": "FunctionGraph",
        "video": f"beats/{index}.mp4",
        "duration_s": duration,
        "steps": [
            {"start_s": 0.0, "end_s": 8.0, "narration": "First step."},
            {"start_s": 8.0, "end_s": duration, "narration": "Second step."},
        ],
        "chips": [{"term": "gradient", "start_s": 0.0, "end_s": duration}],
        "concept_ids": [12],
    } | overrides


def manifest(beats, beat_count=3, **overrides):
    return ModuleManifest.model_validate(
        {
            "cache_key": "abc",
            "level": 2,
            "voice": "default",
            "library_version": "0.1.0",
            "beat_count": beat_count,
            "beats": beats,
        }
        | overrides
    )


def test_complete_manifest_gives_module_offsets_and_duration():
    complete = manifest([beat_manifest(0), beat_manifest(1, 25.0), beat_manifest(2, 15.0)])
    assert complete.is_complete
    assert complete.beat_offsets_s() == [0.0, 20.0, 45.0]
    assert complete.duration_s == 60.0
    assert complete.beat(1).duration_s == 25.0


def test_manifest_after_im_lost_holds_beats_from_j_onward():
    partial = manifest([beat_manifest(1), beat_manifest(2)])
    assert not partial.is_complete
    assert partial.beat(2).index == 2
    with pytest.raises(KeyError):
        partial.beat(0)
    with pytest.raises(ValueError):
        partial.beat_offsets_s()
    with pytest.raises(ValidationError, match="module_video"):
        manifest([beat_manifest(1), beat_manifest(2)], module_video="module.mp4")


def test_manifest_beats_are_in_order_without_gaps():
    with pytest.raises(ValidationError, match="gaps"):
        manifest([beat_manifest(0), beat_manifest(2)])
    with pytest.raises(ValidationError, match="beyond"):
        manifest([beat_manifest(0), beat_manifest(1)], beat_count=1)


def test_steps_and_chips_stay_inside_their_beat():
    late_step = beat_manifest(0, steps=[{"start_s": 0.0, "end_s": 30.0, "narration": "Too long."}])
    with pytest.raises(ValidationError, match="ends after the beat"):
        manifest([late_step], beat_count=1)

    overlapping = beat_manifest(
        0,
        steps=[
            {"start_s": 0.0, "end_s": 10.0, "narration": "One."},
            {"start_s": 5.0, "end_s": 12.0, "narration": "Two."},
        ],
    )
    with pytest.raises(ValidationError, match="in order"):
        manifest([overlapping], beat_count=1)

    late_chip = beat_manifest(0, chips=[{"term": "gradient", "start_s": 0.0, "end_s": 21.0}])
    with pytest.raises(ValidationError, match="chip"):
        manifest([late_chip], beat_count=1)
