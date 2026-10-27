"""SolidMensuration: the volume and surface area of the O Level solids, drawn as a textbook
draws them, with the formula, the substitution and the answer (4024 5.1, 5.4, 5.5;
PRIMITIVES.md #37).

Solids: cuboid, triangular prism (a right-angled cross-section), cylinder, cone, square-based
pyramid, sphere and hemisphere. They are drawn in oblique projection with hidden edges dashed.
A cone's slant height comes from Pythagoras when it is not given, and so does a pyramid's
slant height of a face. Answers are exact in π where they can be, with the 3 s.f. value.
"""

import math
from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import DashedLine, DashedVMobject, DoubleArrow, Line, ParametricFunction, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import Diagram, label, split_columns, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf, latex_with_pi

Positive = Annotated[float, Field(gt=0, le=1000)]
Solid = Literal["cuboid", "prism", "cylinder", "cone", "pyramid", "sphere", "hemisphere"]
NEEDS = {
    "cuboid": ("length", "width", "height"),
    "prism": ("length", "width", "height"),
    "cylinder": ("radius", "height"),
    "cone": ("radius", "height"),
    "pyramid": ("width", "height"),
    "sphere": ("radius",),
    "hemisphere": ("radius",),
}
DEPTH = (0.5, 0.32)  # where one unit of depth goes on the page


class SolidMensurationParams(PrimitiveParams):
    solid: Solid
    find: Literal["volume", "surface_area", "curved_area"]
    length: Positive | None = None
    width: Positive | None = Field(default=None, description="Depth; the base side of a pyramid")
    height: Positive | None = None
    radius: Positive | None = None
    unit: Literal["cm", "m", "mm", ""] = "cm"


class SolidMensuration(StagedPrimitive[SolidMensurationParams]):
    primitive_id = "SolidMensuration"
    version = "1"
    topic = "Mensuration"
    params_model = SolidMensurationParams
    layout = LayoutContract(
        region=style.GRAPH_REGION, allowed_overlaps=[("solid", "*"), ("dimensions", "*")]
    )

    def default_params(self) -> SolidMensurationParams:
        return SolidMensurationParams(solid="cylinder", radius=3, height=10, find="volume")

    def validate(self, params: SolidMensurationParams) -> list[PredicateFailure]:
        missing = [n for n in NEEDS[params.solid] if getattr(params, n) is None]
        if missing:
            message = f"a {params.solid} needs {', '.join(missing)}"
            return [_failure("needs_dimensions", message, *missing)]
        if params.find == "curved_area" and params.solid not in (
            "cylinder",
            "cone",
            "sphere",
            "hemisphere",
        ):
            message = f"a {params.solid} has no curved surface"
            return [_failure("has_curved_surface", message, "find")]
        return []

    def computed_values(self, params: SolidMensurationParams) -> dict[str, str]:
        return {params.find: format_sf(_formula(params)[2])}

    def build(self, params: SolidMensurationParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        figure_box, working_box = split_columns(area, [1.0, 1], gap=0.4)
        # room on the right of the drawing for a height label
        room = 0.9 if params.solid in ("cylinder", "cone", "pyramid") else 0.3
        drawing_box = style.Box(
            figure_box.left, figure_box.right - room, figure_box.bottom, figure_box.top
        )
        solid, dimensions = _draw(params, drawing_box)
        parts = {"solid": solid, "dimensions": dimensions}
        rows = [*_formula(params)[:2], f"= {_value(_formula(params)[2])}"]
        extra = _extra(params)
        rows = ([extra] if extra else []) + rows
        mobjects = [label(tex, size=32) for tex in rows]
        group = VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.3)
        for mob in mobjects:
            if mob.width > working_box.width:
                mob.scale_to_fit_width(working_box.width)
        style.fit_inside(group.arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.3), working_box)
        for i, mob in enumerate(mobjects, start=1):
            parts[f"row_{i}"] = mob
        word = {
            "volume": "Volume",
            "surface_area": "Surface area",
            "curved_area": "Curved surface area",
        }[params.find]
        power = "^3" if params.find == "volume" else "^2"
        unit = rf"\text{{ {params.unit}}}{power}" if params.unit else ""
        name = "triangular prism" if params.solid == "prism" else params.solid
        if params.solid == "pyramid":
            name = "square-based pyramid"
        parts["question"] = text_line(rf"\text{{The {word.lower()} of the {name}}}", upper)
        parts["answer"] = text_line(
            rf"\text{{{word}}} = {format_sf(_formula(params)[2])}{unit}",
            lower,
            colour=style.HIGHLIGHT_COLOUR,
        )
        return parts

    def stages(self, params: SolidMensurationParams, level) -> list[Stage]:
        extra = 1 if _extra(params) else 0
        rows = [f"row_{i}" for i in range(1, 4 + extra)]
        steps = [
            stage(
                "solid",
                "Here is the solid with its measurements",
                2.5,
                ["question", "solid", "dimensions"],
            )
        ]
        if extra:
            steps.append(stage("slant", "First the slant height, by Pythagoras", 3.0, rows[:1]))
        steps += [
            stage("formula", _spoken(params), 3.0, [rows[extra]], emphasise=[rows[extra]]),
            stage("substitute", "Substitute the measurements", 3.0, [rows[extra + 1]]),
            stage("answer", "Work it out", 2.5, [rows[extra + 2], "answer"], emphasise=["answer"]),
        ]

        def standard(s):
            return [*s[:-3], combine("formula", s[-3].description, 4.0, s[-3], s[-2]), s[-1]]

        def concise(s):
            return [s[0], combine("working", _spoken(params), 5.0, *s[1:])]

        return by_level(level, steps, standard, concise)


def _n(value):
    return sp.nsimplify(value)


def _plain(value: float) -> str:
    return format_sf(value, 6)


def _slant(params) -> sp.Expr:
    if params.solid == "cone":
        return sp.sqrt(_n(params.radius) ** 2 + _n(params.height) ** 2)
    return sp.sqrt(_n(params.height) ** 2 + (_n(params.width) / 2) ** 2)


def _extra(params) -> str | None:
    """The slant height first, when the formula needs it."""
    if params.solid == "cone" and params.find != "volume":
        r, h = _plain(params.radius), _plain(params.height)
        return rf"l = \sqrt{{{r}^2 + {h}^2}} = {_value(_slant(params))}"
    if params.solid == "pyramid" and params.find == "surface_area":
        h, half = _plain(params.height), _plain(params.width / 2)
        return rf"l = \sqrt{{{h}^2 + {half}^2}} = {_value(_slant(params))}"
    return None


def _formula(params) -> tuple[str, str, sp.Expr]:
    """(formula, substitution, exact value)."""
    s, f = params.solid, params.find
    L, W, H, R = (
        None if v is None else _n(v)
        for v in (params.length, params.width, params.height, params.radius)
    )
    p = {
        k: _plain(getattr(params, k)) if getattr(params, k) else ""
        for k in ("length", "width", "height", "radius")
    }
    ln, w, h, r = p["length"], p["width"], p["height"], p["radius"]
    if s == "cuboid":
        if f == "volume":
            return r"V = lwh", rf"V = {ln} \times {w} \times {h}", L * W * H
        return (
            r"A = 2(lw + lh + wh)",
            rf"A = 2({ln} \times {w} + {ln} \times {h} + {w} \times {h})",
            2 * (L * W + L * H + W * H),
        )
    if s == "prism":
        if f == "volume":
            return (
                r"V = \text{cross-section} \times \text{length}",
                rf"V = \tfrac{{1}}{{2}} \times {w} \times {h} \times {ln}",
                W * H * L / 2,
            )
        hyp = sp.sqrt(W**2 + H**2)
        return (
            r"A = 2 \times \tfrac{1}{2}bh + l(b + h + \sqrt{b^2 + h^2})",
            rf"A = {w} \times {h} + {ln}({w} + {h} + {_value(hyp, approx_only=True)})",
            W * H + L * (W + H + hyp),
        )
    if s == "cylinder":
        if f == "volume":
            return r"V = \pi r^2 h", rf"V = \pi \times {r}^2 \times {h}", sp.pi * R**2 * H
        if f == "curved_area":
            return r"A = 2\pi r h", rf"A = 2 \times \pi \times {r} \times {h}", 2 * sp.pi * R * H
        return (
            r"A = 2\pi r^2 + 2\pi r h",
            rf"A = 2 \times \pi \times {r}^2 + 2 \times \pi \times {r} \times {h}",
            2 * sp.pi * R**2 + 2 * sp.pi * R * H,
        )
    if s == "cone":
        if f == "volume":
            return (
                r"V = \tfrac{1}{3}\pi r^2 h",
                rf"V = \tfrac{{1}}{{3}} \times \pi \times {r}^2 "
                rf"\times {h}",
                sp.pi * R**2 * H / 3,
            )
        slant = _slant(params)
        sl = _value(slant, approx_only=True)
        if f == "curved_area":
            return r"A = \pi r l", rf"A = \pi \times {r} \times {sl}", sp.pi * R * slant
        return (
            r"A = \pi r^2 + \pi r l",
            rf"A = \pi \times {r}^2 + \pi \times {r} \times {sl}",
            sp.pi * R**2 + sp.pi * R * slant,
        )
    if s == "pyramid":
        if f == "volume":
            return (
                r"V = \tfrac{1}{3} \times \text{base} \times h",
                rf"V = \tfrac{{1}}{{3}} \times {w}^2 \times {h}",
                W**2 * H / 3,
            )
        slant = _slant(params)
        return (
            r"A = a^2 + 4 \times \tfrac{1}{2} a l",
            rf"A = {w}^2 + 2 \times {w} \times {_value(slant, approx_only=True)}",
            W**2 + 2 * W * slant,
        )
    if s == "sphere":
        if f == "volume":
            return (
                r"V = \tfrac{4}{3}\pi r^3",
                rf"V = \tfrac{{4}}{{3}} \times \pi \times {r}^3",
                4 * sp.pi * R**3 / 3,
            )
        return r"A = 4\pi r^2", rf"A = 4 \times \pi \times {r}^2", 4 * sp.pi * R**2
    if f == "volume":
        return (
            r"V = \tfrac{2}{3}\pi r^3",
            rf"V = \tfrac{{2}}{{3}} \times \pi \times {r}^3",
            2 * sp.pi * R**3 / 3,
        )
    if f == "curved_area":
        return r"A = 2\pi r^2", rf"A = 2 \times \pi \times {r}^2", 2 * sp.pi * R**2
    return (
        r"A = 2\pi r^2 + \pi r^2 = 3\pi r^2",
        rf"A = 3 \times \pi \times {r}^2",
        3 * sp.pi * R**2,
    )


def _value(expr, approx_only: bool = False) -> str:
    expr = sp.nsimplify(expr, [sp.pi])
    if approx_only:
        return format_sf(expr) if not expr.is_Integer else str(expr)
    return latex_with_pi(expr)


def _spoken(params) -> str:
    return {
        ("cuboid", "volume"): "The volume of a cuboid is length times width times height",
        ("prism", "volume"): "The volume of a prism is the area of its cross-section times its "
        "length",
        ("cylinder", "volume"): "The volume of a cylinder is pi r squared h",
        ("cone", "volume"): "The volume of a cone is a third of pi r squared h",
        ("pyramid", "volume"): "The volume of a pyramid is a third of the base area times the "
        "height",
        ("sphere", "volume"): "The volume of a sphere is four thirds pi r cubed",
        ("hemisphere", "volume"): "A hemisphere is half a sphere: two thirds pi r cubed",
    }.get((params.solid, params.find), "Add up the areas of all the faces")


# drawing


def _project(x: float, y: float, z: float) -> tuple[float, float]:
    return (x + DEPTH[0] * z, y + DEPTH[1] * z)


def _draw(params, box) -> tuple[VGroup, VGroup]:
    s = params.solid
    unit = rf"\text{{ {params.unit}}}" if params.unit else ""
    if s in ("cuboid", "prism", "pyramid"):
        L = params.width if s == "pyramid" else params.length
        W, H = params.width, params.height
        scale = 1 / max(L, W, H)
        L, W, H = L * scale * 3, W * scale * 3, H * scale * 3
        if s == "cuboid":
            corners = {
                (i, j, k): (i * L, j * H, k * W) for i in (0, 1) for j in (0, 1) for k in (0, 1)
            }
            edges = [
                ((0, 0, 0), (1, 0, 0)),
                ((1, 0, 0), (1, 1, 0)),
                ((1, 1, 0), (0, 1, 0)),
                ((0, 1, 0), (0, 0, 0)),
                ((1, 0, 0), (1, 0, 1)),
                ((1, 1, 0), (1, 1, 1)),
                ((0, 1, 0), (0, 1, 1)),
                ((1, 0, 1), (1, 1, 1)),
                ((0, 1, 1), (1, 1, 1)),
            ]
            hidden = [((0, 0, 1), (1, 0, 1)), ((0, 0, 1), (0, 1, 1)), ((0, 0, 1), (0, 0, 0))]
            points = {k: _project(*v) for k, v in corners.items()}
            dims = [
                ((0, 0, 0), (1, 0, 0), params.length, [0, -1]),
                ((1, 0, 0), (1, 0, 1), params.width, [1, -1]),
                ((1, 0, 1), (1, 1, 1), params.height, [1, 0]),
            ]
        elif s == "prism":
            # right-angled triangle cross-section (base W, height H) running along L
            corners = {
                "a": (0, 0, 0),
                "b": (W, 0, 0),
                "c": (0, H, 0),
                "a2": (0, 0, L),
                "b2": (W, 0, L),
                "c2": (0, H, L),
            }
            edges = [("a", "b"), ("b", "c"), ("c", "a"), ("b", "b2"), ("c", "c2"), ("b2", "c2")]
            hidden = [("a", "a2"), ("a2", "b2"), ("a2", "c2")]
            points = {k: _project(*v) for k, v in corners.items()}
            dims = [
                ("a", "b", params.width, [0, -1]),
                ("a", "c", params.height, [-1, 0]),
                ("b", "b2", params.length, [1, -1]),
            ]
        else:
            half = L / 2
            corners = {
                "a": (0, 0, 0),
                "b": (L, 0, 0),
                "c": (L, 0, L),
                "d": (0, 0, L),
                "t": (half, H, half),
                "m": (half, 0, half),
            }
            edges = [("a", "b"), ("b", "c"), ("a", "t"), ("b", "t"), ("c", "t")]
            hidden = [("c", "d"), ("d", "a"), ("d", "t"), ("t", "m")]
            points = {k: _project(*v) for k, v in corners.items()}
            dims = [("a", "b", params.width, [0, -1])]
        diagram = Diagram(list(points.values()), box, margin=0.45)
        p = {k: diagram.p(*v) for k, v in points.items()}
        solid = VGroup(*(Line(p[a], p[b], stroke_width=4) for a, b in edges))
        solid.add(*(DashedLine(p[a], p[b], stroke_width=3, dash_length=0.1) for a, b in hidden))
        dimensions = VGroup()
        for a, b, value, direction in dims:
            text = label(rf"{_plain(value)}{unit}", size=28)
            offset = np.array([direction[0], direction[1], 0]) * (0.2 + text.height)
            dimensions.add(text.move_to((p[a] + p[b]) / 2 + offset))
        if s == "pyramid":
            dimensions.add(_height_arrow(solid, p["m"][1], p["t"][1], params.height, unit))
        return solid, dimensions
    # round solids: radius r, height h (none for a sphere)
    r = params.radius
    h = params.height or 0
    scale = 3 / max(2 * r, h, r)
    R, Hh = r * scale, h * scale
    squash = 0.32
    top = {"cylinder": Hh, "cone": Hh, "sphere": R, "hemisphere": R}[s]
    bottom = -R if s == "sphere" else 0
    diagram = Diagram(
        [(-R, bottom), (R, top), (-R, -R * squash), (R, R * squash)], box, margin=0.45
    )
    k = diagram.scale
    centre = diagram.p(0, 0)

    def ellipse(y, start, end, dashed=False):
        curve = ParametricFunction(
            lambda t: diagram.p(R * math.cos(t), y + R * squash * math.sin(t)),
            t_range=[start, end],
            stroke_width=3 if dashed else 4,
        )
        return DashedVMobject(curve, num_dashes=18) if dashed else curve

    solid = VGroup()
    if s == "cylinder":
        solid.add(
            ellipse(Hh, 0, 2 * math.pi),
            ellipse(0, math.pi, 2 * math.pi),
            ellipse(0, 0, math.pi, dashed=True),
            Line(diagram.p(-R, 0), diagram.p(-R, Hh), stroke_width=4),
            Line(diagram.p(R, 0), diagram.p(R, Hh), stroke_width=4),
        )
        radius_from, radius_to = diagram.p(0, Hh), diagram.p(R, Hh)
        height_at = diagram.p(R, Hh / 2) + np.array([0.15, 0, 0])
    elif s == "cone":
        solid.add(
            ellipse(0, math.pi, 2 * math.pi),
            ellipse(0, 0, math.pi, dashed=True),
            Line(diagram.p(-R, 0), diagram.p(0, Hh), stroke_width=4),
            Line(diagram.p(R, 0), diagram.p(0, Hh), stroke_width=4),
            DashedLine(diagram.p(0, 0), diagram.p(0, Hh), stroke_width=3),
        )
        radius_from, radius_to = centre, diagram.p(R, 0)
        height_at = "arrow"
    else:
        arc = ParametricFunction(
            lambda t: centre + k * R * np.array([math.cos(t), math.sin(t), 0]),
            t_range=[0, 2 * math.pi if s == "sphere" else math.pi],
            stroke_width=4,
        )
        solid.add(arc, ellipse(0, math.pi, 2 * math.pi), ellipse(0, 0, math.pi, dashed=True))
        radius_from, radius_to = centre, diagram.p(R, 0)
        height_at = None
    solid.add(Line(radius_from, radius_to, stroke_width=3, color=style.RUN_COLOUR))
    dimensions = VGroup(
        label(rf"{_plain(r)}{unit}", colour=style.RUN_COLOUR, size=26).next_to(
            (radius_from + radius_to) / 2, [0, -1, 0], buff=0.06
        )
    )
    if isinstance(height_at, str):
        dimensions.add(_height_arrow(solid, centre[1], diagram.p(0, Hh)[1], h, unit))
    elif height_at is not None:
        text = label(rf"{_plain(h)}{unit}", size=28)
        dimensions.add(text.next_to(height_at, [1, 0, 0], buff=0.15))
    return solid, dimensions


def _height_arrow(solid: VGroup, bottom: float, top: float, value: float, unit: str) -> VGroup:
    """A vertical dimension line with its length, just right of the solid."""
    x = solid.get_right()[0] + 0.3
    arrow = DoubleArrow(
        [x, bottom, 0],
        [x, top, 0],
        buff=0,
        stroke_width=2,
        tip_length=0.15,
        color=style.TEXT_COLOUR,
    )
    text = label(rf"{_plain(value)}{unit}", size=28).next_to(arrow, [1, 0, 0], buff=0.12)
    return VGroup(arrow, text)


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
