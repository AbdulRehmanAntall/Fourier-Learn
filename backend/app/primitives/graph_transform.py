"""GraphTransform: the graph of y = f(x) moved by translations, reflections and stretches, one
at a time, ending at y = pf(qx + r) + s (9709 1.2).

The syllabus forms: y = f(x) + a is a translation by (0, a); y = f(x + a) a translation by
(-a, 0); y = af(x) a stretch parallel to the y-axis, factor a; y = f(ax) a stretch parallel to
the x-axis, factor 1/a; y = -f(x) and y = f(-x) reflections in the x-axis and the y-axis. A
change inside the bracket acts on x, the opposite way to how it looks; a change outside acts on
y as it looks. A point is followed through every step, and SymPy gives its image exactly.
"""

from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import Dot
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.analysis import samples
from app.primitives.plotting import curve, label, make_plot, place_label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    exact,
    failing_samples,
    format_value,
    latex_value,
    parse_expression,
    sample_points,
    tidy_latex,
    written_latex,
)

X = sp.Symbol("x", real=True)
Coordinate = Annotated[float, Field(ge=-10, le=10)]
Kind = Literal["translate_x", "translate_y", "stretch_x", "stretch_y", "reflect_x", "reflect_y"]


class Transformation(PrimitiveParams):
    kind: Kind = Field(
        description="translate_y: y = f(x) + a. translate_x: y = f(x + a), which moves the "
        "graph a units LEFT. stretch_y: y = af(x). stretch_x: y = f(ax), factor 1/a. "
        "reflect_x: y = -f(x). reflect_y: y = f(-x)"
    )
    value: Annotated[float, Field(ge=-10, le=10)] = Field(
        default=1, description="The a of the form; not used by the reflections"
    )


class GraphTransformParams(PrimitiveParams):
    expression: str = Field(min_length=1, max_length=100, description="f(x), e.g. x**2")
    x_min: Coordinate
    x_max: Coordinate
    transformations: list[Transformation] = Field(
        min_length=1, max_length=3, description="Applied in order, each to the result so far"
    )
    point_x: Coordinate | None = Field(
        default=None, description="Optionally follow the point (a, f(a)) through every step"
    )


class GraphTransform(StagedPrimitive[GraphTransformParams]):
    primitive_id = "GraphTransform"
    version = "1"
    topic = "Functions"
    params_model = GraphTransformParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("axes", "*"),
            ("base", "*"),
            ("curve_*", "*"),
            ("point_*", "point_*"),
        ],
    )

    def default_params(self) -> GraphTransformParams:
        return GraphTransformParams(
            expression="x**2",
            x_min=-2,
            x_max=2,
            transformations=[
                Transformation(kind="translate_x", value=1),
                Transformation(kind="stretch_y", value=2),
                Transformation(kind="translate_y", value=-3),
            ],
            point_x=1,
        )

    def validate(self, params: GraphTransformParams) -> list[PredicateFailure]:
        try:
            f = parse_expression(params.expression, {"x"})
        except ExpressionError as error:
            return [_failure("parsing", "expression_parses", str(error), "expression")]
        if params.x_min >= params.x_max:
            return [_failure("consistency", "interval_ordered", "x_min must be below x_max")]
        if failing_samples(f, X, sample_points(params.x_min, params.x_max)):
            message = "f is not real and finite everywhere on the interval; shorten it"
            return [_failure("domain", "real_and_finite", message, "expression")]
        for step in params.transformations:
            if step.kind.startswith("stretch") and (step.value <= 0 or step.value == 1):
                message = "a stretch factor must be positive and not 1 (use a reflection for -1)"
                return [_failure("consistency", "stretch_factor", message, "transformations")]
            if step.kind.startswith("translate") and step.value == 0:
                message = "a translation by 0 does nothing"
                return [_failure("consistency", "translation_moves", message, "transformations")]
        if params.point_x is not None and not params.x_min <= params.point_x <= params.x_max:
            message = "the point must lie on the drawn part of the graph"
            return [_failure("consistency", "point_on_graph", message, "point_x")]
        return []

    def computed_values(self, params: GraphTransformParams) -> dict[str, str]:
        chain = _Chain(params)
        values = {
            "equation": chain.notation_text(len(params.transformations)),
            "final_expression": str(chain.expression(len(params.transformations))),
        }
        for k, (x, y) in enumerate(chain.points() if params.point_x is not None else []):
            values[f"point_{k}"] = f"({format_value(x)}, {format_value(y)})"
        return values

    def build(self, params: GraphTransformParams, level):
        chain = _Chain(params)
        n = len(params.transformations)
        f_num = sp.lambdify(X, chain.f, "math")
        domains = chain.domains()
        xs, ys = [], []
        for k in range(n + 1):
            lo, hi = domains[k]
            xs += [lo, hi]
            _, values = samples(chain.expression(k), lo, hi, 121)
            ys += [v for v in values if np.isfinite(v)]
        plot = make_plot(self.layout.region, xs, ys)
        parts = {"axes": plot.axes, "x_label": plot.x_label, "y_label": plot.y_label}
        obstacles = plot.obstacles()
        lo, hi = domains[0]
        parts["base"] = curve(plot, f_num, lo, hi)
        for k in range(n + 1):
            p, q, r, s = chain.coefficients[k]
            lo, hi = domains[k]

            def g(x, p=p, q=q, r=r, s=s):
                return p * f_num(q * x + r) + s

            parts[f"curve_{k}"] = curve(
                plot, g, lo, hi, colour=style.CURVE_COLOUR if k == 0 else style.TANGENT_COLOUR
            )
            parts[f"eq_{k}"] = text_line(f"y = {chain.notation(k)}", plot.upper)
        for k, step in enumerate(params.transformations, start=1):
            parts[f"desc_{k}"] = text_line(_description_latex(step), plot.lower, size=34)
        parts["result"] = text_line(
            f"y = {sp.latex(chain.expression(n, evaluate=False))}",
            plot.lower,
            colour=style.TANGENT_COLOUR,
        )
        paths = [parts["base"], *plot.axis_lines()]
        if params.point_x is not None:
            for k, (x, y) in enumerate(chain.points()):
                dot = Dot(plot.point(float(x), float(y)), color=style.POINT_COLOUR)
                parts[f"point_{k}"] = dot
            for k, (x, y) in enumerate(chain.points()):
                text = label(
                    rf"({latex_value(x)},\ {latex_value(y)})", colour=style.POINT_COLOUR, size=26
                )
                others = [parts[f"curve_{k}"], parts["base"], *plot.axis_lines()]
                parts[f"point_{k}_label"] = place_label(
                    text,
                    plot.point(float(x), float(y)),
                    plot.plot_box,
                    [*obstacles, parts[f"point_{k}"]],
                    others,
                    wide=True,
                )
            obstacles += [parts["point_0"], parts["point_0_label"]]
        base_text = label(f"y = {written_latex(params.expression)}", colour=style.CURVE_COLOUR)
        end = plot.point(
            domains[0][1], min(max(f_num(domains[0][1]), plot.y_range[0]), plot.y_range[1])
        )
        parts["base_label"] = place_label(
            base_text, end, plot.plot_box, obstacles, [*paths, parts[f"curve_{n}"]], wide=True
        )
        return parts

    def stages(self, params: GraphTransformParams, level) -> list[Stage]:
        n = len(params.transformations)
        point = params.point_x is not None
        steps = [
            stage("axes", "Draw the axes", 1.5, ["axes", "x_label", "y_label"]),
            stage(
                "graph",
                "Draw y equals f of x, the graph we start from",
                2.5,
                ["base", "curve_0", "base_label", "eq_0"],
            ),
        ]
        if point:
            steps.append(
                stage(
                    "point",
                    "Follow one point through every step",
                    2.0,
                    ["point_0", "point_0_label"],
                    emphasise=["point_0"],
                )
            )
        for k, step in enumerate(params.transformations, start=1):
            describe = stage(
                f"describe_{k}",
                _spoken(step),
                2.5,
                [f"desc_{k}"] if k == 1 else [],
                morph=[] if k == 1 else [(f"desc_{k - 1}", f"desc_{k}")],
                emphasise=[f"desc_{k}"],
            )
            moves = [(f"curve_{k - 1}", f"curve_{k}"), (f"eq_{k - 1}", f"eq_{k}")]
            if point:
                moves += [
                    (f"point_{k - 1}", f"point_{k}"),
                    (f"point_{k - 1}_label", f"point_{k}_label"),
                ]
            apply = stage(f"apply_{k}", _effect(step), 3.0, morph=moves)
            steps += [describe, apply]
        steps.append(
            stage(
                "result",
                "Written out, the new graph's equation is",
                2.5,
                morph=[(f"desc_{n}", "result")],
                emphasise=["result"],
            )
        )
        head = 3 if point else 2

        def standard(s):
            out = [combine("graph", "The graph of y equals f of x", 3.0, *s[:head])]
            for k in range(n):
                describe, apply = s[head + 2 * k], s[head + 2 * k + 1]
                out.append(combine(apply.name, describe.description, 3.0, describe, apply))
            return [*out, s[-1]]

        def concise(s):
            out = standard(s)
            return [*out[:-2], combine("last", out[-2].description, 3.0, out[-2], out[-1])]

        return by_level(level, steps, standard, concise)


class _Chain:
    """The transformations as y = p f(qx + r) + s after each step."""

    def __init__(self, params: GraphTransformParams):
        self.params = params
        self.f = sp.nsimplify(parse_expression(params.expression, {"x"}), rational=True)
        p, q, r, s = sp.Integer(1), sp.Integer(1), sp.Integer(0), sp.Integer(0)
        self.coefficients = [(p, q, r, s)]
        for step in params.transformations:
            a = exact(step.value)
            if step.kind == "translate_y":
                s = s + a
            elif step.kind == "stretch_y":
                p, s = p * a, s * a
            elif step.kind == "reflect_x":
                p, s = -p, -s
            elif step.kind == "translate_x":
                r = r + q * a
            elif step.kind == "stretch_x":
                q = q * a
            else:
                q = -q
            self.coefficients.append((p, q, r, s))

    def expression(self, k: int, evaluate: bool = True) -> sp.Expr:
        p, q, r, s = self.coefficients[k]
        inner = self.f.subs(X, q * X + r)
        if not evaluate:
            return sp.Add(sp.Mul(p, inner, evaluate=False), s, evaluate=False) if s else p * inner
        return sp.expand(p * inner + s) if self.f.is_polynomial(X) else p * inner + s

    def notation(self, k: int) -> str:
        p, q, r, s = self.coefficients[k]
        inner = tidy_latex(q * X + r)
        lead = "" if p == 1 else ("-" if p == -1 else latex_value(p))
        tail = "" if s == 0 else (f" + {latex_value(s)}" if s > 0 else f" - {latex_value(-s)}")
        return rf"{lead}\mathrm{{f}}\left({inner}\right){tail}"

    def notation_text(self, k: int) -> str:
        p, q, r, s = self.coefficients[k]
        return f"y = {p}*f({q * X + r}) + {s}"

    def _map(self, x, y, step):
        a = exact(step.value)
        return {
            "translate_y": (x, y + a),
            "stretch_y": (x, a * y),
            "reflect_x": (x, -y),
            "translate_x": (x - a, y),
            "stretch_x": (x / a, y),
            "reflect_y": (-x, y),
        }[step.kind]

    def points(self) -> list[tuple[sp.Expr, sp.Expr]]:
        x = exact(self.params.point_x)
        y = sp.nsimplify(self.f.subs(X, x))
        out = [(x, y)]
        for step in self.params.transformations:
            x, y = self._map(x, y, step)
            out.append((sp.nsimplify(x), sp.nsimplify(y)))
        return out

    def domains(self) -> list[tuple[float, float]]:
        lo, hi = exact(self.params.x_min), exact(self.params.x_max)
        out = [(float(lo), float(hi))]
        for step in self.params.transformations:
            lo, _ = self._map(lo, 0, step)
            hi, _ = self._map(hi, 0, step)
            lo, hi = min(lo, hi), max(lo, hi)
            out.append((float(lo), float(hi)))
        return out


def _description_latex(step: Transformation) -> str:
    a = exact(step.value)
    if step.kind == "translate_y":
        return rf"\text{{Translation by }}\begin{{pmatrix}}0\\{latex_value(a)}\end{{pmatrix}}"
    if step.kind == "translate_x":
        return rf"\text{{Translation by }}\begin{{pmatrix}}{latex_value(-a)}\\0\end{{pmatrix}}"
    if step.kind == "stretch_y":
        return rf"\text{{Stretch parallel to the }}y\text{{-axis, factor }}{latex_value(a)}"
    if step.kind == "stretch_x":
        return rf"\text{{Stretch parallel to the }}x\text{{-axis, factor }}{latex_value(1 / a)}"
    if step.kind == "reflect_x":
        return r"\text{Reflection in the }x\text{-axis}"
    return r"\text{Reflection in the }y\text{-axis}"


def _spoken(step: Transformation) -> str:
    a = exact(step.value)
    if step.kind == "translate_y":
        way = "up" if a > 0 else "down"
        return (
            f"Adding {format_value(a)} outside the function moves every point {way} "
            f"{format_value(abs(a))}"
        )
    if step.kind == "translate_x":
        way = "left" if a > 0 else "right"
        return (
            f"Adding {format_value(a)} inside the bracket moves every point {way} "
            f"{format_value(abs(a))}: the opposite way to the sign"
        )
    if step.kind == "stretch_y":
        return (
            f"Multiplying the function by {format_value(a)} stretches it vertically, "
            f"factor {format_value(a)}"
        )
    if step.kind == "stretch_x":
        return (
            f"Multiplying x by {format_value(a)} inside the bracket stretches it horizontally, "
            f"factor {format_value(1 / a)}"
        )
    if step.kind == "reflect_x":
        return "A minus sign outside the function reflects it in the x-axis"
    return "A minus sign on x inside the bracket reflects it in the y-axis"


def _effect(step: Transformation) -> str:
    if step.kind in ("translate_y", "stretch_y", "reflect_x"):
        return "Each y-coordinate changes; the x-coordinates stay the same"
    return "Each x-coordinate changes; the y-coordinates stay the same"


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
