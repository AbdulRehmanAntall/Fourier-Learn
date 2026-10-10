"""FastAPI application entry point: `uvicorn app.main:app --reload --port 8000`."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes import health, variants
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings().media_dir.mkdir(parents=True, exist_ok=True)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="FourierLearn API", version=__version__, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(variants.router, prefix="/api")
    # Rendered beats and modules; manifests give paths relative to media/variants/<key>/.
    app.mount("/media", StaticFiles(directory=settings.media_dir, check_dir=False), name="media")
    return app


app = create_app()
