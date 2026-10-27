"""FractionModel: fractions as shaded bars and grids: equivalent fractions, adding and
subtracting over a common denominator, multiplying as an area, and dividing as "how many fit"
(4024 1.4, 1.6; PRIMITIVES.md #4).

Equivalent: cutting every part into k pieces does not change how much is shaded. Add or
subtract: both bars are cut into the same number of parts (the lowest common denominator) so
their parts can be counted together. Multiply: a/b of the columns and c/d of the rows of a
square overlap in ac/bd of it, the picture that fixes "multiplying makes bigger". Divide: count
how many pieces of size c/d fit into a/b. Every value is exact.
"""

from fractions import Fraction
from math import lcm
from typing import Annotated, Literal

from manim import MathTex, Rectangle, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage

FractionText = Annotated[str, StringConstraints(pattern=r"^\s*\d{1,2}\s*/\s*\d{1,2}\s*$")]
FIRST_COLOUR, SECOND_COLOUR = style.CURVE_COLOUR, style.RUN_COLOUR


class FractionModelParams(PrimitiveParams):
    operation: Literal["equivalent", "add", "subtract", "multiply", "divide"]
    first: FractionText = Field(description='The first fraction, e.g. "3/4"')
    second: FractionText | None = Field(
        default=None, description='The second fraction (not for "equivalent")'
    )
    factor: Annotated[int, Field(ge=2, le=6)] = Field(
        default=2, description="For equivalent: cut every part into this many pieces"
    )


class FractionModel(StagedPrimitive[FractionModelParams]):
    primitive_id = "FractionModel"
    version = "1"
    topic = "Number"
    params_model = FractionModelParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("bar_*", "bar_*"),
            ("grid", "*"),
            ("columns", "*"),
            ("rows", "*"),
            ("overlap", "*"),
        ],
    )

    def default_params(self) -> FractionModelParams:
        return FractionModelParams(operation="add", first="1/2", second="1/3")

    def validate(self, params: FractionModelParams) -> list[PredicateFailure]:
        first = _fraction(params.first)
        if first.denominator > 12 or first == 0 or first > 3:
            return [
                _failure(
                    "first_fits",
                    "the first fraction needs a denominator up to 12 and a value between 0 and 3",
                    "first",
                )
            ]
        if params.operation == "equivalent":
            if first.denominator * params.factor > 24:
                return [
                    _failure(
                        "equivalent_fits", "too many parts to draw; use a smaller factor", "factor"
                    )
                ]
            return []
        if params.second is None:
            return [
                _failure("needs_second", f"{params.operation} needs a second fraction", "second")
            ]
        second = _fraction(params.second)
        if second.denominator > 12 or second == 0 or second > 3:
            return [
                _failure(
                    "second_fits",
                    "the second fraction needs a denominator up to 12 and a value between 0 and 3",
                    "second",
                )
            ]
        if params.operation == "subtract" and second > first:
            return [
                _failure(
                    "difference_positive", "the second fraction is bigger than the first", "second"
                )
            ]
        if params.operation in ("add", "subtract"):
            if lcm(first.denominator, second.denominator) > 24:
                return [
                    _failure(
                        "common_fits",
                        "the common denominator is over 24, too many parts to draw",
                        "second",
                    )
                ]
            if params.operation == "add" and first + second > 3:
                return [_failure("sum_fits", "the sum is more than 3 wholes", "second")]
        if params.operation == "multiply" and (first > 1 or second > 1):
            return [
                _failure(
                    "proper_for_area", "the area model needs fractions up to 1", "first", "second"
                )
            ]
        if params.operation == "divide":
            parts = first / second
            if parts > 12 or (first.denominator * second.denominator) > 48:
                return [_failure("division_fits", "too many pieces to draw", "second")]
        return []

    def computed_values(self, params: FractionModelParams) -> dict[str, str]:
        result = _result(params)
        values = {"result": _text(result)}
        if result.denominator != 1 and result > 1:
            values["mixed"] = _mixed_text(result)
        return values

    def build(self, params: FractionModelParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        first = _fraction(params.first)
        result = _result(params)
        parts = {
            "question": text_line(_question_latex(params), upper),
            "answer": text_line(_answer_latex(params, result), lower),
        }
        width = min(area.width - 1.6, 6.0)
        left = area.center[0] - width / 2 + 0.5
        rows = [area.top - 0.6 - k * 1.25 for k in range(4)]
        if params.operation == "equivalent":
            k = params.factor
            parts["bar_first"] = _bar(
                first.numerator,
                first.denominator,
                left,
                rows[0],
                width,
                FIRST_COLOUR,
                label_tex=_latex(first),
            )
            parts["bar_split"] = _bar(
                first.numerator * k,
                first.denominator * k,
                left,
                rows[1],
                width,
                FIRST_COLOUR,
                label_tex=rf"\tfrac{{{first.numerator * k}}}"
                rf"{{{first.denominator * k}}}",
            )
            return parts
        second = _fraction(params.second)
        if params.operation in ("add", "subtract"):
            common = lcm(first.denominator, second.denominator)
            a, c = (
                first.numerator * common // first.denominator,
                second.numerator * common // second.denominator,
            )
            parts["bar_first"] = _bars(
                first, first.denominator, left, rows[0], width, FIRST_COLOUR, _latex(first)
            )
            parts["bar_second"] = _bars(
                second, second.denominator, left, rows[1], width, SECOND_COLOUR, _latex(second)
            )
            parts["bar_first_common"] = _bars(
                first, common, left, rows[0], width, FIRST_COLOUR, rf"\tfrac{{{a}}}{{{common}}}"
            )
            parts["bar_second_common"] = _bars(
                second, common, left, rows[1], width, SECOND_COLOUR, rf"\tfrac{{{c}}}{{{common}}}"
            )
            parts["bar_result"] = _bars(
                result, common, left, rows[2] - 0.3, width, style.RISE_COLOUR, _latex(result)
            )
            return parts
        if params.operation == "multiply":
            size = min(area.height - 1.7, width * 0.7)
            parts.update(_area_model(first, second, area.center + [0.3, -0.35, 0], size))
            return parts
        # Divide: the first fraction as a bar over a common denominator, measured in pieces of
        # the second.
        common = lcm(first.denominator, second.denominator)
        parts["bar_first"] = _bars(first, common, left, rows[0], width, FIRST_COLOUR, _latex(first))
        parts["bar_pieces"] = _pieces(first, second, left, rows[1], width)
        return parts

    def stages(self, params: FractionModelParams, level) -> list[Stage]:
        op = params.operation
        question = stage("question", "The calculation", 1.5, ["question"])
        answer = stage("answer", "So the answer is", 2.0, ["answer"], emphasise=["answer"])
        if op == "equivalent":
            steps = [
                question,
                stage("bar", "Shade the fraction of a bar", 2.5, ["bar_first"]),
                stage(
                    "split",
                    f"Cut every part into {params.factor}: the same amount is shaded",
                    3.0,
                    ["bar_split"],
                    emphasise=["bar_split"],
                ),
                answer,
            ]
        elif op in ("add", "subtract"):
            steps = [
                question,
                stage("bars", "Shade each fraction of a bar", 2.5, ["bar_first", "bar_second"]),
                stage(
                    "common",
                    "Cut both into the same number of equal parts",
                    3.0,
                    morph=[("bar_first", "bar_first_common"), ("bar_second", "bar_second_common")],
                ),
                stage(
                    "result",
                    f"{'Add' if op == 'add' else 'Take away'} the parts",
                    3.0,
                    ["bar_result"],
                    emphasise=["bar_result"],
                ),
                answer,
            ]
        elif op == "multiply":
            steps = [
                question,
                stage(
                    "columns",
                    "Shade the first fraction of the square's columns",
                    2.5,
                    ["grid", "columns"],
                ),
                stage("rows", "Shade the second fraction of its rows", 2.5, ["rows"]),
                stage(
                    "overlap",
                    "The answer is the part shaded twice",
                    3.0,
                    ["overlap"],
                    emphasise=["overlap"],
                ),
                answer,
            ]
        else:
            steps = [
                question,
                stage("bar", "Shade the first fraction of a bar", 2.5, ["bar_first"]),
                stage(
                    "pieces",
                    "Count how many pieces the size of the second fraction fit",
                    3.5,
                    ["bar_pieces"],
                    emphasise=["bar_pieces"],
                ),
                answer,
            ]

        def standard(s):
            return [combine("setup", s[1].description, 3.0, s[0], s[1]), *s[2:]]

        def concise(s):
            return [
                combine("setup", "The fractions as bars", 3.0, *s[:2]),
                combine("result", "The calculation in the picture", 3.5, *s[2:]),
            ]

        return by_level(level, steps, standard, concise)


def _fraction(text: str) -> Fraction:
    top, bottom = (int(t) for t in text.split("/"))
    if bottom == 0:
        raise ValueError("denominator 0")
    return Fraction(top, bottom)


def _result(params: FractionModelParams) -> Fraction:
    first = _fraction(params.first)
    if params.operation == "equivalent":
        return first
    second = _fraction(params.second)
    return {
        "add": first + second,
        "subtract": first - second,
        "multiply": first * second,
        "divide": first / second,
    }[params.operation]


def _latex(f: Fraction) -> str:
    return (
        str(f.numerator) if f.denominator == 1 else rf"\tfrac{{{f.numerator}}}{{{f.denominator}}}"
    )


def _text(f: Fraction) -> str:
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"


def _mixed_text(f: Fraction) -> str:
    whole, rest = divmod(f.numerator, f.denominator)
    return f"{whole} {rest}/{f.denominator}"


def _mixed_latex(f: Fraction) -> str:
    whole, rest = divmod(f.numerator, f.denominator)
    return rf"{whole}\tfrac{{{rest}}}{{{f.denominator}}}"


def _question_latex(params: FractionModelParams) -> str:
    first = _latex(_fraction(params.first))
    if params.operation == "equivalent":
        return rf"{first} = \ ?"
    symbol = {"add": "+", "subtract": "-", "multiply": r"\times", "divide": r"\div"}
    return rf"{first} {symbol[params.operation]} {_latex(_fraction(params.second))}"


def _answer_latex(params: FractionModelParams, result: Fraction) -> str:
    if params.operation == "equivalent":
        f, k = _fraction(params.first), params.factor
        return rf"{_latex(f)} = \tfrac{{{f.numerator * k}}}{{{f.denominator * k}}}"
    text = rf"{_question_latex(params)} = {_latex(result)}"
    if result.denominator != 1 and result > 1:
        text += rf" = {_mixed_latex(result)}"
    return text


def _bar(
    shaded: int,
    parts: int,
    left: float,
    y: float,
    width: float,
    colour,
    label_tex: str,
    height: float = 0.6,
) -> VGroup:
    """One whole as a bar of `parts` equal parts, the first `shaded` of them filled."""
    group = VGroup()
    cell = width / parts
    for k in range(parts):
        group.add(
            Rectangle(
                width=cell,
                height=height,
                stroke_width=2,
                stroke_color=style.TEXT_COLOUR,
                fill_color=colour,
                fill_opacity=0.7 if k < shaded else 0,
            ).move_to([left + (k + 0.5) * cell, y, 0])
        )
    group.add(_side_label(label_tex, colour).next_to(group, [-1, 0, 0], buff=0.2))
    return group


def _bars(value: Fraction, parts: int, left, y, width, colour, label_tex) -> VGroup:
    """A fraction up to 3 wholes as bars of `parts` parts each, side by side if it is over 1."""
    shaded = int(value * parts)  # whole parts: `parts` is a multiple of the denominator
    wholes = max(1, -(-shaded // parts))
    group = VGroup()
    each = width / wholes - 0.15 * (wholes - 1) / wholes
    for w in range(wholes):
        count = min(parts, max(0, shaded - w * parts))
        bar = _bar(count, parts, left + w * (each + 0.15), y, each, colour, label_tex)
        group.add(*bar[:-1])
        if w == 0:
            group.add(bar[-1])
    return group


def _area_model(first: Fraction, second: Fraction, centre, size) -> dict:
    b, d = first.denominator, second.denominator
    a, c = first.numerator, second.numerator
    cell_w, cell_h = size / b, size / d
    left, top = centre[0] - size / 2, centre[1] + size / 2
    grid, columns, rows, overlap = VGroup(), VGroup(), VGroup(), VGroup()
    for i in range(b):
        for j in range(d):
            box = Rectangle(
                width=cell_w, height=cell_h, stroke_width=2, stroke_color=style.TEXT_COLOUR
            ).move_to([left + (i + 0.5) * cell_w, top - (j + 0.5) * cell_h, 0])
            grid.add(box)
            if i < a:
                columns.add(box.copy().set_fill(FIRST_COLOUR, 0.45).set_stroke(width=0))
            if j < c:
                rows.add(box.copy().set_fill(SECOND_COLOUR, 0.45).set_stroke(width=0))
            if i < a and j < c:
                overlap.add(box.copy().set_fill(style.RISE_COLOUR, 0.9).set_stroke(width=0))
    columns.add(_side_label(_latex(first), FIRST_COLOUR).next_to(grid, [0, 1, 0], buff=0.15))
    rows.add(_side_label(_latex(second), SECOND_COLOUR).next_to(grid, [-1, 0, 0], buff=0.2))
    return {"grid": grid, "columns": columns, "rows": rows, "overlap": overlap}


def _pieces(first: Fraction, second: Fraction, left, y, width) -> VGroup:
    """Pieces the size of `second` laid along the first fraction's bar: the quotient."""
    wholes = max(1, -(-first.numerator // first.denominator))
    each = width / wholes
    group = VGroup()
    length = float(second) * each
    count = first / second
    full = int(count)
    for k in range(full):
        group.add(
            Rectangle(
                width=length - 0.04,
                height=0.45,
                stroke_width=2,
                stroke_color=style.TEXT_COLOUR,
                fill_color=SECOND_COLOUR,
                fill_opacity=0.7,
            ).move_to([left + (k + 0.5) * length, y, 0])
        )
    remainder = count - full
    if remainder:
        piece = Rectangle(
            width=float(remainder) * length - 0.04,
            height=0.45,
            stroke_width=2,
            stroke_color=style.TEXT_COLOUR,
            fill_color=SECOND_COLOUR,
            fill_opacity=0.35,
        )
        piece.move_to([left + full * length + float(remainder) * length / 2, y, 0])
        group.add(piece)
    group.add(_side_label(_latex(second), SECOND_COLOUR).next_to(group, [-1, 0, 0], 0.2))
    return group


def _side_label(tex: str, colour) -> MathTex:
    """A fraction beside a bar, at full size so it can be read."""
    return MathTex(tex.replace(r"\tfrac", r"\frac"), font_size=40, color=colour)


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
