"""AreaUnderCurve: the region under a curve shaded between two limits, with its area computed
(report Table 5.2, introductory calculus).

The area is the definite integral of f from the lower to the upper limit, found by SymPy as
[F(x)] evaluated between the limits. f must not cross the x-axis between the limits: an area
on both sides needs one integral per side, so a plan splits it into two segments. Below the
axis the area is the size of the (negative) integral.
"""

import numpy as np
import sympy as sp
from manim import (
    Create,
    DashedLine,
    FadeIn,
    Indicate,
    MathTex,
    ReplacementTransform,
    Succession,
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
)
from app.primitives.symbolic import (
    exact,
    format_number,
    latex_number,
    sample_points,
    written_latex,
)


class AreaUnderCurveParams(CurveParams):
    lower: Coordinate = Field(description="Lower limit a of the shaded region")
    upper: Coordinate = Field(description="Upper limit b of the shaded region")


class AreaUnderCurve(Primitive[AreaUnderCurveParams]):
    primitive_id = "AreaUnderCurve"
    version = "1"
    topic = "Introductory calculus"
    params_model = AreaUnderCurveParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("axes", "*"),
            ("curve", "*"),
            ("area", "*"),
            ("limit_lower", "*"),
            ("limit_upper", "*"),
        ],
    )

    def default_params(self) -> AreaUnderCurveParams:
        return AreaUnderCurveParams(expression="x**2", x_min=-1, x_max=4, lower=1, upper=3)

    def validate(self, params: AreaUnderCurveParams) -> list[PredicateFailure]:
        f, failures = check_curve(params)
        if failures:
            return failures
        if params.lower >= params.upper:
            message = "the lower limit must be below the upper limit"
            return [failure("consistency", "limits_ordered", message, "lower", "upper")]
        outside = [
            name
            for name in ("lower", "upper")
            if not params.x_min <= getattr(params, name) <= params.x_max
        ]
        if outside:
            message = f"{' and '.join(outside)} must lie inside the plotted interval"
            return [failure("consistency", "limits_in_interval", message, *outside)]
        values = [sp.N(f.subs(X, x)) for x in sample_points(params.lower, params.upper)]
        if any(v > 1e-12 for v in values) and any(v < -1e-12 for v in values):
            message = "f crosses the x-axis between the limits; split the region at the crossing"
            return [failure("consistency", "one_side_of_axis", message, "lower", "upper")]
        if _antiderivative(f) is None:
            message = "SymPy cannot integrate f in closed form"
            return [failure("domain", "integrable", message, "expression")]
        return []

    def computed_values(self, params: AreaUnderCurveParams) -> dict[str, str]:
        f = parse_function(params.expression)
        a, b = exact(params.lower), exact(params.upper)
        antiderivative = _antiderivative(f)
        at_b, at_a = antiderivative.subs(X, b), antiderivative.subs(X, a)
        integral = sp.simplify(at_b - at_a)
        return {
            "lower": format_number(a),
            "upper": format_number(b),
            "integral": format_number(integral),
            "area": format_number(sp.Abs(integral)),
            "upper_value": format_number(at_b),
            "lower_value": format_number(at_a),
        }

    def steps(self, params: AreaUnderCurveParams, level: Level) -> list[StepSpec]:
        return [spec for spec, _ in _plan(level)]

    def animate(self, scene, params, level, run_times, carried):
        fades, visible = style.clear_region(carried, self.layout.region)
        parts = self._build(params, level)
        for i, ((spec, names), run_time) in enumerate(zip(_plan(level), run_times, strict=True)):
            animations = []
            for name in names:
                if name == "evaluation":
                    # The integral turns into its evaluation, in the same place.
                    animations.append(ReplacementTransform(parts["result"], parts["evaluation"]))
                else:
                    animations.append(_introduce(name, parts[name], level))
            style.play_step(
                scene, (fades if i == 0 else []) + animations, run_time, spec.min_run_time_s
            )
            for name in names:
                if name == "evaluation":
                    visible["result"] = parts["evaluation"]
                else:
                    visible[name] = parts[name]
            yield dict(visible)

    def _build(self, params: AreaUnderCurveParams, level: Level) -> dict:
        f = parse_function(params.expression)
        y_of = sp.lambdify(X, f, "math")
        figure = draw_curve(params, f, self.layout.region)
        axes = figure.axes
        a, b = exact(params.lower), exact(params.upper)

        area = axes.get_area(
            figure.curve,
            x_range=[params.lower, params.upper],
            color=style.AREA_COLOUR,
            opacity=style.AREA_OPACITY,
        )
        limits, limit_labels = {}, {}
        obstacles = [figure.x_label, figure.y_label, *style.axis_numbers(axes)]
        for key, x in (("lower", params.lower), ("upper", params.upper)):
            top = axes.c2p(x, float(y_of(x)))
            limits[key] = DashedLine(axes.c2p(x, 0), top, color=style.POINT_COLOUR)
            label = MathTex(
                rf"x = {latex_number(exact(x))}",
                font_size=style.LABEL_FONT_SIZE,
                color=style.POINT_COLOUR,
            )
            # Beside the top of its line, outside the region first.
            beside = np.array([(-1 if key == "lower" else 1) * (label.width / 2 + 0.2), 0, 0])
            candidates = [top + beside, *style.around(top, label), axes.c2p(x, 0) + beside]
            style.place_clear(label, candidates, figure.plot_box, obstacles, label_paths(figure))
            obstacles.append(label)
            limit_labels[key] = label

        middle = (params.lower + params.upper) / 2
        area_label = MathTex("A", font_size=style.FONT_SIZE, color=style.TEXT_COLOUR)
        centre = axes.c2p(middle, float(y_of(middle)) / 2)
        style.place_clear(
            area_label,
            [centre, *style.around(centre, area_label)],
            figure.plot_box,
            obstacles + list(limits.values()),
            label_paths(figure),
        )

        antiderivative = _antiderivative(f)
        at_b, at_a = antiderivative.subs(X, b), antiderivative.subs(X, a)
        integral = sp.simplify(at_b - at_a)
        integrand = inline(written_latex(params.expression))
        if isinstance(f, sp.Add):  # ∫ (x^2 - 4) dx, not ∫ x^2 - 4 dx
            integrand = rf"\left( {integrand} \right)"
        setup = rf"\int_{{{latex_number(a)}}}^{{{latex_number(b)}}} {integrand} \, dx"
        below = bool(integral < 0)
        value = latex_number(sp.Abs(integral))
        if below:  # the region is under the axis: the area is the size of the integral
            setup = rf"\left| {setup} \right|"
        limits_tex = rf"_{{{latex_number(a)}}}^{{{latex_number(b)}}}"
        primitive_tex = inline(sp.latex(antiderivative, ln_notation=True))
        bracket = rf"\left[ {primitive_tex} \right]{limits_tex}"
        if below:
            bracket = rf"\left| {bracket} \right|"
        difference = rf"{latex_number(at_b)} - {_bracketed(latex_number(at_a))}"
        if below:
            difference = rf"\left| {difference} \right|"

        def line(tex):
            return style.fit_inside(
                MathTex(inline(tex), font_size=style.FONT_SIZE), figure.lower_line
            )

        # One short line per level, so it stays readable in the title band (Table 5.3). Level 1
        # writes the integral, then evaluates it with every step; Level 2 integrates and gives the
        # value; Level 3 gives the value directly. Longer working belongs to an
        # EquationTransform segment in the working region.
        evaluation = line(rf"A = {bracket} = {difference} = {value}")
        if level is Level.SUPPORTED:
            result = line(rf"A = {setup}")
        elif level is Level.STANDARD:
            result = line(rf"A = {bracket} = {value}")
        else:
            result = line(rf"A = {setup} = {value}")

        return {
            "axes": axes,
            "x_label": figure.x_label,
            "y_label": figure.y_label,
            "equation": figure.equation,
            "curve": figure.curve,
            "limit_lower": limits["lower"],
            "limit_upper": limits["upper"],
            "limit_lower_label": limit_labels["lower"],
            "limit_upper_label": limit_labels["upper"],
            "area": area,
            "area_label": area_label,
            "result": result,
            "evaluation": evaluation,
        }


def _antiderivative(f: sp.Expr) -> sp.Expr | None:
    antiderivative = sp.integrate(f, X)
    return None if antiderivative.has(sp.Integral) else antiderivative


def _bracketed(tex: str) -> str:
    """A negative number after a minus sign keeps its brackets: 9 - (-2)."""
    return rf"\left({tex}\right)" if tex.startswith("-") else tex


def _plan(level: Level) -> list[tuple[StepSpec, list[str]]]:
    graph = ["axes", "x_label", "y_label", "equation", "curve"]
    limits = ["limit_lower", "limit_lower_label", "limit_upper", "limit_upper_label"]
    if level is Level.SUPPORTED:
        return [
            (_step("axes", "Draw and label the axes", 2.0, labels=2), graph[:3]),
            (_step("equation", "Show the equation of the curve", 1.5, labels=1), ["equation"]),
            (_step("curve", "Draw the curve from left to right", 3.0), ["curve"]),
            (_step("limits", "Mark the two limits on the x-axis", 2.0, 2, 2), limits),
            (_step("shade", "Shade the area between the curve and the x-axis", 2.0, 1, 1),
             ["area", "area_label"]),
            (_step("integral", "Write the area as a definite integral", 2.5, 1), ["result"]),
            (_step("evaluate", "Integrate and subtract to find the area", 3.0, 1, 1),
             ["evaluation"]),
        ]  # fmt: skip
    if level is Level.STANDARD:
        return [
            (_step("graph", "Draw the axes and the curve with its equation", 2.5, 3), graph),
            (_step("region", "Mark the limits and shade the area between them", 2.5, 3),
             limits + ["area", "area_label"]),
            (_step("integral", "Write the area as an integral and evaluate it", 3.0, 1),
             ["result"]),
        ]  # fmt: skip
    return [
        (_step("region", "Draw the curve and shade the area between the limits", 2.5, 6),
         graph + limits + ["area", "area_label"]),
        (_step("area", "Give the area as an integral and its value", 2.0, 1), ["result"]),
    ]  # fmt: skip


def _introduce(name: str, mobject, level: Level):
    if name in ("axes", "curve", "limit_lower", "limit_upper"):
        appear = Create(mobject)
    elif name == "area":
        appear = FadeIn(mobject)
    else:
        appear = Write(mobject)
    if level is Level.SUPPORTED and name in ("area", "limit_lower", "limit_upper"):
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
