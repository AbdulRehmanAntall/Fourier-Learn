"""StandardForm: a number written as A × 10ⁿ by moving the decimal point one place at a time,
and multiplying or dividing in standard form with the index laws (4024 1.7, 1.8; PRIMITIVES.md
#7, powers of ten).

The digits stay where they are while the decimal point hops until one non-zero digit is in front
of it: each hop is one power of ten, left for a big number and right for a small one. For two
numbers, the front parts are multiplied (or divided) and the powers added (or subtracted), then
the result is put back into standard form. Every value is exact.
"""

import re
from decimal import Decimal
from typing import Annotated, Literal

from manim import ArcBetweenPoints, Dot, MathTex, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage

Number = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^\d{1,14}(\.\d{1,14})?$")
]


class StandardFormParams(PrimitiveParams):
    number: Number = Field(
        description='A positive number written out, e.g. "34500000" or "0.000345"'
    )
    operation: Literal["none", "multiply", "divide"] = "none"
    other: Number | None = Field(default=None, description="The second number, for × or ÷")


class StandardForm(StagedPrimitive[StandardFormParams]):
    primitive_id = "StandardForm"
    version = "1"
    topic = "Number"
    params_model = StandardFormParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("digits", "hops"), ("point", "*"), ("point_end", "*")],
    )

    def default_params(self) -> StandardFormParams:
        return StandardFormParams(number="34500000")

    def validate(self, params: StandardFormParams) -> list[PredicateFailure]:
        if Decimal(params.number) == 0:
            return [_failure("nonzero", "0 has no standard form", "number")]
        digits, point, first = _layout(params.number)
        if abs(first + 1 - point) > 12:
            return [_failure("hops_fit", "more than 12 places to move", "number")]
        if params.operation != "none":
            if params.other is None:
                return [
                    _failure("needs_other", "multiply and divide need a second number", "other")
                ]
            if Decimal(params.other) == 0:
                return [_failure("nonzero", "the second number is 0", "other")]
        return []

    def computed_values(self, params: StandardFormParams) -> dict[str, str]:
        a, n = _standard(Decimal(params.number))
        values = {"mantissa": _plain(a), "power": str(n), "standard_form": f"{_plain(a)} x 10^{n}"}
        if params.operation != "none":
            ra, rn = _result(params)
            values["result"] = f"{_plain(ra)} x 10^{rn}"
        return values

    def build(self, params: StandardFormParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        digits, point, first = _layout(params.number)
        a, n = _standard(Decimal(params.number))
        size = min(56, (area.width - 1.0) / (len(digits) * 0.42) * 30)
        glyphs = VGroup(*(MathTex(d, font_size=size) for d in digits))
        glyphs.arrange(buff=0.28 * size / 48).move_to(area.center + [0, 1.4, 0])
        gap = glyphs[1].get_left()[0] - glyphs[0].get_right()[0] if len(glyphs) > 1 else 0.2

        def slot(i: int):
            """The position between digit i-1 and digit i (i = len means after the last)."""
            if i <= 0:
                x = glyphs[0].get_left()[0] - gap / 2
            elif i >= len(glyphs):
                x = glyphs[-1].get_right()[0] + gap / 2
            else:
                x = (glyphs[i - 1].get_right()[0] + glyphs[i].get_left()[0]) / 2
            return [x, glyphs.get_bottom()[1] + 0.06, 0]

        target = first + 1
        hops = VGroup()
        step = 1 if target > point else -1
        for k, i in enumerate(range(point, target, step)):
            arc = ArcBetweenPoints(
                slot(i),
                slot(i + step),
                angle=-1.6 if step > 0 else 1.6,
                color=style.TANGENT_COLOUR,
                stroke_width=3,
            )
            arc.shift([0, -0.15, 0])
            number = label(str(k + 1), colour=style.TANGENT_COLOUR, size=26)
            number.next_to(arc, [0, -1, 0], buff=0.05)
            hops.add(VGroup(arc, number))
        parts = {
            "digits": glyphs,
            "point": Dot(slot(point), radius=0.07, color=style.HIGHLIGHT_COLOUR),
            "point_end": Dot(slot(target), radius=0.07, color=style.HIGHLIGHT_COLOUR),
            "hops": hops,
            "question": text_line(_question(params), upper),
            "answer": text_line(rf"{_written(params.number)} = {_sf_latex(a, n)}", lower),
            "rule": label(
                rf"\text{{{abs(n)} place{'s' if abs(n) != 1 else ''} "
                rf"{'left' if n > 0 else 'right'}: }} 10^{{{n}}}",
                colour=style.TANGENT_COLOUR,
                size=36,
            ).move_to(area.center + [0, -0.4, 0]),
        }
        if params.operation != "none":
            b, m = _standard(Decimal(params.other))
            ra, rn = _result(params)
            symbol = r"\times" if params.operation == "multiply" else r"\div"
            powers = (
                f"{n} + {_bracket(m)}" if params.operation == "multiply" else f"{n} - {_bracket(m)}"
            )
            product = a * b if params.operation == "multiply" else a / b
            power = n + m if params.operation == "multiply" else n - m
            lines = [
                rf"\left({_sf_latex(a, n)}\right) {symbol} \left({_sf_latex(b, m)}\right)",
                rf"= ({_plain(a)} {symbol} {_plain(b)}) \times 10^{{{powers}}}",
                rf"= {_plain(product.normalize())} \times 10^{{{power}}}",
                rf"= {_sf_latex(ra, rn)}",
            ]
            for i, tex in enumerate(lines, start=1):
                parts[f"calc_{i}"] = MathTex(tex, font_size=36)
            calc = VGroup(*(parts[f"calc_{i}"] for i in range(1, 5)))
            calc.arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.25)
            style.fit_inside(
                calc, style.Box(area.left, area.right, area.bottom, area.center[1] - 1.05)
            )
        return parts

    def stages(self, params: StandardFormParams, level) -> list[Stage]:
        _, n = _standard(Decimal(params.number))
        steps = [
            stage("question", "Here is the number", 1.5, ["question", "digits", "point"]),
            stage(
                "hops",
                "Move the decimal point until one non-zero digit is in front of it, "
                "counting the places",
                3.5,
                ["hops", "point_end"],
                hide=["point"],
            ),
            stage(
                "rule",
                f"Moving {abs(n)} place{'s' if abs(n) != 1 else ''} "
                f"{'left' if n > 0 else 'right'} means times 10 to the power {n}",
                2.5,
                ["rule"],
                emphasise=["rule"],
            ),
            stage("answer", "So in standard form", 2.0, ["answer"], emphasise=["answer"]),
        ]
        if params.operation != "none":
            word = "Multiply" if params.operation == "multiply" else "Divide"
            verb = "add" if params.operation == "multiply" else "subtract"
            steps += [
                stage("calc_1", "Now the calculation in standard form", 2.0, ["calc_1"]),
                stage(
                    "calc_2", f"{word} the front numbers; {verb} the powers of ten", 3.0, ["calc_2"]
                ),
                stage("calc_3", "Work them out", 2.0, ["calc_3"]),
                stage(
                    "calc_4",
                    "Put the answer back into standard form",
                    2.5,
                    ["calc_4"],
                    emphasise=["calc_4"],
                ),
            ]

        def standard(s):
            out = [
                combine("question", "Move the decimal point, counting the places", 3.5, s[0], s[1]),
                combine("answer", s[2].description, 2.5, s[2], s[3]),
            ]
            if len(s) > 4:
                out += [
                    combine(
                        "calc", "The calculation, front numbers and powers apart", 3.5, s[4], s[5]
                    ),
                    combine("result", "The result in standard form", 3.0, s[6], s[7]),
                ]
            return out

        def concise(s):
            out = [combine("convert", "Write it in standard form", 3.5, *s[:4])]
            if len(s) > 4:
                out.append(combine("calc", "The calculation", 3.5, *s[4:]))
            return out

        return by_level(level, steps, standard, concise)


def _layout(text: str) -> tuple[str, int, int]:
    """The digits without the point, where the point is (as a slot index) and where the first
    non-zero digit is."""
    whole, _, fraction = text.partition(".")
    digits = whole + fraction
    point = len(whole)
    first = next(i for i, d in enumerate(digits) if d != "0")
    return digits, point, first


def _standard(value: Decimal) -> tuple[Decimal, int]:
    sign, digits, exponent = value.normalize().as_tuple()
    n = len(digits) + exponent - 1
    return (value.scaleb(-n)).normalize(), n


def _result(params: StandardFormParams) -> tuple[Decimal, int]:
    a, n = _standard(Decimal(params.number))
    b, m = _standard(Decimal(params.other))
    value = (
        a * b * Decimal(10) ** (n + m)
        if params.operation == "multiply"
        else (a / b) * Decimal(10) ** (n - m)
    )
    return _standard(value.normalize())


def _plain(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        whole, fraction = text.split(".")
        if len(fraction) > 4:
            return f"{float(value):.4g}"
    return text


def _sf_latex(a: Decimal, n: int) -> str:
    return rf"{_plain(a)} \times 10^{{{n}}}"


def _bracket(m: int) -> str:
    return f"({m})" if m < 0 else str(m)


def _written(text: str) -> str:
    """A long number with thin spaces between groups of three digits, as written in O Level."""
    whole, _, fraction = text.partition(".")
    grouped = re.sub(r"(?<=\d)(?=(\d{3})+$)", r"\\,", whole)
    return grouped + ("." + fraction if fraction else "")


def _question(params: StandardFormParams) -> str:
    return rf"{_written(params.number)} = \ ? \times 10^{{n}}"


def _failure(predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=[parameter]
    )
