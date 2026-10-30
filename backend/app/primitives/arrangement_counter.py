"""ArrangementCounter: counting arrangements and selections: the letters of a word with repeated
letters, arrangements with some items kept together or kept apart, and selections from groups
(9709 5.2).

n different items can be arranged in n! ways; when a letter is repeated, swapping its copies
gives nothing new, so divide by the factorial of each repeat. Items that must be together are
tied into one block, which is arranged with the rest, then the block is arranged inside itself.
Two items that must be apart: all arrangements take away those with the two together. Choosing r
of n where order does not matter gives ⁿCᵣ, and choices from separate groups multiply. Every
count is checked by listing the arrangements one by one when there are few enough.
"""

import itertools
import math
from typing import Annotated, Literal

from manim import Circle, Rectangle, SurroundingRectangle, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import label, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage

Word = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2,10}$")]
Name = Annotated[str, StringConstraints(min_length=1, max_length=12)]
BRUTE_LIMIT = 8


class Group(PrimitiveParams):
    name: Name = Field(description='e.g. "men"')
    size: Annotated[int, Field(ge=1, le=15)]
    choose: Annotated[int, Field(ge=0, le=15)]


class ArrangementCounterParams(PrimitiveParams):
    kind: Literal["word", "together", "apart", "selection"]
    word: Word | None = Field(default=None, description="word: the letters to arrange, in capitals")
    n: Annotated[int, Field(ge=3, le=10)] | None = Field(
        default=None, description="together, apart: how many different people or items"
    )
    k: Annotated[int, Field(ge=2, le=9)] = Field(
        default=2, description="together: how many must be together"
    )
    groups: list[Group] | None = Field(
        default=None, min_length=1, max_length=3, description="selection"
    )


class ArrangementCounter(StagedPrimitive[ArrangementCounterParams]):
    primitive_id = "ArrangementCounter"
    version = "1"
    topic = "Permutations and combinations"
    params_model = ArrangementCounterParams
    layout = LayoutContract(region=FULL_FRAME, allowed_overlaps=[("block", "*"), ("chosen_*", "*")])

    def default_params(self) -> ArrangementCounterParams:
        return ArrangementCounterParams(kind="word", word="NEEDLESS")

    def validate(self, params: ArrangementCounterParams) -> list[PredicateFailure]:
        need = {"word": "word", "together": "n", "apart": "n", "selection": "groups"}[params.kind]
        if getattr(params, need) is None:
            return [_failure("inputs_given", f"{params.kind} needs {need}", need)]
        if params.kind == "together" and params.k >= params.n:
            return [_failure("block_smaller", "k must be less than n", "k")]
        if params.kind == "selection":
            for g in params.groups:
                if g.choose > g.size:
                    return [
                        _failure(
                            "choose_fits",
                            f"cannot choose {g.choose} of {g.size} {g.name}",
                            "groups",
                        )
                    ]
        count, checked = _count(params)
        if checked is not None and checked != count:  # pragma: no cover - a formula bug
            return [_failure("count_checks", "the formula and the listing disagree", "kind")]
        return []

    def computed_values(self, params: ArrangementCounterParams) -> dict[str, str]:
        count, _ = _count(params)
        return {"count": str(count)}

    def build(self, params: ArrangementCounterParams, level):
        area = style.region_box(style.GRAPH_REGION).shrink(style.PADDING)
        parts = {
            "title": text_line(
                _title(params), style.Box(area.left, area.right, area.top - 0.9, area.top)
            )
        }
        body = style.Box(area.left, area.right, area.bottom + 1.0, area.top - 1.2)
        if params.kind == "selection":
            rows = VGroup()
            for gi, g in enumerate(params.groups):
                colour = [style.CURVE_COLOUR, style.RUN_COLOUR, style.RISE_COLOUR][gi]
                circles = VGroup(
                    *(Circle(radius=0.2, color=colour, stroke_width=3) for _ in range(g.size))
                )
                circles.arrange([1, 0, 0], buff=0.12)
                name = label(rf"\text{{{g.name}}}", colour=colour, size=26)
                row = VGroup(name, circles).arrange([1, 0, 0], buff=0.3)
                rows.add(row)
            rows.arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.5)
            style.fit_inside(rows, body)
            for gi, g in enumerate(params.groups):
                circles = rows[gi][1]
                parts[f"chosen_{gi}"] = VGroup(
                    *(c.copy().set_fill(c.get_color(), opacity=0.8) for c in circles[: g.choose])
                )
            parts["items"] = rows
        else:
            tiles = _tiles(params)
            group = VGroup()
            for text, colour in tiles:
                box = Rectangle(width=0.7, height=0.8, color=colour, stroke_width=3)
                group.add(
                    VGroup(box, label(rf"\text{{{text}}}", colour=colour, size=34).move_to(box))
                )
            group.arrange([1, 0, 0], buff=0.1)
            style.fit_inside(group, body)
            parts["items"] = group
            if params.kind == "together":
                parts["block"] = SurroundingRectangle(
                    VGroup(*group[: params.k]), color=style.HIGHLIGHT_COLOUR, buff=0.08
                )
            elif params.kind == "apart":
                parts["block"] = SurroundingRectangle(
                    VGroup(*group[:2]), color=style.TANGENT_COLOUR, buff=0.08
                )
            else:
                parts["block"] = VGroup()
        count, _ = _count(params)
        parts["answer"] = text_line(
            rf"{count:,}".replace(",", r"\,") + r"\text{ ways}",
            style.Box(area.left, area.right, area.bottom, area.bottom + 0.8),
            colour=style.HIGHLIGHT_COLOUR,
        )
        rows_tex = _rows(params)
        work = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines(
            [r for r, _ in rows_tex], work, size=32, colours=[c for _, c in rows_tex]
        )
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: ArrangementCounterParams, level) -> list[Stage]:
        n = len(_rows(params))
        rows = [f"row_{i}" for i in range(1, n + 1)]
        if params.kind == "selection":
            chosen = [f"chosen_{i}" for i in range(len(params.groups))]
            steps = [
                stage("items", "The groups to choose from", 2.5, ["title", "items"]),
                stage(
                    "choose",
                    "Order does not matter: n choose r ways for each group",
                    3.5,
                    [*chosen, *rows[:-1]],
                ),
                stage(
                    "multiply",
                    "Choices from different groups multiply",
                    3.0,
                    [rows[-1], "answer"],
                    emphasise=["answer"],
                ),
            ]
        else:
            words = {
                "word": "Arrange all the letters, then divide out the swaps of repeated letters",
                "together": "Tie the ones that must be together into one block",
                "apart": "Count all the arrangements, then take away those with the two together",
            }[params.kind]
            steps = [
                stage("items", "The items to arrange", 2.5, ["title", "items"]),
                stage("method", words, 3.5, ["block", *rows[:-1]]),
                stage("count", "So", 2.5, [rows[-1], "answer"], emphasise=["answer"]),
            ]

        def standard(s):
            return list(s)

        def concise(s):
            return [combine("count", s[1].description, 4.0, s[0], s[1]), s[2]]

        return by_level(level, steps, standard, concise)


def _title(params) -> str:
    if params.kind == "word":
        return rf"\text{{Arrangements of {params.word}}}"
    if params.kind == "together":
        return rf"\text{{{params.n} people in a line, {params.k} together}}"
    if params.kind == "apart":
        return rf"\text{{{params.n} people in a line, two not together}}"
    return r"\text{Choose } " + r",\ ".join(f"{g.choose}\\text{{ {g.name}}}" for g in params.groups)


def _tiles(params) -> list[tuple[str, object]]:
    if params.kind == "word":
        repeats = {c for c in params.word if params.word.count(c) > 1}
        palette = [style.RUN_COLOUR, style.RISE_COLOUR, style.SECANT_COLOUR, style.TANGENT_COLOUR]
        colour = {c: palette[i % 4] for i, c in enumerate(sorted(repeats))}
        return [(c, colour.get(c, style.TEXT_COLOUR)) for c in params.word]
    names = [chr(ord("A") + i) for i in range(params.n)]
    if params.kind == "together":
        return [
            (c, style.HIGHLIGHT_COLOUR if i < params.k else style.TEXT_COLOUR)
            for i, c in enumerate(names)
        ]
    return [(c, style.TANGENT_COLOUR if i < 2 else style.TEXT_COLOUR) for i, c in enumerate(names)]


def _count(params) -> tuple[int, int | None]:
    """The count by formula, and by listing when the listing is small enough (else None)."""
    if params.kind == "word":
        word = params.word
        count = math.factorial(len(word))
        for c in set(word):
            count //= math.factorial(word.count(c))
        listed = len(set(itertools.permutations(word))) if len(word) <= BRUTE_LIMIT else None
        return count, listed
    if params.kind == "together":
        n, k = params.n, params.k
        count = math.factorial(n - k + 1) * math.factorial(k)
        listed = None
        if n <= BRUTE_LIMIT:
            block = set(range(k))
            listed = sum(
                1
                for order in itertools.permutations(range(n))
                if max(order.index(i) for i in block) - min(order.index(i) for i in block) == k - 1
            )
        return count, listed
    if params.kind == "apart":
        n = params.n
        count = math.factorial(n) - 2 * math.factorial(n - 1)
        listed = None
        if n <= BRUTE_LIMIT:
            listed = sum(
                1
                for order in itertools.permutations(range(n))
                if abs(order.index(0) - order.index(1)) > 1
            )
        return count, listed
    count = 1
    for g in params.groups:
        count *= math.comb(g.size, g.choose)
    return count, None


def _rows(params) -> list[tuple[str, object]]:
    count, _ = _count(params)
    if params.kind == "word":
        word = params.word
        repeats = sorted({c for c in word if word.count(c) > 1})
        described = (
            r",\ ".join(rf"\text{{{c}}} \times {word.count(c)}" for c in repeats)
            or r"\text{no repeats}"
        )
        divisor = "".join(f"{word.count(c)}!" for c in repeats)
        fraction = rf"\dfrac{{{len(word)}!}}{{{divisor}}}" if divisor else f"{len(word)}!"
        return [
            (rf"{len(word)}\text{{ letters: }}{described}", None),
            (rf"{fraction} = {count}", style.HIGHLIGHT_COLOUR),
        ]
    if params.kind == "together":
        n, k = params.n, params.k
        return [
            (rf"\text{{Block + {n - k} others: }}{n - k + 1}\text{{ items}}", None),
            (rf"\text{{Arrange them: }}{n - k + 1}!", None),
            (rf"\text{{Inside the block: }}{k}!", None),
            (rf"{n - k + 1}! \times {k}! = {count}", style.HIGHLIGHT_COLOUR),
        ]
    if params.kind == "apart":
        n = params.n
        return [
            (rf"\text{{All: }}{n}! = {math.factorial(n)}", None),
            (rf"\text{{Together: }}{n - 1}! \times 2! = {2 * math.factorial(n - 1)}", None),
            (
                rf"{math.factorial(n)} - {2 * math.factorial(n - 1)} = {count}",
                style.HIGHLIGHT_COLOUR,
            ),
        ]
    rows = [
        (
            rf"\binom{{{g.size}}}{{{g.choose}}} = {math.comb(g.size, g.choose)}\ "
            rf"\text{{({g.name})}}",
            None,
        )
        for g in params.groups
    ]
    if len(params.groups) == 1:
        rows.append((rf"{count}\text{{ ways}}", style.HIGHLIGHT_COLOUR))
    else:
        product = r" \times ".join(str(math.comb(g.size, g.choose)) for g in params.groups)
        rows.append((rf"{product} = {count}", style.HIGHLIGHT_COLOUR))
    return rows


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
