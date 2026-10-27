"""TreeDiagram: probability tree diagrams for two or three events, independent or drawn from a
bag with or without replacement; multiply along the branches, add the outcomes you want
(4024 8.3; PRIMITIVES.md #45).

Each branch carries its probability; the probabilities from one point add to 1. The probability
of a path is the product of its branches. Without replacement, the second branch changes,
because one item has gone from the bag. Everything is exact fractions.
"""

import itertools
import math
from typing import Annotated

import numpy as np
import sympy as sp
from manim import Dot, Line, SurroundingRectangle, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, split_columns, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf, latex_number

Outcome = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z]{1,3}$")]
Fraction = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^\d{1,3}(/\d{1,3})?$|^0?\.\d{1,4}$")
]
COLOURS = [style.CURVE_COLOUR, style.RUN_COLOUR, style.RISE_COLOUR]


class TreeDiagramParams(PrimitiveParams):
    outcomes: list[Outcome] = Field(min_length=2, max_length=3, description='e.g. ["R", "B"]')
    probabilities: list[Fraction] | None = Field(
        default=None, description='For independent events: e.g. ["3/5", "2/5"]'
    )
    counts: list[Annotated[int, Field(ge=1, le=20)]] | None = Field(
        default=None, description="For a bag: how many of each outcome"
    )
    replace: bool = Field(default=True, description="For a bag: put the item back each time")
    events: Annotated[int, Field(ge=2, le=3)] = 2
    find: list[Annotated[str, StringConstraints(pattern=r"^[A-Za-z,]{2,20}$")]] = Field(
        min_length=1,
        max_length=9,
        description='The paths wanted, outcomes joined by commas, e.g. ["R,B", "B,R"]',
    )


class TreeDiagram(StagedPrimitive[TreeDiagramParams]):
    primitive_id = "TreeDiagram"
    version = "1"
    topic = "Probability"
    params_model = TreeDiagramParams
    layout = LayoutContract(
        region=style.GRAPH_REGION, allowed_overlaps=[("branches_*", "*"), ("picked", "*")]
    )

    def default_params(self) -> TreeDiagramParams:
        return TreeDiagramParams(
            outcomes=["R", "B"], counts=[3, 2], replace=False, find=["R,B", "B,R"]
        )

    def validate(self, params: TreeDiagramParams) -> list[PredicateFailure]:
        n = len(params.outcomes)
        if len(set(params.outcomes)) != n:
            return [_failure("outcomes_distinct", "the outcomes must differ", "outcomes")]
        if (params.probabilities is None) == (params.counts is None):
            return [
                _failure(
                    "one_source",
                    "give probabilities or counts, not both",
                    "probabilities",
                    "counts",
                )
            ]
        if params.probabilities is not None:
            if len(params.probabilities) != n:
                return [_failure("one_each", "one probability per outcome", "probabilities")]
            if sum(sp.Rational(p) for p in params.probabilities) != 1:
                return [_failure("sum_one", "the probabilities must add to 1", "probabilities")]
        else:
            if len(params.counts) != n:
                return [_failure("one_each", "one count per outcome", "counts")]
            if not params.replace and sum(params.counts) < params.events:
                return [_failure("enough_items", "not enough items to draw", "counts")]
        if len(params.outcomes) ** params.events > 9:
            return [
                _failure("tree_fits", "more than 9 paths: use fewer outcomes or events", "events")
            ]
        for path in params.find:
            steps = path.split(",")
            if len(steps) != params.events or any(s not in params.outcomes for s in steps):
                message = f"{path!r} is not a path of {params.events} outcomes"
                return [_failure("paths_exist", message, "find")]
        return []

    def computed_values(self, params: TreeDiagramParams) -> dict[str, str]:
        return {"probability": str(_answer(params))}

    def build(self, params: TreeDiagramParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        tree_box, working_box = split_columns(area, [1.6, 1], gap=0.3)
        events, outcomes = params.events, params.outcomes
        leaves = len(outcomes) ** events
        column = (tree_box.width - 1.4) / events
        gap = tree_box.height / leaves
        wanted = {tuple(p.split(",")) for p in params.find}

        def leaf_y(index: float) -> float:
            return tree_box.top - gap * (index + 0.5)

        parts = {}
        picked = VGroup()
        for level_index in range(events):
            branches = VGroup()
            span = len(outcomes) ** (events - level_index - 1)
            for prefix in itertools.product(outcomes, repeat=level_index):
                start_index = _index(prefix, outcomes) * len(outcomes) * span
                start_y = leaf_y(start_index + (len(outcomes) * span - 1) / 2)
                start = [tree_box.left + 0.2 + column * level_index, start_y, 0]
                for k, outcome in enumerate(outcomes):
                    end_y = leaf_y(start_index + k * span + (span - 1) / 2)
                    end = [tree_box.left + 0.2 + column * (level_index + 1) - 0.35, end_y, 0]
                    path = (*prefix, outcome)
                    on_path = any(w[: len(path)] == path for w in wanted)
                    line = Line(
                        start,
                        end,
                        stroke_width=4 if on_path else 2,
                        color=style.HIGHLIGHT_COLOUR if on_path else style.TEXT_COLOUR,
                    )
                    p = _probability(params, prefix, outcome)
                    tag = label(_show(params, p), size=28, colour=COLOURS[k % 3])
                    # beside the branch, on its outer side: above the top branch, else below
                    dx, dy = end[0] - start[0], end[1] - start[1]
                    normal = np.array([-dy, dx, 0]) / max(math.hypot(dx, dy), 1e-9)
                    if (normal[1] < 0) == (k == 0):
                        normal = -normal
                    size = max(tag.width, tag.height) / 2
                    tag.move_to(line.point_from_proportion(0.45) + normal * (0.08 + size))
                    name = label(rf"\text{{{outcome}}}", size=24).next_to(end, [1, 0, 0], buff=0.06)
                    branches.add(line, tag, name)
            parts[f"branches_{level_index + 1}"] = branches
        products = VGroup()
        for index, path in enumerate(itertools.product(outcomes, repeat=events)):
            value = _path_probability(params, path)
            text = label(
                _show(params, value),
                size=26,
                colour=style.HIGHLIGHT_COLOUR if path in wanted else style.TEXT_COLOUR,
            )
            text.move_to([tree_box.right - 0.45, leaf_y(index), 0])
            products.add(text)
            if path in wanted:
                picked.add(SurroundingRectangle(text, color=style.HIGHLIGHT_COLOUR, buff=0.05))
        parts["products"] = products
        parts["picked"] = picked
        parts["root"] = Dot([tree_box.left + 0.2, leaf_y((leaves - 1) / 2), 0], radius=0.05)
        rows = _working(params)
        mobjects = [label(t, size=28) for t in rows]
        group = VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.3)
        for mob in mobjects:
            if mob.width > working_box.width:
                mob.scale_to_fit_width(working_box.width)
        style.fit_inside(group.arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.3), working_box)
        for i, mob in enumerate(mobjects, start=1):
            parts[f"row_{i}"] = mob
        parts["question"] = text_line(_question(params), upper, size=34)
        parts["answer"] = text_line(
            rf"P = {_show(params, _answer(params))}", lower, colour=style.HIGHLIGHT_COLOUR
        )
        return parts

    def stages(self, params: TreeDiagramParams, level) -> list[Stage]:
        rows = [f"row_{i}" for i in range(1, len(_working(params)) + 1)]
        second = (
            "The second branches: one has gone, so there is one fewer in the bag"
            if params.counts is not None and not params.replace
            else "The second branches are the same: the events are independent"
        )
        steps = [
            stage(
                "first",
                "The first event: its branches add up to 1",
                3.0,
                ["question", "root", "branches_1"],
            ),
            stage("second", second, 3.5, ["branches_2"]),
        ]
        if params.events == 3:
            steps.append(stage("third", "And the third event", 3.0, ["branches_3"]))
        steps += [
            stage("multiply", "Multiply along each path", 3.5, ["products"]),
            stage("add", "Add the paths we want", 3.5, ["picked", *rows], emphasise=["picked"]),
            stage("answer", "So", 1.5, ["answer"], emphasise=["answer"]),
        ]

        def standard(s):
            tree = len(s) - 3
            return [combine("tree", "Draw the tree", 4.5, *s[:tree]), *s[tree:]]

        def concise(s):
            tree = len(s) - 3
            return [
                combine("tree", "Draw the tree", 4.5, *s[:tree]),
                combine("result", "Multiply along, add the paths", 4.5, *s[tree:]),
            ]

        return by_level(level, steps, standard, concise)


def _show(params: TreeDiagramParams, value) -> str:
    """Decimals if the probabilities were given as decimals, otherwise fractions."""
    if params.probabilities is not None and any("." in p for p in params.probabilities):
        return format_sf(value, 6)
    return latex_number(value)


def _index(prefix, outcomes) -> int:
    index = 0
    for o in prefix:
        index = index * len(outcomes) + outcomes.index(o)
    return index


def _probability(params: TreeDiagramParams, prefix, outcome) -> sp.Rational:
    k = params.outcomes.index(outcome)
    if params.probabilities is not None:
        return sp.Rational(params.probabilities[k])
    counts = list(params.counts)
    if not params.replace:
        for taken in prefix:
            counts[params.outcomes.index(taken)] -= 1
    total = sum(counts)
    return sp.Rational(max(counts[k], 0), total) if total else sp.Integer(0)


def _path_probability(params: TreeDiagramParams, path) -> sp.Rational:
    value = sp.Integer(1)
    for i, outcome in enumerate(path):
        value *= _probability(params, path[:i], outcome)
    return value


def _answer(params: TreeDiagramParams) -> sp.Rational:
    return sum((_path_probability(params, tuple(p.split(","))) for p in params.find), sp.Integer(0))


def _working(params: TreeDiagramParams) -> list[str]:
    rows = []
    for p in params.find:
        path = tuple(p.split(","))
        factors = r" \times ".join(
            _show(params, _probability(params, path[:i], o)) for i, o in enumerate(path)
        )
        rows.append(rf"P({p}) = {factors} = {_show(params, _path_probability(params, path))}")
    if len(params.find) > 1:
        terms = " + ".join(
            _show(params, _path_probability(params, tuple(p.split(",")))) for p in params.find
        )
        rows.append(rf"P = {terms} = {_show(params, _answer(params))}")
    return rows


def _question(params: TreeDiagramParams) -> str:
    wanted = r",\ ".join(rf"\text{{{p.replace(',', '')}}}" for p in params.find)
    if params.counts is not None:
        bag = ", ".join(f"{c} {o}" for o, c in zip(params.outcomes, params.counts, strict=True))
        how = "with" if params.replace else "without"
        return (
            rf"\text{{A bag has {bag}. {params.events} are taken {how} replacement.}}\ "
            rf"P({wanted})?"
        )
    return rf"P({wanted})?"


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
