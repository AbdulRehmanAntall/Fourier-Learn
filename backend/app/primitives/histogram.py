"""Histogram: a histogram with unequal class widths, where the height of each bar is the frequency
density and its area is the frequency, and an estimate of how many lie in a range read from the
areas (4024 9.7; PRIMITIVES.md #51).

Frequency density = frequency ÷ class width. Bars touch, with no gaps, because the data is
continuous. The number between a and b is estimated by the area of the bars between them,
taking each class to be spread evenly.
"""

from typing import Annotated

import sympy as sp
from manim import Rectangle, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import make_plot, make_table, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf

Number = Annotated[float, Field(ge=-10_000, le=10_000)]
TABLE_REGION = style.Region(x_min=0.62, x_max=1.0, y_min=0.0, y_max=1.0)


class HistogramParams(PrimitiveParams):
    bounds: list[Number] = Field(min_length=3, max_length=8, description="Class boundaries")
    frequencies: list[Annotated[int, Field(ge=0, le=10_000)]] = Field(min_length=2, max_length=7)
    name: Annotated[str, Field(max_length=20)] = "x"
    between: tuple[Number, Number] | None = Field(
        default=None, description="Estimate how many lie between these two values"
    )


class Histogram(StagedPrimitive[HistogramParams]):
    primitive_id = "Histogram"
    version = "1"
    topic = "Statistics"
    params_model = HistogramParams
    layout = LayoutContract(
        region=style.Region(x_min=0.0, x_max=1.0, y_min=0.0, y_max=1.0),
        allowed_overlaps=[("axes", "*"), ("bars", "*"), ("shade", "*"), ("table", "*")],
    )

    def default_params(self) -> HistogramParams:
        return HistogramParams(
            bounds=[0, 10, 15, 20, 30, 50], frequencies=[8, 12, 15, 14, 6], name="time"
        )

    def validate(self, params: HistogramParams) -> list[PredicateFailure]:
        if len(params.bounds) != len(params.frequencies) + 1:
            return [_failure("one_each", "one more boundary than frequencies", "bounds")]
        if any(b <= a for a, b in zip(params.bounds, params.bounds[1:], strict=False)):
            return [_failure("bounds_increase", "the boundaries must increase", "bounds")]
        if params.between is not None:
            a, b = params.between
            if not params.bounds[0] <= a < b <= params.bounds[-1]:
                return [
                    _failure("between_in_range", "the range must lie within the classes", "between")
                ]
        return []

    def computed_values(self, params: HistogramParams) -> dict[str, str]:
        values = {f"density_{i + 1}": format_sf(d) for i, d in enumerate(_densities(params))}
        if params.between is not None:
            values["estimate"] = format_sf(_estimate(params))
        return values

    def build(self, params: HistogramParams, level):
        b = params.bounds
        fd = _densities(params)
        plot = make_plot(
            style.GRAPH_REGION,
            b,
            [0, *(float(d) for d in fd)],
            x_label=rf"\text{{{params.name}}}",
            y_label=r"\text{f.d.}",
            origin=False,
        )
        parts = {"axes": VGroup(plot.axes, plot.x_label, plot.y_label)}
        bars = VGroup()
        palette = [style.CURVE_COLOUR, style.RUN_COLOUR]
        for i, d in enumerate(fd):
            low, high = plot.point(b[i], 0), plot.point(b[i + 1], float(d))
            bars.add(
                Rectangle(
                    width=high[0] - low[0],
                    height=max(high[1] - low[1], 1e-3),
                    stroke_color=style.TEXT_COLOUR,
                    stroke_width=2,
                    fill_color=palette[i % 2],
                    fill_opacity=0.55,
                ).move_to((low + high) / 2)
            )
        parts["bars"] = bars
        rows = [[r"\text{class}", "f", r"\text{width}", r"\text{f.d.}"]]
        for i, (f, d) in enumerate(zip(params.frequencies, fd, strict=True)):
            rows.append(
                [
                    rf"{format_sf(b[i], 6)} \text{{--}} {format_sf(b[i + 1], 6)}",
                    str(f),
                    format_sf(b[i + 1] - b[i], 6),
                    format_sf(d),
                ]
            )
        table = make_table(rows, style.region_box(TABLE_REGION).shrink(0.35), font_size=26)
        parts["table"] = VGroup(table.lines, *(c for row in table.cells for c in row[:2]))
        parts["density_column"] = VGroup(*(c for row in table.cells for c in row[2:]))
        parts["question"] = text_line(
            r"\text{frequency density} = \frac{\text{frequency}}"
            r"{\text{class width}}",
            plot.upper,
            size=34,
        )
        if params.between is not None:
            lo, hi = params.between
            shade = VGroup()
            for i, d in enumerate(fd):
                left, right = max(lo, b[i]), min(hi, b[i + 1])
                if right > left:
                    p, q = plot.point(left, 0), plot.point(right, float(d))
                    shade.add(
                        Rectangle(
                            width=q[0] - p[0],
                            height=max(q[1] - p[1], 1e-3),
                            stroke_width=0,
                            fill_color=style.HIGHLIGHT_COLOUR,
                            fill_opacity=0.55,
                        ).move_to((p + q) / 2)
                    )
            parts["shade"] = shade
            parts["answer"] = text_line(
                rf"\text{{Between {format_sf(lo, 6)} and {format_sf(hi, 6)}: about }} "
                rf"{format_sf(_estimate(params))}",
                plot.lower,
                colour=style.HIGHLIGHT_COLOUR,
            )
        else:
            parts["answer"] = text_line(
                r"\text{Each bar's area is its frequency}",
                plot.lower,
                colour=style.HIGHLIGHT_COLOUR,
            )
        return parts

    def stages(self, params: HistogramParams, level) -> list[Stage]:
        steps = [
            stage("table", "The classes have different widths", 2.5, ["table"]),
            stage(
                "density",
                "Divide each frequency by its class width",
                3.5,
                ["question", "density_column"],
                emphasise=["density_column"],
            ),
            stage(
                "bars",
                "Draw each bar as tall as its frequency density, with no gaps",
                4.0,
                ["axes", "bars"],
            ),
        ]
        if params.between is not None:
            steps.append(
                stage(
                    "estimate",
                    "The number in the range is the area of the bars over it",
                    4.0,
                    ["shade", "answer"],
                    emphasise=["shade"],
                )
            )
        else:
            steps.append(
                stage("answer", "So the area of each bar is its frequency", 2.5, ["answer"])
            )

        def concise(s):
            return [combine("table", s[1].description, 4.0, s[0], s[1]), *s[2:]]

        return by_level(level, steps, lambda s: s, concise)


def _densities(params: HistogramParams) -> list[sp.Rational]:
    b = [sp.nsimplify(v) for v in params.bounds]
    return [sp.Integer(f) / (b[i + 1] - b[i]) for i, f in enumerate(params.frequencies)]


def _estimate(params: HistogramParams) -> sp.Expr:
    lo, hi = (sp.nsimplify(v) for v in params.between)
    b = [sp.nsimplify(v) for v in params.bounds]
    total = sp.Integer(0)
    for i, d in enumerate(_densities(params)):
        overlap = min(hi, b[i + 1]) - max(lo, b[i])
        if overlap > 0:
            total += d * overlap
    return total


def _failure(predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=[parameter]
    )
