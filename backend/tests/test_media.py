"""Audio and video assembly. Needs neither Manim nor FFmpeg."""

import math
import wave

import numpy as np
import pytest

from app.audio_pipeline.tts import SAMPLE_RATE, Clip
from app.renderer import media


def tone(path, seconds):
    t = np.arange(round(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes((8000 * np.sin(2 * math.pi * 440 * t)).astype("<i2").tobytes())
    return Clip(path=path, duration_s=seconds)


def test_audio_track_places_each_passage_at_its_step_start(tmp_path):
    clips = [tone(tmp_path / "a.wav", 0.5), tone(tmp_path / "b.wav", 0.25)]
    out = tmp_path / "track.wav"
    media.build_audio_track(clips, [0.25, 1.5], 2.0, out)
    with wave.open(str(out)) as wav:
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
    assert len(samples) == 2 * SAMPLE_RATE
    loud = np.flatnonzero(np.abs(samples) > 100) / SAMPLE_RATE
    assert loud[0] == pytest.approx(0.25, abs=0.001)
    assert loud[loud < 1.0][-1] == pytest.approx(0.75, abs=0.001)
    assert loud[loud > 1.0][0] == pytest.approx(1.5, abs=0.001)


def test_ffmpeg_commands_keep_video_and_stream_well():
    mux = media.mux_command("v.mp4", "a.wav", "out.mp4")
    assert mux[mux.index("-c:v") + 1] == "copy"
    assert "+faststart" in mux
    concat = media.concat_command("list.txt", "module.mp4")
    assert concat[concat.index("-c") + 1] == "copy"
