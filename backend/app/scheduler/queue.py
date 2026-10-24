"""The render queue (report §4.4.4, §5.5, §6.4.6), kept in Postgres.

The report names no queue technology; a table avoids running Redis as well (KISS, §6.2.3).
A job renders one module at one level. Workers take the queued job with the best priority,
oldest first, using SELECT ... FOR UPDATE SKIP LOCKED: any number of workers can share the
queue, and no two take the same job. A job whose worker dies is taken over once its lease
runs out. Each job gets `render_attempts` tries; every failure is logged on the job.

Before a job is queued, the variant cache is consulted (§4.2.3): a variant that is already
rendered, or already being rendered for another lesson, is reused.

Progress is published as stream events (app/contracts/stream.py) in the stream_event table,
which the API serves to the browser over Server-Sent Events (§6.4.12).
"""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.contracts import (
    BeatManifest,
    BeatReady,
    GenerationProgress,
    Level,
    ModuleFailed,
    ModuleManifest,
    ModuleReady,
    ModuleRenderRequest,
    RenderStatus,
)
from app.db.models import Module, RenderJob, StreamEventRecord, Variant
from app.renderer.store import MODULE_FILE, cache_key_for, load_manifest, variant_directory

ACTIVE = ("queued", "rendering")


def now() -> datetime:
    return datetime.now(UTC)


def publish(db: Session, lesson_id: int, event) -> None:
    """Add an event to a lesson's stream."""
    db.add(StreamEventRecord(lesson_id=lesson_id, payload=event.model_dump(mode="json")))


def enqueue(
    db: Session,
    module: Module,
    request: ModuleRenderRequest,
    *,
    priority: int,
    tts_name: str,
    media_dir: Path,
) -> RenderJob | None:
    """Make sure `module` gets rendered with `request`, rendering as little as possible.

    Returns the job that will render it, or None if the variant is already in the cache.
    """
    request = request.model_copy(update={"module_id": module.module_id})
    key = cache_key_for(request, tts_name)
    module.cache_key = key
    module.difficulty_level = request.level.label

    manifest = load_manifest(variant_directory(media_dir, key))
    if manifest is not None and manifest.is_complete:
        _mark_ready(db, [module], manifest)
        return None

    active = db.scalar(
        select(RenderJob)
        .where(RenderJob.cache_key == key, RenderJob.status.in_(ACTIVE))
        .order_by(RenderJob.job_id)
        .limit(1)
    )
    if active is not None:
        # Another lesson is waiting for the same variant: share the job. A more urgent wait
        # raises its priority.
        active.priority = min(active.priority, priority)
        module.render_status = active.status
        return active

    job = RenderJob(
        module_id=module.module_id,
        lesson_id=module.lesson_id,
        cache_key=key,
        level=int(request.level),
        priority=priority,
        status="queued",
        attempts=0,
        request=request.model_dump(mode="json"),
        log="",
    )
    db.add(job)
    db.flush()  # visible to the next enqueue in this transaction, so it shares the job
    module.render_status = RenderStatus.QUEUED.value
    return job


def claim(db: Session, worker: str, lease_s: int) -> RenderJob | None:
    """Take the next job for `worker`, or None if there is nothing to do.

    Commit right after, so other workers see the job as taken.
    """
    stale = now() - timedelta(seconds=lease_s)
    candidate = (
        select(RenderJob.job_id)
        .where(
            or_(
                RenderJob.status == "queued",
                (RenderJob.status == "rendering") & (RenderJob.started_at < stale),
            )
        )
        .order_by(RenderJob.priority, RenderJob.created_at, RenderJob.job_id)
        .limit(1)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    job_id = db.scalar(
        update(RenderJob)
        .where(RenderJob.job_id == candidate)
        .values(
            status="rendering",
            attempts=RenderJob.attempts + 1,
            worker=worker,
            started_at=now(),
        )
        .returning(RenderJob.job_id)
    )
    if job_id is None:
        return None
    job = db.get(RenderJob, job_id, populate_existing=True)
    _log(job, f"attempt {job.attempts}: taken by {worker}")
    for module in _waiting(db, job.cache_key):
        module.render_status = RenderStatus.RENDERING.value
        publish(db, module.lesson_id, GenerationProgress(
            lesson_id=module.lesson_id, module_id=module.module_id, stage="rendering"
        ))  # fmt: skip
    return job


def beat_ready(db: Session, job: RenderJob, beat: BeatManifest) -> None:
    """A beat of the job's variant is stored: every module waiting for it can start on it."""
    _log(job, f"beat {beat.index} ready")
    for module in _waiting(db, job.cache_key):
        publish(
            db,
            module.lesson_id,
            BeatReady(
                lesson_id=module.lesson_id,
                module_id=module.module_id,
                level=Level(job.level),
                beat_index=beat.index,
                cache_key=job.cache_key,
            ),
        )


def complete(db: Session, job: RenderJob, manifest: ModuleManifest) -> None:
    """The job's variant is fully rendered: record it in the cache and release every module
    that was waiting for it."""
    job.status = "ready"
    job.finished_at = now()
    job.duration_s = (job.finished_at - job.started_at).total_seconds() if job.started_at else None
    job.error = None
    _log(job, f"finished: {manifest.beat_count} beats, {manifest.duration_s:.1f} s")
    if db.get(Variant, manifest.cache_key) is None:
        db.add(
            Variant(
                cache_key=manifest.cache_key,
                level=int(manifest.level),
                voice=manifest.voice,
                library_version=manifest.library_version,
                beat_count=manifest.beat_count,
                duration_s=manifest.duration_s,
            )
        )
    _mark_ready(db, _waiting(db, job.cache_key), manifest)


def fail(db: Session, job: RenderJob, error: str, max_attempts: int) -> None:
    """An attempt failed: try again later, or after the last attempt give up (§6.4.6)."""
    job.error = error
    _log(job, f"attempt {job.attempts} failed: {error}")
    if job.attempts < max_attempts:
        job.status = "queued"
        job.worker = None
        return
    job.status = "failed"
    job.finished_at = now()
    _log(job, f"gave up after {job.attempts} attempts")
    for module in _waiting(db, job.cache_key):
        module.render_status = RenderStatus.FAILED.value
        publish(
            db,
            module.lesson_id,
            ModuleFailed(
                lesson_id=module.lesson_id,
                module_id=module.module_id,
                level=Level(job.level),
                fallback=None,
                message="This part of the lesson could not be prepared.",
            ),
        )


def _waiting(db: Session, cache_key: str) -> list[Module]:
    """The modules that play this variant and are not yet marked ready."""
    return list(
        db.scalars(
            select(Module).where(
                Module.cache_key == cache_key,
                Module.render_status != RenderStatus.READY.value,
            )
        )
    )


def _mark_ready(db: Session, modules: Iterable[Module], manifest: ModuleManifest) -> None:
    for module in modules:
        module.render_status = RenderStatus.READY.value
        module.video_path = f"variants/{manifest.cache_key}/{MODULE_FILE}"
        publish(
            db,
            module.lesson_id,
            ModuleReady(
                lesson_id=module.lesson_id,
                module_id=module.module_id,
                level=manifest.level,
                cache_key=manifest.cache_key,
            ),
        )


def _log(job: RenderJob, line: str) -> None:
    stamp = now().strftime("%Y-%m-%d %H:%M:%S")
    job.log = f"{job.log}{stamp} {line}\n"
