"""SymmetryReveal: the lines of symmetry of a shape, and its order of rotational symmetry shown by
turning a copy until it fits again (4024 4.5; PRIMITIVES.md #32).

Shapes: the special triangles and quadrilaterals, regular polygons, and a polygon given by its
vertices. The lines of symmetry and the order are found from the vertices, not looked up: a
line counts if reflecting the vertices in it gives the same vertices, and the order is the
number of turns under 360° that give the same vertices.
"""

import math
from typing import Annotated, Literal

import numpy as np
from manim import DashedLine, Polygon, Rotate, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import Diagram, label, split_columns, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage

Shape = Literal[
    "equilateral_triangle",
    "isosceles_triangle",
    "square",
    "rectangle",
    "rhombus",
    "parallelogram",
    "kite",
    "isosceles_trapezium",
    "regular_polygon",
    "custom",
]
NAMES = {
    "equilateral_triangle": "an equilateral triangle",
    "isosceles_triangle": "an isosceles triangle",
    "square": "a square",
    "rectangle": "a rectangle",
    "rhombus": "a rhombus",
    "parallelogram": "a parallelogram",
    "kite": "a kite",
    "isosceles_trapezium": "an isosceles trapezium",
    "custom": "the shape",
}
TOLERANCE = 1e-4  # relative to the shape's size


class SymmetryRevealParams(PrimitiveParams):
    shape: Shape
    sides: Annotated[int, Field(ge=3, le=12)] = Field(
        default=5, description="For regular_polygon: the number of sides"
    )
    vertices: list[tuple[float, float]] | None = Field(
        default=None, max_length=12, description="For custom: the corners in order"
    )


class SymmetryReveal(StagedPrimitive[SymmetryRevealParams]):
    primitive_id = "SymmetryReveal"
    version = "1"
    topic = "Geometry"
    params_model = SymmetryRevealParams
    layout = LayoutContract(
        region=style.GRAPH_REGION, allowed_overlaps=[("shape", "*"), ("lines", "*")]
    )

    def default_params(self) -> SymmetryRevealParams:
        return SymmetryRevealParams(shape="rectangle")

    def validate(self, params: SymmetryRevealParams) -> list[PredicateFailure]:
        if params.shape == "custom" and (params.vertices is None or len(params.vertices) < 3):
            return [
                PredicateFailure(
                    kind="consistency",
                    predicate="needs_vertices",
                    message="a custom shape needs at least three vertices",
                    parameters=["vertices"],
                )
            ]
        return []

    def computed_values(self, params: SymmetryRevealParams) -> dict[str, str]:
        points = _vertices(params)
        return {"lines": str(len(_lines(points))), "order": str(_order(points))}

    def build(self, params: SymmetryRevealParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        figure_box, working_box = split_columns(area, [1.2, 1], gap=0.3)
        points = _vertices(params)
        lines = _lines(points)
        reach = 1.25 * max(np.hypot(*p) for p in points)
        diagram = Diagram([(-reach, -reach), (reach, reach)], figure_box, margin=0.2)
        corners = [diagram.p(*p) for p in points]
        shape = Polygon(
            *corners,
            color=style.TEXT_COLOUR,
            stroke_width=4,
            fill_color=style.CURVE_COLOUR,
            fill_opacity=0.35,
        )
        parts = {"shape": shape}
        mirror = VGroup()
        for angle in lines:
            direction = np.array([math.cos(angle), math.sin(angle)])
            mirror.add(
                DashedLine(
                    diagram.p(*(-reach * direction)),
                    diagram.p(*(reach * direction)),
                    color=style.HIGHLIGHT_COLOUR,
                    stroke_width=3,
                )
            )
        parts["lines"] = mirror
        order = _order(points)
        rows = [
            rf"\text{{lines of symmetry: {len(lines)}}}",
            rf"\text{{order of rotational symmetry: {order}}}",
        ]
        mobjects = [label(tex, size=32) for tex in rows]
        VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.5)
        style.fit_inside(VGroup(*mobjects), working_box)
        parts["count_lines"], parts["count_order"] = mobjects
        name = _name(params)
        parts["question"] = text_line(rf"\text{{The symmetry of {name}}}", upper)
        parts["answer"] = text_line(
            rf"\text{{{len(lines)} line{'s' if len(lines) != 1 else ''}, order {order}}}",
            lower,
            colour=style.HIGHLIGHT_COLOUR,
        )
        self._turn = (shape, order)
        return parts

    def turn(self, scene, parts, level, run_time, min_run_time):
        """A copy turns by 360°/order at a time and fits the shape after each turn."""
        shape, order = self._turn
        copy = shape.copy().set_fill(opacity=0).set_stroke(style.HIGHLIGHT_COLOUR, width=5)
        scene.add(copy)
        hold = min(0.15, 0.2 * run_time)
        animation_time = min(max(min_run_time, 0.7 * run_time), run_time - hold)
        turns = max(order, 1)
        for _ in range(turns):
            scene.play(
                Rotate(copy, angle=-2 * math.pi / turns, about_point=shape.get_center_of_mass()),
                run_time=animation_time / turns,
            )
        scene.remove(copy)
        scene.wait(run_time - animation_time)

    def stages(self, params: SymmetryRevealParams, level) -> list[Stage]:
        points = _vertices(params)
        count, order = len(_lines(points)), _order(points)
        line_words = (
            f"It has {count} line{'s' if count != 1 else ''} of symmetry: fold along "
            f"one and the halves match"
            if count
            else "No line of symmetry: no fold makes the halves match"
        )
        turn_words = (
            f"Turn it: it fits {order} times in a full turn, so the order is {order}"
            if order > 1
            else "Turn it: it only fits again after a full turn, so the order is 1"
        )
        steps = [
            stage("shape", "Here is the shape", 2.0, ["question", "shape"]),
            stage("lines", line_words, 3.5, ["lines", "count_lines"], emphasise=["lines"]),
            stage("turn", turn_words, 4.5, ["count_order"], motion="turn"),
            stage("answer", "So", 1.5, ["answer"], emphasise=["answer"]),
        ]

        def concise(s):
            return [combine("lines", s[1].description, 4.0, s[0], s[1]), s[2], s[3]]

        return by_level(level, steps, lambda s: s, concise)


def _name(params: SymmetryRevealParams) -> str:
    if params.shape == "regular_polygon":
        names = {
            3: "triangle",
            4: "square",
            5: "pentagon",
            6: "hexagon",
            7: "heptagon",
            8: "octagon",
            9: "nonagon",
            10: "decagon",
            12: "dodecagon",
        }
        return f"a regular {names.get(params.sides, f'{params.sides}-gon')}"
    return NAMES[params.shape]


def _vertices(params: SymmetryRevealParams) -> list[tuple[float, float]]:
    """The corners, centred on the origin (their mean)."""
    s = params.shape
    if s == "regular_polygon" or s == "equilateral_triangle" or s == "square":
        n = {"equilateral_triangle": 3, "square": 4}.get(s, params.sides)
        offset = math.pi / 2 if n % 2 else math.pi / 2 - math.pi / n
        pts = [
            (math.cos(offset + 2 * math.pi * k / n), math.sin(offset + 2 * math.pi * k / n))
            for k in range(n)
        ]
    else:
        pts = {
            "isosceles_triangle": [(-0.6, -0.8), (0.6, -0.8), (0, 1.0)],
            "rectangle": [(-1.2, -0.7), (1.2, -0.7), (1.2, 0.7), (-1.2, 0.7)],
            "rhombus": [(0, -1.0), (0.65, 0), (0, 1.0), (-0.65, 0)],
            "parallelogram": [(-1.2, -0.6), (0.6, -0.6), (1.2, 0.6), (-0.6, 0.6)],
            "kite": [(0, -1.2), (0.6, 0.3), (0, 0.8), (-0.6, 0.3)],
            "isosceles_trapezium": [(-1.1, -0.6), (1.1, -0.6), (0.6, 0.6), (-0.6, 0.6)],
            "custom": [tuple(v) for v in params.vertices or []],
        }[s]
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return [(x - cx, y - cy) for x, y in pts]


def _same(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> bool:
    scale = max(max(abs(x), abs(y)) for x, y in a) or 1
    return all(min(math.hypot(p[0] - q[0], p[1] - q[1]) for q in b) < TOLERANCE * scale for p in a)


def _lines(points) -> list[float]:
    """Angles of the lines of symmetry through the centre."""
    candidates = []
    for k, (x, y) in enumerate(points):
        nx, ny = points[(k + 1) % len(points)]
        candidates += [math.atan2(y, x), math.atan2((y + ny) / 2, (x + nx) / 2)]
    found: list[float] = []
    for angle in candidates:
        angle %= math.pi
        if any(abs(angle - f) < 1e-6 or abs(abs(angle - f) - math.pi) < 1e-6 for f in found):
            continue
        c, s = math.cos(2 * angle), math.sin(2 * angle)
        mirrored = [(c * x + s * y, s * x - c * y) for x, y in points]
        if _same(points, mirrored):
            found.append(angle)
    return found


def _order(points) -> int:
    for n in range(len(points), 1, -1):
        t = 2 * math.pi / n
        turned = [
            (x * math.cos(t) - y * math.sin(t), x * math.sin(t) + y * math.cos(t))
            for x, y in points
        ]
        if _same(points, turned):
            return n
    return 1
