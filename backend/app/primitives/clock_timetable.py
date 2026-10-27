"""ClockTimetable: time on a clock face in 12- and 24-hour form, time intervals by counting on,
journeys read from a timetable, and money changed between currencies (4024 1.15, 1.16;
PRIMITIVES.md #12).

An interval is counted on in hops, as O Level teaches: to the next whole hour, whole hours, then
the minutes left; it may run past midnight. A timetable journey reads the departure and arrival
in one column, then counts on the same way. Currency is a double number line: 1 unit of one
currency matches the rate in the other, so the amount is multiplied by the rate.
"""

import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal

import numpy as np
from manim import (
    ArcBetweenPoints,
    Circle,
    Dot,
    Line,
    SurroundingRectangle,
    VGroup,
)
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, make_table, split_columns, stack_boxes, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage

Time = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
]
Stop = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=14, pattern=r"^[A-Za-z][A-Za-z .]*$"
    ),
]
Code = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
DAY = 24 * 60


class ClockTimetableParams(PrimitiveParams):
    kind: Literal["convert", "interval", "timetable", "exchange"]
    start: Time | None = Field(default=None, description='24-hour time, e.g. "14:35"')
    end: Time | None = Field(default=None, description="For interval: the end time")
    stops: list[Stop] | None = Field(default=None, min_length=2, max_length=6)
    times: list[list[Time]] | None = Field(
        default=None, description="For timetable: one row of times per stop, a column per service"
    )
    service: Annotated[int, Field(ge=0, le=3)] = Field(default=0, description="Which column")
    board: Annotated[int, Field(ge=0, le=5)] = Field(default=0, description="Stop boarded at")
    leave: Annotated[int, Field(ge=0, le=5)] = Field(default=1, description="Stop left at")
    amount: Annotated[float, Field(gt=0, le=1_000_000)] | None = None
    rate: Annotated[float, Field(gt=0, le=100_000)] | None = Field(
        default=None, description="For exchange: 1 unit of from_currency in to_currency"
    )
    from_currency: Code = "USD"
    to_currency: Code = "PKR"


class ClockTimetable(StagedPrimitive[ClockTimetableParams]):
    primitive_id = "ClockTimetable"
    version = "1"
    topic = "Number"
    params_model = ClockTimetableParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("face", "hands"),
            ("table", "column"),
            ("table", "picked"),
            ("lines", "marks"),
            ("hops", "nodes"),
            ("column", "picked"),
            ("scale", "*"),
            ("lines", "result"),
        ],
    )

    def default_params(self) -> ClockTimetableParams:
        return ClockTimetableParams(kind="interval", start="09:35", end="14:20")

    def validate(self, params: ClockTimetableParams) -> list[PredicateFailure]:
        kind = params.kind
        if kind in ("convert", "interval") and params.start is None:
            return [_failure("needs_start", f"{kind} needs a start time", "start")]
        if kind == "interval":
            if params.end is None:
                return [_failure("needs_end", "an interval needs an end time", "end")]
            if params.end == params.start:
                return [_failure("times_differ", "the start and end are the same", "end")]
        if kind == "timetable":
            if params.stops is None or params.times is None:
                return [_failure("needs_table", "a timetable needs stops and times", "stops")]
            if len(params.times) != len(params.stops):
                return [_failure("one_row_each", "give one row of times per stop", "times")]
            columns = {len(row) for row in params.times}
            if len(columns) != 1 or not 1 <= columns.pop() <= 4:
                return [_failure("columns_match", "each stop needs 1 to 4 times", "times")]
            if params.service >= len(params.times[0]):
                return [_failure("service_exists", "no such service column", "service")]
            if not params.board < params.leave < len(params.stops):
                message = "board must come before leave, both among the stops"
                return [_failure("stops_in_order", message, "board", "leave")]
            for c in range(len(params.times[0])):
                column = [_minutes(row[c]) for row in params.times]
                if any(b <= a for a, b in zip(column, column[1:], strict=False)):
                    message = f"the times in service {c + 1} must increase down the column"
                    return [_failure("times_increase", message, "times")]
        if kind == "exchange" and (params.amount is None or params.rate is None):
            return [_failure("needs_amount_rate", "exchange needs amount and rate", "amount")]
        return []

    def computed_values(self, params: ClockTimetableParams) -> dict[str, str]:
        if params.kind == "convert":
            return {
                "twelve_hour": _twelve(_minutes(params.start)),
                "twenty_four_hour": params.start,
            }
        if params.kind == "exchange":
            return {"result": _money(_exchange(params))}
        start, end = _journey(params)
        return {"duration": _duration_text(end - start)}

    def build(self, params: ClockTimetableParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        kind = params.kind
        if kind == "convert":
            minutes = _minutes(params.start)
            clock_box, text_box = split_columns(area, [1, 1], gap=0.4)
            face, hands = _clock(minutes, clock_box)
            top, bottom = stack_boxes(text_box.shrink(0.6), 2, gap=0.4)
            return {
                "question": text_line(rf"\text{{Write {params.start} in 12-hour time}}", upper),
                "face": face,
                "hands": hands,
                "digital": text_line(rf"\text{{{params.start}}}", top, size=56),
                "twelve": text_line(
                    rf"\text{{{_twelve(minutes)}}}", bottom, size=56, colour=style.HIGHLIGHT_COLOUR
                ),
                "answer": text_line(
                    rf"\text{{{params.start} is {_twelve(minutes)}}}",
                    lower,
                    colour=style.HIGHLIGHT_COLOUR,
                ),
            }
        if kind == "exchange":
            return _exchange_parts(params, area, upper, lower)
        parts = {}
        if kind == "timetable":
            table_box, line_box = stack_boxes(area, 2, gap=0.3)
            rows = [
                [r"\text{" + s + "}", *(rf"\text{{{t}}}" for t in times)]
                for s, times in zip(params.stops, params.times, strict=True)
            ]
            table = make_table(rows, table_box, font_size=30)
            column = table.column(params.service + 1)
            parts["table"] = table.group
            parts["column"] = SurroundingRectangle(column, color=style.CURVE_COLOUR, buff=0.08)
            picked = VGroup(
                *(
                    SurroundingRectangle(
                        table.cells[r][params.service + 1], color=style.HIGHLIGHT_COLOUR, buff=0.04
                    )
                    for r in (params.board, params.leave)
                )
            )
            parts["picked"] = picked
            start, end = _journey(params)
            question = (
                rf"\text{{{params.stops[params.board]} to "
                rf"{params.stops[params.leave]}: how long?}}"
            )
        else:
            line_box = area
            start, end = _journey(params)
            question = rf"\text{{From {params.start} to {params.end}: how long?}}"
        parts["question"] = text_line(question, upper)
        nodes, hops = _timeline(start, end, line_box)
        parts["nodes"] = nodes
        parts["hops"] = hops
        total = " + ".join(_duration_text(b - a) for a, b in _legs(start, end))
        parts["working"] = text_line(rf"\text{{{total}}}", lower)
        parts["answer"] = text_line(
            rf"\text{{{total} = {_duration_text(end - start)}}}",
            lower,
            colour=style.HIGHLIGHT_COLOUR,
        )
        return parts

    def stages(self, params: ClockTimetableParams, level) -> list[Stage]:
        kind = params.kind
        question = stage("question", "Read the question", 1.5, ["question"])
        if kind == "convert":
            minutes = _minutes(params.start)
            after_noon = (
                "after noon, so take away 12 and write pm"
                if minutes >= 12 * 60
                else ("before noon, so it is am")
            )
            steps = [
                question,
                stage("clock", "Here it is on a clock face", 2.5, ["face", "hands", "digital"]),
                stage("twelve", f"It is {after_noon}", 3.0, ["twelve"], emphasise=["twelve"]),
                stage("answer", "So in 12-hour time", 2.0, ["answer"]),
            ]
        elif kind == "exchange":
            steps = [
                question,
                stage(
                    "unit",
                    f"1 {params.from_currency} is worth {_plain(params.rate)} {params.to_currency}",
                    3.0,
                    ["lines", "marks"],
                ),
                stage("scale", "Multiply both lines by the same number", 3.0, ["scale", "working"]),
                stage(
                    "answer",
                    "So the amount is",
                    2.5,
                    ["result"],
                    morph=[("working", "answer")],
                    emphasise=["answer"],
                ),
            ]
        else:
            read = (
                [
                    stage(
                        "read",
                        "Find the service and read the two times in its column",
                        3.5,
                        ["table", "column", "picked"],
                        emphasise=["picked"],
                    )
                ]
                if kind == "timetable"
                else []
            )
            steps = [
                question,
                *read,
                stage(
                    "count",
                    "Count on: to the next whole hour, whole hours, then the minutes",
                    4.0,
                    ["nodes", "hops", "working"],
                ),
                stage(
                    "answer",
                    "Add up the hops",
                    2.5,
                    morph=[("working", "answer")],
                    emphasise=["answer"],
                ),
            ]

        def standard(s):
            return [combine("setup", s[1].description, 3.5, s[0], s[1]), *s[2:]]

        def concise(s):
            return [
                combine("setup", s[1].description, 3.5, s[0], s[1]),
                combine("rest", "Work it out", 4.0, *s[2:]),
            ]

        return by_level(level, steps, standard, concise)


def _minutes(text: str) -> int:
    hours, minutes = text.split(":")
    return int(hours) * 60 + int(minutes)


def _clock_text(minutes: int) -> str:
    minutes %= DAY
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _twelve(minutes: int) -> str:
    hours, mins = divmod(minutes % DAY, 60)
    suffix = "am" if hours < 12 else "pm"
    return f"{(hours - 1) % 12 + 1}:{mins:02d} {suffix}"


def _duration_text(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} h {mins} min"
    return f"{hours} h" if hours else f"{mins} min"


def _journey(params: ClockTimetableParams) -> tuple[int, int]:
    """Start and end in minutes; an end before the start is the next day."""
    if params.kind == "timetable":
        start = _minutes(params.times[params.board][params.service])
        end = _minutes(params.times[params.leave][params.service])
    else:
        start, end = _minutes(params.start), _minutes(params.end)
    return start, end + DAY if end <= start else end


def _legs(start: int, end: int) -> list[tuple[int, int]]:
    """Counting on: to the next whole hour, the whole hours, then the minutes left."""
    first = -(-start // 60) * 60
    last = end // 60 * 60
    if first >= last:
        return [(start, end)]
    points = [start, first, last, end]
    return [(a, b) for a, b in zip(points, points[1:], strict=False) if b > a]


def _timeline(start: int, end: int, box) -> tuple[VGroup, VGroup]:
    legs = _legs(start, end)
    points = [legs[0][0]] + [b for _, b in legs]
    y = box.center[1] - 0.3
    width = box.width - 1.2
    xs = [box.left + 0.6 + width * i / (len(points) - 1) for i in range(len(points))]
    nodes = VGroup(Line([xs[0], y, 0], [xs[-1], y, 0], stroke_width=3))
    for x, t in zip(xs, points, strict=True):
        nodes.add(Dot([x, y, 0], color=style.POINT_COLOUR))
        nodes.add(
            label(rf"\text{{{_clock_text(t)}}}", size=30).next_to([x, y, 0], [0, -1, 0], buff=0.25)
        )
    hops = VGroup()
    for i, (a, b) in enumerate(legs):
        arc = ArcBetweenPoints(
            [xs[i], y + 0.1, 0],
            [xs[i + 1], y + 0.1, 0],
            angle=-1.2,
            color=style.RUN_COLOUR,
            stroke_width=3,
        )
        text = label(rf"+\text{{{_duration_text(b - a)}}}", colour=style.RUN_COLOUR, size=28)
        hops.add(arc, text.next_to(arc, [0, 1, 0], buff=0.1))
    return nodes, hops


def _clock(minutes: int, box) -> tuple[VGroup, VGroup]:
    radius = min(box.width, box.height) / 2 - 0.2
    centre = box.center
    face = VGroup(Circle(radius=radius, color=style.TEXT_COLOUR, stroke_width=4).move_to(centre))
    for hour in range(1, 13):
        angle = math.pi / 2 - hour * math.pi / 6
        direction = [math.cos(angle), math.sin(angle), 0]
        outer = centre + radius * 0.95 * np.array(direction)
        inner = centre + radius * 0.85 * np.array(direction)
        face.add(Line(inner, outer, stroke_width=3))
        face.add(label(str(hour), size=26).move_to(centre + radius * 0.7 * np.array(direction)))
    hours, mins = divmod(minutes % (12 * 60), 60)
    hands = VGroup()
    for turn, length, width, colour in (
        ((hours + mins / 60) / 12, 0.42, 7, style.TEXT_COLOUR),
        (mins / 60, 0.6, 4, style.HIGHLIGHT_COLOUR),
    ):
        angle = math.pi / 2 - turn * 2 * math.pi
        tip = [
            centre[0] + radius * length * math.cos(angle),
            centre[1] + radius * length * math.sin(angle),
            0,
        ]
        hands.add(Line(centre, tip, stroke_width=width, color=colour))
    hands.add(Dot(centre, radius=0.07, color=style.TEXT_COLOUR))
    return face, hands


def _exchange(params: ClockTimetableParams) -> Decimal:
    return Decimal(str(params.amount)) * Decimal(str(params.rate))


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _plain(value: float) -> str:
    return format(Decimal(str(value)).normalize(), "f")


def _exchange_parts(params: ClockTimetableParams, area, upper, lower) -> dict:
    a, b = params.from_currency, params.to_currency
    amount, rate = _plain(params.amount), _plain(params.rate)
    result = _money(_exchange(params))
    y_top, y_bottom = area.center[1] + 0.8, area.center[1] - 0.8
    left, right = area.left + 1.6, area.right - 0.4
    x_one = left + (right - left) * 0.25
    lines = VGroup(
        Line([left, y_top, 0], [right, y_top, 0], stroke_width=3),
        Line([left, y_bottom, 0], [right, y_bottom, 0], stroke_width=3),
        label(rf"\text{{{a}}}", colour=style.CURVE_COLOUR, size=32).move_to(
            [area.left + 0.7, y_top, 0]
        ),
        label(rf"\text{{{b}}}", colour=style.RUN_COLOUR, size=32).move_to(
            [area.left + 0.7, y_bottom, 0]
        ),
    )
    marks = VGroup()
    for x, top_text, bottom_text in ((left, "0", "0"), (x_one, "1", rate)):
        marks.add(Line([x, y_top - 0.12, 0], [x, y_top + 0.12, 0], stroke_width=3))
        marks.add(Line([x, y_bottom - 0.12, 0], [x, y_bottom + 0.12, 0], stroke_width=3))
        marks.add(label(top_text, size=30).next_to([x, y_top, 0], [0, 1, 0], buff=0.2))
        marks.add(label(bottom_text, size=30).next_to([x, y_bottom, 0], [0, -1, 0], buff=0.2))
    scale = VGroup()
    for y, side in ((y_top, 1), (y_bottom, -1)):
        arc = ArcBetweenPoints(
            [x_one, y + side * 0.6, 0],
            [right, y + side * 0.6, 0],
            angle=-0.8 * side,
            color=style.HIGHLIGHT_COLOUR,
        )
        text = label(rf"\times {amount}", colour=style.HIGHLIGHT_COLOUR, size=28)
        scale.add(arc, text.next_to(arc, [0, side, 0], buff=0.08))
    result_marks = VGroup(
        Line([right, y_top - 0.12, 0], [right, y_top + 0.12, 0], stroke_width=3),
        Line([right, y_bottom - 0.12, 0], [right, y_bottom + 0.12, 0], stroke_width=3),
        label(amount, size=30).next_to([right, y_top, 0], [0, 1, 0], buff=0.2),
        label(result, colour=style.HIGHLIGHT_COLOUR, size=30).next_to(
            [right, y_bottom, 0], [0, -1, 0], buff=0.2
        ),
    )
    return {
        "question": text_line(rf"\text{{Change {amount} {a} to {b}: 1 {a} = {rate} {b}}}", upper),
        "lines": lines,
        "marks": marks,
        "scale": scale,
        "result": result_marks,
        "working": text_line(rf"{amount} \times {rate}", lower),
        "answer": text_line(
            rf"{amount} \times {rate} = {result} \text{{ {b}}}",
            lower,
            colour=style.HIGHLIGHT_COLOUR,
        ),
    }


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
