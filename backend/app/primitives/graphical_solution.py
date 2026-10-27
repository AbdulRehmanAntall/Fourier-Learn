"""GraphicalSolution: an equation f(x) = g(x) solved by drawing y = f(x) and y = g(x) and
reading the x-coordinates where they meet (4024 2.10; PRIMITIVES.md #19, line-curve
intersections).

O Level asks for solutions "by drawing a suitable line" on a given curve; this shows both
graphs, marks where they cross, and drops a line to the x-axis at each crossing. The crossings
are found by SymPy (exactly where it can, by bisection otherwise) and read off to 3 significant
figures, with the exact value when it is simple.
"""

from typing import Annotated

import numpy as np
import sympy as sp
from manim import DashedLine, Dot, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.analysis import samples, zeros
from app.primitives.plotting import curve, label, make_plot, place_label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    format_sf,
    format_value,
    latex_value,
    parse_expression,
    written_latex,
)

X = sp.Symbol("x", real=True)
Coordinate = Annotated[float, Field(ge=-20, le=20)]
MAX_SOLUTIONS = 4


class GraphicalSolutionParams(PrimitiveParams):
    curve: str = Field(min_length=1, max_length=120, description="The first graph, e.g. x**2 - 2*x")
    line: str = Field(min_length=1, max_length=120, description="The second graph, e.g. x + 1")
    x_min: Coordinate
    x_max: Coordinate


class GraphicalSolution(StagedPrimitive[GraphicalSolutionParams]):
    primitive_id = "GraphicalSolution"
    version = "1"
    topic = "Functions and graphs"
    params_model = GraphicalSolutionParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("axes", "*"),
            ("curve", "*"),
            ("line", "*"),
            ("drops", "*"),
            ("meet_*", "meet_*"),
        ],
    )

    def default_params(self) -> GraphicalSolutionParams:
        return GraphicalSolutionParams(curve="x**2 - 2*x - 1", line="x + 1", x_min=-2, x_max=5)

    def validate(self, params: GraphicalSolutionParams) -> list[PredicateFailure]:
        parsed = {}
        for name in ("curve", "line"):
            try:
                parsed[name] = parse_expression(getattr(params, name), {"x"})
            except ExpressionError as error:
                return [_failure("parsing", "expression_parses", str(error), name)]
        if params.x_min >= params.x_max:
            message = "x_min must be below x_max"
            return [_failure("consistency", "interval_ordered", message, "x_min")]
        for name, expr in parsed.items():
            _, ys = samples(expr, params.x_min, params.x_max, 201)
            if not np.isfinite(ys).all():
                message = f"{name} is not real and finite everywhere on the interval"
                return [_failure("domain", "real_and_finite", message, name)]
        if sp.simplify(parsed["curve"] - parsed["line"]) == 0:
            message = "the two graphs are the same"
            return [_failure("consistency", "different_graphs", message, "line")]
        found = _solutions(params)
        if not found:
            message = "the graphs do not meet on the plotted interval"
            return [_failure("consistency", "graphs_meet", message, "x_min", "x_max")]
        if len(found) > MAX_SOLUTIONS:
            message = f"the graphs meet more than {MAX_SOLUTIONS} times; narrow the interval"
            return [_failure("consistency", "few_solutions", message, "x_min", "x_max")]
        return []

    def computed_values(self, params: GraphicalSolutionParams) -> dict[str, str]:
        found = _solutions(params)
        values = {"number_of_solutions": str(len(found))}
        f = parse_expression(params.curve, {"x"})
        for i, x in enumerate(found, start=1):
            values[f"solution_{i}"] = format_value(x)
            values[f"point_{i}"] = f"({format_value(x)}, {format_value(f.subs(X, x))})"
        return values

    def build(self, params: GraphicalSolutionParams, level):
        f = parse_expression(params.curve, {"x"})
        g = parse_expression(params.line, {"x"})
        found = _solutions(params)
        _, fy = samples(f, params.x_min, params.x_max, 121)
        _, gy = samples(g, params.x_min, params.x_max, 121)
        plot = make_plot(self.layout.region, [params.x_min, params.x_max], [*fy, *gy])
        f_num, g_num = sp.lambdify(X, f, "math"), sp.lambdify(X, g, "math")
        solved = r"\ \text{or}\ ".join(_reading(x) for x in found)
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "equation": text_line(
                f"{written_latex(params.curve)} = {written_latex(params.line)}", plot.upper
            ),
            "curve": curve(plot, f_num, params.x_min, params.x_max),
            "line": curve(plot, g_num, params.x_min, params.x_max, colour=style.RUN_COLOUR),
            "solutions": text_line(solved, plot.lower),
        }
        obstacles = plot.obstacles()
        paths = [parts["curve"], parts["line"], *plot.axis_lines()]
        meets, drops = [], VGroup()
        for i, x in enumerate(found, start=1):
            point = plot.point(float(x), float(f.subs(X, x)))
            parts[f"meet_{i}"] = Dot(point, color=style.POINT_COLOUR)
            meets.append(parts[f"meet_{i}"])
            drops.add(DashedLine(point, plot.point(float(x), 0), color=style.POINT_COLOUR))
        parts["drops"] = drops
        obstacles += meets
        paths.append(drops)
        for name, expr, colour, end in (
            ("curve_label", params.curve, style.CURVE_COLOUR, params.x_max),
            ("line_label", params.line, style.RUN_COLOUR, params.x_max),
        ):
            numeric = f_num if name == "curve_label" else g_num
            y_end = min(max(float(numeric(end)), plot.y_range[0]), plot.y_range[1])
            text = label(f"y = {written_latex(expr)}", colour=colour)
            parts[name] = place_label(
                text, plot.point(end, y_end), plot.plot_box, obstacles, paths, wide=True
            )
            obstacles.append(text)
        for i, x in enumerate(found, start=1):
            text = label(_reading(x), colour=style.POINT_COLOUR)
            anchor = plot.point(float(x), 0)
            parts[f"meet_{i}_label"] = place_label(
                text, anchor, plot.plot_box, obstacles, paths, wide=True
            )
            obstacles.append(text)
        return parts

    def stages(self, params: GraphicalSolutionParams, level) -> list[Stage]:
        count = len(_solutions(params))
        meets = [f"meet_{i}" for i in range(1, count + 1)]
        values = [f"meet_{i}_label" for i in range(1, count + 1)]
        steps = [
            stage("axes", "Draw the axes", 1.5, ["axes", "x_label", "y_label"]),
            stage("equation", "This is the equation to solve", 1.5, ["equation"]),
            stage("curve", "Draw the graph of the left-hand side", 2.5, ["curve", "curve_label"]),
            stage(
                "line",
                "Draw the graph of the right-hand side on the same axes",
                2.5,
                ["line", "line_label"],
            ),
            stage(
                "meet", "The solutions are where the two graphs meet", 2.0, meets, emphasise=meets
            ),
            stage(
                "read",
                "Read the x-coordinate of each meeting point off the x-axis",
                3.0,
                ["drops", *values, "solutions"],
                emphasise=["solutions"],
            ),
        ]

        def standard(s):
            return [
                combine("graphs", "Draw the axes and the first graph", 3.0, *s[:3]),
                s[3],
                combine("solve", "Mark where they meet and read off the x-values", 3.5, *s[4:]),
            ]

        def concise(s):
            return [
                combine("graphs", "Draw both sides of the equation as graphs", 3.0, *s[:4]),
                combine("solve", "Read off the x-values where they meet", 3.5, *s[4:]),
            ]

        return by_level(level, steps, standard, concise)


def _solutions(params: GraphicalSolutionParams) -> list:
    f = sp.nsimplify(parse_expression(params.curve, {"x"}), rational=True)
    g = sp.nsimplify(parse_expression(params.line, {"x"}), rational=True)
    return zeros(sp.simplify(f - g), params.x_min, params.x_max, [])[: MAX_SOLUTIONS + 1]


def _reading(x) -> str:
    """A solution as read off a graph: exact if it is a simple fraction, else to 3 s.f."""
    value = sp.nsimplify(x) if not isinstance(x, float) else x
    if isinstance(value, sp.Rational) and abs(value.q) <= 20:
        return f"x = {latex_value(value)}"
    return rf"x \approx {format_sf(value)}"


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
