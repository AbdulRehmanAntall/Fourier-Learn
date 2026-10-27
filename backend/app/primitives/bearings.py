"""Bearings: three-figure bearings measured clockwise from north, the back bearing, and how far
east and north a journey goes (4024 4.3, with 6.2; PRIMITIVES.md #31).

A north line stands at each point. The bearing of B from A is the clockwise turn from north at A
to the line AB, written with three figures (065°). The back bearing, of A from B, differs by
180°: add 180° if the bearing is under 180°, otherwise take 180° away; the parallel north lines
make this the co-interior angle fact. A journey of d on bearing θ goes d sin θ east and d cos θ
north.
"""

import math
from typing import Annotated, Literal

import numpy as np
from manim import Arc, Arrow, Dot, Line, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import Diagram, label, split_columns, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf


class BearingsParams(PrimitiveParams):
    bearing: Annotated[float, Field(gt=0, lt=360)] = Field(description="Bearing of B from A")
    distance: Annotated[float, Field(gt=0, le=100_000)] | None = Field(
        default=None, description="AB, for components"
    )
    find: Literal["back_bearing", "components"] = "back_bearing"
    unit: Literal["km", "m", "nautical miles", ""] = "km"


class Bearings(StagedPrimitive[BearingsParams]):
    primitive_id = "Bearings"
    version = "1"
    topic = "Geometry"
    params_model = BearingsParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("north_*", "*"), ("turn_*", "*"), ("path", "*"), ("components", "*")],
    )

    def default_params(self) -> BearingsParams:
        return BearingsParams(bearing=65)

    def validate(self, params: BearingsParams) -> list[PredicateFailure]:
        if params.find == "components" and params.distance is None:
            return [
                PredicateFailure(
                    kind="consistency",
                    predicate="needs_distance",
                    message="components need the distance AB",
                    parameters=["distance"],
                )
            ]
        return []

    def computed_values(self, params: BearingsParams) -> dict[str, str]:
        if params.find == "back_bearing":
            return {"back_bearing": _three(_back(params.bearing))}
        east, north = _components(params)
        return {"east": format_sf(east), "north": format_sf(north)}

    def build(self, params: BearingsParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        figure_box, working_box = split_columns(area, [1.15, 1], gap=0.3)
        theta = math.radians(params.bearing)
        b_point = (math.sin(theta), math.cos(theta))
        north = 0.55
        diagram = Diagram(
            [
                (0, 0),
                b_point,
                (0, north + 0.15),
                (b_point[0], b_point[1] + north + 0.15),
                (-0.3, -0.3),
                (b_point[0] + 0.3, b_point[1] - 0.3),
            ],
            figure_box,
            margin=0.35,
        )
        a, b = diagram.p(0, 0), diagram.p(*b_point)
        length = diagram.length(north)
        parts = {
            "path": VGroup(
                Line(a, b, stroke_width=4),
                Dot(a),
                Dot(b),
                label("A", size=30).move_to(a + 0.24 * _gap(a, b, params.bearing)),
                label("B", size=30).move_to(b + 0.24 * _gap(b, a, _back(params.bearing))),
            ),
            "north_a": _north(a, length),
            "turn_a": _turn(
                a, params.bearing, 0.5, style.HIGHLIGHT_COLOUR, rf"{_three(params.bearing)}^\circ"
            ),
        }
        rows: list[str]
        if params.find == "back_bearing":
            back = _back(params.bearing)
            parts["north_b"] = _north(b, length)
            parts["turn_b"] = _turn(b, back, 0.5, style.TANGENT_COLOUR, rf"{_three(back)}^\circ")
            sign = "+" if params.bearing < 180 else "-"
            rows = [
                r"\text{the north lines are parallel}",
                rf"\text{{back bearing}} = {_plain(params.bearing)}^\circ {sign} 180^\circ",
                rf"= {_three(back)}^\circ",
            ]
            answer = rf"\text{{Bearing of A from B}} = {_three(back)}^\circ"
            question = (
                rf"\text{{B is on a bearing of }} {_three(params.bearing)}^\circ "
                r"\text{ from A. Find the bearing of A from B.}"
            )
        else:
            east, north_part = _components(params)
            corner = diagram.p(b_point[0], 0)
            unit = rf"\text{{ {params.unit}}}" if params.unit else ""
            parts["components"] = VGroup(
                Line(a, corner, stroke_width=3, color=style.RUN_COLOUR),
                Line(corner, b, stroke_width=3, color=style.RISE_COLOUR),
                label(rf"{format_sf(abs(east))}{unit}", colour=style.RUN_COLOUR, size=26).next_to(
                    corner + 0.4 * (a - corner), [0, 1 if b_point[1] >= 0 else -1, 0], buff=0.12
                ),
                label(
                    rf"{format_sf(abs(north_part))}{unit}", colour=style.RISE_COLOUR, size=26
                ).next_to((corner + b) / 2, [1 if b_point[0] >= 0 else -1, 0, 0], buff=0.12),
            )
            d = _plain(params.distance)
            rows = [
                rf"\text{{east}} = {d}\sin {_plain(params.bearing)}^\circ = {format_sf(east)}",
                rf"\text{{north}} = {d}\cos {_plain(params.bearing)}^\circ = "
                rf"{format_sf(north_part)}",
            ]
            answer = (
                rf"\text{{{format_sf(abs(east))} {params.unit} "
                rf"{'east' if east >= 0 else 'west'}, {format_sf(abs(north_part))} "
                rf"{params.unit} {'north' if north_part >= 0 else 'south'}}}"
            )
            question = (
                rf"\text{{B is {d} {params.unit} from A on a bearing of }} "
                rf"{_three(params.bearing)}^\circ"
            )
        mobjects = [label(tex, size=32) for tex in rows]
        group = VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.3)
        style.fit_inside(group, working_box)
        for i, mob in enumerate(mobjects, start=1):
            parts[f"row_{i}"] = mob
        parts["question"] = text_line(question, upper, size=34)
        parts["answer"] = text_line(answer, lower, colour=style.HIGHLIGHT_COLOUR)
        return parts

    def stages(self, params: BearingsParams, level) -> list[Stage]:
        steps = [
            stage("journey", "Here is the journey from A to B", 2.0, ["question", "path"]),
            stage(
                "bearing",
                "A bearing is measured from north, turning clockwise, written with three figures",
                3.5,
                ["north_a", "turn_a"],
                emphasise=["turn_a"],
            ),
        ]
        if params.find == "back_bearing":
            steps += [
                stage(
                    "north_b",
                    "Draw the north line at B: it is parallel to the one at A",
                    3.0,
                    ["north_b", "row_1"],
                ),
                stage(
                    "back",
                    "The back bearing differs by 180 degrees",
                    3.5,
                    ["turn_b", "row_2", "row_3"],
                    emphasise=["turn_b"],
                ),
            ]
        else:
            steps += [
                stage(
                    "components",
                    "Split the journey into east and north with the right-"
                    "angled triangle: sine for east, cosine for north",
                    4.0,
                    ["components", "row_1", "row_2"],
                ),
            ]
        steps.append(stage("answer", "So", 1.5, ["answer"], emphasise=["answer"]))

        def standard(s):
            return [combine("setup", s[1].description, 4.0, s[0], s[1]), *s[2:]]

        def concise(s):
            return [
                combine("setup", s[1].description, 4.0, s[0], s[1]),
                combine("working", "Work it out", 4.0, *s[2:]),
            ]

        return by_level(level, steps, standard, concise)


def _three(value: float) -> str:
    """A three-figure bearing: 065, 180, 247.5."""
    whole = int(value)
    text = f"{whole:03d}"
    if value != whole:
        text += f"{value - whole:.1f}"[1:]
    return text


def _plain(value: float) -> str:
    return format_sf(value, 6)


def _back(bearing: float) -> float:
    return bearing + 180 if bearing < 180 else bearing - 180


def _components(params: BearingsParams) -> tuple[float, float]:
    t = math.radians(params.bearing)
    return params.distance * math.sin(t), params.distance * math.cos(t)


def _gap(point: np.ndarray, other: np.ndarray, turn: float) -> np.ndarray:
    """A unit direction for a point's letter, in the widest gap between its north line, the line
    to the other point and the middle of its turn."""
    to_other = other - point
    angles = sorted(
        [
            math.pi / 2,
            math.atan2(to_other[1], to_other[0]),
            math.pi / 2 - math.radians(turn) / 2,
        ]
    )
    following = angles[1:] + [angles[0] + 2 * math.pi]
    width, start = max((b - a, a) for a, b in zip(angles, following, strict=True))
    middle = start + width / 2
    return np.array([math.cos(middle), math.sin(middle), 0.0])


def _north(point: np.ndarray, length: float) -> VGroup:
    arrow = Arrow(
        point,
        point + np.array([0, length, 0]),
        buff=0,
        stroke_width=3,
        max_tip_length_to_length_ratio=0.18,
        color=style.TEXT_COLOUR,
    )
    return VGroup(arrow, label("N", size=26).next_to(arrow, [0, 1, 0], buff=0.08))


def _turn(point: np.ndarray, bearing: float, radius: float, colour, text: str) -> VGroup:
    """The clockwise turn from north through `bearing` degrees, with its label."""
    arc = Arc(
        radius=radius,
        start_angle=math.pi / 2,
        angle=-math.radians(bearing),
        arc_center=point,
        color=colour,
        stroke_width=4,
    )
    middle = math.pi / 2 - math.radians(bearing) / 2
    tag = label(text, colour=colour, size=26)
    distance = radius + 0.2 + max(tag.width, tag.height) / 2
    tag.move_to(point + distance * np.array([math.cos(middle), math.sin(middle), 0]))
    return VGroup(arc, tag)
