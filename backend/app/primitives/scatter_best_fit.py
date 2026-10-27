"""ScatterBestFit: a scatter graph, the type and strength of correlation, the line of best fit
through the mean point, and an estimate read from the line, with a warning when it lies outside
the data (4024 9.5; PRIMITIVES.md #49).

The mean point (x̄, ȳ) is marked first: a line of best fit goes through it. The line drawn is
the least-squares line, which does. The correlation is named from the correlation coefficient:
positive or negative by its sign, strong above 0.7, weak below 0.3 (where it is called none).
"""

import math
from typing import Annotated

import numpy as np
from manim import Cross, DashedLine, Dot, Line, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, make_plot, place_label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf

Name = Annotated[str, StringConstraints(strip_whitespace=True, max_length=24)]
Point = tuple[
    Annotated[float, Field(ge=-10_000, le=10_000)], Annotated[float, Field(ge=-10_000, le=10_000)]
]


class ScatterBestFitParams(PrimitiveParams):
    points: list[Point] = Field(min_length=5, max_length=30)
    x_name: Name = "x"
    y_name: Name = "y"
    estimate_x: Annotated[float, Field(ge=-10_000, le=10_000)] | None = Field(
        default=None, description="Estimate y at this x from the line"
    )


class ScatterBestFit(StagedPrimitive[ScatterBestFitParams]):
    primitive_id = "ScatterBestFit"
    version = "1"
    topic = "Statistics"
    params_model = ScatterBestFitParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("axes", "*"),
            ("points", "*"),
            ("line", "*"),
            ("estimate", "*"),
            ("mean_point", "*"),
        ],
    )

    def default_params(self) -> ScatterBestFitParams:
        return ScatterBestFitParams(
            points=[(2, 52), (3, 55), (5, 61), (6, 60), (8, 70), (9, 71), (11, 78)],
            x_name="hours",
            y_name="score",
            estimate_x=7,
        )

    def validate(self, params: ScatterBestFitParams) -> list[PredicateFailure]:
        xs = [p[0] for p in params.points]
        if max(xs) == min(xs):
            return [_failure("x_varies", "the x values are all the same", "points")]
        return []

    def computed_values(self, params: ScatterBestFitParams) -> dict[str, str]:
        fit = _fit(params)
        values = {
            "correlation": fit["words"],
            "r": format_sf(fit["r"]),
            "gradient": format_sf(fit["m"]),
            "intercept": format_sf(fit["c"]),
        }
        if params.estimate_x is not None:
            values["estimate"] = format_sf(fit["m"] * params.estimate_x + fit["c"])
        return values

    def build(self, params: ScatterBestFitParams, level):
        fit = _fit(params)
        region = style.GRAPH_REGION
        xs = [p[0] for p in params.points]
        ys = [p[1] for p in params.points]
        if params.estimate_x is not None:
            xs.append(params.estimate_x)
            ys.append(fit["m"] * params.estimate_x + fit["c"])
        plot = make_plot(
            region,
            xs,
            ys,
            x_label=rf"\text{{{params.x_name}}}",
            y_label=rf"\text{{{params.y_name}}}",
            origin=False,
        )
        parts = {"axes": VGroup(plot.axes, plot.x_label, plot.y_label)}
        parts["points"] = VGroup(
            *(
                Cross(scale_factor=0.09, stroke_width=4, stroke_color=style.CURVE_COLOUR).move_to(
                    plot.point(*p)
                )
                for p in params.points
            )
        )
        mx, my = fit["mean"]
        parts["mean_point"] = VGroup(
            Dot(plot.point(mx, my), radius=0.09, color=style.HIGHLIGHT_COLOUR),
        )
        x0, x1 = plot.x_range[0], plot.x_range[1]
        y_lo, y_hi = plot.y_range[0], plot.y_range[1]
        ends = []
        for x in (x0, x1):
            y = fit["m"] * x + fit["c"]
            if not y_lo <= y <= y_hi and fit["m"] != 0:
                y = min(max(y, y_lo), y_hi)
                x = (y - fit["c"]) / fit["m"]
            ends.append(plot.point(x, y))
        parts["line"] = Line(*ends, color=style.TANGENT_COLOUR, stroke_width=3)
        parts["question"] = text_line(
            rf"\text{{{params.y_name} against {params.x_name}}}", plot.upper, size=34
        )
        parts["correlation"] = text_line(
            rf"\text{{{fit['words']} correlation}}", plot.lower, colour=style.HIGHLIGHT_COLOUR
        )
        if params.estimate_x is not None:
            ex = params.estimate_x
            ey = fit["m"] * ex + fit["c"]
            inside = min(p[0] for p in params.points) <= ex <= max(p[0] for p in params.points)
            parts["estimate"] = VGroup(
                DashedLine(
                    plot.point(ex, plot.y_range[0]),
                    plot.point(ex, ey),
                    color=style.RISE_COLOUR,
                    stroke_width=3,
                ),
                DashedLine(
                    plot.point(ex, ey),
                    plot.point(plot.x_range[0], ey),
                    color=style.RISE_COLOUR,
                    stroke_width=3,
                ),
                Dot(plot.point(ex, ey), color=style.RISE_COLOUR, radius=0.07),
            )
            warning = "" if inside else r"\text{ (outside the data: unreliable)}"
            parts["answer"] = text_line(
                rf"\text{{At {params.x_name} = {format_sf(ex, 6)}, {params.y_name}}} \approx "
                rf"{format_sf(ey)}{warning}",
                plot.lower,
                colour=style.RISE_COLOUR,
            )
        # the mean point's label keeps clear of every line drawn, the estimate's included
        paths = [*parts["points"], parts["line"], *parts.get("estimate", [])]
        mean_label = label(
            rf"(\bar x, \bar y) = ({format_sf(mx)},\ {format_sf(my)})",
            colour=style.HIGHLIGHT_COLOUR,
            size=26,
        )
        parts["mean_point"].add(
            place_label(
                mean_label, plot.point(mx, my), plot.plot_box, plot.obstacles(), paths, wide=True
            )
        )
        return parts

    def stages(self, params: ScatterBestFitParams, level) -> list[Stage]:
        fit = _fit(params)
        steps = [
            stage("plot", "Plot each pair as a cross", 3.0, ["question", "axes", "points"]),
            stage(
                "correlation",
                f"As one goes up, the other {fit['trend']}: {fit['words'].lower()} correlation",
                3.0,
                ["correlation"],
            ),
            stage(
                "mean",
                "Work out the mean point: the mean of the x values and of the y values",
                3.0,
                ["mean_point"],
                emphasise=["mean_point"],
            ),
            stage(
                "line",
                "The line of best fit goes through the mean point, with the crosses "
                "balanced either side",
                3.5,
                ["line"],
            ),
        ]
        if params.estimate_x is not None:
            steps.append(
                stage(
                    "estimate",
                    "Read the estimate from the line",
                    3.0,
                    ["estimate", "answer"],
                    hide=["correlation"],
                )
            )

        def concise(s):
            return [
                combine("plot", s[1].description, 3.5, s[0], s[1]),
                combine("line", s[3].description, 4.0, s[2], s[3]),
                *s[4:],
            ]

        return by_level(level, steps, lambda s: s, concise)


def _fit(params: ScatterBestFitParams) -> dict:
    xs = np.array([p[0] for p in params.points], dtype=float)
    ys = np.array([p[1] for p in params.points], dtype=float)
    mx, my = xs.mean(), ys.mean()
    sxx = ((xs - mx) ** 2).sum()
    syy = ((ys - my) ** 2).sum()
    sxy = ((xs - mx) * (ys - my)).sum()
    m = sxy / sxx
    r = sxy / math.sqrt(sxx * syy) if syy else 0.0
    strength = abs(r)
    if strength < 0.3:
        words, trend = "No", "does not follow a pattern"
    else:
        kind = "positive" if r > 0 else "negative"
        size = "Strong" if strength >= 0.7 else "Weak"
        words = f"{size} {kind}"
        trend = "goes up" if r > 0 else "goes down"
    return {"m": m, "c": my - m * mx, "r": r, "mean": (mx, my), "words": words, "trend": trend}


def _failure(predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=[parameter]
    )
