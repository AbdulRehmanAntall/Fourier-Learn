"""RatioSplitter: sharing in a ratio with a bar model: equal units for each share, one unit
found from what is known, then every share (4024 1.11, 1.12; PRIMITIVES.md #10).

Each share is a row of equal boxes, as many as its number in the ratio. What is known (the
total, one share, or the difference between the largest and smallest share) is that many
units, so one unit is the amount divided by the number of units, and each share is its units
times one unit. A ratio can also be simplified by dividing by the highest common factor. Every
value is exact; money is shown to the cent.
"""

from functools import reduce
from math import gcd
from typing import Annotated, Literal

import sympy as sp
from manim import Brace, Rectangle, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_sf

Name = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=12, pattern=r"^[A-Za-z][A-Za-z ]*$"
    ),
]
Part = Annotated[int, Field(ge=1, le=60)]
COLOURS = [style.CURVE_COLOUR, style.RUN_COLOUR, style.RISE_COLOUR, style.SECANT_COLOUR]
MAX_UNITS = 24


class RatioSplitterParams(PrimitiveParams):
    ratio: list[Part] = Field(min_length=2, max_length=4, description="e.g. [2, 3]")
    names: list[Name] | None = Field(default=None, description='e.g. ["Ali", "Sara"]')
    kind: Literal["share", "part", "difference", "simplify"] = Field(
        description="share: the total is known; part: one share is known; difference: the "
        "largest minus the smallest is known; simplify: write the ratio in its simplest form"
    )
    amount: Annotated[float, Field(gt=0, le=10_000_000)] | None = Field(
        default=None, description="The known total, share or difference"
    )
    known: Annotated[int, Field(ge=0, le=3)] = Field(
        default=0, description="For part: which share is known (0 = first)"
    )
    money: bool = Field(default=False, description="Show amounts as money ($, to the cent)")


class RatioSplitter(StagedPrimitive[RatioSplitterParams]):
    primitive_id = "RatioSplitter"
    version = "1"
    topic = "Number"
    params_model = RatioSplitterParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("row_*", "row_*"), ("units_*", "row_*"), ("group_*", "row_*")],
    )

    def default_params(self) -> RatioSplitterParams:
        return RatioSplitterParams(ratio=[2, 3], names=["Ali", "Sara"], kind="share", amount=40)

    def validate(self, params: RatioSplitterParams) -> list[PredicateFailure]:
        ratio = params.ratio
        if params.names is not None and len(params.names) != len(ratio):
            return [_failure("one_name_each", "give one name for each part", "names")]
        if params.kind == "simplify":
            if _hcf(ratio) == 1:
                message = "the ratio is already in its simplest form"
                return [_failure("can_simplify", message, "ratio")]
            if sum(r // _hcf(ratio) for r in ratio) > MAX_UNITS:
                return [_failure("units_fit", f"more than {MAX_UNITS} units", "ratio")]
            return []
        if sum(ratio) > MAX_UNITS:
            return [_failure("units_fit", f"more than {MAX_UNITS} units to draw", "ratio")]
        if params.amount is None:
            return [_failure("needs_amount", f"{params.kind} needs an amount", "amount")]
        if params.kind == "part" and params.known >= len(ratio):
            return [_failure("known_exists", "known is not one of the parts", "known")]
        if params.kind == "difference" and max(ratio) == min(ratio):
            return [_failure("parts_differ", "the parts are equal: no difference", "ratio")]
        return []

    def computed_values(self, params: RatioSplitterParams) -> dict[str, str]:
        if params.kind == "simplify":
            return {"simplest": ":".join(str(r // _hcf(params.ratio)) for r in params.ratio)}
        unit, _ = _unit(params)
        values = {"unit": _amount(unit, params.money)}
        for name, r in zip(_names(params), params.ratio, strict=True):
            values[name] = _amount(unit * r, params.money)
        values["total"] = _amount(unit * sum(params.ratio), params.money)
        return values

    def build(self, params: RatioSplitterParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        names = _names(params)
        ratio = params.ratio
        units = [r // _hcf(ratio) for r in ratio] if params.kind == "simplify" else ratio
        rows = len(ratio)
        name_width = 1.5
        side = min(0.9, (area.width - name_width - 1.6) / max(ratio))  # box width
        tall = min(0.9, area.height / (rows * 1.8))  # box height
        left = area.left + name_width
        gap = (area.height - rows * tall) / (rows + 1)
        parts = {"question": text_line(_question(params, names), upper)}
        unit = _unit(params)[0] if params.kind != "simplify" else None
        for i, (name, r) in enumerate(zip(names, ratio, strict=True)):
            y = area.top - gap * (i + 1) - tall * (i + 0.5)
            colour = COLOURS[i % len(COLOURS)]
            boxes = VGroup(
                *(
                    Rectangle(
                        width=side,
                        height=min(tall, max(side, 0.45)),
                        stroke_color=style.TEXT_COLOUR,
                        stroke_width=2,
                        fill_color=colour,
                        fill_opacity=0.5,
                    ).move_to([left + side * (k + 0.5), y, 0])
                    for k in range(r)
                )
            )
            parts[f"row_{i}"] = boxes
            parts[f"name_{i}"] = label(rf"\text{{{name}}}", colour=colour, size=32).move_to(
                [area.left + name_width / 2, y, 0]
            )
            parts[f"count_{i}"] = label(str(r), colour=colour, size=28).next_to(
                boxes, [1, 0, 0], buff=0.2
            )
            if params.kind == "simplify":
                groups = VGroup()
                size = r // units[i]
                for g in range(units[i]):
                    block = VGroup(*boxes[g * size : (g + 1) * size])
                    groups.add(
                        Rectangle(
                            width=block.width,
                            height=block.height + 0.12,
                            stroke_color=style.HIGHLIGHT_COLOUR,
                            stroke_width=4,
                        ).move_to(block)
                    )
                parts[f"group_{i}"] = groups
                parts[f"share_{i}"] = label(
                    str(units[i]), colour=style.HIGHLIGHT_COLOUR, size=32
                ).next_to(boxes, [1, 0, 0], buff=0.75)
            else:
                fits = side >= 0.55
                text = _amount(unit, params.money)
                parts[f"units_{i}"] = VGroup(
                    *(
                        label(text, size=min(26, 16 / max(len(text), 1) * side * 9)).move_to(box)
                        for box in (boxes if fits else boxes[:1])
                    )
                )
                parts[f"share_{i}"] = label(
                    _amount(unit * r, params.money), colour=colour, size=32
                ).next_to(boxes, [1, 0, 0], buff=0.75)
        if params.kind == "simplify":
            parts["working"] = text_line(_simplify_latex(ratio), lower)
        else:
            parts["working"] = text_line(_unit_latex(params), lower)
            parts["answer"] = text_line(
                _answer_latex(params, names), lower, colour=style.HIGHLIGHT_COLOUR
            )
            if params.kind in ("share", "difference"):
                parts["brace"] = _known_brace(params, parts, area)
        return parts

    def stages(self, params: RatioSplitterParams, level) -> list[Stage]:
        n = len(params.ratio)
        rows = [f"row_{i}" for i in range(n)] + [f"name_{i}" for i in range(n)]
        counts = [f"count_{i}" for i in range(n)]
        shares = [f"share_{i}" for i in range(n)]
        question = stage("question", "Read the question", 1.5, ["question"])
        bars = stage(
            "bars",
            "Draw a bar for each part, one box for each unit of the ratio",
            3.0,
            [*rows, *counts],
        )
        if params.kind == "simplify":
            steps = [
                question,
                bars,
                stage(
                    "groups",
                    f"Divide every part by the highest common factor, {_hcf(params.ratio)}",
                    3.0,
                    [f"group_{i}" for i in range(n)],
                    hide=counts,
                ),
                stage(
                    "simplest",
                    "The ratio in its simplest form",
                    2.5,
                    [*shares, "working"],
                    emphasise=["working"],
                ),
            ]
        else:
            known = {
                "share": "The total is all the units together",
                "part": "We know this part, so we know its units",
                "difference": "The difference is the extra units of the largest part",
            }[params.kind]
            brace = ["brace"] if params.kind in ("share", "difference") else []
            show_known = brace or [f"share_{params.known}"]
            steps = [
                question,
                bars,
                stage("known", known, 2.5, show_known, emphasise=show_known),
                stage(
                    "unit",
                    "Divide to find one unit",
                    3.0,
                    ["working", *(f"units_{i}" for i in range(n))],
                ),
                stage(
                    "shares",
                    "Each part is its number of units times one unit",
                    3.0,
                    [s for s in shares if s not in show_known],
                    morph=[("working", "answer")],
                    hide=counts,
                    emphasise=["answer"],
                ),
            ]

        def standard(s):
            return [combine("setup", s[1].description, 3.5, s[0], s[1]), *s[2:]]

        def concise(s):
            return [
                combine("setup", s[1].description, 3.5, s[0], s[1]),
                combine("working", "Find one unit, then each part", 4.0, *s[2:]),
            ]

        return by_level(level, steps, standard, concise)


def _hcf(ratio: list[int]) -> int:
    return reduce(gcd, ratio)


def _names(params: RatioSplitterParams) -> list[str]:
    return params.names or [chr(ord("A") + i) for i in range(len(params.ratio))]


def _unit(params: RatioSplitterParams) -> tuple[sp.Rational, int]:
    """One unit, and the number of units the known amount covers."""
    ratio = params.ratio
    units = {
        "share": sum(ratio),
        "part": ratio[params.known] if params.known < len(ratio) else 1,
        "difference": max(ratio) - min(ratio),
    }[params.kind]
    return exact(params.amount) / units, units


def _amount(value, money: bool) -> str:
    value = sp.nsimplify(value)
    if money:
        return rf"\${float(value):,.2f}".replace(",", "{,}")
    if value.is_integer:
        return str(int(value))
    return format_sf(value)


def _question(params: RatioSplitterParams, names: list[str]) -> str:
    ratio = " : ".join(str(r) for r in params.ratio)
    who = " : ".join(rf"\text{{{n}}}" for n in names)
    if params.kind == "simplify":
        return rf"\text{{Simplify }} {ratio}"
    amount = _amount(exact(params.amount), params.money)
    what = {
        "share": r"\text{total}",
        "part": rf"\text{{{names[params.known]}}}",
        "difference": r"\text{difference}",
    }[params.kind]
    return rf"{who} = {ratio}, \quad {what} = {amount}"


def _unit_latex(params: RatioSplitterParams) -> str:
    unit, units = _unit(params)
    amount = _amount(exact(params.amount), params.money)
    return rf"1 \text{{ unit}} = {amount} \div {units} = {_amount(unit, params.money)}"


def _answer_latex(params: RatioSplitterParams, names: list[str]) -> str:
    unit, _ = _unit(params)
    shares = [
        rf"\text{{{n}}} = {_amount(unit * r, params.money)}"
        for n, r in zip(names, params.ratio, strict=True)
    ]
    if params.kind != "share":
        shares.append(rf"\text{{total}} = {_amount(unit * sum(params.ratio), params.money)}")
    return r",\ ".join(shares)


def _simplify_latex(ratio: list[int]) -> str:
    h = _hcf(ratio)
    return (
        " : ".join(str(r) for r in ratio)
        + rf" = {' : '.join(str(r // h) for r in ratio)} \quad (\div {h})"
    )


def _known_brace(params: RatioSplitterParams, parts: dict, area) -> VGroup:
    """A brace on the right over all the rows (the total) or the extra units (difference)."""
    amount = _amount(exact(params.amount), params.money)
    rows = [parts[f"row_{i}"] for i in range(len(params.ratio))]
    if params.kind == "share":
        target = VGroup(*rows)
        brace = Brace(target, direction=[0, -1, 0], color=style.HIGHLIGHT_COLOUR)
        brace.next_to(target, [0, -1, 0], buff=0.1)
        text = label(rf"\text{{total}} = {amount}", colour=style.HIGHLIGHT_COLOUR, size=30)
        text.next_to(brace, [0, -1, 0], buff=0.08)
        return VGroup(brace, text)
    big = max(range(len(params.ratio)), key=lambda i: params.ratio[i])
    extra = VGroup(*rows[big][min(params.ratio) :])
    brace = Brace(extra, direction=[0, 1, 0], color=style.HIGHLIGHT_COLOUR)
    text = label(amount, colour=style.HIGHLIGHT_COLOUR, size=30).next_to(brace, [0, 1, 0], 0.05)
    return VGroup(brace, text)


def _failure(predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=[parameter]
    )
