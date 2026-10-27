"""TableOfValues: a table of values worked out from y = f(x), its points plotted, and the smooth
curve drawn through them (4024 2.10; PRIMITIVES.md #19, table of values).

This is how O Level asks for graphs to be drawn: complete the table, plot the points, join them
with a smooth curve. Each y-value is computed by SymPy and shown exactly when it is a whole
number, otherwise to 3 significant figures.
"""

from typing import Annotated

import numpy as np
import sympy as sp
from manim import Dot, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams, Region
from app.primitives import style
from app.primitives.analysis import vertical_asymptotes
from app.primitives.plotting import curve, make_plot, make_table, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    exact,
    format_sf,
    parse_expression,
    written_latex,
)

X = sp.Symbol("x", real=True)
Coordinate = Annotated[float, Field(ge=-20, le=20)]
GRAPH = Region(x_min=0.0, x_max=0.62, y_min=0.0, y_max=0.62)
MAX_POINTS = 11


class TableOfValuesParams(PrimitiveParams):
    expression: str = Field(min_length=1, max_length=120, description="y = f(x), e.g. x**2 - 2*x")
    x_min: Coordinate
    x_max: Coordinate
    step: Annotated[float, Field(gt=0, le=10)] = Field(default=1, description="Gap between x's")


class TableOfValues(StagedPrimitive[TableOfValuesParams]):
    primitive_id = "TableOfValues"
    version = "1"
    topic = "Functions and graphs"
    params_model = TableOfValuesParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("axes", "*"), ("curve", "*"), ("points", "*"), ("table*", "table*")],
    )

    def default_params(self) -> TableOfValuesParams:
        return TableOfValuesParams(expression="x**2 - 2*x - 3", x_min=-2, x_max=4)

    def validate(self, params: TableOfValuesParams) -> list[PredicateFailure]:
        try:
            f = parse_expression(params.expression, {"x"})
        except ExpressionError as error:
            return [_failure("parsing", "expression_parses", str(error), "expression")]
        if params.x_min >= params.x_max:
            return [
                _failure("consistency", "interval_ordered", "x_min must be below x_max", "x_min")
            ]
        xs = _xs(params)
        if len(xs) > MAX_POINTS:
            message = f"more than {MAX_POINTS} columns; use a bigger step"
            return [_failure("consistency", "few_columns", message, "step")]
        if len(xs) < 3:
            return [_failure("consistency", "enough_columns", "fewer than 3 columns", "step")]
        for x in xs:
            value = f.subs(X, x)
            if not (value.is_real and value.is_finite):
                message = f"y is not defined at x = {sp.sstr(x)}; leave that column out"
                return [_failure("domain", "defined_at_each_x", message, "x_min", "step")]
        if vertical_asymptotes(sp.nsimplify(f, rational=True), params.x_min, params.x_max):
            message = "the curve has an asymptote inside the table; plot each branch separately"
            return [_failure("domain", "no_asymptote", message, "x_min", "x_max")]
        return []

    def computed_values(self, params: TableOfValuesParams) -> dict[str, str]:
        f = parse_expression(params.expression, {"x"})
        return {f"y_at_{format_sf(x)}": _value(f.subs(X, x)) for x in _xs(params)}

    def build(self, params: TableOfValuesParams, level):
        f = sp.nsimplify(parse_expression(params.expression, {"x"}), rational=True)
        xs = _xs(params)
        ys = [f.subs(X, x) for x in xs]
        title, _ = style.graph_boxes(style.GRAPH_REGION)
        upper, _ = style.title_lines(title)
        table_box = style.Box(title.left, title.right, title.bottom - 1.25, title.bottom - 0.05)
        table = make_table(
            [["x", *(format_sf(x) for x in xs)], ["y", *(_value(y) for y in ys)]],
            table_box,
            font_size=28,
        )
        numeric = sp.lambdify(X, f, "math")
        fine = np.linspace(float(xs[0]), float(xs[-1]), 121)
        plot = make_plot(
            GRAPH,
            [float(xs[0]), float(xs[-1])],
            [float(y) for y in ys] + [numeric(x) for x in fine],
            title=False,
        )
        points = VGroup(
            *(
                Dot(plot.point(float(x), float(y)), color=style.POINT_COLOUR, radius=0.07)
                for x, y in zip(xs, ys, strict=True)
            )
        )
        return {
            "equation": text_line(f"y = {written_latex(params.expression)}", upper),
            "table_lines": table.lines,
            "table_x": VGroup(*table.cells[0]),
            "table_y": VGroup(*table.cells[1][1:]),
            "table_y_head": table.cells[1][0],
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "points": points,
            "curve": curve(plot, numeric, float(xs[0]), float(xs[-1])),
        }

    def stages(self, params: TableOfValuesParams, level) -> list[Stage]:
        steps = [
            stage("equation", "This is the equation to draw", 1.5, ["equation"]),
            stage(
                "table", "Make a table of x values", 2.0, ["table_lines", "table_x", "table_y_head"]
            ),
            stage(
                "values",
                "Substitute each x to work out its y",
                3.5,
                ["table_y"],
                emphasise=["table_y"],
            ),
            stage(
                "axes",
                "Draw axes that fit every value in the table",
                2.0,
                ["axes", "x_label", "y_label"],
            ),
            stage("points", "Plot each pair as a point", 2.5, ["points"]),
            stage("curve", "Join the points with a smooth curve", 2.5, ["curve"]),
        ]

        def standard(s):
            return [
                combine("table", "The equation and a table of x values", 2.5, s[0], s[1]),
                s[2],
                combine("plot", "Draw the axes and plot the points", 3.0, s[3], s[4]),
                s[5],
            ]

        def concise(s):
            return [
                combine("table", "Complete the table of values", 3.5, *s[:3]),
                combine("graph", "Plot the points and join them", 3.5, *s[3:]),
            ]

        return by_level(level, steps, standard, concise)


def _xs(params: TableOfValuesParams) -> list[sp.Expr]:
    lo, hi, step = exact(params.x_min), exact(params.x_max), exact(params.step)
    count = int(sp.floor((hi - lo) / step)) + 1
    return [lo + k * step for k in range(min(count, MAX_POINTS + 1))]


def _value(y: sp.Expr) -> str:
    return format_sf(y)


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
