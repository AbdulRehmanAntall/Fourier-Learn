"""Offline validation of the primitive library (report §5.3.2).

Before a primitive enters the library it is rendered across a grid of parameter values spanning
its permitted ranges, at every level. Every render is checked for execution errors and layout
violations by the render engine, and the last frame of each is saved so a sample can be reviewed
by hand against the mathematics it is meant to show. Run it again whenever a primitive changes.

    python -m app.primitives.harness                      every primitive
    python -m app.primitives.harness GradientTriangle     one primitive
    npm run primitives:check -- GradientTriangle          the same, from the repo root

Writes media/harness/<primitive>/review.md. Exits with 1 if any case fails.
"""

import argparse
import subprocess
import sys
from pathlib import Path

from app.audio_pipeline.tts import FakeTTS
from app.contracts import Level, ModuleRenderRequest
from app.core.config import get_settings
from app.primitives.library import LIBRARY_VERSION, PRIMITIVES, get_primitive
from app.renderer.beat import QUALITIES
from app.renderer.engine import render_module
from app.renderer.errors import RenderError

# Parameter sets spanning each primitive's permitted ranges: small and large values, negative
# values, fractions, and shapes that crowd the frame. Add a case whenever a bug is found.
GRIDS: dict[str, list[dict]] = {  # fmt: skip
    "FunctionGraph": [
        {"expression": "x**2", "x_min": -3, "x_max": 3, "marked_x": [2]},
        {"expression": "x**3 - 3*x", "x_min": -2.5, "x_max": 2.5, "marked_x": [-1, 1]},
        {"expression": "sin(x)", "x_min": -6, "x_max": 6},
        {"expression": "1/x", "x_min": 0.5, "x_max": 8, "marked_x": [1, 4]},
        {"expression": "-0.5*x + 4", "x_min": -10, "x_max": 10, "marked_x": [-6, 6]},
        {"expression": "x**2 - 20", "x_min": -20, "x_max": 20, "marked_x": [0]},
    ],
    "GradientTriangle": [
        {"point_a": [1, 2], "point_b": [4, 8]},
        {"point_a": [-3, 4], "point_b": [5, -2]},
        {"point_a": [0, 0], "point_b": [2, 7]},
        {"point_a": [-15, -10], "point_b": [15, 12]},
        {"point_a": [0.5, 0.5], "point_b": [1.5, 3]},
        {"point_a": [2, 9], "point_b": [3, 1]},
    ],
    "TangentSlide": [
        {"expression": "x**2", "x_min": -3, "x_max": 3, "x_start": -2, "x_end": 2},
        {"expression": "x**3 - 3*x", "x_min": -2.5, "x_max": 2.5, "x_start": -2, "x_end": 2},
        {"expression": "sin(x)", "x_min": -6, "x_max": 6, "x_start": -5, "x_end": 5},
        {"expression": "1/x", "x_min": 0.5, "x_max": 8, "x_start": 1, "x_end": 6},
        {"expression": "0.5*x**2 - 2*x + 1", "x_min": -2, "x_max": 6, "x_start": 5, "x_end": -1},
        {"expression": "sqrt(x)", "x_min": 0, "x_max": 9, "x_start": 1, "x_end": 8},
    ],
    "SecantToTangent": [
        {"expression": "x**2", "x_min": -1, "x_max": 4, "x0": 1, "h_values": [2, 1, 0.5, 0.1]},
        {"expression": "x**3", "x_min": -2, "x_max": 3, "x0": 1, "h_values": [1.5, 1, 0.5, 0.2]},
        {"expression": "sin(x)", "x_min": -1, "x_max": 4, "x0": 0.5, "h_values": [2, 1, 0.25]},
        {"expression": "1/x", "x_min": 0.2, "x_max": 5, "x0": 1, "h_values": [3, 1, 0.5, 0.1]},
        {"expression": "-x**2 + 4*x", "x_min": -1, "x_max": 5, "x0": 3, "h_values": [-2, -1, -0.5]},
        {
            "expression": "x**2/10 - 5",
            "x_min": -20,
            "x_max": 20,
            "x0": -10,
            "h_values": [15, 8, 2, 0.5],
        },
    ],
    "TravelGraph": [
        {
            "kind": "distance_time",
            "points": [[0, 0], [10, 6], [15, 6], [30, 0]],
            "time_unit": "min",
            "distance_unit": "km",
        },
        {"kind": "speed_time", "points": [[0, 0], [4, 8], [10, 8], [12, 0]], "show": "areas"},
        {"kind": "speed_time", "points": [[0, 0], [5, 10], [15, 10], [20, 0]]},
        {
            "kind": "distance_time",
            "points": [[0, 0], [1, 60], [1.5, 60], [3.5, 0]],
            "time_unit": "h",
            "distance_unit": "km",
        },
        {"kind": "speed_time", "points": [[0, 5], [10, 25], [30, 25], [40, 0]], "show": "areas"},
        {
            "kind": "distance_time",
            "points": [[0, 0], [5, 200], [10, 200], [15, 500], [20, 500], [30, 0]],
        },
    ],
    "AreaUnderCurve": [
        {"expression": "x**2", "x_min": -1, "x_max": 4, "lower": 1, "upper": 3},
        {"expression": "4 - x**2", "x_min": -3, "x_max": 3, "lower": -2, "upper": 2},
        {"expression": "sin(x)", "x_min": 0, "x_max": 4, "lower": 0, "upper": 3},
        {"expression": "x**2 - 4", "x_min": -3, "x_max": 3, "lower": -2, "upper": 2},
        {"expression": "1/x", "x_min": 0.5, "x_max": 6, "lower": 1, "upper": 5},
        {"expression": "0.5*x + 1", "x_min": -2, "x_max": 10, "lower": 0, "upper": 8},
    ],
    "EquationTransform": [
        {"expressions": ["(8 - 2)/(4 - 1)", "6/3", "2"]},
        {"expressions": ["2*x + 3 = 7", "2*x = 4", "x = 2"]},
        {"expressions": ["x**2 - 5*x + 6", "(x - 2)*(x - 3)"]},
        {"expressions": ["3*(x - 4) = 2*x + 1", "3*x - 12 = 2*x + 1", "x - 12 = 1", "x = 13"]},
        {"expressions": ["(3/4)*(8/9)", "24/36", "2/3"]},
        {"expressions": ["(x + 1)**2", "x**2 + 2*x + 1"]},
    ],
    "AlgebraBalance": [
        {"equation": "3*x + 5 = 20", "operations": ["-5", "/3"]},
        {"equation": "v = u + a*t", "operations": ["-u", "/a", "swap"]},
        {"equation": "x/4 - 3 = 2", "operations": ["+3", "*4"]},
        {"equation": "3*(x - 4) = 2*x + 1", "operations": ["expand", "-2*x", "+12"]},
        {"equation": "5 - 2*x = 11", "operations": ["-5", "/(-2)"]},
        {
            "equation": "7*x + 2 = 3*x - 10",
            "operations": ["-3*x", "-2", "/4"],
            "results": ["4*x + 2 = -10", "4*x = -12", "x = -3"],
        },
    ],
    "ExpansionGrid": [
        {"factors": ["x + 2", "x + 3"]},
        {"factors": ["2*x + 3", "x - 4"]},
        {"factors": ["x - 5", "x + 5"]},
        {"factors": ["3*x - 1", "2*x - 7"], "mode": "factorise"},
        {"factors": ["x + 2", "x**2 - 3*x + 1"]},
        {"factors": ["a + b", "a - b"], "mode": "factorise"},
    ],
    "CompletingSquare": [
        {"b": 6, "c": 5},
        {"b": 4, "c": 0},
        {"b": 10, "c": -3},
        {"b": 3, "c": 1},
        {"b": 1, "c": 2},
        {"b": 20, "c": 100},
    ],
    "QuadraticExplorer": [
        {"a": 1, "b": -2, "c": -3},
        {"a": 1, "b": -4, "c": 4},
        {"a": -2, "b": 4, "c": 1},
        {"a": 0.5, "b": 1, "c": 3},
        {"a": 1, "b": 0, "c": -2},
        {"a": 3, "b": -7, "c": 2},
        {"a": -1, "b": 10, "c": -16},
    ],
    "InequalityRegion": [
        {"inequalities": ["y <= 2*x + 1", "x + y < 6", "y >= 1"]},
        {"inequalities": ["x > -1", "y > x", "y < 4"], "show_integer_points": True},
        {"inequalities": ["2*x + 3*y <= 12", "x >= 0", "y >= 0"], "shade": "wanted"},
        {"inequalities": ["y < 3"]},
        {"inequalities": ["y >= x**1 - 2", "y <= -x + 4", "x >= -1", "y > -3"]},
        {"inequalities": ["x + 2*y < 8", "y > 0.5*x"], "x_range": [-2, 10], "y_range": [-2, 6]},
    ],
    "SequencePattern": [
        {"terms": [5, 8, 11, 14], "show_pattern": True},
        {"terms": [2, 6, 12, 20, 30]},
        {"terms": [3, 6, 12, 24, 48]},
        {"terms": [1, 8, 27, 64, 125]},
        {"terms": [20, 17, 14, 11, 8]},
        {"terms": [1, 3, 6, 10, 15], "show_pattern": True},
        {"terms": [64, 32, 16, 8]},
    ],
    "ProportionGraph": [
        {"kind": "direct", "power": "2", "known": [2, 12], "find_x": 5},
        {"kind": "inverse", "power": "1", "known": [4, 5], "find_x": 10},
        {"kind": "inverse", "power": "2", "known": [2, 9], "find_y": 4},
        {"kind": "direct", "power": "1/2", "known": [9, 6]},
        {"kind": "direct", "power": "1", "known": [3, 7.5], "find_y": 20},
        {"kind": "direct", "power": "3", "known": [2, 40], "find_x": 0.5},
    ],
    "CurveSketch": [
        {"expression": "x**3 - 3*x", "x_min": -2.5, "x_max": 2.5},
        {"expression": "1/(x - 2) + 1", "x_min": -3, "x_max": 7},
        {"expression": "2**x - 3", "x_min": -3, "x_max": 3},
        {"expression": "x**2*(x - 3)", "x_min": -1.5, "x_max": 4},
        {"expression": "4/x**2", "x_min": -4, "x_max": 4},
        {"expression": "sin(x)", "x_min": -6, "x_max": 6},
        {"expression": "-x**2 + 4*x + 5", "x_min": -2, "x_max": 6},
    ],
    "FunctionMachine": [
        {"operations": ["*2", "+3"], "inputs": [4, -1], "show_inverse": True},
        {"operations": ["+3", "*2", "**3"], "inputs": [1], "name": "g", "show_inverse": True},
        {"operations": ["**2", "-5"], "inputs": [3, -2, 0.5]},
        {"operations": ["/4", "+1", "sqrt", "*-3"], "inputs": [12], "show_inverse": True},
        {"operations": ["-7"], "inputs": [10], "show_inverse": True},
        {"operations": ["*0.5", "-1.5"], "name": "h"},
    ],
    "GraphicalSolution": [
        {"curve": "x**2 - 2*x - 1", "line": "x + 1", "x_min": -2, "x_max": 5},
        {"curve": "x**3 - 4*x", "line": "1", "x_min": -2.5, "x_max": 2.5},
        {"curve": "2**x", "line": "3 - x", "x_min": -2, "x_max": 4},
        {"curve": "6/x", "line": "x + 1", "x_min": 0.5, "x_max": 6},
        {"curve": "x**2", "line": "2*x + 3", "x_min": -3, "x_max": 5},
        {"curve": "sin(x)", "line": "0.5", "x_min": 0, "x_max": 6},
    ],
    "CoordinatePlotter": [
        {"point_a": [1, 2], "point_b": [4, 8]},
        {"point_a": [-3, 4], "point_b": [5, -2]},
        {"point_a": [0, 0], "point_b": [6, 0]},
        {"point_a": [-2, -1], "point_b": [-2, 5], "show": ["midpoint"]},
        {"point_a": [0.5, 1.5], "point_b": [3, 4], "show": ["length"]},
        {"point_a": [-12, 7], "point_b": [10, -9]},
    ],
    "LineBuilder": [
        {"gradient": 2, "intercept": -1, "general_form": True},
        {"gradient": -0.5, "intercept": 3, "general_form": True},
        {"gradient": 0, "intercept": 2},
        {"gradient": 3, "intercept": 0},
        {"gradient": 0.75, "intercept": -2, "general_form": True},
        {"gradient": -4, "intercept": 10},
    ],
    "ParallelPerpendicular": [
        {"mode": "perpendicular", "gradient": 2, "intercept": 1, "point": [4, 1]},
        {"mode": "parallel", "gradient": -0.5, "intercept": 3, "point": [2, -2]},
        {"mode": "bisector", "point_a": [-2, 1], "point_b": [4, 5]},
        {"mode": "perpendicular", "gradient": 0, "intercept": 2, "point": [3, -1]},
        {"mode": "bisector", "point_a": [1, -3], "point_b": [1, 5]},
        {"mode": "parallel", "gradient": 3, "intercept": -4, "point": [-1, 2]},
    ],
    "CoordinateCircle": [
        {"centre": [2, 1], "radius": 5, "line_gradient": 1, "line_intercept": 4},
        {"centre": [0, 0], "radius": 5, "line_gradient": 0.75, "line_intercept": 6.25},
        {"centre": [-1, 2], "radius": 2},
        {"centre": [0, 0], "radius": 1, "line_gradient": 1, "line_intercept": 5},
        {"centre": [3, -2], "radius": 4, "line_gradient": 0, "line_intercept": 0},
        {"centre": [-6, 5], "radius": 7.5},
    ],
    "DerivativePanels": [
        {"expression": "x**3 - 3*x", "x_min": -2.5, "x_max": 2.5},
        {"expression": "x**2 - 4*x + 1", "x_min": -1, "x_max": 5},
        {"expression": "sin(x)", "x_min": -4, "x_max": 4},
        {"expression": "-x**3 + 3*x**2", "x_min": -1, "x_max": 3.5},
        {"expression": "2*x + 1", "x_min": -3, "x_max": 3},
        {"expression": "x**4 - 2*x**2", "x_min": -1.8, "x_max": 1.8},
    ],
    "DifferentiationStepper": [
        {"rule": "power", "expression": "3*x**4 - 2/x + 4*sqrt(x) - 7", "at_x": 1},
        {"rule": "chain", "inner": "3*x + 1", "outer": "u**5"},
        {"rule": "chain", "inner": "x**2 + 1", "outer": "sqrt(u)", "at_x": 2},
        {"rule": "product", "u": "x**2", "v": "(x + 1)**3"},
        {"rule": "quotient", "u": "2*x + 1", "v": "x - 3", "at_x": 4},
        {"rule": "power", "expression": "x**3 - 6*x**2 + 9*x"},
        {"rule": "product", "u": "x", "v": "sin(x)"},
    ],
    "TangentNormal": [
        {"expression": "x**2 - 2*x", "x_min": -1, "x_max": 4, "x0": 2.5},
        {"expression": "x**3 - 3*x", "x_min": -2, "x_max": 2, "x0": 1},
        {"expression": "4/x", "x_min": 0.5, "x_max": 6, "x0": 2},
        {"expression": "sqrt(x)", "x_min": 0, "x_max": 9, "x0": 4},
        {"expression": "x**2", "x_min": -3, "x_max": 3, "x0": -1},
        {"expression": "0.5*x**3 - x", "x_min": -2, "x_max": 2.5, "x0": 2},
    ],
    "AreaBetweenCurves": [
        {"upper": "4 - x**2", "lower": "x + 2"},
        {"upper": "sqrt(x)", "lower": "x**2"},
        {"upper": "x**2 + 2", "lower": "x", "lower_limit": 0, "upper_limit": 2},
        {"upper": "2*x + 3", "lower": "x**2"},
        {"upper": "6 - x", "lower": "x**2 - 2*x"},
        {"upper": "sin(x) + 2", "lower": "1", "lower_limit": 0, "upper_limit": 3},
    ],
    "KinematicsGraphs": [
        {"expression": "t**3 - 6*t**2 + 9*t", "t_max": 4},
        {"given": "velocity", "expression": "12 - 3*t**2", "s0": 2, "t_max": 3},
        {"expression": "5*t - t**2", "t_max": 6},
        {"given": "velocity", "expression": "t**2 - 4*t + 3", "t_max": 4},
        {"expression": "2*t**2 + 3*t", "t_max": 5},
        {"given": "velocity", "expression": "10", "s0": 0, "t_max": 8},
    ],
    "OptimisationScene": [
        {"scenario": "open_box", "size": 12},
        {"scenario": "fence_wall", "size": 40},
        {"scenario": "rectangle", "size": 20},
        {"scenario": "cylinder", "size": 500},
        {"scenario": "open_box", "size": 30},
        {"scenario": "fence_wall", "size": 7.5},
    ],
    "GrowthDecay": [
        {"initial": 1000, "rate": 5, "periods": 10, "compare_simple": True},
        {"initial": 15000, "rate": -20, "periods": 6},
        {"initial": 2400, "rate": 3, "periods": 20, "unit": "people"},
        {"initial": 500, "rate": 12.5, "periods": 8, "compare_simple": True},
        {"initial": 80, "rate": -5, "periods": 15, "unit": "kg"},
        {"initial": 250000, "rate": 2.5, "periods": 4},
    ],
    "UnitCircleWaves": [
        {"function": "sin", "a": 2, "b": 2, "c": 1},
        {"function": "cos"},
        {"function": "sin", "a": -3, "b": 0.5, "c": 0},
        {"function": "sin"},
        {"function": "cos", "a": 1.5, "b": 3, "c": -1},
        {"function": "cos", "a": 4, "b": 1, "c": 2},
    ],
    "ConnectedRates": [
        {"shape": "circle", "rate": 2, "at": 5},
        {"shape": "sphere", "known": "quantity", "rate": 100, "at": 3},
        {"shape": "cube", "rate": 0.5, "at": 4},
        {"shape": "square", "known": "quantity", "rate": 12, "at": 3},
        {"shape": "sphere", "rate": 0.2, "at": 10},
        {"shape": "circle", "known": "quantity", "rate": 50, "at": 2.5},
    ],
    "InverseGraph": [
        {"expression": "2*x + 1", "x_min": -3, "x_max": 2, "point_x": 1},
        {"expression": "x**2", "x_min": 0, "x_max": 2.5, "point_x": 2},
        {"expression": "2**x", "x_min": -2, "x_max": 2.5},
        {"expression": "(x + 3)/2", "x_min": -3, "x_max": 5, "point_x": 1},
        {"expression": "1/(x - 1)", "x_min": 1.5, "x_max": 5},
        {"expression": "x**3", "x_min": -1.5, "x_max": 1.5, "point_x": 1.4},
    ],
    "SimultaneousEquations": [
        {"equation_1": "3*x + 2*y = 16", "equation_2": "x - 2*y = 0"},
        {"equation_1": "2*x + 3*y = 13", "equation_2": "5*x - 2*y = 4"},
        {"equation_1": "y = x**2 - 3", "equation_2": "y = 2*x", "method": "substitution"},
        {"equation_1": "x + y = 5", "equation_2": "x**2 + y**2 = 13", "method": "substitution"},
        {"equation_1": "4*x - 3*y = 1", "equation_2": "4*x + y = 9"},
        {"equation_1": "y = 3*x - 1", "equation_2": "2*x + y = 9", "method": "substitution"},
    ],
    "TableOfValues": [
        {"expression": "x**2 - 2*x - 3", "x_min": -2, "x_max": 4},
        {"expression": "12/x", "x_min": 1, "x_max": 6},
        {"expression": "x**3 - 4*x", "x_min": -2.5, "x_max": 2.5, "step": 0.5},
        {"expression": "2**x", "x_min": -2, "x_max": 3},
        {"expression": "5 - x**2", "x_min": -3, "x_max": 3},
        {"expression": "x + 4/x", "x_min": 0.5, "x_max": 5, "step": 0.5},
    ],
    "NumberLine": [
        {"numbers": ["3/4", "-1.5", "sqrt(2)"], "inequality": "-2 < x <= 3"},
        {"numbers": ["0.3", "1/3", "0.33", "pi/10"]},
        {"inequality": "x >= -1"},
        {"inequality": "-3 <= x < 2", "integers_only": True},
        {"numbers": ["-4", "2.5", "-0.5", "7/2", "-sqrt(5)"]},
        {"numbers": ["150", "155"], "inequality": "145 <= x < 165"},
    ],
    "PrimeFactorTree": [
        {"number": 360, "other": 84},
        {"number": 1024},
        {"number": 2310, "other": 1050},
        {"number": 90},
        {"number": 72, "other": 120},
        {"number": 9999},
    ],
    "VennDiagram": [
        {
            "sets": [["1", "2", "3", "4", "6", "12"], ["2", "4", "6", "8", "10"]],
            "universal": ["5", "7", "9", "11"],
            "shade": "A ∩ B",
        },
        {"counts": {"A": 12, "AB": 5, "B": 8, "": 3}, "shade": "A ∪ B'"},
        {
            "counts": {"A": 4, "B": 3, "C": 6, "AB": 2, "AC": 1, "BC": 5, "ABC": 7, "": 2},
            "set_count": 3,
            "shade": "(A ∩ B) ∪ C'",
        },
        {
            "sets": [["a", "e", "i"], ["a", "b", "c"], ["c", "e", "f"]],
            "universal": ["g", "h"],
            "shade": "A'",
        },
        {"sets": [["2", "4", "6", "8"], ["3", "6", "9"]], "universal": ["1", "5", "7"]},
        {"counts": {"A": 9, "AB": 0, "B": 6, "": 5}, "shade": "A ∩ B'"},
    ],
    "FractionModel": [
        {"operation": "add", "first": "1/2", "second": "1/3"},
        {"operation": "add", "first": "3/4", "second": "2/3"},
        {"operation": "multiply", "first": "2/3", "second": "3/4"},
        {"operation": "divide", "first": "3/4", "second": "1/8"},
        {"operation": "equivalent", "first": "2/3", "factor": 3},
        {"operation": "subtract", "first": "5/6", "second": "1/4"},
        {"operation": "divide", "first": "2/1", "second": "3/4"},
    ],
}


def check_primitive(primitive_id: str, media_dir: Path, quality: str) -> bool:
    primitive = get_primitive(primitive_id)
    out_dir = media_dir / "harness" / primitive_id
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, ok = [], True
    for case, raw in enumerate(GRIDS[primitive_id], start=1):
        params = primitive.parse_params(raw)
        failures = primitive.validate(params)
        for level in Level:
            outcome, video, frame = "ok", "", ""
            if failures:
                outcome = "rejected: " + "; ".join(f.predicate for f in failures)
            else:
                request = ModuleRenderRequest(
                    module_id=1,
                    level=level,
                    voice="default",
                    library_version=LIBRARY_VERSION,
                    # Narration that matches the steps, so the timing follows the step minimums.
                    beats=[
                        {
                            "primitive_id": primitive_id,
                            "params": raw,
                            "narration": [s.description for s in primitive.steps(params, level)],
                        }
                    ],
                )
                try:
                    result = render_module(
                        request,
                        media_dir=media_dir / "harness" / "renders",
                        tts=FakeTTS(),
                        library_version=LIBRARY_VERSION,
                        quality=quality,
                        workers=1,
                        force=True,  # always test the code as it is now, never a cached render
                    )
                    video_path = result.directory / result.manifest.beats[0].video
                    frame_path = out_dir / f"case{case}_L{int(level)}.png"
                    _last_frame(video_path, frame_path)
                    video, frame = str(video_path), frame_path.name
                except RenderError as error:
                    outcome = f"FAILED: {error}"
            ok = ok and outcome == "ok"
            rows.append((case, level.label, raw, outcome, video, frame))
            print(f"{primitive_id} case {case} {level.label}: {outcome}")

    lines = [
        f"# {primitive_id} validation",
        "",
        f"Library {LIBRARY_VERSION}, primitive version {primitive.version}, {quality}.",
        "Review a sample of frames against the mathematics each case should show (§5.3.2).",
        "",
        "| Case | Level | Parameters | Outcome | Last frame |",
        "| ---- | ----- | ---------- | ------- | ---------- |",
    ]
    for case, level, raw, outcome, _video, frame in rows:
        image = f"![]({frame})" if frame else ""
        lines.append(f"| {case} | {level} | `{raw}` | {outcome} | {image} |")
    (out_dir / "review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Review sheet: {out_dir / 'review.md'}")
    return ok


def _last_frame(video: Path, out: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-sseof", "-0.1", "-i", str(video)]
        + ["-frames:v", "1", str(out)],
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.primitives.harness", description=__doc__)
    parser.add_argument("primitives", nargs="*", choices=[[], *sorted(PRIMITIVES)], default=[])
    parser.add_argument("--quality", default="480p30", choices=sorted(QUALITIES))
    args = parser.parse_args(argv)
    media_dir = get_settings().media_dir
    results = [
        check_primitive(pid, media_dir, args.quality) for pid in args.primitives or PRIMITIVES
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
