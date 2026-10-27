"""FunctionMachine: a function as a chain of operations, with values passed through it and the
inverse as the same machine run backwards (4024 2.12; AM 1.1 to 1.8; PRIMITIVES.md #21).

x enters on the left, each box does one operation, and f(x) comes out on the right; the
expression after each box is written under its arrow, so f(x) is built up in front of the
learner. Input values are traced through the same boxes. The inverse machine undoes each
operation in the reverse order, right to left, giving f⁻¹(x). Every expression and value is
computed by SymPy.
"""

from typing import Annotated

import sympy as sp
from manim import Arrow, MathTex, RoundedRectangle, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    exact,
    format_value,
    latex_value,
    parse_expression,
    tidy_latex,
)

X = sp.Symbol("x", real=True)
Operation = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
Value = Annotated[float, Field(ge=-1000, le=1000)]
POWERS = {"**2": 2, "**3": 3, "^2": 2, "^3": 3}


class FunctionMachineParams(PrimitiveParams):
    operations: list[Operation] = Field(
        min_length=1,
        max_length=4,
        description='The boxes in order: "+3", "-2", "*4", "/2", "**2", "**3" or "sqrt"',
    )
    inputs: list[Value] = Field(default=[], max_length=3, description="Values to put through")
    name: str = Field(default="f", pattern="^[a-hk-z]$", description="The function's letter")
    show_inverse: bool = Field(default=False, description="Also show the inverse machine")


class FunctionMachine(StagedPrimitive[FunctionMachineParams]):
    primitive_id = "FunctionMachine"
    version = "1"
    topic = "Functions and graphs"
    params_model = FunctionMachineParams
    layout = LayoutContract(region=style.GRAPH_REGION)

    def default_params(self) -> FunctionMachineParams:
        return FunctionMachineParams(operations=["*2", "+3"], inputs=[4], show_inverse=True)

    def validate(self, params: FunctionMachineParams) -> list[PredicateFailure]:
        try:
            ops = [_parse_op(op) for op in params.operations]
        except _Bad as bad:
            return [_failure("parsing", "operation_parses", str(bad), "operations")]
        if params.show_inverse and any(kind == "power" and n == 2 for kind, n in ops):
            message = "squaring is not one-to-one, so this machine has no inverse"
            return [_failure("consistency", "invertible", message, "show_inverse")]
        for i, value in enumerate(params.inputs):
            for expr in _flow(ops, exact(value)):
                if not (expr.is_real and expr.is_finite):
                    message = f"input {format_value(exact(value))} gives a value that is not real"
                    return [_failure("domain", "real_values", message, f"inputs[{i}]")]
        return []

    def computed_values(self, params: FunctionMachineParams) -> dict[str, str]:
        ops = [_parse_op(op) for op in params.operations]
        values = {"function": str(_flow(ops, X)[-1])}
        for i, value in enumerate(params.inputs, start=1):
            values[f"output_{i}"] = format_value(_flow(ops, exact(value))[-1])
        if params.show_inverse:
            values["inverse"] = str(_inverse_flow(ops, X)[-1])
        return values

    def build(self, params: FunctionMachineParams, level):
        ops = [_parse_op(op) for op in params.operations]
        name = params.name
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        forward = _flow(ops, X)
        parts = {"formula": text_line(rf"{name}(x) = {tidy_latex(forward[-1])}", upper)}
        if params.show_inverse:
            parts["inverse_formula"] = text_line(
                rf"{name}^{{-1}}(x) = {tidy_latex(_inverse_flow(ops, X)[-1])}", lower
            )

        n = len(ops)
        box_w, arrow_w = 1.15, 0.85
        width = n * box_w + (n + 1) * arrow_w
        scale = min(1.0, (area.width - 0.2) / width)
        box_w, arrow_w = box_w * scale, arrow_w * scale
        left = area.center[0] - (n * box_w + (n + 1) * arrow_w) / 2

        def arrow_centre(k: int) -> float:
            return left + k * (box_w + arrow_w) + arrow_w / 2

        def box_centre(k: int) -> float:
            return left + (k + 1) * arrow_w + k * box_w + box_w / 2

        rows = 2 + len(params.inputs) + (3 if params.show_inverse else 0)
        row_h = min(0.95, (area.height - 0.8) / (rows + 0.5))
        y_machine = area.top - row_h * 0.8 - 0.35
        machine = VGroup()
        for k, op in enumerate(ops):
            box = RoundedRectangle(
                corner_radius=0.12,
                width=box_w,
                height=0.8,
                color=style.CURVE_COLOUR,
                fill_opacity=0.2,
            ).move_to([box_centre(k), y_machine, 0])
            text = MathTex(_op_latex(op), font_size=style.FONT_SIZE)
            style.fit_inside(
                text,
                style.Box(
                    box.get_left()[0] + 0.1,
                    box.get_right()[0] - 0.1,
                    y_machine - 0.3,
                    y_machine + 0.3,
                ),
            ).move_to(box)
            machine.add(box, text)
        for k in range(n + 1):
            x = arrow_centre(k)
            machine.add(
                Arrow(
                    [x - arrow_w / 2, y_machine, 0],
                    [x + arrow_w / 2, y_machine, 0],
                    buff=0.05,
                    stroke_width=4,
                    max_tip_length_to_length_ratio=0.3,
                )
            )
        parts["machine"] = machine
        parts["ends"] = VGroup(
            MathTex("x", font_size=30).move_to([arrow_centre(0), y_machine + 0.68, 0]),
            MathTex(f"{name}(x)", font_size=30).move_to([arrow_centre(n), y_machine + 0.68, 0]),
        )

        def value_row(values, y, colour, key):
            group = VGroup()
            for k, value in enumerate(values):
                tex = MathTex(value, font_size=30, color=colour)
                if tex.width > box_w + arrow_w - 0.1:
                    tex.scale_to_fit_width(box_w + arrow_w - 0.1)
                group.add(tex.move_to([arrow_centre(k), y, 0]))
            parts[key] = group

        value_row([tidy_latex(e) for e in forward], y_machine - row_h, style.RISE_COLOUR, "flow")
        for i, value in enumerate(params.inputs, start=1):
            values = [latex_value(v) for v in _flow(ops, exact(value))]
            value_row(values, y_machine - (i + 1) * row_h, style.POINT_COLOUR, f"input_{i}")

        if params.show_inverse:
            y_inverse = y_machine - (len(params.inputs) + 2.4) * row_h - 0.3
            backward = VGroup()
            for k, op in enumerate(ops):
                box = RoundedRectangle(
                    corner_radius=0.12,
                    width=box_w,
                    height=0.8,
                    color=style.TANGENT_COLOUR,
                    fill_opacity=0.2,
                ).move_to([box_centre(k), y_inverse, 0])
                text = MathTex(_op_latex(_inverse_op(op)), font_size=style.FONT_SIZE)
                style.fit_inside(
                    text,
                    style.Box(
                        box.get_left()[0] + 0.1,
                        box.get_right()[0] - 0.1,
                        y_inverse - 0.3,
                        y_inverse + 0.3,
                    ),
                ).move_to(box)
                backward.add(box, text)
            for k in range(n + 1):
                x = arrow_centre(k)
                backward.add(
                    Arrow(
                        [x + arrow_w / 2, y_inverse, 0],
                        [x - arrow_w / 2, y_inverse, 0],
                        buff=0.05,
                        stroke_width=4,
                        max_tip_length_to_length_ratio=0.3,
                        color=style.TANGENT_COLOUR,
                    )
                )
            parts["inverse_machine"] = backward
            parts["inverse_ends"] = VGroup(
                MathTex(f"{name}^{{-1}}(x)", font_size=30).move_to(
                    [arrow_centre(0), y_inverse + 0.68, 0]
                ),
                MathTex("x", font_size=30).move_to([arrow_centre(n), y_inverse + 0.68, 0]),
            )
            # Values under the inverse arrows: x enters on the right.
            inverse = _inverse_flow(ops, X)  # [x, after undoing the last op, ...]
            value_row(
                [tidy_latex(e) for e in reversed(inverse)],
                y_inverse - row_h,
                style.TANGENT_COLOUR,
                "inverse_flow",
            )
        return parts

    def stages(self, params: FunctionMachineParams, level) -> list[Stage]:
        steps = [
            stage(
                "machine",
                "Here is the function as a machine: x goes in on the left",
                2.5,
                ["machine", "ends"],
            ),
            stage(
                "flow",
                "Follow x through each box to build the expression",
                3.0,
                ["flow"],
                emphasise=["flow"],
            ),
            stage("formula", "So this is the function", 2.0, ["formula"], emphasise=["formula"]),
        ]
        for i, value in enumerate(params.inputs, start=1):
            steps.append(
                stage(
                    f"input_{i}",
                    f"Put {format_value(exact(value))} in and follow it through",
                    2.5,
                    [f"input_{i}"],
                )
            )
        if params.show_inverse:
            steps.append(
                stage(
                    "inverse_machine",
                    "The inverse undoes each box, in reverse order, from right to left",
                    3.0,
                    ["inverse_machine", "inverse_ends"],
                )
            )
            steps.append(
                stage(
                    "inverse_flow",
                    "Follow x backwards through the inverse to find it",
                    3.0,
                    ["inverse_flow", "inverse_formula"],
                    emphasise=["inverse_formula"],
                )
            )

        def standard(s):
            out = [
                combine(
                    "function", "Build the function by following x through the machine", 3.5, *s[:3]
                )
            ]
            values = [x for x in s if x.name.startswith("input_")]
            if values:
                out.append(combine("inputs", "Put values through the machine", 3.0, *values))
            inverse = [x for x in s if x.name.startswith("inverse")]
            if inverse:
                out.append(
                    combine(
                        "inverse", "Run the machine backwards to get the inverse", 3.5, *inverse
                    )
                )
            return out

        def concise(s):
            inverse = [x for x in s if x.name.startswith("inverse")]
            first = [x for x in s if x not in inverse]
            out = [
                combine(
                    "function", "The function as a machine, with values put through", 3.5, *first
                )
            ]
            if inverse:
                out.append(combine("inverse", "The inverse machine", 3.0, *inverse))
            return out

        return by_level(level, steps, standard, concise)


class _Bad(ValueError):
    pass


def _parse_op(text: str) -> tuple[str, object]:
    text = text.strip().replace(" ", "")
    if text in POWERS:
        return "power", POWERS[text]
    if text == "sqrt":
        return "sqrt", None
    if text[:1] in "+-*/" and len(text) > 1:
        try:
            operand = parse_expression(text[1:], set())
        except ExpressionError as error:
            raise _Bad(f"{text!r}: {error}") from None
        if not operand.is_number:
            raise _Bad(f"{text!r}: the operand must be a number")
        if text[0] in "*/" and operand == 0:
            raise _Bad(f"{text!r}: multiplying or dividing by 0 is not allowed")
        return text[0], sp.nsimplify(operand)
    raise _Bad(f"{text!r} is not an operation: use +a, -a, *a, /a, **2, **3 or sqrt")


def _apply(op, expr):
    kind, value = op
    if kind == "power":
        return expr**value
    if kind == "sqrt":
        return sp.sqrt(expr)
    if kind in "*/" and not expr.is_number:
        # Keep 2(x + 3) as written rather than SymPy's automatic 2x + 6.
        factor = value if kind == "*" else 1 / value
        return sp.Mul(factor, expr, evaluate=False) if isinstance(expr, sp.Add) else expr * factor
    return {"+": expr + value, "-": expr - value, "*": expr * value, "/": expr / value}[kind]


def _inverse_op(op):
    kind, value = op
    if kind == "power":
        return ("root", value)
    if kind == "sqrt":
        return ("power", 2)
    return ({"+": "-", "-": "+", "*": "/", "/": "*"}[kind], value)


def _apply_inverse(op, expr):
    kind, value = _inverse_op(op)
    if kind == "root":
        return sp.cbrt(expr) if value == 3 else sp.sqrt(expr)
    return _apply((kind, value), expr)


def _flow(ops, start) -> list[sp.Expr]:
    values = [start]
    for op in ops:
        values.append(_apply(op, values[-1]))
    return values


def _inverse_flow(ops, start) -> list[sp.Expr]:
    values = [start]
    for op in reversed(ops):
        values.append(_apply_inverse(op, values[-1]))
    return values


def _op_latex(op) -> str:
    kind, value = op
    if kind == "power":
        return rf"(\ )^{value}"
    if kind == "root":
        return r"\sqrt[3]{\ }" if value == 3 else r"\sqrt{\ }"
    if kind == "sqrt":
        return r"\sqrt{\ }"
    symbol = {"+": "+", "-": "-", "*": r"\times", "/": r"\div"}[kind]
    tex = latex_value(value)
    if value < 0:
        tex = rf"({tex})"
    return f"{symbol} {tex}"


def _failure(kind, predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(kind=kind, predicate=predicate, message=message, parameters=[parameter])
