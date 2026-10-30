"""ImplicitCurve: a curve given by an equation in x and y, differentiated implicitly to find
dy/dx, and the tangent (or normal) at a point on it (9709 2.4, 3.4).

y is a function of x along the curve, so each side of the equation is differentiated with
respect to x, using the chain rule on every term with y: d/dx(y²) = 2y dy/dx, and the product
rule on a term like xy: d/dx(xy) = y + x dy/dx. Collecting the dy/dx terms and dividing gives
the gradient anywhere on the curve, then at the point. The curve itself is drawn from its
equation (every point where the two sides are equal). SymPy does the differentiation exactly.
"""

from typing import Annotated, Literal

import sympy as sp
from manim import Dot, ImplicitFunction
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import label, make_plot, place_label, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    exact,
    format_value,
    latex_value,
    parse_equation,
    tidy_latex,
    written_latex,
)

X, Y = sp.symbols("x y", real=True)
DY = sp.Symbol("zz")  # stands for dy/dx; named to print after x and y
DY_TEX = r"\frac{dy}{dx}"
Coordinate = Annotated[float, Field(ge=-20, le=20)]


class ImplicitCurveParams(PrimitiveParams):
    equation: str = Field(
        min_length=3, max_length=100, description='In x and y, e.g. "x**2 + y**2 = x*y + 7"'
    )
    point: tuple[Coordinate, Coordinate] = Field(description="A point on the curve")
    x_min: Coordinate
    x_max: Coordinate
    y_min: Coordinate
    y_max: Coordinate
    line: Literal["tangent", "normal"] = "tangent"


class ImplicitCurve(StagedPrimitive[ImplicitCurveParams]):
    primitive_id = "ImplicitCurve"
    version = "1"
    topic = "Differentiation"
    params_model = ImplicitCurveParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[("axes", "*"), ("curve", "*"), ("line", "*"), ("point", "*")],
    )

    def default_params(self) -> ImplicitCurveParams:
        return ImplicitCurveParams(
            equation="x**2 + y**2 = x*y + 7", point=(3, 2), x_min=-4, x_max=4, y_min=-4, y_max=4
        )

    def validate(self, params: ImplicitCurveParams) -> list[PredicateFailure]:
        try:
            lhs, rhs = parse_equation(params.equation, {"x", "y"})
        except ExpressionError as error:
            return [_failure("parsing", "expression_parses", str(error), "equation")]
        if not (lhs - rhs).has(Y):
            return [_failure("consistency", "has_y", "the equation must involve y", "equation")]
        if params.x_min >= params.x_max or params.y_min >= params.y_max:
            return [_failure("consistency", "ranges_ordered", "each min must be below its max")]
        x0, y0 = (exact(v) for v in params.point)
        if not (params.x_min < x0 < params.x_max and params.y_min < y0 < params.y_max):
            message = "the point must be inside the drawn ranges"
            return [_failure("consistency", "point_in_range", message, "point")]
        if sp.simplify((lhs - rhs).subs({X: x0, Y: y0})) != 0:
            message = "the point does not satisfy the equation, so it is not on the curve"
            return [_failure("consistency", "point_on_curve", message, "point")]
        c = _Curve(params)
        if c.fy0 == 0:
            message = "the tangent is vertical there (dy/dx is undefined); choose another point"
            return [_failure("consistency", "gradient_defined", message, "point")]
        if params.line == "normal" and c.m == 0:
            message = "the tangent is flat there, so the normal is vertical"
            return [_failure("consistency", "gradient_defined", message, "line")]
        return []

    def computed_values(self, params: ImplicitCurveParams) -> dict[str, str]:
        c = _Curve(params)
        return {"dy_dx": str(c.dydx), "gradient": format_value(c.m), "line": str(c.line_expr)}

    def build(self, params: ImplicitCurveParams, level):
        c = _Curve(params)
        plot = make_plot(
            style.GRAPH_REGION,
            [params.x_min, params.x_max],
            [params.y_min, params.y_max],
            equal=True,
        )
        f = sp.lambdify((X, Y), c.F, "math")
        shape = ImplicitFunction(
            lambda a, b: f(a, b),
            x_range=[params.x_min, params.x_max],
            y_range=[params.y_min, params.y_max],
            color=style.CURVE_COLOUR,
            min_depth=6,
            max_quads=2000,
        )
        shape.apply_function(lambda p: plot.axes.c2p(p[0], p[1]))
        shape.set_stroke(style.CURVE_COLOUR, 4)
        x0, y0 = c.x0, c.y0
        point = plot.point(float(x0), float(y0))
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "title": text_line(written_latex(params.equation), plot.upper),
            "curve": shape,
            "point": Dot(point, color=style.POINT_COLOUR),
            "line": style.line_in_axes(
                plot.axes,
                (float(x0), float(y0)),
                float(c.slope),
                plot.x_range,
                plot.y_range,
                color=style.TANGENT_COLOUR,
                stroke_width=3,
            ),
            "answer": text_line(
                rf"y = {tidy_latex(c.line_expr)}", plot.lower, colour=style.TANGENT_COLOUR
            ),
        }
        parts["point_label"] = place_label(
            label(rf"({latex_value(x0)},\ {latex_value(y0)})", colour=style.POINT_COLOUR),
            point,
            plot.plot_box,
            plot.obstacles(),
            [parts["line"], *plot.axis_lines()],
            wide=True,
        )
        rows = c.rows()
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], box, size=30, colours=[col for _, col in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: ImplicitCurveParams, level) -> list[Stage]:
        steps = [
            stage(
                "curve",
                "The curve is every point whose x and y fit the equation",
                3.0,
                ["axes", "x_label", "y_label", "title", "curve"],
            ),
            stage(
                "differentiate",
                "Differentiate each term with respect to x: a term in y gains a factor d y by "
                "d x, by the chain rule",
                4.0,
                ["row_1", "row_2"],
                emphasise=["row_2"],
            ),
            stage(
                "collect",
                "Collect the d y by d x terms on one side, and divide",
                3.5,
                ["row_3", "row_4"],
            ),
            stage(
                "point",
                "Substitute the point to get the gradient there",
                3.0,
                ["point", "point_label", "row_5"],
                emphasise=["point"],
            ),
            stage(
                "line",
                f"Then the {params.line}"
                + (": gradient minus 1 over m" if params.line == "normal" else ""),
                3.0,
                ["line", "row_6", "answer"],
                emphasise=["answer"],
            ),
        ]

        def standard(s):
            return [s[0], combine("differentiate", s[1].description, 4.5, s[1], s[2]), *s[3:]]

        def concise(s):
            return [
                s[0],
                combine("differentiate", "Differentiate implicitly and rearrange", 4.5, s[1], s[2]),
                combine(
                    "line", f"The gradient at the point, and the {params.line}", 4.0, s[3], s[4]
                ),
            ]

        return by_level(level, steps, standard, concise)


class _Curve:
    def __init__(self, params: ImplicitCurveParams):
        self.params = params
        lhs, rhs = parse_equation(params.equation, {"x", "y"})
        self.lhs = sp.nsimplify(lhs, rational=True)
        self.rhs = sp.nsimplify(rhs, rational=True)
        self.F = self.lhs - self.rhs
        self.fx, self.fy = sp.diff(self.F, X), sp.diff(self.F, Y)
        self.dydx = sp.simplify(-self.fx / self.fy)
        self.x0, self.y0 = (exact(v) for v in params.point)
        at = {X: self.x0, Y: self.y0}
        self.fy0 = sp.simplify(self.fy.subs(at))
        self.m = (
            sp.nsimplify(sp.simplify(-self.fx.subs(at) / self.fy0)) if self.fy0 != 0 else sp.zoo
        )
        self.slope = (
            self.m
            if params.line == "tangent"
            else (-1 / self.m if self.m not in (0, sp.zoo) else sp.zoo)
        )
        self.line_expr = (
            sp.expand(self.slope * (X - self.x0) + self.y0) if self.slope != sp.zoo else sp.nan
        )

    def _implicit(self, side: sp.Expr) -> str:
        """d/dx of one side, with dy/dx written out."""
        yf = sp.Function("y")(X)
        derivative = sp.diff(side.subs(Y, yf), X).subs(sp.Derivative(yf, X), DY).subs(yf, Y)
        return sp.latex(sp.expand(derivative)).replace("zz", DY_TEX)

    def rows(self) -> list[tuple[str, object]]:
        name = "m" if self.params.line == "tangent" else r"m_{\text{normal}}"
        rows = [
            (written_latex(self.params.equation), None),
            (rf"{self._implicit(self.lhs)} = {self._implicit(self.rhs)}", style.RISE_COLOUR),
            (
                rf"{DY_TEX}\left({tidy_latex(self.fy)}\right) = {tidy_latex(-self.fx)}",
                None,
            ),
            (rf"{DY_TEX} = {sp.latex(self.dydx)}", style.RISE_COLOUR),
            (
                rf"\left({latex_value(self.x0)},\ {latex_value(self.y0)}\right):\ "
                rf"{DY_TEX} = {latex_value(self.m)}",
                style.POINT_COLOUR,
            ),
            (
                rf"{name} = {latex_value(self.slope)},\ y = {tidy_latex(self.line_expr)}",
                style.TANGENT_COLOUR,
            ),
        ]
        return rows


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
