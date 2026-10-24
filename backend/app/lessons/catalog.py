"""Topics and glossary from the database (§5.2.1, §5.6.2), once `npm run db:seed` has run."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas.common import Concept, TopicArea
from app.api.schemas.learner import GlossaryDefinition
from app.content import content
from app.db.models import Concept as ConceptRow
from app.db.models import GlossaryTerm


def topics(db: Session) -> list[TopicArea]:
    """The topic areas with their concepts; empty while the database is not seeded."""
    rows = list(db.scalars(select(ConceptRow).order_by(ConceptRow.concept_id)))
    if not rows:
        return []
    # The order of the topic areas is part of the content (the progress screen follows it).
    order = {area: i for i, area in enumerate(content().taxonomy.topic_areas)}
    areas: dict[str, list[Concept]] = {}
    for row in rows:
        areas.setdefault(row.topic_area, []).append(
            Concept(
                id=row.concept_id,
                name=row.name,
                syllabus_code=row.syllabus_code,
                topic_area=row.topic_area,
            )
        )
    return [
        TopicArea(topic_area=area, concepts=concepts)
        for area, concepts in sorted(areas.items(), key=lambda item: order.get(item[0], 99))
    ]


def definition(db: Session, term: str) -> GlossaryDefinition | None:
    row = db.scalar(
        select(GlossaryTerm).where(func.lower(GlossaryTerm.term) == term.strip().lower()).limit(1)
    )
    if row is None:
        return None
    return GlossaryDefinition(term=row.term, definition=row.definition, concept_id=row.concept_id)
