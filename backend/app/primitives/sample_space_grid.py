"""SampleSpaceGrid: the possibility diagram for two events (two dice, a die and a coin, two
spinners) with the outcomes that satisfy the condition highlighted, and P = favourable ÷ total
(4024 8.1, 8.3; PRIMITIVES.md #46).

The grid shows every combined outcome once: the sum, product or difference of the two values, or
the pair itself. The outcomes are equally likely, so the probability is the number highlighted
over the number of cells.
"""

import operator
from typing import Annotated, Literal

import sympy as sp
from manim import Rectangle, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, make_table, split_columns, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import latex_number

Value = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9]{1,3}$")]
Comparison = Literal["=", ">", "<", ">=", "<=", "even", "odd", "multiple_of", "contains"]
COMPARE = {
    "=": operator.eq,
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
}
WORDS = {
    "=": "equal to",
    ">": "greater than",
    "<": "less than",
    ">=": "at least",
    "<=": "at most",
    "multiple_of": "a multiple of",
}


class SampleSpaceGridParams(PrimitiveParams):
    first: list[Value] = Field(min_length=2, max_length=8, description='e.g. ["1", ..., "6"]')
    second: list[Value] = Field(min_length=2, max_length=8)
    first_name: Annotated[str, StringConstraints(max_length=16)] = "first die"
    second_name: Annotated[str, StringConstraints(max_length=16)] = "second die"
    combine: Literal["sum", "product", "difference", "pair"] = "sum"
    condition: Comparison = "="
    value: Annotated[int, Field(ge=-100, le=100)] | None = Field(
        default=None, description="The number in the condition (not for even or odd)"
    )
    contains: Value | None = Field(default=None, description='For contains: e.g. "6"')


class SampleSpaceGrid(StagedPrimitive[SampleSpaceGridParams]):
    primitive_id = "SampleSpaceGrid"
    version = "1"
    topic = "Probability"
    params_model = SampleSpaceGridParams
    layout = LayoutContract(
        region=style.GRAPH_REGION, allowed_overlaps=[("grid", "marks"), ("marks", "grid")]
    )

    def default_params(self) -> SampleSpaceGridParams:
        dice = [str(i) for i in range(1, 7)]
        return SampleSpaceGridParams(first=dice, second=dice, condition="=", value=7)

    def validate(self, params: SampleSpaceGridParams) -> list[PredicateFailure]:
        numeric = all(v.lstrip("-").isdigit() for v in params.first + params.second)
        if params.combine != "pair" and not numeric:
            return [_failure("numbers", f"a {params.combine} needs numbers", "first", "second")]
        if params.condition == "contains":
            if params.contains is None:
                return [_failure("needs_contains", "give the value to look for", "contains")]
            return []
        if params.combine == "pair":
            return [_failure("pair_contains", "for pairs use the contains condition", "condition")]
        if params.condition not in ("even", "odd") and params.value is None:
            return [_failure("needs_value", "give the number in the condition", "value")]
        if params.condition == "multiple_of" and params.value == 0:
            return [_failure("nonzero", "a multiple of 0 is not useful", "value")]
        return []

    def computed_values(self, params: SampleSpaceGridParams) -> dict[str, str]:
        hits, total = _count(params)
        return {
            "favourable": str(hits),
            "total": str(total),
            "probability": str(sp.Rational(hits, total)),
        }

    def build(self, params: SampleSpaceGridParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        grid_box, working_box = split_columns(area, [1.6, 1], gap=0.3)
        symbol = {"sum": "+", "product": r"\times", "difference": "-", "pair": ""}[params.combine]
        header = [symbol] + [rf"\text{{{v}}}" for v in params.second]
        rows = [header]
        colours = [[None] * len(header)]
        for a in params.first:
            row, colour = [rf"\text{{{a}}}"], [None]
            for b in params.second:
                result = _result(params, a, b)
                row.append(rf"\text{{{result}}}" if params.combine == "pair" else str(result))
                colour.append(style.HIGHLIGHT_COLOUR if _wanted(params, a, b) else None)
            rows.append(row)
            colours.append(colour)
        # room above and to the left for the names of the two events
        table_box = style.Box(
            grid_box.left + 0.45, grid_box.right, grid_box.bottom, grid_box.top - 0.4
        )
        table = make_table(rows, table_box, font_size=30, colours=colours)
        marks = VGroup()
        for r, a in enumerate(params.first, start=1):
            for c, b in enumerate(params.second, start=1):
                if _wanted(params, a, b):
                    cell = table.cells[r][c]
                    marks.add(
                        Rectangle(
                            width=cell.width + 0.18,
                            height=cell.height + 0.14,
                            stroke_width=0,
                            fill_color=style.HIGHLIGHT_COLOUR,
                            fill_opacity=0.25,
                        ).move_to(cell)
                    )
        hits, total = _count(params)
        p = sp.Rational(hits, total)
        parts = {
            "grid": table.group,
            "marks": marks,
            "name_top": label(rf"\text{{{params.second_name}}}", size=24)
            .next_to(table.group, [0, 1, 0], buff=0.1)
            .set_x(VGroup(*table.cells[0][1:]).get_x()),
            "name_side": label(rf"\text{{{params.first_name}}}", size=24)
            .rotate(1.5708)
            .next_to(table.group, [-1, 0, 0], buff=0.1)
            .set_y(VGroup(*(row[0] for row in table.cells[1:])).get_y()),
        }
        lines = [
            rf"\text{{{total} equally likely outcomes}}",
            rf"\text{{{hits} of them are wanted}}",
            rf"P = \frac{{{hits}}}{{{total}}}" + (rf" = {latex_number(p)}" if p.q != total else ""),
        ]
        mobjects = [label(t, size=30) for t in lines]
        group = VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.3)
        style.fit_inside(group, working_box)
        for i, mob in enumerate(mobjects, start=1):
            parts[f"row_{i}"] = mob
        parts["question"] = text_line(_question(params), upper, size=34)
        parts["answer"] = text_line(rf"P = {latex_number(p)}", lower, colour=style.HIGHLIGHT_COLOUR)
        return parts

    def stages(self, params: SampleSpaceGridParams, level) -> list[Stage]:
        steps = [
            stage(
                "grid",
                f"Every outcome once: one row for each value of the "
                f"{params.first_name}, one column for each of the {params.second_name}",
                4.0,
                ["question", "grid", "name_top", "name_side", "row_1"],
            ),
            stage(
                "mark", "Mark the outcomes we want", 3.5, ["marks", "row_2"], emphasise=["marks"]
            ),
            stage(
                "probability",
                "Probability is the number wanted over the total",
                3.0,
                ["row_3", "answer"],
                emphasise=["answer"],
            ),
        ]

        def concise(s):
            return [s[0], combine("result", "Mark them and count", 4.0, s[1], s[2])]

        return by_level(level, steps, lambda s: s, concise)


def _result(params: SampleSpaceGridParams, a: str, b: str):
    if params.combine == "pair":
        return f"{a},{b}"
    x, y = int(a), int(b)
    return {"sum": x + y, "product": x * y, "difference": abs(x - y)}[params.combine]


def _wanted(params: SampleSpaceGridParams, a: str, b: str) -> bool:
    if params.condition == "contains":
        return params.contains in (a, b)
    result = _result(params, a, b)
    if params.condition == "even":
        return result % 2 == 0
    if params.condition == "odd":
        return result % 2 == 1
    if params.condition == "multiple_of":
        return result % params.value == 0
    return COMPARE[params.condition](result, params.value)


def _count(params: SampleSpaceGridParams) -> tuple[int, int]:
    hits = sum(_wanted(params, a, b) for a in params.first for b in params.second)
    return hits, len(params.first) * len(params.second)


def _question(params: SampleSpaceGridParams) -> str:
    if params.condition == "contains":
        return rf"P(\text{{at least one {params.contains}}})"
    what = params.combine
    if params.condition in ("even", "odd"):
        return rf"P(\text{{the {what} is {params.condition}}})"
    return rf"P(\text{{the {what} is {WORDS[params.condition]} {params.value}}})"


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
