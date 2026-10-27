"""CircleTheorems: the O Level circle theorems, each drawn true to size from the given angle with
the unknown angle found and the theorem named (4024 4.7, 4.8; PRIMITIVES.md #29).

Theorems: the angle in a semicircle is 90°; the angle at the centre is twice the angle at the
circumference; angles in the same segment are equal; opposite angles of a cyclic quadrilateral
add to 180°; a tangent is perpendicular to the radius; tangents from a point are equal; and the
alternate segment theorem. The points are placed on the circle so that the given angle is
exactly the angle drawn.
"""

import math
from dataclasses import dataclass, field
from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import Circle, Dot, Line, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import (
    Diagram,
    angle_label_position,
    angle_mark,
    label,
    split_columns,
    text_line,
)
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import latex_value

Theorem = Literal[
    "semicircle",
    "centre",
    "same_segment",
    "cyclic_quadrilateral",
    "tangent_radius",
    "two_tangents",
    "alternate_segment",
]
# the range of the given angle that keeps each figure drawable
LIMITS = {
    "semicircle": (10, 80),
    "centre": (10, 85),
    "same_segment": (10, 80),
    "cyclic_quadrilateral": (30, 150),
    "tangent_radius": (15, 75),
    "two_tangents": (40, 140),
    "alternate_segment": (15, 80),
}


class CircleTheoremsParams(PrimitiveParams):
    theorem: Theorem
    given: Annotated[float, Field(gt=0, lt=180)] = Field(description="The known angle, degrees")
    given_at: Literal["circumference", "centre"] = Field(
        default="circumference", description="For centre: which angle is given"
    )


@dataclass
class _Figure:
    points: dict[str, tuple[float, float]]
    on_circle: set[str]
    segments: list[tuple[str, str]]
    given: tuple[str, str, str]
    find: tuple[str, str, str]
    steps: list[tuple[str, str]]  # (reason, working)
    answer: sp.Expr
    right: list[tuple[str, str, str]] = field(default_factory=list)
    lines: list[tuple[tuple[float, float], tuple[float, float]]] = field(default_factory=list)


class CircleTheorems(StagedPrimitive[CircleTheoremsParams]):
    primitive_id = "CircleTheorems"
    version = "1"
    topic = "Geometry"
    params_model = CircleTheoremsParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("figure", "*"), ("given", "*"), ("find", "*"), ("right", "*")],
    )

    def default_params(self) -> CircleTheoremsParams:
        return CircleTheoremsParams(theorem="centre", given=40)

    def validate(self, params: CircleTheoremsParams) -> list[PredicateFailure]:
        lo, hi = LIMITS[params.theorem]
        given = params.given
        if params.theorem == "centre" and params.given_at == "centre":
            lo, hi = 2 * lo, 2 * hi
        if not lo <= given <= hi:
            message = f"for {params.theorem} the given angle must be {lo}° to {hi}°"
            return [
                PredicateFailure(
                    kind="consistency",
                    predicate="angle_drawable",
                    message=message,
                    parameters=["given"],
                )
            ]
        return []

    def computed_values(self, params: CircleTheoremsParams) -> dict[str, str]:
        return {"x": latex_value(_figure(params).answer)}

    def build(self, params: CircleTheoremsParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        figure_box, working_box = split_columns(area, [1.1, 1], gap=0.3)
        fig = _figure(params)
        extent = [(-1.25, -1.25), (1.25, 1.25), *fig.points.values()]
        for a, b in fig.lines:
            extent += [a, b]
        diagram = Diagram(extent, figure_box, margin=0.25)
        p = {name: diagram.p(*xy) for name, xy in fig.points.items()}
        centre = diagram.p(0, 0)
        figure = VGroup(
            Circle(radius=diagram.length(1), color=style.TEXT_COLOUR, stroke_width=4).move_to(
                centre
            )
        )
        for a, b in fig.segments:
            figure.add(Line(p[a], p[b], stroke_width=3, color=style.TEXT_COLOUR))
        for a, b in fig.lines:
            figure.add(
                Line(diagram.p(*a), diagram.p(*b), stroke_width=3, color=style.TANGENT_COLOUR)
            )
        for name, point in p.items():
            figure.add(Dot(point, radius=0.05, color=style.TEXT_COLOUR))
            if name in fig.on_circle:
                direction = (point - centre) / max(np.linalg.norm(point - centre), 1e-9)
            else:
                direction = _away(name, fig, p)
            figure.add(label(name, size=30).move_to(point + 0.3 * direction))
        parts = {"figure": figure}
        for key, (v, a, b), colour, text in (
            ("given", fig.given, style.CURVE_COLOUR, rf"{latex_value(params.given)}^\circ"),
            ("find", fig.find, style.HIGHLIGHT_COLOUR, "x"),
        ):
            arc = angle_mark(p[v], p[a], p[b], radius=0.4, colour=colour)
            tex = label(text, colour=colour, size=28)
            tex.move_to(
                angle_label_position(p[v], p[a], p[b], 0.62 + max(tex.width, tex.height) / 2)
            )
            parts[key] = VGroup(arc, tex)
        if fig.right:
            parts["right"] = VGroup(
                *(
                    angle_mark(p[v], p[a], p[b], radius=0.3, colour=style.RISE_COLOUR)
                    for v, a, b in fig.right
                )
            )
        rows = []
        for reason, working in fig.steps:
            rows += [(reason, 26, style.HIGHLIGHT_COLOUR), (working, 34, style.TEXT_COLOUR)]
        mobjects = [label(tex, size=size, colour=colour) for tex, size, colour in rows]
        group = VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.25)
        style.fit_inside(group, working_box)
        for i in range(len(fig.steps)):
            parts[f"reason_{i + 1}"] = mobjects[2 * i]
            parts[f"working_{i + 1}"] = mobjects[2 * i + 1]
        parts["question"] = text_line(r"\text{Find the angle } x", upper)
        parts["answer"] = text_line(
            rf"x = {latex_value(fig.answer)}^\circ", lower, colour=style.HIGHLIGHT_COLOUR
        )
        return parts

    def stages(self, params: CircleTheoremsParams, level) -> list[Stage]:
        fig = _figure(params)
        right = ["right"] if fig.right else []
        steps = [
            stage("figure", "Here is the circle", 2.5, ["question", "figure", "given", "find"])
        ]
        for i, (reason, _) in enumerate(fig.steps, start=1):
            show = [f"reason_{i}", f"working_{i}"] + (right if i == 1 else [])
            steps.append(stage(f"step_{i}", _spoken(reason), 3.5, show, emphasise=[f"reason_{i}"]))
        steps.append(stage("answer", "So", 1.5, ["answer"], emphasise=["answer"]))

        def standard(s):
            return [s[0], *s[1:-2], combine("last", s[-2].description, 3.5, s[-2], s[-1])]

        def concise(s):
            return [s[0], combine("working", "Use the circle theorems", 4.5, *s[1:])]

        return by_level(level, steps, standard, concise)


def _on(degrees: float) -> tuple[float, float]:
    t = math.radians(degrees)
    return (math.cos(t), math.sin(t))


def _deg(value) -> str:
    return rf"{latex_value(sp.nsimplify(value))}^\circ"


def _figure(params: CircleTheoremsParams) -> _Figure:
    g = sp.nsimplify(params.given)
    t = params.theorem
    if t == "semicircle":
        x = 90 - g
        return _Figure(
            points={"A": _on(180), "B": _on(0), "C": _on(2 * float(g)), "O": (0, 0)},
            on_circle={"A", "B", "C"},
            segments=[("A", "B"), ("A", "C"), ("B", "C")],
            given=("A", "B", "C"),
            find=("B", "C", "A"),
            right=[("C", "A", "B")],
            steps=[
                (r"\text{the angle in a semicircle is } 90^\circ", r"A\hat{C}B = 90^\circ"),
                (
                    r"\text{angles in a triangle add to } 180^\circ",
                    rf"x = 180^\circ - 90^\circ - {_deg(g)} = {_deg(x)}",
                ),
            ],
            answer=x,
        )
    if t == "centre":
        at_centre = params.given_at == "centre"
        half = g / 2 if at_centre else g
        x = half if at_centre else 2 * g
        h = float(half)
        given, find = ("O", "A", "B"), ("C", "A", "B")
        if not at_centre:
            given, find = find, given
        working = (
            rf"x = {_deg(g)} \div 2 = {_deg(x)}"
            if at_centre
            else rf"x = 2 \times {_deg(g)} = {_deg(x)}"
        )
        return _Figure(
            points={"A": _on(270 - h), "B": _on(270 + h), "C": _on(100), "O": (0, 0)},
            on_circle={"A", "B", "C"},
            segments=[("A", "C"), ("B", "C"), ("O", "A"), ("O", "B")],
            given=given,
            find=find,
            steps=[
                (
                    _lines(
                        r"\text{angle at the centre} =",
                        r"2 \times \text{angle at the circumference}",
                    ),
                    working,
                )
            ],
            answer=x,
        )
    if t == "same_segment":
        h = float(g)
        return _Figure(
            points={"A": _on(270 - h), "B": _on(270 + h), "C": _on(135), "D": _on(50)},
            on_circle={"A", "B", "C", "D"},
            segments=[("A", "C"), ("B", "C"), ("A", "D"), ("B", "D")],
            given=("C", "A", "B"),
            find=("D", "A", "B"),
            steps=[(r"\text{angles in the same segment are equal}", rf"x = {_deg(g)}")],
            answer=g,
        )
    if t == "cyclic_quadrilateral":
        x = 180 - g
        h = float(g)
        return _Figure(
            points={"A": _on(180), "B": _on(h), "C": _on(0), "D": _on(-h)},
            on_circle={"A", "B", "C", "D"},
            segments=[("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")],
            given=("A", "B", "D"),
            find=("C", "B", "D"),
            steps=[
                (
                    _lines(
                        r"\text{opposite angles of a cyclic}",
                        r"\text{quadrilateral add to } 180^\circ",
                    ),
                    rf"x = 180^\circ - {_deg(g)} = {_deg(x)}",
                )
            ],
            answer=x,
        )
    if t == "tangent_radius":
        x = 90 - g
        d = 1 / math.tan(math.radians(float(g)))
        return _Figure(
            points={"O": (0, 0), "T": (0, -1), "P": (d, -1)},
            on_circle={"T"},
            segments=[("O", "T"), ("O", "P")],
            lines=[((-0.6, -1), (d + 0.4, -1))],
            given=("P", "O", "T"),
            find=("O", "T", "P"),
            right=[("T", "O", "P")],
            steps=[
                (r"\text{a tangent is perpendicular to the radius}", r"O\hat{T}P = 90^\circ"),
                (
                    r"\text{angles in a triangle add to } 180^\circ",
                    rf"x = 180^\circ - 90^\circ - {_deg(g)} = {_deg(x)}",
                ),
            ],
            answer=x,
        )
    if t == "two_tangents":
        alpha = 90 - float(g) / 2
        d = 1 / math.cos(math.radians(alpha))
        x = (180 - g) / 2
        return _Figure(
            points={"O": (0, 0), "A": _on(alpha), "B": _on(-alpha), "P": (d, 0)},
            on_circle={"A", "B"},
            segments=[("A", "B"), ("O", "A"), ("O", "B")],
            lines=[(_on(alpha), (d, 0)), (_on(-alpha), (d, 0))],
            given=("P", "A", "B"),
            find=("A", "B", "P"),
            steps=[
                (
                    _lines(r"\text{tangents from a point are}", r"\text{equal, so } PA = PB"),
                    r"\text{triangle } PAB \text{ is isosceles}",
                ),
                (
                    _lines(r"\text{base angles are equal;}", r"\text{angles add to } 180^\circ"),
                    rf"x = (180^\circ - {_deg(g)}) \div 2 = {_deg(x)}",
                ),
            ],
            answer=x,
        )
    # alternate segment: tangent at A, chord AB, C in the other segment
    h = float(g)
    return _Figure(
        points={"A": _on(270), "B": _on(270 + 2 * h), "C": _on(90 + h), "T": (1.0, -1)},
        on_circle={"A", "B", "C"},
        segments=[("A", "B"), ("A", "C"), ("B", "C")],
        lines=[((-1.1, -1), (1.1, -1))],
        given=("A", "T", "B"),
        find=("C", "A", "B"),
        steps=[(r"\text{the alternate segment theorem}", rf"x = {_deg(g)}")],
        answer=g,
    )


def _away(name: str, fig: _Figure, p: dict) -> np.ndarray:
    """A label direction for a point off the circle: away from the lines that meet there."""
    ends = [p[b] for a, b in fig.segments if a == name] + [
        p[a] for a, b in fig.segments if b == name
    ]
    if name == "O" or not ends:
        ends = ends or [p[n] for n in fig.on_circle]
    mean = sum((e - p[name]) / max(np.linalg.norm(e - p[name]), 1e-9) for e in ends)
    norm = np.linalg.norm(mean)
    return -mean / norm if norm > 1e-6 else np.array([0.0, -1.0, 0.0])


def _lines(*rows: str) -> str:
    """A reason over several lines."""
    return r"\begin{array}{l}" + r"\\".join(rows) + r"\end{array}"


def _spoken(tex: str) -> str:
    """The narration for a reason: the \\text parts read as a sentence."""
    for markup in (r"\begin{array}{l}", r"\end{array}"):
        tex = tex.replace(markup, "")
    tex = tex.replace("\\\\", " ")
    words = tex.replace(r"\text{", "").replace("}", "").replace("^\\circ", " degrees")
    words = words.replace(r"\times", "times").replace("=", "equals")
    return words[0].upper() + words[1:]
