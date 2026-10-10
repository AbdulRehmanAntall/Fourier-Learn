from collections.abc import Iterator

import pytest
from pydantic import Field, ValidationError

from app.contracts import (
    LayoutContract,
    Level,
    PredicateFailure,
    Primitive,
    PrimitiveParams,
    Region,
    StepSpec,
)


class LineParams(PrimitiveParams):
    gradient: float = Field(ge=-10, le=10)
    intercept: float = Field(ge=-10, le=10)


class FakeScene:
    """Stands in for a Manim scene: records what was played."""

    def __init__(self):
        self.played: list[tuple[str, float]] = []
        self.added: list[str] = []


class StraightLine(Primitive[LineParams]):
    """A minimal primitive used only to exercise the interface."""

    primitive_id = "StraightLine"
    version = "1"
    topic = "Coordinate geometry"
    params_model = LineParams
    layout = LayoutContract(
        region=Region(x_min=0, x_max=0.6, y_min=0, y_max=1),
        allowed_overlaps=[("axes", "*")],
    )

    def default_params(self) -> LineParams:
        return LineParams(gradient=1, intercept=0)

    def validate(self, params: LineParams) -> list[PredicateFailure]:
        if params.gradient == 0:
            return [
                PredicateFailure(
                    kind="consistency",
                    predicate="non_zero_gradient",
                    message="a horizontal line has no rise to show",
                    parameters=["gradient"],
                )
            ]
        return []

    def computed_values(self, params: LineParams) -> dict[str, str]:
        return {"gradient": str(params.gradient)}

    def steps(self, params: LineParams, level: Level) -> list[StepSpec]:
        steps = [StepSpec(name="axes", description="Draw the axes", min_run_time_s=1)]
        if level is Level.SUPPORTED:
            steps.append(StepSpec(name="points", description="Mark two points", min_run_time_s=2))
        steps.append(StepSpec(name="line", description="Draw the line", min_run_time_s=1, labels=1))
        return steps

    def animate(self, scene, params, level, run_times, carried) -> Iterator[dict]:
        visible = dict(carried)
        for step, run_time in zip(self.steps(params, level), run_times, strict=True):
            scene.played.append((step.name, run_time))
            visible[step.name] = step.name
            yield visible

    def add_final_state(self, scene, params, level) -> dict:
        scene.added.append("line")
        return {"axes": "axes", "line": "line"}


def test_an_incomplete_primitive_cannot_be_created():
    class Incomplete(Primitive[LineParams]):
        primitive_id = "Incomplete"

    with pytest.raises(TypeError):
        Incomplete()


def test_parameters_are_checked_against_the_schema_and_its_ranges():
    assert StraightLine.parse_params({"gradient": 2, "intercept": 1}).gradient == 2
    with pytest.raises(ValidationError):
        StraightLine.parse_params({"gradient": 20, "intercept": 1})
    with pytest.raises(ValidationError):
        StraightLine.parse_params({"gradient": 2, "intercept": 1, "colour": "red"})


def test_the_schema_for_constrained_decoding_has_names_types_and_ranges():
    schema = StraightLine.params_json_schema()
    assert schema["additionalProperties"] is False
    assert schema["properties"]["gradient"] == {
        "maximum": 10,
        "minimum": -10,
        "title": "Gradient",
        "type": "number",
    }


def test_predicates_name_the_failure():
    line = StraightLine()
    assert line.validate(line.default_params()) == []
    [failure] = line.validate(LineParams(gradient=0, intercept=0))
    assert failure.predicate == "non_zero_gradient"


def test_steps_depend_on_the_level_and_animate_yields_after_each_step():
    line, scene = StraightLine(), FakeScene()
    params = line.default_params()
    assert len(line.steps(params, Level.SUPPORTED)) == 3
    assert len(line.steps(params, Level.CONCISE)) == 2

    carried = line.add_final_state(FakeScene(), params, Level.STANDARD)
    snapshots = list(line.animate(scene, params, Level.STANDARD, [1.5, 2.0], carried))
    assert scene.played == [("axes", 1.5), ("line", 2.0)]
    assert len(snapshots) == 2


def test_layout_contract_overlaps():
    layout = StraightLine.layout
    assert layout.may_overlap("axes", "line")
    assert layout.may_overlap("label", "axes")
    assert not layout.may_overlap("label", "line")
    with pytest.raises(ValidationError):
        Region(x_min=0.5, x_max=0.5, y_min=0, y_max=1)
    with pytest.raises(ValidationError):
        Region(x_min=0, x_max=1.2, y_min=0, y_max=1)
