"""TangentSlide: a tangent line moving along a curve with a read-out of its gradient at each
position (report Table 5.2, introductory calculus).

The tangent first touches the curve at x_start, then slides to x_end while the read-out follows
its gradient. At rest the gradient is shown exactly, as SymPy computes it; while the tangent
moves, the read-out shows it to two decimal places.
"""

import sympy as sp
from manim import (
    RIGHT,
    Create,
    DecimalNumber,
    Dot,
    FadeIn,
    Indicate,
    MathTex,
    ReplacementTransform,
    Succession,
    ValueTracker,
    VGroup,
    Write,
)
from pydantic import Field

from app.contracts import LayoutContract, Level, PredicateFailure, Primitive, StepSpec
from app.primitives import style
from app.primitives.curves import (
    Coordinate,
    CurveParams,
    X,
    check_curve,
    draw_curve,
    failure,
    inline,
    label_paths,
    parse_function,
    point_latex,
    point_text,
    smooth_failures,
)
from app.primitives.symbolic import exact, format_number, latex_number

SLIDE = "slide"
"""The plan's marker for the step in which the tangent moves."""


class TangentSlideParams(CurveParams):
    x_start: Coordinate = Field(description="x where the tangent first touches the curve")
    x_end: Coordinate = Field(description="x the point of tangency slides to")


class TangentSlide(Primitive[TangentSlideParams]):
    primitive_id = "TangentSlide"
    version = "1"
    topic = "Introductory calculus"
    params_model = TangentSlideParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("axes", "*"), ("curve", "*"), ("tangent", "*"), ("point", "point_*")],
    )

    def default_params(self) -> TangentSlideParams:
        return TangentSlideParams(expression="x**2", x_min=-3, x_max=3, x_start=-2, x_end=2)

    def validate(self, params: TangentSlideParams) -> list[PredicateFailure]:
        f, failures = check_curve(params)
        if failures:
            return failures
        outside = [
            name
            for name in ("x_start", "x_end")
            if not params.x_min <= getattr(params, name) <= params.x_max
        ]
        if outside:
            message = f"{' and '.join(outside)} must lie inside the plotted interval"
            return [failure("consistency", "slide_in_interval", message, *outside)]
        if params.x_start == params.x_end:
            message = "x_start and x_end are the same, so the tangent would not move"
            return [failure("consistency", "tangent_moves", message, "x_start", "x_end")]
        lo, hi = sorted((params.x_start, params.x_end))
        return smooth_failures(f, lo, hi, "x_start", "x_end")

    def computed_values(self, params: TangentSlideParams) -> dict[str, str]:
        f = parse_function(params.expression)
        derivative = sp.diff(f, X)
        values = {}
        for key, x in (("start", params.x_start), ("end", params.x_end)):
            x = exact(x)
            y, gradient = f.subs(X, x), sp.simplify(derivative.subs(X, x))
            values[f"{key}_x"] = format_number(x)
            values[f"{key}_y"] = format_number(y)
            values[f"{key}_gradient"] = format_number(gradient)
            values[f"point_{key}"] = point_text(x, y)
        return values

    def steps(self, params: TangentSlideParams, level: Level) -> list[StepSpec]:
        return [spec for spec, _ in _plan(level)]

    def animate(self, scene, params, level, run_times, carried):
        fades, visible = style.clear_region(carried, self.layout.region)
        parts, motion = self._build(params, level)
        for i, ((spec, names), run_time) in enumerate(zip(_plan(level), run_times, strict=True)):
            if SLIDE in names:
                _slide(scene, parts, motion, level, run_time, spec.min_run_time_s)
                visible["readout"] = parts["readout_end"]
                visible["point_end_label"] = parts["point_end_label"]
            else:
                animations = [_introduce(name, parts[name], level) for name in names]
                style.play_step(
                    scene, (fades if i == 0 else []) + animations, run_time, spec.min_run_time_s
                )
                visible.update({name: parts[name] for name in names})
            yield dict(visible)

    def _build(self, params: TangentSlideParams, level: Level) -> tuple[dict, dict]:
        f = parse_function(params.expression)
        derivative = sp.diff(f, X)
        y_of = sp.lambdify(X, f, "math")
        slope_of = sp.lambdify(X, derivative, "math")
        figure = draw_curve(params, f, self.layout.region)
        axes = figure.axes

        def tangent_at(x: float):
            return style.line_in_axes(
                axes,
                (x, float(y_of(x))),
                float(slope_of(x)),
                figure.x_range,
                figure.y_range,
                color=style.TANGENT_COLOUR,
                stroke_width=5,
            )

        def point_at(x: float):
            return axes.c2p(x, float(y_of(x)))

        start, end = exact(params.x_start), exact(params.x_end)
        word = r"\text{gradient}" if level is Level.CONCISE else r"\text{gradient of tangent}"

        def readout(x):
            value = latex_number(sp.simplify(derivative.subs(X, x)))
            text = MathTex(rf"{word} = {inline(value)}", font_size=style.FONT_SIZE)
            return style.fit_inside(text, figure.lower_line)

        start_dot = Dot(point_at(params.x_start), color=style.POINT_COLOUR)
        tangent = tangent_at(params.x_start)
        end_tangent = tangent_at(params.x_end)
        obstacles = [figure.x_label, figure.y_label, start_dot, *style.axis_numbers(axes)]
        paths = label_paths(figure, tangent, end_tangent)
        labels = {}
        for key, x in (("start", start), ("end", end)):
            label = MathTex(
                point_latex(x, f.subs(X, x)),
                font_size=style.LABEL_FONT_SIZE,
                color=style.POINT_COLOUR,
            )
            anchor = point_at(float(x))
            style.place_clear(label, style.around(anchor, label), figure.plot_box, obstacles, paths)
            obstacles.append(label)
            labels[key] = label

        parts = {
            "axes": axes,
            "x_label": figure.x_label,
            "y_label": figure.y_label,
            "equation": figure.equation,
            "curve": figure.curve,
            "point_start": start_dot,
            "point_start_label": labels["start"],
            "point": Dot(point_at(params.x_start), color=style.POINT_COLOUR),
            "tangent": tangent,
            "readout": readout(start),
            "readout_end": readout(end),
            "point_end_label": labels["end"],
        }
        motion = {
            "x_start": params.x_start,
            "x_end": params.x_end,
            "tangent_at": tangent_at,
            "point_at": point_at,
            "slope_of": slope_of,
            "word": word,
            "box": figure.lower_line,
        }
        return parts, motion


def _slide(scene, parts, motion, level, run_time, min_run_time) -> None:
    """Move the tangent from x_start to x_end with a live read-out, then state the gradient at
    x_end exactly. Takes exactly `run_time`."""
    tracker = ValueTracker(motion["x_start"])
    tangent, point = parts["tangent"], parts["point"]
    tangent.add_updater(lambda m: m.become(motion["tangent_at"](tracker.get_value())))
    point.add_updater(lambda m: m.move_to(motion["point_at"](tracker.get_value())))

    # The read-out, live: the same words, with the number following the tangent.
    words = MathTex(rf"{motion['word']} =", font_size=style.FONT_SIZE)
    number = DecimalNumber(
        motion["slope_of"](motion["x_start"]), num_decimal_places=2, font_size=style.FONT_SIZE
    )
    live = VGroup(words, number).arrange(RIGHT, buff=0.2)
    style.fit_inside(live, motion["box"])
    number.add_updater(
        lambda m: m.set_value(motion["slope_of"](tracker.get_value())).next_to(
            words, RIGHT, buff=0.2
        )
    )
    scene.remove(parts["readout"])
    scene.add(live)

    settle = min(0.8, 0.25 * run_time)
    moving = min(run_time - settle, max(min_run_time - settle, 0.6 * run_time))
    scene.play(tracker.animate.set_value(motion["x_end"]), run_time=moving)
    for mobject in (tangent, point, number):
        mobject.clear_updaters()

    end_label = parts["point_end_label"]
    appear = Write(end_label)
    if level is Level.SUPPORTED:
        appear = Succession(appear, Indicate(end_label))
    scene.play(ReplacementTransform(live, parts["readout_end"]), appear, run_time=settle)
    if run_time - moving - settle > 1e-6:
        scene.wait(run_time - moving - settle)


def _plan(level: Level) -> list[tuple[StepSpec, list[str]]]:
    graph = ["axes", "x_label", "y_label", "equation", "curve"]
    touch = ["point_start", "point_start_label", "tangent", "point", "readout"]
    slide = (
        _step(
            SLIDE,
            "Slide the tangent along the curve and watch its gradient change",
            {Level.SUPPORTED: 4.0, Level.STANDARD: 3.5, Level.CONCISE: 2.5}[level],
            labels=1,
            highlights=1 if level is Level.SUPPORTED else 0,
        ),
        [SLIDE, "point_end_label"],
    )
    if level is Level.SUPPORTED:
        return [
            (_step("axes", "Draw and label the axes", 2.0, labels=2), graph[:3]),
            (_step("equation", "Show the equation of the curve", 1.5, labels=1), ["equation"]),
            (_step("curve", "Draw the curve from left to right", 3.0), ["curve"]),
            (
                _step("point", "Mark the point where the tangent touches the curve", 1.5, 1, 1),
                touch[:2],
            ),
            (
                _step("tangent", "Draw the tangent there and read its gradient", 2.5, 1, 1),
                touch[2:],
            ),
            slide,
        ]
    if level is Level.STANDARD:
        return [
            (_step("graph", "Draw the axes and the curve with its equation", 2.5, 3), graph),
            (
                _step("tangent", "Draw the tangent at a point and read its gradient", 2.5, 2),
                touch,
            ),
            slide,
        ]
    return [
        (
            _step("graph_and_tangent", "Draw the curve and a tangent with its gradient", 2.5, 5),
            graph + touch,
        ),
        slide,
    ]


def _introduce(name: str, mobject, level: Level):
    if name in ("point_start", "point"):
        appear = FadeIn(mobject, scale=0.5)
    elif name in ("axes", "curve", "tangent"):
        appear = Create(mobject)
    else:
        appear = Write(mobject)
    if level is Level.SUPPORTED and name in ("point_start", "tangent", "readout"):
        return Succession(appear, Indicate(mobject))
    return appear


def _step(name, description, min_run_time, labels=0, highlights=0) -> StepSpec:
    return StepSpec(
        name=name,
        description=description,
        min_run_time_s=min_run_time,
        labels=labels,
        highlights=highlights,
    )
