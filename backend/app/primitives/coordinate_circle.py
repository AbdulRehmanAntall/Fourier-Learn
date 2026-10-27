"""CoordinateCircle: the circle (x - a)² + (y - b)² = r², its expanded form, and where a straight
line meets it (AM 8.1 to 8.4; PRIMITIVES.md #26, AM-EXT).

The centre and radius are read from the equation. Substituting the line into the circle gives a
quadratic in x whose discriminant says whether the line cuts the circle twice, touches it (a
tangent) or misses it. One unit is the same length on both axes, so the circle is round. Every
value is computed exactly by SymPy.
"""

from typing import Annotated

import sympy as sp
from manim import Circle, Dot, Line
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, make_plot, place_label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_value, latex_value, tidy_latex

X, Y = sp.symbols("x y", real=True)
Number = Annotated[float, Field(ge=-15, le=15)]


class CoordinateCircleParams(PrimitiveParams):
    centre: tuple[Number, Number]
    radius: Annotated[float, Field(gt=0, le=15)]
    line_gradient: Number | None = Field(default=None, description="Optional line y = mx + c: m")
    line_intercept: Number | None = Field(default=None, description="Optional line: c")


class CoordinateCircle(StagedPrimitive[CoordinateCircleParams]):
    primitive_id = "CoordinateCircle"
    version = "1"
    topic = "Coordinate geometry"
    params_model = CoordinateCircleParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("axes", "*"),
            ("circle", "*"),
            ("radius", "*"),
            ("line", "*"),
            ("meet_*", "*"),
            ("centre", "radius"),
        ],
    )

    def default_params(self) -> CoordinateCircleParams:
        return CoordinateCircleParams(centre=(2, 1), radius=5, line_gradient=1, line_intercept=4)

    def validate(self, params: CoordinateCircleParams):
        if (params.line_gradient is None) != (params.line_intercept is None):
            return [
                PredicateFailure(
                    kind="consistency",
                    predicate="whole_line",
                    message="give both line_gradient and line_intercept, or neither",
                    parameters=["line_gradient", "line_intercept"],
                )
            ]
        return []

    def computed_values(self, params: CoordinateCircleParams) -> dict[str, str]:
        c = _Circle(params)
        values = {
            "centre": f"({format_value(c.a)}, {format_value(c.b)})",
            "radius": format_value(c.r),
            "equation": f"(x - {c.a})**2 + (y - {c.b})**2 = {c.r**2}",
            "expanded": f"{c.expanded} = 0",
        }
        if c.has_line:
            values["discriminant"] = format_value(c.discriminant)
            values["meets"] = str(len(c.meets))
            for i, (x, y) in enumerate(c.meets, start=1):
                values[f"meet_{i}"] = f"({format_value(x)}, {format_value(y)})"
        return values

    def build(self, params: CoordinateCircleParams, level):
        c = _Circle(params)
        a, b, r = (float(v) for v in (c.a, c.b, c.r))
        plot = make_plot(
            self.layout.region, [a - r - 1, a + r + 1], [b - r - 1, b + r + 1], equal=True
        )
        centre = plot.point(a, b)
        unit = plot.point(1, 0)[0] - plot.point(0, 0)[0]
        edge = plot.point(a + r, b)
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "equation": text_line(c.equation_latex(), plot.upper),
            "expanded": text_line(f"{tidy_latex(c.expanded)} = 0", plot.lower),
            "circle": Circle(radius=r * unit, color=style.CURVE_COLOUR).move_to(centre),
            "centre": Dot(centre, color=style.POINT_COLOUR),
            "radius": Line(centre, edge, color=style.RISE_COLOUR, stroke_width=4),
        }
        obstacles = [*plot.obstacles(), parts["centre"]]
        paths = [parts["circle"], parts["radius"], *plot.axis_lines()]
        if c.has_line:
            line = style.line_in_axes(
                plot.axes,
                (0.0, float(c.c)),
                float(c.m),
                plot.x_range,
                plot.y_range,
                color=style.TANGENT_COLOUR,
                stroke_width=4,
            )
            parts["line"] = line
            paths.append(line)
            parts["discriminant"] = text_line(c.discriminant_latex(), plot.lower, size=34)
            for i, (x, y) in enumerate(c.meets, start=1):
                parts[f"meet_{i}"] = Dot(plot.point(float(x), float(y)), color=style.POINT_COLOUR)
                obstacles.append(parts[f"meet_{i}"])
        labels = [
            (
                "centre_label",
                centre,
                rf"({latex_value(c.a)},\ {latex_value(c.b)})",
                style.POINT_COLOUR,
            ),
            ("radius_label", (centre + edge) / 2, f"r = {latex_value(c.r)}", style.RISE_COLOUR),
        ]
        if c.has_line:
            labels.append(
                (
                    "line_label",
                    line.get_end(),
                    f"y = {tidy_latex(c.m * X + c.c)}",
                    style.TANGENT_COLOUR,
                )
            )
            for i, (x, y) in enumerate(c.meets, start=1):
                labels.append(
                    (
                        f"meet_{i}_label",
                        plot.point(float(x), float(y)),
                        rf"({latex_value(x)},\ {latex_value(y)})",
                        style.POINT_COLOUR,
                    )
                )
        for name, anchor, tex, colour in labels:
            text = label(tex, colour=colour)
            parts[name] = place_label(text, anchor, plot.plot_box, obstacles, paths, wide=True)
            obstacles.append(text)
        return parts

    def stages(self, params: CoordinateCircleParams, level) -> list[Stage]:
        c = _Circle(params)
        steps = [
            stage(
                "axes",
                "Draw the axes, with one unit the same length on both",
                1.5,
                ["axes", "x_label", "y_label", "equation"],
            ),
            stage(
                "centre",
                "The equation gives the centre",
                2.0,
                ["centre", "centre_label"],
                emphasise=["centre"],
            ),
            stage(
                "circle",
                "and the radius: every point of the circle is r from the centre",
                2.5,
                ["circle", "radius", "radius_label"],
            ),
            stage("expanded", "Multiplied out, the equation takes this form", 2.5, ["expanded"]),
        ]
        if c.has_line:
            meets = [
                n for i in range(1, len(c.meets) + 1) for n in (f"meet_{i}", f"meet_{i}_label")
            ]
            verdict = {
                2: "the line cuts the circle twice",
                1: "the line is a tangent",
                0: "the line misses the circle",
            }[len(c.meets)]
            steps.append(stage("line", "Draw the line", 2.0, ["line", "line_label"]))
            steps.append(
                stage(
                    "meet",
                    f"Substitute the line into the circle: the discriminant says {verdict}",
                    3.5,
                    meets,
                    morph=[("expanded", "discriminant")],
                    emphasise=[m for m in meets if not m.endswith("label")],
                )
            )

        def standard(s):
            out = [combine("circle", "The centre and radius from the equation", 3.5, *s[:3]), s[3]]
            if c.has_line:
                out.append(combine("line", "Where the line meets the circle", 4.0, s[4], s[5]))
            return out

        def concise(s):
            out = [combine("circle", "The circle from its equation", 3.5, *s[:4])]
            if c.has_line:
                out.append(combine("line", "Where the line meets the circle", 4.0, s[4], s[5]))
            return out

        return by_level(level, steps, standard, concise)


class _Circle:
    def __init__(self, params: CoordinateCircleParams):
        self.a, self.b = (exact(v) for v in params.centre)
        self.r = exact(params.radius)
        self.expanded = sp.expand((X - self.a) ** 2 + (Y - self.b) ** 2 - self.r**2)
        self.has_line = params.line_gradient is not None
        self.meets = []
        if self.has_line:
            self.m, self.c = exact(params.line_gradient), exact(params.line_intercept)
            quadratic = sp.expand(self.expanded.subs(Y, self.m * X + self.c))
            # Whole-number coefficients with no common factor: x^2 + 6x + 9, not 25x^2/16 + ...
            _, primitive = sp.Poly(quadratic, X).primitive()
            if primitive.LC() < 0:
                primitive = -primitive
            quadratic = primitive.as_expr()
            self.quadratic = quadratic
            p = sp.Poly(quadratic, X)
            A, B, C = (p.coeff_monomial(X**k) for k in (2, 1, 0))
            self.discriminant = sp.nsimplify(B**2 - 4 * A * C)
            if self.discriminant >= 0:
                roots = sorted(set(sp.solve(quadratic, X)), key=float)
                self.meets = [(x, sp.nsimplify(self.m * x + self.c)) for x in roots]

    def equation_latex(self) -> str:
        def part(symbol, centre):
            if centre == 0:
                return f"{symbol}^2"
            return rf"\left({tidy_latex(sp.Symbol(symbol) - centre)}\right)^2"

        return f"{part('x', self.a)} + {part('y', self.b)} = {latex_value(self.r**2)}"

    def discriminant_latex(self) -> str:
        value = latex_value(self.discriminant)
        verdict = (
            "= 0"
            if self.discriminant == 0
            else (f"= {value} > 0" if self.discriminant > 0 else f"= {value} < 0")
        )
        return rf"{tidy_latex(self.quadratic)} = 0:\ b^2 - 4ac {verdict}"
