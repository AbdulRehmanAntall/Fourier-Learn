"""ParallelPerpendicular: the line through a point parallel or perpendicular to a given line,
and the perpendicular bisector of a segment (4024 3.6, 3.7; AM 7.2, 7.3; PRIMITIVES.md #25).

Parallel lines share a gradient; perpendicular gradients multiply to -1, so the new gradient is
the negative reciprocal ("flip and change sign"). The perpendicular bisector of AB passes through
the midpoint of AB at right angles to it. One unit is the same length on both axes, so right
angles look right. A perpendicular to a horizontal line is vertical (x = a), and the other way
round. Every value is computed exactly by SymPy.
"""

from typing import Annotated, Literal

import sympy as sp
from manim import Dot, Line
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import angle_mark, label, make_plot, place_label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_value, latex_number, tidy_latex

X = sp.Symbol("x", real=True)
Number = Annotated[float, Field(ge=-20, le=20)]
Point = tuple[Number, Number]


class ParallelPerpendicularParams(PrimitiveParams):
    mode: Literal["parallel", "perpendicular", "bisector"]
    gradient: Number | None = Field(default=None, description="Given line y = mx + c: m")
    intercept: Number | None = Field(default=None, description="Given line y = mx + c: c")
    point: Point | None = Field(default=None, description="The new line passes through it")
    point_a: Point | None = Field(default=None, description="Bisector mode: one end of AB")
    point_b: Point | None = Field(default=None, description="Bisector mode: the other end")


class ParallelPerpendicular(StagedPrimitive[ParallelPerpendicularParams]):
    primitive_id = "ParallelPerpendicular"
    version = "1"
    topic = "Coordinate geometry"
    params_model = ParallelPerpendicularParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("axes", "*"),
            ("given", "*"),
            ("new", "*"),
            ("right_angle", "*"),
            ("point_*", "point_*"),
            ("segment", "*"),
        ],
    )

    def default_params(self) -> ParallelPerpendicularParams:
        return ParallelPerpendicularParams(
            mode="perpendicular", gradient=2, intercept=1, point=(4, 1)
        )

    def validate(self, params: ParallelPerpendicularParams) -> list[PredicateFailure]:
        if params.mode == "bisector":
            if params.point_a is None or params.point_b is None:
                return [
                    _failure(
                        "needs_two_points",
                        "bisector mode needs point_a and point_b",
                        "point_a",
                        "point_b",
                    )
                ]
            if tuple(params.point_a) == tuple(params.point_b):
                return [_failure("distinct_points", "A and B are the same point", "point_b")]
            return []
        missing = [n for n in ("gradient", "intercept", "point") if getattr(params, n) is None]
        if missing:
            message = f"{params.mode} mode needs {', '.join(missing)}"
            return [_failure("needs_line_and_point", message, *missing)]
        return []

    def computed_values(self, params: ParallelPerpendicularParams) -> dict[str, str]:
        g = _Geometry(params)
        values = {"new_line": g.new_text()}
        if g.new_m is not None:
            values["new_gradient"] = format_value(g.new_m)
        if params.mode == "bisector":
            values["midpoint"] = f"({format_value(g.px)}, {format_value(g.py)})"
            values["gradient_ab"] = "undefined" if g.given_m is None else format_value(g.given_m)
        else:
            values["given_gradient"] = format_value(g.given_m)
        return values

    def build(self, params: ParallelPerpendicularParams, level):
        g = _Geometry(params)
        xs, ys = g.extent()
        plot = make_plot(self.layout.region, xs, ys, equal=True)
        given = _line(plot, g.given_m, g.given_through, style.CURVE_COLOUR)
        new = _line(plot, g.new_m, (g.px, g.py), style.TANGENT_COLOUR)
        p = plot.point(float(g.px), float(g.py))
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "given": given,
            "new": new,
            "point_p": Dot(p, color=style.POINT_COLOUR),
            "question": text_line(g.question_latex(), plot.upper),
            "gradient": text_line(g.gradient_latex(), plot.lower),
            "answer": text_line(g.answer_latex(), plot.lower),
        }
        obstacles = [*plot.obstacles(), parts["point_p"]]
        paths = [given, new, *plot.axis_lines()]
        if params.mode == "bisector":
            a = plot.point(*(float(v) for v in g.a))
            b = plot.point(*(float(v) for v in g.b))
            parts["segment"] = Line(a, b, color=style.CURVE_COLOUR, stroke_width=5)
            parts["point_a"] = Dot(a, color=style.POINT_COLOUR)
            parts["point_b"] = Dot(b, color=style.POINT_COLOUR)
            obstacles += [parts["point_a"], parts["point_b"]]
            for name, anchor, tex in (("point_a_label", a, "A"), ("point_b_label", b, "B")):
                text = label(tex, colour=style.POINT_COLOUR, size=style.FONT_SIZE)
                parts[name] = place_label(text, anchor, plot.plot_box, obstacles, paths, wide=True)
                obstacles.append(text)
        if params.mode != "parallel":
            meet = g.foot()
            corner = plot.point(*(float(v) for v in meet))
            along_given = plot.point(*(float(v) for v in g.along(meet, given_line=True)))
            along_new = plot.point(*(float(v) for v in g.along(meet, given_line=False)))
            parts["right_angle"] = angle_mark(
                corner, along_given, along_new, radius=0.3, colour=style.TEXT_COLOUR
            )
        name_p = "M" if params.mode == "bisector" else "P"
        text = label(
            rf"{name_p}({latex_number(g.px)},\ {latex_number(g.py)})", colour=style.POINT_COLOUR
        )
        parts["point_p_label"] = place_label(text, p, plot.plot_box, obstacles, paths, wide=True)
        obstacles.append(text)
        if params.mode != "bisector":
            text = label(g.given_equation_latex(), colour=style.CURVE_COLOUR)
            anchor = plot.point(*(float(v) for v in g.given_through))
            parts["given_label"] = place_label(
                text, anchor, plot.plot_box, obstacles, paths, wide=True
            )
        return parts

    def stages(self, params: ParallelPerpendicularParams, level) -> list[Stage]:
        mode = params.mode
        gradient_words = {
            "parallel": "Parallel lines have the same gradient",
            "perpendicular": "Perpendicular gradients multiply to minus 1: flip the gradient and "
            "change its sign",
            "bisector": "Find the gradient of AB; the bisector's gradient is its negative "
            "reciprocal",
        }[mode]
        if mode == "bisector":
            first = [
                stage("axes", "Draw the axes", 1.5, ["axes", "x_label", "y_label", "question"]),
                stage(
                    "segment",
                    "Plot A and B and join them",
                    2.0,
                    ["point_a", "point_b", "point_a_label", "point_b_label", "segment"],
                ),
                stage(
                    "midpoint",
                    "The bisector passes through the midpoint M of AB",
                    2.5,
                    ["point_p", "point_p_label"],
                    emphasise=["point_p"],
                ),
            ]
        else:
            first = [
                stage("axes", "Draw the axes", 1.5, ["axes", "x_label", "y_label", "question"]),
                stage("given", "Draw the given line", 2.0, ["given", "given_label"]),
                stage(
                    "point",
                    "Mark the point the new line must pass through",
                    2.0,
                    ["point_p", "point_p_label"],
                    emphasise=["point_p"],
                ),
            ]
        gradient = stage("gradient", gradient_words, 3.0, ["gradient"], emphasise=["gradient"])
        draw = ["new"] + (["right_angle"] if mode != "parallel" else [])
        new = stage("new", "Draw the new line through the point", 2.0, draw)
        answer = stage(
            "answer",
            "Use y minus y1 equals m times x minus x1 for its equation",
            3.0,
            morph=[("gradient", "answer")],
            emphasise=["answer"],
        )
        steps = [*first, gradient, new, answer]

        def standard(s):
            return [
                combine("setup", "Draw the axes and what is given", 3.0, *s[:3]),
                s[3],
                combine("new", "Draw the new line and find its equation", 3.5, s[4], s[5]),
            ]

        def concise(s):
            return [
                combine("setup", "Draw what is given", 3.0, *s[:3]),
                combine(
                    "new", "Find the gradient, draw the line and write its equation", 4.0, *s[3:]
                ),
            ]

        return by_level(level, steps, standard, concise)


class _Geometry:
    """The given line (or AB), the point P (or midpoint M) and the new line, exactly. A gradient
    of None means a vertical line."""

    def __init__(self, params: ParallelPerpendicularParams):
        self.mode = params.mode
        if params.mode == "bisector":
            self.a = tuple(exact(v) for v in params.point_a)
            self.b = tuple(exact(v) for v in params.point_b)
            (x1, y1), (x2, y2) = self.a, self.b
            self.given_m = None if x1 == x2 else (y2 - y1) / (x2 - x1)
            self.given_through = self.a
            self.px, self.py = (x1 + x2) / 2, (y1 + y2) / 2
            self.c = None
        else:
            self.given_m = exact(params.gradient)
            self.c = exact(params.intercept)
            self.given_through = (sp.Integer(0), self.c)
            self.px, self.py = (exact(v) for v in params.point)
        if params.mode == "parallel":
            self.new_m = self.given_m
        elif self.given_m is None:
            self.new_m = sp.Integer(0)
        elif self.given_m == 0:
            self.new_m = None
        else:
            self.new_m = -1 / self.given_m

    def new_equation(self):
        if self.new_m is None:
            return None
        return self.new_m * (X - self.px) + self.py

    def new_text(self) -> str:
        expr = self.new_equation()
        return f"x = {self.px}" if expr is None else f"y = {sp.expand(expr)}"

    def foot(self) -> tuple:
        """Where the new line meets the given line (or AB)."""
        if self.mode == "bisector":
            return self.px, self.py
        m, c = self.given_m, self.c
        if self.new_m is None:
            return self.px, m * self.px + c
        if m == 0 and self.new_m is None:
            return self.px, c
        x = sp.solve(sp.Eq(m * X + c, self.new_equation()), X)[0]
        return x, m * x + c

    def along(self, point, given_line: bool) -> tuple:
        """A point one unit along a line from `point`, for the right-angle mark."""
        m = self.given_m if given_line else self.new_m
        x, y = point
        if m is None:
            return x, y + 1
        step = 1 / sp.sqrt(1 + m**2)
        return x + step, y + m * step

    def extent(self):
        points = [(self.px, self.py), self.given_through]
        if self.mode == "bisector":
            points += [self.a, self.b]
        elif self.mode == "perpendicular":
            points.append(self.foot())  # parallel lines never meet
        xs = [float(x) for x, _ in points]
        ys = [float(y) for _, y in points]
        return [min(xs) - 2, max(xs) + 2], [min(ys) - 2, max(ys) + 2]

    def given_equation_latex(self) -> str:
        return f"y = {tidy_latex(self.given_m * X + self.c)}"

    def question_latex(self) -> str:
        if self.mode == "bisector":
            (x1, y1), (x2, y2) = self.a, self.b
            return (
                rf"\text{{bisector of }} A({latex_number(x1)},\ {latex_number(y1)}),\ "
                rf"B({latex_number(x2)},\ {latex_number(y2)})"
            )
        word = "parallel" if self.mode == "parallel" else "perpendicular"
        return (
            rf"\text{{{word} to }} {self.given_equation_latex()} \text{{ through }} "
            rf"({latex_number(self.px)},\ {latex_number(self.py)})"
        )

    def gradient_latex(self) -> str:
        given = r"\infty" if self.given_m is None else latex_number(self.given_m)
        if self.mode == "parallel":
            return rf"m = {given}"
        if self.given_m is None:
            return r"AB \text{ is vertical, so the bisector is horizontal: } m = 0"
        if self.new_m is None:
            return r"m_1 = 0 \text{, so the new line is vertical}"
        return rf"m_1 = {given},\ m_2 = -\tfrac{{1}}{{m_1}} = {latex_number(self.new_m)}"

    def answer_latex(self) -> str:
        if self.new_m is None:
            return f"x = {latex_number(self.px)}"
        return f"y = {tidy_latex(sp.expand(self.new_equation()))}"


def _line(plot, m, through, colour) -> Line:
    x0, y0 = (float(v) for v in through)
    if m is None:
        return Line(
            plot.point(x0, plot.y_range[0]),
            plot.point(x0, plot.y_range[1]),
            color=colour,
            stroke_width=5,
        )
    return style.line_in_axes(
        plot.axes, (x0, y0), float(m), plot.x_range, plot.y_range, color=colour, stroke_width=5
    )


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
