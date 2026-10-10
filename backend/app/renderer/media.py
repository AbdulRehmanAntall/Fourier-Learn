"""Audio and video assembly with FFmpeg (report §5.3.4, §5.4.4)."""

import subprocess
import wave
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from app.audio_pipeline.tts import SAMPLE_RATE, Clip
from app.renderer.errors import MediaError


def build_audio_track(
    clips: Sequence[Clip], starts: Sequence[float], duration_s: float, out: Path
) -> None:
    """One WAV track of `duration_s`, with each clip starting at its step's start time.

    The animation is fitted to the audio, so each passage begins when its step begins and the
    silence after it lasts until the next step (§5.4.4).
    """
    track = np.zeros(round(duration_s * SAMPLE_RATE), dtype=np.int32)
    for clip, start in zip(clips, starts, strict=True):
        samples = _read_samples(clip.path)
        offset = round(start * SAMPLE_RATE)
        end = min(len(track), offset + len(samples))
        track[offset:end] += samples[: end - offset]
    with wave.open(str(out), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(np.clip(track, -32768, 32767).astype("<i2").tobytes())


def _read_samples(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, SAMPLE_RATE):
            raise MediaError(f"{path.name} is not mono 16-bit {SAMPLE_RATE} Hz audio")
        return np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.int32)


def mux_command(video: Path, audio: Path, out: Path) -> list[str]:
    """Video stream copied as is, narration encoded as AAC, ready to stream in a browser."""
    return [
        *_FFMPEG,
        "-i",
        str(video),
        "-i",
        str(audio),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        str(out),
    ]


def concat_command(list_file: Path, out: Path) -> list[str]:
    """Join beat videos that share encoding settings without re-encoding them."""
    return [
        *_FFMPEG,
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(out),
    ]


def concat_list(videos: Sequence[Path]) -> str:
    return "".join(f"file '{video.resolve().as_posix()}'\n" for video in videos)


def probe_duration(path: Path) -> float:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    return float(result.strip())


def run(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise MediaError(f"{command[0]} failed: {result.stderr.strip()[-800:]}")
    return result.stdout


_FFMPEG = ["ffmpeg", "-nostdin", "-loglevel", "error", "-y"]
