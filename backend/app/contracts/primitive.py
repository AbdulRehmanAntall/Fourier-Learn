"""The visual primitive interface (report §5.3.1).

A visual primitive is a parameterised Manim CE component that draws one type of mathematical
visual. It is defined by four elements:

1. a parameter schema listing the parameters it accepts with their types and permitted ranges
   (`params_model`);
2. validation predicates that a parameter set must pass before rendering (`validate`, §5.3.3);
3. a layout contract fixing the region of the frame it may occupy (`layout`, §5.3.4);
4. difficulty hooks: the number of intermediate animation steps, their durations, and the
   number of labels and highlights drawn (`steps`, Table 5.3).

Manim code is written only here, before deployment (§5.3.2). At runtime a model supplies
parameter values and nothing else.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, PositiveFloat, model_validator

from app.contracts.level import Level

if TYPE_CHECKING:
    from manim import Mobject, Scene


class PrimitiveParams(BaseModel):
    """Base class of every primitive's parameter schema.

    Subclasses declare each parameter with its type and permitted range (`Field(ge=..., le=...)`).
    The JSON Schema of the subclass is what constrained decoding restricts the parameter model
    to, so the model cannot emit a name, type or value outside it (§5.3.3).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class PredicateFailure(BaseModel):
    """A validation predicate that a parameter set failed (§5.3.3).

    It is returned to the parameter model with the failing predicate named.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["parsing", "domain", "consistency"]
    """Parsing: an expression is not well formed. Domain: a function is not real and finite at
    sampled points of its plotted interval. Consistency: a relation between parameters fails,
    such as the point of tangency lying outside the plotted interval."""
    predicate: str
    message: str
    parameters: list[str] = []
    """The parameters involved."""


class Region(BaseModel):
    """A rectangle of the frame, in fractions of its width and height from the bottom left."""

    model_config = ConfigDict(frozen=True)

    x_min: float = Field(ge=0, le=1)
    x_max: float = Field(ge=0, le=1)
    y_min: float = Field(ge=0, le=1)
    y_max: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.x_min >= self.x_max or self.y_min >= self.y_max:
            raise ValueError("a region needs x_min < x_max and y_min < y_max")
        return self


FULL_FRAME = Region(x_min=0, x_max=1, y_min=0, y_max=1)


class LayoutContract(BaseModel):
    """The region a primitive may occupy, and which of its objects may overlap (§5.3.4).

    The layout check rejects a segment if any visible object leaves the frame or the region, or
    if two objects intersect that this contract does not allow to overlap. Objects are the names
    a primitive yields from `animate`; "*" matches any object.
    """

    model_config = ConfigDict(frozen=True)

    region: Region = FULL_FRAME
    allowed_overlaps: list[tuple[str, str]] = []

    def may_overlap(self, a: str, b: str) -> bool:
        for x, y in self.allowed_overlaps:
            if (x in (a, "*") and y in (b, "*")) or (x in (b, "*") and y in (a, "*")):
                return True
        return False


class StepSpec(BaseModel):
    """One animation step of a segment at a given level: the difficulty hooks (Table 5.3)."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    """What the step shows. The narration model writes one passage per step from it (§5.4.2)."""
    min_run_time_s: PositiveFloat
    """The minimum time the step needs at this level. The step runs for the larger of this and
    the duration of its synthesised passage (§5.4.4)."""
    labels: NonNegativeInt = 0
    highlights: NonNegativeInt = 0


NamedObjects = Mapping[str, "Mobject"]
"""Visible Manim objects by name, as used by the layout check and the next segment."""


class Primitive[P: PrimitiveParams](ABC):
    """A validated, parameterised Manim component in the primitive library."""

    primitive_id: ClassVar[str]
    """Unique name, e.g. "FunctionGraph" (Table 5.2). Scene plans refer to primitives by it."""
    version: ClassVar[str]
    """Bumped whenever the primitive changes; the library version is part of the cache key."""
    topic: ClassVar[str]
    """Topic area of Table 5.2, e.g. "Introductory calculus"."""
    params_model: ClassVar[type[PrimitiveParams]]
    layout: ClassVar[LayoutContract]

    @classmethod
    def parse_params(cls, raw: Mapping[str, Any]) -> P:
        """Check a raw parameter set against the schema (types and permitted ranges)."""
        return cls.params_model.model_validate(raw)  # type: ignore[return-value]

    @classmethod
    def params_json_schema(cls) -> dict[str, Any]:
        """The schema the parameter model's output is constrained to."""
        return cls.params_model.model_json_schema()

    @abstractmethod
    def default_params(self) -> P:
        """The validated default parameter set, used after three failed attempts (§5.3.3)."""

    @abstractmethod
    def validate(self, params: P) -> list[PredicateFailure]:
        """Apply the SymPy parsing, domain and consistency predicates. Empty means valid."""

    @abstractmethod
    def computed_values(self, params: P) -> dict[str, str]:
        """Every quantity shown on screen as a number, computed by SymPy, by slot name.

        The narration refers to these through named slots such as "{gradient}" (§5.4.2).
        """

    @abstractmethod
    def steps(self, params: P, level: Level) -> list[StepSpec]:
        """The animation steps of the segment at a level (the difficulty hooks).

        Level 1 animates every intermediate step separately, Level 2 combines minor steps, and
        Level 3 shows main steps only (Table 5.3). The narration has one passage per step.
        """

    @abstractmethod
    def animate(
        self,
        scene: "Scene",
        params: P,
        level: Level,
        run_times: Sequence[float],
        carried: NamedObjects,
    ) -> Iterator[NamedObjects]:
        """Play the steps of the segment in `scene`, one per entry of `run_times`.

        `carried` holds the objects the previous segment left on screen; the primitive may keep,
        transform or remove them. After each step, yield every visible object by name, so the
        engine can run the layout check and record the step's end time.
        """

    @abstractmethod
    def add_final_state(self, scene: "Scene", params: P, level: Level) -> NamedObjects:
        """Add the objects left on screen at the end of the segment, without animation.

        Each segment is rendered as a separate scene, so the next segment starts from this
        state and the joined video shows no break at segment boundaries (§5.3.4).
        """
