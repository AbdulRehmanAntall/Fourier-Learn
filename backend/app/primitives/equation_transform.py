"""EquationTransform: an algebraic derivation shown step by step, with the terms changed at each
step highlighted (report Table 5.2, all topics).

Every line must be equivalent to the line before it (a consistency predicate of §5.3.3):
expressions must be equal, and equations must differ only by a non-zero constant factor, as in
2x + 3 = 7, then 2x = 4, then x = 2.
"""

from collections import Counter
from typing import Annotated

import sympy as sp
from manim import (
    DOWN,
    LEFT,
    WHITE,
    Create,
    FadeIn,
    MathTex,
    SurroundingRectangle,
    TransformMatchingShapes,
    VGroup,
    Write,
)
from pydantic import Field, StringConstraints

from app.contracts import (
    LayoutContract,
    Level,
    PredicateFailure,
    Primitive,
    PrimitiveParams,
    StepSpec,
)
from app.primitives import style
from app.primitives.symbolic import (
    ExpressionError,
    equivalent,
    format_number,
    parse_equation,
    parse_expression,
    written_latex,
)

Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class EquationTransformParams(PrimitiveParams):
    expressions: list[Line] = Field(
        min_length=2,
        max_length=6,
        description='Lines of the working in SymPy syntax, e.g. ["(8 - 2)/(4 - 1)", "6/3", "2"] '
        'or equations such as ["2*x + 3 = 7", "2*x = 4", "x = 2"]',
    )


class EquationTransform(Primitive[EquationTransformParams]):
    primitive_id = "EquationTransform"
    version = "1"
    topic = "All topics"
    params_model = EquationTransformParams
    layout = LayoutContract(
        region=style.WORKING_REGION, allowed_overlaps=[("result_box", "line_*")]
    )

    def default_params(self) -> EquationTransformParams:
        return EquationTransformParams(expressions=["2*x + 3 = 7", "2*x = 4", "x = 2"])

    def validate(self, params: EquationTransformParams) -> list[PredicateFailure]:
        lines = params.expressions
        equations = ["=" in line for line in lines]
        if any(equations) and not all(equations):
            return [_failure("consistency", "same_kind", "mix of equations and expressions", 0)]

        parsed, failures = [], []
        for index, line in enumerate(lines):
            try:
                parsed.append(_parse(line, evaluate=True))
            except ExpressionError as error:
                failures.append(_failure("parsing", "line_parses", str(error), index))
        if failures:
            return failures

        for index in range(1, len(parsed)):
            if not _follows(parsed[index - 1], parsed[index]):
                failures.append(
                    _failure(
                        "consistency",
                        "step_equivalent",
                        f"line {index + 1} is not equivalent to line {index}",
                        index,
                    )
                )
        return failures

    def computed_values(self, params: EquationTransformParams) -> dict[str, str]:
        last = _parse(params.expressions[-1], evaluate=True)
        if isinstance(last, tuple):
            lhs, rhs = last
            if isinstance(lhs, sp.Symbol) and not rhs.free_symbols:
                return {"result": format_number(rhs), "unknown": str(lhs)}
            return {}
        return {} if last.free_symbols else {"result": format_number(last)}

    def steps(self, params: EquationTransformParams, level: Level) -> list[StepSpec]:
        return [spec for spec, _ in _plan(len(params.expressions), level)]

    def animate(self, scene, params, level, run_times, carried):
        fades, visible = style.clear_region(carried, self.layout.region)
        lines = self._build(params)
        result_box = SurroundingRectangle(lines[-1], color=style.HIGHLIGHT_COLOUR, buff=0.12)
        for i, ((spec, shown), run_time) in enumerate(
            zip(_plan(len(lines), level), run_times, strict=True)
        ):
            first = shown[0]
            animations = list(fades) if i == 0 else []
            if first == 0:
                animations.append(Write(lines[0]))
            elif len(shown) == 1 and level is not Level.CONCISE:
                previous = lines[first - 1]
                if level is Level.SUPPORTED:
                    _highlight_changes(previous, lines[first])
                    animations.append(previous.animate.set_color(WHITE))
                animations.append(TransformMatchingShapes(previous.copy(), lines[first]))
            else:
                animations.append(FadeIn(VGroup(*(lines[k] for k in shown)), shift=0.2 * DOWN))
            if level is Level.CONCISE and shown[-1] == len(lines) - 1 and len(lines) > 1:
                animations.append(Create(result_box))
                visible["result_box"] = result_box
            style.play_step(scene, animations, run_time, spec.min_run_time_s)
            visible.update({f"line_{k + 1}": lines[k] for k in shown})
            yield dict(visible)

    def _build(self, params: EquationTransformParams) -> list[MathTex]:
        lines = []
        for index, text in enumerate(params.expressions):
            # Equations are shown whole; each later expression continues the working with "=".
            tex = written_latex(text)
            if "=" not in text and index > 0:
                tex = f"= {tex}"
            lines.append(MathTex(tex, font_size=style.FONT_SIZE))
        group = VGroup(*lines).arrange(DOWN, aligned_edge=LEFT, buff=0.35)
        style.fit_inside(group, style.region_box(self.layout.region).shrink(style.PADDING))
        return lines


def _plan(count: int, level: Level) -> list[tuple[StepSpec, list[int]]]:
    """Each step and the indices of the lines it shows."""
    first = (_step("first_line", "Write the starting line", 2.0, 1), [0])
    if level is Level.CONCISE:
        rest = list(range(1, count))
        return [
            (_step("first_line", "Write the starting line", 1.5, 1), [0]),
            (_step("result", "Show the working and the result directly", 2.0, 1, 1), rest),
        ]
    if level is Level.SUPPORTED:
        return [first] + [
            (
                _step(
                    f"line_{k + 1}",
                    f"Rewrite as line {k + 1}, highlighting what changed",
                    2.5,
                    1,
                    1,
                ),
                [k],
            )
            for k in range(1, count)
        ]
    if count <= 3:
        return [first] + [
            (_step(f"line_{k + 1}", f"Rewrite as line {k + 1}", 2.0, 1), [k])
            for k in range(1, count)
        ]
    return [
        first,
        (
            _step("working", "Show the intermediate lines", 2.5, count - 2),
            list(range(1, count - 1)),
        ),
        (_step("result", "Write the final line", 2.0, 1), [count - 1]),
    ]


def _highlight_changes(previous: MathTex, line: MathTex) -> None:
    """Colour the glyphs of `line` that do not appear in `previous`: the changed terms."""
    key = TransformMatchingShapes.get_mobject_key
    available = Counter(key(glyph) for glyph in previous.family_members_with_points())
    for glyph in line.family_members_with_points():
        glyph_key = key(glyph)
        if available[glyph_key] > 0:
            available[glyph_key] -= 1
        else:
            glyph.set_color(style.HIGHLIGHT_COLOUR)


def _parse(text: str, evaluate: bool):
    return (
        parse_equation(text, evaluate=evaluate)
        if "=" in text
        else parse_expression(text, evaluate=evaluate)
    )


def _follows(before, after) -> bool:
    if isinstance(before, tuple):
        old, new = before[0] - before[1], after[0] - after[1]
        if sp.simplify(old) == 0:
            return False
        ratio = sp.simplify(new / old)
        return bool(ratio.is_number) and ratio != 0
    return equivalent(before, after)


def _step(name, description, min_run_time, labels=0, highlights=0) -> StepSpec:
    return StepSpec(
        name=name,
        description=description,
        min_run_time_s=min_run_time,
        labels=labels,
        highlights=highlights,
    )


def _failure(kind, predicate, message, index) -> PredicateFailure:
    return PredicateFailure(
        kind=kind,
        predicate=predicate,
        message=message,
        parameters=[f"expressions[{index}]"],
    )
