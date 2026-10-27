"""LineBuilder: the straight line y = mx + c built from its y-intercept and gradient, with the
form ax + by = c (4024 3.2, 3.3, 3.5; PRIMITIVES.md #24).

The line starts at the y-intercept (0, c); a step of the gradient ("q across, p up" for
m = p/q) gives a second point; the line passes through both. Where it crosses the x-axis is
marked, and the equation can be rearranged to ax + by = c with whole numbers. Every value is
computed exactly by SymPy.
"""

from typing import Annotated

import sympy as sp
from manim import Dot, Line
from pydantic import Field

from app.contracts import LayoutContract, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, make_plot, place_label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_value, latex_number, tidy_latex

X, Y = sp.symbols("x y", real=True)
Number = Annotated[float, Field(ge=-20, le=20)]


class LineBuilderParams(PrimitiveParams):
    gradient: Number = Field(description="m in y = mx + c")
    intercept: Number = Field(description="c in y = mx + c")
    general_form: bool = Field(default=False, description="Also rearrange to ax + by = c")


class LineBuilder(StagedPrimitive[LineBuilderParams]):
    primitive_id = "LineBuilder"
    version = "1"
    topic = "Coordinate geometry"
    params_model = LineBuilderParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("axes", "*"),
            ("line", "*"),
            ("run", "*"),
            ("rise", "*"),
            ("point_*", "point_*"),
        ],
    )

    def default_params(self) -> LineBuilderParams:
        return LineBuilderParams(gradient=2, intercept=-1, general_form=True)

    def validate(self, params: LineBuilderParams):
        return []

    def computed_values(self, params: LineBuilderParams) -> dict[str, str]:
        m, c = exact(params.gradient), exact(params.intercept)
        run, rise = _step(m)
        values = {
            "gradient": format_value(m),
            "intercept": format_value(c),
            "equation": f"y = {m * X + c}",
            "run": format_value(run),
            "rise": format_value(rise),
            "general_form": _general(m, c),
        }
        if m != 0:
            values["x_intercept"] = format_value(-c / m)
        return values

    def build(self, params: LineBuilderParams, level):
        m, c = exact(params.gradient), exact(params.intercept)
        run, rise = _step(m)
        xs = [-1.0, float(run) + 1]
        if m != 0:
            xs.append(float(-c / m))
        x_lo, x_hi = min(xs) - 0.5, max(xs) + 0.5
        ys = [float(c), float(c + rise), float(m * x_lo + c), float(m * x_hi + c)]
        plot = make_plot(self.layout.region, [x_lo, x_hi], ys)
        start = plot.point(0, float(c))
        corner = plot.point(float(run), float(c))
        end = plot.point(float(run), float(c + rise))
        line = style.line_in_axes(
            plot.axes,
            (0.0, float(c)),
            float(m),
            plot.x_range,
            plot.y_range,
            color=style.CURVE_COLOUR,
            stroke_width=5,
        )
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "equation": text_line(f"y = {tidy_latex(m * X + c)}", plot.upper),
            "meaning": text_line(
                rf"\text{{gradient }} m = {latex_number(m)},\ "
                rf"y\text{{-intercept }} c = {latex_number(c)}",
                plot.lower,
            ),
            "general": text_line(_general_latex(m, c), plot.lower),
            "point_intercept": Dot(start, color=style.POINT_COLOUR),
            "point_step": Dot(end, color=style.POINT_COLOUR),
            "line": line,
        }
        obstacles = [*plot.obstacles(), parts["point_intercept"], parts["point_step"]]
        paths = [line, *plot.axis_lines()]
        if m != 0:
            parts["run"] = Line(start, corner, color=style.RUN_COLOUR, stroke_width=5)
            parts["rise"] = Line(corner, end, color=style.RISE_COLOUR, stroke_width=5)
            paths += [parts["run"], parts["rise"]]
            x0 = -c / m
            parts["point_x_intercept"] = Dot(plot.point(float(x0), 0), color=style.TANGENT_COLOUR)
            obstacles.append(parts["point_x_intercept"])
        else:
            parts["run"] = Line(start, corner, color=style.RUN_COLOUR, stroke_width=5)
            paths.append(parts["run"])
        labels = [
            ("point_intercept_label", start, rf"(0,\ {latex_number(c)})", style.POINT_COLOUR),
            ("run_label", (start + corner) / 2, latex_number(run), style.RUN_COLOUR),
        ]
        if m != 0:
            labels += [
                ("rise_label", (corner + end) / 2, latex_number(rise), style.RISE_COLOUR),
                (
                    "point_x_intercept_label",
                    plot.point(float(-c / m), 0),
                    rf"({latex_number(-c / m)},\ 0)",
                    style.TANGENT_COLOUR,
                ),
            ]
        for name, anchor, tex, colour in labels:
            text = label(tex, colour=colour)
            parts[name] = place_label(text, anchor, plot.plot_box, obstacles, paths, wide=True)
            obstacles.append(text)
        return parts

    def stages(self, params: LineBuilderParams, level) -> list[Stage]:
        m = exact(params.gradient)
        run, rise = _step(m)
        step_words = (
            "The gradient is 0, so the line is flat: across, never up"
            if m == 0
            else f"Use the gradient: {format_value(run)} across, then "
            f"{format_value(abs(rise))} {'up' if rise > 0 else 'down'}"
        )
        step_parts = ["run", "run_label"] + ([] if m == 0 else ["rise", "rise_label"])
        steps = [
            stage("axes", "Draw the axes", 1.5, ["axes", "x_label", "y_label"]),
            stage(
                "equation",
                "Read the gradient and the y-intercept from the equation",
                2.5,
                ["equation", "meaning"],
            ),
            stage(
                "intercept",
                "Start at the y-intercept, on the y-axis",
                2.0,
                ["point_intercept", "point_intercept_label"],
                emphasise=["point_intercept"],
            ),
            stage("step", step_words, 2.5, [*step_parts, "point_step"], emphasise=["point_step"]),
            stage("line", "Draw the line through the two points", 2.0, ["line"]),
        ]
        if m != 0 and exact(params.intercept) != 0:  # through the origin: already marked
            steps.append(
                stage(
                    "x_intercept",
                    "It crosses the x-axis where y = 0",
                    2.0,
                    ["point_x_intercept", "point_x_intercept_label"],
                )
            )
        if params.general_form:
            steps.append(
                stage(
                    "general",
                    "Rearrange to the form a x plus b y equals c",
                    2.5,
                    morph=[("meaning", "general")],
                    emphasise=["general"],
                )
            )

        def standard(s):
            out = [
                combine("setup", "Read m and c and draw the axes", 3.0, s[0], s[1]),
                combine(
                    "draw",
                    "Start at the y-intercept, step by the gradient and draw the line",
                    3.5,
                    s[2],
                    s[3],
                    s[4],
                ),
            ]
            return out + s[5:]

        def concise(s):
            out = [combine("line", "Draw the line from its gradient and y-intercept", 3.5, *s[:5])]
            if len(s) > 5:
                out.append(combine("more", "Its x-intercept and other form", 3.0, *s[5:]))
            return out

        return by_level(level, steps, standard, concise)


def _step(m: sp.Rational) -> tuple[sp.Expr, sp.Expr]:
    """'q across, p up' for m = p/q; 1 across for a whole number gradient."""
    m = sp.nsimplify(m)
    if m == 0:
        return sp.Integer(2), sp.Integer(0)
    if isinstance(m, sp.Rational) and m.q <= 6:
        return sp.Integer(m.q), sp.Integer(m.p)
    return sp.Integer(1), m


def _integer_form(m, c):
    """a, b, k with ax + by = k, whole numbers, a > 0 (or b > 0 if a = 0)."""
    a, b, k = -m, sp.Integer(1), c
    denominators = [sp.fraction(sp.nsimplify(v))[1] for v in (a, b, k)]
    scale = sp.ilcm(*denominators)
    a, b, k = a * scale, b * scale, k * scale
    divisor = sp.igcd(sp.igcd(int(a), int(b)), int(k)) or 1
    a, b, k = a / divisor, b / divisor, k / divisor
    if a < 0 or (a == 0 and b < 0):
        a, b, k = -a, -b, -k
    return a, b, k


def _general(m, c) -> str:
    a, b, k = _integer_form(m, c)
    return f"{a * X + b * Y} = {k}"


def _general_latex(m, c) -> str:
    a, b, k = _integer_form(m, c)
    return f"{tidy_latex(a * X + b * Y)} = {latex_number(k)}"
