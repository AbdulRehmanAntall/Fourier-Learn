"""SineCosineRule: a triangle solved with the sine rule, the cosine rule or the area formula
½ab sin C, the rule chosen from what is known (4024 6.3; PRIMITIVES.md #39).

Sides a, b, c are opposite the angles A, B, C. The cosine rule finds a side from the two sides
round it and the angle between them, or an angle from three sides. The sine rule pairs a side
with its opposite angle: it finds a side from two angles and a side (the third angle from
180° first if needed), or an angle from two sides and an angle not between them, where O Level
takes the acute answer. Lengths are to 3 significant figures, angles to 1 decimal place.
"""

import math
from typing import Annotated, Literal

import numpy as np
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
Angle = Annotated[float, Field(gt=0, lt=180)]
LETTERS = "abc"
OTHERS = {"a": "bc", "b": "ac", "c": "ab"}
REASON = {
    "cosine_side": "Two sides and the angle between them: the cosine rule",
    "cosine_angle": "Three sides: the cosine rule for an angle",
    "sine_side": "A side with its opposite angle: the sine rule",
    "sine_angle": "A side with its opposite angle: the sine rule for an angle",
    "area": "Two sides and the angle between them: area is half a b sine C",
}


class SineCosineRuleParams(PrimitiveParams):
    a: Length | None = None
    b: Length | None = None
    c: Length | None = None
    A: Angle | None = None
    B: Angle | None = None
    C: Angle | None = None
    find: Literal["a", "b", "c", "A", "B", "C", "area"]
    unit: Literal["cm", "m", "mm", "km", ""] = "cm"


class SineCosineRule(StagedPrimitive[SineCosineRuleParams]):
    primitive_id = "SineCosineRule"
    version = "1"
    topic = "Trigonometry"
    params_model = SineCosineRuleParams
    layout = LayoutContract(region=style.GRAPH_REGION, allowed_overlaps=[("triangle", "*")])

    def default_params(self) -> SineCosineRuleParams:
        return SineCosineRuleParams(b=7, c=9, A=48, find="a")

    def validate(self, params: SineCosineRuleParams) -> list[PredicateFailure]:
        if params.find != "area" and getattr(params, params.find) is not None:
            return [_failure("find_unknown", "the value to find is given", params.find)]
        try:
            solved = _solve(params)
        except ValueError as error:
            return [_failure("triangle_determined", str(error), "a", "b", "c", "A", "B", "C")]
        for name in ("a", "b", "c", "A", "B", "C"):
            given = getattr(params, name)
            if given is not None and abs(given - solved[name]) > 0.01 * max(given, 1):
                message = f"{name} = {given} does not fit the other values"
                return [_failure("values_consistent", message, name)]
        try:
            _method(params)
        except ValueError as error:
            return [_failure("one_rule", str(error), "find")]
        return []

    def computed_values(self, params: SineCosineRuleParams) -> dict[str, str]:
        solved = _solve(params)
        if params.find == "area":
            return {"area": format_sf(_area(solved))}
        if params.find.isupper():
            return {params.find: f"{solved[params.find]:.1f}"}
        return {params.find: format_sf(solved[params.find])}

    def build(self, params: SineCosineRuleParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        figure_box, working_box = split_columns(area, [1.1, 1], gap=0.3)
        s = _solve(params)
        A, B, C = (math.radians(s[k]) for k in "ABC")
        pts = {
            "A": (0.0, 0.0),
            "B": (s["c"], 0.0),
            "C": (s["b"] * math.cos(A), s["b"] * math.sin(A)),
        }
        diagram = Diagram(list(pts.values()), figure_box, margin=0.65)
        p = {k: diagram.p(*v) for k, v in pts.items()}
        centroid = (p["A"] + p["B"] + p["C"]) / 3
        triangle = VGroup(Polygon(p["A"], p["B"], p["C"], color=style.TEXT_COLOUR, stroke_width=4))
        for k in "ABC":
            out = (p[k] - centroid) / np.linalg.norm(p[k] - centroid)
            triangle.add(label(k, size=30).move_to(p[k] + 0.32 * out))
        parts = {"triangle": triangle}
        for side in LETTERS:
            q, r = (p[v.upper()] for v in OTHERS[side])
            value = getattr(params, side)
            if side == params.find:
                text = label("x", colour=style.HIGHLIGHT_COLOUR, size=32)
            elif value is not None:
                text = label(rf"{_plain(value)}\text{{ {params.unit}}}", size=30)
            else:
                continue
            mid = (q + r) / 2
            out = (mid - centroid) / np.linalg.norm(mid - centroid)
            text.move_to(mid + out * (0.2 + max(text.width, text.height) / 2))
            parts[f"side_{side}"] = text
        for vertex in "ABC":
            q, r = (p[v] for v in "ABC" if v != vertex)
            value = getattr(params, vertex)
            derived = vertex == _third_angle(params)
            if vertex == params.find:
                tex, colour = "x", style.HIGHLIGHT_COLOUR
            elif value is not None:
                tex, colour = rf"{_plain(value)}^\circ", style.TEXT_COLOUR
            elif derived:
                tex, colour = rf"{_deg(s[vertex])}^\circ", style.RISE_COLOUR
            else:
                continue
            text = label(tex, colour=colour, size=28)
            # an obtuse angle in a flat triangle has no room inside: its label goes outside
            outside = s[vertex] > 100
            distance = (0.62 if outside else 0.55) + max(text.width, text.height) / 2
            text.move_to(angle_label_position(p[vertex], q, r, distance, reflex=outside))
            mark = angle_mark(
                p[vertex], q, r, radius=0.38, colour=style.RISE_COLOUR if derived else colour
            )
            parts[f"angle_{vertex}"] = VGroup(mark, text)
        rows = _working(params, s)
        mobjects = [label(tex, size=32) for tex in rows]
        group = VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.3)
        style.fit_inside(group, working_box)
        for i, mob in enumerate(mobjects, start=1):
            parts[f"row_{i}"] = mob
        unit = rf"\text{{ {params.unit}}}" if params.unit else ""
        if params.find == "area":
            answer = rf"\text{{Area}} = {format_sf(_area(s))}{unit}{'^2' if unit else ''}"
            question = r"\text{Find the area of the triangle}"
        elif params.find.isupper():
            answer = rf"x = {s[params.find]:.1f}^\circ"
            question = r"\text{Find the angle } x \text{ (to 1 d.p.)}"
        else:
            answer = rf"x = {format_sf(s[params.find])}{unit}"
            question = r"\text{Find the length } x \text{ (to 3 s.f.)}"
        parts["question"] = text_line(question, upper)
        parts["answer"] = text_line(answer, lower, colour=style.HIGHLIGHT_COLOUR)
        return parts

    def stages(self, params: SineCosineRuleParams, level) -> list[Stage]:
        method = _method(params)
        third = _third_angle(params)
        built = [f"side_{k}" for k in LETTERS if k == params.find or getattr(params, k)]
        angles = [f"angle_{k}" for k in "ABC" if k == params.find or getattr(params, k)]
        rows = [f"row_{i}" for i in range(1, len(_working(params, _solve(params))) + 1)]
        steps = [
            stage(
                "triangle", "Here is the triangle", 2.5, ["question", "triangle", *built, *angles]
            )
        ]
        if third:
            steps.append(
                stage(
                    "third",
                    "First the third angle: the angles add up to 180 degrees",
                    3.0,
                    [f"angle_{third}", rows[0]],
                )
            )
            rows = rows[1:]
        steps += [
            stage("rule", REASON[method], 3.5, rows[:1], emphasise=rows[:1]),
            stage("substitute", "Substitute the values", 3.0, rows[1:-1]),
            stage("solve", "Work it out", 2.5, [rows[-1], "answer"], emphasise=["answer"]),
        ]

        def standard(s):
            return [*s[:-3], combine("rule", s[-3].description, 4.0, s[-3], s[-2]), s[-1]]

        def concise(s):
            return [s[0], combine("working", REASON[method], 5.0, *s[1:])]

        return by_level(level, steps, standard, concise)


def _known(params) -> dict[str, float]:
    return {
        k: getattr(params, k)
        for k in ("a", "b", "c", "A", "B", "C")
        if getattr(params, k) is not None
    }


def _third_angle(params) -> str | None:
    """The angle found from the other two first, when the sine rule needs it."""
    known = _known(params)
    angles = [k for k in "ABC" if k in known]
    if len(angles) != 2 or params.find in ("A", "B", "C", "area"):
        return None
    missing = next(k for k in "ABC" if k not in known)
    target = params.find
    pair = next(((s, s.upper()) for s in LETTERS if s in known and s.upper() in known), None)
    if target.upper() == missing or pair is None:
        return missing
    return None


def _solve(params) -> dict[str, float]:
    """All sides and angles (degrees) from what is given."""
    k = dict(_known(params))
    angles = [n for n in "ABC" if n in k]
    if len(angles) == 3:
        raise ValueError("give at most two angles")
    if len(angles) == 2:
        missing = next(n for n in "ABC" if n not in k)
        k[missing] = 180 - sum(k[n] for n in angles)
        if k[missing] <= 0:
            raise ValueError("the angles add up to 180° or more")
    sides = [n for n in LETTERS if n in k]
    if len(sides) == 3:
        a, b, c = k["a"], k["b"], k["c"]
        if a + b <= c or a + c <= b or b + c <= a:
            raise ValueError("these sides make no triangle")
        for side in LETTERS:
            x = k[side]
            y, z = (k[o] for o in OTHERS[side])
            k[side.upper()] = math.degrees(math.acos((y * y + z * z - x * x) / (2 * y * z)))
        return k
    if all(n in k for n in "ABC") and sides:
        ratio = k[sides[0]] / math.sin(math.radians(k[sides[0].upper()]))
        for side in LETTERS:
            k[side] = ratio * math.sin(math.radians(k[side.upper()]))
        return k
    if len(sides) == 2:
        x = next(n for n in LETTERS if n not in k)
        if x.upper() in k:  # two sides and the angle between them
            y, z = (k[o] for o in OTHERS[x])
            k[x] = math.sqrt(y * y + z * z - 2 * y * z * math.cos(math.radians(k[x.upper()])))
            return _solve_sss(k)
        pair = next((s for s in sides if s.upper() in k), None)
        if pair is None:
            raise ValueError("give two sides and an angle, two angles and a side, or three sides")
        other = next(s for s in sides if s != pair)
        sine = k[other] * math.sin(math.radians(k[pair.upper()])) / k[pair]
        if sine > 1:
            raise ValueError("no triangle has these values")
        k[other.upper()] = math.degrees(math.asin(sine))  # the acute answer
        k[x.upper()] = 180 - k[pair.upper()] - k[other.upper()]
        if k[x.upper()] <= 0:
            raise ValueError("no triangle has these values")
        k[x] = (
            k[pair] / math.sin(math.radians(k[pair.upper()])) * math.sin(math.radians(k[x.upper()]))
        )
        return k
    raise ValueError("give two sides and an angle, two angles and a side, or three sides")


def _solve_sss(k: dict[str, float]) -> dict[str, float]:
    for side in LETTERS:
        if side.upper() not in k:
            x = k[side]
            y, z = (k[o] for o in OTHERS[side])
            k[side.upper()] = math.degrees(math.acos((y * y + z * z - x * x) / (2 * y * z)))
    return k


def _area(s: dict[str, float]) -> float:
    return 0.5 * s["a"] * s["b"] * math.sin(math.radians(s["C"]))


def _method(params) -> str:
    known = _known(params)
    find = params.find
    sides = [n for n in LETTERS if n in known]
    if find == "area":
        for x in LETTERS:
            y, z = OTHERS[x]
            if y in known and z in known and x.upper() in known:
                return "area"
        raise ValueError("the area formula needs two sides and the angle between them")
    if find.islower():
        y, z = OTHERS[find]
        if y in known and z in known and find.upper() in known:
            return "cosine_side"
        if len([n for n in "ABC" if n in known]) == 2 and sides:
            return "sine_side"
        raise ValueError("use two sides and the angle between them, or two angles and a side")
    if len(sides) == 3:
        return "cosine_angle"
    if find.lower() in known and any(s in known and s.upper() in known for s in LETTERS):
        return "sine_angle"
    raise ValueError("use three sides, or a side with its opposite angle and one more side")


def _deg(value: float) -> str:
    """An angle to 1 decimal place, without a trailing .0."""
    return f"{value:.1f}".removesuffix(".0")


def _plain(value: float) -> str:
    return format_sf(value, 6)


def _working(params, s: dict[str, float]) -> list[str]:
    method = _method(params)
    known = _known(params)
    rows = []
    third = _third_angle(params)
    if third:
        others = [n for n in "ABC" if n != third]
        rows.append(
            rf"{third} = 180^\circ - {_plain(known[others[0]])}^\circ - "
            rf"{_plain(known[others[1]])}^\circ = {_deg(s[third])}^\circ"
        )
    find = params.find
    if method == "cosine_side":
        y, z = OTHERS[find]
        X = find.upper()
        square = s[find] ** 2
        rows += [
            rf"{find}^2 = {y}^2 + {z}^2 - 2{y}{z}\cos {X}",
            rf"x^2 = {_plain(known[y])}^2 + {_plain(known[z])}^2 - 2 \times {_plain(known[y])} "
            rf"\times {_plain(known[z])} \times \cos {_plain(known[X])}^\circ",
            rf"x^2 = {format_sf(square, 5)}",
            rf"x = {format_sf(s[find])}",
        ]
    elif method == "cosine_angle":
        x = find.lower()
        y, z = OTHERS[x]
        value = (s[y] ** 2 + s[z] ** 2 - s[x] ** 2) / (2 * s[y] * s[z])
        rows += [
            rf"\cos {find} = \frac{{{y}^2 + {z}^2 - {x}^2}}{{2{y}{z}}}",
            rf"\cos x = \frac{{{_plain(known[y])}^2 + {_plain(known[z])}^2 - "
            rf"{_plain(known[x])}^2}}{{2 \times {_plain(known[y])} \times {_plain(known[z])}}}"
            rf" = {format_sf(value, 4)}",
            rf"x = {s[find]:.1f}^\circ",
        ]
    elif method == "sine_side":
        pair = next(t for t in LETTERS if t in known and t != find)
        P, X = pair.upper(), find.upper()
        angle_x = known.get(X, s[X])
        rows += [
            rf"\frac{{{find}}}{{\sin {X}}} = \frac{{{pair}}}{{\sin {P}}}",
            rf"\frac{{x}}{{\sin {_plain(angle_x)}^\circ}} = "
            rf"\frac{{{_plain(known[pair])}}}{{\sin {_plain(known.get(P, s[P]))}^\circ}}",
            rf"x = \frac{{{_plain(known[pair])} \sin {_plain(angle_x)}^\circ}}"
            rf"{{\sin {_plain(known.get(P, s[P]))}^\circ}}",
            rf"x = {format_sf(s[find])}",
        ]
    elif method == "sine_angle":
        x = find.lower()
        pair = next(t for t in LETTERS if t in known and t.upper() in known)
        P = pair.upper()
        value = s[x] * math.sin(math.radians(known[P])) / s[pair]
        rows += [
            rf"\frac{{\sin {find}}}{{{x}}} = \frac{{\sin {P}}}{{{pair}}}",
            rf"\sin x = \frac{{{_plain(known[x])} \sin {_plain(known[P])}^\circ}}"
            rf"{{{_plain(known[pair])}}} = {format_sf(value, 4)}",
            rf"x = {s[find]:.1f}^\circ \text{{ (acute)}}",
        ]
    else:
        X = next(t for t in "ABC" if t in known and all(o in known for o in OTHERS[t.lower()]))
        y, z = OTHERS[X.lower()]
        rows += [
            rf"\text{{Area}} = \tfrac{{1}}{{2}}{y}{z}\sin {X}",
            rf"= \tfrac{{1}}{{2}} \times {_plain(known[y])} \times {_plain(known[z])} \times "
            rf"\sin {_plain(known[X])}^\circ",
            rf"= {format_sf(0.5 * known[y] * known[z] * math.sin(math.radians(known[X])))}",
        ]
    return rows


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
