"""Speech synthesis for narration (report §5.4).

Every provider writes the same canonical format (mono, 16-bit PCM WAV at `SAMPLE_RATE`), so the
render engine can place clips on a beat's audio track without resampling. Clips are cached by
provider, voice, speech rate and text, so a passage is synthesised once.

Providers:
- `KokoroTTS`: the local Kokoro-82M neural voice (Apache 2.0). Free and offline, and far more
  natural than espeak-ng. Its model files are downloaded on first use.
- `EspeakTTS`: the local espeak-ng voice. Free and offline, but robotic.
- `FakeTTS`: silent clips whose length follows the word count. Used by tests and CI.

A hosted voice is added as another `TTSProvider` once one is chosen (see docs/PLAN.md, Phase 1).
"""

import hashlib
import json
import shutil
import subprocess
import tempfile
import urllib.request
import uuid
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import numpy as np

from app.contracts import Level
from app.core.config import get_settings

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


class KokoroTTS(TTSProvider):
    """The local Kokoro-82M voice (https://github.com/thewh1teagle/kokoro-onnx).

    Runs on the CPU with ONNX Runtime. The model (about 330 MB) and the voices file are downloaded
    into `settings.tts_model_dir` on first use. Kokoro speaks at SAMPLE_RATE already, so its audio
    is written as is.
    """

    name = "kokoro"
    RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
    MODEL = "kokoro-v1.0.onnx"
    VOICES_FILE = "voices-v1.0.bin"
    # Lessons follow the Cambridge syllabus, so "default" is a British English voice.
    VOICES = {"default": "bf_emma"}

    def __init__(self, model_dir: Path | None = None) -> None:
        self.model_dir = model_dir or get_settings().tts_model_dir
        self._kokoro = None

    def write_wav(self, text: str, voice: str, rate: float, out: Path) -> None:
        name = self.VOICES.get(voice, voice)
        # Voice names start with the accent: "b" British English, "a" American English.
        lang = "en-gb" if name.startswith("b") else "en-us"
        try:
            samples, sample_rate = self._model().create(text, voice=name, speed=rate, lang=lang)
        except (KeyError, ValueError) as error:
            raise TTSError(f"kokoro failed: {error}") from error
        if sample_rate != SAMPLE_RATE:
            raise TTSError(f"kokoro returned {sample_rate} Hz audio, expected {SAMPLE_RATE} Hz")
        pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
        with wave.open(str(out), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(pcm.tobytes())

    def _model(self):
        if self._kokoro is None:
            try:
                from kokoro_onnx import Kokoro
            except ImportError:
                raise TTSError("kokoro-onnx is not installed") from None
            model = self._download(self.MODEL)
            voices = self._download(self.VOICES_FILE)
            self._kokoro = Kokoro(str(model), str(voices))
        return self._kokoro

    def _download(self, filename: str) -> Path:
        path = self.model_dir / filename
        if not path.is_file():
            self.model_dir.mkdir(parents=True, exist_ok=True)
            partial = path.with_name(f"{filename}.{uuid.uuid4().hex}.partial")
            try:
                urllib.request.urlretrieve(f"{self.RELEASE}/{filename}", partial)
            except OSError as error:
                partial.unlink(missing_ok=True)
                raise TTSError(f"could not download {filename}: {error}") from error
            partial.replace(path)
        return path


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


PROVIDERS: dict[str, type[TTSProvider]] = {
    "kokoro": KokoroTTS,
    "espeak": EspeakTTS,
    "fake": FakeTTS,
}


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
