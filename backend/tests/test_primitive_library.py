"""The primitive library beyond Table 5.2 (docs/primitives.md): predicates and computed values
of each primitive, and checks every staged primitive must pass.

The rendering itself is checked by the validation harness (npm run primitives:check), which
renders every case of app/primitives/harness.py at every level.
"""

import shutil

import pytest

from app.contracts import Level
from app.primitives.harness import GRIDS
from app.primitives.library import PRIMITIVES, get_primitive
from app.primitives.staged import StagedPrimitive, check_plan, visible_names

STAGED = sorted(pid for pid, cls in PRIMITIVES.items() if issubclass(cls, StagedPrimitive))
needs_latex = pytest.mark.skipif(
    not all(shutil.which(tool) for tool in ("latex", "dvisvgm")),
    reason="needs LaTeX (it is in the Docker image)",
)


def predicates(primitive_id, raw):
    primitive = get_primitive(primitive_id)
    return [f.predicate for f in primitive.validate(primitive.parse_params(raw))]


def values(primitive_id, raw):
    primitive = get_primitive(primitive_id)
    return primitive.computed_values(primitive.parse_params(raw))


@pytest.mark.parametrize("primitive_id", STAGED)
def test_every_stage_plan_is_consistent(primitive_id):
    # Nothing is shown twice, hidden before it appears, or morphed from something not shown;
    # and the steps the narration is written against are the stages that are played.
    primitive = get_primitive(primitive_id)
    for raw in GRIDS[primitive_id]:
        params = primitive.parse_params(raw)
        for level in Level:
            plan = primitive.stages(params, level)
            visible_names(plan)
            assert [s.name for s in primitive.steps(params, level)] == [s.name for s in plan]
            assert plan[0].motion is None


@pytest.mark.render
@needs_latex
@pytest.mark.parametrize("primitive_id", STAGED)
def test_every_stage_refers_to_parts_that_are_built(primitive_id):
    primitive = get_primitive(primitive_id)
    params = primitive.default_params()
    for level in Level:
        check_plan(primitive.build(params, level), primitive.stages(params, level))


# Algebra and graphs


def test_algebra_balance_computes_each_line():
    raw = {"equation": "3*x + 5 = 20", "operations": ["-5", "/3"]}
    assert predicates("AlgebraBalance", raw) == []
    assert values("AlgebraBalance", raw)["solution"] == "5"
    subject = {"equation": "v = u + a*t", "operations": ["-u", "/a", "swap"]}
    assert values("AlgebraBalance", subject)["line_4"] == "t = (-u + v)/a"
    assert predicates("AlgebraBalance", raw | {"operations": ["*0"]}) == ["nonzero_factor"]
    assert predicates("AlgebraBalance", raw | {"operations": ["%2"]}) == ["operation_parses"]
    assert predicates("AlgebraBalance", raw | {"operations": ["expand"]}) == ["expand_changes"]
    # A written result must be what the operation gives.
    wrong = raw | {"results": ["3*x = 25", "x = 5"]}
    assert predicates("AlgebraBalance", wrong) == ["result_matches_operation"]
    assert predicates("AlgebraBalance", raw | {"results": ["3*x = 15"]}) == [
        "one_result_per_operation"
    ]
    brackets = {"equation": "3*(x - 4) = 2*x + 1", "operations": ["expand", "-2*x", "+12"]}
    assert values("AlgebraBalance", brackets)["solution"] == "13"


def test_expansion_grid_products_and_like_terms():
    raw = {"factors": ["2*x + 3", "x - 4"]}
    result = values("ExpansionGrid", raw)
    assert result["expanded"] == "2*x**2 - 5*x - 12"
    assert [result[f"cell_{r}_{c}"] for r in (1, 2) for c in (1, 2)] == [
        "2*x**2",
        "-8*x",
        "3*x",
        "-12",
    ]
    assert predicates("ExpansionGrid", {"factors": ["x + 1 + y + z", "x"]}) == ["at_most_3_terms"]
    assert predicates("ExpansionGrid", {"factors": ["sqrt(x)", "x"]}) == ["polynomial"]
    assert predicates("ExpansionGrid", {"factors": ["3", "x"]}) == ["polynomial"]


def test_completing_square():
    result = values("CompletingSquare", {"b": 6, "c": 5})
    assert (result["half_b"], result["corner"], result["constant"]) == ("3", "9", "-4")
    assert result["vertex"] == "(-3, -4)"
    assert values("CompletingSquare", {"b": 3})["corner"] == "9/4"
    assert predicates("CompletingSquare", {"b": -4}) == ["b_positive"]


@pytest.mark.parametrize(
    ("abc", "roots", "vertex"),
    [
        ((1, -2, -3), ["-1", "3"], "(1, -4)"),
        ((1, -4, 4), ["2"], "(2, 0)"),
        ((1, 0, 2), [], "(0, 2)"),
        ((1, 0, -2), ["-root 2", "root 2"], "(0, -2)"),
    ],
)
def test_quadratic_explorer(abc, roots, vertex):
    a, b, c = abc
    result = values("QuadraticExplorer", {"a": a, "b": b, "c": c})
    assert [result[f"root_{i}"] for i in range(1, len(roots) + 1)] == roots
    assert result["number_of_roots"] == str(len(roots))
    assert result["vertex"] == vertex
    assert predicates("QuadraticExplorer", {"a": 0, "b": 1, "c": 1}) == ["a_nonzero"]


def test_inequality_region():
    raw = {"inequalities": ["x > -1", "y > x", "y < 4"]}
    result = values("InequalityRegion", raw)
    # x > -1, y > x, y < 4: (0,1), (0,2), (0,3), (1,2), (1,3), (2,3).
    assert result["integer_points"] == "6"
    assert result["line_1_style"] == "broken"
    assert predicates("InequalityRegion", {"inequalities": ["y > x**2"]}) == ["inequality_parses"]
    assert predicates("InequalityRegion", {"inequalities": ["y = x"]}) == ["inequality_parses"]
    empty = {"inequalities": ["y > 5", "y < 1"]}
    assert predicates("InequalityRegion", empty) == ["region_not_empty"]


@pytest.mark.parametrize(
    ("terms", "kind", "nth"),
    [
        ([5, 8, 11, 14], "linear", "3*n + 2"),
        ([2, 6, 12, 20, 30], "quadratic", "n**2 + n"),
        ([1, 8, 27, 64, 125], "cubic", "n**3"),
        ([3, 6, 12, 24], "geometric", "3*2**(n - 1)"),
        ([20, 17, 14, 11], "linear", "23 - 3*n"),
    ],
)
def test_sequence_pattern_finds_the_nth_term(terms, kind, nth):
    result = values("SequencePattern", {"terms": terms})
    assert (result["kind"], result["nth_term"]) == (kind, nth)


def test_sequence_pattern_predicates():
    assert predicates("SequencePattern", {"terms": [1, 2, 4, 7, 13]}) == ["pattern_found"]
    assert predicates("SequencePattern", {"terms": [1, 8, 27, 64]}) == ["pattern_found"]
    big = {"terms": [10, 20, 30, 40], "show_pattern": True}
    assert predicates("SequencePattern", big) == ["pattern_drawable"]
    assert values("SequencePattern", {"terms": [5, 8, 11, 14]})["next_term"] == "17"


def test_proportion_graph():
    result = values(
        "ProportionGraph", {"kind": "direct", "power": "2", "known": [2, 12], "find_x": 5}
    )
    assert (result["k"], result["found_y"]) == ("3", "75")
    inverse = {"kind": "inverse", "power": "2", "known": [2, 9], "find_y": 4}
    assert values("ProportionGraph", inverse)["found_x"] == "3"
    both = inverse | {"find_x": 1}
    assert predicates("ProportionGraph", both) == ["one_unknown"]


def test_curve_sketch_features():
    cubic = values("CurveSketch", {"expression": "x**3 - 3*x", "x_min": -2.5, "x_max": 2.5})
    assert cubic["roots"] == "-root 3, 0, root 3"
    assert (cubic["turning_1"], cubic["turning_1_kind"]) == ("(-1, 2)", "maximum")
    assert (cubic["turning_2"], cubic["turning_2_kind"]) == ("(1, -2)", "minimum")
    reciprocal = values("CurveSketch", {"expression": "1/(x - 2) + 1", "x_min": -3, "x_max": 7})
    assert reciprocal["vertical_asymptote_1"] == "x = 2"
    assert reciprocal["horizontal_asymptote"] == "y = 1"
    assert reciprocal["y_intercept"] == "1/2"
    exponential = values("CurveSketch", {"expression": "2**x - 3", "x_min": -3, "x_max": 3})
    assert exponential["roots"] == "1.58"
    assert exponential["horizontal_asymptote"] == "y = -3"
    assert predicates("CurveSketch", {"expression": "5", "x_min": 0, "x_max": 1}) == [
        "not_constant"
    ]
    assert predicates("CurveSketch", {"expression": "sqrt(x)", "x_min": -10, "x_max": 1}) == [
        "real_on_interval"
    ]


def test_function_machine():
    raw = {"operations": ["*2", "+3"], "inputs": [4], "show_inverse": True}
    result = values("FunctionMachine", raw)
    assert (result["function"], result["output_1"], result["inverse"]) == (
        "2*x + 3",
        "11",
        "(x - 3)/2",
    )
    square = {"operations": ["**2"], "show_inverse": True}
    assert predicates("FunctionMachine", square) == ["invertible"]
    assert predicates("FunctionMachine", {"operations": ["sqrt"], "inputs": [-4]}) == [
        "real_values"
    ]
    assert predicates("FunctionMachine", {"operations": ["log"]}) == ["operation_parses"]


def test_graphical_solution():
    raw = {"curve": "x**2", "line": "2*x + 3", "x_min": -3, "x_max": 5}
    result = values("GraphicalSolution", raw)
    assert (result["solution_1"], result["solution_2"]) == ("-1", "3")
    apart = raw | {"line": "-1"}
    assert predicates("GraphicalSolution", apart) == ["graphs_meet"]
    assert predicates("GraphicalSolution", raw | {"line": "x**2"}) == ["different_graphs"]
    exponential = {"curve": "2**x", "line": "3 - x", "x_min": -2, "x_max": 4}
    assert values("GraphicalSolution", exponential)["solution_1"] == "1"


# Coordinate geometry


def test_coordinate_plotter():
    result = values("CoordinatePlotter", {"point_a": [1, 2], "point_b": [4, 8]})
    assert (result["midpoint"], result["length"]) == ("(5/2, 5)", "3 root 5")
    assert values("CoordinatePlotter", {"point_a": [0, 0], "point_b": [3, 4]})["length"] == "5"
    same = {"point_a": [1, 1], "point_b": [1, 1]}
    assert predicates("CoordinatePlotter", same) == ["distinct_points"]


def test_line_builder():
    result = values("LineBuilder", {"gradient": -0.5, "intercept": 3})
    assert (result["run"], result["rise"], result["x_intercept"]) == ("2", "-1", "6")
    assert result["general_form"] == "x + 2*y = 6"
    assert values("LineBuilder", {"gradient": 2, "intercept": -1})["general_form"] == "2*x - y = 1"


def test_parallel_perpendicular():
    perpendicular = {"mode": "perpendicular", "gradient": 2, "intercept": 1, "point": [4, 1]}
    result = values("ParallelPerpendicular", perpendicular)
    assert (result["new_gradient"], result["new_line"]) == ("-1/2", "y = 3 - x/2")
    parallel = perpendicular | {"mode": "parallel"}
    assert values("ParallelPerpendicular", parallel)["new_line"] == "y = 2*x - 7"
    flat = perpendicular | {"gradient": 0}
    assert values("ParallelPerpendicular", flat)["new_line"] == "x = 4"
    bisector = {"mode": "bisector", "point_a": [-2, 1], "point_b": [4, 5]}
    result = values("ParallelPerpendicular", bisector)
    assert (result["midpoint"], result["new_gradient"]) == ("(1, 3)", "-3/2")
    assert predicates("ParallelPerpendicular", {"mode": "parallel", "gradient": 1}) == [
        "needs_line_and_point"
    ]
    assert predicates("ParallelPerpendicular", {"mode": "bisector"}) == ["needs_two_points"]


def test_coordinate_circle():
    raw = {"centre": [2, 1], "radius": 5, "line_gradient": 1, "line_intercept": 4}
    result = values("CoordinateCircle", raw)
    assert (result["meets"], result["meet_1"], result["meet_2"]) == ("2", "(-3, 1)", "(2, 6)")
    assert result["expanded"] == "x**2 - 4*x + y**2 - 2*y - 20 = 0"
    tangent = {"centre": [0, 0], "radius": 5, "line_gradient": 0.75, "line_intercept": 6.25}
    assert values("CoordinateCircle", tangent)["meets"] == "1"
    miss = {"centre": [0, 0], "radius": 1, "line_gradient": 1, "line_intercept": 5}
    assert values("CoordinateCircle", miss)["meets"] == "0"
    half_line = {"centre": [0, 0], "radius": 1, "line_gradient": 1}
    assert predicates("CoordinateCircle", half_line) == ["whole_line"]


# Calculus


def test_derivative_panels():
    result = values("DerivativePanels", {"expression": "x**3 - 3*x", "x_min": -2.5, "x_max": 2.5})
    assert result["derivative"] == "3*x**2 - 3"
    assert (result["stationary_1"], result["stationary_1_kind"]) == ("(-1, 2)", "maximum")
    assert (result["stationary_2"], result["stationary_2_kind"]) == ("(1, -2)", "minimum")
    corner = {"expression": "abs(x)", "x_min": -2, "x_max": 2}
    assert predicates("DerivativePanels", corner) == ["differentiable"]


@pytest.mark.parametrize(
    ("raw", "derivative"),
    [
        ({"rule": "power", "expression": "3*x**4 - 2/x"}, "12*x**3 + 2/x**2"),
        ({"rule": "chain", "inner": "3*x + 1", "outer": "u**5"}, "15*(3*x + 1)**4"),
        ({"rule": "product", "u": "x**2", "v": "x - 1"}, "x*(3*x - 2)"),
        ({"rule": "quotient", "u": "2*x + 1", "v": "x - 3"}, "-7/(x - 3)**2"),
    ],
)
def test_differentiation_stepper(raw, derivative):
    assert values("DifferentiationStepper", raw)["derivative"] == derivative


def test_differentiation_stepper_predicates():
    assert predicates("DifferentiationStepper", {"rule": "chain", "inner": "x"}) == ["rule_inputs"]
    not_powers = {"rule": "power", "expression": "sin(x)"}
    assert predicates("DifferentiationStepper", not_powers) == ["power_terms"]
    trivial = {"rule": "chain", "inner": "3*x", "outer": "u"}
    assert predicates("DifferentiationStepper", trivial) == ["outer_not_u"]
    at_pole = {"rule": "power", "expression": "1/x", "at_x": 0}
    assert predicates("DifferentiationStepper", at_pole) == ["gradient_defined"]
    at_one = {"rule": "power", "expression": "x**3", "at_x": 2}
    assert values("DifferentiationStepper", at_one)["gradient_at_x"] == "12"


def test_tangent_normal():
    raw = {"expression": "x**2 - 2*x", "x_min": -1, "x_max": 4, "x0": 2.5}
    result = values("TangentNormal", raw)
    assert (result["tangent"], result["normal"]) == ("y = 3*x - 25/4", "y = 25/12 - x/3")
    flat = {"expression": "x**3 - 3*x", "x_min": -2, "x_max": 2, "x0": 1}
    assert values("TangentNormal", flat)["normal"] == "x = 1"
    outside = raw | {"x0": 7}
    assert predicates("TangentNormal", outside) == ["point_in_interval"]


def test_area_between_curves():
    assert values("AreaBetweenCurves", {"upper": "4 - x**2", "lower": "x + 2"})["area"] == "9/2"
    assert values("AreaBetweenCurves", {"upper": "sqrt(x)", "lower": "x**2"})["area"] == "1/3"
    swapped = {"upper": "x + 2", "lower": "4 - x**2"}
    assert predicates("AreaBetweenCurves", swapped) == ["upper_above_lower"]
    apart = {"upper": "x**2 + 5", "lower": "x"}
    assert predicates("AreaBetweenCurves", apart) == ["limits_found"]


def test_kinematics_graphs():
    raw = {"expression": "t**3 - 6*t**2 + 9*t", "t_max": 4}
    result = values("KinematicsGraphs", raw)
    assert (result["velocity"], result["acceleration"]) == ("3*t**2 - 12*t + 9", "6*t - 12")
    assert (result["rest_1_time"], result["rest_2_time"]) == ("1", "3")
    assert result["rest_1_displacement"] == "4"
    velocity = {"given": "velocity", "expression": "12 - 3*t**2", "s0": 2, "t_max": 3}
    result = values("KinematicsGraphs", velocity)
    assert (result["displacement"], result["rest_1_time"]) == ("-t**3 + 12*t + 2", "2")


@pytest.mark.parametrize(
    ("scenario", "size", "best", "value"),
    [
        ("open_box", 12, "2", "128"),
        ("fence_wall", 40, "10", "200"),
        ("rectangle", 20, "5", "25"),
        ("cylinder", 500, "4.3", "349"),
    ],
)
def test_optimisation_scene(scenario, size, best, value):
    result = values("OptimisationScene", {"scenario": scenario, "size": size})
    assert (result["best_x"], result["best_value"]) == (best, value)


# Number, and the rest of the core


def test_growth_decay():
    result = values(
        "GrowthDecay", {"initial": 1000, "rate": 5, "periods": 10, "compare_simple": True}
    )
    assert (result["multiplier"], result["final"], result["simple_final"]) == (
        "1.05",
        "1628.89",
        "1500.00",
    )
    decay = values("GrowthDecay", {"initial": 15000, "rate": -20, "periods": 6})
    assert decay["final"] == "3932.16"
    people = values("GrowthDecay", {"initial": 2400, "rate": 3, "periods": 20, "unit": "people"})
    assert people["final"] == "4335"
    assert predicates("GrowthDecay", {"initial": 100, "rate": 0, "periods": 2}) == ["rate_nonzero"]


def test_unit_circle_waves():
    result = values("UnitCircleWaves", {"function": "sin", "a": 2, "b": 2, "c": 1})
    assert (result["amplitude"], result["period"]) == ("2", "180")
    assert (result["maximum"], result["minimum"]) == ("3", "-1")
    assert predicates("UnitCircleWaves", {"function": "cos", "a": 0}) == ["a_nonzero"]


def test_connected_rates():
    circle = values("ConnectedRates", {"shape": "circle", "rate": 2, "at": 5})
    assert circle["answer"] == "62.8"  # 20π
    sphere = {"shape": "sphere", "known": "quantity", "rate": 100, "at": 3}
    assert values("ConnectedRates", sphere)["answer"] == "0.884"  # 25/(9π)
    cube = values("ConnectedRates", {"shape": "cube", "rate": 0.5, "at": 4})
    assert cube["answer"] == "24"


def test_inverse_graph():
    assert (
        values("InverseGraph", {"expression": "2*x + 1", "x_min": -3, "x_max": 2})["inverse"]
        == "x/2 - 1/2"
    )
    square = {"expression": "x**2", "x_min": 0, "x_max": 2.5, "point_x": 2}
    result = values("InverseGraph", square)
    assert (result["inverse"], result["reflected"]) == ("sqrt(x)", "(4, 2)")
    both_sides = {"expression": "x**2", "x_min": -2, "x_max": 2}
    assert predicates("InverseGraph", both_sides) == ["one_to_one"]
    on_mirror = {"expression": "x**3", "x_min": -1.5, "x_max": 1.5, "point_x": 1}
    assert predicates("InverseGraph", on_mirror) == ["point_off_mirror"]


@pytest.mark.parametrize(
    ("raw", "solutions"),
    [
        ({"equation_1": "3*x + 2*y = 16", "equation_2": "x - 2*y = 0"}, [("4", "2")]),
        ({"equation_1": "2*x + 3*y = 13", "equation_2": "5*x - 2*y = 4"}, [("2", "3")]),
        (
            {"equation_1": "y = x**2 - 3", "equation_2": "y = 2*x", "method": "substitution"},
            [("-1", "-2"), ("3", "6")],
        ),
    ],
)
def test_simultaneous_equations(raw, solutions):
    result = values("SimultaneousEquations", raw)
    found = [(result[f"x_{i}"], result[f"y_{i}"]) for i in range(1, len(solutions) + 1)]
    assert found == solutions


def test_simultaneous_equations_predicates():
    parallel = {"equation_1": "x + y = 2", "equation_2": "2*x + 2*y = 7"}
    assert predicates("SimultaneousEquations", parallel) == ["one_solution"]
    curve = {"equation_1": "y = x**2", "equation_2": "x + y = 2"}
    assert predicates("SimultaneousEquations", curve) == ["linear_equations"]
    apart = {"equation_1": "y = x**2 + 5", "equation_2": "y = x", "method": "substitution"}
    assert predicates("SimultaneousEquations", apart) == ["real_solution"]


def test_table_of_values():
    result = values(
        "TableOfValues", {"expression": "x**3 - 4*x", "x_min": -2.5, "x_max": 2.5, "step": 0.5}
    )
    assert result["y_at_-2.5"] == "-5.63"  # -5.625, half rounded up
    assert result["y_at_2.5"] == "5.63"
    reciprocal = {"expression": "1/x", "x_min": -2, "x_max": 2}
    assert predicates("TableOfValues", reciprocal) == ["defined_at_each_x"]
    many = {"expression": "x", "x_min": -10, "x_max": 10, "step": 1}
    assert predicates("TableOfValues", many) == ["few_columns"]


def test_number_line():
    result = values("NumberLine", {"numbers": ["0.3", "1/3", "0.33", "pi/10"]})
    assert result["in_order"] == "0.3, pi/10, 0.33, 1/3"
    integers = {"inequality": "-3 <= x < 2", "integers_only": True}
    assert values("NumberLine", integers)["integers"] == "-3, -2, -1, 0, 1"
    assert predicates("NumberLine", {"inequality": "x = 3"}) == ["inequality_parses"]
    assert predicates("NumberLine", {"numbers": ["sqrt(-1)"]}) == ["real_number"]


def test_prime_factor_tree():
    result = values("PrimeFactorTree", {"number": 360, "other": 84})
    assert (result["index_form"], result["hcf"], result["lcm"]) == ("2^3 x 3^2 x 5", "12", "2520")
    assert predicates("PrimeFactorTree", {"number": 97}) == ["composite"]


def test_venn_diagram():
    raw = {
        "sets": [["1", "2", "3", "4", "6", "12"], ["2", "4", "6", "8", "10"]],
        "universal": ["5", "7", "9", "11"],
        "shade": "A ∩ B",
    }
    result = values("VennDiagram", raw)
    assert (result["n_shaded"], result["shaded_elements"], result["n_universal"]) == (
        "3",
        "2, 4, 6",
        "12",
    )
    counts = {
        "counts": {"A": 4, "B": 3, "C": 6, "AB": 2, "AC": 1, "BC": 5, "ABC": 7, "": 2},
        "set_count": 3,
        "shade": "(A ∩ B) ∪ C'",
    }
    assert values("VennDiagram", counts)["n_shaded"] == "18"
    assert values("VennDiagram", counts | {"shade": "A' ∩ B'"})["n_shaded"] == "8"
    assert predicates("VennDiagram", counts | {"shade": "A ∩ D"}) == ["shade_parses"]
    assert predicates("VennDiagram", {"counts": {"AD": 1}}) == ["region_keys"]


@pytest.mark.parametrize(
    ("operation", "first", "second", "result"),
    [
        ("add", "3/4", "2/3", "17/12"),
        ("subtract", "5/6", "1/4", "7/12"),
        ("multiply", "2/3", "3/4", "1/2"),
        ("divide", "3/4", "1/8", "6"),
    ],
)
def test_fraction_model(operation, first, second, result):
    raw = {"operation": operation, "first": first, "second": second}
    assert values("FractionModel", raw)["result"] == result


def test_fraction_model_predicates():
    assert predicates("FractionModel", {"operation": "add", "first": "1/2"}) == ["needs_second"]
    bigger = {"operation": "subtract", "first": "1/4", "second": "1/2"}
    assert predicates("FractionModel", bigger) == ["difference_positive"]
    improper = {"operation": "multiply", "first": "3/2", "second": "1/2"}
    assert predicates("FractionModel", improper) == ["proper_for_area"]
    assert (
        values("FractionModel", {"operation": "add", "first": "3/4", "second": "2/3"})["mixed"]
        == "1 5/12"
    )
