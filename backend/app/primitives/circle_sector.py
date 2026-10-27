"""CircleSector: arc length, sector area and perimeter, the segment area, and the angle from an
arc, in degrees or radians (4024 5.3; AM 9.1, 9.2; PRIMITIVES.md #36).

A sector is the fraction θ/360 of the whole circle, so its arc is that fraction of 2πr and its
area that fraction of πr². In radians the same facts read s = rθ and A = ½r²θ. The segment is
the sector take away the triangle, ½r²(θ − sin θ). Answers are exact in π where they can be,
with the value to 3 significant figures beside them.
"""

import math
from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import Arc, Circle, Line, Polygon, Sector, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import (
    angle_label_position,
    angle_mark,
    label,
    split_columns,
    text_line,
)
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf, latex_with_pi

Positive = Annotated[float, Field(gt=0, le=10_000)]


class CircleSectorParams(PrimitiveParams):
    radius: Positive
    angle: Annotated[float, Field(gt=0, lt=360)] | None = Field(
        default=None, description="The angle at the centre (degrees, or radians if radians)"
    )
    arc: Positive | None = Field(default=None, description="For find=angle: the arc length")
    radians: bool = Field(default=False, description="Work in radians (Additional Maths)")
    find: Literal["arc", "area", "perimeter", "segment", "angle"]
    unit: Literal["cm", "m", "mm", "km", ""] = "cm"


class CircleSector(StagedPrimitive[CircleSectorParams]):
    primitive_id = "CircleSector"
    version = "1"
    topic = "Mensuration"
    params_model = CircleSectorParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("circle", "*"),
            ("sector", "*"),
            ("segment", "*"),
            ("arc", "*"),
            ("angle", "*"),
            ("radii", "*"),
            ("triangle", "*"),
        ],
    )

    def default_params(self) -> CircleSectorParams:
        return CircleSectorParams(radius=6, angle=120, find="arc")

    def validate(self, params: CircleSectorParams) -> list[PredicateFailure]:
        if params.find == "angle":
            if params.arc is None:
                return [_failure("needs_arc", "finding the angle needs the arc length", "arc")]
            if params.angle is not None:
                return [_failure("find_unknown", "the angle to find is given", "angle")]
            if params.arc >= 2 * math.pi * params.radius:
                return [_failure("arc_fits", "the arc is longer than the circle", "arc")]
            return []
        if params.angle is None:
            return [_failure("needs_angle", f"{params.find} needs the angle", "angle")]
        if params.radians and params.angle >= 2 * math.pi:
            return [_failure("angle_fits", "the angle is a full turn or more", "angle")]
        if params.find == "segment" and _theta(params) >= sp.pi:
            message = "the segment formula here is for angles under 180°"
            return [_failure("minor_segment", message, "angle")]
        return []

    def computed_values(self, params: CircleSectorParams) -> dict[str, str]:
        if params.find == "angle":
            theta = _theta(params)
            if params.radians:
                return {"angle": format_sf(theta)}
            return {"angle": f"{float(sp.deg(theta)):.1f}"}
        return {params.find: format_sf(_result(params))}

    def build(self, params: CircleSectorParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        figure_box, working_box = split_columns(area, [1.05, 1], gap=0.3)
        theta = float(_theta(params))
        radius = min(figure_box.width, figure_box.height) / 2 - 0.55
        centre = figure_box.center
        start = math.pi / 2 - theta / 2  # the sector stands upright, symmetric about the vertical
        a = centre + radius * np.array([math.cos(start), math.sin(start), 0])
        b = centre + radius * np.array([math.cos(start + theta), math.sin(start + theta), 0])
        parts = {
            "circle": Circle(
                radius=radius, color=style.TEXT_COLOUR, stroke_width=2, stroke_opacity=0.45
            ).move_to(centre),
            "sector": Sector(
                radius=radius,
                angle=theta,
                start_angle=start,
                fill_color=style.AREA_COLOUR,
                fill_opacity=style.AREA_OPACITY,
                stroke_width=0,
            ).move_arc_center_to(centre),
            "radii": VGroup(Line(centre, a, stroke_width=4), Line(centre, b, stroke_width=4)),
            "arc": Arc(
                radius=radius,
                start_angle=start,
                angle=theta,
                arc_center=centre,
                color=style.HIGHLIGHT_COLOUR,
                stroke_width=6,
            ),
        }
        mark = angle_mark(
            centre, a, b, radius=0.45, colour=style.TEXT_COLOUR, reflex=theta > math.pi
        )
        angle_text = "x" if params.find == "angle" else _angle_tex(params)
        tag = label(
            angle_text,
            colour=style.HIGHLIGHT_COLOUR if params.find == "angle" else style.TEXT_COLOUR,
            size=28,
        )
        tag.move_to(
            angle_label_position(centre, a, b, 0.75 + tag.width / 2, reflex=theta > math.pi)
        )
        parts["angle"] = VGroup(mark, tag)
        r_label = label(rf"{_plain(params.radius)}\text{{ {params.unit}}}", size=28)
        middle = (centre + a) / 2
        side = np.array([math.cos(start - math.pi / 2), math.sin(start - math.pi / 2), 0])
        parts["radius_label"] = r_label.move_to(middle + side * (0.2 + r_label.height))
        top = centre + radius * 1.0 * np.array(
            [math.cos(start + theta / 2), math.sin(start + theta / 2), 0]
        )
        arc_text = (
            "x"
            if params.find == "arc"
            else rf"{_plain(params.arc)}\text{{ {params.unit}}}"
            if params.arc
            else None
        )
        if arc_text:
            arc_label = label(arc_text, colour=style.HIGHLIGHT_COLOUR, size=28)
            direction = (top - centre) / np.linalg.norm(top - centre)
            parts["arc_label"] = arc_label.move_to(top + direction * (0.2 + arc_label.height))
        if params.find == "segment":
            parts["triangle"] = Polygon(
                centre,
                a,
                b,
                color=style.RUN_COLOUR,
                stroke_width=3,
                fill_color=style.RUN_COLOUR,
                fill_opacity=0.35,
            )
        rows = _working(params)
        mobjects = [label(tex, size=32) for tex in rows]
        group = VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.3)
        style.fit_inside(group, working_box)
        for i, mob in enumerate(mobjects, start=1):
            parts[f"row_{i}"] = mob
        parts["question"] = text_line(_question(params), upper)
        parts["answer"] = text_line(_answer(params), lower, colour=style.HIGHLIGHT_COLOUR)
        return parts

    def stages(self, params: CircleSectorParams, level) -> list[Stage]:
        rows = [f"row_{i}" for i in range(1, len(_working(params)) + 1)]
        labels = ["radius_label", "angle"] + (
            ["arc_label"] if params.find in ("arc", "angle") or params.arc else []
        )
        fraction = (
            "In radians, the arc is r theta and the area is half r squared theta"
            if params.radians
            else "The sector is the angle over 360 of the whole circle"
        )
        steps = [
            stage(
                "sector",
                "Here is the sector",
                2.5,
                ["question", "circle", "sector", "radii", *labels],
            ),
            stage(
                "fraction",
                fraction,
                3.5,
                [rows[0]],
                emphasise=["arc"] if params.find in ("arc", "perimeter", "angle") else ["sector"],
            ),
        ]
        if params.find == "segment":
            steps.append(
                stage(
                    "triangle",
                    "The segment is the sector take away the triangle",
                    3.5,
                    ["triangle", *rows[1:2]],
                )
            )
            rest = rows[2:]
        else:
            rest = rows[1:]
        steps.append(stage("solve", "Substitute and work it out", 3.0, rest))
        steps.append(stage("answer", "So", 1.5, ["answer"], emphasise=["answer"]))

        def standard(s):
            return [combine("setup", s[1].description, 4.0, s[0], s[1]), *s[2:]]

        def concise(s):
            return [
                combine("setup", s[1].description, 4.0, s[0], s[1]),
                combine("working", "Work it out", 4.0, *s[2:]),
            ]

        return by_level(level, steps, standard, concise)


def _theta(params: CircleSectorParams) -> sp.Expr:
    """The angle in radians, exact where the given angle allows."""
    if params.find == "angle":
        return sp.nsimplify(params.arc) / sp.nsimplify(params.radius)
    angle = sp.nsimplify(params.angle)
    return angle if params.radians else angle * sp.pi / 180


def _result(params: CircleSectorParams) -> sp.Expr:
    r, t = sp.nsimplify(params.radius), _theta(params)
    return {
        "arc": r * t,
        "area": r**2 * t / 2,
        "perimeter": 2 * r + r * t,
        "segment": r**2 * (t - sp.sin(t)) / 2,
    }[params.find]


def _plain(value: float) -> str:
    return format_sf(value, 6)


def _angle_tex(params: CircleSectorParams) -> str:
    if params.radians:
        return rf"{_plain(params.angle)}\text{{ rad}}"
    return rf"{_plain(params.angle)}^\circ"


def _value(expr: sp.Expr) -> str:
    """Exact in π with its 3 s.f. value, or just to 3 s.f."""
    expr = sp.nsimplify(expr, [sp.pi])
    if expr.has(sp.sin) or expr.has(sp.cos):
        return format_sf(expr)
    return latex_with_pi(expr)


def _working(params: CircleSectorParams) -> list[str]:
    r = _plain(params.radius)
    s = _plain(params.arc) if params.arc is not None else "s"
    find = params.find
    if params.radians:
        t = _plain(params.angle) if params.angle is not None else "x"
        rows = {
            "arc": [r"s = r\theta", rf"s = {r} \times {t}"],
            "area": [
                r"A = \tfrac{1}{2}r^2\theta",
                rf"A = \tfrac{{1}}{{2}} \times {r}^2 \times {t}",
            ],
            "perimeter": [r"P = 2r + r\theta", rf"P = 2 \times {r} + {r} \times {t}"],
            "segment": [
                r"\text{sector} = \tfrac{1}{2}r^2\theta",
                r"\text{segment} = \tfrac{1}{2}r^2(\theta - \sin\theta)",
                rf"= \tfrac{{1}}{{2}} \times {r}^2 ({t} - \sin {t})",
            ],
            "angle": [
                r"s = r\theta",
                rf"{s} = {r}x",
                rf"x = {s} \div {r}",
            ],
        }[find]
    else:
        t = _plain(params.angle) if params.angle is not None else "x"
        frac = rf"\tfrac{{{t}}}{{360}}"
        rows = {
            "arc": [
                r"\text{arc} = \tfrac{\theta}{360} \times 2\pi r",
                rf"= {frac} \times 2 \times \pi \times {r}",
            ],
            "area": [
                r"\text{area} = \tfrac{\theta}{360} \times \pi r^2",
                rf"= {frac} \times \pi \times {r}^2",
            ],
            "perimeter": [
                r"\text{perimeter} = 2r + \tfrac{\theta}{360} \times 2\pi r",
                rf"= 2 \times {r} + {frac} \times 2\pi \times {r}",
            ],
            "segment": [
                r"\text{sector} = \tfrac{\theta}{360} \times \pi r^2",
                r"\text{segment} = \text{sector} - \tfrac{1}{2}r^2\sin\theta",
                rf"= {frac} \times \pi \times {r}^2 - \tfrac{{1}}{{2}} \times {r}^2 "
                rf"\sin {t}^\circ",
            ],
            "angle": [
                r"\text{arc} = \tfrac{\theta}{360} \times 2\pi r",
                rf"{s} = \tfrac{{x}}{{360}} \times 2\pi \times {r}",
                rf"x = \frac{{{s} \times 360}}{{2\pi \times {r}}}",
            ],
        }[find]
    return [*rows, _final(params)]


def _final(params: CircleSectorParams) -> str:
    if params.find == "angle":
        theta = _theta(params)
        if params.radians:
            return rf"x = {format_sf(theta)}\text{{ rad}}"
        return rf"x = {float(sp.deg(theta)):.1f}^\circ"
    return f"= {_value(_result(params))}"


def _units(params: CircleSectorParams) -> str:
    if not params.unit:
        return ""
    square = "^2" if params.find in ("area", "segment") else ""
    return rf"\text{{ {params.unit}}}{square}"


def _answer(params: CircleSectorParams) -> str:
    if params.find == "angle":
        return _final(params)
    name = {
        "arc": "Arc length",
        "area": "Sector area",
        "perimeter": "Perimeter",
        "segment": "Segment area",
    }[params.find]
    return rf"\text{{{name}}} = {format_sf(_result(params))}{_units(params)}"


def _question(params: CircleSectorParams) -> str:
    what = {
        "arc": "the arc length",
        "area": "the area of the sector",
        "perimeter": "the perimeter of the sector",
        "segment": "the area of the segment",
        "angle": "the angle " + ("(radians)" if params.radians else "(degrees)"),
    }[params.find]
    return rf"\text{{Find {what}}}"


def _failure(predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=[parameter]
    )
