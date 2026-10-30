"""VolumeOfRevolution: a region turned through 360° about the x-axis or the y-axis, the solid
it sweeps out, and its volume π∫y² dx or π∫x² dy (9709 1.8).

The solid is cut into thin discs across the axis: a disc at x has radius y and thickness δx,
so volume πy²δx, and adding them is integrating. A region between two curves (one not on the
axis) sweeps a solid with a hole, cut into washers of volume π(y₁² − y₂²)δx. The sketch shows the
curve reflected in the axis and the outlines of discs, as a textbook drawing of the solid. The
volume is exact in π where SymPy can integrate, with its value to 3 significant figures.
"""

from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import DashedLine, Ellipse, Polygon, VGroup, VMobject
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import label, make_plot, place_label, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    exact,
    failing_samples,
    format_sf,
    latex_value,
    latex_with_pi,
    parse_expression,
    sample_points,
    written_latex,
)

Coordinate = Annotated[float, Field(ge=-20, le=20)]
DISCS = 7


class VolumeOfRevolutionParams(PrimitiveParams):
    axis: Literal["x", "y"] = Field(description="The axis the region turns about")
    curve: str = Field(
        min_length=1,
        max_length=100,
        description="About the x-axis: y in terms of x. About the y-axis: x in terms of y",
    )
    lower: Coordinate = Field(description="The limits, along the axis of rotation")
    upper: Coordinate
    inner: str | None = Field(
        default=None,
        max_length=100,
        description="Optionally the other boundary (same variable), for a solid with a hole",
    )


class VolumeOfRevolution(StagedPrimitive[VolumeOfRevolutionParams]):
    primitive_id = "VolumeOfRevolution"
    version = "1"
    topic = "Integration"
    params_model = VolumeOfRevolutionParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[
            ("axes", "*"),
            ("curve", "*"),
            ("inner_curve", "*"),
            ("region", "*"),
            ("mirror", "*"),
            ("discs", "*"),
            ("slice", "*"),
            ("limit_*", "*"),
        ],
    )

    def default_params(self) -> VolumeOfRevolutionParams:
        return VolumeOfRevolutionParams(axis="x", curve="sqrt(x)", lower=0, upper=4)

    def validate(self, params: VolumeOfRevolutionParams) -> list[PredicateFailure]:
        var = params.axis
        try:
            outer = parse_expression(params.curve, {var})
            inner = parse_expression(params.inner, {var}) if params.inner else sp.Integer(0)
        except ExpressionError as error:
            message = f"{error} (use {var} as the variable when turning about the {var}-axis)"
            return [_failure("parsing", "expression_parses", message, "curve", "inner")]
        if params.lower >= params.upper:
            return [_failure("consistency", "limits_ordered", "lower must be below upper")]
        symbol = sp.Symbol(var, real=True)
        points = sample_points(params.lower, params.upper)
        if failing_samples(outer, symbol, points) or failing_samples(inner, symbol, points):
            message = "the boundaries must be real and finite between the limits"
            return [_failure("domain", "real_and_finite", message, "curve", "inner")]
        o = [float(outer.subs(symbol, p)) for p in points]
        i = [float(inner.subs(symbol, p)) for p in points]
        same_side = all(a >= -1e-9 and b >= -1e-9 for a, b in zip(o, i, strict=True)) or all(
            a <= 1e-9 and b <= 1e-9 for a, b in zip(o, i, strict=True)
        )
        if not same_side:
            message = "the region must lie on one side of the axis of rotation"
            return [_failure("consistency", "one_side_of_axis", message, "curve", "inner")]
        if any(abs(b) > abs(a) + 1e-9 for a, b in zip(o, i, strict=True)):
            message = "the inner boundary must be nearer the axis than the curve"
            return [_failure("consistency", "inner_inside", message, "inner")]
        return []

    def computed_values(self, params: VolumeOfRevolutionParams) -> dict[str, str]:
        volume = _Solid(params).volume
        return {"volume": str(volume), "volume_3sf": format_sf(volume)}

    def build(self, params: VolumeOfRevolutionParams, level):
        solid = _Solid(params)
        lo, hi = float(solid.a), float(solid.b)
        t = np.linspace(lo, hi, 160)
        r_out = np.array([solid.outer_num(v) for v in t])
        r_in = np.array([solid.inner_num(v) for v in t])
        reach = float(np.max(np.abs(r_out)))
        along = [lo, hi]
        across = [reach, -reach]
        if params.axis == "x":
            plot = make_plot(style.GRAPH_REGION, along, across, equal=False)

            def p(s, r):  # position along the axis, distance from it
                return plot.point(s, r)
        else:
            plot = make_plot(style.GRAPH_REGION, across, along, equal=False)

            def p(s, r):
                return plot.point(r, s)

        def path(values, sign=1):
            line = VMobject(stroke_width=4)
            line.set_points_as_corners([p(s, sign * r) for s, r in zip(t, values, strict=True)])
            return line

        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "title": text_line(solid.title_latex(), plot.upper),
            "curve": path(r_out).set_color(style.CURVE_COLOUR),
        }
        outline = [p(s, r) for s, r in zip(t, r_out, strict=True)] + [
            p(s, r) for s, r in zip(t[::-1], r_in[::-1], strict=True)
        ]
        parts["region"] = Polygon(
            *outline, stroke_width=0, fill_color=style.AREA_COLOUR, fill_opacity=style.AREA_OPACITY
        )
        if params.inner:
            parts["inner_curve"] = path(r_in).set_color(style.RUN_COLOUR)
        limits = VGroup()
        for s in (lo, hi):
            limits.add(
                DashedLine(
                    p(s, 0), p(s, solid.outer_num(s)), color=style.HIGHLIGHT_COLOUR, stroke_width=2
                )
            )
        parts["limit_lines"] = limits
        mirror = VGroup(path(r_out, -1).set_color(style.CURVE_COLOUR).set_stroke(opacity=0.7))
        if params.inner:
            mirror.add(path(r_in, -1).set_color(style.RUN_COLOUR).set_stroke(opacity=0.7))
        parts["mirror"] = mirror
        discs = VGroup()
        for s in np.linspace(lo, hi, DISCS):
            for r in {solid.outer_num(s), solid.inner_num(s)}:
                if abs(r) < 1e-6:
                    continue
                discs.add(_disc(p, s, r, params.axis, style.SECANT_COLOUR, 2))
        parts["discs"] = discs
        middle = (lo + hi) / 2
        slice_group = VGroup(
            _disc(p, middle, solid.outer_num(middle), params.axis, style.TANGENT_COLOUR, 4)
        )
        if params.inner and abs(solid.inner_num(middle)) > 1e-6:
            slice_group.add(
                _disc(p, middle, solid.inner_num(middle), params.axis, style.TANGENT_COLOUR, 3)
            )
        parts["slice"] = slice_group
        radius = "y" if params.axis == "x" else "x"
        parts["slice_label"] = place_label(
            label(rf"\pi {radius}^2\,\delta {params.axis}", colour=style.TANGENT_COLOUR),
            p(middle, solid.outer_num(middle)),
            plot.plot_box,
            plot.obstacles(),
            [parts["curve"], *plot.axis_lines()],
            wide=True,
        )
        parts["answer"] = text_line(
            rf"V = {latex_with_pi(solid.volume)}", plot.lower, colour=style.HIGHLIGHT_COLOUR
        )
        rows = solid.rows()
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: VolumeOfRevolutionParams, level) -> list[Stage]:
        curves = ["curve", "inner_curve"] if params.inner else ["curve"]
        steps = [
            stage("axes", "Draw the axes", 1.5, ["axes", "x_label", "y_label", "title"]),
            stage("curve", "Draw the boundary of the region", 2.5, curves),
            stage(
                "region",
                "Shade the region between the limits",
                2.5,
                ["region", "limit_lines"],
            ),
            stage(
                "rotate",
                f"Turn it through 360 degrees about the {params.axis}-axis: it sweeps out a solid",
                3.5,
                ["mirror", "discs"],
            ),
            stage(
                "slice",
                "Cut the solid into thin discs; one disc has volume pi r squared times its "
                "thickness"
                if not params.inner
                else "Cut it into thin washers: a disc with a smaller disc taken out",
                3.5,
                ["slice", "slice_label", "row_1"],
                emphasise=["slice"],
            ),
            stage("integrate", "Adding the discs is integrating", 3.5, ["row_2", "row_3"]),
            stage(
                "answer",
                "Evaluate between the limits",
                3.0,
                ["row_4", "answer"],
                emphasise=["answer"],
            ),
        ]

        def standard(s):
            return [
                combine("region", "Draw the region", 3.0, *s[:3]),
                *s[3:5],
                combine("integrate", "Add the discs: integrate between the limits", 4.0, *s[5:]),
            ]

        def concise(s):
            out = standard(s)
            return [
                combine("solid", "The region and the solid it sweeps out", 4.0, *out[:2]),
                *out[2:],
            ]

        return by_level(level, steps, standard, concise)


class _Solid:
    def __init__(self, params: VolumeOfRevolutionParams):
        self.params = params
        self.var = sp.Symbol(params.axis, real=True)
        self.outer = sp.nsimplify(parse_expression(params.curve, {params.axis}), rational=True)
        self.inner = (
            sp.nsimplify(parse_expression(params.inner, {params.axis}), rational=True)
            if params.inner
            else sp.Integer(0)
        )
        self.a, self.b = exact(params.lower), exact(params.upper)
        self.integrand = sp.expand(self.outer**2 - self.inner**2)
        antiderivative = sp.integrate(self.integrand, self.var)
        self.antiderivative = None if antiderivative.has(sp.Integral) else antiderivative
        if self.antiderivative is not None:
            value = self.antiderivative.subs(self.var, self.b) - self.antiderivative.subs(
                self.var, self.a
            )
            self.volume = sp.nsimplify(sp.simplify(sp.pi * value))
        else:
            self.volume = sp.Float(
                sp.N(sp.pi * sp.Integral(self.integrand, (self.var, self.a, self.b)))
            )
        self.outer_num = sp.lambdify(self.var, self.outer, "math")
        inner_num = sp.lambdify(self.var, self.inner, "math")
        self.inner_num = lambda v: float(inner_num(v))

    def title_latex(self) -> str:
        other = "y" if self.params.axis == "x" else "x"
        text = rf"{other} = {written_latex(self.params.curve)}"
        if self.params.inner:
            text += rf",\ {other} = {written_latex(self.params.inner)}"
        return text + rf"\text{{, about the }}{self.params.axis}\text{{-axis}}"

    def rows(self) -> list[tuple[str, object]]:
        v, other = self.params.axis, ("y" if self.params.axis == "x" else "x")
        a, b = latex_value(self.a), latex_value(self.b)
        square = (
            rf"{other}^2" if not self.params.inner else rf"\left({other}_1^2 - {other}_2^2\right)"
        )
        rows = [(rf"V = \pi\int_{{{a}}}^{{{b}}} {square}\, d{v}", None)]
        rows.append(
            (rf"= \pi\int_{{{a}}}^{{{b}}} \left({sp.latex(self.integrand)}\right) d{v}", None)
        )
        if self.antiderivative is not None:
            rows.append(
                (rf"= \pi\left[{sp.latex(self.antiderivative)}\right]_{{{a}}}^{{{b}}}", None)
            )
        else:
            rows.append((r"\text{(evaluated numerically)}", None))
        rows.append((rf"= {latex_with_pi(self.volume)}", style.HIGHLIGHT_COLOUR))
        return rows


def _disc(p, s, r, axis, colour, width) -> Ellipse:
    """The outline of a disc of radius r at position s along the axis, seen at a slant."""
    top, bottom = p(s, r), p(s, -r)
    size = float(np.linalg.norm(top - bottom))
    if axis == "x":
        disc = Ellipse(width=max(0.22 * size, 0.08), height=size)
    else:
        disc = Ellipse(width=size, height=max(0.22 * size, 0.08))
    return disc.move_to((top + bottom) / 2).set_stroke(colour, width)


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
