"""AreaBetweenCurves: the area enclosed between two graphs, as the integral of the upper minus
the lower (AM 14.10 to 14.13; PRIMITIVES.md #57, between a line and a curve or two curves).

The limits are where the graphs meet, unless they are given. Rectangles between the graphs show
the area as a sum of thin strips of height (upper - lower), which the integral adds up. Every
value is computed exactly by SymPy where it can be.
"""

from typing import Annotated

import numpy as np
import sympy as sp
from manim import Dot, Polygon, Rectangle, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.analysis import samples, zeros
from app.primitives.plotting import curve, label, make_plot, place_label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    exact,
    format_value,
    latex_value,
    parse_expression,
    tidy_latex,
    written_latex,
)

X = sp.Symbol("x", real=True)
Coordinate = Annotated[float, Field(ge=-20, le=20)]
STRIPS = 10


class AreaBetweenCurvesParams(PrimitiveParams):
    upper: str = Field(min_length=1, max_length=120, description="The upper graph, e.g. 4 - x**2")
    lower: str = Field(min_length=1, max_length=120, description="The lower graph, e.g. x + 2")
    lower_limit: Coordinate | None = Field(
        default=None, description="Left limit; where the graphs meet if omitted"
    )
    upper_limit: Coordinate | None = Field(
        default=None, description="Right limit; where the graphs meet if omitted"
    )


class AreaBetweenCurves(StagedPrimitive[AreaBetweenCurvesParams]):
    primitive_id = "AreaBetweenCurves"
    version = "1"
    topic = "Introductory calculus"
    params_model = AreaBetweenCurvesParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("axes", "*"),
            ("upper", "*"),
            ("lower", "*"),
            ("region", "*"),
            ("strips", "*"),
            ("meet_*", "*"),
        ],
    )

    def default_params(self) -> AreaBetweenCurvesParams:
        return AreaBetweenCurvesParams(upper="4 - x**2", lower="x + 2")

    def validate(self, params: AreaBetweenCurvesParams) -> list[PredicateFailure]:
        parsed = {}
        for name in ("upper", "lower"):
            try:
                parsed[name] = parse_expression(getattr(params, name), {"x"})
            except ExpressionError as error:
                return [_failure("parsing", "expression_parses", str(error), name)]
        try:
            a, b = _limits(params)
        except _NoLimits as problem:
            return [
                _failure("consistency", "limits_found", str(problem), "lower_limit", "upper_limit")
            ]
        if a >= b:
            return [
                _failure(
                    "consistency",
                    "limits_ordered",
                    "the left limit must be below the right",
                    "lower_limit",
                    "upper_limit",
                )
            ]
        difference = parsed["upper"] - parsed["lower"]
        xs, ys = samples(difference, float(a), float(b), 201)
        if not np.isfinite(ys).all():
            message = "a graph is not real and finite between the limits"
            return [_failure("domain", "real_and_finite", message, "upper", "lower")]
        if (ys[1:-1] < -1e-9).any():
            message = (
                "the 'upper' graph goes below the 'lower' one between the limits; swap them "
                "or split the area at the crossing"
            )
            return [_failure("consistency", "upper_above_lower", message, "upper", "lower")]
        return []

    def computed_values(self, params: AreaBetweenCurvesParams) -> dict[str, str]:
        a, b = _limits(params)
        area = _area(params, a, b)
        return {
            "lower_limit": format_value(a),
            "upper_limit": format_value(b),
            "area": format_value(area),
        }

    def build(self, params: AreaBetweenCurvesParams, level):
        a, b = _limits(params)
        f = sp.nsimplify(parse_expression(params.upper, {"x"}), rational=True)
        g = sp.nsimplify(parse_expression(params.lower, {"x"}), rational=True)
        f_num, g_num = sp.lambdify(X, f, "math"), sp.lambdify(X, g, "math")
        lo, hi = float(a), float(b)
        pad = 0.25 * (hi - lo)
        x_lo, x_hi = lo - pad, hi + pad
        _, fy = samples(f, x_lo, x_hi, 121)
        _, gy = samples(g, x_lo, x_hi, 121)
        values = [v for v in [*fy, *gy] if np.isfinite(v)]
        plot = make_plot(self.layout.region, [x_lo, x_hi], values)
        xs = np.linspace(lo, hi, 80)
        outline = [plot.point(x, f_num(x)) for x in xs] + [
            plot.point(x, g_num(x)) for x in xs[::-1]
        ]
        width = (hi - lo) / STRIPS
        strips = VGroup()
        for k in range(STRIPS):
            x = lo + (k + 0.5) * width
            top, bottom = plot.point(x - width / 2, f_num(x)), plot.point(x + width / 2, g_num(x))
            strip = Rectangle(
                width=abs(top[0] - bottom[0]),
                height=abs(top[1] - bottom[1]),
                stroke_color=style.HIGHLIGHT_COLOUR,
                stroke_width=1.5,
                fill_color=style.AREA_COLOUR,
                fill_opacity=0.35,
            )
            strip.move_to((top + bottom) / 2)
            strips.add(strip)
        area = _area(params, a, b)
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "upper": curve(plot, f_num, x_lo, x_hi),
            "lower": curve(plot, g_num, x_lo, x_hi, colour=style.RUN_COLOUR),
            "region": Polygon(
                *outline,
                stroke_width=0,
                fill_color=style.AREA_COLOUR,
                fill_opacity=style.AREA_OPACITY,
            ),
            "strips": strips,
            "integral": text_line(
                rf"A = \textstyle\int_{{{latex_value(a)}}}^{{{latex_value(b)}}} "
                rf"\left({tidy_latex(f - g)}\right)\,dx",
                plot.upper,
            ),
            "result": text_line(rf"A = {latex_value(area)}", plot.lower),
        }
        obstacles = [*plot.obstacles()]
        paths = [parts["upper"], parts["lower"], *plot.axis_lines()]
        for i, x in enumerate((a, b), start=1):
            point = plot.point(float(x), f_num(float(x)))
            parts[f"meet_{i}"] = Dot(point, color=style.POINT_COLOUR)
            obstacles.append(parts[f"meet_{i}"])
        for name, expr, colour, numeric in (
            ("upper_label", params.upper, style.CURVE_COLOUR, f_num),
            ("lower_label", params.lower, style.RUN_COLOUR, g_num),
        ):
            y = min(max(numeric(x_hi), plot.y_range[0]), plot.y_range[1])
            text = label(f"y = {written_latex(expr)}", colour=colour)
            parts[name] = place_label(
                text, plot.point(x_hi, y), plot.plot_box, obstacles, paths, wide=True
            )
            obstacles.append(text)
        for i, x in enumerate((a, b), start=1):
            text = label(f"x = {latex_value(x)}", colour=style.POINT_COLOUR)
            parts[f"meet_{i}_label"] = place_label(
                text,
                plot.point(float(x), f_num(float(x))),
                plot.plot_box,
                obstacles,
                paths,
                wide=True,
            )
            obstacles.append(text)
        return parts

    def stages(self, params: AreaBetweenCurvesParams, level) -> list[Stage]:
        given = params.lower_limit is not None and params.upper_limit is not None
        limits_words = "Mark the limits" if given else "The limits are where the graphs meet"
        steps = [
            stage("axes", "Draw the axes", 1.5, ["axes", "x_label", "y_label"]),
            stage(
                "graphs",
                "Draw the two graphs",
                2.5,
                ["upper", "lower", "upper_label", "lower_label"],
            ),
            stage(
                "limits",
                limits_words,
                2.0,
                ["meet_1", "meet_2", "meet_1_label", "meet_2_label"],
                emphasise=["meet_1", "meet_2"],
            ),
            stage(
                "strips",
                "Cut the area into thin strips, each upper minus lower high",
                3.0,
                ["strips"],
            ),
            stage(
                "integral",
                "Adding infinitely thin strips is integrating upper minus lower",
                3.0,
                ["integral"],
                hide=["strips"],
            ),
            stage(
                "result",
                "Shade the area and evaluate the integral",
                3.0,
                ["region", "result"],
                emphasise=["result"],
            ),
        ]

        def standard(s):
            return [
                combine("graphs", "Draw the two graphs and where they meet", 3.0, *s[:3]),
                s[3],
                combine("result", "Integrate upper minus lower between the limits", 3.5, *s[4:]),
            ]

        def concise(s):
            return [
                combine("graphs", "The two graphs and their limits", 3.0, *s[:3]),
                combine("result", "The area is the integral of upper minus lower", 3.5, *s[3:]),
            ]

        return by_level(level, steps, standard, concise)


class _NoLimits(ValueError):
    pass


def _limits(params: AreaBetweenCurvesParams) -> tuple[sp.Expr, sp.Expr]:
    if params.lower_limit is not None and params.upper_limit is not None:
        return exact(params.lower_limit), exact(params.upper_limit)
    f = sp.nsimplify(parse_expression(params.upper, {"x"}), rational=True)
    g = sp.nsimplify(parse_expression(params.lower, {"x"}), rational=True)
    meets = zeros(sp.simplify(f - g), -20, 20, [])
    if params.lower_limit is not None:
        meets = [exact(params.lower_limit), *[m for m in meets if m > params.lower_limit]]
    if params.upper_limit is not None:
        meets = [*[m for m in meets if m < params.upper_limit], exact(params.upper_limit)]
    if len(meets) < 2:
        raise _NoLimits("the graphs do not meet twice; give lower_limit and upper_limit")
    return meets[0], meets[1]


def _area(params: AreaBetweenCurvesParams, a, b) -> sp.Expr:
    f = sp.nsimplify(parse_expression(params.upper, {"x"}), rational=True)
    g = sp.nsimplify(parse_expression(params.lower, {"x"}), rational=True)
    exact_area = sp.integrate(f - g, (X, a, b))
    if exact_area.has(sp.Integral):
        return sp.Float(sp.N(sp.Integral(f - g, (X, a, b))))
    return sp.nsimplify(sp.simplify(exact_area))


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
