"""CompletingSquare: completing the square seen as an area (4024 2.5.5; AM 2.1; PRIMITIVES.md
#14, the geometric view).

x² is a square of side x and bx a rectangle of sides x and b. The rectangle is cut in half and
the halves are placed on two sides of the square, which leaves a missing corner of (b/2)². So
x² + bx = (x + b/2)² - (b/2)², and adding c gives the completed-square form. The area picture
needs b > 0; the algebra on screen is computed by SymPy for any c.
"""

from typing import Annotated

import numpy as np
import sympy as sp
from manim import DashedVMobject, MathTex, Polygon, Rectangle, Square
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import inline, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_number, latex_number, tidy_latex

X = sp.Symbol("x", real=True)
Coefficient = Annotated[float, Field(ge=-100, le=100)]


class CompletingSquareParams(PrimitiveParams):
    b: Coefficient = Field(description="The coefficient of x in x² + bx + c; must be positive")
    c: Coefficient = Field(default=0, description="The constant term")


class CompletingSquare(StagedPrimitive[CompletingSquareParams]):
    primitive_id = "CompletingSquare"
    version = "1"
    topic = "Algebra and graphs"
    params_model = CompletingSquareParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("square", "*_label"),
            ("strip_*", "*_label"),
            ("corner", "corner_label"),
            ("corner", "strip_*"),
            ("corner", "square"),
            ("strip_*", "square"),
            ("strip_*", "strip_*"),
            ("outline", "*"),
            ("rectangle", "rectangle_label"),
        ],
    )

    def default_params(self) -> CompletingSquareParams:
        return CompletingSquareParams(b=6, c=5)

    def validate(self, params: CompletingSquareParams) -> list[PredicateFailure]:
        if params.b <= 0:
            message = (
                "the area picture needs b > 0; use QuadraticExplorer or AlgebraBalance for b <= 0"
            )
            return [
                PredicateFailure(
                    kind="consistency", predicate="b_positive", message=message, parameters=["b"]
                )
            ]
        return []

    def computed_values(self, params: CompletingSquareParams) -> dict[str, str]:
        b, c = exact(params.b), exact(params.c)
        half = b / 2
        return {
            "half_b": format_number(half),
            "corner": format_number(half**2),
            "constant": format_number(c - half**2),
            "completed": str((X + half) ** 2 + c - half**2),
            "vertex": f"({format_number(-half)}, {format_number(c - half**2)})",
        }

    def build(self, params: CompletingSquareParams, level):
        b, c = exact(params.b), exact(params.c)
        half = b / 2
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        quadratic = X**2 + b * X + c
        parts = {
            "expression": text_line(tidy_latex(quadratic), upper),
            "identity": text_line(
                rf"x^2 + {latex_number(b)}x = \left(x + {latex_number(half)}\right)^2 - "
                rf"{_bracket(half**2)}",
                lower,
            ),
            "result": text_line(
                rf"{tidy_latex(quadratic)} = \left(x + {latex_number(half)}\right)^2 "
                rf"{_signed(c - half**2)}",
                lower,
            ),
        }

        # The square is drawn with side 3 units; b/2 is drawn shorter or longer, but never to
        # scale, since x is unknown.
        side = 3.0
        strip = min(max(1.0, float(half) / 2), 2.0)
        # Room: a label left of the square and the whole rectangle beside it; a label above and
        # below.
        scale = min(
            (area.width - 1.2) / (side + 2 * strip + 0.3), (area.height - 1.5) / (side + strip), 1.2
        )
        side, strip = side * scale, strip * scale
        width = side + 2 * strip + 0.3
        # Top-left corner of the square, with room above it for the side labels.
        origin = np.array([area.center[0] - width / 2 + 0.2, area.top - 0.7, 0.0])

        def at(x: float, y: float):
            return origin + [x, -y, 0]

        square = Square(side, color=style.CURVE_COLOUR, fill_opacity=0.35)
        square.move_to(at(side / 2, side / 2))
        parts["square"] = square
        parts["square_label"] = MathTex("x^2", font_size=style.FONT_SIZE).move_to(square)
        parts["top_label"] = MathTex("x", font_size=style.LABEL_FONT_SIZE).next_to(
            square, [0, 1, 0], buff=0.15
        )
        parts["left_label"] = MathTex("x", font_size=style.LABEL_FONT_SIZE).next_to(
            square, [-1, 0, 0], buff=0.15
        )

        # The rectangle bx, first whole beside the square, then cut into two strips.
        whole = Rectangle(width=2 * strip, height=side, color=style.RISE_COLOUR, fill_opacity=0.35)
        whole.move_to(at(side + strip + 0.3, side / 2))
        parts["rectangle"] = whole
        parts["rectangle_label"] = MathTex(
            rf"{latex_number(b)}x", font_size=style.LABEL_FONT_SIZE
        ).move_to(whole)
        right = Rectangle(width=strip, height=side, color=style.RISE_COLOUR, fill_opacity=0.35)
        right.move_to(at(side + strip / 2, side / 2))
        bottom = Rectangle(width=side, height=strip, color=style.RUN_COLOUR, fill_opacity=0.35)
        bottom.move_to(at(side / 2, side + strip / 2))
        parts["strip_right"] = right
        parts["strip_bottom"] = bottom
        half_tex = inline(latex_number(half))
        parts["strip_right_label"] = _fit(MathTex(rf"{half_tex}x", font_size=30), right)
        parts["strip_bottom_label"] = _fit(MathTex(rf"{half_tex}x", font_size=30), bottom)
        parts["half_label"] = MathTex(half_tex, font_size=style.LABEL_FONT_SIZE).next_to(
            right, [0, 1, 0], buff=0.15
        )

        corner = Polygon(
            at(side, side),
            at(side + strip, side),
            at(side + strip, side + strip),
            at(side, side + strip),
            color=style.HIGHLIGHT_COLOUR,
            fill_opacity=0.2,
        )
        parts["corner"] = DashedVMobject(corner, num_dashes=24)
        parts["corner_label"] = _fit(
            MathTex(inline(latex_number(half**2)), font_size=30, color=style.HIGHLIGHT_COLOUR),
            corner,
        )
        outline = Square(side + strip, color=style.HIGHLIGHT_COLOUR, stroke_width=5)
        outline.move_to(at((side + strip) / 2, (side + strip) / 2))
        parts["outline"] = outline
        parts["outline_label"] = MathTex(
            rf"x + {half_tex}", font_size=style.LABEL_FONT_SIZE, color=style.HIGHLIGHT_COLOUR
        ).next_to(outline, [0, -1, 0], buff=0.15)
        return parts

    def stages(self, params: CompletingSquareParams, level) -> list[Stage]:
        expression = stage("expression", "Show the expression", 1.5, ["expression"])
        square = stage(
            "square",
            "x squared is a square of side x",
            2.0,
            ["square", "square_label", "top_label", "left_label"],
            emphasise=["square"],
        )
        rectangle = stage(
            "rectangle", "b x is a rectangle, x by b", 2.0, ["rectangle", "rectangle_label"]
        )
        cut = stage(
            "cut",
            "Cut the rectangle in half and put one half on each side of the square",
            3.0,
            [
                "strip_right",
                "strip_bottom",
                "strip_right_label",
                "strip_bottom_label",
                "half_label",
            ],
            hide=["rectangle", "rectangle_label"],
        )
        corner = stage(
            "corner",
            "A corner is missing; its area is half of b, squared",
            2.5,
            ["corner", "corner_label"],
            emphasise=["corner_label"],
        )
        big = stage(
            "big_square",
            "With the corner the shape is a square of side x plus half of b, so subtract the "
            "corner",
            3.0,
            ["outline", "outline_label", "identity"],
            emphasise=["outline"],
        )
        result = stage(
            "result", "Add c to get the completed square form", 2.5, morph=[("identity", "result")]
        )
        steps = [expression, square, rectangle, cut, corner, big, result]

        def standard(s):
            return [
                combine(
                    "pieces", "x squared is a square, and b x a rectangle", 2.5, s[0], s[1], s[2]
                ),
                s[3],
                combine(
                    "complete",
                    "The missing corner completes a bigger square, so subtract it",
                    3.5,
                    s[4],
                    s[5],
                ),
                s[6],
            ]

        def concise(s):
            return [
                combine(
                    "pieces",
                    "Show x squared plus b x as a square and two strips",
                    3.0,
                    s[0],
                    s[1],
                    s[2],
                    s[3],
                ),
                combine(
                    "complete",
                    "Complete the square and write the completed form",
                    3.5,
                    s[4],
                    s[5],
                    s[6],
                ),
            ]

        return by_level(level, steps, standard, concise)


def _fit(label, shape):
    box = style.Box(
        shape.get_left()[0] + 0.08,
        shape.get_right()[0] - 0.08,
        shape.get_bottom()[1] + 0.08,
        shape.get_top()[1] - 0.08,
    )
    return style.fit_inside(label, box)


def _bracket(value: sp.Expr) -> str:
    tex = latex_number(value)
    return rf"\left({tex}\right)" if "frac" in tex else tex


def _signed(value: sp.Expr) -> str:
    if value == 0:
        return ""
    tex = latex_number(abs(value))
    return f"- {tex}" if value < 0 else f"+ {tex}"
