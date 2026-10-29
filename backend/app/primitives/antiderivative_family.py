"""AntiderivativeFamily: integrating dy/dx gives a family of curves y = F(x) + c, one for each
constant c, and a point the curve passes through picks out one of them (9709 1.8).

Every curve of the family has the same gradient at the same x, so they are copies of one
another shifted up and down. Substituting the point into y = F(x) + c gives c. SymPy integrates
(exactly), and checks that the curve found really has the given gradient and passes through the
point.
"""

from typing import Annotated

import numpy as np
import sympy as sp
from manim import Dot, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.analysis import samples
from app.primitives.plotting import curve, label, make_plot, place_label, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    exact,
    failing_samples,
    format_value,
    latex_value,
    parse_expression,
    sample_points,
    written_latex,
)

X = sp.Symbol("x", real=True)
Coordinate = Annotated[float, Field(ge=-20, le=20)]
SHIFTS = (-2, -1, 1, 2)


class AntiderivativeFamilyParams(PrimitiveParams):
    gradient: str = Field(
        min_length=1, max_length=100, description="dy/dx in terms of x, e.g. 3*x**2 - 4"
    )
    point: tuple[Coordinate, Coordinate] = Field(description="A point on the curve, (x, y)")
    x_min: Coordinate
    x_max: Coordinate


class AntiderivativeFamily(StagedPrimitive[AntiderivativeFamilyParams]):
    primitive_id = "AntiderivativeFamily"
    version = "1"
    topic = "Integration"
    params_model = AntiderivativeFamilyParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[("axes", "*"), ("family", "*"), ("curve", "*"), ("point", "*")],
    )

    def default_params(self) -> AntiderivativeFamilyParams:
        return AntiderivativeFamilyParams(gradient="3*x**2 - 4", point=(2, 5), x_min=-3, x_max=3)

    def validate(self, params: AntiderivativeFamilyParams) -> list[PredicateFailure]:
        try:
            g = parse_expression(params.gradient, {"x"})
        except ExpressionError as error:
            return [_failure("parsing", "expression_parses", str(error), "gradient")]
        if params.x_min >= params.x_max:
            return [_failure("consistency", "interval_ordered", "x_min must be below x_max")]
        if not params.x_min <= params.point[0] <= params.x_max:
            message = "the point must be inside the plotted interval"
            return [_failure("consistency", "point_in_interval", message, "point")]
        if failing_samples(g, X, sample_points(params.x_min, params.x_max)):
            message = "dy/dx must be real and finite across the interval"
            return [_failure("domain", "real_and_finite", message, "gradient")]
        integral = sp.integrate(sp.nsimplify(g, rational=True), X, manual=True)
        if integral.has(sp.Integral):
            integral = sp.integrate(sp.nsimplify(g, rational=True), X)
        if integral.has(sp.Integral):
            message = "dy/dx has no integral in a simple form"
            return [_failure("consistency", "integrable", message, "gradient")]
        return []

    def computed_values(self, params: AntiderivativeFamilyParams) -> dict[str, str]:
        f, c = _solve(params)
        return {"integral": str(f), "c": format_value(c), "curve": str(f + c)}

    def build(self, params: AntiderivativeFamilyParams, level):
        f, c = _solve(params)
        x0, y0 = exact(params.point[0]), exact(params.point[1])
        lo, hi = float(params.x_min), float(params.x_max)
        _, ys = samples(f + c, lo, hi, 161)
        values = [v for v in ys if np.isfinite(v)]
        spread = max(values) - min(values) if values else 1
        shift = _nice(max(spread / 4, 1))
        values += [min(values) + SHIFTS[0] * shift, max(values) + SHIFTS[-1] * shift]
        plot = make_plot(style.GRAPH_REGION, [lo, hi], values, y_ticks=6)
        numeric = sp.lambdify(X, f, "math")
        family = VGroup()
        for k in SHIFTS:
            family.add(
                curve(
                    plot,
                    lambda x, k=k: numeric(x) + float(c) + k * shift,
                    lo,
                    hi,
                    colour=style.SECANT_COLOUR,
                    stroke_width=2.5,
                )
            )
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "title": text_line(
                rf"\frac{{dy}}{{dx}} = {written_latex(params.gradient)}", plot.upper
            ),
            "family": family,
            "curve": curve(
                plot, lambda x: numeric(x) + float(c), lo, hi, colour=style.TANGENT_COLOUR
            ),
            "point": Dot(plot.point(float(x0), float(y0)), color=style.POINT_COLOUR),
        }
        parts["point_label"] = place_label(
            label(rf"({latex_value(x0)},\ {latex_value(y0)})", colour=style.POINT_COLOUR),
            plot.point(float(x0), float(y0)),
            plot.plot_box,
            plot.obstacles(),
            [parts["curve"], *family, *plot.axis_lines()],
            wide=True,
        )
        parts["answer"] = text_line(f"y = {_terms(f, c)}", plot.lower, colour=style.TANGENT_COLOUR)
        rows = [
            (rf"y = \int \left({written_latex(params.gradient)}\right) dx", None),
            (rf"y = {_terms(f)} + c", style.SECANT_COLOUR),
            (
                rf"{latex_value(y0)} = {_substituted(f, x0)} + c",
                style.POINT_COLOUR,
            ),
            (rf"c = {latex_value(c)}", None),
            (rf"y = {_terms(f, c)}", style.TANGENT_COLOUR),
        ]
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([t for t, _ in rows], box, size=30, colours=[col for _, col in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: AntiderivativeFamilyParams, level) -> list[Stage]:
        steps = [
            stage("axes", "Draw the axes", 1.5, ["axes", "x_label", "y_label", "title"]),
            stage(
                "integrate",
                "Integrating undoes differentiating, but a constant c could have been lost",
                3.0,
                ["row_1", "row_2"],
            ),
            stage(
                "family",
                "So there is a whole family of curves, one for each c, all the same shape",
                3.0,
                ["family", "curve"],
            ),
            stage(
                "point",
                "The curve passes through this point: substitute it",
                3.0,
                ["point", "point_label", "row_3"],
                emphasise=["point"],
            ),
            stage(
                "constant",
                "That fixes c, and picks out one curve from the family",
                3.0,
                ["row_4", "row_5", "answer"],
                hide=["family"],
                emphasise=["curve"],
            ),
        ]

        def standard(s):
            return [combine("integrate", s[1].description, 3.0, *s[:2]), *s[2:]]

        def concise(s):
            return [
                combine("family", "Integrate: a family of curves, one for each c", 3.5, *s[:3]),
                combine("constant", "The point fixes c", 3.5, *s[3:]),
            ]

        return by_level(level, steps, standard, concise)


def _solve(params: AntiderivativeFamilyParams):
    g = sp.nsimplify(parse_expression(params.gradient, {"x"}), rational=True)
    f = sp.integrate(g, X, manual=True)
    if f.has(sp.Integral):
        f = sp.integrate(g, X)
    x0, y0 = exact(params.point[0]), exact(params.point[1])
    c = sp.nsimplify(sp.simplify(y0 - f.subs(X, x0)))
    return f, c


def _terms(f: sp.Expr, constant=None) -> str:
    """F(x) term by term, highest power first, then the constant: x^3 - 4x + 5, -6/x + 4."""
    terms = sp.Add.make_args(f)
    ordered = sorted(terms, key=lambda t: -float(sp.degree(t, X)) if t.is_polynomial(X) else -0.5)
    if constant is not None and constant != 0:
        ordered.append(sp.sympify(constant))
    out = ""
    for term in ordered:
        coefficient, rest = term.as_coeff_Mul()
        body = sp.latex(abs(coefficient) * rest)
        sign = "-" if coefficient < 0 else "+"
        out += (("-" if sign == "-" else "") if not out else f" {sign} ") + body
    return out


def _substituted(f: sp.Expr, x0) -> str:
    """F(x0) written out with x0 in place of x, as in the working: 2^3 - 4(2)."""
    written = ""
    for term in sp.expand(f).as_ordered_terms():
        coefficient, rest = term.as_coeff_Mul()
        body = sp.latex(abs(coefficient) * rest.subs(X, sp.UnevaluatedExpr(x0)), mul_symbol="times")
        sign = "-" if coefficient < 0 else "+"
        written += (("-" if sign == "-" else "") if not written else f" {sign} ") + body
    return written if len(written) <= 60 else latex_value(sp.nsimplify(f.subs(X, x0)))


def _nice(value: float) -> float:
    for step in (1, 2, 5, 10, 20, 50, 100):
        if value <= step:
            return step
    return 100


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
