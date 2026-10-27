"""DerivativePanels: y = f(x) above and its gradient function dy/dx below, on the same x-scale,
with a cursor that moves through both (AM 14.6, 14.9; PRIMITIVES.md #53).

Where f increases, f' is positive; where f decreases, f' is negative; at a stationary point f'
is zero, and the sign of f' either side says whether it is a maximum or a minimum (the first
derivative test). Both curves are coloured by the sign of f' to show this, and each stationary
point is joined to the zero of f' below it. Every value is computed by SymPy.
"""

from typing import Annotated

import numpy as np
import sympy as sp
from manim import RIGHT, DashedLine, Dot, Line, MathTex, ValueTracker, VGroup, always_redraw
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams, Region
from app.primitives import style
from app.primitives.analysis import zeros
from app.primitives.plotting import curve, label, make_plot, place_label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    format_value,
    latex_value,
    parse_expression,
    tidy_latex,
    written_latex,
)

X = sp.Symbol("x", real=True)
Coordinate = Annotated[float, Field(ge=-20, le=20)]
TOP = Region(x_min=0.0, x_max=0.62, y_min=0.47, y_max=1.0)
BOTTOM = Region(x_min=0.0, x_max=0.62, y_min=0.0, y_max=0.47)
UP_COLOUR = style.RISE_COLOUR
DOWN_COLOUR = style.TANGENT_COLOUR


class DerivativePanelsParams(PrimitiveParams):
    expression: str = Field(min_length=1, max_length=120, description="f(x), e.g. x**3 - 3*x")
    x_min: Coordinate
    x_max: Coordinate


class DerivativePanels(StagedPrimitive[DerivativePanelsParams]):
    primitive_id = "DerivativePanels"
    version = "1"
    topic = "Introductory calculus"
    params_model = DerivativePanelsParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("axes*", "*"),
            ("curve*", "*"),
            ("connectors", "*"),
            ("stationary_*", "stationary_*"),
            ("zero_*", "zero_*"),
        ],
    )

    def default_params(self) -> DerivativePanelsParams:
        return DerivativePanelsParams(expression="x**3 - 3*x", x_min=-2.5, x_max=2.5)

    def validate(self, params: DerivativePanelsParams) -> list[PredicateFailure]:
        try:
            f = parse_expression(params.expression, {"x"})
        except ExpressionError as error:
            return [_failure("parsing", "expression_parses", str(error), "expression")]
        if params.x_min >= params.x_max:
            return [
                _failure("consistency", "interval_ordered", "x_min must be below x_max", "x_min")
            ]
        from app.primitives.curves import CurveParams, check_curve, smooth_failures

        _, failures = check_curve(
            CurveParams(expression=params.expression, x_min=params.x_min, x_max=params.x_max)
        )
        if failures:
            return failures
        failures = smooth_failures(sp.nsimplify(f, rational=True), params.x_min, params.x_max)
        if failures:
            return failures
        if len(_Analysis(params).stationary) > 4:
            message = "more than 4 stationary points; narrow the interval"
            return [_failure("consistency", "few_stationary_points", message, "x_min", "x_max")]
        return []

    def computed_values(self, params: DerivativePanelsParams) -> dict[str, str]:
        a = _Analysis(params)
        values = {"derivative": str(a.derivative)}
        for i, (x, y, kind) in enumerate(a.stationary, start=1):
            values[f"stationary_{i}"] = f"({format_value(x)}, {format_value(y)})"
            values[f"stationary_{i}_kind"] = kind
        return values

    def build(self, params: DerivativePanelsParams, level):
        a = _Analysis(params)
        lo, hi = params.x_min, params.x_max
        xs = np.linspace(lo, hi, 121)
        top = make_plot(TOP, [lo, hi], [a.f_num(x) for x in xs], y_ticks=3)
        bottom = make_plot(
            BOTTOM,
            [lo, hi],
            [a.d_num(x) for x in xs],
            y_label=r"\tfrac{dy}{dx}",
            y_ticks=3,
            title=False,
        )
        parts = {
            "axes_top": top.axes,
            "axes_top_labels": VGroup(top.x_label, top.y_label),
            "axes_bottom": bottom.axes,
            "axes_bottom_labels": VGroup(bottom.x_label, bottom.y_label),
            "equation": text_line(f"y = {written_latex(params.expression)}", top.upper),
            "derivative": text_line(rf"\frac{{dy}}{{dx}} = {tidy_latex(a.derivative)}", top.lower),
            "curve_f": curve(top, a.f_num, lo, hi),
            "curve_d": curve(bottom, a.d_num, lo, hi, colour=style.SECANT_COLOUR),
        }
        # The same curves coloured by the sign of f': green where f increases, red where it
        # decreases.
        cuts = [lo, *[float(x) for x, _, _ in a.stationary], hi]
        coloured_f, coloured_d = VGroup(), VGroup()
        for left, right in zip(cuts, cuts[1:], strict=False):
            if right - left < 1e-9:
                continue
            colour = UP_COLOUR if a.d_num((left + right) / 2) > 0 else DOWN_COLOUR
            coloured_f.add(*curve(top, a.f_num, left, right, colour=colour))
            coloured_d.add(*curve(bottom, a.d_num, left, right, colour=colour))
        parts["curve_f_coloured"] = coloured_f
        parts["curve_d_coloured"] = coloured_d
        key = VGroup(
            MathTex(r"\text{up: } \tfrac{dy}{dx} > 0", font_size=30, color=UP_COLOUR),
            MathTex(r"\text{down: } \tfrac{dy}{dx} < 0", font_size=30, color=DOWN_COLOUR),
        ).arrange(RIGHT, buff=0.6)
        parts["key"] = style.fit_inside(key, top.lower)

        obstacles_top = [*top.obstacles()]
        obstacles_bottom = [*bottom.obstacles()]
        paths_top = [parts["curve_f"], *top.axis_lines()]
        paths_bottom = [parts["curve_d"], *bottom.axis_lines()]
        connectors = VGroup()
        for i, (x, y, _) in enumerate(a.stationary, start=1):
            point = top.point(float(x), float(y))
            zero = bottom.point(float(x), 0)
            parts[f"stationary_{i}"] = Dot(point, color=style.POINT_COLOUR)
            parts[f"zero_{i}"] = Dot(zero, color=style.POINT_COLOUR)
            obstacles_top.append(parts[f"stationary_{i}"])
            obstacles_bottom.append(parts[f"zero_{i}"])
            connectors.add(DashedLine(point, zero, color=style.POINT_COLOUR, stroke_width=2))
        parts["connectors"] = connectors
        paths_top.append(connectors)
        paths_bottom.append(connectors)
        for i, (x, y, kind) in enumerate(a.stationary, start=1):
            text = label(
                rf"\text{{{'max' if kind == 'maximum' else 'min'}}}\ "
                rf"({latex_value(x)},\ {latex_value(y)})",
                colour=style.POINT_COLOUR,
            )
            parts[f"stationary_{i}_label"] = place_label(
                text,
                top.point(float(x), float(y)),
                top.plot_box,
                obstacles_top,
                paths_top,
                wide=True,
            )
            obstacles_top.append(text)
        self._sweep = (top, bottom, a, lo, hi)
        return parts

    def sweep(self, scene, parts, level, run_time, min_run_time):
        """A cursor moves from left to right through both graphs, with a dot on each curve."""
        top, bottom, a, lo, hi = self._sweep
        tracker = ValueTracker(lo)

        def cursor():
            x = tracker.get_value()
            return VGroup(
                Line(
                    top.point(x, top.y_range[1]),
                    bottom.point(x, bottom.y_range[0]),
                    color=style.HIGHLIGHT_COLOUR,
                    stroke_width=2,
                ),
                Dot(top.point(x, a.f_num(x)), color=style.HIGHLIGHT_COLOUR),
                Dot(bottom.point(x, a.d_num(x)), color=style.HIGHLIGHT_COLOUR),
            )

        moving = always_redraw(cursor)
        scene.add(moving)
        hold = min(0.15, 0.2 * run_time)
        animation_time = min(max(min_run_time, 0.6 * run_time), run_time - hold)
        scene.play(tracker.animate.set_value(hi), run_time=animation_time)
        scene.remove(moving)
        scene.wait(run_time - animation_time)

    def stages(self, params: DerivativePanelsParams, level) -> list[Stage]:
        count = len(_Analysis(params).stationary)
        points = [
            n
            for i in range(1, count + 1)
            for n in (f"stationary_{i}", f"zero_{i}", f"stationary_{i}_label")
        ]
        steps = [
            stage(
                "graph",
                "Here is the curve",
                2.0,
                ["axes_top", "axes_top_labels", "equation", "curve_f"],
            ),
            stage(
                "derivative",
                "Below it, its gradient function on the same x-scale",
                2.5,
                ["axes_bottom", "axes_bottom_labels", "derivative", "curve_d"],
            ),
            stage(
                "sweep",
                "Follow both graphs from left to right: the gradient of the top curve "
                "is the height of the bottom one",
                4.0,
                motion="sweep",
            ),
            stage(
                "colour",
                "Where the curve goes up, dy by dx is positive; where it goes down, negative",
                3.0,
                morph=[
                    ("curve_f", "curve_f_coloured"),
                    ("curve_d", "curve_d_coloured"),
                    ("derivative", "key"),
                ],
            ),
        ]
        if count:
            steps.append(
                stage(
                    "stationary",
                    "At each turning point dy by dx is zero: up then down is a "
                    "maximum, down then up a minimum",
                    3.5,
                    [*points, "connectors"],
                    emphasise=[f"stationary_{i}" for i in range(1, count + 1)],
                )
            )

        def standard(s):
            return [
                combine(
                    "graphs", "The curve and, below it, its gradient function", 3.0, s[0], s[1]
                ),
                s[2],
                combine(
                    "signs",
                    "The sign of dy by dx shows where the curve rises, falls and turns",
                    4.0,
                    *s[3:],
                ),
            ]

        def concise(s):
            return [
                combine("graphs", "The curve and its gradient function", 3.0, s[0], s[1]),
                combine("signs", "Rising, falling and turning points", 4.0, *s[3:]),
            ]

        return by_level(level, steps, standard, concise)


class _Analysis:
    def __init__(self, params: DerivativePanelsParams):
        self.f = sp.nsimplify(parse_expression(params.expression, {"x"}), rational=True)
        self.derivative = sp.simplify(sp.diff(self.f, X))
        self.f_num = sp.lambdify(X, self.f, "math")
        self.d_num = sp.lambdify(X, self.derivative, "math")
        self.stationary = []
        for x in zeros(self.derivative, params.x_min, params.x_max, []):
            if not params.x_min < float(x) < params.x_max:
                continue
            left = self.d_num(float(x) - 1e-4)
            right = self.d_num(float(x) + 1e-4)
            kind = "maximum" if left > 0 > right else ("minimum" if left < 0 < right else None)
            if kind:
                y = self.f.subs(X, x) if not isinstance(x, float) else self.f_num(x)
                self.stationary.append(
                    (x, sp.nsimplify(y) if not isinstance(y, float) else y, kind)
                )


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
