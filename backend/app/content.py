"""The teaching content: concept taxonomy, glossary and item bank (§5.2.1, §5.6.2, §5.7.3).

It lives as data in backend/content/, written and reviewed by people, not code: concepts.json
(topic areas, concepts, syllabus codes and prerequisite edges), glossary.json (the terms shown
as concept chips, with their definitions) and items.json (check questions with their verified
answers). `npm run db:seed` loads them into the database, and the Phase 2 stub serves them too.

Loading checks what the database alone cannot: every prerequisite, glossary and item concept
exists, the prerequisite edges form no cycle (a lesson plan orders concepts by them, §5.2.3), no
concept has the same glossary term twice, and every item's answer is one of its options.

The syllabus codes are placeholders until they are checked against the Cambridge syllabus
documents; replace them in concepts.json, never in code.
"""

import json
from functools import lru_cache
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

from app.contracts.scene_plan import GlossaryTerm
from app.core.config import BACKEND_DIR

CONTENT_DIR = BACKEND_DIR / "content"


class _Content(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConceptEntry(_Content):
    id: PositiveInt
    name: str = Field(min_length=1, max_length=100)
    syllabus_code: str = Field(min_length=1, max_length=20)
    topic_area: str = Field(min_length=1, max_length=50)
    prerequisites: list[PositiveInt] = []


class GlossaryEntry(_Content):
    id: PositiveInt
    concept_id: PositiveInt
    term: GlossaryTerm
    definition: str = Field(min_length=1)


class ItemEntry(_Content):
    """A check question with its verified answer. Text may contain `$...$` math."""

    id: PositiveInt
    concept_id: PositiveInt
    item_type: Literal["mcq", "true_false"]
    question_text: str = Field(min_length=1)
    options: list[str] = Field(min_length=2, max_length=4)
    correct_option: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def _answer_is_an_option(self) -> Self:
        if len(set(self.options)) != len(self.options):
            raise ValueError(f"item {self.id} repeats an option")
        if self.item_type == "true_false" and self.options != ["True", "False"]:
            raise ValueError(f"true/false item {self.id} must have the options True and False")
        if self.correct_option not in self.options:
            raise ValueError(f"item {self.id}: the answer is not one of the options")
        return self


class Taxonomy(_Content):
    topic_areas: list[str] = Field(min_length=1)
    concepts: list[ConceptEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ids = [c.id for c in self.concepts]
        if len(set(ids)) != len(ids):
            raise ValueError("concept ids must be unique")
        unknown_areas = {c.topic_area for c in self.concepts} - set(self.topic_areas)
        if unknown_areas:
            raise ValueError(f"concepts use topic areas that are not listed: {unknown_areas}")
        for concept in self.concepts:
            missing = set(concept.prerequisites) - set(ids)
            if missing:
                raise ValueError(f"concept {concept.id} has unknown prerequisites {missing}")
            if concept.id in concept.prerequisites:
                raise ValueError(f"concept {concept.id} is its own prerequisite")
        try:
            list(self.order())
        except CycleError as error:
            raise ValueError(f"the prerequisite edges form a cycle: {error.args[1]}") from error
        return self

    def order(self) -> list[int]:
        """Every concept after all of its prerequisites (a topological order)."""
        graph = {c.id: set(c.prerequisites) for c in self.concepts}
        return list(TopologicalSorter(graph).static_order())


class Content(_Content):
    taxonomy: Taxonomy
    glossary: list[GlossaryEntry]
    items: list[ItemEntry]

    @model_validator(mode="after")
    def _glossary_consistent(self) -> Self:
        concepts = {c.id for c in self.taxonomy.concepts}
        ids = [g.id for g in self.glossary]
        if len(set(ids)) != len(ids):
            raise ValueError("glossary ids must be unique")
        seen = set()
        for entry in self.glossary:
            if entry.concept_id not in concepts:
                raise ValueError(f"glossary term {entry.term!r} names unknown concept")
            key = (entry.concept_id, entry.term.lower())
            if key in seen:
                raise ValueError(f"concept {entry.concept_id} has the term {entry.term!r} twice")
            seen.add(key)
        item_ids = [i.id for i in self.items]
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("item ids must be unique")
        for item in self.items:
            if item.concept_id not in concepts:
                raise ValueError(f"item {item.id} names an unknown concept")
        return self


def load_content(directory: Path = CONTENT_DIR) -> Content:
    taxonomy = json.loads((directory / "concepts.json").read_text(encoding="utf-8"))
    glossary = json.loads((directory / "glossary.json").read_text(encoding="utf-8"))
    items = json.loads((directory / "items.json").read_text(encoding="utf-8"))
    return Content(taxonomy=taxonomy, glossary=glossary, items=items)


@lru_cache
def content() -> Content:
    """The content of backend/content/, loaded once."""
    return load_content()
