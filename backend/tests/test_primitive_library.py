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


# A Level (9709): Pure Mathematics 1 and the algebra of Pure Mathematics 2 and 3


def test_graph_transform_follows_a_point_and_builds_the_equation():
    raw = {
        "expression": "x**2",
        "x_min": -2,
        "x_max": 2,
        "transformations": [
            {"kind": "translate_x", "value": 1},
            {"kind": "stretch_y", "value": 2},
            {"kind": "translate_y", "value": -3},
        ],
        "point_x": 1,
    }
    found = values("GraphTransform", raw)
    # y = 2f(x + 1) - 3 with f(x) = x^2: (1, 1) moves left 1, doubles, then drops 3
    assert found["final_expression"] == "2*x**2 + 4*x - 1"
    assert [found[f"point_{k}"] for k in range(4)] == ["(1, 1)", "(0, 1)", "(0, 2)", "(0, -1)"]
    stretch = raw | {"transformations": [{"kind": "stretch_x", "value": 2}]}
    assert values("GraphTransform", stretch)["point_1"] == "(1/2, 1)"
    assert predicates(
        "GraphTransform", stretch | {"transformations": [{"kind": "stretch_x", "value": -2}]}
    ) == ["stretch_factor"]
    assert predicates("GraphTransform", raw | {"point_x": 5}) == ["point_on_graph"]
    assert predicates("GraphTransform", raw | {"expression": "1/x"}) == ["real_and_finite"]


def test_function_mapping_range_one_one_and_composite():
    found = values(
        "FunctionMapping", {"kind": "range", "f": "(x - 2)**2 + 1", "f_min": 0, "f_max": 5}
    )
    assert (found["range_min"], found["range_max"]) == ("1", "10")
    turning = values(
        "FunctionMapping", {"kind": "one_one", "f": "x**2 - 4*x + 7", "f_min": -1, "f_max": 5}
    )
    assert turning["one_one"] == "no" and turning["restricted_domain"] == "-1 <= x <= 2"
    monotonic = values(
        "FunctionMapping", {"kind": "one_one", "f": "1/(x + 1)", "f_min": 0, "f_max": 4}
    )
    assert monotonic["one_one"] == "yes"
    composite = {"kind": "composite", "f": "2*x + 1", "f_min": 0, "f_max": 3, "g": "x**2 - 1"}
    found = values("FunctionMapping", composite)
    assert found["gf"] == "4*x**2 + 4*x"
    assert (found["gf_range_min"], found["gf_range_max"]) == ("0", "48")
    # the range of f (-2 to 3) is not inside the domain of g (x >= 1/2): no gf
    outside = {"kind": "composite", "f": "3 - x", "f_min": 0, "f_max": 5, "g": "1/x", "g_min": 0.5}
    assert values("FunctionMapping", outside)["composite_exists"] == "no"
    assert predicates("FunctionMapping", composite | {"g": None}) == ["g_given"]


def test_line_meets_curve_discriminant():
    found = values("LineMeetsCurve", {"curve": "x**2 - 4*x + 7", "line": "x + k"})
    assert found["discriminant"] == "4*k - 3"
    assert (found["tangent_k_1"], found["tangent_point_1"]) == ("3/4", "(5/2, 13/4)")
    gradient = values("LineMeetsCurve", {"curve": "x**2 + 3", "line": "k*x - 1"})
    assert (gradient["tangent_k_1"], gradient["tangent_k_2"]) == ("-4", "4")
    assert gradient["no_points"] == "Interval.open(-4, 4)"
    assert predicates("LineMeetsCurve", {"curve": "x**3", "line": "x + k"}) == ["curve_quadratic"]
    assert predicates("LineMeetsCurve", {"curve": "x**2", "line": "x + 1"}) == ["line_has_k"]
    assert predicates("LineMeetsCurve", {"curve": "x**2", "line": "k*x**2"}) == ["line_linear"]


@pytest.mark.parametrize(
    ("raw", "solutions"),
    [
        ({"function": "sin", "b": 2, "c": 30, "k": 0.5}, ["0", "60", "180", "240", "360"]),
        ({"function": "cos", "k": -0.5}, ["120", "240"]),
        ({"function": "tan", "k": 2, "x_min": -180, "x_max": 180}, ["-116.6", "63.4"]),
        ({"function": "cos", "b": 3, "k": 0.8, "x_max": 180}, ["12.3", "107.7", "132.3"]),
        (
            {
                "function": "tan",
                "b": 0.5,
                "c": -0.25,
                "k": 1,
                "x_min": -2,
                "x_max": 2,
                "radians": True,
            },
            ["-pi", "pi"],
        ),
    ],
)
def test_trig_equation_solver_finds_every_solution(raw, solutions):
    found = values("TrigEquationSolver", raw)
    assert [found[f"x_{i}"] for i in range(1, int(found["count"]) + 1)] == solutions


def test_trig_equation_solver_predicates():
    assert predicates("TrigEquationSolver", {"function": "sin", "k": 1.5}) == ["value_possible"]
    assert predicates(
        "TrigEquationSolver", {"function": "tan", "k": 1, "x_min": -360, "x_max": 720}
    ) == ["interval_short"]
    assert predicates(
        "TrigEquationSolver", {"function": "sin", "k": 0.5, "x_min": 40, "x_max": 50}
    ) == ["has_solutions"]


def test_binomial_expansion():
    found = values("BinomialExpansion", {"a": 2, "b": 3, "n": 5, "terms": 4})
    assert [found[f"coefficient_{r}"] for r in range(4)] == ["32", "240", "720", "1080"]
    rational = values("BinomialExpansion", {"a": 4, "b": -3, "n": -0.5, "terms": 4})
    assert [rational[f"coefficient_{r}"] for r in range(4)] == ["1/2", "3/16", "27/256", "135/2048"]
    assert rational["valid_for"] == "|x| < 4/3"
    assert predicates("BinomialExpansion", {"a": 1, "b": 1, "n": 3, "terms": 5}) == ["terms_exist"]
    assert predicates("BinomialExpansion", {"a": -2, "b": 1, "n": 0.5}) == ["a_positive"]
    assert predicates("BinomialExpansion", {"a": 1, "b": 1, "n": 4, "find_power": 4}) == [
        "power_shown"
    ]


@pytest.mark.parametrize(
    ("raw", "answer"),
    [
        ({"kind": "arithmetic", "a": 3, "d": 2, "find": "sum", "n": 8}, "80"),
        ({"kind": "arithmetic", "a": 50, "d": -7, "find": "nth_term", "n": 9}, "-6"),
        ({"kind": "geometric", "a": 64, "r": 0.5, "find": "sum", "n": 7}, "127"),
        ({"kind": "geometric", "a": 10, "r": -0.6, "find": "sum_to_infinity"}, "25/4"),
    ],
)
def test_progression_answers(raw, answer):
    assert values("Progression", raw)["answer"] == answer


def test_progression_predicates():
    assert predicates(
        "Progression", {"kind": "geometric", "a": 1, "r": 2, "find": "sum_to_infinity"}
    ) == ["convergent"]
    assert predicates(
        "Progression", {"kind": "arithmetic", "a": 1, "d": 1, "find": "sum_to_infinity"}
    ) == ["convergent"]
    assert predicates(
        "Progression", {"kind": "geometric", "a": 1, "r": 1, "find": "sum", "n": 5}
    ) == ["ratio_not_one"]


def test_antiderivative_family_constant():
    found = values(
        "AntiderivativeFamily", {"gradient": "3*x**2 - 4", "point": [2, 5], "x_min": -3, "x_max": 3}
    )
    assert (found["c"], found["curve"]) == ("5", "x**3 - 4*x + 5")
    chain = values(
        "AntiderivativeFamily",
        {"gradient": "(2*x - 1)**3", "point": [1, 0], "x_min": 0, "x_max": 2},
    )
    assert chain["integral"] == "(2*x - 1)**4/8"  # kept as a power, as A Level writes it
    assert chain["c"] == "-1/8"


@pytest.mark.parametrize(
    ("raw", "volume"),
    [
        ({"axis": "x", "curve": "sqrt(x)", "lower": 0, "upper": 4}, "8*pi"),
        ({"axis": "x", "curve": "9 - x**2", "lower": -2, "upper": 2, "inner": "5"}, "704*pi/5"),
        ({"axis": "y", "curve": "2/y", "lower": 1, "upper": 4}, "3*pi"),
    ],
)
def test_volume_of_revolution(raw, volume):
    assert values("VolumeOfRevolution", raw)["volume"] == volume


def test_volume_of_revolution_predicates():
    base = {"axis": "x", "curve": "x - 1", "lower": 0, "upper": 2}
    assert predicates("VolumeOfRevolution", base) == ["one_side_of_axis"]
    assert predicates("VolumeOfRevolution", base | {"curve": "y"}) == ["expression_parses"]
    washer = {"axis": "x", "curve": "2", "lower": 0, "upper": 1, "inner": "3"}
    assert predicates("VolumeOfRevolution", washer) == ["inner_inside"]


@pytest.mark.parametrize(
    ("raw", "solution"),
    [
        ({"left": "abs(3*x - 2)", "right": "abs(2*x + 7)"}, "{-1, 9}"),
        ({"left": "2*x + 5", "relation": "<", "right": "abs(x + 1)"}, "Interval.open(-oo, -2)"),
        ({"left": "abs(x - 3)", "relation": "<=", "right": "4"}, "Interval(-1, 7)"),
        ({"left": "abs(x + 2)", "right": "3*x - 4"}, "{3}"),  # the other case's root is rejected
    ],
)
def test_modulus_equation(raw, solution):
    assert values("ModulusEquation", raw)["solution"] == solution


def test_modulus_equation_predicates():
    assert predicates("ModulusEquation", {"left": "x + 1", "right": "3"}) == ["has_modulus"]
    assert predicates("ModulusEquation", {"left": "abs(x**2 - 1)", "right": "3"}) == [
        "linear_inside"
    ]
    assert predicates("ModulusEquation", {"left": "abs(x)", "right": "-1"}) == ["has_solutions"]


def test_polynomial_division():
    found = values(
        "PolynomialDivision", {"dividend": "2*x**3 + 3*x**2 - 8*x + 3", "divisor": "x - 1"}
    )
    assert (found["quotient"], found["remainder"], found["is_factor"]) == (
        "2*x**2 + 5*x - 3",
        "0",
        "yes",
    )
    rest = values(
        "PolynomialDivision", {"dividend": "6*x**3 + x**2 - 5*x + 2", "divisor": "2*x - 1"}
    )
    assert rest["remainder"] == "1/2" and rest["remainder_theorem"] == "f(1/2) = 1/2"
    quadratic = values(
        "PolynomialDivision", {"dividend": "x**4 + 2*x**3 - x + 5", "divisor": "x**2 + 1"}
    )
    assert (quadratic["quotient"], quadratic["remainder"]) == ("x**2 + 2*x - 1", "6 - 3*x")
    assert predicates("PolynomialDivision", {"dividend": "x**2 + 1", "divisor": "x**2"}) == [
        "degree_order"
    ]


# A Level (9709): Pure Mathematics 2 and 3


def test_partial_fractions_recombine():
    import sympy as sp

    x = sp.Symbol("x", real=True)
    for raw in GRIDS["PartialFractions"]:
        found = values("PartialFractions", raw)
        original = sp.sympify(raw["numerator"], locals={"x": x}) / sp.sympify(
            raw["denominator"], locals={"x": x}
        )
        assert sp.simplify(sp.sympify(found["result"], locals={"x": x}) - original) == 0
    simple = values("PartialFractions", {"numerator": "5*x + 1", "denominator": "(x + 1)*(x - 2)"})
    assert (simple["A"], simple["B"]) == ("4/3", "11/3")  # A over (x + 1), as written


def test_partial_fractions_predicates():
    raw = {"numerator": "x**2", "denominator": "(x + 1)*(x - 2)"}
    assert predicates("PartialFractions", raw) == ["proper"]
    raw = {"numerator": "1", "denominator": "(x + 1)**3"}
    assert predicates("PartialFractions", raw) == ["denominator_type"]
    raw = {"numerator": "x + 1", "denominator": "(x + 1)*(x - 2)"}
    assert predicates("PartialFractions", raw) == ["no_common_factor"]


def test_log_linearisation_reads_the_constants():
    power = values("LogLinearisation", {"model": "power", "points": [[2, 5.66], [8, 45.3]]})
    assert (power["n"], power["k"]) == ("1.50", "2.00")
    decay = values("LogLinearisation", {"model": "exponential", "points": [[1, 40], [3, 10]]})
    assert (decay["a"], decay["k"]) == ("0.5", "80")  # exact values are not padded
    bad = {"model": "power", "points": [[0, 1], [1, 2]]}
    assert predicates("LogLinearisation", bad) == ["positive_x"]


def test_harmonic_form():
    found = values("HarmonicForm", {"a": 3, "b": 4, "form": "R sin(t + a)"})
    assert (found["R"], found["alpha"], found["maximum_at"]) == ("5", "53.1", "36.9")
    solved = values("HarmonicForm", {"a": 3, "b": 2, "form": "R sin(t + a)", "solve_for": -2})
    assert (solved["theta_1"], solved["theta_2"]) == ("180.0", "292.6")
    cosine = values("HarmonicForm", {"a": -2, "b": 3, "form": "R cos(t + a)", "solve_for": 1})
    assert (cosine["theta_1"], cosine["theta_2"]) == ("40.2", "252.4")
    wrong = {"a": 3, "b": -4, "form": "R sin(t + a)"}
    assert predicates("HarmonicForm", wrong) == ["form_matches"]
    too_big = {"a": 3, "b": 4, "form": "R sin(t + a)", "solve_for": 6}
    assert predicates("HarmonicForm", too_big) == ["value_possible"]


def test_trapezium_rule():
    found = values(
        "TrapeziumRule", {"expression": "sin(x)", "lower": "0", "upper": "pi", "strips": 4}
    )
    assert (found["estimate"], found["exact"], found["shape"]) == ("1.90", "2", "under")
    convex = values("TrapeziumRule", {"expression": "x**3", "lower": "1", "upper": "3"})
    assert convex["shape"] == "over"
    line = values(
        "TrapeziumRule", {"expression": "2*x + 1", "lower": "0", "upper": "4", "strips": 2}
    )
    assert (line["estimate"], line["shape"]) == ("20", "exact")
    assert predicates("TrapeziumRule", {"expression": "x", "lower": "2", "upper": "1"}) == [
        "limits_ordered"
    ]


def test_iteration_diagram():
    found = values(
        "IterationDiagram", {"iteration": "(x + 5)**(1/3)", "x0": 2, "sign_change": [1, 2]}
    )
    assert (found["converges"], found["root"]) == ("yes", "1.90")
    runaway = values("IterationDiagram", {"iteration": "(x**2 + 3)/5", "x0": 5})
    assert runaway["converges"] == "no"
    no_change = {"iteration": "(x + 5)**(1/3)", "x0": 2, "sign_change": [2, 3]}
    assert predicates("IterationDiagram", no_change) == ["sign_changes"]


def test_parametric_curve():
    found = values("ParametricCurve", {"x": "t**2", "y": "2*t", "t_min": -2, "t_max": 2, "t0": 1})
    assert (found["dy_dx"], found["point"], found["line"]) == ("1/t", "(1, 2)", "y = x + 1")
    normal = {"x": "2*t + 1", "y": "4/t", "t_min": 0.5, "t_max": 4, "t0": 2, "line": "normal"}
    assert values("ParametricCurve", normal)["line"] == "y = 2*x - 8"
    vertical = {"x": "t**2", "y": "t", "t_min": -1, "t_max": 1, "t0": 0}
    assert predicates("ParametricCurve", vertical) == ["gradient_defined"]


def test_implicit_curve():
    raw = {
        "equation": "x**2 + y**2 = x*y + 7",
        "point": [3, 2],
        "x_min": -4,
        "x_max": 4,
        "y_min": -4,
        "y_max": 4,
    }
    found = values("ImplicitCurve", raw)
    assert (found["gradient"], found["line"]) == ("-4", "14 - 4*x")
    assert predicates("ImplicitCurve", raw | {"point": [1, 1]}) == ["point_on_curve"]
    circle = raw | {"equation": "x**2 + y**2 = 9", "point": [3, 0]}
    assert predicates("ImplicitCurve", circle) == ["gradient_defined"]


@pytest.mark.parametrize(
    ("raw", "result"),
    [
        (
            {"method": "parts", "integrand": "x*ln(x)", "u": "ln(x)", "lower": "1", "upper": "2"},
            "-3/4 + log(4)",
        ),
        (
            {
                "method": "substitution",
                "integrand": "x*sqrt(x**2 + 1)",
                "u": "x**2 + 1",
                "lower": "0",
                "upper": "2",
            },
            "-1/3 + 5*sqrt(5)/3",
        ),
        (
            {"method": "log_form", "integrand": "tan(x)", "lower": "0", "upper": "pi/4"},
            "log(sqrt(2))",
        ),
    ],
)
def test_integration_method_definite(raw, result):
    assert values("IntegrationMethod", raw)["value"] == result


def test_integration_method_predicates():
    wrong_u = {"method": "parts", "integrand": "x*exp(x**2)", "u": "x"}
    assert predicates("IntegrationMethod", wrong_u) == ["method_fits"]
    not_log = {"method": "log_form", "integrand": "x/(x + 1)"}
    assert predicates("IntegrationMethod", not_log) == ["method_fits"]
    assert predicates("IntegrationMethod", {"method": "parts", "integrand": "x*sin(x)"}) == [
        "u_given"
    ]


@pytest.mark.parametrize(
    ("gradient", "point", "particular"),
    [
        ("x*y", [0, 1], "y = exp(x**2/2)"),
        ("(y - 1)/x", [1, 3], "y = 2*x + 1"),
        ("-0.5*y", [0, 8], "y = 8*exp(-x/2)"),
        ("x/y", [0, 2], "y = sqrt(x**2 + 4)"),
    ],
)
def test_differential_equation_particular_solution(gradient, point, particular):
    raw = {
        "gradient": gradient,
        "point": point,
        "x_min": 0.5 if gradient.endswith("/x") else -2,
        "x_max": 2,
    }
    assert values("DifferentialEquation", raw)["particular"] == particular


def test_differential_equation_predicates():
    base = {"point": [0, 1], "x_min": -1, "x_max": 1}
    assert predicates("DifferentialEquation", base | {"gradient": "x + y"}) == ["separable"]
    assert predicates("DifferentialEquation", base | {"gradient": "x*(y - 1)"}) == ["solvable"]


def test_vector_lines_3d():
    meet = {"kind": "intersection", "a": [1, 2, 0], "b": [1, 0, 1], "c": [3, 1, 1], "d": [0, 1, 1]}
    assert values("VectorLines3D", meet) == {"point": "(3, 2, 2)", "relation": "meet"}
    skew = {
        "kind": "intersection",
        "a": [1, 0, 2],
        "b": [2, 1, -1],
        "c": [0, 3, 1],
        "d": [1, -1, 2],
    }
    assert values("VectorLines3D", skew)["relation"] == "skew"
    parallel = meet | {"c": [3, 0, 0], "d": [-2, 0, -2]}
    assert values("VectorLines3D", parallel)["relation"] == "parallel"
    angle = {"kind": "angle", "a": [1, 0, 0], "b": [2, -1, 2], "c": [0, 1, 3], "d": [1, 1, 0]}
    assert values("VectorLines3D", angle)["angle"] == "76.4"
    foot = {"kind": "foot", "a": [1, 2, 3], "b": [1, -1, 2], "p": [4, 5, 0]}
    assert values("VectorLines3D", foot) == {"foot": "(0, 3, 1)", "distance": "sqrt(21)"}
    assert predicates("VectorLines3D", foot | {"p": [2, 1, 5]}) == ["point_off_line"]


@pytest.mark.parametrize(
    ("raw", "result"),
    [
        ({"kind": "multiply", "z": [1, 1], "w": [1, 2]}, "-1 + 3*I"),
        ({"kind": "divide", "z": [5, 5], "w": [1, 2]}, "3 - I"),
        ({"kind": "square_roots", "z": [5, 12]}, "3 + 2*I"),
        ({"kind": "conjugate", "z": [2, 3]}, "2 - 3*I"),
    ],
)
def test_argand_diagram(raw, result):
    assert values("ArgandDiagram", raw)["result"] == result


def test_argand_diagram_modulus_argument_is_exact():
    found = values("ArgandDiagram", {"kind": "modulus_argument", "z": [-1, "sqrt(3)"]})
    assert (found["modulus"], found["argument"]) == ("2", "2*pi/3")
    assert predicates("ArgandDiagram", {"kind": "add", "z": [1, 1]}) == ["w_given"]


def test_complex_loci_meeting_points():
    two_half_lines = {
        "loci": [
            {"kind": "half_line", "a": [1, 0], "angle": "3*pi/4"},
            {"kind": "half_line", "a": [-2, 0], "angle": "pi/4"},
        ]
    }
    assert values("ComplexLoci", two_half_lines)["meet_1"] == "-1/2 + 3/2i"
    # a half-line meets the circle once, not twice: the other root is behind its start
    circle_line = {
        "loci": [
            {"kind": "circle", "a": [0, 0], "r": 5},
            {"kind": "half_line", "a": [0, 0], "angle": "pi/4"},
        ]
    }
    found = values("ComplexLoci", circle_line)
    assert "meet_1" in found and "meet_2" not in found
    bad = {"loci": [{"kind": "sector", "a": [0, 0], "angle": "pi/2", "angle_2": "0"}]}
    assert predicates("ComplexLoci", bad) == ["angles_ordered"]


# A Level (9709): Mechanics and Probability & Statistics 1


def test_force_diagram_resolves():
    incline = values("ForceDiagram", GRIDS["ForceDiagram"][0])
    assert (incline["F"], incline["R"], incline["mu"]) == ("12.6", "29.6", "0.425")
    three_forces = values("ForceDiagram", GRIDS["ForceDiagram"][1])
    assert (three_forces["Q"], three_forces["S"]) == ("8.15", "9.22")
    pulled = values("ForceDiagram", GRIDS["ForceDiagram"][2])
    assert (pulled["R"], pulled["a"]) == ("25", "4.93")
    no_mass = {"find": "acceleration", "forces": [{"name": "P", "magnitude": 3, "angle": 0}]}
    assert predicates("ForceDiagram", no_mass)


@pytest.mark.parametrize(
    ("raw", "found"),
    [
        ({"u": 4, "a": 2, "t": 5, "find": "s"}, {"s": "45", "v": "14"}),
        ({"u": 20, "v": 0, "s": 50, "find": "a"}, {"a": "-4", "t": "5"}),
        ({"s": 120, "t": 8, "v": 20, "find": "u"}, {"u": "10", "a": "1.25"}),
        ({"u": 2, "a": 1.5, "s": 30, "find": "v"}, {"v": "9.70", "t": "5.13"}),
    ],
)
def test_suvat_solver(raw, found):
    result = values("SuvatSolver", raw)
    assert {k: result[k] for k in found} == found


def test_momentum_is_conserved():
    assert values("MomentumCollision", {"m1": 3, "m2": 2, "u1": 6, "u2": -4, "v2": 5}) == {
        "v1": "0"
    }
    stuck = {"m1": 0.5, "m2": 1.5, "u1": 8, "u2": 0, "coalesce": True}
    assert values("MomentumCollision", stuck) == {"v1": "2"}
    assert values("MomentumCollision", GRIDS["MomentumCollision"][3]) == {"m2": "3"}


@pytest.mark.parametrize(
    ("raw", "a", "tension"),
    [
        ({"setup": "table_pulley", "m_a": 4, "m_b": 2, "mu": 0.2}, "2", "16"),
        ({"setup": "two_hanging", "m_a": 3, "m_b": 5}, "2.5", "37.5"),
        ({"setup": "incline_pulley", "m_a": 2, "m_b": 3, "slope": 30, "mu": 0.25}, "3.13", "20.6"),
        (GRIDS["ConnectedParticles"][6], "1.5", "800"),
    ],
)
def test_connected_particles(raw, a, tension):
    found = values("ConnectedParticles", raw)
    assert (found["a"], found["T"]) == (a, tension)


def test_work_energy_and_power():
    expected = ["8.79", "9.39", "7.2", "75", "1", "15.6", "11500"]
    for raw, answer in zip(GRIDS["WorkEnergy"], expected, strict=True):
        assert values("WorkEnergy", raw)[raw["find"]] == answer


def test_box_plot_quartiles():
    odd = values("BoxPlot", GRIDS["BoxPlot"][0])
    assert (odd["q1_1"], odd["median_1"], odd["q3_1"], odd["iqr_1"]) == ("39/2", "27", "36", "33/2")
    pair = values("BoxPlot", GRIDS["BoxPlot"][1])
    assert (pair["median_1"], pair["median_2"], pair["iqr_2"]) == ("91/2", "37", "19")
    decimals = {"data": [1.5, 2, 3, 4, 5], "stem_leaf": True}
    assert predicates("BoxPlot", decimals) == ["whole_numbers"]


@pytest.mark.parametrize(
    ("raw", "mean", "sd"),
    [
        ({"kind": "list", "data": [4, 7, 7, 8, 10, 12]}, "8", "2.52"),
        (GRIDS["StandardDeviation"][1], "1.8", "1.14"),
        ({"kind": "totals", "n": 20, "sum_x": 360, "sum_x2": 6880}, "18", "4.47"),
        ({"kind": "coded", "n": 12, "sum_x": 30, "sum_x2": 210, "a": 50}, "52.5", "3.35"),
    ],
)
def test_standard_deviation(raw, mean, sd):
    found = values("StandardDeviation", raw)
    assert (found["mean"], found["standard_deviation"]) == (mean, sd)


@pytest.mark.parametrize(
    ("raw", "count"),
    [
        ({"kind": "word", "word": "NEEDLESS"}, "3360"),
        ({"kind": "word", "word": "STATISTICS"}, "50400"),
        ({"kind": "together", "n": 7, "k": 3}, "720"),
        ({"kind": "apart", "n": 6}, "480"),
        (GRIDS["ArrangementCounter"][4], "200"),
    ],
)
def test_arrangement_counter(raw, count):
    assert values("ArrangementCounter", raw)["count"] == count


@pytest.mark.parametrize(
    ("raw", "probability"),
    [
        ({"kind": "binomial", "n": 8, "p": "0.3", "high": 2}, "0.5518"),
        ({"kind": "binomial", "n": 12, "p": "1/4", "low": 3, "high": 5}, "0.5549"),
        ({"kind": "geometric", "p": "0.2", "low": 4}, "64/125"),
        ({"kind": "poisson", "lam": 4, "low": 6}, "0.2149"),
        (GRIDS["DiscreteDistribution"][2], "9/10"),
    ],
)
def test_discrete_distribution(raw, probability):
    assert values("DiscreteDistribution", raw)["probability"] == probability


@pytest.mark.parametrize(
    ("raw", "found"),
    [
        (
            {"kind": "probability", "mu": 50, "sigma": 8, "low": 45, "high": 60},
            {"answer": "0.6284"},
        ),
        ({"kind": "inverse", "mu": 120, "sigma": 15, "probability": 0.9}, {"answer": "139.2"}),
        (GRIDS["NormalDistribution"][7], {"mu": "29.83", "sigma": "7.668"}),
        (GRIDS["NormalDistribution"][8], {"answer": "0.7699"}),  # P(24.5 < X < 35.5)
        (GRIDS["NormalDistribution"][10], {"answer": "0.1841"}),
    ],
)
def test_normal_distribution(raw, found):
    result = values("NormalDistribution", raw)
    assert {k: result[k] for k in found} == found


def test_normal_distribution_predicates():
    small = {"kind": "approximation", "source": "binomial", "n": 10, "p": 0.3, "high": 4}
    assert predicates("NormalDistribution", small) == ["approximation_valid"]
    crossed = {
        "kind": "find_parameters",
        "conditions": [{"x": 20, "below": 0.8}, {"x": 30, "below": 0.2}],
    }
    assert predicates("NormalDistribution", crossed) == ["conditions_consistent"]


# A Level (9709): Probability & Statistics 2, and the A Level extensions


@pytest.mark.parametrize(
    ("index", "mean", "variance", "probability"),
    [
        (0, "5", "25", "0.8413"),  # P(X > Y) = P(X - Y > 0) = Φ(1)
        (1, "45", "40", None),  # 3X - 2Y + 5: the constant adds no variance
        (2, "260", "100", "0.1587"),  # four copies: 4 Var(W), not 16 Var(W)
        (4, "5.5", "5.5", "0.3575"),  # X + Y ~ Po(5.5)
    ],
)
def test_linear_combination(index, mean, variance, probability):
    found = values("LinearCombination", GRIDS["LinearCombination"][index])
    assert (found["mean"], found["variance"]) == (mean, variance)
    assert found.get("probability") == probability


def test_linear_combination_predicates():
    scaled = {
        "terms": [{"name": "X", "mean": 3, "variance": 3, "coefficient": 2}],
        "distribution": "poisson",
        "high": 4,
    }
    assert predicates("LinearCombination", scaled) == ["poisson_sum"]
    unknown = {"terms": [{"name": "X", "mean": 3, "variance": 2}], "distribution": "any", "low": 1}
    assert predicates("LinearCombination", unknown) == ["distribution_known"]


def test_continuous_pdf():
    found = values("ContinuousPDF", GRIDS["ContinuousPDF"][0])
    assert (found["k"], found["probability"], found["mean"], found["variance"]) == (
        "3/32",
        "11/16",
        "2",
        "4/5",
    )
    assert values("ContinuousPDF", GRIDS["ContinuousPDF"][1])["median"] == "2.828"  # √8
    infinite = values("ContinuousPDF", GRIDS["ContinuousPDF"][2])
    assert (infinite["k"], infinite["mean"], infinite["variance"]) == ("4", "4/3", "2/9")


def test_continuous_pdf_predicates():
    assert predicates("ContinuousPDF", {"pdf": "x", "lower": "0", "upper": "1"}) == ["area_one"]
    heavy = {"pdf": "k/x**2", "lower": "1", "upper": "inf"}
    assert predicates("ContinuousPDF", heavy) == ["moments_finite"]
    negative = {"pdf": "k*(x - 1)", "lower": "0", "upper": "3"}
    assert predicates("ContinuousPDF", negative)


@pytest.mark.parametrize(
    ("index", "found"),
    [
        (0, {"mean": "31", "variance": "32.31"}),
        (1, {"mean": "61.4", "variance": "6.792"}),  # coded with a = 60
        (2, {"standard_error": "2", "probability": "0.1587"}),
        (4, {"lower": "23.14", "upper": "25.46"}),
        (6, {"lower": "0.1717", "upper": "0.2883"}),
    ],
)
def test_sampling_estimation(index, found):
    result = values("SamplingEstimation", GRIDS["SamplingEstimation"][index])
    assert {k: result[k] for k in found} == found


@pytest.mark.parametrize(
    ("index", "found"),
    [
        (0, {"p_value": "0.03548", "decision": "reject", "critical_region": "X <= 2"}),
        (1, {"critical_region": "X <= 5 or X >= 15", "type_1": "0.04139"}),
        (2, {"critical_region": "X >= 6", "type_2": "0.4032"}),
        (4, {"decision": "accept", "critical_region": "X <= 5", "type_2": "0.6993"}),
        (5, {"z": "1.897", "decision": "reject"}),
        (7, {"decision": "accept", "type_2": "0.1962"}),
    ],
)
def test_hypothesis_test(index, found):
    result = values("HypothesisTest", GRIDS["HypothesisTest"][index])
    assert {k: result[k] for k in found} == found


def test_hypothesis_test_predicates():
    wrong_side = {
        "kind": "binomial",
        "null_value": 0.3,
        "tail": "lower",
        "observed": 2,
        "n": 20,
        "alternative": 0.5,
    }
    assert predicates("HypothesisTest", wrong_side) == ["alternative_side"]
    tiny = {"kind": "binomial", "null_value": 0.5, "tail": "lower", "observed": 0, "n": 3}
    assert predicates("HypothesisTest", tiny) == ["critical_region_exists"]


@pytest.mark.parametrize(
    ("raw", "solution"),
    [
        ({"a": 1, "b": -2, "c": -3, "inequality": "<"}, "-1 < x < 3"),
        ({"a": 3, "b": -7, "c": 2, "inequality": ">="}, "x <= 1/3 or x >= 2"),
        ({"a": 1, "b": -4, "c": 4, "inequality": ">"}, "x != 2"),
        ({"a": 1, "b": -4, "c": 4, "inequality": "<="}, "x = 2"),
        ({"a": 0.5, "b": 1, "c": 3, "inequality": "<"}, "no real x"),
        ({"a": 0.5, "b": 1, "c": 3, "inequality": ">"}, "all real x"),
    ],
)
def test_quadratic_inequality(raw, solution):
    assert values("QuadraticExplorer", raw)["solution"] == solution


def test_tree_diagram_conditional():
    same = {
        "outcomes": ["R", "B"],
        "counts": [3, 2],
        "replace": False,
        "find": ["R,R"],
        "given": ["R,R", "B,B"],
    }
    found = values("TreeDiagram", same)
    assert (found["joint"], found["given"], found["probability"]) == ("3/10", "2/5", "3/4")
    impossible = {
        "outcomes": ["R", "B"],
        "counts": [1, 2],
        "replace": False,
        "find": ["B,B"],
        "given": ["R,R"],
    }
    assert predicates("TreeDiagram", impossible) == ["condition_possible"]
