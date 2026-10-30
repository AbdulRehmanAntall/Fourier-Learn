"""LogLinearisation: data following y = kxⁿ or y = k·aˣ turned into a straight line by taking
logarithms, and the constants read from its gradient and intercept (9709 2.2, 3.2).

Taking ln of y = kxⁿ gives ln y = ln k + n ln x: a straight line in ln x and ln y with gradient n
and intercept ln k. Taking ln of y = k·aˣ gives ln y = ln k + x ln a: a straight line in x and
ln y with gradient ln a. The curve of the data becomes the line on the transformed axes; the
line is the least-squares line through the transformed points (through both, for two points),
and k = e^(intercept). Values are to 3 significant figures.
"""

import math
from typing import Annotated, Literal

import numpy as np
from manim import Dot, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams, Region
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import curve, make_plot, stack_lines
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf

Positive = Annotated[float, Field(gt=0, le=100_000)]
TOP = Region(x_min=0.0, x_max=0.62, y_min=0.5, y_max=1.0)
BOTTOM = Region(x_min=0.0, x_max=0.62, y_min=0.0, y_max=0.5)


class LogLinearisationParams(PrimitiveParams):
    model: Literal["power", "exponential"] = Field(
        description="power: y = k x^n (plot ln y against ln x). exponential: y = k a^x "
        "(plot ln y against x)"
    )
    points: list[tuple[Annotated[float, Field(ge=-50, le=100_000)], Positive]] = Field(
        min_length=2, max_length=8, description="The data (x, y); y > 0, and x > 0 for power"
    )


class LogLinearisation(StagedPrimitive[LogLinearisationParams]):
    primitive_id = "LogLinearisation"
    version = "1"
    topic = "Logarithms and exponentials"
    params_model = LogLinearisationParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[
            ("data_axes", "*"),
            ("log_axes", "*"),
            ("data_curve", "*"),
            ("data_points", "*"),
            ("log_points", "*"),
            ("log_line", "*"),
        ],
    )

    def default_params(self) -> LogLinearisationParams:
        return LogLinearisationParams(
            model="power", points=[(1, 3), (2, 12.1), (3, 27), (4, 47.9), (5, 75.2)]
        )

    def validate(self, params: LogLinearisationParams) -> list[PredicateFailure]:
        xs = [x for x, _ in params.points]
        if params.model == "power" and min(xs) <= 0:
            message = "for y = kx^n every x must be positive (ln x is needed)"
            return [_failure("positive_x", message, "points")]
        if len(set(xs)) != len(xs):
            return [_failure("distinct_x", "each x must be different", "points")]
        if xs != sorted(xs):
            return [_failure("ordered_x", "give the points in order of x", "points")]
        return []

    def computed_values(self, params: LogLinearisationParams) -> dict[str, str]:
        fit = _Fit(params)
        values = {"gradient": format_sf(fit.gradient), "intercept": format_sf(fit.intercept)}
        values["k"] = format_sf(fit.k)
        values["n" if params.model == "power" else "a"] = format_sf(fit.second)
        return values

    def build(self, params: LogLinearisationParams, level):
        fit = _Fit(params)
        xs = [x for x, _ in params.points]
        ys = [y for _, y in params.points]
        top = make_plot(TOP, xs, ys, title=False, y_ticks=4, origin=params.model == "exponential")
        u, v = fit.u, fit.v
        bottom = make_plot(
            BOTTOM,
            u,
            v,
            title=False,
            y_ticks=4,
            x_label=r"\ln x" if params.model == "power" else "x",
            y_label=r"\ln y",
        )
        model_curve = curve(
            top,
            fit.model,
            max(min(xs), 1e-3) if params.model == "power" else min(xs),
            max(xs),
            colour=style.CURVE_COLOUR,
        )
        u_lo, u_hi = bottom.x_range[0], bottom.x_range[1]
        parts = {
            "data_axes": VGroup(top.axes, top.x_label, top.y_label),
            "data_points": VGroup(
                *(Dot(top.point(x, y), color=style.POINT_COLOUR) for x, y in params.points)
            ),
            "data_curve": model_curve,
            "log_axes": VGroup(bottom.axes, bottom.x_label, bottom.y_label),
            "log_points": VGroup(
                *(
                    Dot(bottom.point(a, b), color=style.POINT_COLOUR)
                    for a, b in zip(u, v, strict=True)
                )
            ),
            "log_line": style.line_in_axes(
                bottom.axes,
                (0, fit.intercept),
                fit.gradient,
                (u_lo, u_hi),
                bottom.y_range,
                color=style.TANGENT_COLOUR,
                stroke_width=3,
            ),
        }
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        rows = fit.rows()
        texts = stack_lines([t for t, _ in rows], box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: LogLinearisationParams, level) -> list[Stage]:
        power = params.model == "power"
        steps = [
            stage(
                "data",
                "The data lie on a curve, so its constants are hard to read",
                3.0,
                ["data_axes", "data_points", "data_curve", "row_1"],
            ),
            stage(
                "logs",
                "Take natural logs of both sides: the equation of a straight line",
                3.5,
                ["row_2", "row_3"],
                emphasise=["row_3"],
            ),
            stage(
                "plot",
                "Plot ln y against " + ("ln x" if power else "x") + ": the points lie on a line",
                3.5,
                ["log_axes", "log_points", "log_line", "row_4"],
            ),
            stage(
                "gradient",
                "The gradient is " + ("n" if power else "ln a") + ", and the intercept is ln k",
                3.5,
                ["row_5", "row_6"],
            ),
            stage(
                "constants",
                "Undo the logs to find the constants",
                3.0,
                ["row_7", "row_8"],
                emphasise=["row_8"],
            ),
        ]

        def standard(s):
            return [s[0], combine("logs", s[1].description, 4.0, s[1], s[2]), s[3], s[4]]

        def concise(s):
            return [
                s[0],
                combine("logs", s[1].description, 4.0, s[1], s[2]),
                combine(
                    "constants",
                    "Read the gradient and intercept, and undo the logs",
                    4.0,
                    s[3],
                    s[4],
                ),
            ]

        return by_level(level, steps, standard, concise)


class _Fit:
    def __init__(self, params: LogLinearisationParams):
        self.params = params
        power = params.model == "power"
        self.u = [math.log(x) if power else x for x, _ in params.points]
        self.v = [math.log(y) for _, y in params.points]
        if len(self.u) == 2:
            self.gradient = (self.v[1] - self.v[0]) / (self.u[1] - self.u[0])
            self.intercept = self.v[0] - self.gradient * self.u[0]
        else:
            self.gradient, self.intercept = (float(c) for c in np.polyfit(self.u, self.v, 1))
        self.k = math.exp(self.intercept)
        self.second = self.gradient if power else math.exp(self.gradient)

    def model(self, x: float) -> float:
        if self.params.model == "power":
            return self.k * x**self.gradient
        return self.k * self.second**x

    def rows(self) -> list[tuple[str, object]]:
        power = self.params.model == "power"
        g, c = format_sf(self.gradient), format_sf(self.intercept)
        through = "Through the two points" if len(self.u) == 2 else "The line of best fit"
        if power:
            rows = [
                (r"y = kx^n", None),
                (r"\ln y = \ln k + \ln x^n", None),
                (r"\ln y = n\ln x + \ln k", style.TANGENT_COLOUR),
                (rf"\text{{{through}}}", None),
                (rf"n = \text{{gradient}} = {g}", None),
                (rf"\ln k = \text{{intercept}} = {c}", None),
                (rf"k = e^{{{c}}} = {format_sf(self.k)}", None),
                (rf"y = {format_sf(self.k)}x^{{{g}}}", style.HIGHLIGHT_COLOUR),
            ]
        else:
            rows = [
                (r"y = k\,a^x", None),
                (r"\ln y = \ln k + \ln a^x", None),
                (r"\ln y = x\ln a + \ln k", style.TANGENT_COLOUR),
                (rf"\text{{{through}}}", None),
                (rf"\ln a = \text{{gradient}} = {g},\ a = {format_sf(self.second)}", None),
                (rf"\ln k = \text{{intercept}} = {c}", None),
                (rf"k = e^{{{c}}} = {format_sf(self.k)}", None),
                (
                    rf"y = {format_sf(self.k)}\times {format_sf(self.second)}^x",
                    style.HIGHLIGHT_COLOUR,
                ),
            ]
        return rows


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
