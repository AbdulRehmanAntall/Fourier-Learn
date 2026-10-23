from pathlib import Path

import pytest
from pydantic import ValidationError

from app.contracts import Level, ModuleRenderRequest
from app.primitives.equation_transform import EquationTransform
from app.primitives.function_graph import FunctionGraph
from app.primitives.gradient_triangle import GradientTriangle
from app.primitives.library import (
    LIBRARY_VERSION,
    PRIMITIVES,
    UnknownPrimitiveError,
    get_primitive,
)


def predicates(primitive, raw):
    return [failure.predicate for failure in primitive.validate(primitive.parse_params(raw))]


def test_library_holds_the_first_primitives_of_table_5_2():
    assert set(PRIMITIVES) == {"FunctionGraph", "GradientTriangle", "EquationTransform"}
    with pytest.raises(UnknownPrimitiveError):
        get_primitive("TangentSlide")


@pytest.mark.parametrize("primitive_id", sorted(PRIMITIVES))
def test_defaults_are_valid_and_levels_change_the_number_of_steps(primitive_id):
    primitive = get_primitive(primitive_id)
    params = primitive.default_params()
    assert primitive.validate(params) == []
    counts = [len(primitive.steps(params, level)) for level in Level]
    assert counts[0] >= counts[1] >= counts[2] >= 1
    assert counts[0] > counts[2]


@pytest.mark.parametrize("primitive_id", sorted(PRIMITIVES))
def test_schema_for_constrained_decoding_forbids_unknown_parameters(primitive_id):
    schema = get_primitive(primitive_id).params_json_schema()
    assert schema["additionalProperties"] is False


def test_function_graph_predicates():
    graph = FunctionGraph()
    base = {"expression": "x**2", "x_min": -3, "x_max": 3}
    assert predicates(graph, base | {"marked_x": [2]}) == []
    assert predicates(graph, base | {"expression": "x +* 2"}) == ["expression_parses"]
    assert predicates(graph, base | {"expression": "x + y"}) == ["expression_parses"]
    assert predicates(graph, base | {"expression": "1/x"}) == ["real_and_finite"]
    assert predicates(graph, base | {"expression": "sqrt(x)"}) == ["real_and_finite"]
    assert predicates(graph, base | {"x_min": 3, "x_max": -3}) == ["interval_ordered"]
    assert predicates(graph, base | {"marked_x": [5]}) == ["marked_points_in_interval"]
    with pytest.raises(ValidationError):
        graph.parse_params(base | {"x_max": 50})


def test_function_graph_computes_the_marked_coordinates():
    graph = FunctionGraph()
    params = graph.parse_params(
        {"expression": "x**2 - 1", "x_min": -2, "x_max": 2, "marked_x": [0.5]}
    )
    assert graph.computed_values(params) == {
        "point_1_x": "1/2",
        "point_1_y": "-3/4",
        "point_1": "(1/2, -3/4)",
    }


def test_gradient_triangle_predicates_and_values():
    triangle = GradientTriangle()
    assert predicates(triangle, {"point_a": [1, 2], "point_b": [1, 5]}) == ["not_vertical"]
    assert predicates(triangle, {"point_a": [1, 2], "point_b": [4, 2]}) == ["not_horizontal"]
    assert predicates(triangle, {"point_a": [1, 2], "point_b": [1, 2]}) == ["distinct_points"]
    params = triangle.parse_params({"point_a": [-1, 3], "point_b": [3, 1]})
    assert triangle.computed_values(params) == {
        "rise": "-2",
        "run": "4",
        "gradient": "-1/2",
        "point_a": "(-1, 3)",
        "point_b": "(3, 1)",
    }


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        (["(8 - 2)/(4 - 1)", "6/3", "2"], []),
        (["2*x + 3 = 7", "2*x = 4", "x = 2"], []),
        (["x**2 - 1", "(x - 1)*(x + 1)"], []),
        (["(8 - 2)/(4 - 1)", "6/4", "3/2"], ["step_equivalent"]),
        (["2*x + 3 = 7", "2*x = 4", "x = 3"], ["step_equivalent"]),
        (["2*x = 4", "x"], ["same_kind"]),
        (["2*x = 4", "x == 2"], ["line_parses"]),
    ],
)
def test_equation_transform_checks_every_step(lines, expected):
    assert predicates(EquationTransform(), {"expressions": lines}) == expected


def test_equation_transform_levels_follow_table_5_3():
    transform = EquationTransform()
    params = transform.parse_params({"expressions": ["a", "a + 0", "a*1", "a - 0", "a"]})
    names = {level: [s.name for s in transform.steps(params, level)] for level in Level}
    assert len(names[Level.SUPPORTED]) == 5  # every intermediate step separately
    assert names[Level.STANDARD] == ["first_line", "working", "result"]  # minor steps combined
    assert names[Level.CONCISE] == ["first_line", "result"]  # results shown directly
    assert transform.computed_values(params) == {}
    two_lines = transform.parse_params({"expressions": ["(8 - 2)/(4 - 1)", "2"]})
    assert transform.computed_values(two_lines) == {"result": "2"}


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.mark.parametrize("level", list(Level))
def test_example_requests_are_valid_for_the_library(level):
    path = EXAMPLES / f"gradient_of_line.L{int(level)}.render.json"
    request = ModuleRenderRequest.model_validate_json(path.read_text())
    assert request.library_version == LIBRARY_VERSION
    for beat in request.beats:
        primitive = get_primitive(beat.primitive_id)
        params = primitive.parse_params(beat.params)
        assert primitive.validate(params) == []
        assert len(primitive.steps(params, level)) == len(beat.narration)


def test_stub_primitive_list_matches_the_library():
    # The admin stub lists primitives without importing Manim (app/stub/seed.py).
    from app.primitives.library import PRIMITIVES
    from app.stub.seed import PRIMITIVES as LISTED

    library = {(cls.primitive_id, cls.topic, cls.version) for cls in PRIMITIVES.values()}
    assert {(pid, topic, version) for pid, topic, version, _ in LISTED} == library
