"""ProbabilitySpinner: probability from equally likely outcomes on a spinner, placed on the
probability scale from impossible (0) to certain (1), the probability that it does not happen,
and the expected frequency in a number of spins (4024 8.1, 8.2; PRIMITIVES.md #44).

The spinner has equal sectors, so P(A) is the sectors marked A over all the sectors. P(not A)
= 1 − P(A). In n spins, A is expected n × P(A) times. Values are exact fractions.
"""

import math
from typing import Annotated

import numpy as np
import sympy as sp
from manim import Arrow, Dot, Line, Sector, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, split_columns, stack_boxes, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf, latex_number

Name = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9]{1,8}$")]
PALETTE = [
    style.CURVE_COLOUR,
    style.RUN_COLOUR,
    style.RISE_COLOUR,
    style.SECANT_COLOUR,
    style.AREA_COLOUR,
]
SCALE_WORDS = [(0, "impossible"), (0.5, "even chance"), (1, "certain")]


class ProbabilitySpinnerParams(PrimitiveParams):
    sectors: list[Name] = Field(
        min_length=2, max_length=12, description='The equal sectors in order, e.g. ["red", ...]'
    )
    event: Name = Field(description="The outcome whose probability is wanted")
    trials: Annotated[int, Field(ge=1, le=100_000)] | None = Field(
        default=None, description="For expected frequency: the number of spins"
    )


class ProbabilitySpinner(StagedPrimitive[ProbabilitySpinnerParams]):
    primitive_id = "ProbabilitySpinner"
    version = "1"
    topic = "Probability"
    params_model = ProbabilitySpinnerParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("spinner", "*"), ("marked", "*"), ("scale", "*"), ("marker*", "*")],
    )

    def default_params(self) -> ProbabilitySpinnerParams:
        return ProbabilitySpinnerParams(
            sectors=["red", "blue", "red", "green", "red", "blue"], event="red", trials=120
        )

    def validate(self, params: ProbabilitySpinnerParams) -> list[PredicateFailure]:
        return []

    def computed_values(self, params: ProbabilitySpinnerParams) -> dict[str, str]:
        p = _p(params)
        values = {"probability": str(p), "not": str(1 - p)}
        if params.trials:
            values["expected"] = format_sf(p * params.trials)
        return values

    def build(self, params: ProbabilitySpinnerParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        top, bottom = stack_boxes(area, 2, gap=0.2)
        spinner_box, working_box = split_columns(
            style.Box(area.left, area.right, bottom.top - 0.3, area.top), [1, 1.2], gap=0.3
        )
        names = list(dict.fromkeys(params.sectors))
        n = len(params.sectors)
        radius = min(spinner_box.width, spinner_box.height) / 2 - 0.2
        centre = spinner_box.center
        step = 2 * math.pi / n
        spinner, marked = VGroup(), VGroup()
        for k, name in enumerate(params.sectors):
            index = names.index(name)
            colour = PALETTE[index % len(PALETTE)]
            shade = 0.6 if index < len(PALETTE) else 0.3  # past five outcomes, a lighter shade
            sector = Sector(
                radius=radius,
                angle=step,
                start_angle=math.pi / 2 - (k + 1) * step,
                fill_color=colour,
                fill_opacity=shade,
                stroke_color=style.TEXT_COLOUR,
                stroke_width=2,
            ).move_arc_center_to(centre)
            spinner.add(sector)
            middle = math.pi / 2 - (k + 0.5) * step
            tag = label(rf"\text{{{name}}}", size=min(24, 160 / n))
            tag.move_to(centre + 0.62 * radius * np.array([math.cos(middle), math.sin(middle), 0]))
            spinner.add(tag)
            if name == params.event:
                marked.add(
                    Sector(
                        radius=radius,
                        angle=step,
                        start_angle=math.pi / 2 - (k + 1) * step,
                        fill_opacity=0,
                        stroke_color=style.HIGHLIGHT_COLOUR,
                        stroke_width=5,
                    ).move_arc_center_to(centre)
                )
        spinner.add(
            Arrow(
                centre,
                centre + np.array([0.17 * radius, 0.37 * radius, 0]),
                buff=0,
                color=style.TEXT_COLOUR,
                stroke_width=4,
            ),
            Dot(centre, radius=0.06),
        )
        p = _p(params)
        parts = {"spinner": spinner, "marked": marked}
        # the probability scale from 0 to 1 along the bottom
        left, right = area.left + 0.6, area.right - 0.6
        y = bottom.center[1] - 0.1

        def at(value) -> np.ndarray:
            return np.array([left + float(value) * (right - left), y, 0])

        scale = VGroup(Line(at(0), at(1), stroke_width=4))
        for value, word in SCALE_WORDS:
            scale.add(Line(at(value) + [0, -0.12, 0], at(value) + [0, 0.12, 0], stroke_width=3))
            scale.add(label(str(value), size=24).next_to(at(value), [0, -1, 0], buff=0.2))
            scale.add(label(rf"\text{{{word}}}", size=22).next_to(at(value), [0, -1, 0], buff=0.55))
        parts["scale"] = scale
        parts["marker"] = VGroup(
            Dot(at(p), color=style.HIGHLIGHT_COLOUR, radius=0.09),
            label(rf"P(\text{{{params.event}}})", colour=style.HIGHLIGHT_COLOUR, size=26).next_to(
                at(p), [0, 1, 0], buff=0.15
            ),
        )
        parts["marker_not"] = VGroup(
            Dot(at(1 - p), color=style.TANGENT_COLOUR, radius=0.09),
            label(rf"P(\text{{not {params.event}}})", colour=style.TANGENT_COLOUR, size=26)
            .next_to(at(1 - p), [0, 1, 0], buff=0.15)
            .shift([0, 0.35 if abs(2 * p - 1) < 0.25 else 0, 0]),
        )
        count = params.sectors.count(params.event)
        rows = [
            rf"P(\text{{{params.event}}}) = \frac{{{count}}}{{{n}}}"
            + (rf" = {latex_number(p)}" if p.q != n else ""),
            rf"P(\text{{not {params.event}}}) = 1 - {latex_number(p)} = {latex_number(1 - p)}",
        ]
        if params.trials:
            rows.append(
                rf"\text{{expected}} = {params.trials} \times {latex_number(p)} = "
                rf"{format_sf(p * params.trials)}"
            )
        mobjects = [label(t, size=30) for t in rows]
        group = VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.3)
        style.fit_inside(group, working_box)
        for i, mob in enumerate(mobjects, start=1):
            parts[f"row_{i}"] = mob
        question = rf"\text{{The spinner is spun. Find P({params.event})}}"
        if params.trials:
            question = (
                rf"\text{{The spinner is spun {params.trials} times. How many "
                rf"{params.event}?}}"
            )
        parts["question"] = text_line(question, upper, size=34)
        answer = (
            rf"\text{{Expected }} {format_sf(p * params.trials)}"
            if params.trials
            else rf"P(\text{{{params.event}}}) = {latex_number(p)}"
        )
        parts["answer"] = text_line(answer, lower, colour=style.HIGHLIGHT_COLOUR)
        return parts

    def stages(self, params: ProbabilitySpinnerParams, level) -> list[Stage]:
        steps = [
            stage(
                "spinner",
                "The sectors are equal, so each is equally likely",
                2.5,
                ["question", "spinner"],
            ),
            stage(
                "count",
                f"Count the {params.event} sectors out of all of them",
                3.0,
                ["marked", "row_1"],
                emphasise=["marked"],
            ),
            stage(
                "scale", "Place it on the probability scale, from 0 to 1", 3.0, ["scale", "marker"]
            ),
            stage(
                "not", "Not happening is 1 take away the probability", 3.0, ["marker_not", "row_2"]
            ),
        ]
        if params.trials:
            steps.append(
                stage(
                    "expected",
                    "Expected frequency is the number of spins times the probability",
                    3.0,
                    ["row_3"],
                )
            )
        steps.append(stage("answer", "So", 1.5, ["answer"], emphasise=["answer"]))

        def standard(s):
            return [combine("setup", s[1].description, 3.5, s[0], s[1]), *s[2:]]

        def concise(s):
            return [
                combine("setup", s[1].description, 3.5, s[0], s[1]),
                combine("rest", "On the scale, and the rest", 4.5, *s[2:]),
            ]

        return by_level(level, steps, standard, concise)


def _p(params: ProbabilitySpinnerParams) -> sp.Rational:
    return sp.Rational(params.sectors.count(params.event), len(params.sectors))
