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
        ("cylinder", 500, "4.30", "349"),
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


# Number and geometry


@pytest.mark.parametrize(
    ("raw", "answer"),
    [
        ({"kind": "increase", "amount": 80, "percent": 15}, "92.00"),
        ({"kind": "of", "amount": 240, "percent": 35}, "84.00"),
        ({"kind": "reverse_increase", "amount": 69, "percent": 15}, "60.00"),
        ({"kind": "reverse_decrease", "amount": 340, "percent": 15}, "400.00"),
        ({"kind": "change", "amount": 40, "new_amount": 52}, "30"),
    ],
)
def test_percentage_bar(raw, answer):
    assert values("PercentageBar", raw)["answer"] == answer


def test_percentage_bar_predicates():
    assert predicates("PercentageBar", {"kind": "decrease", "amount": 10, "percent": 120}) == [
        "decrease_below_100"
    ]
    assert predicates("PercentageBar", {"kind": "change", "amount": 10}) == ["needs_new_amount"]


def test_standard_form():
    assert values("StandardForm", {"number": "34500000"})["standard_form"] == "3.45 x 10^7"
    assert values("StandardForm", {"number": "0.000345"})["standard_form"] == "3.45 x 10^-4"
    calc = {"number": "0.0072", "operation": "divide", "other": "900000"}
    assert values("StandardForm", calc)["result"] == "8 x 10^-9"
    assert predicates("StandardForm", {"number": "0"}) == ["nonzero"]


def test_index_laws():
    raw = {
        "lines": ["27**(2/3)", "(27**(1/3))**2", "3**2", "9"],
        "laws": ["power", "fractional", "evaluate"],
    }
    assert predicates("IndexLaws", raw) == []
    assert values("IndexLaws", raw)["result"] == "9"
    wrong = {"lines": ["x**3 * x**4", "x**12"], "laws": ["multiply"]}
    assert predicates("IndexLaws", wrong) == ["step_equivalent"]


@pytest.mark.parametrize(
    ("raw", "answer"),
    [
        ({"kind": "simplify", "number": 72}, "6*sqrt(2)"),
        ({"kind": "combine", "expression": "2*sqrt(12) + sqrt(27) - sqrt(3)"}, "6*sqrt(3)"),
        (
            {"kind": "rationalise", "numerator": "6", "denominator": "3 - sqrt(5)"},
            "(3*sqrt(5) + 9)/2",
        ),
    ],
)
def test_surd_simplifier(raw, answer):
    assert values("SurdSimplifier", raw)["answer"] == answer


def test_surd_simplifier_predicates():
    assert predicates("SurdSimplifier", {"kind": "simplify", "number": 49}) == ["not_square"]
    assert predicates("SurdSimplifier", {"kind": "simplify", "number": 30}) == ["has_square_factor"]
    two_sums = {"kind": "rationalise", "numerator": "1", "denominator": "1 + 2 + sqrt(3)"}
    assert predicates("SurdSimplifier", two_sums) == ["two_terms"]


def test_ratio_splitter():
    share = values(
        "RatioSplitter", {"ratio": [2, 3], "names": ["Ali", "Sara"], "kind": "share", "amount": 40}
    )
    assert (share["Ali"], share["Sara"]) == ("16", "24")
    difference = {"ratio": [2, 5], "kind": "difference", "amount": 45}
    assert values("RatioSplitter", difference)["total"] == "105"
    assert values("RatioSplitter", {"ratio": [12, 18], "kind": "simplify"})["simplest"] == "2:3"
    assert predicates("RatioSplitter", {"ratio": [2, 3], "kind": "simplify"}) == ["can_simplify"]


def test_bounds_interval():
    single = values("BoundsInterval", {"value": "340", "sf": 2})
    assert (single["lower_bound"], single["upper_bound"]) == ("335", "345")
    calc = {
        "value": "250",
        "nearest": "10",
        "operation": "subtract",
        "other": "80",
        "other_nearest": "5",
    }
    result = values("BoundsInterval", calc)
    assert (result["largest"], result["smallest"]) == ("177.5", "162.5")
    assert predicates("BoundsInterval", {"value": "7.45", "nearest": "0.1"}) == ["value_rounded"]


def test_clock_timetable():
    assert values("ClockTimetable", {"kind": "convert", "start": "00:25"})["twelve_hour"] == (
        "12:25 am"
    )
    overnight = {"kind": "interval", "start": "22:45", "end": "01:10"}
    assert values("ClockTimetable", overnight)["duration"] == "2 h 25 min"
    exchange = {"kind": "exchange", "amount": 250, "rate": 278.5}
    assert values("ClockTimetable", exchange)["result"] == "69625.00"
    backwards = {
        "kind": "timetable",
        "stops": ["A", "B"],
        "times": [["09:00"], ["08:00"]],
        "board": 0,
        "leave": 1,
    }
    assert predicates("ClockTimetable", backwards) == ["times_increase"]


@pytest.mark.parametrize(
    ("raw", "x"),
    [
        ({"layout": "line", "angles": ["2*x", "x + 30", "60"]}, "30"),
        ({"layout": "point", "angles": ["110", "3*x", "2*x + 50"]}, "40"),
        ({"layout": "triangle", "angles": ["65", "x", "130"], "exterior": True}, "65"),
        ({"layout": "parallel", "given": 70, "given_at": "upper_bl", "find_at": "lower_tl"}, "110"),
        ({"layout": "parallel", "given": 70, "given_at": "upper_tr", "find_at": "lower_bl"}, "70"),
    ],
)
def test_angle_chaser(raw, x):
    assert values("AngleChaser", raw)["x"] == x


def test_polygon_angles():
    assert values("PolygonAngles", {"kind": "interior_sum", "sides": 8})["interior_angle"] == "135"
    found = values("PolygonAngles", {"kind": "find_sides", "angle": 140, "given": "interior"})
    assert found["sides"] == "9"
    assert predicates("PolygonAngles", {"kind": "find_sides", "angle": 25}) == ["whole_sides"]


@pytest.mark.parametrize(
    ("raw", "x"),
    [
        ({"theorem": "semicircle", "given": 35}, "55"),
        ({"theorem": "centre", "given": 40}, "80"),
        ({"theorem": "centre", "given": 130, "given_at": "centre"}, "65"),
        ({"theorem": "cyclic_quadrilateral", "given": 75}, "105"),
        ({"theorem": "two_tangents", "given": 70}, "55"),
    ],
)
def test_circle_theorems(raw, x):
    assert values("CircleTheorems", raw)["x"] == x


# Geometry, mensuration and trigonometry


@pytest.mark.parametrize(
    ("raw", "key", "value"),
    [
        ({"angle": 35, "hypotenuse": 12, "find": "opposite"}, "opposite", "6.88"),
        ({"angle": 50, "opposite": 8, "find": "hypotenuse"}, "hypotenuse", "10.4"),
        ({"opposite": 5, "adjacent": 12, "find": "angle"}, "angle", "22.6"),
        ({"opposite": 3, "adjacent": 4, "find": "hypotenuse"}, "hypotenuse", "5"),
        ({"hypotenuse": 13, "adjacent": 5, "find": "opposite"}, "opposite", "12"),
    ],
)
def test_right_triangle_trig(raw, key, value):
    assert values("RightTriangleTrig", raw)[key] == value


def test_right_triangle_trig_predicates():
    too_long = {"opposite": 12, "hypotenuse": 10, "find": "adjacent"}
    assert predicates("RightTriangleTrig", too_long) == ["hypotenuse_longest"]
    assert predicates("RightTriangleTrig", {"angle": 40, "find": "opposite"}) == ["one_side"]


@pytest.mark.parametrize(
    ("raw", "key", "value"),
    [
        ({"b": 7, "c": 9, "A": 48, "find": "a"}, "a", "6.76"),
        ({"a": 7, "b": 8, "c": 10, "find": "C"}, "C", "83.3"),
        ({"a": 12, "A": 40, "B": 65, "find": "c"}, "c", "18.0"),
        ({"a": 9, "b": 7, "A": 70, "find": "B"}, "B", "47.0"),
        ({"a": 6, "b": 8, "C": 110, "find": "area"}, "area", "22.6"),
    ],
)
def test_sine_cosine_rule(raw, key, value):
    assert values("SineCosineRule", raw)[key] == value


def test_sine_cosine_rule_predicates():
    no_triangle = {"a": 3, "b": 4, "c": 9, "find": "A"}
    assert predicates("SineCosineRule", no_triangle) == ["triangle_determined"]


@pytest.mark.parametrize(
    ("raw", "key", "value"),
    [
        ({"radius": 6, "angle": 120, "find": "arc"}, "arc", "12.6"),
        ({"radius": 6, "angle": 60, "find": "segment"}, "segment", "3.26"),
        ({"radius": 4, "arc": 6, "find": "angle"}, "angle", "85.9"),
        ({"radius": 5, "angle": 1.2, "radians": True, "find": "area"}, "area", "15"),
    ],
)
def test_circle_sector(raw, key, value):
    assert values("CircleSector", raw)[key] == value


@pytest.mark.parametrize(
    ("raw", "value"),
    [
        ({"solid": "cylinder", "radius": 3, "height": 10, "find": "volume"}, "283"),
        ({"solid": "cone", "radius": 5, "height": 12, "find": "surface_area"}, "283"),
        ({"solid": "pyramid", "width": 6, "height": 4, "find": "surface_area"}, "96"),
        ({"solid": "hemisphere", "radius": 4, "find": "surface_area"}, "151"),
    ],
)
def test_solid_mensuration(raw, value):
    assert values("SolidMensuration", raw)[raw["find"]] == value


def test_solid_mensuration_predicates():
    cuboid = {"solid": "cuboid", "length": 1, "width": 1, "height": 1, "find": "curved_area"}
    assert predicates("SolidMensuration", cuboid) == ["has_curved_surface"]


def test_bearings():
    assert values("Bearings", {"bearing": 65})["back_bearing"] == "245"
    assert values("Bearings", {"bearing": 230})["back_bearing"] == "050"
    journey = values("Bearings", {"bearing": 320, "distance": 12, "find": "components"})
    assert (journey["east"], journey["north"]) == ("-7.71", "9.19")


def test_similarity_scaler():
    assert (
        values("SimilarityScaler", {"sides": [4, 5, 6], "known_value": 12, "find": "side"})["side"]
        == "15"
    )
    area = {"sides": [3, 4, 5], "known_value": 7.5, "find": "area", "small_value": 6}
    assert values("SimilarityScaler", area)["area"] == "37.5"
    volume = {"sides": [3, 4, 5], "known_value": 6, "find": "volume", "small_value": 40}
    assert values("SimilarityScaler", volume)["volume"] == "320"


@pytest.mark.parametrize(
    ("raw", "lines", "order"),
    [
        ({"shape": "rectangle"}, "2", "2"),
        ({"shape": "parallelogram"}, "0", "2"),
        ({"shape": "kite"}, "1", "1"),
        ({"shape": "regular_polygon", "sides": 6}, "6", "6"),
    ],
)
def test_symmetry_reveal(raw, lines, order):
    result = values("SymmetryReveal", raw)
    assert (result["lines"], result["order"]) == (lines, order)


def test_area_dissector_and_net_folder():
    trapezium = {"shape": "trapezium", "base": 9, "height": 4, "top": 5}
    assert values("AreaDissector", trapezium)["area"] == "28"
    assert (
        values("NetFolder", {"solid": "cylinder", "radius": 3, "height": 8})["surface_area"]
        == "207"
    )
    assert (
        values("NetFolder", {"solid": "cuboid", "length": 5, "width": 3, "height": 2})[
            "surface_area"
        ]
        == "62"
    )


def test_compass_construction():
    assert (
        values("CompassConstruction", {"construction": "angle_bisector", "angle": 70})["half_angle"]
        == "35"
    )
    no_triangle = {"construction": "triangle", "sides": [1, 2, 5]}
    assert predicates("CompassConstruction", no_triangle) == ["triangle_exists"]


# Probability, statistics, transformations, vectors and 3D trigonometry


def test_tree_diagram():
    bag = {"outcomes": ["R", "B"], "counts": [3, 2], "replace": False, "find": ["R,B", "B,R"]}
    assert values("TreeDiagram", bag)["probability"] == "3/5"
    coins = {
        "outcomes": ["H", "T"],
        "probabilities": ["1/2", "1/2"],
        "events": 3,
        "find": ["H,H,H"],
    }
    assert values("TreeDiagram", coins)["probability"] == "1/8"
    bad = {"outcomes": ["R", "B"], "probabilities": ["1/2", "1/3"], "find": ["R,R"]}
    assert predicates("TreeDiagram", bad) == ["sum_one"]


def test_sample_space_grid():
    dice = [str(i) for i in range(1, 7)]
    seven = values("SampleSpaceGrid", {"first": dice, "second": dice, "value": 7})
    assert (seven["favourable"], seven["probability"]) == ("6", "1/6")
    six = {"first": dice, "second": dice, "condition": "contains", "contains": "6"}
    assert values("SampleSpaceGrid", six)["probability"] == "11/36"


def test_probability_spinner():
    spinner = {
        "sectors": ["red", "blue", "red", "green", "red", "blue"],
        "event": "red",
        "trials": 120,
    }
    result = values("ProbabilitySpinner", spinner)
    assert (result["probability"], result["not"], result["expected"]) == ("1/2", "1/2", "60")


def test_chart_builder():
    pie = {
        "chart": "pie",
        "categories": ["Bus", "Car", "Walk", "Cycle"],
        "frequencies": [12, 8, 15, 5],
    }
    angles = values("ChartBuilder", pie)
    assert (angles["Bus"], angles["Walk"], angles["total"]) == ("108", "135", "40")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            {"kind": "list", "data": [4, 7, 2, 9, 7, 3, 5, 7, 6]},
            {"mean": "5.56", "median": "6", "mode": "7", "range": "7"},
        ),
        (
            {"kind": "table", "values": [0, 1, 2, 3, 4], "frequencies": [3, 7, 6, 3, 1]},
            {"mean": "1.6", "median": "1.5", "mode": "1"},
        ),
        (
            {"kind": "grouped", "bounds": [0, 10, 20, 30, 40], "frequencies": [4, 9, 12, 5]},
            {"mean": "21", "modal_class": "20 - 30", "median_class": "20 - 30"},
        ),
    ],
)
def test_averages_visualizer(raw, expected):
    result = values("AveragesVisualizer", raw)
    assert {k: result[k] for k in expected} == expected


def test_scatter_best_fit():
    raw = {
        "points": [[2, 52], [3, 55], [5, 61], [6, 60], [8, 70], [9, 71], [11, 78]],
        "estimate_x": 7,
    }
    result = values("ScatterBestFit", raw)
    assert (result["correlation"], result["estimate"]) == ("Strong positive", "65.9")
    none = {"points": [[1, 5], [2, 1], [3, 6], [4, 2], [5, 5], [6, 3]]}
    assert values("ScatterBestFit", none)["correlation"] == "No"


def test_cumulative_frequency_and_histogram():
    ogive = values(
        "CumulativeFrequency",
        {"bounds": [0, 10, 20, 30, 40, 50], "frequencies": [4, 11, 19, 12, 4]},
    )
    assert (ogive["median"], ogive["iqr"]) == ("25.3", "14.2")
    histogram = {
        "bounds": [0, 10, 15, 20, 30, 50],
        "frequencies": [8, 12, 15, 14, 6],
        "between": [12, 25],
    }
    result = values("Histogram", histogram)
    assert (result["density_2"], result["estimate"]) == ("2.4", "29.2")


@pytest.mark.parametrize(
    ("raw", "image"),
    [
        (
            {"kind": "enlargement", "shape": [[1, 1], [3, 1], [1, 2]], "scale": 2},
            "(2, 2); (6, 2); (2, 4)",
        ),
        (
            {"kind": "rotation", "shape": [[1, 1], [3, 1], [1, 2]], "angle": 90, "clockwise": True},
            "(1, -1); (1, -3); (2, -1)",
        ),
        (
            {
                "kind": "reflection",
                "shape": [[1, 1], [3, 1], [1, 2]],
                "mirror": "x=a",
                "line_value": 4,
            },
            "(7, 1); (5, 1); (7, 2)",
        ),
    ],
)
def test_transformation_stage(raw, image):
    assert values("TransformationStage", raw)["image"] == image


def test_vector_arena():
    assert values("VectorArena", {"kind": "magnitude", "a": [3, 4]})["magnitude"] == "5"
    assert values("VectorArena", {"kind": "add", "a": [3, 1], "b": [1, 3]})["result"] == "(4, 4)"
    midpoint = {"kind": "geometry", "a": [4, 0], "b": [2, 4], "ratio": [1, 1]}
    assert values("VectorArena", midpoint)["result"] == "(3, 2)"


def test_trig_3d():
    cuboid = values("Trig3D", {"solid": "cuboid", "length": 8, "width": 6, "height": 5})
    assert (cuboid["shadow"], cuboid["line"], cuboid["angle"]) == ("10", "11.2", "26.6")
    pyramid = values("Trig3D", {"solid": "pyramid", "length": 6, "width": 6, "height": 8})
    assert (pyramid["line"], pyramid["angle"]) == ("9.06", "62.1")


# Text on screen


@pytest.mark.parametrize(
    ("raw", "predicate"),
    [
        ({"layout": "question", "text": "Solve $2x + 3 = 7$"}, None),
        ({"layout": "question", "text": r"A shirt costs \$24 after a 20% discount."}, None),
        ({"layout": "question", "text": r"Find $\input{secret}$"}, "safe_text"),
        ({"layout": "question", "text": r"text with \textbf{markup}"}, "safe_text"),
        ({"layout": "question", "text": "x^2 outside the maths"}, "safe_text"),
        ({"layout": "question", "text": "An unclosed $x + 1"}, "safe_text"),
        ({"layout": "question", "text": r"Braces $\frac{1}{2$"}, "safe_text"),
        ({"layout": "title"}, "needs_title"),
        ({"layout": "points", "title": "Key points"}, "needs_points"),
    ],
)
def test_text_card_only_passes_safe_text(raw, predicate):
    assert predicates("TextCard", raw) == ([predicate] if predicate else [])


def test_text_card_wraps_without_breaking_maths():
    from app.primitives.text_card import _tex, _wrap

    text = "A ladder leans on a wall with its foot $\\sqrt{7} + 2$ m from the wall. How high?"
    for line in _wrap(text, 30):
        assert line.count("$") % 2 == 0
    assert _tex(r"Cost \$5 & 10%") == r"Cost \$5 \& 10\%"


def test_text_card_levels():
    card = get_primitive("TextCard")
    params = card.parse_params(
        {"layout": "points", "title": "Remember", "points": ["SOH CAH TOA", "Angles to 1 d.p."]}
    )
    assert len(card.steps(params, Level.SUPPORTED)) == 3
    assert len(card.steps(params, Level.CONCISE)) == 1
