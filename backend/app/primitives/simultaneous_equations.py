"""SimultaneousEquations: two equations in x and y solved together, by elimination or by
substitution (4024 2.5; PRIMITIVES.md #13, simultaneous elimination).

Elimination: each equation is multiplied so one unknown has the same size of coefficient in
both, then the equations are added or subtracted to remove it, and the other unknown is found by
substituting back. Substitution: the linear equation is made y = ... and put into the other one,
which may be a quadratic, giving up to two pairs of solutions. Every line is computed by SymPy.
"""

from typing import Annotated, Literal

import sympy as sp
from manim import DOWN, LEFT, MathTex, SurroundingRectangle, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import inline
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    format_value,
    latex_value,
    parse_equation,
    tidy_latex,
    written_latex,
)

X, Y = sp.symbols("x y", real=True)
Equation = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=80)]


class SimultaneousEquationsParams(PrimitiveParams):
    equation_1: Equation = Field(description='e.g. "3*x + 2*y = 16"')
    equation_2: Equation = Field(description='e.g. "x - 2*y = 0" or "y = x**2 - 3"')
    method: Literal["elimination", "substitution"] = "elimination"


class SimultaneousEquations(StagedPrimitive[SimultaneousEquationsParams]):
    primitive_id = "SimultaneousEquations"
    version = "1"
    topic = "Algebra and graphs"
    params_model = SimultaneousEquationsParams
    layout = LayoutContract(region=style.WORKING_REGION, allowed_overlaps=[("result_box", "*")])

    def default_params(self) -> SimultaneousEquationsParams:
        return SimultaneousEquationsParams(equation_1="3*x + 2*y = 16", equation_2="x - 2*y = 0")

    def validate(self, params: SimultaneousEquationsParams) -> list[PredicateFailure]:
        try:
            work = _Working(params)
        except _Bad as bad:
            return [bad.failure]
        if not work.solutions:
            return [
                _failure(
                    "consistency",
                    "real_solution",
                    "the equations have no real solution",
                    "equation_2",
                )
            ]
        return []

    def computed_values(self, params: SimultaneousEquationsParams) -> dict[str, str]:
        work = _Working(params)
        values = {"number_of_solutions": str(len(work.solutions))}
        for i, (x, y) in enumerate(work.solutions, start=1):
            values[f"x_{i}"] = format_value(x)
            values[f"y_{i}"] = format_value(y)
        return values

    def build(self, params: SimultaneousEquationsParams, level):
        work = _Working(params)
        box = style.region_box(self.layout.region).shrink(style.PADDING)
        lines = []
        for _, tex, _ in work.lines:
            line = MathTex(inline(tex), font_size=style.FONT_SIZE)
            if line.width > box.width:
                line.scale_to_fit_width(box.width)
            lines.append(line)
        group = VGroup(*lines).arrange(DOWN, aligned_edge=LEFT, buff=0.3)
        style.fit_inside(group, box)
        parts = {name: line for (name, _, _), line in zip(work.lines, lines, strict=True)}
        parts["result_box"] = SurroundingRectangle(
            lines[-1], color=style.HIGHLIGHT_COLOUR, buff=0.1
        )
        return parts

    def stages(self, params: SimultaneousEquationsParams, level) -> list[Stage]:
        work = _Working(params)
        steps = [stage(name, words, 2.5, [name]) for name, _, words in work.lines]
        steps[0] = combine("equations", "Write the two equations and number them", 2.5, *steps[:2])
        del steps[1]
        steps[-1] = combine(
            steps[-1].name,
            steps[-1].description,
            2.5,
            steps[-1],
            stage("box", "", 0.1, ["result_box"], emphasise=["result_box"]),
        )
        middle = steps[1:-1]

        def standard(s):
            half = max(1, len(middle) // 2)
            return [
                s[0],
                combine("first", work.first_half_words, 3.0, *middle[:half]),
                combine("second", work.second_half_words, 3.0, *middle[half:], s[-1]),
            ]

        def concise(s):
            return [s[0], combine("solve", f"Solve by {params.method}", 4.0, *middle, s[-1])]

        return by_level(level, steps, standard, concise)


class _Bad(Exception):
    def __init__(self, failure: PredicateFailure):
        self.failure = failure


def _parse(text: str, name: str):
    try:
        lhs, rhs = parse_equation(text, {"x", "y"})
    except ExpressionError as error:
        raise _Bad(_failure("parsing", "equation_parses", str(error), name)) from None
    return sp.nsimplify(lhs, rational=True), sp.nsimplify(rhs, rational=True)


def _linear(lhs, rhs) -> tuple | None:
    """a, b, c with a x + b y = c, or None if the equation is not linear."""
    expr = sp.expand(lhs - rhs)
    if not expr.free_symbols or sp.Poly(expr, X, Y).total_degree() != 1:
        return None
    a, b = expr.coeff(X), expr.coeff(Y)
    return a, b, -expr.subs({X: 0, Y: 0})


def _row(a, b, c) -> str:
    return f"{tidy_latex(a * X + b * Y)} = {latex_value(c)}"


class _Working:
    """The lines as (name, LaTeX, what the step says) and the solutions."""

    def __init__(self, params: SimultaneousEquationsParams):
        first, second = (
            _parse(params.equation_1, "equation_1"),
            _parse(params.equation_2, "equation_2"),
        )
        self.lines = [
            ("eq_1", rf"{written_latex(params.equation_1)} \quad (1)", ""),
            ("eq_2", rf"{written_latex(params.equation_2)} \quad (2)", ""),
        ]
        self.solutions = []
        if params.method == "elimination":
            self._eliminate(first, second)
        else:
            self._substitute(first, second)

    def _add(self, name, tex, words):
        self.lines.append((name, tex, words))

    def _eliminate(self, first, second):
        one, two = _linear(*first), _linear(*second)
        if one is None or two is None:
            raise _Bad(
                _failure(
                    "consistency",
                    "linear_equations",
                    "elimination needs two linear equations; use substitution",
                    "method",
                )
            )
        (a1, b1, c1), (a2, b2, c2) = one, two
        if a1 * b2 - a2 * b1 == 0:
            raise _Bad(
                _failure(
                    "consistency",
                    "one_solution",
                    "the lines are parallel or the same: no single solution",
                    "equation_2",
                )
            )
        # Eliminate y unless x is easier (its coefficients already match).
        eliminate_x = abs(a1) == abs(a2) and abs(b1) != abs(b2)
        p, q = (a1, a2) if eliminate_x else (b1, b2)
        # Multiply each equation by the size of the other's coefficient, less any common
        # factor: 3y and 2y become 6y in both.
        k1, k2 = abs(q), abs(p)
        if k1.is_integer and k2.is_integer:
            common = sp.igcd(int(k1), int(k2))
            k1, k2 = k1 / common, k2 / common
        rows = [(a1 * k1, b1 * k1, c1 * k1), (a2 * k2, b2 * k2, c2 * k2)]
        if k1 != 1:
            self._add(
                "scale_1",
                rf"(1) \times {latex_value(k1)}:\ {_row(*rows[0])} \quad (3)",
                f"Multiply equation 1 by {format_value(k1)}",
            )
        if k2 != 1:
            self._add(
                "scale_2",
                rf"(2) \times {latex_value(k2)}:\ {_row(*rows[1])} \quad (4)",
                f"Multiply equation 2 by {format_value(k2)}",
            )
        same_sign = (rows[0][0 if eliminate_x else 1] > 0) == (rows[1][0 if eliminate_x else 1] > 0)
        sign = -1 if same_sign else 1
        combined = tuple(r1 + sign * r2 for r1, r2 in zip(rows[0], rows[1], strict=True))
        unknown, other = (Y, X) if eliminate_x else (X, Y)
        left = "(3)" if k1 != 1 else "(1)"
        right = "(4)" if k2 != 1 else "(2)"
        operation = "-" if same_sign else "+"
        self._add(
            "combine",
            rf"{left} {operation} {right}:\ {_row(*combined)}",
            f"{'Subtract' if same_sign else 'Add'} to eliminate {other}",
        )
        value = sp.solve(sp.Eq(combined[0] * X + combined[1] * Y, combined[2]), unknown)[0]
        self._add("first_value", f"{unknown} = {latex_value(value)}", f"Solve for {unknown}")
        a, b, c = one
        substituted = (a * X + b * Y).subs(unknown, value)
        other_value = sp.solve(sp.Eq(substituted, c), other)[0]
        self._add(
            "substitute",
            rf"\text{{in }} (1):\ {tidy_latex(substituted)} = {latex_value(c)}"
            rf"\ \Rightarrow\ {other} = {latex_value(other_value)}",
            f"Substitute {unknown} into equation 1 to find {other}",
        )
        x, y = (other_value, value) if eliminate_x else (value, other_value)
        self.solutions = [(x, y)]
        self._add("answer", rf"x = {latex_value(x)},\ y = {latex_value(y)}", "So the solution is")
        self.first_half_words = "Make the coefficients match and eliminate one unknown"
        self.second_half_words = "Solve, substitute back and give the solution"

    def _substitute(self, first, second):
        linear_first = _linear(*first) is not None
        linear, other = (first, second) if linear_first else (second, first)
        coefficients = _linear(*linear)
        if coefficients is None:
            raise _Bad(
                _failure(
                    "consistency",
                    "one_linear",
                    "substitution needs at least one linear equation",
                    "equation_1",
                )
            )
        a, b, c = coefficients
        number = "1" if linear_first else "2"
        if b != 0:
            y_expr = sp.solve(sp.Eq(a * X + b * Y, c), Y)[0]
            self._add(
                "rearrange",
                rf"\text{{from }} ({number}):\ y = {tidy_latex(y_expr)}",
                "Make y the subject of the linear equation",
            )
            substituted = sp.expand(other[0].subs(Y, y_expr) - other[1].subs(Y, y_expr))
            solve_for, back = X, lambda v: y_expr.subs(X, v)
        else:
            x_value = c / a
            self._add(
                "rearrange",
                rf"\text{{from }} ({number}):\ x = {latex_value(x_value)}",
                "The linear equation gives x",
            )
            substituted = sp.expand(other[0].subs(X, x_value) - other[1].subs(X, x_value))
            solve_for, back = Y, None
        _, primitive = sp.Poly(substituted, solve_for).primitive()
        if primitive.LC() < 0:
            primitive = -primitive
        equation = primitive.as_expr()
        self._add(
            "substituted",
            f"{tidy_latex(equation)} = 0",
            "Substitute it into the other equation and collect the terms",
        )
        roots = sorted({r for r in sp.solve(equation, solve_for) if r.is_real}, key=float)
        factored = sp.factor(equation)
        if factored != equation and len(roots) > 0:
            self._add("factorised", f"{sp.latex(factored)} = 0", "Factorise")
        if not roots:
            return
        names = r"\ \text{or}\ ".join(f"{solve_for} = {latex_value(r)}" for r in roots)
        self._add(
            "roots", names, f"So {solve_for} has {len(roots)} value{'s' if len(roots) > 1 else ''}"
        )
        if back is not None:
            self.solutions = [(r, sp.nsimplify(back(r))) for r in roots]
        else:
            self.solutions = [(x_value, r) for r in roots]
        pairs = r",\quad ".join(
            rf"({latex_value(x)},\ {latex_value(y)})" for x, y in self.solutions
        )
        self._add("answer", pairs, "Find each partner value: the solutions")
        self.first_half_words = "Make y the subject and substitute it in"
        self.second_half_words = "Solve, then find each partner value"


def _failure(kind, predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(kind=kind, predicate=predicate, message=message, parameters=[parameter])
