"""SimilarityScaler: similar shapes: the scale factor from a pair of corresponding sides, a
missing length, and how areas scale by k² and volumes by k³ (4024 4.4, with 5.5;
PRIMITIVES.md #30).

Two similar triangles (or, for volumes, two similar cylinders) are drawn side by side with
corresponding sides in the same colour. The scale factor k is a large length over the matching
small length; every length multiplies by k, every area by k² and every volume by k³.
"""

from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import Ellipse, Line, Polygon, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, split_columns, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf, latex_value

Length = Annotated[float, Field(gt=0, le=10_000)]
SIDE_COLOURS = [style.CURVE_COLOUR, style.RUN_COLOUR, style.RISE_COLOUR]
NAMES = ["AB", "BC", "CA"]
LARGE = ["PQ", "QR", "RP"]


class SimilarityScalerParams(PrimitiveParams):
    sides: list[Length] = Field(
        min_length=3, max_length=3, description="The small triangle's AB, BC, CA"
    )
    known_side: Annotated[int, Field(ge=0, le=2)] = Field(
        default=0, description="Which side of the large shape is known (0 = AB)"
    )
    known_value: Length = Field(description="Its length on the large shape")
    find: Literal["side", "area", "volume"]
    find_side: Annotated[int, Field(ge=0, le=2)] = Field(
        default=1, description="For side: which side of the large triangle to find"
    )
    small_value: Length | None = Field(
        default=None, description="For area or volume: the small shape's area or volume"
    )
    unit: Literal["cm", "m", "mm", ""] = "cm"


class SimilarityScaler(StagedPrimitive[SimilarityScalerParams]):
    primitive_id = "SimilarityScaler"
    version = "1"
    topic = "Geometry"
    params_model = SimilarityScalerParams
    layout = LayoutContract(
        region=style.GRAPH_REGION, allowed_overlaps=[("small", "*"), ("large", "*")]
    )

    def default_params(self) -> SimilarityScalerParams:
        return SimilarityScalerParams(sides=[4, 5, 6], known_value=12, find="side")

    def validate(self, params: SimilarityScalerParams) -> list[PredicateFailure]:
        a, b, c = sorted(params.sides)
        if a + b <= c:
            return [_failure("triangle_exists", "these sides make no triangle", "sides")]
        if params.find == "side" and params.find_side == params.known_side:
            return [
                _failure("find_other_side", "find a side other than the known one", "find_side")
            ]
        if params.find != "side" and params.small_value is None:
            message = f"give the small shape's {params.find}"
            return [_failure("needs_small_value", message, "small_value")]
        if _k(params) == 1:
            return [
                _failure(
                    "not_congruent",
                    "the scale factor is 1: the shapes are congruent",
                    "known_value",
                )
            ]
        return []

    def computed_values(self, params: SimilarityScalerParams) -> dict[str, str]:
        values = {"scale_factor": latex_value(_k(params))}
        values[params.find] = format_sf(_answer(params))
        return values

    def build(self, params: SimilarityScalerParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        figure_box, working_box = split_columns(area, [1.25, 1], gap=0.3)
        k = float(_k(params))
        unit = rf"\text{{ {params.unit}}}" if params.unit else ""
        if params.find == "volume":
            small, large = _cylinders(params, figure_box, k)
        else:
            small, large = _triangles(params, figure_box, k, unit)
        parts = {"small": small, "large": large}
        rows = _working(params, unit)
        mobjects = [label(tex, size=32) for tex in rows]
        group = VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.3)
        style.fit_inside(group, working_box)
        for i, mob in enumerate(mobjects, start=1):
            parts[f"row_{i}"] = mob
        question = {
            "side": rf"\text{{The triangles are similar. Find }} {LARGE[params.find_side]}",
            "area": r"\text{The triangles are similar. Find the area of } PQR",
            "volume": r"\text{The cylinders are similar. Find the volume of the second}",
        }[params.find]
        power = {"side": "", "area": "^2", "volume": "^3"}[params.find]
        name = {
            "side": LARGE[params.find_side],
            "area": r"\text{area}",
            "volume": r"\text{volume}",
        }[params.find]
        parts["question"] = text_line(question, upper, size=34)
        parts["answer"] = text_line(
            rf"{name} = {format_sf(_answer(params))}{unit}{power}",
            lower,
            colour=style.HIGHLIGHT_COLOUR,
        )
        return parts

    def stages(self, params: SimilarityScalerParams, level) -> list[Stage]:
        rows = [f"row_{i}" for i in range(1, len(_working(params, "")) + 1)]
        what = {
            "side": "Every length is multiplied by k",
            "area": "Areas are multiplied by k squared",
            "volume": "Volumes are multiplied by k cubed",
        }[params.find]
        steps = [
            stage(
                "shapes",
                "The shapes are similar: matching sides are in the same colour",
                3.0,
                ["question", "small", "large"],
            ),
            stage(
                "factor",
                "The scale factor is a large length over the matching small one",
                3.5,
                rows[:1],
                emphasise=rows[:1],
            ),
            stage("scale", what, 3.5, rows[1:]),
            stage("answer", "So", 1.5, ["answer"], emphasise=["answer"]),
        ]

        def standard(s):
            return [s[0], combine("factor", s[1].description, 4.0, s[1], s[2]), s[3]]

        def concise(s):
            return [s[0], combine("working", "Use the scale factor", 4.5, *s[1:])]

        return by_level(level, steps, standard, concise)


def _k(params: SimilarityScalerParams) -> sp.Expr:
    return sp.nsimplify(params.known_value) / sp.nsimplify(params.sides[params.known_side])


def _answer(params: SimilarityScalerParams) -> sp.Expr:
    k = _k(params)
    if params.find == "side":
        return k * sp.nsimplify(params.sides[params.find_side])
    power = 2 if params.find == "area" else 3
    return k**power * sp.nsimplify(params.small_value)


def _plain(value) -> str:
    return format_sf(value, 6)


def _working(params: SimilarityScalerParams, unit: str) -> list[str]:
    k = _k(params)
    known = params.known_side
    top, bottom = (LARGE[known], NAMES[known])
    if params.find == "volume":
        top, bottom = r"\text{new}", r"\text{old}"
    rows = [
        rf"k = \frac{{{top}}}{{{bottom}}} = "
        rf"\frac{{{_plain(params.known_value)}}}{{{_plain(params.sides[known])}}} = "
        rf"{latex_value(k)}"
    ]
    if params.find == "side":
        j = params.find_side
        rows.append(rf"{LARGE[j]} = k \times {NAMES[j]}")
        rows.append(
            rf"= {latex_value(k)} \times {_plain(params.sides[j])} = "
            rf"{format_sf(_answer(params))}"
        )
    else:
        power = 2 if params.find == "area" else 3
        rows.append(rf"\text{{{params.find} factor}} = k^{power} = {latex_value(k**power)}")
        rows.append(
            rf"{latex_value(k**power)} \times {_plain(params.small_value)} = "
            rf"{format_sf(_answer(params))}"
        )
    return rows


def _triangle_points(sides) -> list[np.ndarray]:
    """A, B, C with AB along the base, from the three side lengths."""
    ab, bc, ca = (float(s) for s in sides)
    x = (ab**2 + ca**2 - bc**2) / (2 * ab)
    y = max(ca**2 - x**2, 0) ** 0.5
    return [np.array([0.0, 0, 0]), np.array([ab, 0, 0]), np.array([x, y, 0])]


def _triangles(params, box, k, unit) -> tuple[VGroup, VGroup]:
    left, right = split_columns(box, [1, k], gap=0.9)
    base = _triangle_points(params.sides)
    width = max(p[0] for p in base) - min(p[0] for p in base)
    height = max(p[1] for p in base)
    scale = min(right.width / (width * k), (right.height - 1.0) / (height * k))
    out = []
    for factor, region, letters in ((1.0, left, "ABC"), (k, right, "PQR")):
        pts = [p * scale * factor for p in base]
        centre = sum(pts) / 3
        shift = np.array([region.center[0], region.bottom + 0.6, 0]) - np.array(
            [(min(p[0] for p in pts) + max(p[0] for p in pts)) / 2, 0, 0]
        )
        pts = [p + shift for p in pts]
        centre = sum(pts) / 3
        group = VGroup()
        for i in range(3):
            p, q = pts[i], pts[(i + 1) % 3]
            group.add(Line(p, q, color=SIDE_COLOURS[i], stroke_width=5))
            value = params.sides[i] * factor if factor == 1.0 else None
            if factor != 1.0 and i == params.known_side:
                value = params.known_value
            text = (
                "x"
                if factor != 1.0 and params.find == "side" and i == params.find_side
                else (rf"{_plain(value)}{unit}" if value is not None else None)
            )
            if text:
                mid = (p + q) / 2
                out_dir = (mid - centre) / np.linalg.norm(mid - centre)
                tag = label(text, colour=SIDE_COLOURS[i], size=26)
                group.add(tag.move_to(mid + out_dir * (0.18 + max(tag.width, tag.height) / 2)))
        for letter, p in zip(letters, pts, strict=True):
            out_dir = (p - centre) / np.linalg.norm(p - centre)
            group.add(label(letter, size=26).move_to(p + out_dir * 0.28))
        if params.find != "side":
            group.add(
                Polygon(*pts, stroke_width=0, fill_color=style.AREA_COLOUR, fill_opacity=0.25)
            )
            if factor == 1.0:
                group.add(label(rf"{_plain(params.small_value)}{unit}^2", size=26).move_to(centre))
        out.append(group)
    return out[0], out[1]


def _cylinders(params, box, k) -> tuple[VGroup, VGroup]:
    left, right = split_columns(box, [1, k], gap=0.9)
    radius, height = 0.5, 1.0
    scale = min(right.width / (2 * radius * k), (right.height - 1.2) / ((height + 0.4) * k))
    out = []
    unit = rf"\text{{ {params.unit}}}" if params.unit else ""
    for factor, region in ((1.0, left), (k, right)):
        r, h = radius * scale * factor, height * scale * factor
        bottom = np.array([region.center[0], region.bottom + 0.7, 0])
        top = bottom + np.array([0, h, 0])
        group = VGroup(
            Ellipse(width=2 * r, height=0.6 * r, color=style.TEXT_COLOUR).move_to(top),
            Ellipse(width=2 * r, height=0.6 * r, color=style.TEXT_COLOUR).move_to(bottom),
            Line(bottom + [-r, 0, 0], top + [-r, 0, 0]),
            Line(bottom + [r, 0, 0], top + [r, 0, 0]),
        )
        index = params.known_side
        length = params.sides[index] if factor == 1.0 else params.known_value
        tag = label(rf"{_plain(length)}{unit}", colour=SIDE_COLOURS[0], size=26)
        group.add(
            Line(
                bottom + [r + 0.15, 0, 0],
                top + [r + 0.15, 0, 0],
                color=SIDE_COLOURS[0],
                stroke_width=4,
            )
        )
        group.add(tag.next_to((bottom + top) / 2 + [r + 0.15, 0, 0], [1, 0, 0], buff=0.1))
        if factor == 1.0:
            group.add(
                label(rf"{_plain(params.small_value)}{unit}^3", size=26).next_to(
                    bottom, [0, -1, 0], buff=0.3
                )
            )
        out.append(group)
    return out[0], out[1]


def _failure(predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=[parameter]
    )
