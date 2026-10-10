import wave

import pytest

from app.audio_pipeline.tts import (
    SAMPLE_RATE,
    SPEECH_RATE,
    FakeTTS,
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
