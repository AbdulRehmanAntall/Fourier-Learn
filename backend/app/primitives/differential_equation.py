"""DifferentialEquation: a first order differential equation dy/dx = f(x)g(y) solved by separating
the variables, with its slope field, the family of solutions and the particular solution through
a given point (9709 3.8).

The equation gives the gradient at every point, drawn as a short line segment: the slope
field. Every solution curve follows the segments. Separating gives ∫ dy/g(y) = ∫ f(x) dx, so
integrating both sides gives the general solution with one constant c: a family of curves. The
initial condition picks out one of them. SymPy separates, integrates and solves exactly; the
curves are drawn by stepping along the slope field (Runge-Kutta), so the picture and the
algebra are checked against each other.
"""

import math
from typing import Annotated

import numpy as np
import sympy as sp
from manim import Dot, Line, VGroup, VMobject
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import label, make_plot, place_label, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    exact,
    is_elementary_integral,
    latex_value,
    parse_expression,
    written_latex,
)

X, Y = sp.symbols("x y", real=True)
Coordinate = Annotated[float, Field(ge=-20, le=20)]
GRID = 13
FAMILY = 4


class DifferentialEquationParams(PrimitiveParams):
    gradient: str = Field(
        min_length=1, max_length=100, description='dy/dx in x and y, separable, e.g. "x*y"'
    )
    point: tuple[Coordinate, Coordinate] = Field(description="The initial condition (x, y)")
    x_min: Coordinate
    x_max: Coordinate


class DifferentialEquation(StagedPrimitive[DifferentialEquationParams]):
    primitive_id = "DifferentialEquation"
    version = "1"
    topic = "Differential equations"
    params_model = DifferentialEquationParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[
            ("axes", "*"),
            ("field", "*"),
            ("family", "*"),
            ("solution", "*"),
            ("point", "*"),
        ],
    )

    def default_params(self) -> DifferentialEquationParams:
        return DifferentialEquationParams(gradient="x*y", point=(0, 1), x_min=-2, x_max=2)

    def validate(self, params: DifferentialEquationParams) -> list[PredicateFailure]:
        try:
            rhs = parse_expression(params.gradient, {"x", "y"})
        except ExpressionError as error:
            return [_failure("parsing", "expression_parses", str(error), "gradient")]
        if params.x_min >= params.x_max:
            return [_failure("consistency", "interval_ordered", "x_min must be below x_max")]
        if not params.x_min <= params.point[0] <= params.x_max:
            return [
                _failure("consistency", "point_in_interval", "the point must be in the interval")
            ]
        parts = sp.separatevars(sp.nsimplify(rhs, rational=True), symbols=[X, Y], dict=True)
        if parts is None or not rhs.has(Y):
            message = "dy/dx must be a function of x times a function of y, involving y"
            return [_failure("consistency", "separable", message, "gradient")]
        try:
            solved = _Solution(params)
        except _Unsolvable as problem:
            return [_failure("consistency", "solvable", str(problem), "gradient")]
        if not solved.curve_ok:
            message = "the solution through the point is not defined across the interval"
            return [_failure("domain", "real_and_finite", message, "x_min", "x_max")]
        return []

    def computed_values(self, params: DifferentialEquationParams) -> dict[str, str]:
        s = _Solution(params)
        values = {"general": f"{s.left} = {s.right} + c", "c": str(s.c)}
        if s.explicit is not None:
            values["particular"] = f"y = {s.explicit}"
        return values

    def build(self, params: DifferentialEquationParams, level):
        s = _Solution(params)
        xs, ys = s.curve
        finite = [y for y in ys if math.isfinite(y)]
        lo, hi = min(finite), max(finite)
        spread = max(hi - lo, 2.0)
        y_lo, y_hi = lo - 0.4 * spread, hi + 0.4 * spread
        plot = make_plot(style.GRAPH_REGION, [params.x_min, params.x_max], [y_lo, y_hi])
        y_lo, y_hi = plot.y_range[0], plot.y_range[1]
        f = s.numeric
        field = VGroup()
        unit_x = plot.point(1, 0)[0] - plot.point(0, 0)[0]
        unit_y = plot.point(0, 1)[1] - plot.point(0, 0)[1]
        size = 0.18
        for gx in np.linspace(plot.x_range[0], plot.x_range[1], GRID):
            for gy in np.linspace(y_lo, y_hi, GRID):
                m = f(gx, gy)
                if not math.isfinite(m):
                    continue
                direction = np.array([unit_x, m * unit_y, 0.0])
                direction = direction / np.linalg.norm(direction) * size
                centre = plot.point(gx, gy)
                field.add(
                    Line(
                        centre - direction,
                        centre + direction,
                        stroke_width=2,
                        color=style.SECANT_COLOUR,
                    )
                )
        family = VGroup()
        for k in range(1, FAMILY + 1):
            for start_y in (s.y0 + k * spread * 0.35, s.y0 - k * spread * 0.35):
                cx, cy = _integrate(f, s.x0, start_y, params.x_min, params.x_max)
                family.add(_path(plot, cx, cy, style.CURVE_COLOUR, 2, y_lo, y_hi))
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "title": text_line(
                rf"\frac{{dy}}{{dx}} = {written_latex(params.gradient)}", plot.upper
            ),
            "field": field,
            "family": family,
            "solution": _path(plot, xs, ys, style.TANGENT_COLOUR, 5, y_lo, y_hi),
            "point": Dot(plot.point(float(s.x0), float(s.y0)), color=style.POINT_COLOUR),
            "answer": text_line(s.answer_latex(), plot.lower, colour=style.TANGENT_COLOUR),
        }
        parts["point_label"] = place_label(
            label(rf"({latex_value(s.x0)},\ {latex_value(s.y0)})", colour=style.POINT_COLOUR),
            plot.point(float(s.x0), float(s.y0)),
            plot.plot_box,
            plot.obstacles(),
            [*plot.axis_lines()],
            wide=True,
        )
        rows = s.rows()
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: DifferentialEquationParams, level) -> list[Stage]:
        n = len(_Solution(params).rows())
        steps = [
            stage(
                "field",
                "The equation gives the gradient at every point: the slope field",
                3.5,
                ["axes", "x_label", "y_label", "title", "field", "row_1"],
            ),
            stage(
                "separate",
                "Separate the variables: everything in y with d y, everything in x with d x",
                3.5,
                ["row_2"],
                emphasise=["row_2"],
            ),
            stage(
                "integrate",
                "Integrate both sides: one constant c gives a whole family of solutions",
                3.5,
                ["row_3", "family"],
            ),
            stage(
                "condition",
                "The initial condition picks out one curve: substitute it to find c",
                3.5,
                ["point", "point_label", "row_4"],
                emphasise=["point"],
            ),
            stage(
                "particular",
                "The particular solution, following the slope field through the point",
                3.5,
                ["solution", *[f"row_{i}" for i in range(5, n + 1)], "answer"],
                hide=["family"],
                emphasise=["answer"],
            ),
        ]

        def standard(s):
            return [
                s[0],
                combine("integrate", "Separate the variables and integrate", 4.0, s[1], s[2]),
                *s[3:],
            ]

        def concise(s):
            return [
                s[0],
                combine("integrate", "Separate the variables and integrate", 4.0, s[1], s[2]),
                combine(
                    "particular", "The point fixes c: the particular solution", 4.0, s[3], s[4]
                ),
            ]

        return by_level(level, steps, standard, concise)


class _Unsolvable(ValueError):
    pass


def _integrate(f, x0, y0, x_min, x_max, steps=200):
    """y along the solution through (x0, y0), by fourth order Runge-Kutta, both ways."""

    def run(direction):
        xs, ys = [x0], [y0]
        end = x_max if direction > 0 else x_min
        h = (end - x0) / steps
        x, y = x0, y0
        for _ in range(steps):
            if not math.isfinite(y) or abs(y) > 1e6:
                break
            k1 = f(x, y)
            k2 = f(x + h / 2, y + h * k1 / 2)
            k3 = f(x + h / 2, y + h * k2 / 2)
            k4 = f(x + h, y + h * k3)
            step = h * (k1 + 2 * k2 + 2 * k3 + k4) / 6
            if not math.isfinite(step):
                break
            y += step
            x += h
            xs.append(x)
            ys.append(y)
        return xs, ys

    lx, ly = run(-1)
    rx, ry = run(1)
    return lx[::-1] + rx[1:], ly[::-1] + ry[1:]


def _path(plot, xs, ys, colour, width, y_lo, y_hi) -> VMobject:
    path = VMobject(stroke_width=width, color=colour)
    points = [
        plot.point(x, y)
        for x, y in zip(xs, ys, strict=True)
        if math.isfinite(y) and y_lo <= y <= y_hi
    ]
    if len(points) < 2:
        points = [plot.point(xs[0], max(min(ys[0], y_hi), y_lo))] * 2
    path.set_points_as_corners(points)
    return path


class _Solution:
    def __init__(self, params: DifferentialEquationParams):
        self.params = params
        self.rhs = sp.nsimplify(parse_expression(params.gradient, {"x", "y"}), rational=True)
        parts = sp.separatevars(self.rhs, symbols=[X, Y], dict=True)
        self.fx = sp.simplify(parts["coeff"] * parts[X])
        self.gy = sp.simplify(parts[Y])
        self.x0, self.y0 = exact(params.point[0]), exact(params.point[1])
        if self.gy.subs(Y, self.y0) == 0:
            raise _Unsolvable("y is constant through that point (g(y) = 0): choose another point")
        left = sp.integrate(1 / self.gy, Y, manual=True)
        right = sp.integrate(self.fx, X, manual=True)
        if not (is_elementary_integral(left) and is_elementary_integral(right)):
            raise _Unsolvable("one side cannot be integrated in a simple form")
        self.left, self.right = left, right
        self.c = sp.nsimplify(sp.simplify(left.subs(Y, self.y0) - right.subs(X, self.x0)))
        self.explicit = None
        try:
            found = sp.solve(sp.Eq(left, right + self.c), Y)
        except (NotImplementedError, ValueError):
            found = []
        for candidate in found:
            if sp.simplify(candidate.subs(X, self.x0) - self.y0) == 0:
                self.explicit = sp.simplify(candidate)
                break
        numeric = sp.lambdify((X, Y), self.rhs, "math")

        def f(x, y):
            try:
                return float(numeric(x, y))
            except (ValueError, ZeroDivisionError, OverflowError, TypeError):
                return math.nan

        self.numeric = f
        self.curve = _integrate(f, float(self.x0), float(self.y0), params.x_min, params.x_max)
        span = params.x_max - params.x_min
        reached = self.curve[0][-1] - self.curve[0][0]
        self.curve_ok = reached >= 0.98 * span

    def answer_latex(self) -> str:
        if self.explicit is not None:
            return rf"y = {_tex(self.explicit)}"
        return rf"{_tex(self.left)} = {_tex(self.right)} {_signed(self.c)}"

    def rows(self) -> list[tuple[str, object]]:
        rows = [
            (rf"\frac{{dy}}{{dx}} = {written_latex(self.params.gradient)}", None),
            (rf"\int {_tex(1 / self.gy)}\,dy = \int {_tex(self.fx)}\,dx", style.RISE_COLOUR),
            (rf"{_tex(self.left)} = {_tex(self.right)} + c", None),
            (
                rf"x = {latex_value(self.x0)},\ y = {latex_value(self.y0)}:\ c = {_tex(self.c)}",
                style.POINT_COLOUR,
            ),
            (rf"{_tex(self.left)} = {_tex(self.right)} {_signed(self.c)}", None),
        ]
        if self.explicit is not None:
            rows.append((rf"y = {_tex(self.explicit)}", style.TANGENT_COLOUR))
        return rows


def _tex(expr) -> str:
    return sp.latex(expr, ln_notation=True, inv_trig_style="power")


def _signed(c) -> str:
    if c == 0:
        return ""
    text = _tex(c)
    return f"- {text[1:]}" if text.startswith("-") else f"+ {text}"


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
