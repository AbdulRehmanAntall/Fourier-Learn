"""AlgebraBalance: an equation solved by doing the same thing to both sides (4024 2.1, 2.2, 2.3,
2.5; PRIMITIVES.md #13).

The model gives the starting equation and the operations: "-5" (subtract 5 from both sides),
"/3", "*(x - 1)", "+2*x", "expand" (expand the brackets on both sides) or "swap" (swap the
sides). Each new line is computed by SymPy from the line before, so the working is correct by
construction; the model may give the lines as it wants them written (`results`), and each is
checked against the computed line. Linear and fractional equations and changing the subject of a
formula all use this one engine.
"""

from typing import Annotated

import sympy as sp
from manim import MathTex, SurroundingRectangle, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, Level, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.staged import Stage, StagedPrimitive, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    format_value,
    parse_equation,
    parse_expression,
    tidy_latex,
    written_latex,
)

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
OPERATORS = {"+": "+", "-": "-", "*": r"\times", "/": r"\div"}


class AlgebraBalanceParams(PrimitiveParams):
    equation: Text = Field(description='The starting equation, e.g. "3*x + 5 = 20"')
    operations: list[Text] = Field(
        min_length=1,
        max_length=5,
        description='What is done to both sides, in order: "-5", "/3", "*2", "+2*x", '
        '"*(x - 1)", "expand" or "swap"',
    )
    results: list[Text] = Field(
        default=[],
        max_length=5,
        description="Optional: each new line as it should be written, one per operation; "
        "each must equal the line SymPy computes",
    )


class AlgebraBalance(StagedPrimitive[AlgebraBalanceParams]):
    primitive_id = "AlgebraBalance"
    version = "1"
    topic = "Algebra and graphs"
    params_model = AlgebraBalanceParams
    layout = LayoutContract(
        region=style.WORKING_REGION, allowed_overlaps=[("result_box", "line_*")]
    )

    def default_params(self) -> AlgebraBalanceParams:
        return AlgebraBalanceParams(equation="3*x + 5 = 20", operations=["-5", "/3"])

    def validate(self, params: AlgebraBalanceParams) -> list[PredicateFailure]:
        try:
            lines = _lines(params)
        except _Problem as problem:
            return [problem.failure]
        failures = []
        if params.results and len(params.results) != len(params.operations):
            message = "give one result per operation, or none"
            failures.append(_failure("consistency", "one_result_per_operation", message, "results"))
            return failures
        for i, written in enumerate(params.results):
            try:
                lhs, rhs = parse_equation(written)
            except ExpressionError as error:
                failures.append(_failure("parsing", "result_parses", str(error), f"results[{i}]"))
                continue
            expected_lhs, expected_rhs = lines[i + 1]
            if not (_same(lhs, expected_lhs) and _same(rhs, expected_rhs)):
                message = (
                    f"result {i + 1} should be {tidy_latex(expected_lhs)} = "
                    f"{tidy_latex(expected_rhs)} after '{params.operations[i]}'"
                )
                failures.append(
                    _failure("consistency", "result_matches_operation", message, f"results[{i}]")
                )
        return failures

    def computed_values(self, params: AlgebraBalanceParams) -> dict[str, str]:
        lines = _lines(params)
        lhs, rhs = lines[-1]
        values = {f"line_{i + 1}": f"{lhs_i} = {rhs_i}" for i, (lhs_i, rhs_i) in enumerate(lines)}
        if isinstance(lhs, sp.Symbol):
            values["unknown"] = str(lhs)
            values["solution"] = format_value(rhs) if rhs.is_number else str(rhs)
        return values

    def build(self, params: AlgebraBalanceParams, level):
        lines = _lines(params)
        rows: list[MathTex] = []
        for i, (lhs, rhs) in enumerate(lines):
            if i == 0:
                left, right = (written_latex(side) for side in params.equation.split("="))
            elif params.results:
                left, right = (written_latex(side) for side in params.results[i - 1].split("="))
            else:
                left, right = tidy_latex(lhs), tidy_latex(rhs)
            rows.append(MathTex(left, "=", right, font_size=style.FONT_SIZE))
        notes = [_note(op) for op in params.operations]

        # Each row's "=" sits on one vertical line; each note sits under the sides it acts on.
        gap = 0.32
        y = 0.0
        column = 0.0
        stacked = []
        for i, row in enumerate(rows):
            row.shift([column - row[1].get_center()[0], y - row.get_center()[1], 0])
            stacked.append(row)
            y -= row.height / 2 + gap
            if i < len(notes):
                left_note, right_note = notes[i]
                height = max(left_note.height, right_note.height)
                y -= height / 2
                left_note.move_to([row[0].get_center()[0], y, 0])
                right_note.move_to([row[2].get_center()[0], y, 0])
                # Short sides would put the two notes on top of each other: keep each on its
                # own side of the "=".
                if left_note.get_right()[0] > column - 0.2:
                    left_note.shift([column - 0.2 - left_note.get_right()[0], 0, 0])
                if right_note.get_left()[0] < column + 0.2:
                    right_note.shift([column + 0.2 - right_note.get_left()[0], 0, 0])
                if params.operations[i].strip() == "swap":
                    left_note.move_to([column, y, 0])
                stacked.extend(notes[i])
                y -= height / 2 + gap
                y -= rows[i + 1].height / 2
        group = VGroup(*stacked)
        style.fit_inside(group, style.region_box(self.layout.region).shrink(style.PADDING))

        parts = {f"line_{i + 1}": row for i, row in enumerate(rows)}
        for i, (left_note, right_note) in enumerate(notes):
            if params.operations[i].strip() == "swap":
                parts[f"op_{i + 1}"] = left_note
            else:
                parts[f"op_{i + 1}"] = VGroup(left_note, right_note)
        parts["result_box"] = SurroundingRectangle(
            rows[-1], color=style.HIGHLIGHT_COLOUR, buff=0.12
        )
        return parts

    def stages(self, params: AlgebraBalanceParams, level) -> list[Stage]:
        count = len(params.operations)
        first = stage("equation", "Write the equation to solve", 2.0, ["line_1"])
        moves = []
        for i, op in enumerate(params.operations, start=1):
            what = _describe(op)
            note = stage(
                f"op_{i}", f"{what}, to keep the balance", 2.5, [f"op_{i}"], emphasise=[f"op_{i}"]
            )
            line = stage(
                f"line_{i + 1}",
                f"Write the new equation after {what.lower()}",
                2.0,
                [f"line_{i + 1}"],
            )
            moves.append((note, line))
        box = stage("result", "Box the result", 1.5, ["result_box"], emphasise=["result_box"])
        if level is Level.SUPPORTED:
            return [first] + [s for pair in moves for s in pair] + [box]
        if level is Level.STANDARD:
            merged = [
                combine(f"step_{i}", f"{_describe(op)}; write the new equation", 2.5, *pair)
                for i, (op, pair) in enumerate(zip(params.operations, moves, strict=True), 1)
            ]
            merged[-1] = combine(
                merged[-1].name,
                merged[-1].description + ", and box the result",
                2.5,
                merged[-1],
                box,
            )
            return [first] + merged
        rest = [s for pair in moves for s in pair] + [box]
        what = "the operation" if count == 1 else f"all {count} operations"
        return [first, combine("solve", f"Apply {what} and give the result", 2.5, *rest)]


class _Problem(Exception):
    def __init__(self, failure: PredicateFailure):
        self.failure = failure


def _lines(params: AlgebraBalanceParams) -> list[tuple[sp.Expr, sp.Expr]]:
    try:
        lhs, rhs = parse_equation(params.equation)
    except ExpressionError as error:
        raise _Problem(_failure("parsing", "equation_parses", str(error), "equation")) from None
    lines = [(lhs, rhs)]
    written = params.equation
    for i, op in enumerate(params.operations):
        lhs, rhs = _apply(op, lhs, rhs, i, written)
        lines.append((lhs, rhs))
        written = params.results[i] if i < len(params.results) else ""
    return lines


def _apply(
    op: str, lhs: sp.Expr, rhs: sp.Expr, index: int, written: str = ""
) -> tuple[sp.Expr, sp.Expr]:
    """The equation after `op`. `written` is the line before as displayed, if the model wrote
    it: SymPy has already multiplied out 3*(x - 4), so brackets are looked for there."""
    where = f"operations[{index}]"
    op = op.strip()
    if op == "swap":
        return rhs, lhs
    if op == "expand":
        new = sp.expand(lhs), sp.expand(rhs)
        if new == (lhs, rhs) and "(" not in written:
            raise _Problem(_failure("consistency", "expand_changes", "nothing to expand", where))
        return new
    symbol, operand_text = op[0], op[1:].strip()
    if symbol not in OPERATORS or not operand_text:
        message = f"'{op}' is not an operation: use +a, -a, *a, /a, expand or swap"
        raise _Problem(_failure("parsing", "operation_parses", message, where))
    try:
        operand = parse_expression(operand_text)
    except ExpressionError as error:
        raise _Problem(_failure("parsing", "operation_parses", str(error), where)) from None
    if symbol in "*/" and sp.simplify(operand) == 0:
        message = "multiplying or dividing both sides by 0 is not allowed"
        raise _Problem(_failure("consistency", "nonzero_factor", message, where))
    apply = {
        "+": lambda e: e + operand,
        "-": lambda e: e - operand,
        "*": lambda e: e * operand,
        "/": lambda e: e / operand,
    }[symbol]
    return _tidy(apply(lhs)), _tidy(apply(rhs))


def _tidy(expr: sp.Expr) -> sp.Expr:
    """The simplest of the usual forms of `expr`: as it is, expanded, factorised or over one
    denominator."""
    candidates = [expr, sp.expand(expr), sp.cancel(expr), sp.factor(expr)]
    return min(candidates, key=lambda e: (sp.count_ops(e), len(sp.latex(e))))


def _same(a: sp.Expr, b: sp.Expr) -> bool:
    return sp.simplify(a - b) == 0


def _note(op: str) -> tuple[MathTex, MathTex]:
    op = op.strip()
    if op in ("swap", "expand"):
        text = r"\text{swap sides}" if op == "swap" else r"\text{expand}"
        return (
            MathTex(text, font_size=style.LABEL_FONT_SIZE, color=style.HIGHLIGHT_COLOUR),
            MathTex(text, font_size=style.LABEL_FONT_SIZE, color=style.HIGHLIGHT_COLOUR),
        )
    tex = f"{OPERATORS[op[0]]} {_operand_latex(op[1:].strip())}"
    return (
        MathTex(tex, font_size=style.LABEL_FONT_SIZE, color=style.HIGHLIGHT_COLOUR),
        MathTex(tex, font_size=style.LABEL_FONT_SIZE, color=style.HIGHLIGHT_COLOUR),
    )


def _operand_latex(text: str) -> str:
    tex = written_latex(text)
    expr = parse_expression(text)
    needs_brackets = isinstance(expr, sp.Add) or (expr.is_number and expr.is_negative)
    return rf"\left({tex}\right)" if needs_brackets and not tex.startswith(r"\left(") else tex


def _describe(op: str) -> str:
    op = op.strip()
    if op == "swap":
        return "Swap the two sides"
    if op == "expand":
        return "Expand the brackets on both sides"
    words = {
        "+": "Add",
        "-": "Subtract",
        "*": "Multiply both sides by",
        "/": "Divide both sides by",
    }
    operand = op[1:].strip()
    if op[0] == "+":
        return f"Add {operand} to both sides"
    if op[0] == "-":
        return f"Subtract {operand} from both sides"
    return f"{words[op[0]]} {operand}"


def _failure(kind, predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(kind=kind, predicate=predicate, message=message, parameters=[parameter])
