"""Speech synthesis for narration (report §5.4).

Every provider writes the same canonical format (mono, 16-bit PCM WAV at `SAMPLE_RATE`), so the
render engine can place clips on a beat's audio track without resampling. Clips are cached by
provider, voice, speech rate and text, so a passage is synthesised once.

Providers:
- `EspeakTTS`: the local espeak-ng voice. Free and offline; good enough for development.
- `FakeTTS`: silent clips whose length follows the word count. Used by tests and CI.

A hosted voice is added as another `TTSProvider` once one is chosen (see docs/PLAN.md, Phase 1).
"""

import hashlib
import json
import shutil
import subprocess
import tempfile
import uuid
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from app.contracts import Level

SAMPLE_RATE = 24_000

# Speech rate of each level relative to the reference rate (Table 5.3): Level 1 slower than the
# reference, Level 2 at the reference rate, Level 3 faster.
SPEECH_RATE: dict[Level, float] = {
    Level.SUPPORTED: 0.85,
    Level.STANDARD: 1.0,
    Level.CONCISE: 1.15,
}


class TTSError(RuntimeError):
    pass


@dataclass(frozen=True)
class Clip:
    path: Path
    duration_s: float


class TTSProvider(ABC):
    name: ClassVar[str]

    @abstractmethod
    def write_wav(self, text: str, voice: str, rate: float, out: Path) -> None:
        """Synthesise `text` into `out` as canonical WAV (mono, 16-bit, SAMPLE_RATE)."""


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / wav.getframerate()


def write_silence(path: Path, duration_s: float) -> None:
    frames = round(duration_s * SAMPLE_RATE)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"\x00\x00" * frames)


class FakeTTS(TTSProvider):
    """Silent clips at a typical narration pace. Needs no voice, network or API key."""

    name = "fake"
    WORDS_PER_MINUTE = 150

    def write_wav(self, text: str, voice: str, rate: float, out: Path) -> None:
        words = max(1, len(text.split()))
        write_silence(out, max(0.5, words * 60 / (self.WORDS_PER_MINUTE * rate)))


class EspeakTTS(TTSProvider):
    """The local espeak-ng voice (https://github.com/espeak-ng/espeak-ng)."""

    name = "espeak"
    WORDS_PER_MINUTE = 160
    # Lessons follow the Cambridge syllabus, so "default" is British English.
    VOICES = {"default": "en-gb"}

    def write_wav(self, text: str, voice: str, rate: float, out: Path) -> None:
        for tool in ("espeak-ng", "ffmpeg"):
            if shutil.which(tool) is None:
                raise TTSError(f"{tool} is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw.wav"
            espeak = [
                "espeak-ng",
                "-v",
                self.VOICES.get(voice, voice),
                "-s",
                str(round(self.WORDS_PER_MINUTE * rate)),
                "-w",
                str(raw),
                "--stdin",
            ]
            _run(espeak, stdin=text)
            _run(_to_canonical_wav(raw, out))


def _to_canonical_wav(source: Path, out: Path) -> list[str]:
    return [
        "ffmpeg",
        "-nostdin",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE),
        "-sample_fmt",
        "s16",
        str(out),
    ]


def _run(command: list[str], stdin: str | None = None) -> None:
    result = subprocess.run(command, input=stdin, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise TTSError(f"{command[0]} failed: {result.stderr.strip()[:500]}")


PROVIDERS: dict[str, type[TTSProvider]] = {"espeak": EspeakTTS, "fake": FakeTTS}


def get_provider(name: str) -> TTSProvider:
    try:
        return PROVIDERS[name]()
    except KeyError:
        raise TTSError(f"unknown TTS provider {name!r}; choose from {sorted(PROVIDERS)}") from None


def synthesize(provider: TTSProvider, text: str, voice: str, level: Level, cache_dir: Path) -> Clip:
    """The clip of one narration passage at a level's speech rate, from the cache if present."""
    rate = SPEECH_RATE[level]
    key = json.dumps([provider.name, voice, rate, text], ensure_ascii=False)
    path = cache_dir / f"{hashlib.sha256(key.encode()).hexdigest()}.wav"
    if not path.is_file():
        cache_dir.mkdir(parents=True, exist_ok=True)
        # A unique name, so two processes synthesising the same passage do not collide.
        partial = path.with_name(f"{path.stem}.{uuid.uuid4().hex}.partial.wav")
        provider.write_wav(text, voice, rate, partial)
        partial.replace(path)
    return Clip(path=path, duration_s=wav_duration(path))
