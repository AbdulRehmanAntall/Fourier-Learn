"""TrapeziumRule: a definite integral estimated by n trapezia of equal width, and whether the
estimate is too big or too small from the shape of the curve (9709 2.5, 3.5).

With width h = (b − a)/n and heights y₀, ..., yₙ, the trapezia add to
½h[y₀ + 2(y₁ + ... + yₙ₋₁) + yₙ]. Where the curve bends upwards (f'' > 0) every trapezium's top
lies above the curve, so the estimate is too big; where it bends downwards, too small. SymPy
checks the sign of f'' across the interval, and gives the exact value of the integral where it
can, so the error can be seen. Heights are shown to 4 significant figures, the estimate to 3.
"""

from typing import Annotated

import numpy as np
import sympy as sp
from manim import Polygon, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.analysis import samples
from app.primitives.plotting import curve, make_plot, make_table, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    failing_samples,
    format_sf,
    latex_value,
    latex_with_pi,
    parse_expression,
    sample_points,
    written_latex,
)

X = sp.Symbol("x", real=True)
Limit = Annotated[str, Field(min_length=1, max_length=12, description='A number, or "pi", "pi/2"')]


class TrapeziumRuleParams(PrimitiveParams):
    expression: str = Field(min_length=1, max_length=100, description="f(x), e.g. sqrt(1 + x**2)")
    lower: Limit
    upper: Limit
    strips: Annotated[int, Field(ge=2, le=8)] = Field(default=4, description="How many trapezia")


class TrapeziumRule(StagedPrimitive[TrapeziumRuleParams]):
    primitive_id = "TrapeziumRule"
    version = "1"
    topic = "Integration"
    params_model = TrapeziumRuleParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[("axes", "*"), ("curve", "*"), ("trapezia", "*"), ("table", "*")],
    )

    def default_params(self) -> TrapeziumRuleParams:
        return TrapeziumRuleParams(expression="sqrt(1 + x**2)", lower="0", upper="2", strips=4)

    def validate(self, params: TrapeziumRuleParams) -> list[PredicateFailure]:
        try:
            f = parse_expression(params.expression, {"x"})
        except ExpressionError as error:
            return [_failure("parsing", "expression_parses", str(error), "expression")]
        try:
            a, b = _limit(params.lower), _limit(params.upper)
        except (ExpressionError, ValueError) as error:
            return [_failure("parsing", "limit_parses", str(error), "lower", "upper")]
        if a >= b:
            return [_failure("consistency", "limits_ordered", "lower must be below upper")]
        if abs(a) > 20 or abs(b) > 20:
            return [_failure("consistency", "limits_range", "keep the limits within 20 of 0")]
        if failing_samples(f, X, sample_points(float(a), float(b))):
            message = "f must be real and finite between the limits"
            return [_failure("domain", "real_and_finite", message, "expression")]
        return []

    def computed_values(self, params: TrapeziumRuleParams) -> dict[str, str]:
        t = _Trapezia(params)
        values = {"h": str(t.h), "estimate": format_sf(t.estimate), "shape": t.shape}
        if t.exact is not None:
            values["exact"] = format_sf(t.exact)
        return values

    def build(self, params: TrapeziumRuleParams, level):
        t = _Trapezia(params)
        lo, hi = float(t.a), float(t.b)
        _, ys = samples(t.f, lo, hi, 161)
        plot = make_plot(style.GRAPH_REGION, [lo, hi], [*ys, 0], origin=True)
        f_num = sp.lambdify(X, t.f, "math")
        trapezia = VGroup()
        for x0, x1, y0, y1 in zip(t.xs, t.xs[1:], t.ys, t.ys[1:], strict=False):
            trapezia.add(
                Polygon(
                    plot.point(float(x0), 0),
                    plot.point(float(x1), 0),
                    plot.point(float(x1), float(y1)),
                    plot.point(float(x0), float(y0)),
                    stroke_color=style.HIGHLIGHT_COLOUR,
                    stroke_width=2,
                    fill_color=style.AREA_COLOUR,
                    fill_opacity=0.4,
                )
            )
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "title": text_line(
                rf"\int_{{{_x(t.a)}}}^{{{_x(t.b)}}} {written_latex(params.expression)}\,dx",
                plot.upper,
            ),
            "curve": curve(plot, f_num, lo, hi),
            "trapezia": trapezia,
            "answer": text_line(t.answer_latex(), plot.lower, colour=style.HIGHLIGHT_COLOUR),
        }
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        table_box = style.Box(box.left, box.right, box.top - 1.6, box.top)
        table = make_table(
            [["x", *(_x(x) for x in t.xs)], ["y", *(format_sf(y, 4) for y in t.ys)]],
            table_box,
            font_size=28,
            pad=0.12,
        )
        parts["table"] = table.group
        rows = t.rows()
        rest = style.Box(box.left, box.right, box.bottom, table.group.get_bottom()[1] - 0.3)
        texts = stack_lines([r for r, _ in rows], rest, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: TrapeziumRuleParams, level) -> list[Stage]:
        steps = [
            stage(
                "graph",
                "Draw the curve between the limits",
                2.5,
                ["axes", "x_label", "y_label", "title", "curve"],
            ),
            stage(
                "strips",
                "Cut the area into strips of equal width h, each topped by a straight line",
                3.5,
                ["trapezia", "row_1"],
            ),
            stage("table", "Work out the height of the curve at each edge", 3.0, ["table"]),
            stage(
                "formula",
                "Add the trapezia: the end heights once, every inside height twice, times half h",
                3.5,
                ["row_2", "row_3", "answer"],
                emphasise=["answer"],
            ),
            stage("shape", _shape_words(_Trapezia(params).shape), 3.0, ["row_4"]),
        ]

        def standard(s):
            return [
                s[0],
                combine("strips", "Cut it into trapezia and find their heights", 4.0, s[1], s[2]),
                *s[3:],
            ]

        def concise(s):
            return [
                combine("strips", "The curve, cut into trapezia", 4.0, *s[:3]),
                combine("formula", s[3].description, 4.0, s[3], s[4]),
            ]

        return by_level(level, steps, standard, concise)


class _Trapezia:
    def __init__(self, params: TrapeziumRuleParams):
        self.f = sp.nsimplify(parse_expression(params.expression, {"x"}), rational=True)
        self.a, self.b = _limit(params.lower), _limit(params.upper)
        n = params.strips
        self.n = n
        self.h = (self.b - self.a) / n
        self.xs = [self.a + k * self.h for k in range(n + 1)]
        self.ys = [sp.N(self.f.subs(X, x), 30) for x in self.xs]
        inside = sum(self.ys[1:-1])
        self.estimate = self.h / 2 * (self.ys[0] + 2 * inside + self.ys[-1])
        integral = sp.integrate(self.f, (X, self.a, self.b))
        self.exact = None if integral.has(sp.Integral) else sp.N(integral, 30)
        second = sp.diff(self.f, X, 2)
        _, bends = samples(second, float(self.a), float(self.b), 101)
        bends = bends[1:-1][np.isfinite(bends[1:-1])]  # the ends may be points of inflexion
        if (bends > 1e-12).all():
            self.shape = "over"
        elif (bends < -1e-12).all():
            self.shape = "under"
        elif (abs(bends) <= 1e-12).all():
            self.shape = "exact"
        else:
            self.shape = "unknown"

    def answer_latex(self) -> str:
        text = rf"\approx {format_sf(self.estimate)}"
        if self.exact is not None:
            text += rf"\quad (\text{{exact }}{format_sf(self.exact)})"
        return text

    def rows(self) -> list[tuple[str, object]]:
        h = _x(self.h)
        ends = f"{format_sf(self.ys[0], 4)} + {format_sf(self.ys[-1], 4)}"
        inside = " + ".join(format_sf(y, 4) for y in self.ys[1:-1])
        verdict = {
            "over": (r"f''(x) > 0\text{: an over-estimate}", style.TANGENT_COLOUR),
            "under": (r"f''(x) < 0\text{: an under-estimate}", style.TANGENT_COLOUR),
            "exact": (r"\text{A straight line: exact}", style.TANGENT_COLOUR),
            "unknown": (r"\text{The curve bends both ways}", None),
        }[self.shape]
        return [
            (
                rf"h = \frac{{{_x(self.b)} - {_bracket(self.a)}}}{{{self.n}}} = {h}",
                None,
            ),
            (
                rf"\approx \tfrac{{1}}{{2}}\times {h}\left[{ends} + 2\left({inside}\right)\right]",
                None,
            ),
            (rf"\approx {format_sf(self.estimate)}", style.HIGHLIGHT_COLOUR),
            verdict,
        ]


def _limit(text: str) -> sp.Expr:
    value = sp.nsimplify(parse_expression(text, set()), [sp.pi], rational=True)
    if not value.is_real or not value.is_finite:
        raise ValueError(f"{text!r} is not a number")
    return value


def _x(value) -> str:
    """An x-value: a multiple of pi exactly, a simple fraction, or 3 significant figures."""
    value = sp.nsimplify(value)
    if value.has(sp.pi):
        return latex_with_pi(value, approx=False)
    if isinstance(value, sp.Rational) and value.q <= 12:
        return latex_value(value)
    return format_sf(value)


def _bracket(value) -> str:
    return rf"\left({_x(value)}\right)" if value < 0 else _x(value)


def _shape_words(shape: str) -> str:
    return {
        "over": "The curve bends upwards, so each trapezium overshoots: an over-estimate",
        "under": "The curve bends downwards, so each trapezium falls short: an under-estimate",
        "exact": "The graph is straight, so the trapezia fit it exactly",
        "unknown": "The curve bends both ways, so the shape alone does not say",
    }[shape]


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
