"""ConnectedRates: a shape growing with time, and the chain rule linking the rate its size
changes to the rate its area or volume changes (AM 14.7; PRIMITIVES.md #56).

A circle's radius, a square's side, a sphere's radius or a cube's edge grows at a known rate;
dA/dt = dA/dr × dr/dt gives how fast the area (or volume) grows at a given size, or the other way
round when the area's rate is known. The shape is drawn growing. Every value is computed by
SymPy, exact where it can be (with π) and to 3 significant figures beside it.
"""

from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import Circle, Line, Square, ValueTracker, VGroup, always_redraw
from pydantic import Field

from app.contracts import LayoutContract, PrimitiveParams, Region
from app.primitives import style
from app.primitives.plotting import label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_value, latex_value, latex_with_pi

R = sp.Symbol("r", positive=True)
SHAPE = Region(x_min=0.0, x_max=0.62, y_min=0.0, y_max=0.8)
SHAPES = {
    # quantity, length, formula, quantity word, length word, is volume
    "circle": ("A", "r", sp.pi * R**2, "area", "radius", False),
    "square": ("A", "x", R**2, "area", "side", False),
    "sphere": ("V", "r", sp.Rational(4, 3) * sp.pi * R**3, "volume", "radius", True),
    "cube": ("V", "x", R**3, "volume", "edge", True),
}


class ConnectedRatesParams(PrimitiveParams):
    shape: Literal["circle", "square", "sphere", "cube"]
    known: Literal["length", "quantity"] = Field(
        default="length",
        description="length: the rate of the radius or side is known; quantity: the rate of the "
        "area or volume is known",
    )
    rate: Annotated[float, Field(gt=0, le=1000)] = Field(description="The known rate, per second")
    at: Annotated[float, Field(gt=0, le=100)] = Field(
        description="The radius or side at the moment"
    )


class ConnectedRates(StagedPrimitive[ConnectedRatesParams]):
    primitive_id = "ConnectedRates"
    version = "1"
    topic = "Introductory calculus"
    params_model = ConnectedRatesParams
    layout = LayoutContract(region=style.GRAPH_REGION, allowed_overlaps=[("shape*", "*")])

    def default_params(self) -> ConnectedRatesParams:
        return ConnectedRatesParams(shape="circle", rate=2, at=5)

    def validate(self, params: ConnectedRatesParams):
        return []

    def computed_values(self, params: ConnectedRatesParams) -> dict[str, str]:
        r = _Rates(params)
        return {"derivative": str(r.derivative_at), "answer": format_value(r.answer)}

    def build(self, params: ConnectedRatesParams, level):
        r = _Rates(params)
        title, _ = style.graph_boxes(style.GRAPH_REGION)
        upper, lower = style.title_lines(title)
        box = style.region_box(SHAPE).shrink(0.6)
        size = min(box.width, box.height) * 0.42
        q, x = r.q_name, r.x_name
        parts = {
            "formula": text_line(rf"{q} = {sp.latex(r.formula)}", upper),
            "derivative": text_line(
                rf"\frac{{d{q}}}{{d{x}}} = {sp.latex(r.derivative)} = "
                rf"{latex_value(r.derivative_at)}\text{{ when }} {x} = {latex_value(r.at)}",
                lower,
            ),
            "chain": text_line(r.chain_latex(), upper),
            "answer": text_line(r.answer_latex(), lower),
        }
        shape, measure = _shape(params.shape, box.center, size)
        parts["shape"] = shape
        parts["shape_measure"] = measure
        parts["shape_label"] = label(
            f"{x} = {latex_value(r.at)}", colour=style.RISE_COLOUR, size=style.FONT_SIZE
        ).next_to(measure, [0, 1, 0], 0.15)
        parts["rate_label"] = label(
            r.given_latex(), colour=style.HIGHLIGHT_COLOUR, size=style.FONT_SIZE
        ).move_to([box.center[0], box.bottom - 0.3, 0])
        self._growth = (params.shape, box.center, size)
        return parts

    def grow(self, scene, parts, level, run_time, min_run_time):
        """The shape grows to its size at the moment, so the rate is something seen."""
        kind, centre, size = self._growth
        scale = ValueTracker(0.55)
        scene.remove(parts["shape"], parts["shape_measure"])
        moving = always_redraw(lambda: VGroup(*_shape(kind, centre, size * scale.get_value())))
        scene.add(moving)
        hold = min(0.15, 0.2 * run_time)
        animation_time = min(max(min_run_time, 0.6 * run_time), run_time - hold)
        scene.play(scale.animate.set_value(1.0), run_time=animation_time)
        scene.remove(moving)
        scene.add(parts["shape"], parts["shape_measure"])
        scene.wait(run_time - animation_time)

    def stages(self, params: ConnectedRatesParams, level) -> list[Stage]:
        r = _Rates(params)
        steps = [
            stage(
                "shape",
                f"The {params.shape}, with its {r.x_word}",
                2.0,
                ["shape", "shape_measure", "shape_label", "formula"],
            ),
            stage(
                "grow",
                f"It is growing: the rate of its {r.given_word} is known",
                3.0,
                ["rate_label"],
                motion="grow",
            ),
            stage(
                "derivative",
                f"Differentiate the {r.q_word} with respect to {r.x_name}",
                3.0,
                ["derivative"],
                emphasise=["derivative"],
            ),
            stage("chain", "The chain rule links the two rates", 3.0, morph=[("formula", "chain")]),
            stage(
                "answer",
                "Substitute the values",
                3.0,
                morph=[("derivative", "answer")],
                emphasise=["answer"],
            ),
        ]

        def standard(s):
            return [
                s[0],
                s[1],
                s[2],
                combine("answer", "Use the chain rule and substitute", 3.5, s[3], s[4]),
            ]

        def concise(s):
            return [
                s[0],
                s[1],
                combine("answer", "Differentiate and use the chain rule", 4.0, *s[2:]),
            ]

        return by_level(level, steps, standard, concise)


class _Rates:
    def __init__(self, params: ConnectedRatesParams):
        self.q_name, self.x_name, formula, self.q_word, self.x_word, _ = SHAPES[params.shape]
        x = sp.Symbol(self.x_name, positive=True)
        self.formula = formula.subs(R, x)
        self.derivative = sp.diff(self.formula, x)
        self.at = exact(params.at)
        self.rate = exact(params.rate)
        self.derivative_at = self.derivative.subs(x, self.at)
        self.known = params.known
        if params.known == "length":
            self.answer = self.derivative_at * self.rate
        else:
            self.answer = self.rate / self.derivative_at
        self.given_word = self.x_word if params.known == "length" else self.q_word

    def given_latex(self) -> str:
        name = self.x_name if self.known == "length" else self.q_name
        return rf"\frac{{d{name}}}{{dt}} = {latex_value(self.rate)}"

    def chain_latex(self) -> str:
        q, x = self.q_name, self.x_name
        if self.known == "length":
            return rf"\frac{{d{q}}}{{dt}} = \frac{{d{q}}}{{d{x}}} \times \frac{{d{x}}}{{dt}}"
        return rf"\frac{{d{x}}}{{dt}} = \frac{{d{q}}}{{dt}} \div \frac{{d{q}}}{{d{x}}}"

    def answer_latex(self) -> str:
        q, x = self.q_name, self.x_name
        if self.known == "length":
            return (
                rf"\frac{{d{q}}}{{dt}} = {latex_with_pi(self.derivative_at, False)} \times "
                rf"{latex_value(self.rate)} = {latex_with_pi(self.answer)}"
            )
        return (
            rf"\frac{{d{x}}}{{dt}} = {latex_value(self.rate)} \div "
            rf"{latex_with_pi(self.derivative_at, False)} = {latex_with_pi(self.answer)}"
        )


def _shape(kind: str, centre: np.ndarray, size: float) -> tuple:
    """The shape of the given half-width at `centre`, and the line that measures it."""
    colour = style.CURVE_COLOUR
    if kind in ("circle", "sphere"):
        outline = Circle(radius=size, color=colour, fill_opacity=0.25).move_to(centre)
        if kind == "sphere":
            outline = VGroup(
                outline,
                Circle(radius=size, color=colour, stroke_width=2).stretch(0.3, 1).move_to(centre),
            )
        measure = Line(centre, centre + [size, 0, 0], color=style.RISE_COLOUR, stroke_width=5)
        return outline, measure
    square = Square(side_length=2 * size, color=colour, fill_opacity=0.25).move_to(centre)
    if kind == "cube":
        depth = np.array([0.45 * size, 0.35 * size, 0])
        back = Square(side_length=2 * size, color=colour, stroke_width=2).move_to(centre + depth)
        edges = VGroup(
            *(
                Line(square.get_corner(c), back.get_corner(c), color=colour, stroke_width=2)
                for c in ([1, 1, 0], [-1, 1, 0], [1, -1, 0])
            )
        )
        square = VGroup(square, back, edges)
        base = square[0]
    else:
        base = square
    measure = Line(
        base.get_corner([-1, -1, 0]),
        base.get_corner([1, -1, 0]),
        color=style.RISE_COLOUR,
        stroke_width=5,
    )
    return square, measure
