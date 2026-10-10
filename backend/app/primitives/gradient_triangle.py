"""GradientTriangle: the rise and run between two points drawn as a right-angled triangle, with
the gradient computed as their ratio (report Table 5.2, coordinate geometry)."""

from typing import Annotated

import numpy as np
from manim import Create, Dot, FadeIn, Indicate, Line, MathTex, Succession, Write
from pydantic import Field

from app.contracts import (
    LayoutContract,
    Level,
    PredicateFailure,
    Primitive,
    PrimitiveParams,
    StepSpec,
)
from app.primitives import style
from app.primitives.symbolic import exact, format_number, latex_number

Coordinate = Annotated[float, Field(ge=-20, le=20)]


class GradientTriangleParams(PrimitiveParams):
    point_a: tuple[Coordinate, Coordinate] = Field(description="First point (x, y)")
    point_b: tuple[Coordinate, Coordinate] = Field(description="Second point (x, y)")


class GradientTriangle(Primitive[GradientTriangleParams]):
    primitive_id = "GradientTriangle"
    version = "1"
    topic = "Coordinate geometry"
    params_model = GradientTriangleParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("axes", "*"),
            ("line", "*"),
            ("run", "rise"),
            ("run", "point_*"),
            ("rise", "point_*"),
        ],
    )

    def default_params(self) -> GradientTriangleParams:
        return GradientTriangleParams(point_a=(1, 2), point_b=(4, 8))

    def validate(self, params: GradientTriangleParams) -> list[PredicateFailure]:
        (xa, ya), (xb, yb) = params.point_a, params.point_b
        if (xa, ya) == (xb, yb):
            return [_failure("distinct_points", "the two points are the same point")]
        failures = []
        if xa == xb:
            failures.append(_failure("not_vertical", "a vertical line has no run, so no gradient"))
        if ya == yb:
            failures.append(_failure("not_horizontal", "a horizontal line has no rise to draw"))
        return failures

    def computed_values(self, params: GradientTriangleParams) -> dict[str, str]:
        rise, run, gradient = _rise_run_gradient(params)
        return {
            "rise": format_number(rise),
            "run": format_number(run),
            "gradient": format_number(gradient),
            "point_a": _point_text(params.point_a),
            "point_b": _point_text(params.point_b),
        }

    def steps(self, params: GradientTriangleParams, level: Level) -> list[StepSpec]:
        return [spec for spec, _ in _plan(level)]

    def animate(self, scene, params, level, run_times, carried):
        fades, visible = style.clear_region(carried, self.layout.region)
        parts = self._build(params, level)
        for i, ((spec, names), run_time) in enumerate(zip(_plan(level), run_times, strict=True)):
            animations = [_introduce(name, parts[name], level) for name in names]
            style.play_step(
                scene, (fades if i == 0 else []) + animations, run_time, spec.min_run_time_s
            )
            visible.update({name: parts[name] for name in names})
            yield dict(visible)

    def _build(self, params: GradientTriangleParams, level: Level) -> dict:
        (xa, ya), (xb, yb) = params.point_a, params.point_b
        rise, run, gradient = _rise_run_gradient(params)
        title_box, plot_box = style.graph_boxes(self.layout.region)
        x_range = style.axis_range([xa, xb])
        y_range = style.axis_range([ya, yb])
        axes, x_label, y_label = style.make_axes(x_range, y_range, plot_box)

        a, b, corner = axes.c2p(xa, ya), axes.c2p(xb, yb), axes.c2p(xb, ya)
        slope = (yb - ya) / (xb - xa)
        x_lo, x_hi = _visible_x(slope, xa, ya, x_range, y_range)

        run_line = Line(a, corner, color=style.RUN_COLOUR, stroke_width=6)
        rise_line = Line(corner, b, color=style.RISE_COLOUR, stroke_width=6)
        run_label = MathTex(
            rf"\text{{run}} = {latex_number(run)}",
            font_size=style.LABEL_FONT_SIZE,
            color=style.RUN_COLOUR,
        )
        rise_label = MathTex(
            rf"\text{{rise}} = {latex_number(rise)}",
            font_size=style.LABEL_FONT_SIZE,
            color=style.RISE_COLOUR,
        )
        # Point labels first, then the run and rise labels, each clear of what is placed and
        # of the line. The run and rise labels try the middle of their segment first, then
        # nearer each end, outside the triangle before inside.
        line = Line(
            axes.c2p(x_lo, ya + slope * (x_lo - xa)),
            axes.c2p(x_hi, ya + slope * (x_hi - xa)),
            color=style.CURVE_COLOUR,
        )
        dot_a, dot_b = Dot(a, color=style.POINT_COLOUR), Dot(b, color=style.POINT_COLOUR)
        obstacles = [x_label, y_label, dot_a, dot_b, run_line, rise_line]
        obstacles += style.axis_numbers(axes)
        point_labels = []
        for point, anchor in ((params.point_a, a), (params.point_b, b)):
            label = _point_label(point)
            style.place_clear(label, style.around(anchor, label), plot_box, obstacles, [line])
            obstacles.append(label)
            point_labels.append(label)
        outside = -np.sign(yb - ya)
        offset = np.array([0, run_label.height / 2 + 0.15, 0])
        style.place_clear(
            run_label,
            [
                run_line.point_from_proportion(t) + side * offset
                for side in (outside, -outside)
                for t in (0.5, 0.3, 0.7, 0.15, 0.85)
            ],
            plot_box,
            obstacles,
            [line],
        )
        obstacles.append(run_label)
        outside = np.sign(xb - xa)
        offset = np.array([rise_label.width / 2 + 0.15, 0, 0])
        style.place_clear(
            rise_label,
            [
                rise_line.point_from_proportion(t) + side * offset
                for side in (outside, -outside)
                for t in (0.5, 0.3, 0.7, 0.15, 0.85)
            ],
            plot_box,
            obstacles,
            [line],
        )

        fraction = rf"\frac{{{latex_number(rise)}}}{{{latex_number(run)}}}"
        if level is Level.CONCISE:
            formula = rf"\text{{gradient}} = {fraction} = {latex_number(gradient)}"
        else:
            formula = (
                rf"\text{{gradient}} = \frac{{\text{{rise}}}}{{\text{{run}}}}"
                rf" = {fraction} = {latex_number(gradient)}"
            )
        return {
            "axes": axes,
            "x_label": x_label,
            "y_label": y_label,
            "point_a": dot_a,
            "point_b": dot_b,
            "point_a_label": point_labels[0],
            "point_b_label": point_labels[1],
            "line": line,
            "run": run_line,
            "rise": rise_line,
            "run_label": run_label,
            "rise_label": rise_label,
            "formula": style.fit_inside(MathTex(formula, font_size=style.FONT_SIZE), title_box),
        }


def _plan(level: Level) -> list[tuple[StepSpec, list[str]]]:
    if level is Level.SUPPORTED:
        return [
            (
                _step("axes", "Draw and label the axes", 2.0, labels=2),
                ["axes", "x_label", "y_label"],
            ),
            (_step("point_a", "Mark the first point", 1.5, 1, 1), ["point_a", "point_a_label"]),
            (_step("point_b", "Mark the second point", 1.5, 1, 1), ["point_b", "point_b_label"]),
            (_step("line", "Draw the straight line through both points", 2.0), ["line"]),
            (
                _step("run", "Draw the run: the horizontal distance", 2.0, 1, 1),
                ["run", "run_label"],
            ),
            (
                _step("rise", "Draw the rise: the vertical distance", 2.0, 1, 1),
                ["rise", "rise_label"],
            ),
            (_step("gradient", "Divide the rise by the run", 3.0, 1, 1), ["formula"]),
        ]
    points = ["point_a", "point_a_label", "point_b", "point_b_label"]
    if level is Level.STANDARD:
        return [
            (
                _step("axes_and_points", "Draw the axes and mark both points", 2.0, 4),
                ["axes", "x_label", "y_label", *points],
            ),
            (_step("line", "Draw the straight line through both points", 1.5), ["line"]),
            (
                _step("rise_and_run", "Draw the run and the rise", 2.5, 2),
                ["run", "run_label", "rise", "rise_label"],
            ),
            (_step("gradient", "Divide the rise by the run", 2.5, 1), ["formula"]),
        ]
    return [
        (
            _step("line_through_points", "Draw the line through the two points", 2.0, 4),
            ["axes", "x_label", "y_label", *points, "line"],
        ),
        (
            _step("triangle_and_gradient", "Draw rise and run and give the gradient", 2.5, 3),
            ["run", "run_label", "rise", "rise_label", "formula"],
        ),
    ]


def _introduce(name: str, mobject, level: Level):
    highlight = level is Level.SUPPORTED and name in (
        "point_a",
        "point_b",
        "run",
        "rise",
        "formula",
    )
    if name in ("point_a", "point_b"):
        animation = FadeIn(mobject, scale=0.5)
    elif name in ("axes", "line", "run", "rise"):
        animation = Create(mobject)
    else:
        animation = Write(mobject)
    return Succession(animation, Indicate(mobject)) if highlight else animation


def _rise_run_gradient(params: GradientTriangleParams):
    (xa, ya), (xb, yb) = params.point_a, params.point_b
    rise, run = exact(yb) - exact(ya), exact(xb) - exact(xa)
    return rise, run, rise / run


def _visible_x(slope, xa, ya, x_range, y_range) -> tuple[float, float]:
    """The part of the axes' x-range where the line stays inside the y-range."""
    x_lo, x_hi = x_range[0], x_range[1]
    ends = sorted(xa + (y - ya) / slope for y in (y_range[0], y_range[1]))
    return max(x_lo, ends[0]), min(x_hi, ends[1])


def _point_text(point) -> str:
    return f"({format_number(exact(point[0]))}, {format_number(exact(point[1]))})"


def _point_label(point) -> MathTex:
    return MathTex(
        rf"({latex_number(exact(point[0]))},\ {latex_number(exact(point[1]))})",
        font_size=style.LABEL_FONT_SIZE,
        color=style.POINT_COLOUR,
    )


def _step(name, description, min_run_time, labels=0, highlights=0) -> StepSpec:
    return StepSpec(
        name=name,
        description=description,
        min_run_time_s=min_run_time,
        labels=labels,
        highlights=highlights,
    )


def _failure(predicate, message) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency",
        predicate=predicate,
        message=message,
        parameters=["point_a", "point_b"],
    )
