"""TangentNormal: the tangent and the normal to a curve at a point, with their equations
(AM 14.5; 4024 2.10.4; PRIMITIVES.md #52, tangent and normal equations).

The gradient of the tangent is dy/dx at the point; the normal is perpendicular to it, so its
gradient is -1 over that. Each line's equation comes from y - y₁ = m(x - x₁). One unit is the
same length on both axes, so the normal looks perpendicular. A horizontal tangent has a
vertical normal (x = a). Every value is computed exactly by SymPy.
"""

from typing import Annotated

import sympy as sp
from manim import Dot, Line
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure
from app.primitives import style
from app.primitives.curves import CurveParams, X, check_curve, parse_function, smooth_failures
from app.primitives.plotting import angle_mark, curve, label, make_plot, place_label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_value, latex_value, tidy_latex, written_latex

Coordinate = Annotated[float, Field(ge=-20, le=20)]


class TangentNormalParams(CurveParams):
    x0: Coordinate = Field(description="x of the point where the tangent and normal are drawn")


class TangentNormal(StagedPrimitive[TangentNormalParams]):
    primitive_id = "TangentNormal"
    version = "1"
    topic = "Introductory calculus"
    params_model = TangentNormalParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("axes", "*"),
            ("curve", "*"),
            ("tangent", "*"),
            ("normal", "*"),
            ("right_angle", "*"),
            ("point", "*"),
        ],
    )

    def default_params(self) -> TangentNormalParams:
        return TangentNormalParams(expression="x**2 - 2*x", x_min=-1, x_max=4, x0=2.5)

    def validate(self, params: TangentNormalParams) -> list[PredicateFailure]:
        f, failures = check_curve(params)
        if failures:
            return failures
        if not params.x_min <= params.x0 <= params.x_max:
            return [
                PredicateFailure(
                    kind="consistency",
                    predicate="point_in_interval",
                    message="x0 must lie inside the plotted interval",
                    parameters=["x0"],
                )
            ]
        return smooth_failures(f, params.x0, params.x0, "x0")

    def computed_values(self, params: TangentNormalParams) -> dict[str, str]:
        t = _Lines(params)
        return {
            "point": f"({format_value(t.x0)}, {format_value(t.y0)})",
            "tangent_gradient": format_value(t.m),
            "normal_gradient": "undefined" if t.normal_m is None else format_value(t.normal_m),
            "tangent": t.equation_text(t.m),
            "normal": t.equation_text(t.normal_m),
        }

    def build(self, params: TangentNormalParams, level):
        t = _Lines(params)
        f_num = sp.lambdify(X, t.f, "math")
        xs = [params.x_min + (params.x_max - params.x_min) * i / 60 for i in range(61)]
        plot = make_plot(
            self.layout.region,
            [params.x_min, params.x_max],
            [f_num(x) for x in xs] + [float(t.y0)],
            equal=True,
        )
        point = plot.point(float(t.x0), float(t.y0))
        tangent = style.line_in_axes(
            plot.axes,
            (float(t.x0), float(t.y0)),
            float(t.m),
            plot.x_range,
            plot.y_range,
            color=style.TANGENT_COLOUR,
            stroke_width=4,
        )
        if t.normal_m is None:
            normal = Line(
                plot.point(float(t.x0), plot.y_range[0]),
                plot.point(float(t.x0), plot.y_range[1]),
                color=style.SECANT_COLOUR,
                stroke_width=4,
            )
            along_normal = plot.point(float(t.x0), float(t.y0) + 1)
        else:
            normal = style.line_in_axes(
                plot.axes,
                (float(t.x0), float(t.y0)),
                float(t.normal_m),
                plot.x_range,
                plot.y_range,
                color=style.SECANT_COLOUR,
                stroke_width=4,
            )
            step = 1 / (1 + float(t.normal_m) ** 2) ** 0.5
            along_normal = plot.point(float(t.x0) + step, float(t.y0) + float(t.normal_m) * step)
        step = 1 / (1 + float(t.m) ** 2) ** 0.5
        along_tangent = plot.point(float(t.x0) + step, float(t.y0) + float(t.m) * step)
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "equation": text_line(f"y = {written_latex(params.expression)}", plot.upper),
            "curve": curve(plot, f_num, params.x_min, params.x_max),
            "point": Dot(point, color=style.POINT_COLOUR),
            "gradient": text_line(
                rf"\frac{{dy}}{{dx}} = {tidy_latex(t.derivative)} = {latex_value(t.m)}"
                rf"\text{{ at }} x = {latex_value(t.x0)}",
                plot.lower,
            ),
            "normal_gradient": text_line(t.normal_gradient_latex(), plot.lower),
            "tangent": tangent,
            "normal": normal,
            "right_angle": angle_mark(
                point, along_tangent, along_normal, radius=0.3, colour=style.TEXT_COLOUR
            ),
        }
        obstacles = [*plot.obstacles(), parts["point"]]
        paths = [parts["curve"], tangent, normal, *plot.axis_lines()]
        for name, tex, colour, anchor in (
            (
                "point_label",
                rf"({latex_value(t.x0)},\ {latex_value(t.y0)})",
                style.POINT_COLOUR,
                point,
            ),
            ("tangent_label", t.equation_latex(t.m), style.TANGENT_COLOUR, tangent.get_end()),
            ("normal_label", t.equation_latex(t.normal_m), style.SECANT_COLOUR, normal.get_end()),
        ):
            text = label(tex, colour=colour)
            parts[name] = place_label(text, anchor, plot.plot_box, obstacles, paths, wide=True)
            obstacles.append(text)
        return parts

    def stages(self, params: TangentNormalParams, level) -> list[Stage]:
        steps = [
            stage(
                "graph", "Draw the curve", 2.0, ["axes", "x_label", "y_label", "equation", "curve"]
            ),
            stage(
                "point",
                "Mark the point on the curve",
                1.5,
                ["point", "point_label"],
                emphasise=["point"],
            ),
            stage(
                "gradient",
                "Differentiate and substitute x to get the tangent's gradient",
                3.0,
                ["gradient"],
                emphasise=["gradient"],
            ),
            stage(
                "tangent",
                "The tangent: y minus y1 equals m times x minus x1",
                3.0,
                ["tangent", "tangent_label"],
            ),
            stage(
                "normal_gradient",
                "The normal is perpendicular: its gradient is minus 1 over the tangent's",
                3.0,
                morph=[("gradient", "normal_gradient")],
            ),
            stage(
                "normal",
                "The normal through the same point",
                3.0,
                ["normal", "normal_label", "right_angle"],
            ),
        ]

        def standard(s):
            return [
                combine("graph", "Draw the curve and mark the point", 2.5, s[0], s[1]),
                combine("tangent", "Find the gradient and draw the tangent", 3.5, s[2], s[3]),
                combine("normal", "The normal is perpendicular to the tangent", 3.5, s[4], s[5]),
            ]

        def concise(s):
            return [
                combine("graph", "The curve and the point", 2.5, s[0], s[1]),
                combine("lines", "The tangent and the normal at the point", 4.0, *s[2:]),
            ]

        return by_level(level, steps, standard, concise)


class _Lines:
    def __init__(self, params: TangentNormalParams):
        self.f = parse_function(params.expression)
        self.derivative = sp.diff(self.f, X)
        self.x0 = exact(params.x0)
        self.y0 = sp.nsimplify(self.f.subs(X, self.x0))
        self.m = sp.nsimplify(self.derivative.subs(X, self.x0))
        self.normal_m = None if self.m == 0 else -1 / self.m

    def _rhs(self, m):
        return sp.expand(m * (X - self.x0) + self.y0)

    def equation_text(self, m) -> str:
        return f"x = {self.x0}" if m is None else f"y = {self._rhs(m)}"

    def equation_latex(self, m) -> str:
        return f"x = {latex_value(self.x0)}" if m is None else f"y = {tidy_latex(self._rhs(m))}"

    def normal_gradient_latex(self) -> str:
        if self.normal_m is None:
            return r"m = 0\text{, so the normal is vertical}"
        return (
            rf"m_{{\text{{normal}}}} = \frac{{-1}}{{{latex_value(self.m)}}} = "
            rf"{latex_value(self.normal_m)}"
        )
