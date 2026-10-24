"""FastAPI application entry point: `uvicorn app.main:app --reload --port 8000`."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from pydantic import TypeAdapter

from app import __version__
from app.api.database import track_source
from app.api.routes import admin, auth, events, health, learner, lessons, variants
from app.contracts.stream import StreamEvent
from app.core.config import get_settings
from app.stub.fixtures import install_fixture_variants

# Endpoints served by real code, not the stub (docs/frontend.md §8). The rest of /api is stub.
REAL_PATHS = ("/api/health", "/api/variants/", "/api/dev/variants", "/api/dev/render")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    if settings.stub_api:
        install_fixture_variants(settings.media_dir)
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
    if settings.stub_api:
        for module in (auth, learner, lessons, events, admin):
            app.include_router(module.router, prefix="/api")

        @app.middleware("http")
        async def mark_stub(request: Request, call_next):
            path = request.url.path
            is_stub = path.startswith("/api/") and not path.startswith(REAL_PATHS)
            if is_stub and settings.stub_latency_ms > 0:
                await asyncio.sleep(settings.stub_latency_ms / 1000)
            source = track_source()
            response = await call_next(request)
            # Endpoints that read the database (lessons made by POST /api/dev/render, seeded
            # topics and glossary) are not stub data, even on a stub-capable path.
            if is_stub and not source["database"]:
                response.headers["X-FourierLearn-Stub"] = "1"
            return response

    # Rendered beats and modules; manifests give paths relative to media/variants/<key>/.
    app.mount("/media", StaticFiles(directory=settings.media_dir, check_dir=False), name="media")
    app.openapi = lambda: _openapi(app)
    return app


def _openapi(app: FastAPI) -> dict:
    """The OpenAPI document, plus the Server-Sent Events payloads (`StreamEvent`), which no
    JSON route returns but the frontend needs types for."""
    if app.openapi_schema is None:
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        stream = TypeAdapter(StreamEvent).json_schema(ref_template="#/components/schemas/{model}")
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        components.update(stream.pop("$defs", {}))
        components["StreamEvent"] = stream
        app.openapi_schema = schema
    return app.openapi_schema


app = create_app()
