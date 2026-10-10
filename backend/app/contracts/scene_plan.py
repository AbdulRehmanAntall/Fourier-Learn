"""Scene plans and lesson plans produced by the Prompt Interpreter (report §5.2, Table 5.1).

These models are the schema check of §5.2.3. The reference check (every primitive, glossary term
and check item exists, and every expression parses) needs the library and the taxonomy, so it
belongs to the Prompt Interpreter.
"""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, StringConstraints, model_validator

from app.contracts.status import ModuleStyle

# GLOSSARY_TERM.term is Varchar(60) (Table 4.8).
GlossaryTerm = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Segment(_Contract):
    """One segment (a "beat" in Chapter 6) of a micro-module."""

    primitive_id: NonEmptyStr
    """The visual primitive the segment shows."""
    content: dict[NonEmptyStr, NonEmptyStr] = Field(min_length=1)
    """The mathematical objects the segment shows, as expressions, by name."""
    narration_intent: NonEmptyStr
    """A one-sentence statement of what the segment explains."""
    glossary_terms: list[GlossaryTerm] = []
    """The concepts surfaced as chips during the segment."""


class BranchOption(_Contract):
    """A branch offered after the module, described by its own scene plan (§5.6.4)."""

    kind: Literal[ModuleStyle.THEORY, ModuleStyle.WORKED_EXAMPLE]
    plan: "ScenePlan"

    @model_validator(mode="after")
    def _branch_inserts_one_module(self) -> Self:
        # A chosen branch inserts one module, after which the original plan resumes.
        if self.plan.branch_options:
            raise ValueError("a branch module cannot offer branch options of its own")
        return self


class ScenePlan(_Contract):
    """The plan of one micro-module (Table 5.1).

    A scene plan carries no difficulty level: the same plan is rendered at every level, and the
    segment list fixes the number and order of segments for every variant (§5.2.3). Unknown
    fields such as "level" are rejected.
    """

    module_id: PositiveInt
    concept_id: PositiveInt
    segments: list[Segment] = Field(min_length=1)
    check_items: list[PositiveInt] = Field(min_length=1, max_length=2)
    """Bank items for the check after the module: one or two, never repeated (§5.7.3)."""
    branch_options: list[BranchOption] = Field(default=[], max_length=2)
    """Empty when the module offers no branch."""

    @model_validator(mode="after")
    def _no_duplicates(self) -> Self:
        if len(set(self.check_items)) != len(self.check_items):
            raise ValueError("check_items must not repeat an item")
        kinds = [option.kind for option in self.branch_options]
        if len(set(kinds)) != len(kinds):
            raise ValueError("each branch kind may be offered at most once")
        return self


BranchOption.model_rebuild()


class LessonPlan(_Contract):
    """The ordered micro-modules of one lesson (§5.2.3).

    Missing prerequisites come first, in prerequisite order, and the target concept last.
    Review and branch modules are inserted while the lesson runs (Algorithm 1).
    """

    target_concept_id: PositiveInt
    modules: list[ScenePlan] = Field(min_length=1)

    @model_validator(mode="after")
    def _target_last_and_ids_unique(self) -> Self:
        if self.modules[-1].concept_id != self.target_concept_id:
            raise ValueError("the last module must teach the target concept")
        ids = [module.module_id for module in self.modules]
        ids += [
            option.plan.module_id for module in self.modules for option in module.branch_options
        ]
        if len(set(ids)) != len(ids):
            raise ValueError("module_id must be unique within the lesson, branch plans included")
        return self


class QueryInterpretation(_Contract):
    """The Prompt Interpreter's reading of a topic query (§5.2.2)."""

    in_scope: bool
    target_concept_id: PositiveInt | None = None
    nearest_concept_ids: list[PositiveInt] = []
    """For an out-of-scope query, the nearest in-scope concepts to name in the reply."""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.in_scope and self.target_concept_id is None:
            raise ValueError("an in-scope query needs a target_concept_id")
        if not self.in_scope:
            if self.target_concept_id is not None:
                raise ValueError("an out-of-scope query has no target_concept_id")
            if not self.nearest_concept_ids:
                raise ValueError("an out-of-scope query must name the nearest concepts")
        return self
