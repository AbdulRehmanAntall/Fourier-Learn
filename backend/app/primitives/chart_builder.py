"""ChartBuilder: statistical charts drawn from a frequency table: a bar chart, a pie chart with
each angle worked out, and an ordered stem-and-leaf diagram with its key (4024 9.1, 9.4;
PRIMITIVES.md #47).

A pie chart's angle for a category is its frequency over the total, times 360°; the angles add
to 360°. A stem-and-leaf diagram keeps every value: the stem is the tens, the leaves the units,
in order, with a key such as 3 | 7 means 37.
"""

import math
from collections import defaultdict
from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import Line, Rectangle, Sector, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, make_table, split_columns, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=14)]
PALETTE = [
    style.CURVE_COLOUR,
    style.RUN_COLOUR,
    style.RISE_COLOUR,
    style.SECANT_COLOUR,
    style.AREA_COLOUR,
    style.TANGENT_COLOUR,
]


class ChartBuilderParams(PrimitiveParams):
    chart: Literal["bar", "pie", "stem_leaf"]
    categories: list[Name] | None = Field(default=None, min_length=2, max_length=6)
    frequencies: list[Annotated[int, Field(ge=0, le=10_000)]] | None = Field(
        default=None, min_length=2, max_length=6
    )
    data: list[Annotated[int, Field(ge=0, le=999)]] | None = Field(
        default=None, min_length=5, max_length=30, description="For stem_leaf: the raw values"
    )
    title: Annotated[str, StringConstraints(max_length=40)] = ""


class ChartBuilder(StagedPrimitive[ChartBuilderParams]):
    primitive_id = "ChartBuilder"
    version = "1"
    topic = "Statistics"
    params_model = ChartBuilderParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("axes", "*"), ("bars", "*"), ("sectors", "*"), ("table", "*")],
    )

    def default_params(self) -> ChartBuilderParams:
        return ChartBuilderParams(
            chart="pie", categories=["Bus", "Car", "Walk", "Cycle"], frequencies=[12, 8, 15, 5]
        )

    def validate(self, params: ChartBuilderParams) -> list[PredicateFailure]:
        if params.chart == "stem_leaf":
            if params.data is None:
                return [_failure("needs_data", "a stem-and-leaf diagram needs data", "data")]
            stems = {v // 10 for v in params.data}
            if len(stems) > 8:
                return [_failure("stems_fit", "more than 8 stems", "data")]
            return []
        if params.categories is None or params.frequencies is None:
            return [_failure("needs_table", "give categories and frequencies", "categories")]
        if len(params.categories) != len(params.frequencies):
            return [_failure("one_each", "one frequency per category", "frequencies")]
        if sum(params.frequencies) == 0:
            return [_failure("nonzero_total", "the frequencies add to 0", "frequencies")]
        return []

    def computed_values(self, params: ChartBuilderParams) -> dict[str, str]:
        if params.chart == "stem_leaf":
            values = sorted(params.data)
            return {"min": str(values[0]), "max": str(values[-1])}
        total = sum(params.frequencies)
        out = {"total": str(total)}
        if params.chart == "pie":
            for name, f in zip(params.categories, params.frequencies, strict=True):
                out[name] = format_sf(sp.Rational(f * 360, total))
        return out

    def build(self, params: ChartBuilderParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        heading = (
            params.title
            or {"bar": "Bar chart", "pie": "Pie chart", "stem_leaf": "Stem-and-leaf diagram"}[
                params.chart
            ]
        )
        parts = {"question": text_line(rf"\text{{{heading}}}", upper)}
        if params.chart == "stem_leaf":
            parts.update(_stem_leaf(params, area, lower))
            return parts
        widths = [1.35, 1] if params.chart == "pie" else [1, 1.5]  # room for the angle column
        table_box, chart_box = split_columns(area, widths, gap=0.4)
        total = sum(params.frequencies)
        rows = [[r"\text{Category}", r"\text{Frequency}"]]
        if params.chart == "pie":
            rows[0].append(r"\text{Angle}")
        for name, f in zip(params.categories, params.frequencies, strict=True):
            row = [rf"\text{{{name}}}", str(f)]
            if params.chart == "pie":
                row.append(rf"\tfrac{{{f}}}{{{total}}} \times 360 = {_angle(f, total)}^\circ")
            rows.append(row)
        rows.append(
            [r"\text{Total}", str(total)] + ([r"360^\circ"] if params.chart == "pie" else [])
        )
        table = make_table(rows, table_box, font_size=28)
        if params.chart == "pie":
            # the angles come in their own step, after the frequencies
            angles = table.column(2)
            parts["table"] = VGroup(table.lines, *(c for row in table.cells for c in row[:2]))
            parts["angle_column"] = angles
        else:
            parts["table"] = table.group
        if params.chart == "bar":
            parts.update(_bars(params, chart_box))
            parts["answer"] = text_line(
                rf"\text{{Total frequency}} = {total}", lower, colour=style.HIGHLIGHT_COLOUR
            )
        else:
            parts.update(_pie(params, chart_box, total))
            parts["answer"] = text_line(
                r"\text{The angles add to } 360^\circ", lower, colour=style.HIGHLIGHT_COLOUR
            )
        return parts

    def stages(self, params: ChartBuilderParams, level) -> list[Stage]:
        if params.chart == "stem_leaf":
            steps = [
                stage("data", "Here are the values", 2.5, ["question", "raw"]),
                stage("stems", "The stems are the tens", 2.5, ["stems"]),
                stage("leaves", "Put each units digit on its stem, in order", 4.0, ["leaves"]),
                stage(
                    "key", "A key says how to read it", 2.5, ["key", "answer"], emphasise=["key"]
                ),
            ]
        elif params.chart == "bar":
            steps = [
                stage("table", "The frequency table", 2.5, ["question", "table"]),
                stage(
                    "axes",
                    "Frequency up the side, the categories along the bottom, equal "
                    "gaps between the bars",
                    3.0,
                    ["axes"],
                ),
                stage("bars", "Each bar is as tall as its frequency", 3.5, ["bars", "names"]),
                stage("answer", "So", 1.5, ["answer"]),
            ]
        else:
            steps = [
                stage("table", "The frequency table", 2.5, ["question", "table"]),
                stage(
                    "angles",
                    "Each angle is the frequency over the total, times 360 degrees",
                    3.5,
                    ["angle_column"],
                ),
                stage("sectors", "Draw each sector with its angle", 4.0, ["sectors", "names"]),
                stage("answer", "The angles add up to 360 degrees", 2.0, ["answer"]),
            ]

        def standard(s):
            return [combine("start", s[1].description, 3.5, s[0], s[1]), *s[2:]]

        def concise(s):
            return [
                combine("start", s[1].description, 3.5, s[0], s[1]),
                combine("chart", s[2].description, 4.0, s[2], s[3]),
            ]

        return by_level(level, steps, standard, concise)


def _angle(f: int, total: int) -> str:
    return format_sf(sp.Rational(f * 360, total))


def _bars(params, box) -> dict:
    n = len(params.categories)
    top = max(params.frequencies)
    left, bottom = box.left + 0.7, box.bottom + 0.6
    width, height = box.width - 0.9, box.height - 0.9
    step = _nice(top)
    ticks = list(range(0, int(math.ceil(top / step) * step) + 1, step))
    unit = height / ticks[-1]
    axes = VGroup(
        Line([left, bottom, 0], [left + width, bottom, 0], stroke_width=3),
        Line([left, bottom, 0], [left, bottom + height, 0], stroke_width=3),
    )
    for t in ticks:
        y = bottom + t * unit
        axes.add(Line([left - 0.08, y, 0], [left, y, 0], stroke_width=2))
        axes.add(label(str(t), size=22).next_to([left - 0.08, y, 0], [-1, 0, 0], buff=0.08))
    axes.add(
        label(r"\text{Frequency}", size=22).rotate(math.pi / 2).next_to(axes, [-1, 0, 0], buff=0.15)
    )
    slot = width / n
    bars, names = VGroup(), VGroup()
    for i, (name, f) in enumerate(zip(params.categories, params.frequencies, strict=True)):
        x = left + slot * (i + 0.5)
        bars.add(
            Rectangle(
                width=slot * 0.6,
                height=max(f * unit, 1e-3),
                stroke_width=2,
                stroke_color=style.TEXT_COLOUR,
                fill_color=PALETTE[i % 6],
                fill_opacity=0.7,
            ).move_to([x, bottom + f * unit / 2, 0])
        )
        names.add(
            label(rf"\text{{{name}}}", size=22).next_to([x, bottom, 0], [0, -1, 0], buff=0.12)
        )
    return {"axes": axes, "bars": bars, "names": names}


def _nice(top: int) -> int:
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000, 2000):
        if top / step <= 8:
            return step
    return 5000


def _pie(params, box, total) -> dict:
    radius = min(box.width, box.height) / 2 - 0.35
    centre = box.center
    start = math.pi / 2
    sectors, names = VGroup(), VGroup()
    for i, (name, f) in enumerate(zip(params.categories, params.frequencies, strict=True)):
        angle = 2 * math.pi * f / total
        if angle <= 0:
            continue
        sectors.add(
            Sector(
                radius=radius,
                angle=-angle,
                start_angle=start,
                fill_color=PALETTE[i % 6],
                fill_opacity=0.7,
                stroke_color=style.TEXT_COLOUR,
                stroke_width=2,
            ).move_arc_center_to(centre)
        )
        middle = start - angle / 2
        direction = np.array([math.cos(middle), math.sin(middle), 0])
        tag = label(rf"\text{{{name}}}", size=22)
        inside = angle > 0.5 and tag.width < radius * 0.8
        tag.move_to(centre + direction * (radius * 0.62 if inside else radius + 0.35))
        names.add(tag)
        start -= angle
    return {"sectors": sectors, "names": names}


def _stem_leaf(params, area, lower) -> dict:
    values = sorted(params.data)
    stems: dict[int, list[int]] = defaultdict(list)
    for v in values:
        stems[v // 10].append(v % 10)
    stem_range = range(min(stems), max(stems) + 1)
    raw_box, plot_box = split_columns(area, [1, 1.4], gap=0.4)
    raw_lines = VGroup()
    chunk = 6
    for i in range(0, len(params.data), chunk):
        raw_lines.add(label(", ".join(str(v) for v in params.data[i : i + chunk]), size=28))
    raw_lines.arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.2)
    style.fit_inside(raw_lines, raw_box)
    rows = len(stem_range)
    line_height = min(0.55, (plot_box.height - 0.8) / rows)
    x_stem = plot_box.left + 0.6
    stems_group, leaves_group = VGroup(), VGroup()
    for r, stem in enumerate(stem_range):
        y = plot_box.top - 0.3 - line_height * (r + 0.5)
        stems_group.add(label(str(stem), size=30).move_to([x_stem, y, 0]))
        leaves = " \\ ".join(str(leaf) for leaf in stems[stem])
        if leaves:
            leaves_group.add(
                label(leaves, size=30).next_to([x_stem + 0.35, y, 0], [1, 0, 0], buff=0.05)
            )
    divider = Line(
        [x_stem + 0.3, plot_box.top - 0.3, 0],
        [x_stem + 0.3, plot_box.top - 0.3 - line_height * rows, 0],
        stroke_width=3,
    )
    stems_group.add(divider)
    example = values[-1]
    key = (
        label(
            rf"\text{{Key: }} {example // 10} \,|\, {example % 10} \text{{ means {example}}}",
            size=26,
        )
        .next_to(divider, [0, -1, 0], buff=0.3)
        .align_to(stems_group, [-1, 0, 0])
    )
    # the diagram sits in the middle of its column, level with the raw values
    diagram = VGroup(stems_group, leaves_group, key)
    shift = [0, plot_box.center[1] - diagram.get_center()[1], 0]
    diagram.shift(shift)
    raw_lines.set_y(stems_group.get_y())
    return {
        "raw": raw_lines,
        "stems": stems_group,
        "leaves": leaves_group,
        "key": key,
        "answer": text_line(
            rf"\text{{{len(values)} values, from {values[0]} to {values[-1]}}}",
            lower,
            colour=style.HIGHLIGHT_COLOUR,
        ),
    }


def _failure(predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=[parameter]
    )
