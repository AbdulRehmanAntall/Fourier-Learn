"""PercentageBar: percentages as stretching bars: a percentage of an amount, an increase or a
decrease, the original amount before a change (reverse percentage), and a percentage change
(4024 1.13; PRIMITIVES.md #5).

The original amount is always the 100% bar, marked in tens of percent. An increase stretches it
beyond 100%, a decrease cuts it short, and a reverse percentage starts from the changed bar and
works back to 100% through 1%. Money is shown to the nearest cent; everything is exact.
"""

from typing import Annotated, Literal

from manim import DashedLine, Line, Rectangle, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_sf, latex_value

Amount = Annotated[float, Field(gt=0, le=1_000_000)]
Percent = Annotated[float, Field(gt=0, le=200)]
ORIGINAL, PART, CHANGED = style.CURVE_COLOUR, style.HIGHLIGHT_COLOUR, style.RISE_COLOUR


class PercentageBarParams(PrimitiveParams):
    kind: Literal["of", "increase", "decrease", "reverse_increase", "reverse_decrease", "change"]
    amount: Amount = Field(description="The original amount (for reverse: the amount after)")
    percent: Percent | None = Field(default=None, description="The percentage (not for change)")
    new_amount: Amount | None = Field(default=None, description="For change: the new amount")
    money: bool = Field(default=True, description="Show amounts as money ($, to the cent)")


class PercentageBar(StagedPrimitive[PercentageBarParams]):
    primitive_id = "PercentageBar"
    version = "1"
    topic = "Number"
    params_model = PercentageBarParams
    layout = LayoutContract(region=style.GRAPH_REGION, allowed_overlaps=[("bar_*", "bar_*")])

    def default_params(self) -> PercentageBarParams:
        return PercentageBarParams(kind="increase", amount=80, percent=15)

    def validate(self, params: PercentageBarParams) -> list[PredicateFailure]:
        if params.kind == "change":
            if params.new_amount is None:
                return [
                    _failure(
                        "needs_new_amount", "a percentage change needs new_amount", "new_amount"
                    )
                ]
            if params.new_amount == params.amount:
                return [_failure("amounts_differ", "the amount did not change", "new_amount")]
            if params.new_amount > 3 * params.amount:
                return [
                    _failure("change_fits", "the new amount is over 300% of the old", "new_amount")
                ]
            return []
        if params.percent is None:
            return [_failure("needs_percent", f"{params.kind} needs a percentage", "percent")]
        if params.kind in ("decrease", "reverse_decrease") and params.percent >= 100:
            return [_failure("decrease_below_100", "a decrease must be less than 100%", "percent")]
        if params.kind == "of" and params.percent > 100:
            return [_failure("of_at_most_100", "use increase for more than 100%", "percent")]
        return []

    def computed_values(self, params: PercentageBarParams) -> dict[str, str]:
        p = _Problem(params)
        return {"answer": p.money(p.answer), "multiplier": format_sf(p.multiplier, 6)}

    def build(self, params: PercentageBarParams, level):
        p = _Problem(params)
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        longest = max(p.original_percent, p.changed_percent, 100)
        width = area.width - 1.6
        unit = width / float(longest)  # scene units per 1%
        left = area.left + 1.2
        y_top, y_bottom = area.center[1] + 0.9, area.center[1] - 0.9
        parts = {
            "question": text_line(p.question_latex(), upper),
            "working": text_line(p.working_latex(), lower),
        }
        parts["bar_original"] = _bar(left, y_top, unit, 100, ORIGINAL, tens=True)
        parts["bar_original_label"] = _value_label(
            rf"100\% = {p.money_latex(p.original)}", left, y_top, unit * 100, ORIGINAL
        )
        if params.kind == "of":
            parts["bar_part"] = _bar(left, y_top, unit, float(p.percent), PART, height=0.7)
            parts["bar_part_label"] = _value_label(
                rf"{latex_value(p.percent)}\% = {p.money_latex(p.answer)}",
                left,
                y_top,
                unit * float(p.percent),
                PART,
                below=True,
            )
        else:
            parts["bar_changed"] = _bar(
                left, y_bottom, unit, float(p.changed_percent), CHANGED, tens=True
            )
            parts["bar_changed_label"] = _value_label(
                rf"{latex_value(p.changed_percent)}\% = {p.money_latex(p.changed)}",
                left,
                y_bottom,
                unit * float(p.changed_percent),
                CHANGED,
                below=True,
            )
            start = left + unit * float(min(100, p.changed_percent))
            end = left + unit * float(max(100, p.changed_percent))
            parts["bar_difference"] = VGroup(
                DashedLine(
                    [start, y_top + 0.45, 0],
                    [start, y_bottom - 0.45, 0],
                    color=style.TEXT_COLOUR,
                    stroke_width=2,
                ),
                Line(
                    [start, y_bottom + 0.42, 0],
                    [end, y_bottom + 0.42, 0],
                    color=style.TANGENT_COLOUR,
                    stroke_width=6,
                ),
            )
        parts["answer"] = text_line(p.answer_latex(), lower)
        return parts

    def stages(self, params: PercentageBarParams, level) -> list[Stage]:
        kind = params.kind
        question = stage("question", "Read the question", 1.5, ["question"])
        if kind == "of":
            steps = [
                question,
                stage(
                    "whole",
                    "The whole amount is 100%: cut it into tenths of 10% each",
                    2.5,
                    ["bar_original", "bar_original_label"],
                ),
                stage(
                    "part",
                    "Take the percentage of it",
                    3.0,
                    ["bar_part", "bar_part_label", "working"],
                ),
                stage(
                    "answer",
                    "Multiply by the percentage as a decimal",
                    2.5,
                    morph=[("working", "answer")],
                    emphasise=["answer"],
                ),
            ]
        elif kind.startswith("reverse"):
            steps = [
                question,
                stage(
                    "changed",
                    "The amount after the change is the bigger (or smaller) "
                    "percentage of the original",
                    3.0,
                    ["bar_changed", "bar_changed_label"],
                ),
                stage(
                    "one_percent",
                    "Divide to find 1%, or divide by the multiplier",
                    3.0,
                    ["working", "bar_difference"],
                ),
                stage(
                    "original",
                    "The original is 100%",
                    3.0,
                    ["bar_original", "bar_original_label"],
                    morph=[("working", "answer")],
                    emphasise=["bar_original_label"],
                ),
            ]
        else:
            what = {
                "increase": "Stretch it by the increase",
                "decrease": "Cut off the decrease",
                "change": "Compare the new amount with the original",
            }[kind]
            steps = [
                question,
                stage(
                    "original",
                    "The original amount is 100%",
                    2.5,
                    ["bar_original", "bar_original_label"],
                ),
                stage(
                    "changed",
                    what,
                    3.0,
                    ["bar_changed", "bar_changed_label", "bar_difference", "working"],
                ),
                stage(
                    "answer",
                    "Work it out",
                    2.5,
                    morph=[("working", "answer")],
                    emphasise=["answer"],
                ),
            ]

        def standard(s):
            return [combine("setup", s[1].description, 3.0, s[0], s[1]), *s[2:]]

        def concise(s):
            return [
                combine("setup", s[1].description, 3.0, s[0], s[1]),
                combine("answer", "Work it out", 3.5, *s[2:]),
            ]

        return by_level(level, steps, standard, concise)


class _Problem:
    def __init__(self, params: PercentageBarParams):
        self.params = params
        self.kind = params.kind
        amount = exact(params.amount)
        self.money_mode = params.money
        if params.kind == "change":
            self.original, self.changed = amount, exact(params.new_amount)
            self.percent = abs(self.changed - self.original) / self.original * 100
            self.original_percent, self.changed_percent = 100, self.changed / self.original * 100
            self.multiplier = self.changed / self.original
            self.answer = self.percent
            return
        self.percent = exact(params.percent)
        sign = -1 if params.kind in ("decrease", "reverse_decrease") else 1
        self.multiplier = 1 + sign * self.percent / 100
        if params.kind == "of":
            self.original, self.changed = amount, amount * self.percent / 100
            self.original_percent, self.changed_percent = 100, self.percent
            self.answer = self.changed
        elif params.kind in ("increase", "decrease"):
            self.original, self.changed = amount, amount * self.multiplier
            self.original_percent, self.changed_percent = 100, 100 * self.multiplier
            self.answer = self.changed
        else:
            self.changed, self.original = amount, amount / self.multiplier
            self.original_percent, self.changed_percent = 100, 100 * self.multiplier
            self.answer = self.original

    def money(self, value) -> str:
        if self.kind == "change":
            return format_sf(value)
        return f"{float(value):.2f}" if self.money_mode else format_sf(value)

    def money_latex(self, value) -> str:
        if self.money_mode:
            return rf"\${float(value):.2f}"
        return format_sf(value)

    def question_latex(self) -> str:
        p, k = self.params, self.kind
        amount = self.money_latex(exact(p.amount))
        if k == "of":
            return rf"{latex_value(self.percent)}\% \text{{ of }} {amount}"
        if k in ("increase", "decrease"):
            return rf"{amount} \text{{ {k}d by }} {latex_value(self.percent)}\%"
        if k.startswith("reverse"):
            word = "increase" if k == "reverse_increase" else "decrease"
            return rf"{amount} \text{{ after a }} {latex_value(self.percent)}\% \text{{ {word}}}"
        return rf"{amount} \to {self.money_latex(self.changed)}\text{{: percentage change?}}"

    def working_latex(self) -> str:
        k = self.kind
        if k == "of":
            return rf"{format_sf(self.percent / 100, 6)} \times {self.money_latex(self.original)}"
        if k in ("increase", "decrease"):
            return rf"\times {format_sf(self.multiplier, 6)}"
        if k.startswith("reverse"):
            return (
                rf"1\% = {self.money_latex(self.changed)} \div {latex_value(self.changed_percent)}"
            )
        return rf"\text{{change}} = {self.money_latex(abs(self.changed - self.original))}"

    def answer_latex(self) -> str:
        k = self.kind
        if k == "change":
            word = "increase" if self.changed > self.original else "decrease"
            return (
                rf"\frac{{{self.money_latex(abs(self.changed - self.original))}}}"
                rf"{{{self.money_latex(self.original)}}} \times 100 = "
                rf"{format_sf(self.percent)}\% \text{{ {word}}}"
            )
        if k.startswith("reverse"):
            return (
                rf"{self.money_latex(self.changed)} \div {format_sf(self.multiplier, 6)} = "
                rf"{self.money_latex(self.original)}"
            )
        if k == "of":
            return rf"= {self.money_latex(self.answer)}"
        return (
            rf"{self.money_latex(self.original)} \times {format_sf(self.multiplier, 6)} = "
            rf"{self.money_latex(self.changed)}"
        )


def _bar(left, y, unit, percent: float, colour, tens: bool = False, height: float = 0.55):
    group = VGroup(
        Rectangle(
            width=unit * percent,
            height=height,
            stroke_color=style.TEXT_COLOUR,
            stroke_width=2,
            fill_color=colour,
            fill_opacity=0.55,
        ).move_to([left + unit * percent / 2, y, 0])
    )
    if tens:
        for k in range(1, int(-(-percent // 10))):
            x = left + unit * 10 * k
            if x < left + unit * percent - 1e-6:
                group.add(
                    Line(
                        [x, y - height / 2, 0],
                        [x, y + height / 2, 0],
                        stroke_width=1.5,
                        color=style.TEXT_COLOUR,
                    )
                )
    return group


def _value_label(tex, left, y, length, colour, below=False):
    text = label(tex, colour=colour, size=32)
    offset = -0.55 if below else 0.55
    return text.move_to([left + length / 2, y + offset, 0])


def _failure(predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=[parameter]
    )
