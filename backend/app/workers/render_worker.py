"""A render worker (report §4.4.4): takes jobs from the queue and renders them.

    npm run worker            run until stopped (Ctrl+C finishes the current job first)
    npm run worker -- --once  render at most one job, then stop

Workers are stateless: everything a job needs is in its row, and every result goes to the media
folder and the database. Run more workers, on this machine or others sharing the database and
the media folder, to render more at once. Each job's beats are rendered in parallel processes
(RENDER_WORKERS), so on one machine a single worker usually keeps every core busy.
"""

import argparse
import os
import signal
import socket
import sys
import threading
import traceback
from collections.abc import Callable

from sqlalchemy.exc import SQLAlchemyError

from app.audio_pipeline.tts import TTSProvider, get_provider
from app.contracts import ModuleRenderRequest
from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.primitives.catalog import LIBRARY_VERSION
from app.scheduler import queue

Renderer = Callable[..., object]
"""render_module's signature; the tests pass a stand-in."""


def run(
    stop: threading.Event,
    *,
    once: bool = False,
    render: Renderer | None = None,
    tts: TTSProvider | None = None,
) -> int:
    """Take and render jobs until `stop` is set. Returns how many jobs were processed."""
    settings = get_settings()
    if render is None:
        from app.renderer.engine import render_module  # imports Manim

        render = render_module
    tts = tts or get_provider(settings.tts_provider)
    name = f"{socket.gethostname()}:{os.getpid()}"
    processed = 0
    waiting_for_database = False
    while not stop.is_set():
        try:
            with get_sessionmaker()() as db:
                job = queue.claim(db, name, settings.job_lease_s)
                db.commit()
                job_id = job.job_id if job else None
        except SQLAlchemyError as error:
            # Postgres is not up yet, or the tables are not created: wait, don't crash.
            if not waiting_for_database:
                print(
                    f"Waiting for the database ({type(error).__name__}). Is Postgres running, "
                    "and has npm run db:migrate been run?",
                    flush=True,
                )
                waiting_for_database = True
            if once:
                break
            stop.wait(5)
            continue
        if waiting_for_database:
            print("Database available.", flush=True)
            waiting_for_database = False
        if job_id is None:
            if once:
                break
            stop.wait(settings.worker_poll_s)
            continue
        process(job_id, render, tts)
        processed += 1
        if once:
            break
    return processed


def process(job_id: int, render: Renderer, tts: TTSProvider) -> None:
    """Render one claimed job and record the outcome."""
    settings = get_settings()
    with get_sessionmaker()() as db:
        job = db.get(queue.RenderJob, job_id)
        if job.attempts > settings.render_attempts:
            # Taken over after its worker died on the last attempt.
            queue.fail(db, job, "the worker stopped during the last attempt", 0)
            db.commit()
            return
        request = ModuleRenderRequest.model_validate(job.request)

        def on_beat_ready(beat) -> None:
            queue.beat_ready(db, job, beat)
            db.commit()

        try:
            result = render(
                request,
                media_dir=settings.media_dir,
                tts=tts,
                library_version=LIBRARY_VERSION,
                quality=settings.render_quality,
                workers=settings.render_workers,
                on_beat_ready=on_beat_ready,
            )
        except Exception as error:  # every failure is logged on the job and retried
            db.rollback()
            job = db.get(queue.RenderJob, job_id)
            message = f"{type(error).__name__}: {error}"
            queue.fail(db, job, message, settings.render_attempts)
            db.commit()
            traceback.print_exc()
            print(f"job {job_id} failed: {message}", flush=True)
            return
        queue.complete(db, job, result.manifest)
        db.commit()
        print(f"job {job_id} ready: {result.manifest.cache_key}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="npm run worker --", description=__doc__)
    parser.add_argument("--once", action="store_true", help="render at most one job, then stop")
    args = parser.parse_args(argv)

    stop = threading.Event()

    def request_stop(signum, frame) -> None:
        if stop.is_set():
            raise KeyboardInterrupt
        print("Stopping after the current job (press Ctrl+C again to stop now).", flush=True)
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    print(f"Render worker {socket.gethostname()}:{os.getpid()} waiting for jobs.", flush=True)
    run(stop, once=args.once)
    return 0


if __name__ == "__main__":
    sys.exit(main())
