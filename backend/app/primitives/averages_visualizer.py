"""AveragesVisualizer: mean, median, mode and range from a list, a frequency table or grouped data
(4024 9.2, 9.3; PRIMITIVES.md #48).

A list is put in order: the median is the middle value (the mean of the middle two for an even
count), the mode the most common, the range the largest take the smallest, and the mean the total
over the count, the balance point of a dot plot. A frequency table gives the mean as Σfx ÷ Σf and
the median from the running total. Grouped data uses the midpoints for an estimate of the mean,
and names the modal class and the class containing the median.
"""

from collections import Counter
from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import Dot, Line, Rectangle, SurroundingRectangle, Triangle, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, make_table, split_columns, stack_boxes, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf

Number = Annotated[float, Field(ge=-10_000, le=10_000)]
Count = Annotated[int, Field(ge=0, le=10_000)]


class AveragesVisualizerParams(PrimitiveParams):
    kind: Literal["list", "table", "grouped"]
    data: list[Number] | None = Field(default=None, min_length=2, max_length=20)
    values: list[Number] | None = Field(
        default=None, min_length=2, max_length=8, description="For table: the values x"
    )
    bounds: list[Number] | None = Field(
        default=None,
        min_length=3,
        max_length=9,
        description="For grouped: the class boundaries, e.g. [0, 10, 20, 30]",
    )
    frequencies: list[Count] | None = Field(default=None, min_length=2, max_length=8)


class AveragesVisualizer(StagedPrimitive[AveragesVisualizerParams]):
    primitive_id = "AveragesVisualizer"
    version = "1"
    topic = "Statistics"
    params_model = AveragesVisualizerParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("strip", "*"),
            ("marks", "*"),
            ("dots", "*"),
            ("balance", "*"),
            ("table", "*"),
        ],
    )

    def default_params(self) -> AveragesVisualizerParams:
        return AveragesVisualizerParams(kind="list", data=[4, 7, 2, 9, 7, 3, 5, 7, 6])

    def validate(self, params: AveragesVisualizerParams) -> list[PredicateFailure]:
        if params.kind == "list":
            if params.data is None:
                return [_failure("needs_data", "give the list of values", "data")]
            return []
        if params.frequencies is None:
            return [_failure("needs_frequencies", "give the frequencies", "frequencies")]
        if sum(params.frequencies) == 0:
            return [_failure("nonzero_total", "the frequencies add to 0", "frequencies")]
        if params.kind == "table":
            if params.values is None or len(params.values) != len(params.frequencies):
                return [_failure("one_each", "one frequency per value", "values")]
            return []
        if params.bounds is None or len(params.bounds) != len(params.frequencies) + 1:
            return [_failure("one_each", "one more boundary than frequencies", "bounds")]
        if any(b <= a for a, b in zip(params.bounds, params.bounds[1:], strict=False)):
            return [_failure("bounds_increase", "the boundaries must increase", "bounds")]
        return []

    def computed_values(self, params: AveragesVisualizerParams) -> dict[str, str]:
        stats = _stats(params)
        return {k: (v if isinstance(v, str) else format_sf(v)) for k, v in stats.items()}

    def build(self, params: AveragesVisualizerParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        stats = _stats(params)
        parts = {}
        if params.kind == "list":
            parts.update(_list_parts(params, area))
            rows = _list_rows(params, stats)
            working_box = parts.pop("_working_box")
        else:
            table_box, working_box = split_columns(area, [1.3, 1], gap=0.3)
            parts.update(_table_parts(params, table_box))
            rows = _table_rows(params, stats)
        mobjects = [label(t, size=28) for t in rows]
        group = VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.25)
        for mob in mobjects:
            if mob.width > working_box.width:
                mob.scale_to_fit_width(working_box.width)
        style.fit_inside(group.arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.25), working_box)
        for i, mob in enumerate(mobjects, start=1):
            parts[f"row_{i}"] = mob
        question = {
            "list": r"\text{The averages of the data}",
            "table": r"\text{The averages from the frequency table}",
            "grouped": r"\text{Estimate the mean of the grouped data}",
        }[params.kind]
        parts["question"] = text_line(question, upper)
        if params.kind == "grouped":
            answer = rf"\text{{mean}} \approx {format_sf(stats['mean'])}"
        else:
            answer = (
                rf"\text{{mean}} = {format_sf(stats['mean'])},\ \text{{median}} = "
                rf"{format_sf(stats['median'])},\ \text{{mode}} = \text{{{stats['mode']}}}"
            )
        parts["answer"] = text_line(answer, lower, colour=style.HIGHLIGHT_COLOUR)
        return parts

    def stages(self, params: AveragesVisualizerParams, level) -> list[Stage]:
        n_rows = len(
            _list_rows(params, _stats(params))
            if params.kind == "list"
            else _table_rows(params, _stats(params))
        )
        rows = [f"row_{i}" for i in range(1, n_rows + 1)]
        if params.kind == "list":
            steps = [
                stage("order", "Put the values in order", 3.0, ["question", "strip"]),
                stage(
                    "median",
                    "The median is in the middle; the mode is the most common; "
                    "the range is largest take smallest",
                    4.0,
                    ["marks", *rows[1:4]],
                ),
                stage(
                    "mean",
                    "The mean is the total over how many: the balance point",
                    4.0,
                    ["dots", "balance", rows[0]],
                ),
            ]
        else:
            what = (
                "Multiply each value by its frequency"
                if params.kind == "table"
                else "Use the midpoint of each class, times its frequency"
            )
            steps = [
                stage("table", "Here is the table", 2.5, ["question", "table"]),
                stage("fx", what, 3.5, ["extra_columns"]),
                stage("mean", "Mean is the total of fx over the total frequency", 3.5, rows[:2]),
                stage("others", "The mode and the median from the frequencies", 3.5, rows[2:]),
            ]
        steps.append(stage("answer", "So", 1.5, ["answer"], emphasise=["answer"]))

        def concise(s):
            return [
                combine("start", s[1].description, 4.0, s[0], s[1]),
                combine("rest", "And the rest", 4.0, *s[2:]),
            ]

        return by_level(level, steps, lambda s: s, concise)


def _stats(params: AveragesVisualizerParams) -> dict:
    if params.kind == "list":
        values = sorted(sp.nsimplify(v) for v in params.data)
        n = len(values)
        median = (values[(n - 1) // 2] + values[n // 2]) / 2
        counts = Counter(values)
        top = max(counts.values())
        modes = sorted(v for v, c in counts.items() if c == top)
        mode = "none" if top == 1 else ", ".join(format_sf(m) for m in modes)
        return {
            "mean": sum(values) / n,
            "median": median,
            "mode": mode,
            "range": values[-1] - values[0],
        }
    f = [sp.Integer(x) for x in params.frequencies]
    total = sum(f)
    if params.kind == "table":
        x = [sp.nsimplify(v) for v in params.values]
        order = sorted(range(len(x)), key=lambda i: x[i])

        def value_at(k: int):
            """The k-th value in order (counting from 1)."""
            running = 0
            for i in order:
                running += f[i]
                if running >= k:
                    return x[i]
            return x[order[-1]]

        median = (value_at(int(total + 1) // 2) + value_at(int(total + 2) // 2)) / 2
        top = max(f)
        modes = [x[i] for i in range(len(x)) if f[i] == top]
        mode = "none" if len(modes) == len(x) else ", ".join(format_sf(m) for m in modes)
        return {
            "mean": sum(a * b for a, b in zip(x, f, strict=True)) / total,
            "median": median,
            "mode": mode,
            "range": max(x) - min(x),
        }
    b = [sp.nsimplify(v) for v in params.bounds]
    mids = [(b[i] + b[i + 1]) / 2 for i in range(len(f))]
    modal = max(range(len(f)), key=lambda i: f[i])
    running, median_class = 0, 0
    for i, count in enumerate(f):
        running += count
        if running >= total / 2:
            median_class = i
            break
    return {
        "mean": sum(m * c for m, c in zip(mids, f, strict=True)) / total,
        "modal_class": f"{format_sf(b[modal])} - {format_sf(b[modal + 1])}",
        "median_class": f"{format_sf(b[median_class])} - {format_sf(b[median_class + 1])}",
    }


def _list_parts(params, area) -> dict:
    values = sorted(params.data)
    n = len(values)
    strip_box, plot_box = stack_boxes(
        style.Box(area.left, area.left + area.width * 0.58, area.bottom, area.top), 2, gap=0.3
    )
    size = min(0.6, strip_box.width / n)
    strip = VGroup()
    for i, v in enumerate(values):
        cell = Rectangle(width=size, height=size, stroke_width=2, stroke_color=style.TEXT_COLOUR)
        cell.move_to([strip_box.left + size * (i + 0.5), strip_box.center[1], 0])
        strip.add(cell, label(format_sf(v, 6), size=min(26, size * 45)).move_to(cell))
    middle = [(n - 1) // 2, n // 2]
    marks = VGroup(
        *(
            SurroundingRectangle(strip[2 * i], color=style.HIGHLIGHT_COLOUR, buff=0.03)
            for i in set(middle)
        )
    )
    counts = Counter(values)
    top = max(counts.values())
    if top > 1:
        for i, v in enumerate(values):
            if counts[v] == top:
                marks.add(
                    Dot(
                        strip[2 * i].get_bottom() + [0, -0.12, 0],
                        radius=0.05,
                        color=style.RUN_COLOUR,
                    )
                )
    # a dot plot with the mean as the balance point underneath
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    left, right = plot_box.left + 0.3, plot_box.right - 0.3
    y = plot_box.bottom + 0.6

    def at(v):
        return np.array([left + (v - lo) / span * (right - left), y, 0])

    dots = VGroup(Line(at(lo) + [-0.2, 0, 0], at(hi) + [0.2, 0, 0], stroke_width=3))
    seen: Counter = Counter()
    for v in values:
        seen[v] += 1
        dots.add(Dot(at(v) + [0, 0.22 * seen[v], 0], radius=0.08, color=style.CURVE_COLOUR))
    for v in sorted(set(values)):
        dots.add(label(format_sf(v, 6), size=20).next_to(at(v), [0, -1, 0], buff=0.12))
    mean = float(sum(values)) / n
    balance = VGroup(
        Triangle(color=style.HIGHLIGHT_COLOUR, fill_opacity=1)
        .scale(0.12)
        .move_to(at(mean) + [0, -0.45, 0]),
        label(
            rf"\text{{mean}} = {format_sf(sp.nsimplify(sum(values)) / n)}",
            colour=style.HIGHLIGHT_COLOUR,
            size=24,
        ).next_to(at(mean) + [0, -0.55, 0], [0, -1, 0], buff=0.05),
    )
    working = style.Box(area.left + area.width * 0.62, area.right, area.bottom, area.top)
    return {
        "strip": strip,
        "marks": marks,
        "dots": dots,
        "balance": balance,
        "_working_box": working,
    }


def _list_rows(params, stats) -> list[str]:
    n = len(params.data)
    total = sum(sp.nsimplify(v) for v in params.data)
    position = sp.Rational(n + 1, 2)
    return [
        rf"\text{{mean}} = \frac{{{format_sf(total, 6)}}}{{{n}}} = {format_sf(stats['mean'])}",
        rf"\text{{median: the }} {format_sf(position)}\text{{th value}} = "
        rf"{format_sf(stats['median'])}",
        rf"\text{{mode}} = \text{{{stats['mode']}}}",
        rf"\text{{range}} = {format_sf(stats['range'])}",
    ]


def _table_parts(params, box) -> dict:
    f = params.frequencies
    if params.kind == "table":
        header = ["x", "f", "fx"]
        rows = [
            [format_sf(x, 6), str(c), format_sf(x * c, 6)]
            for x, c in zip(params.values, f, strict=True)
        ]
    else:
        header = [r"\text{class}", "f", r"\text{mid } x", "fx"]
        b = params.bounds
        rows = []
        for i, c in enumerate(f):
            mid = (b[i] + b[i + 1]) / 2
            rows.append(
                [
                    rf"{format_sf(b[i], 6)} \le x < {format_sf(b[i + 1], 6)}",
                    str(c),
                    format_sf(mid, 6),
                    format_sf(mid * c, 6),
                ]
            )
    total_fx = sum(sp.nsimplify(r[-1]) for r in rows)
    footer = [r"\text{total}", str(sum(f))] + [""] * (len(header) - 3) + [format_sf(total_fx, 6)]
    table = make_table([header, *rows, footer], box, font_size=26)
    plain = 2  # the first two columns are the data; the rest come in their own step
    first = VGroup(table.lines, *(c for row in table.cells for c in row[:plain]))
    extra = VGroup(*(c for row in table.cells for c in row[plain:]))
    return {"table": first, "extra_columns": extra}


def _table_rows(params, stats) -> list[str]:
    f = params.frequencies
    if params.kind == "table":
        total_fx = sum(sp.nsimplify(x) * c for x, c in zip(params.values, f, strict=True))
        return [
            rf"\text{{mean}} = \frac{{\Sigma fx}}{{\Sigma f}} = \frac{{{format_sf(total_fx, 6)}}}"
            rf"{{{sum(f)}}}",
            rf"= {format_sf(stats['mean'])}",
            rf"\text{{mode}} = \text{{{stats['mode']}}}",
            rf"\text{{median}} = {format_sf(stats['median'])}",
        ]
    b = params.bounds
    total_fx = sum((sp.nsimplify(b[i]) + sp.nsimplify(b[i + 1])) / 2 * c for i, c in enumerate(f))
    return [
        rf"\text{{mean}} \approx \frac{{{format_sf(total_fx, 6)}}}{{{sum(f)}}}",
        rf"\approx {format_sf(stats['mean'])}",
        rf"\text{{modal class: }} {stats['modal_class']}",
        rf"\text{{median class: }} {stats['median_class']}",
    ]


def _failure(predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=[parameter]
    )
