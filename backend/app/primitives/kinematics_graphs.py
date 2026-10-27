"""KinematicsGraphs: displacement, velocity and acceleration against time, stacked on one
time-axis, beside a particle moving along a line (AM 14.14, 14.15; PRIMITIVES.md #58).

Differentiating moves down the stack (v = ds/dt, a = dv/dt); integrating moves up. The particle
is at rest where v = 0, and those instants are marked through all three graphs. Give s(t), or
v(t) with the starting displacement. Every value is computed by SymPy.
"""

from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import DashedLine, Dot, Line, NumberLine, ValueTracker, VGroup, always_redraw
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams, Region
from app.primitives import style
from app.primitives.analysis import samples, zeros
from app.primitives.plotting import axis_range, curve, label, make_plot, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    exact,
    format_value,
    parse_expression,
    tidy_latex,
    written_latex,
)

T = sp.Symbol("t", real=True)
TOP = 0.8  # the plots fill the region below the title band
ROWS = [
    Region(x_min=0.0, x_max=0.5, y_min=TOP * 2 / 3, y_max=TOP),
    Region(x_min=0.0, x_max=0.5, y_min=TOP / 3, y_max=TOP * 2 / 3),
    Region(x_min=0.0, x_max=0.5, y_min=0.0, y_max=TOP / 3),
]
LINE_COLUMN = Region(x_min=0.5, x_max=0.62, y_min=0.0, y_max=TOP)


class KinematicsGraphsParams(PrimitiveParams):
    given: Literal["displacement", "velocity"] = "displacement"
    expression: str = Field(min_length=1, max_length=120, description="s(t) or v(t) in terms of t")
    s0: Annotated[float, Field(ge=-100, le=100)] = Field(
        default=0, description="Displacement at t = 0, when v(t) is given"
    )
    t_max: Annotated[float, Field(gt=0, le=20)] = Field(description="The end of the motion, in s")


class KinematicsGraphs(StagedPrimitive[KinematicsGraphsParams]):
    primitive_id = "KinematicsGraphs"
    version = "1"
    topic = "Travel graphs and kinematics"
    params_model = KinematicsGraphsParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("axes_*", "*"),
            ("curve_*", "*"),
            ("rest_lines", "*"),
            ("rest_dots", "*"),
            ("track", "*"),
        ],
    )

    def default_params(self) -> KinematicsGraphsParams:
        return KinematicsGraphsParams(expression="t**3 - 6*t**2 + 9*t", t_max=4)

    def validate(self, params: KinematicsGraphsParams) -> list[PredicateFailure]:
        try:
            parse_expression(params.expression, {"t"})
        except ExpressionError as error:
            return [_failure("parsing", "expression_parses", str(error), "expression")]
        m = _Motion(params)
        for name, expr in (("s", m.s), ("v", m.v), ("a", m.a)):
            _, ys = samples(expr.subs(T, sp.Symbol("x", real=True)), 0, params.t_max, 201)
            if not np.isfinite(ys).all():
                message = f"{name}(t) is not real and finite for 0 <= t <= t_max"
                return [_failure("domain", "real_and_finite", message, "expression", "t_max")]
        if len(m.rest) > 4:
            message = "the particle stops more than 4 times; shorten t_max"
            return [_failure("consistency", "few_stops", message, "t_max")]
        return []

    def computed_values(self, params: KinematicsGraphsParams) -> dict[str, str]:
        m = _Motion(params)
        values = {"displacement": str(m.s), "velocity": str(m.v), "acceleration": str(m.a)}
        for i, t in enumerate(m.rest, start=1):
            values[f"rest_{i}_time"] = format_value(t)
            values[f"rest_{i}_displacement"] = format_value(m.s.subs(T, t))
        values["final_displacement"] = format_value(m.s.subs(T, exact(params.t_max)))
        return values

    def build(self, params: KinematicsGraphsParams, level):
        m = _Motion(params)
        t_end = params.t_max
        title, _ = style.graph_boxes(style.GRAPH_REGION)
        upper, lower = style.title_lines(title)
        times = np.linspace(0, t_end, 121)
        plots = []
        for region, expr, name in zip(ROWS, (m.s, m.v, m.a), ("s", "v", "a"), strict=True):
            numeric = sp.lambdify(T, expr, "math")
            plots.append(
                make_plot(
                    region,
                    [0, t_end],
                    [numeric(t) for t in times],
                    x_label="t",
                    y_label=name,
                    title=False,
                    y_ticks=2,
                    x_from_zero=True,
                    left_margin=0.6,
                )
            )
        s_num, v_num, a_num = (sp.lambdify(T, e, "math") for e in (m.s, m.v, m.a))
        parts = {
            "given": text_line(m.given_latex(), upper),
            "derived": text_line(m.derived_latex(), lower, size=34),
        }
        for key, plot, numeric, colour in (
            ("s", plots[0], s_num, style.CURVE_COLOUR),
            ("v", plots[1], v_num, style.RISE_COLOUR),
            ("a", plots[2], a_num, style.RUN_COLOUR),
        ):
            parts[f"axes_{key}"] = VGroup(plot.axes, plot.x_label, plot.y_label)
            parts[f"curve_{key}"] = curve(plot, numeric, 0, t_end, colour=colour)

        # The particle's line: displacement upwards, beside the graphs.
        column = style.region_box(LINE_COLUMN).shrink(style.PADDING)
        s_values = [s_num(t) for t in times]
        s_range = axis_range(s_values, 4)
        track = NumberLine(
            x_range=list(s_range),
            length=column.height - 0.6,
            rotation=np.pi / 2,
            include_numbers=True,
            font_size=style.AXIS_NUMBER_FONT_SIZE,
            label_direction=[-1, 0, 0],
            numbers_to_exclude=[],
        ).move_to(column.center + [0.15, -0.1, 0])
        track_label = label("s", size=style.LABEL_FONT_SIZE).next_to(track, [0, 1, 0], buff=0.1)
        parts["track"] = VGroup(track, track_label)

        rest_lines, rest_dots = VGroup(), VGroup()
        for t in m.rest:
            t = float(t)
            top = plots[0].point(t, plots[0].y_range[1])
            bottom = plots[2].point(t, plots[2].y_range[0])
            rest_lines.add(DashedLine(top, bottom, color=style.POINT_COLOUR, stroke_width=2))
            rest_dots.add(Dot(plots[0].point(t, s_num(t)), color=style.POINT_COLOUR))
            rest_dots.add(Dot(plots[1].point(t, 0), color=style.POINT_COLOUR))
        parts["rest_lines"] = rest_lines
        parts["rest_dots"] = rest_dots
        rest_text = (
            r"v = 0 \text{ at } t = " + r",\ ".join(format_value(t) for t in m.rest)
            if m.rest
            else r"v \neq 0\text{: the particle never stops}"
        )
        parts["rest_text"] = text_line(rest_text, lower)
        self._motion = (plots, (s_num, v_num, a_num), track, t_end)
        return parts

    def move(self, scene, parts, level, run_time, min_run_time):
        """The particle moves along its line while a cursor moves through the three graphs."""
        plots, (s_num, v_num, a_num), track, t_end = self._motion
        tracker = ValueTracker(0)

        def picture():
            t = tracker.get_value()
            group = VGroup(Dot(track.n2p(s_num(t)), color=style.HIGHLIGHT_COLOUR, radius=0.11))
            for plot, numeric in zip(plots, (s_num, v_num, a_num), strict=True):
                group.add(
                    Line(
                        plot.point(t, plot.y_range[0]),
                        plot.point(t, plot.y_range[1]),
                        color=style.HIGHLIGHT_COLOUR,
                        stroke_width=2,
                    )
                )
                group.add(Dot(plot.point(t, numeric(t)), color=style.HIGHLIGHT_COLOUR, radius=0.06))
            return group

        moving = always_redraw(picture)
        scene.add(moving)
        hold = min(0.15, 0.2 * run_time)
        animation_time = min(max(min_run_time, 0.6 * run_time), run_time - hold)
        scene.play(tracker.animate.set_value(t_end), run_time=animation_time)
        scene.remove(moving)
        scene.wait(run_time - animation_time)

    def stages(self, params: KinematicsGraphsParams, level) -> list[Stage]:
        steps = [
            stage("s", "The displacement-time graph", 2.5, ["given", "axes_s", "curve_s"]),
            stage(
                "v", "Differentiate s to get the velocity", 2.5, ["derived", "axes_v", "curve_v"]
            ),
            stage("a", "Differentiate v to get the acceleration", 2.5, ["axes_a", "curve_a"]),
            stage(
                "rest",
                "The particle is at rest where v is zero",
                3.0,
                ["rest_lines", "rest_dots"],
                morph=[("derived", "rest_text")],
                emphasise=["rest_dots"],
            ),
            stage(
                "track", "Watch the particle move along its line as time goes on", 1.5, ["track"]
            ),
            stage("move", "It slows, stops and turns where v is zero", 5.0, motion="move"),
        ]
        if params.given == "velocity":
            steps[0] = stage(
                "s",
                "Integrate v, starting from s at t = 0, for the displacement",
                2.5,
                ["given", "axes_s", "curve_s"],
            )

        def standard(s):
            return [
                s[0],
                combine(
                    "derivatives", "Differentiate for velocity and acceleration", 3.0, s[1], s[2]
                ),
                combine("rest", s[3].description, 3.0, s[3], s[4]),
                s[5],
            ]

        def concise(s):
            return [
                combine("graphs", "Displacement, velocity and acceleration", 3.5, *s[:3]),
                combine("rest", "Where the particle stops", 3.0, s[3], s[4]),
                s[5],
            ]

        return by_level(level, steps, standard, concise)


class _Motion:
    def __init__(self, params: KinematicsGraphsParams):
        expr = sp.nsimplify(parse_expression(params.expression, {"t"}), rational=True)
        self.given = params.given
        self.written = params.expression
        if params.given == "displacement":
            self.s = expr
            self.v = sp.diff(expr, T)
        else:
            self.v = expr
            self.s = sp.integrate(expr, (T, 0, T)) + exact(params.s0)
        self.s = sp.expand(self.s)
        self.a = sp.simplify(sp.diff(self.v, T))
        x = sp.Symbol("x", real=True)
        found = zeros(self.v.subs(T, x), 0, params.t_max, [])
        self.rest = [t for t in found if 0 < float(t) <= params.t_max]

    def given_latex(self) -> str:
        variable = "s" if self.given == "displacement" else "v"
        return f"{variable} = {written_latex(self.written)}"

    def derived_latex(self) -> str:
        if self.given == "displacement":
            return (
                rf"v = \tfrac{{ds}}{{dt}} = {tidy_latex(self.v)},\quad "
                rf"a = \tfrac{{dv}}{{dt}} = {tidy_latex(self.a)}"
            )
        return rf"s = {tidy_latex(self.s)},\quad a = \tfrac{{dv}}{{dt}} = {tidy_latex(self.a)}"


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
