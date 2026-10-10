import pytest
from pydantic import TypeAdapter, ValidationError

from app.contracts import (
    BeatReady,
    InteractionEventBatch,
    InteractionType,
    ModuleFailed,
    PauseEvent,
    SpeedChangeEvent,
    StreamEvent,
    encode_sse,
)

AT = "2026-10-10T10:00:00+05:00"


def event(type_, **fields):
    return {"type": type_, "module_id": 3, "occurred_at": AT} | fields


def test_event_types_are_those_of_the_data_dictionary():
    assert {t.value for t in InteractionType} == {
        "rewind",
        "speed_change",
        "pause",
        "chip_view",
        "im_lost",
        "branch_choice",
    }


def test_a_batch_parses_each_event_by_its_type():
    batch = InteractionEventBatch.model_validate(
        {
            "events": [
                event("rewind", beat_index=1, position_s=4, to_beat_index=1, to_position_s=1),
                event("speed_change", beat_index=1, position_s=5, from_rate=1, to_rate=0.75),
                event("pause", beat_index=1, position_s=6, duration_s=12.5),
                event("chip_view", beat_index=1, position_s=7, term="tangent"),
                event("im_lost", beat_index=2, position_s=1),
                event("branch_choice", option="worked_example"),
            ]
        }
    )
    kinds = [type(e).__name__ for e in batch.events]
    assert kinds == [
        "RewindEvent",
        "SpeedChangeEvent",
        "PauseEvent",
        "ChipViewEvent",
        "ImLostEvent",
        "BranchChoiceEvent",
    ]
    assert batch.events[1].slowed is True


def test_speed_up_is_distinguished_from_slowing_down_by_the_rates():
    sped_up = SpeedChangeEvent.model_validate(
        event("speed_change", beat_index=0, position_s=2, from_rate=1, to_rate=1.5)
    )
    assert sped_up.slowed is False
    with pytest.raises(ValidationError, match="change the rate"):
        SpeedChangeEvent.model_validate(
            event("speed_change", beat_index=0, position_s=2, from_rate=1, to_rate=1)
        )


def test_a_rewind_must_go_back():
    adapter = TypeAdapter(InteractionEventBatch)
    forward = event("rewind", beat_index=1, position_s=4, to_beat_index=1, to_position_s=9)
    with pytest.raises(ValidationError, match="earlier point"):
        adapter.validate_python({"events": [forward]})
    into_previous_beat = event(
        "rewind", beat_index=1, position_s=1, to_beat_index=0, to_position_s=15
    )
    assert adapter.validate_python({"events": [into_previous_beat]}).events[0].to_beat_index == 0


def test_events_need_a_timezone_and_playback_events_need_a_beat():
    with pytest.raises(ValidationError):
        PauseEvent.model_validate(
            event("pause", beat_index=0, position_s=1, duration_s=3)
            | {"occurred_at": "2026-10-10T10:00:00"}
        )
    with pytest.raises(ValidationError):
        PauseEvent.model_validate(event("pause", position_s=1, duration_s=3))


def test_events_never_carry_the_student():
    with pytest.raises(ValidationError):
        InteractionEventBatch.model_validate(
            {"events": [event("im_lost", beat_index=0, position_s=1, student_id=7)]}
        )


def test_stream_events_encode_as_server_sent_events():
    ready = BeatReady(lesson_id=1, module_id=2, level=2, beat_index=0, cache_key="abc")
    message = encode_sse(ready)
    assert message.startswith("event: beat_ready\ndata: {")
    assert message.endswith("\n\n")

    data = message.split("data: ", 1)[1].strip()
    parsed = TypeAdapter(StreamEvent).validate_json(data)
    assert parsed == ready

    failed = ModuleFailed(lesson_id=1, module_id=2, fallback="glossary_definition", message="x")
    assert TypeAdapter(StreamEvent).validate_json(failed.model_dump_json()) == failed
