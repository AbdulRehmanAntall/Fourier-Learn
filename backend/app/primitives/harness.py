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
    "PercentageBar": [
        {"kind": "increase", "amount": 80, "percent": 15},
        {"kind": "of", "amount": 240, "percent": 35},
        {"kind": "decrease", "amount": 1250, "percent": 12.5},
        {"kind": "reverse_increase", "amount": 69, "percent": 15},
        {"kind": "reverse_decrease", "amount": 340, "percent": 15},
        {"kind": "change", "amount": 40, "new_amount": 52},
        {"kind": "change", "amount": 250, "new_amount": 180, "money": False},
    ],
    "StandardForm": [
        {"number": "34500000"},
        {"number": "0.000345"},
        {"number": "7"},
        {"number": "60200"},
        {"number": "4500", "operation": "multiply", "other": "0.0003"},
        {"number": "0.0072", "operation": "divide", "other": "900000"},
    ],
    "IndexLaws": [
        {
            "lines": ["(2*x**3)**2 / (4*x**2)", "4*x**6 / (4*x**2)", "x**(6 - 2)", "x**4"],
            "laws": ["product", "divide", "evaluate"],
        },
        {"lines": ["x**3 * x**4", "x**(3 + 4)", "x**7"], "laws": ["multiply", "evaluate"]},
        {"lines": ["(a**2)**5", "a**(2*5)", "a**10"], "laws": ["power", "evaluate"]},
        {
            "lines": ["5**0 + 2**(-3)", "1 + 2**(-3)", "1 + 1/2**3", "9/8"],
            "laws": ["zero", "negative", "evaluate"],
        },
        {
            "lines": ["27**(2/3)", "(27**(1/3))**2", "3**2", "9"],
            "laws": ["power", "fractional", "evaluate"],
        },
        {
            "lines": ["(16*y**8)**(1/2)", "16**(1/2) * (y**8)**(1/2)", "4*y**4"],
            "laws": ["product", "power"],
        },
    ],
    "SurdSimplifier": [
        {"kind": "simplify", "number": 72},
        {"kind": "simplify", "number": 1800},
        {"kind": "combine", "expression": "2*sqrt(12) + sqrt(27) - sqrt(3)"},
        {"kind": "combine", "expression": "sqrt(50) - sqrt(8) + sqrt(7)"},
        {"kind": "rationalise", "numerator": "6", "denominator": "2*sqrt(3)"},
        {"kind": "rationalise", "numerator": "6", "denominator": "3 - sqrt(5)"},
        {"kind": "rationalise", "numerator": "1 + sqrt(2)", "denominator": "sqrt(2) - 1"},
    ],
    "RatioSplitter": [
        {"ratio": [2, 3], "names": ["Ali", "Sara"], "kind": "share", "amount": 40},
        {"ratio": [3, 5, 4], "kind": "share", "amount": 300, "money": True},
        {"ratio": [4, 7], "names": ["Boys", "Girls"], "kind": "part", "amount": 28, "known": 0},
        {"ratio": [2, 5], "names": ["Tom", "Jo"], "kind": "difference", "amount": 45},
        {"ratio": [12, 18], "kind": "simplify"},
        {"ratio": [5, 7], "names": ["Mina", "Raza"], "kind": "share", "amount": 50, "money": True},
    ],
    "BoundsInterval": [
        {"value": "7.4", "nearest": "0.1"},
        {"value": "340", "sf": 2},
        {"value": "60", "nearest": "5", "letter": "m"},
        {
            "value": "12.5",
            "nearest": "0.5",
            "operation": "multiply",
            "other": "4.2",
            "other_nearest": "0.1",
            "letter": "l",
            "other_letter": "w",
        },
        {
            "value": "9.6",
            "nearest": "0.1",
            "operation": "divide",
            "other": "2.3",
            "other_nearest": "0.1",
            "letter": "d",
            "other_letter": "t",
        },
        {
            "value": "250",
            "nearest": "10",
            "operation": "subtract",
            "other": "80",
            "other_nearest": "5",
        },
    ],
    "ClockTimetable": [
        {"kind": "interval", "start": "09:35", "end": "14:20"},
        {"kind": "interval", "start": "22:45", "end": "01:10"},
        {"kind": "convert", "start": "15:40"},
        {"kind": "convert", "start": "00:25"},
        {
            "kind": "timetable",
            "stops": ["Lahore", "Gujranwala", "Jhelum", "Rawalpindi"],
            "times": [
                ["07:15", "09:40"],
                ["08:05", "10:30"],
                ["09:20", "11:45"],
                ["10:35", "13:05"],
            ],
            "service": 1,
            "board": 0,
            "leave": 3,
        },
        {
            "kind": "exchange",
            "amount": 250,
            "rate": 278.5,
            "from_currency": "USD",
            "to_currency": "PKR",
        },
    ],
    "AngleChaser": [
        {"layout": "line", "angles": ["2*x", "x + 30", "60"]},
        {"layout": "point", "angles": ["110", "3*x", "2*x + 50"]},
        {"layout": "triangle", "angles": ["x", "x", "40"], "isosceles": True},
        {"layout": "triangle", "angles": ["65", "x", "130"], "exterior": True},
        {"layout": "parallel", "given": 70, "given_at": "upper_tr", "find_at": "lower_bl"},
        {"layout": "parallel", "given": 70, "given_at": "upper_bl", "find_at": "lower_tl"},
        {"layout": "parallel", "given": 115, "given_at": "upper_br", "find_at": "lower_tl"},
        {"layout": "crossing", "given": 50, "given_at": "upper_tr", "find_at": "upper_tl"},
    ],
    "PolygonAngles": [
        {"kind": "interior_sum", "sides": 6},
        {"kind": "interior_sum", "sides": 5, "regular": False},
        {"kind": "interior_sum", "sides": 8},
        {"kind": "exterior", "sides": 5},
        {"kind": "exterior", "sides": 9},
        {"kind": "find_sides", "angle": 24, "given": "exterior"},
        {"kind": "find_sides", "angle": 140, "given": "interior"},
    ],
    "CircleTheorems": [
        {"theorem": "semicircle", "given": 35},
        {"theorem": "centre", "given": 40},
        {"theorem": "centre", "given": 130, "given_at": "centre"},
        {"theorem": "same_segment", "given": 48},
        {"theorem": "cyclic_quadrilateral", "given": 75},
        {"theorem": "tangent_radius", "given": 32},
        {"theorem": "two_tangents", "given": 70},
        {"theorem": "alternate_segment", "given": 55},
    ],
    "RightTriangleTrig": [
        {"angle": 35, "hypotenuse": 12, "find": "opposite"},
        {"angle": 50, "opposite": 8, "find": "hypotenuse"},
        {"angle": 28, "adjacent": 15, "find": "opposite", "unit": "m"},
        {"opposite": 5, "adjacent": 12, "find": "angle"},
        {"opposite": 7, "hypotenuse": 10, "find": "angle"},
        {"opposite": 6, "adjacent": 9, "find": "hypotenuse"},
        {"hypotenuse": 13, "adjacent": 5, "find": "opposite"},
    ],
    "SineCosineRule": [
        {"b": 7, "c": 9, "A": 48, "find": "a"},
        {"a": 7, "b": 8, "c": 10, "find": "C"},
        {"a": 12, "A": 40, "B": 65, "find": "b"},
        {"a": 12, "A": 40, "B": 65, "find": "c"},
        {"a": 9, "b": 7, "A": 70, "find": "B"},
        {"a": 6, "b": 8, "C": 110, "find": "area", "unit": "m"},
    ],
    "CircleSector": [
        {"radius": 6, "angle": 120, "find": "arc"},
        {"radius": 10, "angle": 72, "find": "area"},
        {"radius": 8, "angle": 90, "find": "perimeter"},
        {"radius": 6, "angle": 60, "find": "segment"},
        {"radius": 4, "arc": 6, "find": "angle"},
        {"radius": 5, "angle": 1.2, "radians": True, "find": "area"},
        {"radius": 7, "angle": 2, "radians": True, "find": "segment", "unit": "m"},
    ],
    "SolidMensuration": [
        {"solid": "cuboid", "length": 8, "width": 5, "height": 3, "find": "surface_area"},
        {"solid": "prism", "length": 10, "width": 6, "height": 8, "find": "volume"},
        {"solid": "cylinder", "radius": 3, "height": 10, "find": "volume"},
        {"solid": "cone", "radius": 5, "height": 12, "find": "surface_area"},
        {"solid": "pyramid", "width": 6, "height": 4, "find": "surface_area"},
        {"solid": "sphere", "radius": 6, "find": "volume"},
        {"solid": "hemisphere", "radius": 4, "find": "surface_area", "unit": "m"},
    ],
    "Bearings": [
        {"bearing": 65},
        {"bearing": 230},
        {"bearing": 140},
        {"bearing": 300},
        {"bearing": 320, "distance": 12, "find": "components"},
        {"bearing": 125, "distance": 8, "find": "components", "unit": "m"},
    ],
    "SimilarityScaler": [
        {"sides": [4, 5, 6], "known_value": 12, "find": "side"},
        {"sides": [4, 5, 6], "known_side": 2, "known_value": 9, "find": "side", "find_side": 0},
        {"sides": [3, 4, 5], "known_value": 7.5, "find": "area", "small_value": 6},
        {"sides": [5, 5, 6], "known_side": 1, "known_value": 7.5, "find": "side", "find_side": 2},
        {"sides": [3, 4, 5], "known_value": 6, "find": "volume", "small_value": 40},
        {"sides": [6, 8, 10], "known_value": 3, "find": "area", "small_value": 24},
    ],
    "SymmetryReveal": [
        {"shape": "rectangle"},
        {"shape": "equilateral_triangle"},
        {"shape": "parallelogram"},
        {"shape": "kite"},
        {"shape": "regular_polygon", "sides": 6},
        {"shape": "custom", "vertices": [[0, 0], [2, 0], [2, 1], [1, 1], [1, 2], [0, 2]]},
    ],
    "AreaDissector": [
        {"shape": "parallelogram", "base": 8, "height": 5},
        {"shape": "triangle", "base": 10, "height": 6},
        {"shape": "trapezium", "base": 9, "height": 4, "top": 5},
        {"shape": "parallelogram", "base": 6.5, "height": 3.2, "unit": "m"},
        {"shape": "triangle", "base": 7, "height": 9},
        {"shape": "trapezium", "base": 12, "height": 7, "top": 4},
    ],
    "NetFolder": [
        {"solid": "cube", "length": 4},
        {"solid": "cuboid", "length": 5, "width": 3, "height": 2},
        {"solid": "prism", "length": 10, "width": 6, "height": 8},
        {"solid": "pyramid", "width": 6, "height": 5},
        {"solid": "cylinder", "radius": 3, "height": 8},
        {"solid": "cuboid", "length": 8, "width": 2.5, "height": 4, "unit": "m"},
    ],
    "CompassConstruction": [
        {"construction": "perpendicular_bisector", "length": 8},
        {"construction": "angle_bisector", "angle": 70},
        {"construction": "angle_bisector", "angle": 150},
        {"construction": "triangle", "sides": [7, 5, 6]},
        {"construction": "triangle", "sides": [9, 4, 7], "unit": "m"},
        {"construction": "perpendicular_bisector", "length": 5.5},
    ],
    "TreeDiagram": [
        {"outcomes": ["R", "B"], "counts": [3, 2], "replace": False, "find": ["R,B", "B,R"]},
        {"outcomes": ["R", "B"], "counts": [3, 2], "replace": True, "find": ["R,R"]},
        {"outcomes": ["H", "T"], "probabilities": ["1/2", "1/2"], "events": 3, "find": ["H,H,H"]},
        {
            "outcomes": ["W", "L", "D"],
            "probabilities": ["0.5", "0.3", "0.2"],
            "find": ["W,W", "D,D"],
        },
        {"outcomes": ["P", "F"], "probabilities": ["0.7", "0.3"], "find": ["P,F", "F,P", "P,P"]},
        {"outcomes": ["G", "Y"], "counts": [4, 5], "replace": False, "find": ["G,G"]},
    ],
    "SampleSpaceGrid": [
        {
            "first": ["1", "2", "3", "4", "5", "6"],
            "second": ["1", "2", "3", "4", "5", "6"],
            "value": 7,
        },
        {
            "first": ["1", "2", "3", "4", "5", "6"],
            "second": ["1", "2", "3", "4", "5", "6"],
            "condition": ">",
            "value": 8,
        },
        {
            "first": ["1", "2", "3", "4", "5", "6"],
            "second": ["1", "2", "3", "4", "5", "6"],
            "combine": "product",
            "condition": "even",
        },
        {
            "first": ["1", "2", "3", "4", "5", "6"],
            "second": ["H", "T"],
            "combine": "pair",
            "condition": "contains",
            "contains": "6",
            "second_name": "coin",
        },
        {
            "first": ["1", "2", "3", "4"],
            "second": ["1", "2", "3"],
            "combine": "difference",
            "condition": "=",
            "value": 1,
            "first_name": "spinner A",
            "second_name": "spinner B",
        },
        {
            "first": ["1", "2", "3", "4", "5", "6"],
            "second": ["1", "2", "3", "4", "5", "6"],
            "condition": "contains",
            "contains": "6",
        },
    ],
    "ProbabilitySpinner": [
        {"sectors": ["red", "blue", "red", "green", "red", "blue"], "event": "red", "trials": 120},
        {"sectors": ["A", "B", "C", "D"], "event": "B"},
        {"sectors": ["1", "2", "3", "4", "5", "6", "7", "8"], "event": "3", "trials": 200},
        {"sectors": ["win", "lose", "lose", "lose", "lose"], "event": "win", "trials": 60},
        {"sectors": ["red", "red", "red", "blue"], "event": "red"},
        {"sectors": ["X", "Y", "Z"], "event": "Y", "trials": 90},
    ],
    "ChartBuilder": [
        {
            "chart": "pie",
            "categories": ["Bus", "Car", "Walk", "Cycle"],
            "frequencies": [12, 8, 15, 5],
        },
        {
            "chart": "bar",
            "categories": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            "frequencies": [14, 9, 17, 11, 6],
        },
        {"chart": "stem_leaf", "data": [23, 37, 41, 28, 35, 42, 19, 33, 26, 38, 45, 31]},
        {
            "chart": "pie",
            "categories": ["A", "B", "C"],
            "frequencies": [7, 11, 18],
            "title": "Favourite subject",
        },
        {"chart": "bar", "categories": ["Red", "Blue", "Green"], "frequencies": [45, 120, 80]},
        {"chart": "stem_leaf", "data": [5, 12, 17, 8, 21, 14, 9, 16, 11, 25]},
    ],
    "AveragesVisualizer": [
        {"kind": "list", "data": [4, 7, 2, 9, 7, 3, 5, 7, 6]},
        {"kind": "list", "data": [3, 8, 1, 6]},
        {"kind": "table", "values": [0, 1, 2, 3, 4], "frequencies": [3, 7, 6, 3, 1]},
        {"kind": "grouped", "bounds": [0, 10, 20, 30, 40], "frequencies": [4, 9, 12, 5]},
        {"kind": "list", "data": [12.5, 14, 11, 15.5, 14, 13]},
        {"kind": "grouped", "bounds": [140, 150, 160, 170, 180], "frequencies": [6, 14, 11, 3]},
    ],
    "ScatterBestFit": [
        {
            "points": [[2, 52], [3, 55], [5, 61], [6, 60], [8, 70], [9, 71], [11, 78]],
            "x_name": "hours",
            "y_name": "score",
            "estimate_x": 7,
        },
        {"points": [[1, 10], [2, 8], [3, 9], [4, 5], [5, 4], [6, 2]], "estimate_x": 8},
        {"points": [[1, 5], [2, 1], [3, 6], [4, 2], [5, 5], [6, 3]]},
        {
            "points": [[150, 45], [155, 50], [160, 52], [165, 58], [170, 61], [175, 64], [180, 70]],
            "x_name": "height (cm)",
            "y_name": "mass (kg)",
            "estimate_x": 168,
        },
        {
            "points": [[10, 30], [20, 26], [25, 27], [30, 20], [40, 18], [45, 12]],
            "x_name": "temperature",
            "y_name": "sales",
            "estimate_x": 35,
        },
        {"points": [[1, 2], [2, 4], [3, 5], [4, 4], [5, 6], [6, 8], [7, 7], [8, 9]]},
    ],
    "CumulativeFrequency": [
        {"bounds": [0, 10, 20, 30, 40, 50], "frequencies": [4, 11, 19, 12, 4], "name": "time"},
        {
            "bounds": [140, 150, 160, 170, 180, 190],
            "frequencies": [5, 12, 20, 9, 4],
            "name": "height",
            "below": 165,
        },
        {"bounds": [0, 20, 40, 60, 80, 100], "frequencies": [8, 22, 35, 25, 10], "name": "mark"},
        {"bounds": [0, 5, 10, 20, 30], "frequencies": [6, 14, 18, 2], "below": 12},
        {"bounds": [1, 2, 3, 4, 5], "frequencies": [10, 30, 40, 20], "name": "mass"},
        {
            "bounds": [50, 60, 70, 80, 90, 100, 110],
            "frequencies": [3, 9, 16, 24, 12, 6],
            "name": "speed",
            "below": 95,
        },
    ],
    "Histogram": [
        {"bounds": [0, 10, 15, 20, 30, 50], "frequencies": [8, 12, 15, 14, 6], "name": "time"},
        {
            "bounds": [0, 10, 15, 20, 30, 50],
            "frequencies": [8, 12, 15, 14, 6],
            "name": "time",
            "between": [12, 25],
        },
        {
            "bounds": [140, 150, 155, 160, 170, 190],
            "frequencies": [10, 15, 18, 24, 8],
            "name": "height",
        },
        {
            "bounds": [0, 1, 2, 4, 8],
            "frequencies": [5, 9, 12, 8],
            "name": "mass",
            "between": [1.5, 5],
        },
        {"bounds": [20, 30, 35, 40, 60], "frequencies": [12, 18, 15, 20], "name": "age"},
        {"bounds": [0, 5, 10, 20, 40], "frequencies": [20, 30, 25, 10], "between": [0, 15]},
    ],
    "TransformationStage": [
        {"kind": "enlargement", "shape": [[1, 1], [3, 1], [1, 2]], "scale": 2},
        {"kind": "reflection", "shape": [[1, 1], [3, 1], [1, 2]], "mirror": "x=a", "line_value": 4},
        {"kind": "rotation", "shape": [[1, 1], [3, 1], [1, 2]], "angle": 90, "clockwise": True},
        {"kind": "translation", "shape": [[1, 1], [3, 1], [1, 2]], "vector": [-4, 2]},
        {"kind": "enlargement", "shape": [[2, 2], [6, 2], [2, 4]], "scale": -0.5},
        {"kind": "reflection", "shape": [[1, 2], [3, 4], [4, 1]], "mirror": "y=-x"},
        {"kind": "rotation", "shape": [[2, 1], [4, 1], [4, 3]], "angle": 180, "centre": [1, 0]},
    ],
    "VectorArena": [
        {"kind": "magnitude", "a": [3, 4]},
        {"kind": "magnitude", "a": [-2, 5]},
        {"kind": "add", "a": [3, 1], "b": [1, 3]},
        {"kind": "subtract", "a": [4, 1], "b": [1, 3]},
        {"kind": "scalar", "a": [2, 1], "k": -1.5},
        {"kind": "geometry", "a": [4, 0], "b": [1, 4], "ratio": [1, 2]},
        {"kind": "geometry", "a": [5, 1], "b": [1, 4], "ratio": [1, 1]},
    ],
    "Trig3D": [
        {"solid": "cuboid", "length": 8, "width": 6, "height": 5},
        {"solid": "pyramid", "length": 6, "width": 6, "height": 8},
        {"solid": "cuboid", "length": 4, "width": 3, "height": 12, "unit": "m"},
        {"solid": "pyramid", "length": 10, "width": 10, "height": 4},
        {"solid": "cuboid", "length": 12, "width": 5, "height": 3},
        {"solid": "pyramid", "length": 4, "width": 4, "height": 6, "unit": "m"},
    ],
    "TextCard": [
        {"layout": "title", "title": "Circle theorems", "subtitle": "Angles in circles"},
        {
            "layout": "question",
            "title": "Question",
            "text": "A ladder 5 m long leans against a vertical wall with its foot $\\sqrt{7}$ m "
            "from the wall. How far up the wall does it reach?",
        },
        {
            "layout": "points",
            "title": "Key points",
            "points": [
                "The angle in a semicircle is $90^\\circ$",
                "Angles in the same segment are equal",
                "Opposite angles of a cyclic quadrilateral add to $180^\\circ$",
            ],
        },
        {
            "layout": "question",
            "title": "Question 3",
            "place": "side",
            "text": "Find the gradient of $y = x^2 - 3x$ at the point where $x = 4$.",
        },
        {
            "layout": "points",
            "title": "Remember",
            "place": "side",
            "points": [
                "SOH CAH TOA",
                "$\\tan\\theta = \\frac{\\text{opp}}{\\text{adj}}$",
                "Angles to 1 d.p., lengths to 3 s.f.",
            ],
        },
        {"layout": "title", "title": "Simultaneous equations", "place": "side"},
        {
            "layout": "question",
            "text": "A shirt costs \\$24 after a 20% discount. What was the original price?",
        },
    ],
    "GraphTransform": [
        {
            "expression": "x**2",
            "x_min": -2,
            "x_max": 2,
            "transformations": [
                {"kind": "translate_x", "value": 1},
                {"kind": "stretch_y", "value": 2},
                {"kind": "translate_y", "value": -3},
            ],
            "point_x": 1,
        },
        {
            "expression": "sin(x)",
            "x_min": -3.14,
            "x_max": 3.14,
            "transformations": [{"kind": "stretch_x", "value": 2}],
            "point_x": 1.57,
        },
        {
            "expression": "x**3 - 3*x",
            "x_min": -2,
            "x_max": 2,
            "transformations": [{"kind": "reflect_x"}, {"kind": "translate_y", "value": 2}],
            "point_x": -1,
        },
        {
            "expression": "sqrt(x)",
            "x_min": 0,
            "x_max": 4,
            "transformations": [{"kind": "reflect_y"}, {"kind": "translate_x", "value": -3}],
            "point_x": 4,
        },
        {
            "expression": "1/x",
            "x_min": 0.5,
            "x_max": 4,
            "transformations": [
                {"kind": "stretch_y", "value": 3},
                {"kind": "translate_x", "value": 2},
            ],
        },
        {
            "expression": "cos(x)",
            "x_min": 0,
            "x_max": 6.28,
            "transformations": [
                {"kind": "stretch_y", "value": 3},
                {"kind": "translate_y", "value": 1},
            ],
            "point_x": 0,
        },
        {
            "expression": "x**2 - 4*x",
            "x_min": -1,
            "x_max": 5,
            "transformations": [{"kind": "stretch_x", "value": 0.5}],
            "point_x": 2,
        },
    ],
    "FunctionMapping": [
        {"kind": "range", "f": "(x - 2)**2 + 1", "f_min": 0, "f_max": 5},
        {"kind": "range", "f": "2*x - 3", "f_min": -1, "f_max": 4},
        {"kind": "one_one", "f": "x**2 - 4*x + 7", "f_min": -1, "f_max": 5},
        {"kind": "one_one", "f": "1/(x + 1)", "f_min": 0, "f_max": 4},
        {"kind": "one_one", "f": "x**3 - 3*x", "f_min": -2, "f_max": 1.5},
        {"kind": "composite", "f": "2*x + 1", "f_min": 0, "f_max": 3, "g": "x**2 - 1"},
        {
            "kind": "composite",
            "f": "x**2 + 1",
            "f_min": -2,
            "f_max": 2,
            "g": "sqrt(x - 1)",
            "g_min": 1,
        },
        {"kind": "composite", "f": "3 - x", "f_min": 0, "f_max": 5, "g": "1/x", "g_min": 0.5},
    ],
    "LineMeetsCurve": [
        {"curve": "x**2 - 4*x + 7", "line": "x + k"},
        {"curve": "x**2 + 3", "line": "k*x - 1"},
        {"curve": "2*x**2 - 3*x + 4", "line": "k*x + 2"},
        {"curve": "-x**2 + 2*x + 3", "line": "-2*x + k"},
        {"curve": "x**2 - 2*x", "line": "k*x - 4"},
        {"curve": "0.5*x**2 + 1", "line": "3*x + k"},
    ],
    "TrigEquationSolver": [
        {"function": "sin", "b": 2, "c": 30, "k": 0.5, "x_min": 0, "x_max": 360},
        {"function": "cos", "k": -0.5, "x_min": 0, "x_max": 360},
        {"function": "tan", "k": 2, "x_min": -180, "x_max": 180},
        {"function": "sin", "k": 0.3, "x_min": -1, "x_max": 1, "radians": True},
        {"function": "cos", "b": 3, "k": 0.8, "x_min": 0, "x_max": 180},
        {"function": "tan", "b": 0.5, "c": -0.25, "k": 1, "x_min": -2, "x_max": 2, "radians": True},
        {"function": "sin", "c": -60, "k": -1, "x_min": 0, "x_max": 720},
    ],
    "BinomialExpansion": [
        {"a": 2, "b": 3, "n": 5, "terms": 4, "find_power": 2},
        {"a": 1, "b": -2, "n": 6, "terms": 4},
        {"a": 3, "b": -1, "n": 4, "terms": 5, "find_power": 3},
        {"a": 2, "b": 1, "n": -1, "terms": 4},
        {"a": 1, "b": 4, "n": 0.5, "terms": 3},
        {"a": 4, "b": -3, "n": -0.5, "terms": 4, "find_power": 2},
        {"a": 1, "b": 1, "n": 8, "terms": 3},
    ],
    "Progression": [
        {"kind": "arithmetic", "a": 3, "d": 2, "find": "sum", "n": 8},
        {"kind": "arithmetic", "a": 50, "d": -7, "find": "nth_term", "n": 9},
        {"kind": "arithmetic", "a": -4, "d": 1.5, "find": "sum", "n": 20},
        {"kind": "geometric", "a": 2, "r": 3, "find": "nth_term", "n": 6},
        {"kind": "geometric", "a": 64, "r": 0.5, "find": "sum", "n": 7},
        {"kind": "geometric", "a": 8, "r": 0.75, "find": "sum_to_infinity"},
        {"kind": "geometric", "a": 10, "r": -0.6, "find": "sum_to_infinity"},
    ],
    "AntiderivativeFamily": [
        {"gradient": "3*x**2 - 4", "point": [2, 5], "x_min": -3, "x_max": 3},
        {"gradient": "2*x + 1", "point": [1, -2], "x_min": -4, "x_max": 3},
        {"gradient": "(2*x - 1)**3", "point": [1, 0], "x_min": -0.5, "x_max": 1.5},
        {"gradient": "1/sqrt(x)", "point": [4, 3], "x_min": 0.25, "x_max": 9},
        {"gradient": "6/x**2", "point": [2, 1], "x_min": 0.5, "x_max": 6},
        {"gradient": "4 - x**2", "point": [0, 0], "x_min": -3, "x_max": 3},
    ],
    "VolumeOfRevolution": [
        {"axis": "x", "curve": "sqrt(x)", "lower": 0, "upper": 4},
        {"axis": "x", "curve": "9 - x**2", "lower": -2, "upper": 2, "inner": "5"},
        {"axis": "y", "curve": "sqrt(y)", "lower": 0, "upper": 4},
        {"axis": "x", "curve": "1/x", "lower": 1, "upper": 3},
        {"axis": "x", "curve": "x**2 + 1", "lower": 0, "upper": 2},
        {"axis": "y", "curve": "2/y", "lower": 1, "upper": 4},
        {"axis": "x", "curve": "-(x**2) + 4*x", "lower": 0, "upper": 4},
    ],
    "ModulusEquation": [
        {"left": "abs(3*x - 2)", "relation": "=", "right": "abs(2*x + 7)"},
        {"left": "2*x + 5", "relation": "<", "right": "abs(x + 1)"},
        {"left": "abs(x - 3)", "relation": "<=", "right": "4"},
        {"left": "abs(2*x - 1)", "relation": ">", "right": "abs(x + 2)"},
        {"left": "abs(x + 2)", "relation": "=", "right": "3*x - 4"},
        {"left": "2*abs(x - 1)", "relation": ">=", "right": "abs(x + 3)"},
        {"left": "abs(4 - x)", "relation": "=", "right": "0.5*x + 1"},
    ],
    "PolynomialDivision": [
        {"dividend": "2*x**3 + 3*x**2 - 8*x + 3", "divisor": "x - 1"},
        {"dividend": "x**3 - 7*x + 6", "divisor": "x + 3"},
        {"dividend": "x**4 + 2*x**3 - x + 5", "divisor": "x**2 + 1"},
        {"dividend": "6*x**3 + x**2 - 5*x + 2", "divisor": "2*x - 1"},
        {"dividend": "x**3 + 4*x**2 + x - 3", "divisor": "x + 2"},
        {"dividend": "3*x**2 - 5*x + 7", "divisor": "x - 2"},
        {"dividend": "x**4 - 16", "divisor": "x - 2"},
    ],
    "PartialFractions": [
        {"numerator": "5*x + 1", "denominator": "(x + 1)*(x - 2)"},
        {"numerator": "x**2 + 3", "denominator": "(x + 1)*(x - 1)*(x + 3)"},
        {"numerator": "3*x + 4", "denominator": "(2*x + 1)*(x - 1)**2"},
        {"numerator": "2*x**2 - x + 7", "denominator": "(x + 2)*(x**2 + 1)"},
        {"numerator": "7", "denominator": "(3*x - 1)*(x + 2)"},
        {"numerator": "x**2 + 5*x", "denominator": "(x - 2)*(x + 1)**2"},
        {"numerator": "4*x", "denominator": "(2*x - 3)*(x**2 + 3)"},
    ],
    "LogLinearisation": [
        {"model": "power", "points": [[1, 3], [2, 12.1], [3, 27], [4, 47.9], [5, 75.2]]},
        {"model": "exponential", "points": [[0, 5], [1, 7.5], [2, 11.2], [3, 16.9], [4, 25.3]]},
        {"model": "power", "points": [[2, 5.66], [8, 45.3]]},
        {"model": "exponential", "points": [[1, 40], [3, 10]]},
        {"model": "power", "points": [[0.5, 16], [1, 4], [2, 1], [4, 0.25]]},
        {"model": "exponential", "points": [[-2, 0.8], [0, 2], [2, 5], [4, 12.5], [6, 31.2]]},
    ],
    "HarmonicForm": [
        {"a": 3, "b": 4, "form": "R sin(t + a)"},
        {"a": 5, "b": -12, "form": "R sin(t - a)", "solve_for": 6},
        {"a": 1, "b": 1, "form": "R cos(t - a)"},
        {"a": -2, "b": 3, "form": "R cos(t + a)", "solve_for": 1},
        {"a": 3, "b": 2, "form": "R sin(t + a)", "solve_for": -2},
        {"a": 1.5, "b": -2, "form": "R sin(t - a)"},
    ],
    "TrapeziumRule": [
        {"expression": "sqrt(1 + x**2)", "lower": "0", "upper": "2", "strips": 4},
        {"expression": "1/(1 + x)", "lower": "0", "upper": "1", "strips": 2},
        {"expression": "sin(x)", "lower": "0", "upper": "pi", "strips": 4},
        {"expression": "exp(-x**2)", "lower": "-1", "upper": "1", "strips": 4},
        {"expression": "ln(x)", "lower": "1", "upper": "5", "strips": 4},
        {"expression": "x**3", "lower": "1", "upper": "3", "strips": 8},
        {"expression": "2*x + 1", "lower": "0", "upper": "4", "strips": 2},
        {"expression": "sqrt(cos(x))", "lower": "0", "upper": "pi/3", "strips": 3},
    ],
    "IterationDiagram": [
        {"iteration": "(x + 5)**(1/3)", "x0": 2, "sign_change": [1, 2], "places": 2},
        {"iteration": "exp(-x)", "x0": 0.5, "places": 2},
        {"iteration": "(x**2 + 3)/5", "x0": 1, "places": 3},
        {"iteration": "(x**2 + 3)/5", "x0": 5, "places": 2},
        {"iteration": "2 - ln(x)", "x0": 1.5, "sign_change": [1, 2], "places": 2},
        {"iteration": "cos(x)", "x0": 1, "places": 1},
    ],
    "ParametricCurve": [
        {"x": "t**2", "y": "2*t", "t_min": -2, "t_max": 2, "t0": 1},
        {"x": "t - exp(2*t)", "y": "t + exp(2*t)", "t_min": -2, "t_max": 0.5, "t0": 0},
        {
            "x": "3*cos(t)",
            "y": "2*sin(t)",
            "t_min": 0,
            "t_max": 6.283,
            "t0": 0.785,
            "line": "normal",
        },
        {"x": "t**3", "y": "t**2 - 1", "t_min": -1.5, "t_max": 1.5, "t0": 1},
        {"x": "2*t + 1", "y": "4/t", "t_min": 0.5, "t_max": 4, "t0": 2, "line": "normal"},
        {"x": "t - sin(t)", "y": "1 - cos(t)", "t_min": 0, "t_max": 6.28, "t0": 1.5},
    ],
    "ImplicitCurve": [
        {
            "equation": "x**2 + y**2 = x*y + 7",
            "point": [3, 2],
            "x_min": -4,
            "x_max": 4,
            "y_min": -4,
            "y_max": 4,
        },
        {
            "equation": "x**2 + y**2 = 25",
            "point": [3, 4],
            "x_min": -6,
            "x_max": 6,
            "y_min": -6,
            "y_max": 6,
        },
        {
            "equation": "x**3 + y**3 = 9*x*y",
            "point": [2, 4],
            "x_min": -3,
            "x_max": 6,
            "y_min": -3,
            "y_max": 6,
            "line": "normal",
        },
        {
            "equation": "y**2 = x**3 - x + 1",
            "point": [1, -1],
            "x_min": -2,
            "x_max": 3,
            "y_min": -4,
            "y_max": 4,
        },
        {
            "equation": "x*y + y**2 = 6",
            "point": [1, 2],
            "x_min": -5,
            "x_max": 5,
            "y_min": -5,
            "y_max": 5,
        },
        {
            "equation": "x**2 - 4*y**2 = 5",
            "point": [3, 1],
            "x_min": -6,
            "x_max": 6,
            "y_min": -4,
            "y_max": 4,
            "line": "normal",
        },
    ],
    "IntegrationMethod": [
        {"method": "parts", "integrand": "x*sin(2*x)", "u": "x"},
        {"method": "parts", "integrand": "x**2*exp(-x)", "u": "x**2", "lower": "0", "upper": "1"},
        {"method": "parts", "integrand": "x*ln(x)", "u": "ln(x)", "lower": "1", "upper": "2"},
        {"method": "substitution", "integrand": "sin(x)**2*cos(x)", "u": "sin(x)"},
        {
            "method": "substitution",
            "integrand": "x*sqrt(x**2 + 1)",
            "u": "x**2 + 1",
            "lower": "0",
            "upper": "2",
        },
        {"method": "log_form", "integrand": "x/(x**2 + 1)"},
        {"method": "log_form", "integrand": "tan(x)", "lower": "0", "upper": "pi/4"},
    ],
    "DifferentialEquation": [
        {"gradient": "x*y", "point": [0, 1], "x_min": -2, "x_max": 2},
        {"gradient": "(y - 1)/x", "point": [1, 3], "x_min": 0.5, "x_max": 4},
        {"gradient": "-0.5*y", "point": [0, 8], "x_min": 0, "x_max": 6},
        {"gradient": "2*x*(1 + y**2)", "point": [0, 0], "x_min": -1, "x_max": 1},
        {"gradient": "y**2*cos(x)", "point": [0, 0.5], "x_min": -3, "x_max": 3},
        {"gradient": "x/y", "point": [0, 2], "x_min": -3, "x_max": 3},
    ],
    "VectorLines3D": [
        {"kind": "intersection", "a": [1, 2, 0], "b": [1, 0, 1], "c": [3, 1, 1], "d": [0, 1, 1]},
        {"kind": "intersection", "a": [1, 0, 2], "b": [2, 1, -1], "c": [0, 3, 1], "d": [1, -1, 2]},
        {"kind": "intersection", "a": [0, 1, 1], "b": [1, 2, -1], "c": [3, 0, 0], "d": [-2, -4, 2]},
        {"kind": "angle", "a": [1, 0, 0], "b": [2, -1, 2], "c": [0, 1, 3], "d": [1, 1, 0]},
        {"kind": "angle", "a": [0, 0, 0], "b": [1, 2, 3], "c": [1, 1, 1], "d": [-3, 0, 1]},
        {"kind": "foot", "a": [1, 2, 3], "b": [1, -1, 2], "p": [4, 5, 0]},
        {"kind": "foot", "a": [0, 0, 1], "b": [2, 1, 2], "p": [3, -2, 4]},
    ],
    "ArgandDiagram": [
        {"kind": "modulus_argument", "z": [-1, "sqrt(3)"]},
        {"kind": "modulus_argument", "z": [3, -4]},
        {"kind": "conjugate", "z": [2, 3]},
        {"kind": "add", "z": [3, 1], "w": [1, 2]},
        {"kind": "subtract", "z": [2, 3], "w": [3, -1]},
        {"kind": "multiply", "z": [1, 1], "w": [1, 2]},
        {"kind": "divide", "z": [5, 5], "w": [1, 2]},
        {"kind": "square_roots", "z": [5, 12]},
        {"kind": "square_roots", "z": [-3, 4]},
    ],
    "ComplexLoci": [
        {
            "loci": [
                {"kind": "circle", "relation": "<=", "a": [1, 1], "r": 2},
                {"kind": "sector", "a": [1, 1], "angle": "0", "angle_2": "pi/2"},
            ]
        },
        {
            "loci": [
                {"kind": "circle", "a": [0, 0], "r": 5},
                {"kind": "half_line", "a": [0, 0], "angle": "pi/4"},
            ]
        },
        {"loci": [{"kind": "bisector", "a": [2, 0], "b": [0, -2]}]},
        {
            "loci": [
                {"kind": "bisector", "relation": "<", "a": [1, 2], "b": [3, 0]},
                {"kind": "circle", "relation": "<", "a": [2, 1], "r": 3},
            ]
        },
        {
            "loci": [
                {"kind": "circle", "a": [-1, 2], "r": 2},
                {"kind": "bisector", "a": [0, 0], "b": [2, 2]},
            ]
        },
        {
            "loci": [
                {"kind": "half_line", "a": [1, 0], "angle": "3*pi/4"},
                {"kind": "half_line", "a": [-2, 0], "angle": "pi/4"},
            ]
        },
        {"loci": [{"kind": "circle", "relation": ">", "a": [0, 1], "r": 1.5}]},
    ],
    "ForceDiagram": [
        {
            "find": "equilibrium",
            "mass": 5,
            "surface": "incline",
            "slope": 30,
            "friction": "limiting",
            "forces": [{"name": "P", "magnitude": 40, "angle": 20}],
        },
        {
            "find": "equilibrium",
            "forces": [
                {"name": "P", "magnitude": 10, "angle": 0},
                {"name": "Q", "angle": 120},
                {"name": "S", "angle": 230},
            ],
        },
        {
            "find": "acceleration",
            "mass": 4,
            "surface": "horizontal",
            "friction": "limiting",
            "mu": 0.25,
            "forces": [{"name": "T", "magnitude": 30, "angle": 30}],
        },
        {"find": "acceleration", "mass": 2, "surface": "incline", "slope": 25, "friction": "none"},
        {
            "find": "equilibrium",
            "mass": 3,
            "surface": "incline",
            "slope": 40,
            "friction": "unknown",
            "friction_direction": "up",
        },
        {
            "find": "equilibrium",
            "mass": 8,
            "forces": [{"name": "A", "angle": 150}, {"name": "B", "angle": 45}],
        },
        {
            "find": "acceleration",
            "mass": 10,
            "surface": "incline",
            "slope": 20,
            "friction": "limiting",
            "mu": 0.3,
            "forces": [{"name": "P", "magnitude": 120, "angle": 0}],
        },
    ],
    "SuvatSolver": [
        {"u": 4, "a": 2, "t": 5, "find": "s"},
        {"u": 20, "v": 0, "s": 50, "find": "a"},
        {"u": 0, "a": 9.8, "s": 20, "find": "t"},
        {"s": 120, "t": 8, "v": 20, "find": "u"},
        {"u": 12, "a": -3, "t": 6, "find": "v"},
        {"u": 5, "v": 15, "t": 4, "find": "s"},
        {"u": 2, "a": 1.5, "s": 30, "find": "v"},
    ],
    "MomentumCollision": [
        {"m1": 3, "m2": 2, "u1": 6, "u2": -4, "v2": 5},
        {"m1": 0.5, "m2": 1.5, "u1": 8, "u2": 0, "coalesce": True},
        {"m1": 4, "m2": 6, "u1": 5, "u2": 2, "v1": 1},
        {"m1": 2, "u1": 7, "u2": -3, "v1": -2, "v2": 3},
        {"m1": 1200, "m2": 800, "u1": 15, "u2": 10, "coalesce": True},
        {"m1": 5, "m2": 3, "u2": -2, "v1": 0, "v2": 4},
    ],
    "ConnectedParticles": [
        {"setup": "table_pulley", "m_a": 4, "m_b": 2, "mu": 0.2},
        {"setup": "table_pulley", "m_a": 3, "m_b": 1.5},
        {"setup": "two_hanging", "m_a": 3, "m_b": 5},
        {"setup": "two_hanging", "m_a": 0.6, "m_b": 0.4},
        {"setup": "incline_pulley", "m_a": 2, "m_b": 3, "slope": 30, "mu": 0.25},
        {"setup": "incline_pulley", "m_a": 6, "m_b": 1, "slope": 40},
        {
            "setup": "towing",
            "m_a": 1200,
            "m_b": 400,
            "driving_force": 3000,
            "resistance_a": 400,
            "resistance_b": 200,
        },
    ],
    "WorkEnergy": [
        {
            "kind": "work_energy",
            "mass": 60,
            "u": 2,
            "h": -5,
            "d": 40,
            "resistance": 20,
            "find": "v",
        },
        {
            "kind": "work_energy",
            "mass": 2,
            "u": 0,
            "v": 6,
            "h": 0,
            "d": 10,
            "pull_force": 15,
            "pull_angle": 30,
            "find": "resistance",
        },
        {"kind": "work_energy", "mass": 0.5, "u": 12, "v": 0, "d": 0, "resistance": 0, "find": "h"},
        {
            "kind": "work_energy",
            "mass": 1500,
            "u": 20,
            "v": 10,
            "h": 0,
            "resistance": 3000,
            "find": "d",
        },
        {"kind": "power", "mass": 1200, "v": 15, "power": 30000, "resistance": 800, "find": "a"},
        {
            "kind": "power",
            "mass": 900,
            "power": 20000,
            "resistance": 500,
            "slope": 5,
            "find": "max_speed",
        },
        {
            "kind": "power",
            "mass": 1000,
            "v": 20,
            "resistance": 600,
            "slope": -3,
            "acceleration": 0.5,
            "find": "power",
        },
    ],
    "BoxPlot": [
        {"data": [12, 15, 18, 21, 22, 25, 27, 30, 31, 34, 38, 41, 45]},
        {
            "data": [23, 31, 35, 38, 42, 44, 47, 51, 55, 58, 62, 66],
            "data_2": [18, 25, 29, 33, 36, 37, 41, 43, 48, 50, 54],
            "names": ["Boys", "Girls"],
        },
        {"data": [5.2, 6.8, 7.1, 7.5, 8.0, 8.3, 9.9, 10.4], "stem_leaf": False},
        {"data": [101, 104, 108, 111, 113, 117, 120, 125, 131], "stem_leaf": False},
        {
            "data": [7, 9, 12, 15, 15, 16, 19, 23, 28, 34],
            "data_2": [11, 13, 14, 18, 21, 24, 25, 26, 29, 31],
            "names": ["Team X", "Team Y"],
        },
        {"data": [62, 64, 65, 67, 70, 71, 73, 76, 78, 81, 85, 88, 90, 94, 97]},
    ],
    "StandardDeviation": [
        {"kind": "list", "data": [4, 7, 7, 8, 10, 12]},
        {"kind": "frequency", "values": [0, 1, 2, 3, 4], "frequencies": [5, 9, 12, 6, 3]},
        {"kind": "grouped", "bounds": [0, 10, 20, 30, 40, 50], "frequencies": [4, 11, 17, 9, 3]},
        {"kind": "totals", "n": 20, "sum_x": 360, "sum_x2": 6880},
        {"kind": "coded", "n": 12, "sum_x": 30, "sum_x2": 210, "a": 50},
        {"kind": "list", "data": [1.2, 1.5, 1.9, 2.4, 2.4, 3.0, 3.3, 4.1]},
    ],
    "ArrangementCounter": [
        {"kind": "word", "word": "NEEDLESS"},
        {"kind": "word", "word": "STATISTICS"},
        {"kind": "together", "n": 7, "k": 3},
        {"kind": "apart", "n": 6},
        {
            "kind": "selection",
            "groups": [
                {"name": "men", "size": 6, "choose": 3},
                {"name": "women", "size": 5, "choose": 2},
            ],
        },
        {"kind": "selection", "groups": [{"name": "books", "size": 10, "choose": 4}]},
        {"kind": "word", "word": "PARALLEL"},
    ],
    "DiscreteDistribution": [
        {"kind": "binomial", "n": 8, "p": "0.3", "high": 2},
        {"kind": "binomial", "n": 12, "p": "1/4", "low": 3, "high": 5},
        {
            "kind": "table",
            "values": [1, 2, 3, 4],
            "probabilities": ["1/10", "3/10", "2/5", "1/5"],
            "low": 2,
        },
        {"kind": "geometric", "p": "0.2", "low": 4},
        {"kind": "geometric", "p": "1/6", "low": 3, "high": 3},
        {"kind": "poisson", "lam": 2.5, "high": 3},
        {"kind": "poisson", "lam": 4, "low": 6},
    ],
    "NormalDistribution": [
        {"kind": "probability", "mu": 50, "sigma": 8, "low": 45, "high": 60},
        {"kind": "probability", "mu": 172, "sigma": 9, "low": 180},
        {"kind": "probability", "mu": 3.2, "sigma": 0.4, "high": 2.7},
        {"kind": "inverse", "mu": 120, "sigma": 15, "probability": 0.9},
        {"kind": "inverse", "mu": 65, "sigma": 4, "probability": 0.25, "tail": "above"},
        {"kind": "find_parameters", "sigma": 5, "conditions": [{"x": 40, "below": 0.8}]},
        {"kind": "find_parameters", "mu": 30, "conditions": [{"x": 26, "below": 0.15}]},
        {
            "kind": "find_parameters",
            "conditions": [{"x": 20, "below": 0.1}, {"x": 35, "below": 0.75}],
        },
        {"kind": "approximation", "source": "binomial", "n": 100, "p": 0.3, "low": 25, "high": 35},
        {"kind": "approximation", "source": "binomial", "n": 60, "p": 0.4, "high": 20},
        {"kind": "approximation", "source": "poisson", "lam": 25, "low": 30},
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
