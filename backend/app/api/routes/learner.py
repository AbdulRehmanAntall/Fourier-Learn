"""Topics, glossary, the onboarding diagnostic and progress."""

from fastapi import APIRouter

from app.api.database import in_database, served_by_database
from app.api.deps import CurrentUser, Store
from app.api.schemas.common import TopicArea
from app.api.schemas.learner import DiagnosticAnswer, DiagnosticState, GlossaryDefinition, Progress
from app.db.session import database_available
from app.lessons import catalog

router = APIRouter(tags=["learner"])


@router.get("/topics", response_model=list[TopicArea])
async def topics(store: Store) -> list[TopicArea]:
    """The supported syllabus topics. Public: the landing page lists them.

    From the database once it is seeded (npm run db:seed); until then from the same content
    files, through the stub."""
    if database_available():
        found = await in_database(catalog.topics, answers=False)
        if found:
            served_by_database()
            return found
    return store.topics()


@router.get("/glossary/{term}", response_model=GlossaryDefinition)
async def glossary_term(term: str, user: CurrentUser, store: Store) -> GlossaryDefinition:
    """The definition shown when a concept chip is opened (UC 4.5)."""
    if database_available():
        found = await in_database(lambda db: catalog.definition(db, term), answers=False)
        if found is not None:
            served_by_database()
            return found
    return store.definition(term)


@router.get("/diagnostic", response_model=DiagnosticState)
async def diagnostic(user: CurrentUser, store: Store) -> DiagnosticState:
    return store.diagnostic(user)


@router.post("/diagnostic/answers", response_model=DiagnosticState)
async def answer_diagnostic(
    body: DiagnosticAnswer, user: CurrentUser, store: Store
) -> DiagnosticState:
    return store.answer_diagnostic(user, body.check_id, body.selected_option)


@router.get("/progress", response_model=Progress)
async def progress(user: CurrentUser, store: Store) -> Progress:
    """Per-concept confidence (Fig. 4.6)."""
    return store.progress(user)
