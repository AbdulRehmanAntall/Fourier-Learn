"""RightTriangleTrig: a right-angled triangle solved with Pythagoras' theorem or a trigonometric
ratio, the method chosen from what is known (4024 6.1, 6.2; PRIMITIVES.md #38).

The triangle ABC has its right angle at C and the angle θ at A. Two sides known and a side
wanted: Pythagoras. A side known with θ, or two sides and θ wanted: the sides are named
opposite, adjacent and hypotenuse from θ, SOH CAH TOA picks the ratio that uses the known and
the wanted side, and the equation is rearranged. Lengths are given to 3 significant figures
and angles to 1 decimal place, as O Level asks; exact answers are shown exactly.
"""

import math
from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import Polygon, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import (
    Diagram,
    angle_label_position,
    angle_mark,
    label,
    split_columns,
    text_line,
)
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf

Length = Annotated[float, Field(gt=0, le=10_000)]
Side = Literal["opposite", "adjacent", "hypotenuse"]
RATIOS = {
    "sin": ("opposite", "hypotenuse"),
    "cos": ("adjacent", "hypotenuse"),
    "tan": ("opposite", "adjacent"),
}
WORD = {"sin": "SOH", "cos": "CAH", "tan": "TOA"}
SHORT = {"opposite": "opp", "adjacent": "adj", "hypotenuse": "hyp"}
COLOUR = {
    "opposite": style.RISE_COLOUR,
    "adjacent": style.RUN_COLOUR,
    "hypotenuse": style.CURVE_COLOUR,
}


class RightTriangleTrigParams(PrimitiveParams):
    opposite: Length | None = Field(default=None, description="The side BC, opposite θ")
    adjacent: Length | None = Field(default=None, description="The side AC, next to θ")
    hypotenuse: Length | None = Field(default=None, description="The side AB")
    angle: Annotated[float, Field(gt=0, lt=90)] | None = Field(
        default=None, description="θ at A, in degrees"
    )
    find: Literal["opposite", "adjacent", "hypotenuse", "angle"]
    unit: Literal["cm", "m", "mm", "km", ""] = "cm"


class RightTriangleTrig(StagedPrimitive[RightTriangleTrigParams]):
    primitive_id = "RightTriangleTrig"
    version = "1"
    topic = "Trigonometry"
    params_model = RightTriangleTrigParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("triangle", "*"), ("roles", "*"), ("chosen", "mnemonic")],
    )

    def default_params(self) -> RightTriangleTrigParams:
        return RightTriangleTrigParams(angle=35, hypotenuse=12, find="opposite")

    def validate(self, params: RightTriangleTrigParams) -> list[PredicateFailure]:
        known = [
            s for s in ("opposite", "adjacent", "hypotenuse") if getattr(params, s) is not None
        ]
        if params.find != "angle" and getattr(params, params.find) is not None:
            return [_failure("find_unknown", "the side to find is given", params.find)]
        if params.find == "angle":
            if params.angle is not None:
                return [_failure("find_unknown", "the angle to find is given", "angle")]
            if len(known) != 2:
                return [_failure("two_sides", "give exactly two sides", "opposite")]
        elif params.angle is None and len(known) != 2:
            return [_failure("two_sides", "Pythagoras needs the other two sides", "opposite")]
        elif params.angle is not None and len(known) != 1:
            return [_failure("one_side", "with the angle, give exactly one side", "opposite")]
        hyp = params.hypotenuse
        for leg in ("opposite", "adjacent"):
            value = getattr(params, leg)
            if hyp is not None and value is not None and value >= hyp:
                message = "the hypotenuse must be the longest side"
                return [_failure("hypotenuse_longest", message, "hypotenuse", leg)]
        return []

    def computed_values(self, params: RightTriangleTrigParams) -> dict[str, str]:
        solved = _solve(params)
        if params.find == "angle":
            return {"angle": _angle_text(solved["angle"])}
        return {params.find: format_sf(solved[params.find])}

    def build(self, params: RightTriangleTrigParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        figure_box, working_box = split_columns(area, [1.1, 1], gap=0.3)
        solved = _solve(params)
        theta = math.radians(float(solved["angle"]))
        adj = float(solved["adjacent"])
        opp = float(solved["opposite"])
        diagram = Diagram([(0, 0), (adj, 0), (adj, opp)], figure_box, margin=0.75)
        a, c, b = diagram.p(0, 0), diagram.p(adj, 0), diagram.p(adj, opp)
        triangle = VGroup(
            Polygon(a, c, b, color=style.TEXT_COLOUR, stroke_width=4),
            angle_mark(c, a, b, radius=0.3, colour=style.TEXT_COLOUR),
            label("A", size=30).move_to(a + np.array([-0.3, -0.2, 0])),
            label("C", size=30).move_to(c + np.array([0.3, -0.2, 0])),
            label("B", size=30).move_to(b + np.array([0.3, 0.2, 0])),
        )
        parts = {"triangle": triangle}
        if params.find == "angle" or params.angle is not None:
            theta_text = "x" if params.find == "angle" else rf"{_plain(params.angle)}^\circ"
            theta_label = label(
                theta_text,
                colour=style.HIGHLIGHT_COLOUR if params.find == "angle" else style.TEXT_COLOUR,
                size=30,
            )
            theta_label.move_to(angle_label_position(a, c, b, 0.9))
            parts["angle"] = VGroup(
                angle_mark(a, c, b, radius=0.5, colour=style.HIGHLIGHT_COLOUR), theta_label
            )
        normal = {
            "opposite": np.array([1, 0, 0]),
            "adjacent": np.array([0, -1, 0]),
            "hypotenuse": np.array([-math.sin(theta), math.cos(theta), 0]),
        }
        ends = {"opposite": (c, b), "adjacent": (a, c), "hypotenuse": (a, b)}
        roles = VGroup()
        for side, (p, q) in ends.items():
            mid = (p + q) / 2
            role = label(rf"\text{{{SHORT[side]}}}", colour=COLOUR[side], size=24)
            value = getattr(params, side)
            if side == params.find:
                text = label("x", colour=style.HIGHLIGHT_COLOUR, size=32)
            elif value is not None:
                text = label(rf"{_plain(value)}\text{{ {params.unit}}}", size=30)
            else:
                text = None
            if text is not None:
                text.move_to(mid + normal[side] * (0.3 + max(text.width, text.height) / 2))
                parts[f"length_{side}"] = text
                below = side != "hypotenuse"  # the tag under the label keeps the figure narrow
                role.next_to(text, [0, -1, 0] if below else normal[side], buff=0.1)
            else:
                role.move_to(mid + normal[side] * (0.3 + max(role.width, role.height) / 2))
            roles.add(role)
        method = _method(params)
        if method != "pythagoras":
            parts["roles"] = roles
            parts["mnemonic"] = label(r"\text{SOH} \quad \text{CAH} \quad \text{TOA}", size=34)
        rows = _working(params, solved)
        mobjects = [label(tex, size=34) for tex in rows]
        if method != "pythagoras":
            mobjects.insert(0, parts["mnemonic"])
        group = VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.3)
        style.fit_inside(group, working_box)
        if method != "pythagoras":
            word = WORD[method]
            parts["chosen"] = label(rf"\text{{{word}}}", colour=style.HIGHLIGHT_COLOUR, size=34)
            index = ["SOH", "CAH", "TOA"].index(word)
            glyphs = parts["mnemonic"][0]
            start = index * 3  # three letters a word
            parts["chosen"].match_height(glyphs[start : start + 3]).move_to(
                glyphs[start : start + 3]
            )
            mobjects = mobjects[1:]
        for i, mob in enumerate(mobjects, start=1):
            parts[f"row_{i}"] = mob
        parts["question"] = text_line(_question(params), upper)
        answer = (
            rf"x = {_angle_text(solved['angle'])}^\circ"
            if params.find == "angle"
            else rf"x = {format_sf(solved[params.find])}\text{{ {params.unit}}}"
        )
        parts["answer"] = text_line(answer, lower, colour=style.HIGHLIGHT_COLOUR)
        return parts

    def stages(self, params: RightTriangleTrigParams, level) -> list[Stage]:
        method = _method(params)
        rows = [f"row_{i}" for i in range(1, len(_working(params, _solve(params))) + 1)]
        steps = [
            stage(
                "triangle",
                "Here is the right-angled triangle",
                2.5,
                [
                    "question",
                    "triangle",
                    *(["angle"] if params.find == "angle" or params.angle is not None else []),
                    *(
                        f"length_{s}"
                        for s in ("opposite", "adjacent", "hypotenuse")
                        if s == params.find or getattr(params, s) is not None
                    ),
                ],
            )
        ]
        if method == "pythagoras":
            steps += [
                stage(
                    "theorem",
                    "Pythagoras: the square on the hypotenuse equals the sum of "
                    "the squares on the other two sides",
                    3.5,
                    rows[:2],
                ),
                stage("solve", "Work it out", 3.0, rows[2:]),
            ]
        else:
            steps += [
                stage(
                    "roles",
                    "Name the sides from the angle: opposite, adjacent and hypotenuse",
                    3.5,
                    ["roles"],
                ),
                stage(
                    "ratio",
                    f"We use the {SHORT[RATIOS[method][0]]} and the "
                    f"{SHORT[RATIOS[method][1]]}, so it is {WORD[method]}: {method}",
                    3.5,
                    ["mnemonic", "chosen", rows[0]],
                    emphasise=["chosen"],
                ),
                stage("solve", "Substitute and rearrange", 3.5, rows[1:]),
            ]
        steps.append(stage("answer", "So", 1.5, ["answer"], emphasise=["answer"]))

        def standard(s):
            return [s[0], combine("method", s[1].description, 4.0, s[1], s[2]), *s[3:]]

        def concise(s):
            return [s[0], combine("working", "Solve the triangle", 4.5, *s[1:])]

        return by_level(level, steps, standard, concise)


def _method(params: RightTriangleTrigParams) -> str:
    """'pythagoras', or the ratio that links the known and wanted sides."""
    if params.find != "angle" and params.angle is None:
        return "pythagoras"
    sides = {s for s in ("opposite", "adjacent", "hypotenuse") if getattr(params, s) is not None}
    if params.find != "angle":
        sides.add(params.find)
    for ratio, pair in RATIOS.items():
        if set(pair) == sides:
            return ratio
    raise ValueError("no ratio")


def _solve(params: RightTriangleTrigParams) -> dict[str, sp.Expr]:
    """All three sides and θ (degrees), exact where the given values allow."""
    o, a, h = (
        None if v is None else sp.nsimplify(v)
        for v in (params.opposite, params.adjacent, params.hypotenuse)
    )
    if params.angle is not None:
        t = sp.rad(sp.nsimplify(params.angle))
        if h is not None:
            o, a = h * sp.sin(t), h * sp.cos(t)
        elif o is not None:
            h, a = o / sp.sin(t), o / sp.tan(t)
        else:
            h, o = a / sp.cos(t), a * sp.tan(t)
        return {"opposite": o, "adjacent": a, "hypotenuse": h, "angle": sp.nsimplify(params.angle)}
    if h is None:
        h = sp.sqrt(o**2 + a**2)
    elif o is None:
        o = sp.sqrt(h**2 - a**2)
    elif a is None:
        a = sp.sqrt(h**2 - o**2)
    angle = sp.deg(sp.atan2(o, a))
    return {"opposite": o, "adjacent": a, "hypotenuse": h, "angle": angle}


def _plain(value: float) -> str:
    return format_sf(sp.nsimplify(value), 6)


def _angle_text(value: sp.Expr) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:.1f}"


def _working(params: RightTriangleTrigParams, solved) -> list[str]:
    method = _method(params)
    if method == "pythagoras":
        names = {"opposite": "BC", "adjacent": "AC", "hypotenuse": "AB"}
        legs = ["opposite", "adjacent"]
        if params.find == "hypotenuse":
            o, a = (_plain(getattr(params, s)) for s in legs)
            total = sp.nsimplify(params.opposite) ** 2 + sp.nsimplify(params.adjacent) ** 2
            return [
                r"AB^2 = BC^2 + AC^2",
                rf"x^2 = {o}^2 + {a}^2 = {_plain(total)}",
                rf"x = \sqrt{{{_plain(total)}}}",
                rf"x = {format_sf(solved['hypotenuse'])}",
            ]
        other = "adjacent" if params.find == "opposite" else "opposite"
        h, k = _plain(params.hypotenuse), _plain(getattr(params, other))
        total = sp.nsimplify(params.hypotenuse) ** 2 - sp.nsimplify(getattr(params, other)) ** 2
        return [
            rf"{names[params.find]}^2 = AB^2 - {names[other]}^2",
            rf"x^2 = {h}^2 - {k}^2 = {_plain(total)}",
            rf"x = \sqrt{{{_plain(total)}}}",
            rf"x = {format_sf(solved[params.find])}",
        ]
    top, bottom = RATIOS[method]
    formula = rf"\{method} \theta = \frac{{\text{{{SHORT[top]}}}}}{{\text{{{SHORT[bottom]}}}}}"
    if params.find == "angle":
        t, b = _plain(getattr(params, top)), _plain(getattr(params, bottom))
        return [
            formula,
            rf"\{method} x = \frac{{{t}}}{{{b}}}",
            rf"x = \{method}^{{-1}}\left(\frac{{{t}}}{{{b}}}\right)",
            rf"x = {_angle_text(solved['angle'])}^\circ",
        ]
    angle = rf"{_plain(params.angle)}^\circ"
    if params.find == top:
        b = _plain(getattr(params, bottom))
        return [
            formula,
            rf"\{method} {angle} = \frac{{x}}{{{b}}}",
            rf"x = {b} \times \{method} {angle}",
            rf"x = {format_sf(solved[params.find])}",
        ]
    t = _plain(getattr(params, top))
    return [
        formula,
        rf"\{method} {angle} = \frac{{{t}}}{{x}}",
        rf"x = \frac{{{t}}}{{\{method} {angle}}}",
        rf"x = {format_sf(solved[params.find])}",
    ]


def _question(params: RightTriangleTrigParams) -> str:
    if params.find == "angle":
        return r"\text{Find the angle } x \text{ (to 1 d.p.)}"
    return r"\text{Find the length } x \text{ (to 3 s.f.)}"


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
