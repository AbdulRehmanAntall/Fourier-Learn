"""Interaction events from the player's logger (§5.6.1, Table 5.4).

GET /api/dev/events lists them back, so the frontend team can check what the logger sends; it
is a development tool, not part of the student-facing API.
"""

from fastapi import APIRouter, Query

from app.api.database import in_database
from app.api.deps import CurrentUser, Store
from app.api.schemas.events import LoggedEvent
from app.contracts import InteractionEventBatch
from app.lessons import service
from app.stub import is_stub_id

router = APIRouter(tags=["events"])


@router.post("/events", status_code=202)
async def log_events(body: InteractionEventBatch, user: CurrentUser, store: Store) -> None:
    """A batch of up to 100 events. `im_lost` and `branch_choice` are refused here: their own
    endpoints record them. Events for lessons in the database are stored as INTERACTION_EVENT
    rows; the stub keeps its own."""
    stub = [event for event in body.events if is_stub_id(event.module_id)]
    real = [event for event in body.events if not is_stub_id(event.module_id)]
    if stub:
        store.log_events(user, InteractionEventBatch(events=stub))
    if real:
        batch = InteractionEventBatch(events=real)
        await in_database(lambda db: service.log_events(db, user, batch), commit=True)


@router.get("/dev/events", response_model=list[LoggedEvent])
async def list_events(
    user: CurrentUser, store: Store, limit: int = Query(default=100, ge=1, le=1000)
) -> list[LoggedEvent]:
    """The signed-in user's most recent events, oldest first."""
    return store.events_of(user, limit)
