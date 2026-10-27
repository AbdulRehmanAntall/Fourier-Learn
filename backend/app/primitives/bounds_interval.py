"""BoundsInterval: the limits of accuracy of a rounded value on a zoomed number line, and the
largest and smallest results of a calculation with rounded values (4024 1.10; PRIMITIVES.md
#11).

A value rounded to the nearest d lies within half of d either side: lower bound ≤ x < upper
bound, a closed circle at the lower bound and an open one at the upper. For a calculation, the
largest result comes from the bounds that push it up (upper + upper, upper − lower, upper ×
upper, upper ÷ lower) and the smallest from the opposite ones. Values are exact decimals.
"""

from decimal import Decimal
from typing import Annotated, Literal

from manim import BLACK, Circle, Dot, Line, Rectangle, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, stack_boxes, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf

Number = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{1,9}(\.\d{1,6})?$")]
Step = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{1,9}(\.\d{1,6})?$")]
Operation = Literal["none", "add", "subtract", "multiply", "divide"]
SYMBOL = {"add": "+", "subtract": "-", "multiply": r"\times", "divide": r"\div"}
# which bound of (first, second) gives the largest result; the smallest uses the opposite ones
LARGEST = {"add": ("u", "u"), "subtract": ("u", "l"), "multiply": ("u", "u"), "divide": ("u", "l")}


class BoundsIntervalParams(PrimitiveParams):
    value: Number = Field(description='The rounded value, e.g. "7.4"')
    nearest: Step | None = Field(default=None, description='Rounded to the nearest, e.g. "0.1"')
    sf: Annotated[int, Field(ge=1, le=6)] | None = Field(
        default=None, description="Or: rounded to this many significant figures"
    )
    letter: Annotated[str, StringConstraints(pattern=r"^[a-z]$")] = "x"
    operation: Operation = "none"
    other: Number | None = Field(default=None, description="The second rounded value")
    other_nearest: Step | None = None
    other_sf: Annotated[int, Field(ge=1, le=6)] | None = None
    other_letter: Annotated[str, StringConstraints(pattern=r"^[a-z]$")] = "y"


class BoundsInterval(StagedPrimitive[BoundsIntervalParams]):
    primitive_id = "BoundsInterval"
    version = "1"
    topic = "Number"
    params_model = BoundsIntervalParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("line_*", "line_*"),
            ("band_*", "*"),
            ("ends_*", "*"),
            ("value_*", "line_*"),
            ("value_*", "labels_*"),
            ("bound_labels_*", "*"),
        ],
    )

    def default_params(self) -> BoundsIntervalParams:
        return BoundsIntervalParams(value="7.4", nearest="0.1")

    def validate(self, params: BoundsIntervalParams) -> list[PredicateFailure]:
        checks = [("value", "nearest", "sf")]
        if params.operation != "none":
            if params.other is None:
                return [_failure("needs_other", "a calculation needs a second value", "other")]
            checks.append(("other", "other_nearest", "other_sf"))
        for value_name, nearest_name, sf_name in checks:
            nearest, sf = getattr(params, nearest_name), getattr(params, sf_name)
            if (nearest is None) == (sf is None):
                message = f"give exactly one of {nearest_name} and {sf_name}"
                return [_failure("one_accuracy", message, nearest_name, sf_name)]
            value = Decimal(getattr(params, value_name))
            if value == 0:
                return [_failure("nonzero", "the value is 0", value_name)]
            step = _step(value, nearest, sf)
            if step <= 0:
                return [_failure("positive_step", "the accuracy must be positive", nearest_name)]
            if value % step != 0:
                message = f"{value} is not rounded to the nearest {step}"
                return [_failure("value_rounded", message, value_name, nearest_name)]
            if step / 2 >= value:
                message = "the lower bound would not be positive"
                return [_failure("positive_bounds", message, nearest_name)]
        if params.operation == "divide" and _bounds(params, second=True)[0] <= 0:
            return [_failure("nonzero_divisor", "the divisor could be 0", "other")]
        if params.operation != "none" and params.letter == params.other_letter:
            return [_failure("letters_differ", "use different letters", "other_letter")]
        return []

    def computed_values(self, params: BoundsIntervalParams) -> dict[str, str]:
        lower, upper = _bounds(params)
        values = {"lower_bound": _text(lower), "upper_bound": _text(upper)}
        if params.operation != "none":
            largest, smallest = _extremes(params)
            values["largest"] = format_sf(largest, 6)
            values["smallest"] = format_sf(smallest, 6)
        return values

    def build(self, params: BoundsIntervalParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper_box, lower_box = style.title_lines(title)
        calculation = params.operation != "none"
        bands = stack_boxes(area, 3 if calculation else 1, gap=0.3)
        parts = {"question": text_line(_question(params), upper_box)}
        rows = [(False, bands[0])] + ([(True, bands[1])] if calculation else [])
        statements = []
        for key, (second, box) in zip(("x", "y"), rows, strict=False):
            line_parts = _number_line(params, second, box, compact=calculation)
            for name, mobject in line_parts.items():
                parts[f"{name}_{key}"] = mobject
            lo, hi = _bounds(params, second)
            letter = params.other_letter if second else params.letter
            statements.append(rf"{_text(lo)} \le {letter} < {_text(hi)}")
        if not calculation:
            parts["answer"] = text_line(statements[0], lower_box, colour=style.HIGHLIGHT_COLOUR)
            return parts
        parts["statements"] = text_line(r",\quad ".join(statements), lower_box)
        largest, smallest = _extremes(params)
        (bx, by), (sx, sy) = _choices(params)
        symbol = SYMBOL[params.operation]
        top, bottom = stack_boxes(bands[2], 2, gap=0.1)
        parts["largest"] = text_line(
            rf"\text{{largest}} = {_text(bx)} {symbol} {_text(by)} {_result(largest)}",
            top,
            colour=style.RISE_COLOUR,
            size=36,
        )
        parts["smallest"] = text_line(
            rf"\text{{smallest}} = {_text(sx)} {symbol} {_text(sy)} {_result(smallest)}",
            bottom,
            colour=style.TANGENT_COLOUR,
            size=36,
        )
        return parts

    def stages(self, params: BoundsIntervalParams, level) -> list[Stage]:
        step = _step(Decimal(params.value), params.nearest, params.sf)
        half = _text(step / 2)
        x_line = ["line_x", "labels_x", "value_x"]
        steps = [
            stage("question", "Here is the rounded value", 2.0, ["question", *x_line]),
            stage(
                "half",
                f"Rounded to the nearest {_text(step)}, it could be up to half of that, "
                f"{half}, either side",
                3.5,
                ["halves_x"],
            ),
            stage(
                "bounds",
                "The lower bound is included; the upper bound is not, because it would round up",
                3.5,
                ["band_x", "ends_x", "bound_labels_x"],
                emphasise=["ends_x"],
            ),
        ]
        if params.operation == "none":
            steps.append(
                stage(
                    "answer", "So the limits of accuracy are", 2.0, ["answer"], emphasise=["answer"]
                )
            )
        else:
            y_all = [
                f"{n}_y"
                for n in ("line", "labels", "value", "halves", "band", "ends", "bound_labels")
            ]
            steps += [
                stage("second", "The same for the second value", 3.0, [*y_all, "statements"]),
                stage(
                    "largest",
                    _largest_words(params.operation),
                    3.5,
                    ["largest"],
                    emphasise=["largest"],
                ),
                stage(
                    "smallest",
                    "For the smallest result, use the opposite bounds",
                    3.0,
                    ["smallest"],
                    emphasise=["smallest"],
                ),
            ]

        def standard(s):
            out = [s[0], combine("bounds", s[1].description, 4.0, s[1], s[2]), *s[3:]]
            return out

        def concise(s):
            out = [combine("bounds", "Half the accuracy either side", 4.5, *s[:3])]
            if len(s) > 4:
                return [*out, s[3], combine("result", "Largest and smallest", 4.0, *s[4:])]
            return [*out, *s[3:]]

        return by_level(level, steps, standard, concise)


def _step(value: Decimal, nearest: str | None, sf: int | None) -> Decimal:
    if nearest is not None:
        return Decimal(nearest)
    return Decimal(1).scaleb(value.adjusted() - sf + 1)


def _bounds(params: BoundsIntervalParams, second: bool = False) -> tuple[Decimal, Decimal]:
    if second:
        value = Decimal(params.other)
        step = _step(value, params.other_nearest, params.other_sf)
    else:
        value = Decimal(params.value)
        step = _step(value, params.nearest, params.sf)
    return value - step / 2, value + step / 2


def _choices(params: BoundsIntervalParams):
    """((largest x, largest y), (smallest x, smallest y))."""
    x, y = _bounds(params), _bounds(params, second=True)
    pick = {"u": 1, "l": 0}
    bx, by = LARGEST[params.operation]
    big = (x[pick[bx]], y[pick[by]])
    small = (x[1 - pick[bx]], y[1 - pick[by]])
    return big, small


def _apply(operation: str, a: Decimal, b: Decimal) -> Decimal:
    return {"add": a + b, "subtract": a - b, "multiply": a * b, "divide": a / b}[operation]


def _extremes(params: BoundsIntervalParams) -> tuple[Decimal, Decimal]:
    big, small = _choices(params)
    return _apply(params.operation, *big), _apply(params.operation, *small)


def _text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _result(value: Decimal) -> str:
    """'= 54.1875', or '\\approx 4.28889' for a long quotient (6 significant figures)."""
    text = _text(value)
    if len(text.replace(".", "")) > 7:
        return rf"\approx {format_sf(value, 6)}"
    return f"= {text}"


def _largest_words(operation: str) -> str:
    return {
        "add": "For the largest sum, add the two upper bounds",
        "subtract": "For the largest difference, take the upper bound minus the lower bound",
        "multiply": "For the largest product, multiply the two upper bounds",
        "divide": "For the largest quotient, divide the upper bound by the lower bound",
    }[operation]


def _question(params: BoundsIntervalParams) -> str:
    def phrase(letter, value, nearest, sf):
        how = rf"\text{{ to {sf} s.f.}}" if sf else rf"\text{{ to the nearest }} {nearest}"
        return rf"{letter} = {value}{how}"

    text = phrase(params.letter, params.value, params.nearest, params.sf)
    if params.operation == "none":
        return text
    other = phrase(params.other_letter, params.other, params.other_nearest, params.other_sf)
    return rf"{text},\ {other}"


def _number_line(params: BoundsIntervalParams, second: bool, box, compact: bool) -> dict:
    value = Decimal(params.other if second else params.value)
    lo, hi = _bounds(params, second)
    step = hi - lo
    start, end = float(value - step), float(value + step)
    y = box.center[1] + (0.0 if compact else 0.3)
    width = box.width - 1.0

    def at(v) -> list[float]:
        return [box.left + 0.5 + (float(v) - start) / (end - start) * width, y, 0]

    size = 26 if compact else 30
    ticks = VGroup()
    labels = VGroup()
    for v in (value - step, value + step):
        ticks.add(Line([at(v)[0], y - 0.12, 0], [at(v)[0], y + 0.12, 0], stroke_width=3))
        labels.add(label(_text(v), size=size).next_to(at(v), [0, -1, 0], buff=0.3))
    axis = VGroup(Line(at(start), at(end), stroke_width=3, color=style.TEXT_COLOUR), ticks)
    marker = VGroup(
        Line(
            [at(value)[0], y - 0.2, 0],
            [at(value)[0], y + 0.2, 0],
            stroke_width=4,
            color=style.POINT_COLOUR,
        ),
        label(_text(value), colour=style.POINT_COLOUR, size=size + 4).next_to(
            at(value), [0, -1, 0], buff=0.3
        ),
    )
    half = _text(step / 2)
    arrow_y = y + (0.35 if compact else 0.5)
    halves = VGroup()
    for v in (lo, hi):
        halves.add(
            Line(
                [at(value)[0], arrow_y, 0],
                [at(v)[0], arrow_y, 0],
                stroke_width=3,
                color=style.RUN_COLOUR,
            )
        )
        halves.add(
            label(rf"{half}", colour=style.RUN_COLOUR, size=size - 4).next_to(
                [(at(value)[0] + at(v)[0]) / 2, arrow_y, 0], [0, 1, 0], buff=0.08
            )
        )
    band = Rectangle(
        width=at(hi)[0] - at(lo)[0],
        height=0.22,
        stroke_width=0,
        fill_color=style.AREA_COLOUR,
        fill_opacity=0.6,
    ).move_to([(at(lo)[0] + at(hi)[0]) / 2, y, 0])
    ends = VGroup(
        Dot(at(lo), radius=0.1, color=style.HIGHLIGHT_COLOUR),
        Circle(radius=0.1, color=style.HIGHLIGHT_COLOUR, stroke_width=4)
        .set_fill(BLACK, opacity=1)
        .move_to(at(hi)),
    )
    bound_labels = VGroup(
        label(_text(lo), colour=style.HIGHLIGHT_COLOUR, size=size).next_to(
            at(lo), [0, -1, 0], buff=0.75 if not compact else 0.65
        ),
        label(_text(hi), colour=style.HIGHLIGHT_COLOUR, size=size).next_to(
            at(hi), [0, -1, 0], buff=0.75 if not compact else 0.65
        ),
    )
    return {
        "line": axis,
        "labels": labels,
        "value": marker,
        "halves": halves,
        "band": band,
        "ends": ends,
        "bound_labels": bound_labels,
    }


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
