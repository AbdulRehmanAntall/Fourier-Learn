"""CompassConstruction: ruler-and-compasses constructions arc by arc: the perpendicular bisector
of a line, the bisector of an angle, and a triangle from its three sides (4024 4.2;
PRIMITIVES.md #34).

Every arc is drawn at its true radius about its true centre, so the arcs cross where the
construction says: equal arcs from both ends of AB meet on the perpendicular bisector, equal
arcs from two points the same distance along the arms of an angle meet on its bisector, and
arcs of the other two sides' lengths from the ends of the base meet at the third vertex.
"""

import math
from typing import Annotated, Literal

import numpy as np
from manim import Arc, Dot, Line, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import Diagram, angle_mark, label, split_columns, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf

Length = Annotated[float, Field(gt=0, le=100)]
ARC = style.RUN_COLOUR
MARGIN = math.radians(14)  # how far each arc runs past the crossing


class CompassConstructionParams(PrimitiveParams):
    construction: Literal["perpendicular_bisector", "angle_bisector", "triangle"]
    length: Length = Field(default=8, description="For perpendicular_bisector: AB")
    angle: Annotated[float, Field(gt=10, lt=170)] = Field(
        default=70, description="For angle_bisector: the angle in degrees"
    )
    sides: list[Length] | None = Field(
        default=None, min_length=3, max_length=3, description="For triangle: AB, BC, CA"
    )
    unit: Literal["cm", "m", "mm", ""] = "cm"


class CompassConstruction(StagedPrimitive[CompassConstructionParams]):
    primitive_id = "CompassConstruction"
    version = "1"
    topic = "Geometry"
    params_model = CompassConstructionParams
    layout = LayoutContract(
        region=style.GRAPH_REGION, allowed_overlaps=[("base", "*"), ("arc_*", "*"), ("result", "*")]
    )

    def default_params(self) -> CompassConstructionParams:
        return CompassConstructionParams(construction="perpendicular_bisector")

    def validate(self, params: CompassConstructionParams) -> list[PredicateFailure]:
        if params.construction == "triangle":
            if params.sides is None:
                return [_failure("needs_sides", "give the three sides", "sides")]
            a, b, c = sorted(params.sides)
            if a + b <= c:
                return [_failure("triangle_exists", "these sides make no triangle", "sides")]
        return []

    def computed_values(self, params: CompassConstructionParams) -> dict[str, str]:
        if params.construction == "angle_bisector":
            return {"half_angle": format_sf(params.angle / 2)}
        if params.construction == "perpendicular_bisector":
            return {"half_length": format_sf(params.length / 2)}
        ab, bc, ca = params.sides
        angle_a = math.degrees(math.acos((ab**2 + ca**2 - bc**2) / (2 * ab * ca)))
        return {"angle_A": f"{angle_a:.1f}"}

    def build(self, params: CompassConstructionParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        figure_box, working_box = split_columns(area, [1.3, 1], gap=0.3)
        unit = rf"\text{{ {params.unit}}}" if params.unit else ""
        build = {
            "perpendicular_bisector": _bisector,
            "angle_bisector": _angle,
            "triangle": _triangle,
        }[params.construction]
        parts, rows, question, answer = build(params, figure_box, unit)
        mobjects = [label(tex, size=28) for tex in rows]
        group = VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.28)
        style.fit_inside(group, working_box)
        for i, mob in enumerate(mobjects, start=1):
            parts[f"row_{i}"] = mob
        parts["question"] = text_line(question, upper)
        parts["answer"] = text_line(answer, lower, colour=style.HIGHLIGHT_COLOUR)
        return parts

    def stages(self, params: CompassConstructionParams, level) -> list[Stage]:
        c = params.construction
        if c == "perpendicular_bisector":
            words = [
                ("base", "Draw the line AB"),
                ("arc_a", "Open the compasses to more than half of AB; draw arcs from A"),
                ("arc_b", "Keep the same radius; draw arcs from B to cross them"),
                ("result", "Join the two crossings: the perpendicular bisector of AB"),
            ]
        elif c == "angle_bisector":
            words = [
                ("base", "Here is the angle"),
                ("arc_a", "An arc from the vertex cuts both arms"),
                ("arc_b", "Equal arcs from those two points cross inside the angle"),
                ("result", "Join the vertex to the crossing: it bisects the angle"),
            ]
        else:
            words = [
                ("base", "Draw the base AB"),
                ("arc_a", "Open the compasses to CA and draw an arc from A"),
                ("arc_b", "Open them to BC and draw an arc from B"),
                ("result", "C is where the arcs cross: join it to A and B"),
            ]
        steps = [stage("question", "Read the construction", 1.5, ["question"])]
        for i, (name, text) in enumerate(words, start=1):
            steps.append(stage(name, text, 3.0, [name, f"row_{i}"]))
        steps.append(stage("answer", "So", 1.5, ["answer"], emphasise=["result", "answer"]))

        def standard(s):
            return [combine("setup", s[1].description, 3.0, s[0], s[1]), *s[2:]]

        def concise(s):
            return [
                combine("setup", s[1].description, 3.0, s[0], s[1]),
                combine("arcs", "Draw the arcs", 4.0, s[2], s[3]),
                combine("result", s[4].description, 3.0, s[4], s[5]),
            ]

        return by_level(level, steps, standard, concise)


def _arc(diagram: Diagram, centre, radius: float, towards: list[float]) -> Arc:
    """An arc about `centre` (maths units) covering the directions `towards` (radians)."""
    start, end = min(towards) - MARGIN, max(towards) + MARGIN
    return Arc(
        radius=diagram.length(radius),
        start_angle=start,
        angle=end - start,
        arc_center=diagram.p(*centre),
        color=ARC,
        stroke_width=3,
    )


def _direction(frm, to) -> float:
    return math.atan2(to[1] - frm[1], to[0] - frm[0])


def _bisector(params, box, unit):
    half = params.length / 2
    radius = 0.75 * params.length
    rise = math.sqrt(radius**2 - half**2)
    a, b, top, bottom = (-half, 0), (half, 0), (0, rise), (0, -rise)
    reach = rise + 0.15 * params.length
    diagram = Diagram([a, b, (0, reach), (0, -reach)], box, margin=0.45)
    pa, pb = diagram.p(*a), diagram.p(*b)
    parts = {
        "base": VGroup(
            Line(pa, pb, stroke_width=4),
            Dot(pa),
            Dot(pb),
            label("A", size=28).next_to(pa, [-1, 0, 0], buff=0.12),
            label("B", size=28).next_to(pb, [1, 0, 0], buff=0.12),
            label(rf"{_plain(params.length)}{unit}", size=24).next_to(
                diagram.p(-half / 2, 0), [0, -1, 0], buff=0.12
            ),
        ),
        "arc_a": VGroup(
            _arc(diagram, a, radius, [_direction(a, top)]),
            _arc(diagram, a, radius, [_direction(a, bottom)]),
        ),
        "arc_b": VGroup(
            _arc(diagram, b, radius, [_direction(b, top)]),
            _arc(diagram, b, radius, [_direction(b, bottom)]),
        ),
    }
    mid = diagram.p(0, 0)
    parts["result"] = VGroup(
        Line(
            diagram.p(0, -reach), diagram.p(0, reach), color=style.HIGHLIGHT_COLOUR, stroke_width=4
        ),
        Dot(diagram.p(*top), color=style.HIGHLIGHT_COLOUR),
        Dot(diagram.p(*bottom), color=style.HIGHLIGHT_COLOUR),
        angle_mark(mid, pb, diagram.p(*top), radius=0.25, colour=style.HIGHLIGHT_COLOUR),
    )
    rows = [
        r"1.\ \text{draw } AB",
        rf"2.\ \text{{arcs from A, radius {_plain(radius)}}}",
        r"3.\ \text{same radius from B}",
        r"4.\ \text{join the crossings}",
    ]
    answer = (
        rf"\text{{It cuts AB at its midpoint, {_plain(half)}}}{unit}"
        r"\text{ from each end, at }90^\circ"
    )
    return parts, rows, r"\text{Construct the perpendicular bisector of } AB", answer


def _angle(params, box, unit):
    theta = math.radians(params.angle)
    o, p, q = (0.0, 0.0), (1.0, 0.0), (math.cos(theta), math.sin(theta))
    r1, arm = 0.55, 1.6
    pp, qq = (r1, 0.0), (r1 * math.cos(theta), r1 * math.sin(theta))
    # the crossing of equal arcs from pp and qq, on the bisector; the radius must be more than
    # half the gap between them or the arcs never meet
    mid_angle = theta / 2
    d = math.dist(pp, qq) / 2
    r2 = max(0.45, d + 0.15)
    along = r1 * math.cos(mid_angle) + math.sqrt(max(r2**2 - d**2, 0))
    cross = (along * math.cos(mid_angle), along * math.sin(mid_angle))
    diagram = Diagram([o, (arm, 0), (arm * q[0], arm * q[1]), (-0.2, -0.2)], box, margin=0.4)
    po = diagram.p(*o)
    parts = {
        "base": VGroup(
            Line(po, diagram.p(arm, 0), stroke_width=4),
            Line(po, diagram.p(arm * q[0], arm * q[1]), stroke_width=4),
            angle_mark(po, diagram.p(*p), diagram.p(*q), radius=0.3),
            # between the first arm and the bisector, clear of both
            label(rf"{_plain(params.angle)}^\circ", size=24).move_to(
                po + 0.6 * np.array([math.cos(theta / 4), math.sin(theta / 4), 0])
            ),
        ),
        "arc_a": _arc(diagram, o, r1, [0.0, theta]),
        "arc_b": VGroup(
            _arc(diagram, pp, r2, [_direction(pp, cross)]),
            _arc(diagram, qq, r2, [_direction(qq, cross)]),
            Dot(diagram.p(*pp), radius=0.05),
            Dot(diagram.p(*qq), radius=0.05),
        ),
    }
    end = (arm * math.cos(mid_angle), arm * math.sin(mid_angle))
    parts["result"] = VGroup(
        Line(po, diagram.p(*end), color=style.HIGHLIGHT_COLOUR, stroke_width=4),
        Dot(diagram.p(*cross), color=style.HIGHLIGHT_COLOUR),
    )
    half = _plain(params.angle / 2)
    rows = [
        r"1.\ \text{the angle at the vertex}",
        r"2.\ \text{an arc cuts both arms}",
        r"3.\ \text{equal arcs from those points}",
        r"4.\ \text{join the vertex to the crossing}",
    ]
    answer = rf"\text{{Each half is }} {_plain(params.angle)}^\circ \div 2 = {half}^\circ"
    return parts, rows, rf"\text{{Bisect an angle of }} {_plain(params.angle)}^\circ", answer


def _triangle(params, box, unit):
    ab, bc, ca = params.sides
    x = (ab**2 + ca**2 - bc**2) / (2 * ab)
    y = math.sqrt(max(ca**2 - x**2, 0))
    a, b, c = (0.0, 0.0), (ab, 0.0), (x, y)
    diagram = Diagram([a, b, c, (0, -0.1 * ab), (x, y + 0.15 * ab)], box, margin=0.5)
    pa, pb, pc = diagram.p(*a), diagram.p(*b), diagram.p(*c)
    parts = {
        "base": VGroup(
            Line(pa, pb, stroke_width=4),
            Dot(pa),
            Dot(pb),
            label("A", size=28).next_to(pa, [-1, -0.5, 0], buff=0.1),
            label("B", size=28).next_to(pb, [1, -0.5, 0], buff=0.1),
            label(rf"{_plain(ab)}{unit}", size=24).next_to((pa + pb) / 2, [0, -1, 0], buff=0.12),
        ),
        "arc_a": _arc(diagram, a, ca, [_direction(a, c)]),
        "arc_b": _arc(diagram, b, bc, [_direction(b, c)]),
    }
    centre = (pa + pb + pc) / 3
    parts["result"] = VGroup(
        Line(pa, pc, stroke_width=4, color=style.HIGHLIGHT_COLOUR),
        Line(pb, pc, stroke_width=4, color=style.HIGHLIGHT_COLOUR),
        Dot(pc, color=style.HIGHLIGHT_COLOUR),
        label("C", size=28).next_to(pc, [0, 1, 0], buff=0.15),
        label(rf"{_plain(ca)}{unit}", size=24).move_to(
            (pa + pc) / 2 + 0.35 * _unit((pa + pc) / 2 - centre)
        ),
        label(rf"{_plain(bc)}{unit}", size=24).move_to(
            (pb + pc) / 2 + 0.35 * _unit((pb + pc) / 2 - centre)
        ),
    )
    rows = [
        rf"1.\ AB = {_plain(ab)}",
        rf"2.\ \text{{arc from A, radius }} {_plain(ca)}",
        rf"3.\ \text{{arc from B, radius }} {_plain(bc)}",
        r"4.\ \text{join the crossing to A and B}",
    ]
    sides = ", ".join(_plain(s) for s in params.sides)
    return (
        parts,
        rows,
        rf"\text{{Construct the triangle with sides {sides}}}{unit}",
        r"\text{Triangle } ABC",
    )


def _unit(v):
    return v / max(np.linalg.norm(v), 1e-9)


def _plain(value) -> str:
    return format_sf(value, 6)


def _failure(predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=[parameter]
    )
