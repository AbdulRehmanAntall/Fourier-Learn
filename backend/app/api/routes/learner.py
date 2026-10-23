"""Topics, glossary, the onboarding diagnostic and progress."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, Store
from app.api.schemas.common import TopicArea
from app.api.schemas.learner import DiagnosticAnswer, DiagnosticState, GlossaryDefinition, Progress

router = APIRouter(tags=["learner"])


@router.get("/topics", response_model=list[TopicArea])
async def topics(store: Store) -> list[TopicArea]:
    """The supported syllabus topics. Public: the landing page lists them."""
    return store.topics()


@router.get("/glossary/{term}", response_model=GlossaryDefinition)
async def glossary_term(term: str, user: CurrentUser, store: Store) -> GlossaryDefinition:
    """The definition shown when a concept chip is opened (UC 4.5)."""
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
