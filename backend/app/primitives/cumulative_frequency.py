"""CumulativeFrequency: the cumulative frequency table and curve (ogive) for grouped data, and
the median, quartiles and interquartile range read from it, with how many lie below a value
(4024 9.6; PRIMITIVES.md #50).

Each running total is plotted at the upper boundary of its class, starting from 0 at the lower
boundary of the first class, and the points are joined by a smooth increasing curve. The median
is read across from n/2, the lower and upper quartiles from n/4 and 3n/4; the interquartile
range is the upper quartile take the lower.
"""

from typing import Annotated

import numpy as np
from manim import DashedLine, Dot, VGroup, VMobject
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import make_plot, make_table, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf

Number = Annotated[float, Field(ge=-10_000, le=10_000)]
TABLE_REGION = style.Region(x_min=0.62, x_max=1.0, y_min=0.0, y_max=1.0)


class CumulativeFrequencyParams(PrimitiveParams):
    bounds: list[Number] = Field(min_length=3, max_length=9, description="Class boundaries")
    frequencies: list[Annotated[int, Field(ge=0, le=10_000)]] = Field(min_length=2, max_length=8)
    name: Annotated[str, Field(max_length=20)] = "x"
    below: Number | None = Field(default=None, description="Read how many lie below this value")


class CumulativeFrequency(StagedPrimitive[CumulativeFrequencyParams]):
    primitive_id = "CumulativeFrequency"
    version = "1"
    topic = "Statistics"
    params_model = CumulativeFrequencyParams
    # the graph on the left, the running-total table in the working region on the right
    layout = LayoutContract(
        region=style.Region(x_min=0.0, x_max=1.0, y_min=0.0, y_max=1.0),
        allowed_overlaps=[
            ("axes", "*"),
            ("curve", "*"),
            ("points", "*"),
            ("reads", "*"),
            ("below_read", "*"),
        ],
    )

    def default_params(self) -> CumulativeFrequencyParams:
        return CumulativeFrequencyParams(
            bounds=[0, 10, 20, 30, 40, 50], frequencies=[4, 11, 19, 12, 4], name="time"
        )

    def validate(self, params: CumulativeFrequencyParams) -> list[PredicateFailure]:
        if len(params.bounds) != len(params.frequencies) + 1:
            return [_failure("one_each", "one more boundary than frequencies", "bounds")]
        if any(b <= a for a, b in zip(params.bounds, params.bounds[1:], strict=False)):
            return [_failure("bounds_increase", "the boundaries must increase", "bounds")]
        if sum(params.frequencies) < 4:
            return [_failure("enough_data", "at least 4 values are needed", "frequencies")]
        if params.below is not None and not params.bounds[0] <= params.below <= params.bounds[-1]:
            return [_failure("below_in_range", "the value is outside the classes", "below")]
        return []

    def computed_values(self, params: CumulativeFrequencyParams) -> dict[str, str]:
        reads = _reads(params)
        values = {k: format_sf(v) for k, v in reads.items()}
        if params.below is not None:
            values["below"] = format_sf(_curve(params)(params.below))
        return values

    def build(self, params: CumulativeFrequencyParams, level):
        n = sum(params.frequencies)
        xs, cf = _points(params)
        plot = make_plot(
            style.GRAPH_REGION,
            xs,
            [0, n],
            x_label=rf"\text{{{params.name}}}",
            y_label=r"\text{cum. freq.}",
            origin=False,
        )
        f = _curve(params)
        parts = {"axes": VGroup(plot.axes, plot.x_label, plot.y_label)}
        parts["points"] = VGroup(
            *(
                Dot(plot.point(x, y), radius=0.06, color=style.POINT_COLOUR)
                for x, y in zip(xs, cf, strict=True)
            )
        )
        samples = np.linspace(xs[0], xs[-1], 120)
        curve = VMobject(color=style.CURVE_COLOUR, stroke_width=4)
        curve.set_points_smoothly([plot.point(x, f(x)) for x in samples])
        parts["curve"] = curve
        reads = _reads(params)
        colours = {
            "lower_quartile": style.RUN_COLOUR,
            "median": style.HIGHLIGHT_COLOUR,
            "upper_quartile": style.RUN_COLOUR,
        }
        heights = {"lower_quartile": n / 4, "median": n / 2, "upper_quartile": 3 * n / 4}
        group = VGroup()
        for key, height in heights.items():
            x = reads[key]
            colour = colours[key]
            group.add(
                DashedLine(
                    plot.point(plot.x_range[0], height),
                    plot.point(x, height),
                    color=colour,
                    stroke_width=2,
                ),
                DashedLine(
                    plot.point(x, height),
                    plot.point(x, plot.y_range[0]),
                    color=colour,
                    stroke_width=2,
                ),
            )
        parts["reads"] = group
        if params.below is not None:
            y = f(params.below)
            parts["below_read"] = VGroup(
                DashedLine(
                    plot.point(params.below, plot.y_range[0]),
                    plot.point(params.below, y),
                    color=style.RISE_COLOUR,
                    stroke_width=3,
                ),
                DashedLine(
                    plot.point(params.below, y),
                    plot.point(plot.x_range[0], y),
                    color=style.RISE_COLOUR,
                    stroke_width=3,
                ),
            )
        rows = [[r"\text{upper bound}", r"\text{c.f.}"]]
        rows += [[format_sf(x, 6), str(int(c))] for x, c in zip(xs[1:], cf[1:], strict=True)]
        parts["table"] = make_table(
            rows, style.region_box(TABLE_REGION).shrink(0.4), font_size=26
        ).group
        parts["question"] = text_line(rf"n = {n}", plot.upper, size=34)
        parts["results"] = text_line(
            rf"Q_1 = {format_sf(reads['lower_quartile'])},\ \text{{median}} = "
            rf"{format_sf(reads['median'])},\ Q_3 = {format_sf(reads['upper_quartile'])},\ "
            rf"\text{{IQR}} = {format_sf(reads['iqr'])}",
            plot.lower,
            colour=style.HIGHLIGHT_COLOUR,
            size=32,
        )
        if params.below is not None:
            parts["below_text"] = text_line(
                rf"\text{{Below {format_sf(params.below, 6)}: about }} "
                rf"{format_sf(f(params.below))}",
                plot.upper,
                colour=style.RISE_COLOUR,
                size=34,
            )
        return parts

    def stages(self, params: CumulativeFrequencyParams, level) -> list[Stage]:
        steps = [
            stage(
                "table",
                "Add up the frequencies as you go: the running totals",
                3.5,
                ["question", "table"],
            ),
            stage(
                "points",
                "Plot each total at the upper end of its class, starting from 0",
                3.5,
                ["axes", "points"],
            ),
            stage("curve", "Join them with a smooth curve", 2.5, ["curve"]),
            stage(
                "reads",
                "Read across from n over 2 for the median, n over 4 and 3n over 4 "
                "for the quartiles",
                4.5,
                ["reads", "results"],
            ),
        ]
        if params.below is not None:
            steps.append(
                stage(
                    "below",
                    "Read up from the value and across to count those below",
                    3.0,
                    ["below_read", "below_text"],
                    hide=["question"],
                )
            )

        def concise(s):
            return [combine("graph", "Plot the running totals and join them", 4.0, *s[:3]), *s[3:]]

        return by_level(level, steps, lambda s: s, concise)


def _points(params: CumulativeFrequencyParams) -> tuple[list[float], list[float]]:
    cf = [0.0]
    for f in params.frequencies:
        cf.append(cf[-1] + f)
    return list(params.bounds), cf


def _curve(params: CumulativeFrequencyParams):
    """A smooth increasing curve through the points (monotone cubic, Fritsch-Carlson)."""
    xs, ys = (np.array(v, dtype=float) for v in _points(params))
    h = np.diff(xs)
    delta = np.diff(ys) / h
    m = np.zeros_like(xs)
    m[0], m[-1] = delta[0], delta[-1]
    for i in range(1, len(xs) - 1):
        if delta[i - 1] * delta[i] <= 0:
            m[i] = 0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / delta[i - 1] + w2 / delta[i])

    def f(x: float) -> float:
        i = min(max(np.searchsorted(xs, x) - 1, 0), len(h) - 1)
        t = (x - xs[i]) / h[i]
        h00, h10 = 2 * t**3 - 3 * t**2 + 1, t**3 - 2 * t**2 + t
        h01, h11 = -2 * t**3 + 3 * t**2, t**3 - t**2
        return float(h00 * ys[i] + h10 * h[i] * m[i] + h01 * ys[i + 1] + h11 * h[i] * m[i + 1])

    return f


def _inverse(f, target: float, lo: float, hi: float) -> float:
    for _ in range(60):
        mid = (lo + hi) / 2
        if f(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _reads(params: CumulativeFrequencyParams) -> dict[str, float]:
    n = sum(params.frequencies)
    f = _curve(params)
    lo, hi = params.bounds[0], params.bounds[-1]
    q1, med, q3 = (_inverse(f, n * k / 4, lo, hi) for k in (1, 2, 3))
    return {"lower_quartile": q1, "median": med, "upper_quartile": q3, "iqr": q3 - q1}


def _failure(predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=[parameter]
    )
