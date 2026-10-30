"""BoxPlot: raw data ordered in a stem-and-leaf diagram (back-to-back for two sets), then its
quartiles read off and drawn as a box-and-whisker plot on a scale, to compare two sets of data
(9709 5.1).

The data are put in order. The median is the middle value (the mean of the middle two for an
even count); the lower quartile is the median of the values below the median and the upper
quartile the median of those above (the middle value itself is left out when the count is odd).
The box runs from the lower to the upper quartile with a line at the median, and the whiskers
reach the least and greatest values. The interquartile range is the width of the box. Values are
exact; the stem-and-leaf diagram needs whole numbers.
"""

from statistics import median
from typing import Annotated

import sympy as sp
from manim import Line, NumberLine, Rectangle, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import axis_range, label, make_table, stack_lines
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_sf

Value = Annotated[float, Field(ge=0, le=999)]
Name = Annotated[str, StringConstraints(max_length=16)]
COLOURS = [style.CURVE_COLOUR, style.RUN_COLOUR]


class BoxPlotParams(PrimitiveParams):
    data: list[Value] = Field(min_length=5, max_length=30)
    data_2: list[Value] | None = Field(
        default=None, min_length=5, max_length=30, description="A second set to compare"
    )
    names: tuple[Name, Name] = Field(default=("A", "B"), description="Names of the two sets")
    stem_leaf: bool = Field(default=True, description="Show the stem-and-leaf diagram first")


class BoxPlot(StagedPrimitive[BoxPlotParams]):
    primitive_id = "BoxPlot"
    version = "1"
    topic = "Representation of data"
    params_model = BoxPlotParams
    layout = LayoutContract(
        region=FULL_FRAME, allowed_overlaps=[("box_*", "scale"), ("scale", "*")]
    )

    def default_params(self) -> BoxPlotParams:
        return BoxPlotParams(data=[12, 15, 18, 21, 22, 25, 27, 30, 31, 34, 38, 41, 45])

    def validate(self, params: BoxPlotParams) -> list[PredicateFailure]:
        if params.stem_leaf:
            values = [*params.data, *(params.data_2 or [])]
            if any(v != int(v) for v in values):
                message = "a stem-and-leaf diagram needs whole numbers; set stem_leaf false"
                return [_failure("whole_numbers", message, "data", "stem_leaf")]
            if len({int(v) // 10 for v in values}) > 9:
                return [_failure("stems_fit", "the data spread over too many stems", "data")]
        return []

    def computed_values(self, params: BoxPlotParams) -> dict[str, str]:
        out = {}
        for i, data in enumerate(_sets(params), start=1):
            s = _summary(data)
            for key, value in s.items():
                out[f"{key}_{i}"] = str(value)
        return out

    def build(self, params: BoxPlotParams, level):
        sets = _sets(params)
        summaries = [_summary(d) for d in sets]
        area = style.region_box(style.GRAPH_REGION).shrink(style.PADDING)
        parts = {}
        split = area.top - (3.6 if params.stem_leaf else 0.6)
        if params.stem_leaf:
            table_box = style.Box(area.left, area.right, split + 0.2, area.top)
            rows, colours = _stem_leaf_rows(params, sets)
            table = make_table(rows, table_box, font_size=28, pad=0.12, colours=colours)
            parts["stem_leaf"] = table.group
            parts["key"] = label(_key(params, sets), size=22).next_to(
                table.group, [0, -1, 0], buff=0.08
            )
        values = [v for d in sets for v in d]
        lo, hi, step = axis_range([min(values), max(values)], ticks=8, origin=False)
        scale = NumberLine(
            x_range=[lo, hi, step], length=area.width - 0.6, include_numbers=True, font_size=22
        )
        scale.move_to([area.center[0], area.bottom + 0.5, 0])
        parts["scale"] = scale
        band = (split - 0.2 - (area.bottom + 1.0)) / len(sets)
        for i, s in enumerate(summaries):
            y = area.bottom + 1.0 + band * (i + 0.5)
            colour = COLOURS[i]
            x = {
                k: scale.n2p(float(v))[0]
                for k, v in s.items()
                if k in ("min", "q1", "median", "q3", "max")
            }
            height = min(0.7, band * 0.55)
            box = Rectangle(
                width=x["q3"] - x["q1"], height=height, color=colour, fill_opacity=0.25
            ).move_to([(x["q1"] + x["q3"]) / 2, y, 0])
            whiskers = VGroup(
                Line([x["min"], y, 0], [x["q1"], y, 0], color=colour, stroke_width=3),
                Line([x["q3"], y, 0], [x["max"], y, 0], color=colour, stroke_width=3),
                Line(
                    [x["min"], y - height / 3, 0],
                    [x["min"], y + height / 3, 0],
                    color=colour,
                    stroke_width=3,
                ),
                Line(
                    [x["max"], y - height / 3, 0],
                    [x["max"], y + height / 3, 0],
                    color=colour,
                    stroke_width=3,
                ),
            )
            median_line = Line(
                [x["median"], y - height / 2, 0],
                [x["median"], y + height / 2, 0],
                color=style.HIGHLIGHT_COLOUR,
                stroke_width=4,
            )
            parts[f"box_{i}"] = VGroup(box, whiskers, median_line)
            if len(sets) == 2:
                parts[f"name_{i}"] = label(
                    rf"\text{{{params.names[i]}}}", colour=colour, size=26
                ).next_to(box, [0, 1, 0], buff=0.08)
        rows = []
        for i, s in enumerate(summaries):
            prefix = rf"\text{{{params.names[i]}: }}" if len(sets) == 2 else ""
            rows += [
                (
                    rf"{prefix}n = {s['n']},\ \text{{median}} = {_num(s['median'])}",
                    COLOURS[i],
                ),
                (rf"Q_1 = {_num(s['q1'])},\ Q_3 = {_num(s['q3'])}", None),
                (
                    rf"\text{{IQR}} = {_num(s['iqr'])},\ "
                    rf"\text{{range}} = {_num(s['range'])}",
                    None,
                ),
            ]
        if len(sets) == 2:
            rows.append((_comparison(params, summaries), style.HIGHLIGHT_COLOUR))
        box_area = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], box_area, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: BoxPlotParams, level) -> list[Stage]:
        sets = _sets(params)
        steps = []
        if params.stem_leaf:
            steps.append(
                stage(
                    "stem_leaf",
                    "Order the data in a stem-and-leaf diagram"
                    + (", back to back" if len(sets) == 2 else ""),
                    3.5,
                    ["stem_leaf", "key"],
                )
            )
        for i in range(len(sets)):
            base = 3 * i
            steps.append(
                stage(
                    f"quartiles_{i}",
                    "Count the values: the median is the middle one, the quartiles the middles of "
                    "each half",
                    3.5,
                    [f"row_{base + 1}", f"row_{base + 2}"],
                )
            )
            steps.append(
                stage(
                    f"box_{i}",
                    "Draw the box from Q1 to Q3, the median inside it, and whiskers to the "
                    "extremes",
                    3.5,
                    ([] if i else ["scale"])
                    + [f"box_{i}", f"row_{base + 3}"]
                    + ([f"name_{i}"] if len(sets) == 2 else []),
                )
            )
        if len(sets) == 2:
            steps.append(
                stage(
                    "compare",
                    "Compare a measure of centre and a measure of spread",
                    3.5,
                    ["row_7"],
                    emphasise=["row_7"],
                )
            )

        def standard(s):
            return list(s)

        def concise(s):
            out, head = [], 1 if params.stem_leaf else 0
            out += s[:head]
            for i in range(len(sets)):
                q, b = s[head + 2 * i], s[head + 2 * i + 1]
                out.append(combine(b.name, "Quartiles, then the box plot", 4.0, q, b))
            return out + s[head + 2 * len(sets) :]

        return by_level(level, steps, standard, concise)


def _num(value) -> str:
    """Statistics are written as decimals: 19.5, not 39/2."""
    return format_sf(value, 6)


def _sets(params: BoxPlotParams) -> list[list]:
    sets = [sorted(exact(v) for v in params.data)]
    if params.data_2:
        sets.append(sorted(exact(v) for v in params.data_2))
    return sets


def _summary(data) -> dict:
    n = len(data)
    half = n // 2
    lower, upper = data[:half], data[n - half :]
    q1, q2, q3 = (sp.nsimplify(median(part)) for part in (lower, data, upper))
    return {
        "n": n,
        "min": data[0],
        "q1": q1,
        "median": q2,
        "q3": q3,
        "max": data[-1],
        "iqr": q3 - q1,
        "range": data[-1] - data[0],
    }


def _stem_leaf_rows(params, sets):
    stems = sorted({int(v) // 10 for d in sets for v in d})
    rows, colours = [], []
    for stem in stems:
        right = " ".join(str(int(v) % 10) for v in sets[0] if int(v) // 10 == stem)
        if len(sets) == 2:
            left = " ".join(str(int(v) % 10) for v in reversed(sets[1]) if int(v) // 10 == stem)
            rows.append([rf"\text{{{left}}}", str(stem), rf"\text{{{right}}}"])
            colours.append([COLOURS[1], style.TEXT_COLOUR, COLOURS[0]])
        else:
            rows.append([str(stem), rf"\text{{{right}}}"])
            colours.append([style.TEXT_COLOUR, COLOURS[0]])
    return rows, colours


def _key(params, sets) -> str:
    v = int(sets[0][0])
    text = rf"\text{{Key: }}{v // 10}\,|\,{v % 10}\text{{ means {v}}}"
    if len(sets) == 2:
        w = int(sets[1][0])
        a, b = params.names
        text = (
            rf"\text{{Key: }}{w % 10}\,|\,{w // 10}\,|\,{v % 10}"
            rf"\text{{ means {w} for {b}, {v} for {a}}}"
        )
    return text


def _comparison(params, summaries) -> str:
    a, b = summaries
    higher = params.names[0] if a["median"] > b["median"] else params.names[1]
    wider = params.names[0] if a["iqr"] > b["iqr"] else params.names[1]
    return rf"\text{{{higher}: higher median; {wider}: more spread (IQR)}}"


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
