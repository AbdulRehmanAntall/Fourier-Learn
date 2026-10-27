"""InverseGraph: a one-to-one function and its inverse as reflections of each other in the line
y = x (4024 2.12; AM 1.5 to 1.8; PRIMITIVES.md #21, the reflection of f and f⁻¹).

Swapping x and y reflects a graph in y = x: each point (a, b) of f becomes (b, a) on f⁻¹. The
inverse's formula is found by SymPy (swap x and y, make y the subject), and f must be one-to-one
on the interval for it to exist. One unit is the same length on both axes, so the reflection is
a true mirror image.
"""

from typing import Annotated

import sympy as sp
from manim import DashedLine, Dot, Line, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.analysis import samples
from app.primitives.plotting import curve, label, make_plot, place_label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    exact,
    format_sf,
    latex_value,
    parse_expression,
    tidy_latex,
    written_latex,
)

X, Y = sp.symbols("x y", real=True)
Coordinate = Annotated[float, Field(ge=-10, le=10)]


class InverseGraphParams(PrimitiveParams):
    expression: str = Field(min_length=1, max_length=100, description="f(x), e.g. 2*x + 1")
    x_min: Coordinate
    x_max: Coordinate
    point_x: Coordinate | None = Field(
        default=None, description="Optionally follow one point (a, f(a)) to (f(a), a)"
    )


class InverseGraph(StagedPrimitive[InverseGraphParams]):
    primitive_id = "InverseGraph"
    version = "1"
    topic = "Functions and graphs"
    params_model = InverseGraphParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("axes", "*"), ("curve*", "*"), ("mirror", "*"), ("pair*", "*")],
    )

    def default_params(self) -> InverseGraphParams:
        return InverseGraphParams(expression="2*x + 1", x_min=-3, x_max=2, point_x=1)

    def validate(self, params: InverseGraphParams) -> list[PredicateFailure]:
        try:
            f = parse_expression(params.expression, {"x"})
        except ExpressionError as error:
            return [_failure("parsing", "expression_parses", str(error), "expression")]
        if params.x_min >= params.x_max:
            return [
                _failure("consistency", "interval_ordered", "x_min must be below x_max", "x_min")
            ]
        xs, ys = samples(f, params.x_min, params.x_max, 201)
        if not (ys == ys).all():  # NaN check
            return [
                _failure("domain", "real_and_finite", "f is not real on the interval", "expression")
            ]
        steps = ys[1:] - ys[:-1]
        if not ((steps > 0).all() or (steps < 0).all()):
            message = "f is not one-to-one on the interval, so it has no inverse there"
            return [_failure("consistency", "one_to_one", message, "x_min", "x_max")]
        if _inverse(params) is None:
            message = "SymPy cannot make x the subject of y = f(x)"
            return [_failure("consistency", "inverse_found", message, "expression")]
        if params.point_x is not None and not params.x_min <= params.point_x <= params.x_max:
            return [
                _failure(
                    "consistency", "point_in_interval", "point_x is outside the interval", "point_x"
                )
            ]
        if params.point_x is not None:
            a = exact(params.point_x)
            if sp.simplify(_f(params).subs(X, a) - a) == 0:
                message = "the point is on y = x, so it reflects onto itself; pick another"
                return [_failure("consistency", "point_off_mirror", message, "point_x")]
        return []

    def computed_values(self, params: InverseGraphParams) -> dict[str, str]:
        values = {"inverse": str(_inverse(params))}
        if params.point_x is not None:
            a = exact(params.point_x)
            b = _f(params).subs(X, a)
            values["point"] = f"({sp.sstr(a)}, {sp.sstr(b)})"
            values["reflected"] = f"({sp.sstr(b)}, {sp.sstr(a)})"
        return values

    def build(self, params: InverseGraphParams, level):
        f = _f(params)
        inverse = _inverse(params)
        f_num = sp.lambdify(X, f, "math")
        g_num = sp.lambdify(X, _real_roots(inverse), "numpy")
        _, ys = samples(f, params.x_min, params.x_max, 121)
        lo, hi = float(min(ys)), float(max(ys))
        values = [params.x_min, params.x_max, lo, hi]
        plot = make_plot(self.layout.region, values, values, equal=True)
        top = min(plot.x_range[1], plot.y_range[1])
        bottom = max(plot.x_range[0], plot.y_range[0])
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "equation": text_line(rf"f(x) = {written_latex(params.expression)}", plot.upper),
            "inverse_formula": text_line(rf"f^{{-1}}(x) = {_inverse_latex(inverse)}", plot.lower),
            "curve_f": curve(plot, f_num, params.x_min, params.x_max),
            "curve_inverse": curve(plot, g_num, lo, hi, colour=style.TANGENT_COLOUR),
            "mirror": DashedLine(
                plot.point(bottom, bottom),
                plot.point(top, top),
                color=style.TEXT_COLOUR,
                stroke_width=2,
            ),
        }
        obstacles = plot.obstacles()
        paths = [parts["curve_f"], parts["curve_inverse"], parts["mirror"], *plot.axis_lines()]
        if params.point_x is not None:
            a = exact(params.point_x)
            b = f.subs(X, a)
            p, q = plot.point(float(a), float(b)), plot.point(float(b), float(a))
            parts["pair"] = VGroup(
                Dot(p, color=style.POINT_COLOUR),
                Dot(q, color=style.POINT_COLOUR),
                Line(p, q, color=style.POINT_COLOUR, stroke_width=2),
            )
            obstacles += list(parts["pair"][:2])
            # a decimal point_x is written as a decimal, and so is its image
            written = latex_value if a.is_integer else format_sf
            for name, anchor, tex in (
                ("pair_label_1", p, rf"({written(a)},\ {written(b)})"),
                ("pair_label_2", q, rf"({written(b)},\ {written(a)})"),
            ):
                text = label(tex, colour=style.POINT_COLOUR)
                parts[name] = place_label(text, anchor, plot.plot_box, obstacles, paths, wide=True)
                obstacles.append(text)
        for name, anchor, tex, colour in (
            (
                "curve_f_label",
                plot.point(params.x_max, f_num(params.x_max)),
                "y = f(x)",
                style.CURVE_COLOUR,
            ),
            (
                "curve_inverse_label",
                plot.point(f_num(params.x_max), params.x_max),
                "y = f^{-1}(x)",
                style.TANGENT_COLOUR,
            ),
            ("mirror_label", plot.point(top, top), "y = x", style.TEXT_COLOUR),
        ):
            text = label(tex, colour=colour)
            parts[name] = place_label(text, anchor, plot.plot_box, obstacles, paths, wide=True)
            obstacles.append(text)
        return parts

    def stages(self, params: InverseGraphParams, level) -> list[Stage]:
        pair = ["pair", "pair_label_1", "pair_label_2"] if params.point_x is not None else []
        steps = [
            stage(
                "graph",
                "Draw the graph of f",
                2.5,
                ["axes", "x_label", "y_label", "equation", "curve_f", "curve_f_label"],
            ),
            stage("mirror", "Draw the mirror line y = x", 2.0, ["mirror", "mirror_label"]),
            stage(
                "reflect",
                "Reflect f in the mirror: x and y swap places",
                3.0,
                ["curve_inverse", "curve_inverse_label", *pair],
            ),
            stage(
                "formula",
                "Swap x and y in the equation and make y the subject",
                3.0,
                ["inverse_formula"],
                emphasise=["inverse_formula"],
            ),
        ]

        def standard(s):
            return [
                combine("graph", "The graph of f and the line y = x", 3.0, s[0], s[1]),
                s[2],
                s[3],
            ]

        def concise(s):
            return [
                combine("graph", "The graph of f and the line y = x", 3.0, s[0], s[1]),
                combine("inverse", "Reflect it, and swap x and y in the formula", 3.5, s[2], s[3]),
            ]

        return by_level(level, steps, standard, concise)


def _f(params: InverseGraphParams) -> sp.Expr:
    return sp.nsimplify(parse_expression(params.expression, {"x"}), rational=True)


def _inverse(params: InverseGraphParams) -> sp.Expr | None:
    """f⁻¹(x): solve x = f(y) for y, keeping the branch that maps back into the interval."""
    f = _f(params)
    try:
        solutions = sp.solve(sp.Eq(X, f.subs(X, Y)), Y)
    except NotImplementedError:
        return None
    middle = exact((params.x_min + params.x_max) / 2)
    image = f.subs(X, middle)
    for solution in solutions:
        try:
            back = complex(solution.subs(X, image))
        except (TypeError, ValueError):
            continue
        if abs(back.imag) < 1e-9 and abs(back.real - float(middle)) < 1e-6:
            return sp.simplify(solution)
    return None


def _real_roots(expr: sp.Expr) -> sp.Expr:
    """Odd roots taken as the real root, so the inverse of x³ is drawn for negative x too."""
    return expr.replace(
        lambda e: e.is_Pow and e.exp.is_Rational and e.exp.q % 2 == 1 and e.exp.q > 1,
        lambda e: sp.sign(e.base) ** e.exp.p * sp.Abs(e.base) ** e.exp,
    )


def _inverse_latex(inverse: sp.Expr) -> str:
    """(x - 1)/2 rather than x/2 - 1/2, and log₂ x rather than log(x)/log(2)."""
    numerator, denominator = sp.fraction(sp.together(inverse))
    if isinstance(denominator, sp.log) and numerator == sp.log(X):
        return rf"\log_{{{sp.latex(denominator.args[0])}}} x"
    together = sp.together(inverse)
    if sp.count_ops(together) <= sp.count_ops(inverse):
        return sp.latex(together)
    return tidy_latex(inverse)


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
