"""Application settings, loaded from environment variables and backend/.env."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# backend/ directory (this file is backend/app/core/config.py)
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://fourierlearn:fourierlearn@localhost:5433/fourierlearn"
    # Comma-separated list in .env, e.g. "http://localhost:3000,http://127.0.0.1:3000"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    # Relative paths are resolved against the backend/ directory.
    media_dir: Path = Path("media")

    # Narration voice: "kokoro" (local neural voice), "espeak" (local espeak-ng) or "fake"
    # (silent clips, for tests).
    tts_provider: str = "kokoro"
    # Where the Kokoro model files are downloaded on first use.
    tts_model_dir: Path = Path("models/kokoro")
    # Video quality of rendered beats: 480p30, 720p30 or 1080p30 (see docs/benchmarks.md).
    render_quality: str = "720p30"
    # Beats rendered in parallel. 0 means one per CPU core.
    render_workers: int = 0

    # Phase 2: serve the API from the in-memory stub (app/stub, docs/frontend.md §8).
    stub_api: bool = True
    # Delay added to every stub response, so the frontend's loading states show and get tested.
    stub_latency_ms: int = 300
    # Send the session cookie over HTTPS only. Turn on for any deployment served over HTTPS.
    session_cookie_secure: bool = False

    # Not used yet.
    llm_api_key: str = ""
    tts_api_key: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("media_dir", "tts_model_dir")
    @classmethod
    def _resolve_path(cls, value: Path) -> Path:
        return value if value.is_absolute() else BACKEND_DIR / value


@lru_cache
def get_settings() -> Settings:
    return Settings()
