from pathlib import Path

import pytest
from pydantic import ValidationError

from app.contracts import Level, ModuleRenderRequest
from app.primitives.area_under_curve import AreaUnderCurve
from app.primitives.equation_transform import EquationTransform
from app.primitives.function_graph import FunctionGraph
from app.primitives.gradient_triangle import GradientTriangle
from app.primitives.harness import GRIDS
from app.primitives.library import (
    LIBRARY_VERSION,
    PRIMITIVES,
    UnknownPrimitiveError,
    get_primitive,
)
from app.primitives.secant_to_tangent import SecantToTangent
from app.primitives.tangent_slide import TangentSlide
from app.primitives.travel_graph import TravelGraph


def predicates(primitive, raw):
    return [failure.predicate for failure in primitive.validate(primitive.parse_params(raw))]


def test_library_holds_every_primitive_of_table_5_2():
    # Table 5.2 is the core; the library grows beyond it (docs/primitives.md).
    from app.primitives.catalog import PRIMITIVE_IDS

    assert {
        "FunctionGraph",
        "GradientTriangle",
        "TangentSlide",
        "SecantToTangent",
        "TravelGraph",
        "AreaUnderCurve",
        "EquationTransform",
    } <= set(PRIMITIVES)
    assert set(PRIMITIVES) == PRIMITIVE_IDS
    with pytest.raises(UnknownPrimitiveError):
        get_primitive("PieChart")


@pytest.mark.parametrize("primitive_id", sorted(PRIMITIVES))
def test_every_harness_case_is_valid(primitive_id):
    # The validation harness (§5.3.2) must cover every primitive with valid parameter sets.
    primitive = get_primitive(primitive_id)
    assert len(GRIDS[primitive_id]) >= 6
    for raw in GRIDS[primitive_id]:
        assert primitive.validate(primitive.parse_params(raw)) == [], raw


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


def test_catalogue_matches_the_library():
    # The API and the admin pages read the catalogue, which needs no Manim.
    from app.primitives.catalog import CATALOGUE

    library = {(cls.primitive_id, cls.topic, cls.version) for cls in PRIMITIVES.values()}
    assert {(p.primitive_id, p.topic, p.version) for p in CATALOGUE} == library


def test_every_primitive_has_syllabus_codes():
    from app.primitives.catalog import SYLLABUS

    assert set(SYLLABUS) == set(PRIMITIVES)
    assert all(codes.strip() for codes in SYLLABUS.values())


def test_tangent_slide_predicates_and_values():
    slide = TangentSlide()
    base = {"expression": "x**3 - 3*x", "x_min": -2.5, "x_max": 2.5, "x_start": -2, "x_end": 0.5}
    assert predicates(slide, base) == []
    assert predicates(slide, base | {"x_end": 3}) == ["slide_in_interval"]
    assert predicates(slide, base | {"x_end": -2}) == ["tangent_moves"]
    assert predicates(slide, base | {"expression": "abs(x)"}) == ["differentiable"]
    assert predicates(slide, base | {"expression": "tan(x)"}) == ["continuous"]
    sqrt = {"expression": "sqrt(x)", "x_min": 0, "x_max": 9}
    assert predicates(slide, sqrt | {"x_start": 0, "x_end": 4}) == ["differentiable"]
    assert predicates(slide, sqrt | {"x_start": 1, "x_end": 4}) == []
    assert slide.computed_values(slide.parse_params(base)) == {
        "start_x": "-2",
        "start_y": "-2",
        "start_gradient": "9",
        "point_start": "(-2, -2)",
        "end_x": "1/2",
        "end_y": "-11/8",
        "end_gradient": "-9/4",
        "point_end": "(1/2, -11/8)",
    }
    # Decimals in f are made exact before differentiating: no "1.0" in the narration.
    decimal = slide.parse_params(base | {"expression": "0.5*x**2", "x_start": 1, "x_end": 2})
    assert slide.computed_values(decimal)["end_gradient"] == "2"


def test_secant_to_tangent_predicates_and_values():
    secant = SecantToTangent()
    base = {"expression": "x**2", "x_min": -1, "x_max": 4, "x0": 1, "h_values": [2, 1, 0.5]}
    assert predicates(secant, base) == []
    assert predicates(secant, base | {"h_values": [1, 2]}) == ["h_decreasing"]
    assert predicates(secant, base | {"h_values": [1, 0]}) == ["h_nonzero"]
    assert predicates(secant, base | {"h_values": [5, 1]}) == ["q_in_interval"]
    assert predicates(secant, base | {"x0": 6}) == ["point_in_interval"]
    with pytest.raises(ValidationError):
        secant.parse_params(base | {"h_values": [1]})
    values = secant.computed_values(secant.parse_params(base))
    # (f(1 + h) - f(1)) / h = 2 + h for f = x^2, approaching f'(1) = 2.
    assert [values[f"secant_gradient_{i}"] for i in (1, 2, 3)] == ["4", "3", "5/2"]
    assert values["tangent_gradient"] == "2"
    assert values["point_q_3"] == "(3/2, 9/4)"


def test_area_under_curve_predicates_and_values():
    area = AreaUnderCurve()
    base = {"expression": "4 - x**2", "x_min": -3, "x_max": 3, "lower": -2, "upper": 2}
    assert predicates(area, base) == []
    assert predicates(area, base | {"lower": 2, "upper": -2}) == ["limits_ordered"]
    assert predicates(area, base | {"upper": 5}) == ["limits_in_interval"]
    assert predicates(area, base | {"upper": 3}) == ["one_side_of_axis"]
    values = area.computed_values(area.parse_params(base))
    assert values["area"] == values["integral"] == "32/3"
    below = area.computed_values(area.parse_params(base | {"expression": "x**2 - 4"}))
    assert (below["integral"], below["area"]) == ("-32/3", "32/3")
    line = {"expression": "0.5*x + 1", "x_min": -2, "x_max": 10, "lower": 0, "upper": 8}
    assert area.computed_values(area.parse_params(line))["area"] == "24"


def test_travel_graph_predicates_and_values():
    travel = TravelGraph()
    journey = {"kind": "speed_time", "points": [[0, 0], [4, 8], [10, 8], [12, 0]], "show": "areas"}
    assert predicates(travel, journey) == []
    assert predicates(travel, journey | {"points": [[1, 0], [4, 8]]}) == ["starts_at_zero"]
    assert predicates(travel, journey | {"points": [[0, 0], [4, 8], [4, 2]]}) == ["time_increases"]
    assert predicates(travel, journey | {"kind": "distance_time"}) == ["areas_need_speed_time"]
    values = travel.computed_values(travel.parse_params(journey))
    assert [values[f"segment_{i}_distance"] for i in (1, 2, 3)] == ["16", "48", "8"]
    assert [values[f"segment_{i}_acceleration"] for i in (1, 2, 3)] == ["2", "0", "-4"]
    assert values["total_distance"] == "72"
    trip = {
        "kind": "distance_time",
        "points": [[0, 0], [10, 6], [15, 6], [30, 0]],
        "time_unit": "min",
        "distance_unit": "km",
    }
    values = travel.computed_values(travel.parse_params(trip))
    # Speed is the size of the gradient: coming back at 2/5 km/min, not -2/5.
    assert [values[f"segment_{i}_speed"] for i in (1, 2, 3)] == ["3/5", "0", "2/5"]
    assert values["segment_3_gradient"] == "-2/5"
    assert values["speed_unit"] == "km/min"
