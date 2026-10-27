"""ProportionGraph: direct and inverse proportion, with the constant k found from a known pair
and used (4024 2.8; PRIMITIVES.md #18).

"y is proportional to x²" becomes y = kx²; a known pair of values gives k; the graph of the rule
passes through that pair; and a new value of x (or y) is found from the rule. Proportion to x, x²,
x³ and √x, direct or inverse. Every value is computed exactly by SymPy.
"""

from typing import Annotated, Literal

import sympy as sp
from manim import DashedLine, Dot
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import curve, label, make_plot, place_label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_value, latex_value

X = sp.Symbol("x", positive=True)
Positive = Annotated[float, Field(gt=0, le=1000)]


class ProportionGraphParams(PrimitiveParams):
    kind: Literal["direct", "inverse"]
    power: Literal["1", "2", "3", "1/2"] = Field(
        default="1", description="y is proportional to x to this power (1/2 means √x)"
    )
    known: tuple[Positive, Positive] = Field(description="A known pair (x, y)")
    find_x: Positive | None = Field(default=None, description="Find y for this x")
    find_y: Positive | None = Field(default=None, description="Find x for this y")


class ProportionGraph(StagedPrimitive[ProportionGraphParams]):
    primitive_id = "ProportionGraph"
    version = "1"
    topic = "Algebra and graphs"
    params_model = ProportionGraphParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("axes", "*"), ("curve", "*"), ("guide_*", "*"), ("point_*", "point_*")],
    )

    def default_params(self) -> ProportionGraphParams:
        return ProportionGraphParams(kind="direct", power="2", known=(2, 12), find_x=5)

    def validate(self, params: ProportionGraphParams) -> list[PredicateFailure]:
        if params.find_x is not None and params.find_y is not None:
            return [
                PredicateFailure(
                    kind="consistency",
                    predicate="one_unknown",
                    message="give find_x or find_y, not both",
                    parameters=["find_x", "find_y"],
                )
            ]
        return []

    def computed_values(self, params: ProportionGraphParams) -> dict[str, str]:
        p = _Proportion(params)
        values = {"k": format_value(p.k), "rule": f"y = {p.k} * {p.rule_text()}"}
        if p.found is not None:
            values["found_x"] = format_value(p.found[0])
            values["found_y"] = format_value(p.found[1])
        return values

    def build(self, params: ProportionGraphParams, level):
        p = _Proportion(params)
        xs = [float(p.x1)]
        if p.found is not None:
            xs.append(float(p.found[0]))
        x_hi = max(xs) * 1.3
        x_lo = x_hi / 40 if params.kind == "inverse" else 0.0
        ys = [float(p.y1)] + ([float(p.found[1])] if p.found is not None else [])
        y_hi = max(ys) * (1.6 if params.kind == "inverse" else 1.3)
        plot = make_plot(self.layout.region, [0, x_hi], [0, y_hi])
        f = sp.lambdify(X, p.formula, "math")
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "statement": text_line(rf"y \propto {p.shape_latex()}", plot.upper),
            "with_k": text_line(f"y = {p.with_k_latex()}", plot.upper),
            "rule": text_line(f"y = {p.rule_latex()}", plot.upper),
            "find_k": text_line(
                rf"{latex_value(p.y1)} = {p.substituted_latex()}"
                rf"\ \Rightarrow\ k = {latex_value(p.k)}",
                plot.lower,
            ),
            "curve": curve(plot, f, x_lo, plot.x_range[1]),
        }
        obstacles = plot.obstacles()
        paths = [parts["curve"], *plot.axis_lines()]
        known = plot.point(float(p.x1), float(p.y1))
        parts["point_known"] = Dot(known, color=style.POINT_COLOUR)
        obstacles.append(parts["point_known"])
        text = label(rf"({latex_value(p.x1)},\ {latex_value(p.y1)})", colour=style.POINT_COLOUR)
        parts["point_known_label"] = place_label(
            text, known, plot.plot_box, obstacles, paths, wide=True
        )
        obstacles.append(text)
        if p.found is not None:
            fx, fy = (float(v) for v in p.found)
            found = plot.point(fx, fy)
            parts["point_found"] = Dot(found, color=style.TANGENT_COLOUR)
            parts["guide_x"] = DashedLine(plot.point(fx, 0), found, color=style.TANGENT_COLOUR)
            parts["guide_y"] = DashedLine(plot.point(0, fy), found, color=style.TANGENT_COLOUR)
            obstacles.append(parts["point_found"])
            text = label(
                rf"({latex_value(p.found[0])},\ {latex_value(p.found[1])})",
                colour=style.TANGENT_COLOUR,
            )
            parts["point_found_label"] = place_label(
                text,
                found,
                plot.plot_box,
                obstacles,
                [*paths, parts["guide_x"], parts["guide_y"]],
                wide=True,
            )
            parts["answer"] = text_line(p.answer_latex(), plot.lower)
        return parts

    def stages(self, params: ProportionGraphParams, level) -> list[Stage]:
        p = _Proportion(params)
        word = "proportional" if params.kind == "direct" else "inversely proportional"
        steps = [
            stage("statement", f"y is {word} to {p.shape_words()}", 2.0, ["statement"]),
            stage(
                "with_k",
                "Write it as an equation with a constant k",
                2.0,
                morph=[("statement", "with_k")],
            ),
            stage(
                "find_k",
                "Substitute the known pair of values to find k",
                3.0,
                ["find_k"],
                emphasise=["find_k"],
            ),
            stage(
                "graph",
                "Draw the graph of the rule",
                2.5,
                ["axes", "x_label", "y_label", "curve"],
                morph=[("with_k", "rule")],
            ),
            stage(
                "known",
                "It passes through the known pair",
                1.5,
                ["point_known", "point_known_label"],
                emphasise=["point_known"],
            ),
        ]
        if p.found is not None:
            unknown = "y" if params.find_x is not None else "x"
            steps.append(
                stage(
                    "find",
                    f"Use the rule to find {unknown}",
                    3.0,
                    ["guide_x", "guide_y", "point_found", "point_found_label"],
                    morph=[("find_k", "answer")],
                    emphasise=["point_found"],
                )
            )

        def standard(s):
            out = [
                combine("equation", "Write the proportion as an equation with k", 2.5, s[0], s[1]),
                s[2],
                combine("graph", "Draw the graph through the known pair", 3.0, s[3], s[4]),
            ]
            return out + s[5:]

        def concise(s):
            first = combine("k", "Write the equation and find k", 3.0, s[0], s[1], s[2])
            return [first, combine("graph", "Draw the graph and use it", 3.0, *s[3:])]

        return by_level(level, steps, standard, concise)


class _Proportion:
    def __init__(self, params: ProportionGraphParams):
        self.params = params
        self.x1, self.y1 = exact(params.known[0]), exact(params.known[1])
        self.power = sp.Rational(params.power)
        shape = X**self.power
        self.shape = shape if params.kind == "direct" else 1 / shape
        self.k = sp.nsimplify(self.y1 / self.shape.subs(X, self.x1))
        self.formula = self.k * self.shape
        self.found = None
        if params.find_x is not None:
            x = exact(params.find_x)
            self.found = (x, sp.nsimplify(self.formula.subs(X, x)))
        elif params.find_y is not None:
            y = exact(params.find_y)
            solutions = sp.solve(sp.Eq(self.formula, y), X)
            self.found = (sp.nsimplify(solutions[0]), y)

    def power_latex(self, variable: str = "x") -> str:
        if self.power == 1:
            return variable
        if self.power == sp.Rational(1, 2):
            return rf"\sqrt{{{variable}}}"
        return f"{variable}^{{{self.power}}}"

    def shape_latex(self) -> str:
        return (
            self.power_latex()
            if self.params.kind == "direct"
            else rf"\frac{{1}}{{{self.power_latex()}}}"
        )

    def shape_words(self) -> str:
        return {
            "1": "x",
            "2": "x squared",
            "3": "x cubed",
            "1/2": "the square root of x",
        }[self.params.power]

    def with_k_latex(self) -> str:
        if self.params.kind == "direct":
            return f"k{self.power_latex()}"
        return rf"\frac{{k}}{{{self.power_latex()}}}"

    def rule_latex(self) -> str:
        k = latex_value(self.k)
        if self.params.kind == "direct":
            return f"{'' if self.k == 1 else k}{self.power_latex()}"
        return rf"\frac{{{k}}}{{{self.power_latex()}}}"

    def rule_text(self) -> str:
        return str(self.shape)

    def substituted_latex(self) -> str:
        x = latex_value(self.x1)
        shape = (
            self.power_latex(x)
            if self.power == 1 or self.power == sp.Rational(1, 2)
            else (f"{x}^{{{self.power}}}")
        )
        if self.params.kind == "direct":
            return rf"k \times {shape}"
        return rf"\frac{{k}}{{{shape}}}"

    def answer_latex(self) -> str:
        x, y = self.found
        if self.params.find_x is not None:
            return rf"x = {latex_value(x)}:\ y = {latex_value(y)}"
        return rf"y = {latex_value(y)}:\ x = {latex_value(x)}"
