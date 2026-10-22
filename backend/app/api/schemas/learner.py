"""Glossary, diagnostic and progress: what the student reads and answers outside a lesson."""

from pydantic import AwareDatetime, Field, PositiveInt

from app.api.schemas.common import CheckItem, Schema
from app.contracts.scene_plan import GlossaryTerm


class GlossaryDefinition(Schema):
    """What the chip overlay shows (§5.6.2, UC 4.5). The definition may contain `$…$` math."""

    term: GlossaryTerm
    definition: str
    concept_id: PositiveInt


class DiagnosticState(Schema):
    """The onboarding diagnostic (UC 4.2): at most five items, resumable."""

    complete: bool
    total: int = Field(ge=0, le=5)
    answered: int = Field(ge=0, le=5)
    item: CheckItem | None
    """The next unanswered item; null when the diagnostic is complete."""


class DiagnosticAnswer(Schema):
    check_id: PositiveInt
    selected_option: str = Field(min_length=1, max_length=100)


class ConceptConfidence(Schema):
    concept_id: PositiveInt
    name: str
    topic_area: str
    syllabus_code: str
    score: float = Field(ge=0, le=1)
    """The learner model's estimate that the concept is mastered (CONFIDENCE_RECORD.score)."""
    updated_at: AwareDatetime | None
    """Null while the score is still the default prior."""


class Progress(Schema):
    concepts: list[ConceptConfidence]
