"""AreaDissector: where the area formulas come from, by cutting and moving pieces (4024 5.2;
PRIMITIVES.md #35).

A parallelogram: cut the triangle off one end and slide it to the other, and it is a rectangle,
base × height. A triangle: a copy turned half a turn makes a parallelogram, so the triangle is
half of base × height. A trapezium: a copy turned half a turn makes a parallelogram of base
a + b, so the trapezium is ½(a + b)h. The heights are perpendicular heights, drawn dashed.
"""

import math
from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import DashedLine, Polygon, Rotate, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import Diagram, angle_mark, label, split_columns, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf

Length = Annotated[float, Field(gt=0, le=1000)]
PIECE = style.RUN_COLOUR


class AreaDissectorParams(PrimitiveParams):
    shape: Literal["parallelogram", "triangle", "trapezium"]
    base: Length = Field(description="The base b (the longer parallel side of a trapezium)")
    height: Length = Field(description="The perpendicular height")
    top: Length | None = Field(default=None, description="For trapezium: the parallel side a")
    unit: Literal["cm", "m", "mm", ""] = "cm"


class AreaDissector(StagedPrimitive[AreaDissectorParams]):
    primitive_id = "AreaDissector"
    version = "1"
    topic = "Mensuration"
    params_model = AreaDissectorParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("body", "*"), ("piece*", "*"), ("height", "*"), ("result", "*")],
    )

    def default_params(self) -> AreaDissectorParams:
        return AreaDissectorParams(shape="parallelogram", base=8, height=5)

    def validate(self, params: AreaDissectorParams) -> list[PredicateFailure]:
        if params.shape == "trapezium":
            if params.top is None:
                return [_failure("needs_top", "a trapezium needs its top side", "top")]
            if params.top >= params.base:
                return [_failure("top_shorter", "make the top the shorter side", "top")]
        return []

    def computed_values(self, params: AreaDissectorParams) -> dict[str, str]:
        return {"area": format_sf(_area(params))}

    def build(self, params: AreaDissectorParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        figure_box, working_box = split_columns(area, [1.3, 1], gap=0.3)
        b, h = params.base, params.height
        slant = 0.3 * b
        unit = rf"\text{{ {params.unit}}}" if params.unit else ""
        if params.shape == "parallelogram":
            pts = [(0, 0), (b, 0), (b + slant, h), (slant, h)]
            extent = pts + [(b + slant, 0)]
        elif params.shape == "triangle":
            apex = (0.35 * b, h)
            pts = [(0, 0), (b, 0), apex]
            extent = pts + [(apex[0] + b, h)]
        else:
            a = params.top
            left = (b - a) / 2
            pts = [(0, 0), (b, 0), (left + a, h), (left, h)]
            extent = pts + [(b + a, 0), (b + left + a, h)]
        diagram = Diagram(extent, figure_box, margin=0.55)
        p = [diagram.p(*xy) for xy in pts]
        fill = {
            "fill_color": style.CURVE_COLOUR,
            "fill_opacity": 0.45,
            "color": style.TEXT_COLOUR,
            "stroke_width": 4,
        }
        piece_style = {
            "fill_color": PIECE,
            "fill_opacity": 0.55,
            "color": style.TEXT_COLOUR,
            "stroke_width": 3,
        }
        parts = {}
        if params.shape == "parallelogram":
            foot = diagram.p(slant, 0)
            parts["body"] = Polygon(foot, p[1], p[2], p[3], **fill)
            parts["piece"] = Polygon(p[0], foot, p[3], **piece_style)
            shift = p[1] - p[0]
            parts["piece_moved"] = parts["piece"].copy().shift(shift)
            self._motion = ("slide", parts["piece"], shift)
            height_at, height_top = foot, p[3]
            parts["result"] = Polygon(
                foot, foot + shift, p[2], p[3], color=style.HIGHLIGHT_COLOUR, stroke_width=5
            )
        else:
            parts["body"] = Polygon(*p, **fill)
            # the copy turns half a turn about the midpoint of the right-hand side
            pivot = (p[1] + p[2]) / 2
            copy = Polygon(*p, **piece_style)
            parts["piece"] = copy
            moved = copy.copy().rotate(math.pi, about_point=pivot)
            parts["piece_moved"] = moved
            self._motion = ("turn", copy, pivot)
            top_point = p[2] if params.shape == "triangle" else p[3]
            height_at = np.array([top_point[0], p[0][1], 0])
            height_top = top_point
            parts["result"] = Polygon(
                *(diagram.p(*xy) for xy in _joined(params, pts)),
                color=style.HIGHLIGHT_COLOUR,
                stroke_width=5,
            )
        parts["height"] = VGroup(
            DashedLine(height_at, height_top, stroke_width=3, color=style.HIGHLIGHT_COLOUR),
            angle_mark(
                height_at,
                height_at + np.array([1, 0, 0]),
                height_top,
                radius=0.22,
                colour=style.HIGHLIGHT_COLOUR,
            ),
            label(rf"{_plain(h)}{unit}", colour=style.HIGHLIGHT_COLOUR, size=26).next_to(
                (height_at + height_top) / 2, [1, 0, 0], buff=0.1
            ),
        )
        parts["base_label"] = label(rf"{_plain(b)}{unit}", size=26).next_to(
            (p[0] + p[1]) / 2, [0, -1, 0], buff=0.15
        )
        if params.shape == "trapezium":
            parts["top_label"] = label(rf"{_plain(params.top)}{unit}", size=26).next_to(
                (p[2] + p[3]) / 2, [0, 1, 0], buff=0.15
            )
        rows = _working(params)
        mobjects = [label(tex, size=32) for tex in rows]
        group = VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.3)
        style.fit_inside(group, working_box)
        for i, mob in enumerate(mobjects, start=1):
            parts[f"row_{i}"] = mob
        name = {
            "parallelogram": "a parallelogram",
            "triangle": "a triangle",
            "trapezium": "a trapezium",
        }[params.shape]
        parts["question"] = text_line(rf"\text{{The area of {name}}}", upper)
        square = "^2" if unit else ""
        parts["answer"] = text_line(
            rf"\text{{Area}} = {format_sf(_area(params))}{unit}{square}",
            lower,
            colour=style.HIGHLIGHT_COLOUR,
        )
        return parts

    def move(self, scene, parts, level, run_time, min_run_time):
        """Slide or turn the cut piece into place."""
        kind, piece, how = self._motion
        moving = piece.copy()
        scene.remove(piece)
        scene.add(moving)
        hold = min(0.15, 0.2 * run_time)
        animation_time = min(max(min_run_time, 0.7 * run_time), run_time - hold)
        if kind == "slide":
            scene.play(moving.animate.shift(how), run_time=animation_time)
        else:
            scene.play(Rotate(moving, angle=math.pi, about_point=how), run_time=animation_time)
        scene.remove(moving)
        scene.wait(run_time - animation_time)

    def stages(self, params: AreaDissectorParams, level) -> list[Stage]:
        rows = [f"row_{i}" for i in range(1, len(_working(params)) + 1)]
        labels = ["base_label", "height"] + (["top_label"] if params.shape == "trapezium" else [])
        if params.shape == "parallelogram":
            cut = stage("cut", "Cut the triangle off the end", 2.5, ["piece"])
            move_words = "Slide it to the other end: it makes a rectangle"
        else:
            cut = stage("cut", "Take an identical copy", 2.5, ["piece"])
            move_words = "Turn the copy half a turn and fit it on: it makes a parallelogram"
        steps = [
            stage(
                "shape",
                "Here is the shape, with its perpendicular height",
                2.5,
                ["question", "body", *labels],
            ),
            cut,
            stage(
                "move", move_words, 4.0, ["piece_moved", "result"], hide=["piece"], motion="move"
            ),
            stage("formula", "So the area is", 3.5, rows[:3], emphasise=rows[2:3]),
            stage("answer", "Substitute", 2.5, [*rows[3:], "answer"], emphasise=["answer"]),
        ]

        def standard(s):
            return [combine("setup", s[1].description, 3.5, s[0], s[1]), *s[2:]]

        def concise(s):
            return [
                combine("setup", s[1].description, 3.5, s[0], s[1]),
                s[2],
                combine("working", "So the area is", 4.0, s[3], s[4]),
            ]

        return by_level(level, steps, standard, concise)


def _joined(params: AreaDissectorParams, pts) -> list[tuple[float, float]]:
    """The parallelogram made by the shape and its copy turned about the middle of BC: a point
    P goes to 2M - P."""
    (ax, ay), (bx, by), (cx, cy) = pts[0], pts[1], pts[2]
    mx, my = (bx + cx) / 2, (by + cy) / 2
    if params.shape == "triangle":
        return [(ax, ay), (bx, by), (2 * mx - ax, 2 * my - ay), (cx, cy)]
    dx, dy = pts[3]
    return [(ax, ay), (2 * mx - dx, 2 * my - dy), (2 * mx - ax, 2 * my - ay), (dx, dy)]


def _area(params: AreaDissectorParams) -> sp.Expr:
    b, h = sp.nsimplify(params.base), sp.nsimplify(params.height)
    if params.shape == "parallelogram":
        return b * h
    if params.shape == "triangle":
        return b * h / 2
    return (sp.nsimplify(params.top) + b) * h / 2


def _plain(value) -> str:
    return format_sf(value, 6)


def _working(params: AreaDissectorParams) -> list[str]:
    b, h = _plain(params.base), _plain(params.height)
    area = format_sf(_area(params))
    if params.shape == "parallelogram":
        return [
            r"\text{it is now a rectangle}",
            r"\text{area} = \text{base} \times \text{height}",
            r"A = bh",
            rf"A = {b} \times {h} = {area}",
        ]
    if params.shape == "triangle":
        return [
            r"\text{parallelogram} = bh",
            r"\text{the triangle is half of it}",
            r"A = \tfrac{1}{2}bh",
            rf"A = \tfrac{{1}}{{2}} \times {b} \times {h} = {area}",
        ]
    a = _plain(params.top)
    return [
        r"\text{parallelogram} = (a + b)h",
        r"\text{the trapezium is half of it}",
        r"A = \tfrac{1}{2}(a + b)h",
        rf"A = \tfrac{{1}}{{2}}({a} + {b}) \times {h} = {area}",
    ]


def _failure(predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=[parameter]
    )
