"""SecantToTangent: secant lines through x0 and x0 + h approaching the tangent as h decreases
(report Table 5.2, introductory calculus).

P is the point at x0 and Q the point at x0 + h. For each h in turn the secant PQ is drawn with
its gradient (f(x0 + h) - f(x0)) / h; then the tangent at P is drawn with its gradient f'(x0),
the value the secant gradients approach. Every gradient shown is computed exactly by SymPy.
"""

from typing import Annotated

import sympy as sp
from manim import (
    AnimationGroup,
    Create,
    Dot,
    FadeIn,
    Indicate,
    MathTex,
    Succession,
    Transform,
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
    point_text,
    smooth_failures,
)
from app.primitives.symbolic import exact, format_number, latex_number

Step = Annotated[float, Field(ge=-20, le=20)]


class SecantToTangentParams(CurveParams):
    x0: Coordinate = Field(description="x of the point P where the tangent is found")
    h_values: list[Step] = Field(
        min_length=2,
        max_length=5,
        description="Distances from P to Q along x, shrinking towards 0, e.g. [2, 1, 0.5, 0.1]",
    )


class SecantToTangent(Primitive[SecantToTangentParams]):
    primitive_id = "SecantToTangent"
    version = "1"
    topic = "Introductory calculus"
    params_model = SecantToTangentParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("axes", "*"),
            ("curve", "*"),
            ("secant", "*"),
            ("tangent", "*"),
            # As h shrinks Q closes in on P; that is the point of the picture.
            ("point_p", "point_q"),
        ],
    )

    def default_params(self) -> SecantToTangentParams:
        return SecantToTangentParams(
            expression="x**2", x_min=-1, x_max=4, x0=1, h_values=[2, 1, 0.5, 0.1]
        )

    def validate(self, params: SecantToTangentParams) -> list[PredicateFailure]:
        f, failures = check_curve(params)
        if failures:
            return failures
        if not params.x_min <= params.x0 <= params.x_max:
            return [
                failure("consistency", "point_in_interval", "x0 must lie inside the interval", "x0")
            ]
        if any(h == 0 for h in params.h_values):
            return [failure("consistency", "h_nonzero", "h = 0 gives no secant", "h_values")]
        failures = []
        outside = [h for h in params.h_values if not params.x_min <= params.x0 + h <= params.x_max]
        if outside:
            message = f"x0 + h is outside the plotted interval for h = {outside}"
            failures.append(failure("consistency", "q_in_interval", message, "h_values"))
        sizes = [abs(h) for h in params.h_values]
        if any(later >= earlier for earlier, later in zip(sizes, sizes[1:], strict=False)):
            message = "each h must be closer to 0 than the one before"
            failures.append(failure("consistency", "h_decreasing", message, "h_values"))
        return failures + smooth_failures(f, params.x0, params.x0, "x0")

    def computed_values(self, params: SecantToTangentParams) -> dict[str, str]:
        f = parse_function(params.expression)
        x0 = exact(params.x0)
        y0 = f.subs(X, x0)
        values = {"x0": format_number(x0), "y0": format_number(y0), "point_p": point_text(x0, y0)}
        for i, h in enumerate(params.h_values, start=1):
            h = exact(h)
            values[f"h_{i}"] = format_number(h)
            values[f"point_q_{i}"] = point_text(x0 + h, f.subs(X, x0 + h))
            values[f"secant_gradient_{i}"] = format_number(_secant_gradient(f, x0, h))
        values["tangent_gradient"] = format_number(sp.simplify(sp.diff(f, X).subs(X, x0)))
        return values

    def steps(self, params: SecantToTangentParams, level: Level) -> list[StepSpec]:
        return [spec for spec, _ in _plan(len(params.h_values), level)]

    def animate(self, scene, params, level, run_times, carried):
        fades, visible = style.clear_region(carried, self.layout.region)
        parts = self._build(params, level)
        plan = _plan(len(params.h_values), level)
        for i, ((spec, actions), run_time) in enumerate(zip(plan, run_times, strict=True)):
            animations = [_action(action, parts, level) for action in actions]
            style.play_step(
                scene, (fades if i == 0 else []) + animations, run_time, spec.min_run_time_s
            )
            for action in actions:
                if action.startswith(("secant:", "approach:")):
                    visible.update({name: parts[name] for name in _SECANT_PARTS})
                elif action == "tangent":
                    visible["tangent"] = parts["tangent"]
                    visible["readout"] = parts["readout"]
                else:
                    visible[action] = parts[action]
            yield dict(visible)

    def _build(self, params: SecantToTangentParams, level: Level) -> dict:
        f = parse_function(params.expression)
        figure = draw_curve(params, f, self.layout.region)
        axes = figure.axes
        x0 = exact(params.x0)
        y0 = f.subs(X, x0)
        p = axes.c2p(float(x0), float(y0))

        def line(slope, colour):
            return style.line_in_axes(
                axes,
                (float(x0), float(y0)),
                float(slope),
                figure.x_range,
                figure.y_range,
                color=colour,
                stroke_width=5,
            )

        def readout(tex):
            return style.fit_inside(
                MathTex(inline(tex), font_size=style.FONT_SIZE), figure.lower_line
            )

        tangent_gradient = sp.simplify(sp.diff(f, X).subs(X, x0))
        tangent = line(tangent_gradient, style.TANGENT_COLOUR)
        secants, qs, q_labels, readouts = [], [], [], []
        dot_p = Dot(p, color=style.POINT_COLOUR)
        p_label = MathTex("P", font_size=style.LABEL_FONT_SIZE, color=style.POINT_COLOUR)
        for h in params.h_values:
            h = exact(h)
            gradient = _secant_gradient(f, x0, h)
            secants.append(line(gradient, style.SECANT_COLOUR))
            qs.append(
                Dot(axes.c2p(float(x0 + h), float(f.subs(X, x0 + h))), color=style.POINT_COLOUR)
            )
            q_labels.append(MathTex("Q", font_size=style.LABEL_FONT_SIZE, color=style.POINT_COLOUR))
            secant_word = r"\quad \text{gradient of } PQ = "
            readouts.append(
                readout(rf"h = {latex_number(h)}:{secant_word}{latex_number(gradient)}")
            )
        tangent_readout = readout(
            rf"\text{{gradient of tangent}} = {latex_number(tangent_gradient)}"
        )

        # P's label avoids every line it will meet; each Q label avoids P and its own secant.
        obstacles = [figure.x_label, figure.y_label, dot_p, *qs, *style.axis_numbers(axes)]
        paths = label_paths(figure, tangent, *secants)
        style.place_clear(p_label, style.around(p, p_label), figure.plot_box, obstacles, paths)
        obstacles.append(p_label)
        for q, label, secant in zip(qs, q_labels, secants, strict=True):
            style.place_clear(
                label,
                style.around_wide(q.get_center(), label),
                figure.plot_box,
                obstacles,
                label_paths(figure, secant, tangent),
            )

        return {
            "axes": axes,
            "x_label": figure.x_label,
            "y_label": figure.y_label,
            "equation": figure.equation,
            "curve": figure.curve,
            "point_p": dot_p,
            "point_p_label": p_label,
            # The first secant's objects; later ones are what they are transformed into.
            "secant": secants[0],
            "point_q": qs[0],
            "point_q_label": q_labels[0],
            "readout": readouts[0],
            "targets": list(zip(secants, qs, q_labels, readouts, strict=True)),
            "tangent": tangent,
            "tangent_readout": tangent_readout,
        }


_SECANT_PARTS = ("secant", "point_q", "point_q_label", "readout")


def _secant_gradient(f: sp.Expr, x0: sp.Expr, h: sp.Expr) -> sp.Expr:
    return sp.simplify((f.subs(X, x0 + h) - f.subs(X, x0)) / h)


def _action(action: str, parts: dict, level: Level):
    """The animation of one entry of a step's plan.

    "secant:1" draws the first secant; "secant:2" and later move Q, the secant and the read-out
    to the next h; "tangent" draws the tangent and states its gradient.
    """
    if action.startswith("secant:"):
        index = int(action.split(":")[1]) - 1
        if index == 0:
            appear = [
                Create(parts["secant"]),
                FadeIn(parts["point_q"], scale=0.5),
                Write(parts["point_q_label"]),
                Write(parts["readout"]),
            ]
            return Succession(*appear) if level is Level.SUPPORTED else _together(appear)
        secant, q, label, readout = parts["targets"][index]
        return _together(
            [
                Transform(parts["secant"], secant),
                Transform(parts["point_q"], q),
                Transform(parts["point_q_label"], label),
                Transform(parts["readout"], readout),
            ]
        )
    if action.startswith("approach:"):
        first, last = (int(n) for n in action.split(":")[1].split("-"))
        return Succession(*(_action(f"secant:{i}", parts, level) for i in range(first, last + 1)))
    if action == "tangent":
        draw = Create(parts["tangent"])
        if level is Level.SUPPORTED:
            draw = Succession(draw, Indicate(parts["tangent"]))
        return _together([draw, Transform(parts["readout"], parts["tangent_readout"])])
    mobject = parts[action]
    if action in ("point_p",):
        appear = FadeIn(mobject, scale=0.5)
        return Succession(appear, Indicate(mobject)) if level is Level.SUPPORTED else appear
    if action in ("axes", "curve"):
        return Create(mobject)
    return Write(mobject)


def _together(animations):
    return AnimationGroup(*animations)


def _plan(n: int, level: Level) -> list[tuple[StepSpec, list[str]]]:
    """The steps for n values of h. Entries name objects to draw, or actions (see _action)."""
    graph = ["axes", "x_label", "y_label", "equation", "curve"]
    point = ["point_p", "point_p_label"]
    tangent = (
        _step(
            "tangent",
            "Draw the tangent at P: the secant gradients approach its gradient",
            {Level.SUPPORTED: 3.0, Level.STANDARD: 2.5, Level.CONCISE: 2.0}[level],
            labels=1,
            highlights=1 if level is Level.SUPPORTED else 0,
        ),
        ["tangent"],
    )
    if level is Level.SUPPORTED:
        plan = [
            (_step("axes", "Draw and label the axes", 2.0, labels=2), graph[:3]),
            (_step("equation", "Show the equation of the curve", 1.5, labels=1), ["equation"]),
            (_step("curve", "Draw the curve from left to right", 3.0), ["curve"]),
            (_step("point_p", "Mark the point P on the curve", 1.5, 1, 1), point),
            (
                _step("secant_1", "Draw the secant from P to Q and find its gradient", 3.0, 2, 1),
                ["secant:1"],
            ),
        ]
        for i in range(2, n + 1):
            plan.append(
                (
                    _step(
                        f"secant_{i}",
                        "Move Q closer to P and find the new gradient",
                        2.5,
                        labels=1,
                        highlights=1,
                    ),
                    [f"secant:{i}"],
                )
            )
        return plan + [tangent]
    if level is Level.STANDARD:
        return [
            (_step("graph", "Draw the axes and the curve with its equation", 2.5, 3), graph),
            (
                _step("secant", "Mark P, then draw the secant PQ with its gradient", 2.5, 3),
                point + ["secant:1"],
            ),
            (
                _step("approach", "Move Q towards P: the secant gradient changes", 3.0, n - 1),
                [f"approach:2-{n}"],
            ),
            tangent,
        ]
    return [
        (
            _step("graph_and_secant", "Draw the curve with P and the secant PQ", 2.5, 5),
            graph + point + ["secant:1"],
        ),
        (
            _step("approach", "Move Q towards P", 2.0, n - 1),
            [f"approach:2-{n}"],
        ),
        tangent,
    ]


def _step(name, description, min_run_time, labels=0, highlights=0) -> StepSpec:
    return StepSpec(
        name=name,
        description=description,
        min_run_time_s=min_run_time,
        labels=labels,
        highlights=highlights,
    )
