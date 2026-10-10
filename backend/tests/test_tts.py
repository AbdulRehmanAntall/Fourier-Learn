import wave

import numpy as np
import pytest

from app.audio_pipeline.tts import (
    SAMPLE_RATE,
    SPEECH_RATE,
    FakeTTS,
    KokoroTTS,
    TTSError,
    get_provider,
    synthesize,
    wav_duration,
)
from app.contracts import Level


def test_levels_speak_slower_to_faster():
    assert SPEECH_RATE[Level.SUPPORTED] < SPEECH_RATE[Level.STANDARD] < SPEECH_RATE[Level.CONCISE]


def test_fake_clips_are_canonical_wav_and_follow_the_speech_rate(tmp_path):
    text = "one two three four five six seven eight nine ten"
    clips = {level: synthesize(FakeTTS(), text, "default", level, tmp_path) for level in Level}
    assert clips[Level.SUPPORTED].duration_s > clips[Level.STANDARD].duration_s
    assert clips[Level.STANDARD].duration_s > clips[Level.CONCISE].duration_s
    assert clips[Level.STANDARD].duration_s == pytest.approx(4.0)
    with wave.open(str(clips[Level.STANDARD].path)) as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, SAMPLE_RATE)


def test_clips_are_cached_by_text_voice_and_rate(tmp_path):
    class CountingTTS(FakeTTS):
        calls = 0

        def write_wav(self, text, voice, rate, out):
            CountingTTS.calls += 1
            super().write_wav(text, voice, rate, out)

    tts = CountingTTS()
    first = synthesize(tts, "the gradient is 2", "default", Level.STANDARD, tmp_path)
    again = synthesize(tts, "the gradient is 2", "default", Level.STANDARD, tmp_path)
    synthesize(tts, "the gradient is 2", "default", Level.CONCISE, tmp_path)
    assert first.path == again.path
    assert CountingTTS.calls == 2
    assert wav_duration(first.path) == first.duration_s
    assert not list(tmp_path.glob("*.partial.wav"))


def test_unknown_provider_is_refused():
    with pytest.raises(TTSError, match="unknown TTS provider"):
        get_provider("nonexistent")


def test_kokoro_writes_canonical_wav_in_the_voice_accent(tmp_path):
    class StubKokoro:
        def create(self, text, voice, speed, lang):
            StubKokoro.call = (voice, speed, lang)
            return np.full(SAMPLE_RATE // 2, 0.5, dtype=np.float32), SAMPLE_RATE

    tts = KokoroTTS(model_dir=tmp_path)
    tts._kokoro = StubKokoro()
    clip = synthesize(tts, "the gradient is 2", "default", Level.SUPPORTED, tmp_path)
    assert StubKokoro.call == ("bf_emma", SPEECH_RATE[Level.SUPPORTED], "en-gb")
    assert clip.duration_s == pytest.approx(0.5)
    with wave.open(str(clip.path)) as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, SAMPLE_RATE)

    synthesize(tts, "the gradient is 2", "am_michael", Level.STANDARD, tmp_path)
    assert StubKokoro.call == ("am_michael", 1.0, "en-us")
