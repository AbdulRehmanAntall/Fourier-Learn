"""Shapes shared by several areas of the API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class Schema(BaseModel):
    """Base of every API body: unknown fields are rejected, so typos fail loudly."""

    model_config = ConfigDict(extra="forbid")


class Concept(Schema):
    id: PositiveInt
    name: str
    syllabus_code: str
    topic_area: str


class TopicArea(Schema):
    topic_area: str
    concepts: list[Concept]


ItemType = Literal["mcq", "true_false"]

TRUE_FALSE_OPTIONS = ["True", "False"]


class CheckItem(Schema):
    """A bank item as the student sees it: never with its answer (§5.7.3).

    Text may contain inline LaTeX between `$` signs, which the frontend renders with KaTeX.
    """

    id: PositiveInt
    concept_id: PositiveInt
    item_type: ItemType
    question_text: str
    options: list[str] = Field(min_length=2, max_length=4)
