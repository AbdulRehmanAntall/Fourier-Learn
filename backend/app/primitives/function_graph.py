"""FunctionGraph: the graph of f on labelled axes, drawn from left to right, with marked points
and their coordinates (report Table 5.2, functions and graphs)."""

from typing import Annotated

import numpy as np
import sympy as sp
from manim import Create, Dot, FadeIn, Indicate, MathTex, Succession, Write
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
from app.primitives.symbolic import (
    ExpressionError,
    exact,
    failing_samples,
    format_number,
    latex_number,
    parse_expression,
    sample_points,
    written_latex,
)

X = sp.Symbol("x", real=True)
Coordinate = Annotated[float, Field(ge=-20, le=20)]


class FunctionGraphParams(PrimitiveParams):
    expression: str = Field(min_length=1, max_length=120, description="f(x), e.g. x**2 - 3*x")
    x_min: Coordinate
    x_max: Coordinate
    marked_x: list[Coordinate] = Field(
        default=[], max_length=3, description="x-values of points to mark; y is computed"
    )


class FunctionGraph(Primitive[FunctionGraphParams]):
    primitive_id = "FunctionGraph"
    version = "1"
    topic = "Functions and graphs"
    params_model = FunctionGraphParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("axes", "*"), ("curve", "*")],
    )

    def default_params(self) -> FunctionGraphParams:
        return FunctionGraphParams(expression="x**2", x_min=-3, x_max=3, marked_x=[2])

    def validate(self, params: FunctionGraphParams) -> list[PredicateFailure]:
        try:
            f = parse_expression(params.expression, {"x"})
        except ExpressionError as error:
            return [_failure("parsing", "expression_parses", str(error), "expression")]

        failures = []
        if params.x_min >= params.x_max:
            failures.append(
                _failure("consistency", "interval_ordered", "x_min must be below x_max", "x_min")
            )
            return failures
        outside = [x for x in params.marked_x if not params.x_min <= x <= params.x_max]
        if outside:
            failures.append(
                _failure(
                    "consistency",
                    "marked_points_in_interval",
                    f"marked x-values {outside} are outside the plotted interval",
                    "marked_x",
                )
            )
        if len(set(params.marked_x)) != len(params.marked_x):
            failures.append(
                _failure("consistency", "marked_points_distinct", "repeated x", "marked_x")
            )
        points = sample_points(params.x_min, params.x_max) + [exact(x) for x in params.marked_x]
        bad = failing_samples(f, X, points)
        if bad:
            failures.append(
                _failure(
                    "domain",
                    "real_and_finite",
                    f"f is not real and finite at x = {_list_points(bad)}",
                    "expression",
                )
            )
        return failures

    def computed_values(self, params: FunctionGraphParams) -> dict[str, str]:
        f = parse_expression(params.expression, {"x"})
        values = {}
        for i, x in enumerate(params.marked_x, start=1):
            y = f.subs(X, exact(x))
            values[f"point_{i}_x"] = format_number(exact(x))
            values[f"point_{i}_y"] = format_number(y)
            values[f"point_{i}"] = f"({format_number(exact(x))}, {format_number(y)})"
        return values

    def steps(self, params: FunctionGraphParams, level: Level) -> list[StepSpec]:
        return [spec for spec, _ in self._plan(params, level)]

    def _plan(self, params: FunctionGraphParams, level: Level) -> list[tuple[StepSpec, list[str]]]:
        n = len(params.marked_x)
        points = [name for i in range(1, n + 1) for name in (f"point_{i}", f"point_{i}_label")]
        if level is Level.SUPPORTED:
            plan = [
                (
                    _step("axes", "Draw and label the x and y axes", 2.0, labels=2),
                    ["axes", "x_label", "y_label"],
                ),
                (
                    _step("equation", "Show the equation of the function", 1.5, labels=1),
                    ["equation"],
                ),
                (_step("curve", "Draw the graph from left to right", 3.0), ["curve"]),
            ]
            for i in range(1, n + 1):
                plan.append(
                    (
                        _step(f"point_{i}", f"Mark point {i} with its coordinates", 1.5, 1, 1),
                        [f"point_{i}", f"point_{i}_label"],
                    )
                )
            return plan
        if level is Level.STANDARD:
            plan = [
                (
                    _step(
                        "axes_and_equation", "Draw the axes and show the equation", 2.0, labels=3
                    ),
                    ["axes", "x_label", "y_label", "equation"],
                ),
                (_step("curve", "Draw the graph from left to right", 2.5), ["curve"]),
            ]
            if n:
                plan.append(
                    (_step("points", "Mark the points with their coordinates", 1.5, n), points)
                )
            return plan
        plan = [
            (
                _step("graph", "Draw the axes, the equation and the graph", 2.0, labels=3),
                ["axes", "x_label", "y_label", "equation", "curve"],
            )
        ]
        if n:
            plan.append((_step("points", "Mark the points with their coordinates", 1.0, n), points))
        return plan

    def animate(self, scene, params, level, run_times, carried):
        fades, visible = style.clear_region(carried, self.layout.region)
        parts = self._build(params)
        for i, ((spec, names), run_time) in enumerate(
            zip(self._plan(params, level), run_times, strict=True)
        ):
            animations = [_introduce(name, parts[name], level) for name in names]
            style.play_step(
                scene, (fades if i == 0 else []) + animations, run_time, spec.min_run_time_s
            )
            visible.update({name: parts[name] for name in names})
            yield dict(visible)

    def _build(self, params: FunctionGraphParams) -> dict:
        f = parse_expression(params.expression, {"x"})
        evaluate = sp.lambdify(X, f, "math")

        samples = np.linspace(params.x_min, params.x_max, 81)
        ys = [float(evaluate(x)) for x in samples]
        marked = [(x, float(f.subs(X, exact(x)))) for x in params.marked_x]
        title_box, plot_box = style.graph_boxes(self.layout.region)
        axes, x_label, y_label = style.make_axes(
            style.axis_range([params.x_min, params.x_max]),
            style.axis_range(ys + [y for _, y in marked]),
            plot_box,
        )
        parts = {
            "axes": axes,
            "x_label": x_label,
            "y_label": y_label,
            "equation": style.fit_inside(
                MathTex("y = " + written_latex(params.expression), font_size=style.FONT_SIZE),
                title_box,
            ),
            "curve": axes.plot(
                lambda x: float(evaluate(x)),
                x_range=[params.x_min, params.x_max],
                color=style.CURVE_COLOUR,
            ),
        }
        dots = [Dot(axes.c2p(x, y), color=style.POINT_COLOUR) for x, y in marked]
        obstacles = [x_label, y_label, *dots, *style.axis_numbers(axes)]
        for i, (x, y) in enumerate(marked, start=1):
            position = axes.c2p(x, y)
            parts[f"point_{i}"] = dots[i - 1]
            label = MathTex(
                rf"({latex_number(exact(x))},\ {latex_number(f.subs(X, exact(x)))})",
                font_size=style.LABEL_FONT_SIZE,
                color=style.POINT_COLOUR,
            )
            parts[f"point_{i}_label"] = style.place_clear(
                label, style.around(position, label), plot_box, obstacles, [parts["curve"]]
            )
            obstacles.append(label)
        return parts


def _list_points(points, shown: int = 5) -> str:
    text = ", ".join(format_number(p) for p in points[:shown])
    return text + (f" and {len(points) - shown} more points" if len(points) > shown else "")


def _introduce(name: str, mobject, level: Level):
    if name.startswith("point_") and not name.endswith("_label"):
        appear = FadeIn(mobject, scale=0.5)
        return Succession(appear, Indicate(mobject)) if level is Level.SUPPORTED else appear
    if name in ("axes", "curve"):
        return Create(mobject)
    return Write(mobject)


def _step(name, description, min_run_time, labels=0, highlights=0) -> StepSpec:
    return StepSpec(
        name=name,
        description=description,
        min_run_time_s=min_run_time,
        labels=labels,
        highlights=highlights,
    )


def _failure(kind, predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(kind=kind, predicate=predicate, message=message, parameters=[parameter])
