"""CoordinatePlotter: two points on a grid, the midpoint of the segment joining them, and its
length from the right-angled triangle under it (4024 3.1, 3.4, links 6.1; PRIMITIVES.md #23).

The midpoint is the mean of the coordinates; the length is Pythagoras on the horizontal and
vertical sides of the triangle. One unit is the same length on both axes, so the triangle is a
true right-angled triangle. Every value is computed exactly by SymPy; a length that is a surd is
shown exactly and to 3 significant figures.
"""

from typing import Annotated, Literal

import sympy as sp
from manim import DashedLine, Dot, Line
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import angle_mark, label, make_plot, place_label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_value, latex_approx, latex_number

Coordinate = Annotated[float, Field(ge=-20, le=20)]


class CoordinatePlotterParams(PrimitiveParams):
    point_a: tuple[Coordinate, Coordinate]
    point_b: tuple[Coordinate, Coordinate]
    show: list[Literal["midpoint", "length"]] = Field(
        default=["midpoint", "length"], min_length=1, max_length=2
    )


class CoordinatePlotter(StagedPrimitive[CoordinatePlotterParams]):
    primitive_id = "CoordinatePlotter"
    version = "1"
    topic = "Coordinate geometry"
    params_model = CoordinatePlotterParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("axes", "*"),
            ("segment", "*"),
            ("point_*", "point_*"),
            ("across", "*"),
            ("up", "*"),
            ("right_angle", "*"),
            ("midpoint", "segment"),
        ],
    )

    def default_params(self) -> CoordinatePlotterParams:
        return CoordinatePlotterParams(point_a=(1, 2), point_b=(4, 8))

    def validate(self, params: CoordinatePlotterParams) -> list[PredicateFailure]:
        if tuple(params.point_a) == tuple(params.point_b):
            return [
                PredicateFailure(
                    kind="consistency",
                    predicate="distinct_points",
                    message="A and B are the same point",
                    parameters=["point_a", "point_b"],
                )
            ]
        return []

    def computed_values(self, params: CoordinatePlotterParams) -> dict[str, str]:
        (x1, y1), (x2, y2) = _points(params)
        return {
            "midpoint": f"({format_value((x1 + x2) / 2)}, {format_value((y1 + y2) / 2)})",
            "across": format_value(abs(x2 - x1)),
            "up": format_value(abs(y2 - y1)),
            "length": format_value(sp.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)),
            "length_squared": format_value((x2 - x1) ** 2 + (y2 - y1) ** 2),
        }

    def build(self, params: CoordinatePlotterParams, level):
        (x1, y1), (x2, y2) = _points(params)
        plot = make_plot(self.layout.region, [x1, x2], [y1, y2], equal=True)
        a, b = plot.point(float(x1), float(y1)), plot.point(float(x2), float(y2))
        corner = plot.point(float(x2), float(y1))
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        dx, dy = x2 - x1, y2 - y1
        length = sp.sqrt(dx**2 + dy**2)
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "points": text_line(
                rf"A({latex_number(x1)},\ {latex_number(y1)}),\ "
                rf"B({latex_number(x2)},\ {latex_number(y2)})",
                plot.upper,
            ),
            "point_a": Dot(a, color=style.POINT_COLOUR),
            "point_b": Dot(b, color=style.POINT_COLOUR),
            "segment": Line(a, b, color=style.CURVE_COLOUR, stroke_width=5),
            "midpoint": Dot(plot.point(float(mx), float(my)), color=style.TANGENT_COLOUR),
            "midpoint_formula": text_line(
                rf"M = \left(\tfrac{{{latex_number(x1)} + {_paren(x2)}}}{{2}},\ "
                rf"\tfrac{{{latex_number(y1)} + {_paren(y2)}}}{{2}}\right) = "
                rf"\left({latex_number(mx)},\ {latex_number(my)}\right)",
                plot.lower,
            ),
            "length_formula": text_line(
                rf"AB = \sqrt{{{_paren(abs(dx))}^2 + {_paren(abs(dy))}^2}} = "
                rf"{latex_approx(length)}",
                plot.lower,
            ),
        }
        obstacles = [*plot.obstacles(), parts["point_a"], parts["point_b"], parts["midpoint"]]
        paths = [parts["segment"], *plot.axis_lines()]
        if dx != 0 and dy != 0:
            parts["across"] = DashedLine(a, corner, color=style.RUN_COLOUR, stroke_width=4)
            parts["up"] = DashedLine(corner, b, color=style.RISE_COLOUR, stroke_width=4)
            parts["right_angle"] = angle_mark(corner, a, b, radius=0.3, colour=style.TEXT_COLOUR)
            paths += [parts["across"], parts["up"]]
        for name, anchor, tex, colour in (
            ("point_a_label", a, "A", style.POINT_COLOUR),
            ("point_b_label", b, "B", style.POINT_COLOUR),
            ("midpoint_label", plot.point(float(mx), float(my)), "M", style.TANGENT_COLOUR),
        ):
            text = label(tex, colour=colour, size=style.FONT_SIZE)
            parts[name] = place_label(text, anchor, plot.plot_box, obstacles, paths, wide=True)
            obstacles.append(text)
        if dx != 0 and dy != 0:
            for name, start, end, value, colour in (
                ("across_label", a, corner, abs(dx), style.RUN_COLOUR),
                ("up_label", corner, b, abs(dy), style.RISE_COLOUR),
            ):
                text = label(latex_number(value), colour=colour)
                anchor = (start + end) / 2
                parts[name] = place_label(text, anchor, plot.plot_box, obstacles, paths, wide=True)
                obstacles.append(text)
        return parts

    def stages(self, params: CoordinatePlotterParams, level) -> list[Stage]:
        (x1, y1), (x2, y2) = _points(params)
        slanted = x1 != x2 and y1 != y2
        steps = [
            stage(
                "axes",
                "Draw the axes, with one unit the same length on both",
                1.5,
                ["axes", "x_label", "y_label", "points"],
            ),
            stage(
                "point_a",
                "Plot A: across first, then up",
                2.0,
                ["point_a", "point_a_label"],
                emphasise=["point_a"],
            ),
            stage(
                "point_b",
                "Plot B the same way",
                1.5,
                ["point_b", "point_b_label"],
                emphasise=["point_b"],
            ),
            stage("segment", "Join A and B", 1.5, ["segment"]),
        ]
        if "midpoint" in params.show:
            steps.append(
                stage(
                    "midpoint",
                    "The midpoint M is halfway: average the x's and the y's",
                    3.0,
                    ["midpoint", "midpoint_label", "midpoint_formula"],
                    emphasise=["midpoint"],
                )
            )
        if "length" in params.show:
            if slanted:
                steps.append(
                    stage(
                        "triangle",
                        "Draw the right-angled triangle under AB",
                        2.5,
                        ["across", "up", "right_angle", "across_label", "up_label"],
                    )
                )
            morph = [("midpoint_formula", "length_formula")] if "midpoint" in params.show else []
            show = [] if morph else ["length_formula"]
            steps.append(
                stage(
                    "length",
                    "Pythagoras gives the length of AB",
                    3.0,
                    show,
                    morph=morph,
                    emphasise=["length_formula"],
                )
            )

        def standard(s):
            out = [combine("points", "Plot A and B and join them", 3.0, *s[:4])]
            return out + s[4:]

        def concise(s):
            rest = s[4:]
            out = [combine("points", "Plot A and B and join them", 3.0, *s[:4])]
            if len(rest) > 1:
                out.append(combine("results", "Find the midpoint and the length", 4.0, *rest))
            else:
                out += rest
            return out

        return by_level(level, steps, standard, concise)


def _points(params: CoordinatePlotterParams):
    return [tuple(exact(v) for v in params.point_a), tuple(exact(v) for v in params.point_b)]


def _paren(value: sp.Expr) -> str:
    tex = latex_number(value)
    return rf"\left({tex}\right)" if value < 0 or "frac" in tex else tex
