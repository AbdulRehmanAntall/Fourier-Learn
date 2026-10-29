"""ParametricCurve: a curve x = f(t), y = g(t) traced as t increases, its gradient
dy/dx = (dy/dt) ÷ (dx/dt), and the tangent (or normal) at a value of t (9709 2.4, 3.4).

As t changes, the point (f(t), g(t)) moves and draws the curve. Over a small change in t, x
changes by about (dx/dt)δt and y by about (dy/dt)δt, so the gradient is their ratio. At t = t₀
that gives the point and the gradient, then the tangent y − y₁ = m(x − x₁); the normal has
gradient −1/m. SymPy differentiates and evaluates everything exactly.
"""

from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import Dot, ValueTracker, VMobject, always_redraw
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import label, make_plot, place_label, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    exact,
    failing_samples,
    format_sf,
    format_value,
    is_simple_exact,
    latex_value,
    parse_expression,
    sample_points,
    tidy_latex,
    written_latex,
)

T = sp.Symbol("t", real=True)
X, Y = sp.symbols("x y", real=True)
Parameter = Annotated[float, Field(ge=-20, le=20)]


class ParametricCurveParams(PrimitiveParams):
    x: str = Field(min_length=1, max_length=80, description="x in terms of t, e.g. t**2")
    y: str = Field(min_length=1, max_length=80, description="y in terms of t, e.g. 2*t")
    t_min: Parameter
    t_max: Parameter
    t0: Parameter = Field(description="The value of t at the point of interest")
    line: Literal["tangent", "normal"] = "tangent"


class ParametricCurve(StagedPrimitive[ParametricCurveParams]):
    primitive_id = "ParametricCurve"
    version = "1"
    topic = "Differentiation"
    params_model = ParametricCurveParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[("axes", "*"), ("curve", "*"), ("line", "*"), ("point", "*")],
    )

    def default_params(self) -> ParametricCurveParams:
        return ParametricCurveParams(x="t**2", y="2*t", t_min=-2, t_max=2, t0=1)

    def validate(self, params: ParametricCurveParams) -> list[PredicateFailure]:
        try:
            fx = parse_expression(params.x, {"t"})
            fy = parse_expression(params.y, {"t"})
        except ExpressionError as error:
            return [_failure("parsing", "expression_parses", str(error), "x", "y")]
        if params.t_min >= params.t_max:
            return [_failure("consistency", "interval_ordered", "t_min must be below t_max")]
        if not params.t_min <= params.t0 <= params.t_max:
            return [
                _failure("consistency", "point_on_curve", "t0 must lie in the range of t", "t0")
            ]
        points = sample_points(params.t_min, params.t_max)
        if failing_samples(fx, T, points) or failing_samples(fy, T, points):
            message = "x and y must be real and finite for every t in the range"
            return [_failure("domain", "real_and_finite", message, "x", "y")]
        c = _Curve(params)
        if c.dxdt0 == 0:
            message = "dx/dt is 0 there: the tangent is vertical; choose another t0"
            return [_failure("consistency", "gradient_defined", message, "t0")]
        if params.line == "normal" and c.m == 0:
            message = "the tangent is flat there, so the normal is vertical; choose another t0"
            return [_failure("consistency", "gradient_defined", message, "t0")]
        return []

    def computed_values(self, params: ParametricCurveParams) -> dict[str, str]:
        c = _Curve(params)
        return {
            "dy_dx": str(c.dydx),
            "point": f"({format_value(c.x0)}, {format_value(c.y0)})",
            "gradient": format_value(c.m),
            "line": f"y = {c.line_expr}",
        }

    def build(self, params: ParametricCurveParams, level):
        c = _Curve(params)
        ts = np.linspace(params.t_min, params.t_max, 300)
        xs = [c.fx(t) for t in ts]
        ys = [c.fy(t) for t in ts]
        plot = make_plot(style.GRAPH_REGION, xs, ys, equal=True)
        traced = VMobject(color=style.CURVE_COLOUR, stroke_width=4)
        traced.set_points_as_corners([plot.point(x, y) for x, y in zip(xs, ys, strict=True)])
        point = plot.point(float(c.x0), float(c.y0))
        slope = float(c.line_slope)
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "title": text_line(
                rf"x = {written_latex(params.x)},\quad y = {written_latex(params.y)}", plot.upper
            ),
            "curve": traced,
            "point": Dot(point, color=style.POINT_COLOUR),
            "line": style.line_in_axes(
                plot.axes,
                (float(c.x0), float(c.y0)),
                slope,
                plot.x_range,
                plot.y_range,
                color=style.TANGENT_COLOUR,
                stroke_width=3,
            ),
            "answer": text_line(rf"y = {c.line_latex()}", plot.lower, colour=style.TANGENT_COLOUR),
        }
        parts["point_label"] = place_label(
            label(
                rf"t = {latex_value(c.t0)}:\ ({c.value(c.x0)},\ {c.value(c.y0)})",
                colour=style.POINT_COLOUR,
                size=26,
            ),
            point,
            plot.plot_box,
            plot.obstacles(),
            [traced, parts["line"], *plot.axis_lines()],
            wide=True,
        )
        rows = c.rows()
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], box, size=30, colours=[col for _, col in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def trace(self, scene, parts, level, run_time, min_run_time):
        """Draw the curve as t increases, a dot riding along its end."""
        tracker = ValueTracker(0.0)
        full = parts["curve"]
        rider = always_redraw(
            lambda: Dot(
                full.point_from_proportion(max(tracker.get_value(), 1e-4)),
                color=style.HIGHLIGHT_COLOUR,
            )
        )
        partial = always_redraw(
            lambda: full.copy().pointwise_become_partial(full, 0, max(tracker.get_value(), 1e-4))
        )
        scene.add(partial, rider)
        animation = max(min_run_time, 0.8 * run_time)
        scene.play(tracker.animate.set_value(1.0), run_time=animation, rate_func=lambda u: u)
        scene.remove(partial, rider)
        scene.add(full)
        scene.wait(run_time - animation)

    def stages(self, params: ParametricCurveParams, level) -> list[Stage]:
        name = params.line
        steps = [
            stage("axes", "Draw the axes", 1.5, ["axes", "x_label", "y_label", "title"]),
            stage(
                "trace",
                "As t increases, the point x of t, y of t moves and draws the curve",
                3.5,
                ["curve"],
                motion="trace",
            ),
            stage(
                "derivatives",
                "Differentiate x and y with respect to t",
                3.0,
                ["row_1", "row_2"],
            ),
            stage(
                "gradient",
                "The gradient is d y by d t divided by d x by d t",
                3.0,
                ["row_3"],
                emphasise=["row_3"],
            ),
            stage(
                "point",
                f"At t equals {format_value(_Curve(params).t0)}, find the point and the gradient",
                3.0,
                ["point", "point_label", "row_4", "row_5"],
                emphasise=["point"],
            ),
            stage(
                "line",
                f"Then the {name}"
                + (": its gradient is minus 1 over m" if name == "normal" else ""),
                3.0,
                ["line", "row_6", "answer"],
                emphasise=["answer"],
            ),
        ]

        def standard(s):
            return [
                s[0],
                s[1],
                combine("gradient", "dy by dt over dx by dt", 3.5, s[2], s[3]),
                *s[4:],
            ]

        def concise(s):
            return [
                s[0],
                s[1],
                combine("gradient", "dy by dt over dx by dt", 3.5, s[2], s[3]),
                combine("line", f"The point, its gradient and the {name}", 4.0, s[4], s[5]),
            ]

        return by_level(level, steps, standard, concise)


class _Curve:
    def __init__(self, params: ParametricCurveParams):
        self.params = params
        self.x = sp.nsimplify(parse_expression(params.x, {"t"}), rational=True)
        self.y = sp.nsimplify(parse_expression(params.y, {"t"}), rational=True)
        self.fx = sp.lambdify(T, self.x, "math")
        self.fy = sp.lambdify(T, self.y, "math")
        self.dxdt, self.dydt = sp.diff(self.x, T), sp.diff(self.y, T)
        self.dydx = sp.simplify(self.dydt / self.dxdt) if self.dxdt != 0 else sp.zoo
        self.t0 = exact(params.t0)
        self.x0 = sp.nsimplify(self.x.subs(T, self.t0))
        self.y0 = sp.nsimplify(self.y.subs(T, self.t0))
        self.dxdt0 = sp.nsimplify(self.dxdt.subs(T, self.t0))
        dydt0 = sp.nsimplify(self.dydt.subs(T, self.t0))
        self.m = sp.nsimplify(dydt0 / self.dxdt0) if self.dxdt0 != 0 else sp.zoo
        self.line_slope = (
            self.m
            if params.line == "tangent"
            else (-1 / self.m if self.m not in (0, sp.zoo) else sp.zoo)
        )
        self.line_expr = (
            sp.expand(self.line_slope * (X - self.x0) + self.y0)
            if self.line_slope != sp.zoo
            else sp.nan
        )
        # values that are not simple exact numbers (sin 0.785 ...) are worked to 3 s.f.
        self.decimal = not all(
            v == sp.zoo or is_simple_exact(v) for v in (self.x0, self.y0, self.m)
        )

    def value(self, v) -> str:
        return format_sf(sp.N(v)) if self.decimal else latex_value(v)

    def line_latex(self) -> str:
        """The line as y = mx + c, its numbers exact or to 3 s.f."""
        if not self.decimal:
            return tidy_latex(self.line_expr)
        m = sp.N(self.line_slope)
        c = sp.N(self.y0 - self.line_slope * self.x0)
        text = f"{format_sf(m)}x"
        if abs(c) > 1e-12:
            text += f" {'+' if c > 0 else '-'} {format_sf(abs(c))}"
        return text

    def rows(self) -> list[tuple[str, object]]:
        t0 = latex_value(self.t0)
        rows = [
            (
                rf"\frac{{dx}}{{dt}} = {sp.latex(self.dxdt)},\ "
                rf"\frac{{dy}}{{dt}} = {sp.latex(self.dydt)}",
                None,
            ),
            (r"\frac{dy}{dx} = \frac{dy}{dt} \div \frac{dx}{dt}", None),
            (rf"\frac{{dy}}{{dx}} = {sp.latex(self.dydx)}", style.RISE_COLOUR),
            (
                rf"t = {t0}:\ x = {self.value(self.x0)},\ y = {self.value(self.y0)}",
                style.POINT_COLOUR,
            ),
            (rf"m = {self.value(self.m)}", None),
        ]
        if self.params.line == "tangent":
            rows.append(
                (
                    rf"{_minus('y', self.value(self.y0))} = {self.value(self.m)}"
                    rf"\left({_minus('x', self.value(self.x0))}\right)",
                    style.TANGENT_COLOUR,
                )
            )
        else:
            rows.append(
                (
                    rf"\text{{normal: }}m = {self.value(self.line_slope)},\ "
                    rf"y = {self.line_latex()}",
                    style.TANGENT_COLOUR,
                )
            )
        return rows


def _minus(name: str, value: str) -> str:
    """y - 2, y + 1 (not y - (-1)), or y alone for 0."""
    if value == "0":
        return name
    return f"{name} + {value[1:]}" if value.startswith("-") else f"{name} - {value}"


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
