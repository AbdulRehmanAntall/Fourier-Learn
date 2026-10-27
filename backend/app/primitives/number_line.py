"""NumberLine: numbers placed on a number line in order, and an inequality shown as an interval
with open or closed circles (4024 1.1, 1.4, 1.5, 1.9, 1.10, 2.6; PRIMITIVES.md #1).

Integers, fractions, decimals, surds and π are placed exactly where they belong, which shows
their order and how far apart they are. An inequality such as -2 < x ≤ 3 is drawn the O Level
way: an open circle where the end is not included, a filled circle where it is, and a line
between (or an arrow for an inequality with one end). Every position is computed by SymPy.
"""

import re
from typing import Annotated

import sympy as sp
from manim import BLACK, Arrow, Circle, Dot, Line, VGroup
from manim import NumberLine as ManimNumberLine
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    format_sf,
    latex_value,
    parse_expression,
    written_latex,
)

Number = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
Inequality = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=40)]
_PART = re.compile(r"(<=|>=|<|>)")
_TEX = {"<": "<", "<=": r"\leq", ">": ">", ">=": r"\geq"}


class NumberLineParams(PrimitiveParams):
    numbers: list[Number] = Field(
        default=[],
        max_length=6,
        description='Numbers to place, e.g. ["3/4", "-1.5", "sqrt(2)", "pi"]',
    )
    inequality: Inequality | None = Field(
        default=None, description='An inequality in x to show, e.g. "-2 < x <= 3" or "x >= 1"'
    )
    integers_only: bool = Field(
        default=False, description="Also list the integers that satisfy the inequality"
    )


class NumberLine(StagedPrimitive[NumberLineParams]):
    primitive_id = "NumberLine"
    version = "1"
    topic = "Number"
    params_model = NumberLineParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("line", "*"),
            ("interval*", "*"),
            ("number_*", "number_*"),
            ("integer_dots", "*"),
        ],
    )

    def default_params(self) -> NumberLineParams:
        return NumberLineParams(numbers=["3/4", "-1.5", "sqrt(2)"], inequality="-2 < x <= 3")

    def validate(self, params: NumberLineParams) -> list[PredicateFailure]:
        if not params.numbers and params.inequality is None:
            return [
                _failure(
                    "consistency",
                    "something_to_show",
                    "give numbers, an inequality or both",
                    "numbers",
                )
            ]
        for i, text in enumerate(params.numbers):
            try:
                value = parse_expression(text, set())
            except ExpressionError as error:
                return [_failure("parsing", "number_parses", str(error), f"numbers[{i}]")]
            if not (value.is_real and value.is_finite) or abs(float(value)) > 1000:
                return [
                    _failure(
                        "domain",
                        "real_number",
                        f"{text!r} is not a real number between -1000 and 1000",
                        f"numbers[{i}]",
                    )
                ]
        if params.inequality is not None:
            try:
                _interval(params.inequality)
            except _Bad as bad:
                return [_failure("parsing", "inequality_parses", str(bad), "inequality")]
        if params.integers_only and params.inequality is None:
            return [
                _failure(
                    "consistency",
                    "needs_inequality",
                    "integers_only needs an inequality",
                    "integers_only",
                )
            ]
        return []

    def computed_values(self, params: NumberLineParams) -> dict[str, str]:
        values = {}
        ordered = sorted(params.numbers, key=lambda t: float(parse_expression(t, set())))
        values["in_order"] = ", ".join(ordered)
        if params.inequality is not None and params.integers_only:
            values["integers"] = ", ".join(str(n) for n in _integers(params))
        return values

    def build(self, params: NumberLineParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        numbers = [(text, parse_expression(text, set())) for text in params.numbers]
        ends = [float(v) for _, v in numbers]
        interval = _interval(params.inequality) if params.inequality else None
        if interval:
            ends += [float(e) for e in (interval[0], interval[2]) if e is not None]
        if not numbers:  # an inequality alone: some room either side of its ends
            ends += [e + d for e in list(ends) for d in (-3, 3)]
        # Fit the line to the numbers, so close numbers (0.3, 0.33, 1/3) are told apart.
        span = (max(ends) - min(ends)) or 2.0
        lo, hi = min(ends) - 0.15 * span, max(ends) + 0.15 * span
        step = style.nice_step(hi - lo, 8)
        lo = sp.floor(lo / step) * step
        hi = sp.ceiling(hi / step) * step
        line = ManimNumberLine(
            x_range=[float(lo), float(hi), float(step)],
            length=area.width - 0.6,
            include_numbers=True,
            font_size=26,
            include_tip=False,
            decimal_number_config={"num_decimal_places": style._decimal_places(float(step))},
        ).move_to([area.center[0], area.center[1] - 0.3, 0])
        parts = {"line": line}
        if numbers:
            ordered = sorted(numbers, key=lambda pair: float(pair[1]))
            parts["order"] = text_line(r" < ".join(written_latex(t) for t, _ in ordered), upper)
        above = True
        for i, (text, value) in enumerate(sorted(numbers, key=lambda p: float(p[1])), start=1):
            point = line.n2p(float(value))
            tick = Line(
                point + [0, -0.18, 0],
                point + [0, 0.18, 0],
                color=style.POINT_COLOUR,
                stroke_width=5,
            )
            tex = written_latex(text) if not _is_decimal_only(text) else format_sf(value)
            name = label(tex, colour=style.POINT_COLOUR)
            # Alternate above and below so close numbers do not collide.
            name.next_to(point, [0, 1 if above else -1, 0], buff=0.55 if above else 0.75)
            arrow = Arrow(
                name.get_edge_center([0, -1 if above else 1, 0]),
                point,
                buff=0.05,
                stroke_width=2,
                color=style.POINT_COLOUR,
                max_tip_length_to_length_ratio=0.25,
            )
            parts[f"number_{i}"] = VGroup(tick, name, arrow)
            above = not above
        if interval:
            low, low_op, high, high_op = interval
            pieces = VGroup()
            start = line.n2p(float(low)) if low is not None else line.get_start()
            end = line.n2p(float(high)) if high is not None else line.get_end()
            start, end = start + [0, 1.2, 0], end + [0, 1.2, 0]
            colour = style.TANGENT_COLOUR
            if low is not None and high is not None:
                pieces.add(Line(start, end, color=colour, stroke_width=6))
            elif low is None:
                pieces.add(Arrow(end, start, buff=0, color=colour, stroke_width=6))
            else:
                pieces.add(Arrow(start, end, buff=0, color=colour, stroke_width=6))
            for value, closed, point in (
                (low, low_op == "<=", start),
                (high, high_op == "<=", end),
            ):
                if value is None:
                    continue
                pieces.add(
                    Circle(
                        radius=0.13,
                        color=colour,
                        stroke_width=4,
                        fill_color=colour if closed else BLACK,
                        fill_opacity=1,
                    ).move_to(point)
                )
            parts["interval"] = pieces
            parts["interval_text"] = text_line(_interval_latex(interval), lower)
            if params.integers_only:
                integers = _integers(params)
                parts["integers"] = text_line(
                    r"\text{integers: }" + r",\ ".join(str(n) for n in integers), lower
                )
                parts["integer_dots"] = VGroup(
                    *(Dot(line.n2p(n), color=style.POINT_COLOUR, radius=0.09) for n in integers)
                )
        return parts

    def stages(self, params: NumberLineParams, level) -> list[Stage]:
        count = len(params.numbers)
        steps = [stage("line", "Draw a number line", 1.5, ["line"])]
        for i in range(1, count + 1):
            steps.append(
                stage(
                    f"number_{i}",
                    "Place the next number" if i > 1 else "Place the smallest number",
                    2.0,
                    [f"number_{i}"],
                    emphasise=[f"number_{i}"],
                )
            )
        if count:
            steps.append(stage("order", "Read them in order from left to right", 2.0, ["order"]))
        if params.inequality:
            steps.append(
                stage(
                    "interval",
                    "An open circle leaves the end out; a filled circle includes it",
                    3.0,
                    ["interval", "interval_text"],
                    emphasise=["interval"],
                )
            )
            if params.integers_only:
                steps.append(
                    stage(
                        "integers",
                        "List the whole numbers inside the interval",
                        2.5,
                        ["integer_dots"],
                        morph=[("interval_text", "integers")],
                    )
                )

        def standard(s):
            places = [x for x in s if x.name.startswith("number_")]
            out = [s[0]]
            if places:
                out.append(combine("numbers", "Place each number on the line", 3.0, *places))
            out += [x for x in s[1:] if not x.name.startswith("number_")]
            return out

        def concise(s):
            placing = [
                x
                for x in s
                if x.name == "line" or x.name.startswith("number_") or x.name == "order"
            ]
            rest = [x for x in s if x not in placing]
            out = [combine("line", "The numbers on a number line", 3.5, *placing)]
            if rest:
                out.append(combine("interval", "The inequality as an interval", 3.5, *rest))
            return out

        return by_level(level, steps, standard, concise)


class _Bad(ValueError):
    pass


def _interval(text: str):
    """(low, low operator, high, high operator) with x between them; None for an open end. The
    operators are '<' or '<=' as seen from left to right."""
    pieces = [p.strip() for p in _PART.split(text)]
    flip = {"<": ">", ">": "<", "<=": ">=", ">=": "<="}
    try:
        if len(pieces) == 3:
            left, op, right = pieces
            if left == "x":  # x < 3, x >= 1
                bound = parse_expression(right, set())
                return (
                    (None, None, bound, op) if op in ("<", "<=") else (bound, flip[op], None, None)
                )
            if right == "x":  # 3 > x, 1 <= x
                bound = parse_expression(left, set())
                return (
                    (bound, op, None, None) if op in ("<", "<=") else (None, None, bound, flip[op])
                )
        if (
            len(pieces) == 5
            and pieces[2] == "x"
            and pieces[1] in ("<", "<=")
            and pieces[3] in ("<", "<=")
        ):
            low, high = parse_expression(pieces[0], set()), parse_expression(pieces[4], set())
            if float(low) >= float(high):
                raise _Bad("the lower end must be below the upper end")
            return low, pieces[1], high, pieces[3]
    except ExpressionError as error:
        raise _Bad(str(error)) from None
    raise _Bad(f"use a form such as 'x > 2', '-1 <= x' or '-2 < x <= 3', not {text!r}")


def _interval_latex(interval) -> str:
    low, low_op, high, high_op = interval
    text = "x"
    if low is not None:
        text = rf"{latex_value(low)} {_TEX[low_op]} {text}"
    if high is not None:
        text = rf"{text} {_TEX[high_op]} {latex_value(high)}"
    return text


def _integers(params: NumberLineParams) -> list[int]:
    low, low_op, high, high_op = _interval(params.inequality)
    lo = float(low) if low is not None else -1000
    hi = float(high) if high is not None else 1000
    out = []
    for n in range(int(sp.floor(lo)) - 1, int(sp.ceiling(hi)) + 2):
        above = n > lo or (low_op == "<=" and n == lo) if low is not None else True
        below = n < hi or (high_op == "<=" and n == hi) if high is not None else True
        if above and below:
            out.append(n)
    return out[:20]


def _is_decimal_only(text: str) -> bool:
    return bool(re.fullmatch(r"-?\d+(\.\d+)?", text.strip()))


def _failure(kind, predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(kind=kind, predicate=predicate, message=message, parameters=[parameter])
