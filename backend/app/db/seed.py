"""Load the teaching content of backend/content/ into the database: `npm run db:seed`.

Concepts, prerequisite edges, glossary terms and check questions are written by id, so running
the command again updates what changed and adds what is new; it is safe to run at any time.
The content files are the source of the prerequisite edges, so edges they no longer list are
removed. Glossary terms and questions are only added and updated, never removed here, so items
an administrator adds later (Phase 7) survive a re-seed.
"""

import sys

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.content import Content, content
from app.db.models import CheckQuestion, Concept, ConceptPrerequisite, GlossaryTerm
from app.db.session import get_sessionmaker


def seed(db: Session, data: Content) -> dict[str, int]:
    """Write `data` into the database. Returns how many rows of each kind it now holds."""
    concepts = [
        {
            "concept_id": c.id,
            "name": c.name,
            "syllabus_code": c.syllabus_code,
            "topic_area": c.topic_area,
        }
        for c in data.taxonomy.concepts
    ]
    _upsert(db, Concept, concepts, "concept_id")

    edges = {(c.id, p) for c in data.taxonomy.concepts for p in c.prerequisites}
    existing = set(
        db.execute(select(ConceptPrerequisite.concept_id, ConceptPrerequisite.prerequisite_id))
    )
    for concept_id, prerequisite_id in existing - edges:
        db.execute(
            delete(ConceptPrerequisite).where(
                ConceptPrerequisite.concept_id == concept_id,
                ConceptPrerequisite.prerequisite_id == prerequisite_id,
            )
        )
    for concept_id, prerequisite_id in edges - existing:
        db.add(ConceptPrerequisite(concept_id=concept_id, prerequisite_id=prerequisite_id))

    terms = [
        {"term_id": g.id, "concept_id": g.concept_id, "term": g.term, "definition": g.definition}
        for g in data.glossary
    ]
    _upsert(db, GlossaryTerm, terms, "term_id")

    items = [
        {
            "check_id": i.id,
            "concept_id": i.concept_id,
            "item_type": i.item_type,
            "question_text": i.question_text,
            "options": i.options,
            "correct_option": i.correct_option,
        }
        for i in data.items
    ]
    _upsert(db, CheckQuestion, items, "check_id")
    db.flush()

    # Ids were written explicitly, so move each table's sequence past them; otherwise the next
    # row added without an id (by the admin) would collide with a seeded one.
    for table, column in (("glossary_term", "term_id"), ("check_question", "check_id")):
        db.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{table}', '{column}'), "
                f"COALESCE((SELECT MAX({column}) FROM {table}), 1))"
            )
        )
    return {
        "concepts": db.query(Concept).count(),
        "prerequisite edges": db.query(ConceptPrerequisite).count(),
        "glossary terms": db.query(GlossaryTerm).count(),
        "check questions": db.query(CheckQuestion).count(),
    }


def _upsert(db: Session, model, rows: list[dict], key: str) -> None:
    if not rows:
        return
    statement = insert(model).values(rows)
    updates = {column: statement.excluded[column] for column in rows[0] if column != key}
    db.execute(statement.on_conflict_do_update(index_elements=[key], set_=updates))


def main() -> int:
    with get_sessionmaker()() as db:
        counts = seed(db, content())
        db.commit()
    for kind, count in counts.items():
        print(f"{count:4d} {kind}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
