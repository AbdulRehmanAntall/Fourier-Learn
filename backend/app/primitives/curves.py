"""What the primitives that draw y = f(x) on axes share: TangentSlide, SecantToTangent and
AreaUnderCurve (report Table 5.2, introductory calculus).

The parameter schema starts from the function and its plotted interval; the predicates check
that f parses, is real and finite at sampled points, and is continuous on the interval (§5.3.3).
Continuity is checked symbolically, because sampling alone misses an asymptote between two
samples, such as tan(x) at pi/2.
"""

from dataclasses import dataclass
from typing import Annotated

import numpy as np
import sympy as sp
from manim import Axes, MathTex, Mobject
from pydantic import Field
from sympy.calculus.util import continuous_domain

from app.contracts import PredicateFailure, PrimitiveParams, Region
from app.primitives import style
from app.primitives.symbolic import (
    ExpressionError,
    exact,
    failing_samples,
    format_number,
    latex_number,
    parse_expression,
    sample_points,
    written_latex,
)

X = sp.Symbol("x", real=True)
Coordinate = Annotated[float, Field(ge=-20, le=20)]


class CurveParams(PrimitiveParams):
    expression: str = Field(min_length=1, max_length=120, description="f(x), e.g. x**2 - 3*x")
    x_min: Coordinate = Field(description="Left end of the plotted interval")
    x_max: Coordinate = Field(description="Right end of the plotted interval")


def failure(kind: str, predicate: str, message: str, *parameters: str) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )


def parse_function(text: str) -> sp.Expr:
    """f(x) with decimals made exact: 0.5*x becomes x/2, so its derivative and integral are exact
    fractions rather than 0.25*x**2 + 1.0*x."""
    return sp.nsimplify(parse_expression(text, {"x"}), rational=True)


def check_curve(params: CurveParams) -> tuple[sp.Expr | None, list[PredicateFailure]]:
    """Parse f and check it on the plotted interval. Returns f (None if it does not parse) and
    the failures; a primitive adds its own predicates only when there are none."""
    try:
        f = parse_function(params.expression)
    except ExpressionError as error:
        return None, [failure("parsing", "expression_parses", str(error), "expression")]
    if params.x_min >= params.x_max:
        return f, [failure("consistency", "interval_ordered", "x_min must be below x_max", "x_min")]
    bad = failing_samples(f, X, sample_points(params.x_min, params.x_max))
    if bad:
        message = f"f is not real and finite at x = {list_points(bad)}"
        return f, [failure("domain", "real_and_finite", message, "expression")]
    if not continuous_on(f, params.x_min, params.x_max):
        message = "f is not continuous on the plotted interval"
        return f, [failure("domain", "continuous", message, "expression", "x_min", "x_max")]
    return f, []


def continuous_on(expr: sp.Expr, lo: float, hi: float) -> bool:
    """Whether `expr` is continuous on [lo, hi], by SymPy's continuity analysis."""
    interval = sp.Interval(exact(lo), exact(hi))
    try:
        return bool(interval.is_subset(continuous_domain(expr, X, interval)))
    except (NotImplementedError, TypeError, ValueError):
        # SymPy cannot decide; the sampling check has already passed.
        return True


def smooth_failures(f: sp.Expr, lo: float, hi: float, *parameters: str) -> list[PredicateFailure]:
    """Check that f has a gradient everywhere on [lo, hi]: its derivative must exist, be finite and
    be continuous there. A corner, as |x| has at 0, has no tangent."""
    derivative = sp.diff(f, X)
    if derivative.has(sp.sign, sp.Heaviside, sp.DiracDelta, sp.Piecewise):
        message = "f has a corner (from abs), so it has no gradient at some points"
        return [failure("domain", "differentiable", message, "expression")]
    points = sample_points(lo, hi) if lo != hi else [exact(lo)]
    bad = failing_samples(derivative, X, points)
    if bad or (lo != hi and not continuous_on(derivative, lo, hi)):
        where = f" at x = {list_points(bad)}" if bad else ""
        message = f"the gradient of f is not defined{where}"
        return [failure("domain", "differentiable", message, "expression", *parameters)]
    return []


def list_points(points, shown: int = 5) -> str:
    text = ", ".join(format_number(p) for p in points[:shown])
    return text + (f" and {len(points) - shown} more points" if len(points) > shown else "")


def inline(tex: str) -> str:
    """Fractions at text size, so a line of the title band keeps a readable size: a displayed
    fraction is so tall that the whole line would be scaled down to fit."""
    return tex.replace(r"\frac", r"\tfrac")


def label_paths(figure: "CurveFigure", *lines: Mobject) -> list[Mobject]:
    """What a label must not sit on: the curve, the given lines, and the two axis lines."""
    return [figure.curve, *lines, figure.axes.x_axis, figure.axes.y_axis]


def point_latex(x: sp.Expr, y: sp.Expr) -> str:
    return rf"({latex_number(x)},\ {latex_number(y)})"


def point_text(x: sp.Expr, y: sp.Expr) -> str:
    return f"({format_number(x)}, {format_number(y)})"


@dataclass
class CurveFigure:
    """Axes, the curve and its equation, laid out in a graph region."""

    axes: Axes
    x_label: Mobject
    y_label: Mobject
    curve: Mobject
    equation: Mobject
    x_range: tuple[float, float, float]
    y_range: tuple[float, float, float]
    plot_box: style.Box
    lower_line: style.Box
    """The second line of the title band, for a read-out or a result."""


def draw_curve(params: CurveParams, f: sp.Expr, region: Region) -> CurveFigure:
    evaluate = sp.lambdify(X, f, "math")
    xs = np.linspace(params.x_min, params.x_max, 121)
    ys = [float(evaluate(x)) for x in xs]
    title_box, plot_box = style.graph_boxes(region)
    upper, lower = style.title_lines(title_box)
    x_range = style.axis_range([params.x_min, params.x_max])
    y_range = style.axis_range(ys)
    axes, x_label, y_label = style.make_axes(x_range, y_range, plot_box)
    curve = axes.plot(
        lambda x: float(evaluate(x)),
        x_range=[params.x_min, params.x_max],
        color=style.CURVE_COLOUR,
    )
    equation = style.fit_inside(
        MathTex("y = " + inline(written_latex(params.expression)), font_size=style.FONT_SIZE),
        upper,
    )
    return CurveFigure(axes, x_label, y_label, curve, equation, x_range, y_range, plot_box, lower)
