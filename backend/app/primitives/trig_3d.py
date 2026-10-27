"""Trig3D: lengths and angles in three dimensions, found from right-angled triangles inside the
solid: the space diagonal of a cuboid and its angle with the base, or the slant edge of a
square-based pyramid and its angle with the base (4024 6.4; PRIMITIVES.md #40).

The angle between a line and a plane is the angle between the line and its shadow on the
plane, so the working first finds the shadow (a diagonal of the base, by Pythagoras), then the
line, then the angle with tan. Lengths to 3 s.f., angles to 1 d.p.
"""

from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import DashedLine, DoubleArrow, Line, Polygon, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import Diagram, angle_mark, label, split_columns, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf, latex_approx

Length = Annotated[float, Field(gt=0, le=100)]
DEPTH = (0.55, 0.35)  # where one unit of depth goes on the page


class Trig3DParams(PrimitiveParams):
    solid: Literal["cuboid", "pyramid"]
    length: Length = Field(description="AB")
    width: Length = Field(description="BC (a pyramid's base is square: width is ignored)")
    height: Length = Field(description="The height (of the apex above the base's centre)")
    unit: Literal["cm", "m", "mm", ""] = "cm"


class Trig3D(StagedPrimitive[Trig3DParams]):
    primitive_id = "Trig3D"
    version = "1"
    topic = "Trigonometry"
    params_model = Trig3DParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("solid", "*"),
            ("shadow", "*"),
            ("line", "*"),
            ("triangle", "*"),
            ("angle", "*"),
        ],
    )

    def default_params(self) -> Trig3DParams:
        return Trig3DParams(solid="cuboid", length=8, width=6, height=5)

    def validate(self, params: Trig3DParams) -> list[PredicateFailure]:
        return []

    def computed_values(self, params: Trig3DParams) -> dict[str, str]:
        shadow, line, angle = _solve(params)
        return {
            "shadow": format_sf(shadow),
            "line": format_sf(line),
            "angle": f"{float(angle):.1f}",
        }

    def build(self, params: Trig3DParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        figure_box, working_box = split_columns(area, [1.35, 1], gap=0.3)
        L, H = params.length, params.height
        W = params.length if params.solid == "pyramid" else params.width
        scale = 3 / max(L, W, H)
        L, W, H = L * scale, W * scale, H * scale

        def proj(x, y, z):
            return (x + DEPTH[0] * z, y + DEPTH[1] * z)

        if params.solid == "cuboid":
            corners = {
                "A": (0, 0, 0),
                "B": (L, 0, 0),
                "C": (L, 0, W),
                "D": (0, 0, W),
                "E": (0, H, 0),
                "F": (L, H, 0),
                "G": (L, H, W),
                "H": (0, H, W),
            }
            edges = ["AB", "BF", "FE", "EA", "BC", "CG", "GF", "GH", "HE"]
            hidden = ["AD", "DC", "DH"]
            start, foot, top = "A", "C", "G"
        else:
            corners = {
                "A": (0, 0, 0),
                "B": (L, 0, 0),
                "C": (L, 0, W),
                "D": (0, 0, W),
                "M": (L / 2, 0, W / 2),
                "V": (L / 2, H, W / 2),
            }
            edges = ["AB", "BC", "AV", "BV", "CV"]
            hidden = ["CD", "DA", "DV"]
            start, foot, top = "A", "M", "V"
        points = {k: proj(*v) for k, v in corners.items()}
        # a pyramid keeps room on its right for the height's dimension line
        room = 0.9 if params.solid == "pyramid" else 0
        drawing_box = style.Box(
            figure_box.left, figure_box.right - room, figure_box.bottom, figure_box.top
        )
        diagram = Diagram(list(points.values()), drawing_box, margin=0.4)
        p = {k: diagram.p(*v) for k, v in points.items()}
        centre = sum(p.values()) / len(p)
        solid = VGroup(*(Line(p[e[0]], p[e[1]], stroke_width=3) for e in edges))
        solid.add(*(DashedLine(p[e[0]], p[e[1]], stroke_width=2, dash_length=0.1) for e in hidden))
        for k, point in p.items():
            if k == "M":  # the centre of the base, labelled beside the foot of the height
                solid.add(label(k, size=26).next_to(point, [1, -0.3, 0], buff=0.1))
                continue
            direction = point - centre
            direction = direction / (np.linalg.norm(direction) or 1)
            solid.add(label(k, size=26).move_to(point + 0.28 * direction))
        unit = rf"\text{{ {params.unit}}}" if params.unit else ""
        solid.add(
            label(rf"{_plain(params.length)}{unit}", size=24).next_to(
                (p["A"] + p["B"]) / 2, [0, -1, 0], buff=0.12
            )
        )
        if params.solid == "cuboid":
            solid.add(
                label(rf"{_plain(params.width)}{unit}", size=24).next_to(
                    (p["B"] + p["C"]) / 2, [1, -0.4, 0], buff=0.12
                ),
                label(rf"{_plain(params.height)}{unit}", size=24).next_to(
                    (p["C"] + p["G"]) / 2, [1, 0, 0], buff=0.12
                ),
            )
        else:
            # the height as a dimension line beside the pyramid, clear of its edges
            x = max(pt[0] for pt in p.values()) + 0.55
            arrow = DoubleArrow(
                [x, p["M"][1], 0],
                [x, p["V"][1], 0],
                buff=0,
                stroke_width=2,
                tip_length=0.12,
                color=style.TEXT_COLOUR,
            )
            solid.add(
                DashedLine(p["M"], p["V"], stroke_width=2, dash_length=0.08),
                arrow,
                label(rf"{_plain(params.height)}{unit}", size=24).next_to(
                    arrow, [1, 0, 0], buff=0.1
                ),
            )
        parts = {
            "solid": solid,
            "shadow": Line(p[start], p[foot], color=style.RUN_COLOUR, stroke_width=5),
            "line": Line(p[start], p[top], color=style.HIGHLIGHT_COLOUR, stroke_width=5),
            "triangle": Polygon(
                p[start],
                p[foot],
                p[top],
                stroke_width=0,
                fill_color=style.HIGHLIGHT_COLOUR,
                fill_opacity=0.25,
            ),
            "angle": angle_mark(p[start], p[foot], p[top], radius=0.5, colour=style.TANGENT_COLOUR),
        }
        rows = _working(params)
        mobjects = [label(t, size=30) for t in rows]
        group = VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.3)
        for mob in mobjects:
            if mob.width > working_box.width:
                mob.scale_to_fit_width(working_box.width)
        style.fit_inside(group.arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.3), working_box)
        for i, mob in enumerate(mobjects, start=1):
            parts[f"row_{i}"] = mob
        line_name = f"{start}{top}"
        base = "ABCD"
        parts["question"] = text_line(
            rf"\text{{Find {line_name} and the angle between {line_name} and {base}}}",
            upper,
            size=34,
        )
        shadow, line, angle = _solve(params)
        parts["answer"] = text_line(
            rf"{line_name} = {format_sf(line)}{unit},\ \text{{angle}} = {float(angle):.1f}^\circ",
            lower,
            colour=style.HIGHLIGHT_COLOUR,
        )
        return parts

    def stages(self, params: Trig3DParams, level) -> list[Stage]:
        steps = [
            stage("solid", "Here is the solid", 2.5, ["question", "solid"]),
            stage(
                "shadow",
                "First the line in the base, beneath the one we want, by Pythagoras",
                3.5,
                ["shadow", "row_1", "row_2"],
            ),
            stage(
                "line",
                "It makes a right-angled triangle with the height: Pythagoras again",
                3.5,
                ["line", "triangle", "row_3"],
            ),
            stage(
                "angle",
                "The angle with the base is in that triangle: use tan",
                3.5,
                ["angle", "row_4"],
                emphasise=["angle"],
            ),
            stage("answer", "So", 1.5, ["answer"], emphasise=["answer"]),
        ]

        def concise(s):
            return [s[0], combine("triangles", "Two right-angled triangles", 5.0, *s[1:4]), s[4]]

        return by_level(level, steps, lambda s: s, concise)


def _plain(value) -> str:
    return format_sf(value, 6)


def _solve(params: Trig3DParams) -> tuple[sp.Expr, sp.Expr, sp.Expr]:
    L, H = sp.nsimplify(params.length), sp.nsimplify(params.height)
    W = L if params.solid == "pyramid" else sp.nsimplify(params.width)
    diagonal = sp.sqrt(L**2 + W**2)
    shadow = diagonal if params.solid == "cuboid" else diagonal / 2
    line = sp.sqrt(shadow**2 + H**2)
    angle = sp.deg(sp.atan(H / shadow))
    return shadow, line, sp.N(angle)


def _working(params: Trig3DParams) -> list[str]:
    shadow, line, angle = _solve(params)
    L, H = _plain(params.length), _plain(params.height)
    W = L if params.solid == "pyramid" else _plain(params.width)
    if params.solid == "cuboid":
        first = [rf"AC^2 = {L}^2 + {W}^2", rf"AC = {latex_approx(shadow)}"]
        name, base = "AG", "AC"
    else:
        first = [
            rf"AC = \sqrt{{{L}^2 + {W}^2}},\ AM = \tfrac{{1}}{{2}}AC",
            rf"AM = {latex_approx(shadow)}",
        ]
        name, base = "AV", "AM"
    return [
        *first,
        rf"{name} = \sqrt{{{base}^2 + {H}^2}} = {format_sf(line)}",
        rf"\tan\theta = \frac{{{H}}}{{{format_sf(shadow)}}},\ \theta = {float(angle):.1f}^\circ",
    ]
