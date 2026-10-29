"""PolynomialDivision: a polynomial divided by a linear or quadratic one by long division, with
the quotient and remainder, and the remainder and factor theorems (9709 2.1, 3.1).

Each step divides the leading term of what is left by the leading term of the divisor, writes
that term in the quotient, multiplies the divisor by it and subtracts, which removes the leading
term. Missing powers are written with 0 so the columns line up. For a linear divisor ax + b the
remainder is also f(−b/a) (the remainder theorem); a remainder of 0 means ax + b is a factor
(the factor theorem), and the quotient can then be factorised to finish. SymPy checks that
f(x) = divisor × quotient + remainder.
"""

import sympy as sp
from manim import Line, MathTex, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import stack_lines
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import ExpressionError, latex_value, parse_expression, tidy_latex

X = sp.Symbol("x", real=True)
ROW_GAP = 0.3
"""Space between rows of the division; rows with fractions are taller."""


class PolynomialDivisionParams(PrimitiveParams):
    dividend: str = Field(
        min_length=1, max_length=80, description="Degree 2 to 4, e.g. 2*x**3 + 3*x**2 - 8*x + 3"
    )
    divisor: str = Field(
        min_length=1, max_length=40, description='Linear or quadratic, e.g. "x - 1" or "x**2 + 1"'
    )


class PolynomialDivision(StagedPrimitive[PolynomialDivisionParams]):
    primitive_id = "PolynomialDivision"
    version = "1"
    topic = "Algebra"
    params_model = PolynomialDivisionParams
    layout = LayoutContract(region=FULL_FRAME, allowed_overlaps=[("bar", "*"), ("rule_*", "*")])

    def default_params(self) -> PolynomialDivisionParams:
        return PolynomialDivisionParams(dividend="2*x**3 + 3*x**2 - 8*x + 3", divisor="x - 1")

    def validate(self, params: PolynomialDivisionParams) -> list[PredicateFailure]:
        polys = {}
        for name in ("dividend", "divisor"):
            try:
                expr = parse_expression(getattr(params, name), {"x"})
            except ExpressionError as error:
                return [_failure("parsing", "expression_parses", str(error), name)]
            if not expr.is_polynomial(X):
                return [
                    _failure("consistency", "polynomial", f"the {name} must be a polynomial", name)
                ]
            polys[name] = sp.Poly(sp.nsimplify(expr, rational=True), X)
        if not 2 <= polys["dividend"].degree() <= 4:
            message = "the dividend must have degree 2, 3 or 4"
            return [_failure("consistency", "degree_range", message, "dividend")]
        if polys["divisor"].degree() not in (1, 2):
            message = "the divisor must be linear or quadratic"
            return [_failure("consistency", "degree_range", message, "divisor")]
        if polys["divisor"].degree() >= polys["dividend"].degree():
            message = "the divisor must have a lower degree than the dividend"
            return [_failure("consistency", "degree_order", message, "divisor")]
        return []

    def computed_values(self, params: PolynomialDivisionParams) -> dict[str, str]:
        d = _Division(params)
        values = {"quotient": str(d.quotient.as_expr()), "remainder": str(d.remainder.as_expr())}
        if d.root is not None:
            values["remainder_theorem"] = f"f({d.root}) = {d.remainder.as_expr()}"
            values["is_factor"] = "yes" if d.remainder.is_zero else "no"
        return values

    def build(self, params: PolynomialDivisionParams, level):
        d = _Division(params)
        n = d.f.degree()
        powers = list(range(n, -1, -1))
        # each row: {power: coefficient}; row 0 the quotient, row 1 the dividend
        rows: list[dict[int, sp.Rational]] = [
            {
                p: d.quotient.coeff_monomial(X**p)
                for p in range(d.quotient.degree(), -1, -1)
                if d.quotient.coeff_monomial(X**p) != 0
            },
            {p: d.f.coeff_monomial(X**p) for p in powers},
        ]
        for product, rest in d.steps:
            top = product.degree()
            rows.append(
                {p: product.coeff_monomial(X**p) for p in range(top, top - d.g.degree() - 1, -1)}
            )
            rows.append(
                {0: sp.Integer(0)}
                if rest.is_zero
                else {p: rest.coeff_monomial(X**p) for p in range(rest.degree(), -1, -1)}
            )
        texts = [[(p, _term(c, p, first)) for first, (p, c) in _with_first(row)] for row in rows]
        widths = {p: 0.0 for p in powers}
        mobs = []
        for row in texts:
            line = []
            for p, tex in row:
                mob = MathTex(tex, font_size=36)
                widths[p] = max(widths[p], mob.width)
                line.append((p, mob))
            mobs.append(line)
        centres, x = {}, 0.0
        for p in powers:
            centres[p] = x + widths[p] / 2
            x += widths[p] + 0.25
        group = VGroup()
        row_groups = []
        y, previous = 0.0, 0.0
        for r, line in enumerate(mobs):
            height = max((mob.height for _, mob in line), default=0.4)
            if r:
                y -= previous / 2 + ROW_GAP + height / 2
            previous = height
            row_group = VGroup()
            for p, mob in line:
                mob.move_to([centres[p], y, 0])
                row_group.add(mob)
            row_groups.append(row_group)
            group.add(row_group)
        divisor = MathTex(tidy_latex(d.g.as_expr()), font_size=36)
        divisor.next_to(row_groups[1], [-1, 0, 0], buff=0.55)
        group.add(divisor)
        left = row_groups[1].get_left()[0] - 0.2
        right = x
        top = row_groups[1].get_top()[1] + 0.12
        bar = VGroup(
            Line([left, top, 0], [right, top, 0], stroke_width=3),
            Line([left, top, 0], [left, row_groups[1].get_bottom()[1] - 0.1, 0], stroke_width=3),
        )
        group.add(bar)
        rules = []
        for i in range(len(d.steps)):
            product_row = row_groups[2 + 2 * i]
            rule = Line(
                [product_row.get_left()[0] - 0.1, product_row.get_bottom()[1] - 0.1, 0],
                [product_row.get_right()[0] + 0.1, product_row.get_bottom()[1] - 0.1, 0],
                stroke_width=2,
            )
            rules.append(rule)
            group.add(rule)
        area = style.region_box(style.GRAPH_REGION).shrink(style.PADDING + 0.2)
        style.fit_inside(group, area)
        parts = {
            "divisor": divisor,
            "bar": bar,
            "dividend": row_groups[1],
        }
        # quotient terms appear one per step
        for i, mob in enumerate(row_groups[0]):
            parts[f"quotient_{i}"] = mob
        for i in range(len(d.steps)):
            parts[f"product_{i}"] = row_groups[2 + 2 * i]
            parts[f"rule_{i}"] = rules[i]
            parts[f"rest_{i}"] = row_groups[3 + 2 * i]
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        rows_tex = d.rows()
        lines = stack_lines(
            [t for t, _ in rows_tex], box, size=30, colours=[c for _, c in rows_tex]
        )
        for i, line in enumerate(lines, start=1):
            parts[f"row_{i}"] = line
        return parts

    def stages(self, params: PolynomialDivisionParams, level) -> list[Stage]:
        d = _Division(params)
        steps = [
            stage(
                "setup",
                "Write the division, with a 0 for any missing power so the columns line up",
                3.0,
                ["divisor", "bar", "dividend"],
            )
        ]
        for i in range(len(d.steps)):
            steps.append(
                stage(
                    f"divide_{i}",
                    "Divide the leading term by the divisor's leading term: the next term of "
                    "the quotient",
                    2.5,
                    [f"quotient_{i}"],
                    emphasise=[f"quotient_{i}"],
                )
            )
            steps.append(
                stage(
                    f"subtract_{i}",
                    "Multiply the divisor by it, and subtract to remove the leading term",
                    3.0,
                    [f"product_{i}", f"rule_{i}", f"rest_{i}"],
                )
            )
        count = len(d.rows())
        steps.append(
            stage(
                "result",
                "What is left, of lower degree than the divisor, is the remainder",
                3.0,
                [f"row_{i}" for i in range(1, 5)],
                emphasise=["row_3"],
            )
        )
        if count > 4:
            steps.append(
                stage(
                    "theorem",
                    "The remainder theorem: the remainder is f at the root of the divisor"
                    + (", and 0 means a factor" if d.remainder.is_zero else ""),
                    3.5,
                    [f"row_{i}" for i in range(5, count + 1)],
                )
            )
        last = 1 + 2 * len(d.steps)

        def standard(s):
            merged = [
                combine(
                    f"step_{i}", "Divide, multiply and subtract", 3.5, s[1 + 2 * i], s[2 + 2 * i]
                )
                for i in range(len(d.steps))
            ]
            return [s[0], *merged, *s[last:]]

        def concise(s):
            return [
                combine("divide", "Divide, multiply and subtract, term by term", 5.0, *s[:last]),
                *s[last:],
            ]

        return by_level(level, steps, standard, concise)


class _Division:
    def __init__(self, params: PolynomialDivisionParams):
        self.f = sp.Poly(sp.nsimplify(parse_expression(params.dividend, {"x"}), rational=True), X)
        self.g = sp.Poly(sp.nsimplify(parse_expression(params.divisor, {"x"}), rational=True), X)
        self.quotient, self.remainder = sp.div(self.f, self.g)
        self.steps = []
        rest = self.f
        while not rest.is_zero and rest.degree() >= self.g.degree():
            term = sp.Poly(rest.LC() / self.g.LC() * X ** (rest.degree() - self.g.degree()), X)
            product = term * self.g
            rest = rest - product
            self.steps.append((product, rest))
        self.root = sp.nsimplify(sp.solve(self.g.as_expr(), X)[0]) if self.g.degree() == 1 else None

    def rows(self) -> list[tuple[str, object]]:
        f, g = tidy_latex(self.f.as_expr()), tidy_latex(self.g.as_expr())
        q, r = tidy_latex(self.quotient.as_expr()), self.remainder.as_expr()
        rows = [
            (rf"\mathrm{{f}}(x) = {f}", None),
            (rf"\text{{Quotient: }}{q}", style.CURVE_COLOUR),
            (
                rf"\text{{Remainder: }}{latex_value(r) if r.is_number else tidy_latex(r)}",
                style.HIGHLIGHT_COLOUR,
            ),
            (
                rf"\mathrm{{f}}(x) = \left({g}\right)\left({q}\right)"
                + (
                    ""
                    if r == 0
                    else (
                        rf" + {tidy_latex(r)}"
                        if not str(r).startswith("-")
                        else rf" - {tidy_latex(-r)}"
                    )
                ),
                None,
            ),
        ]
        if self.root is not None:
            value = self.f.as_expr().subs(X, self.root)
            rows.append(
                (
                    rf"\mathrm{{f}}\left({latex_value(self.root)}\right) = {latex_value(value)}",
                    style.RISE_COLOUR,
                )
            )
            if self.remainder.is_zero:
                rows.append((rf"\text{{So }}{g}\text{{ is a factor}}", style.RISE_COLOUR))
                full = sp.factor(self.f.as_expr())
                if full != self.f.as_expr():
                    rows.append((rf"\mathrm{{f}}(x) = {sp.latex(full)}", style.HIGHLIGHT_COLOUR))
            else:
                rows.append(
                    (rf"\text{{Not 0, so }}{g}\text{{ is not a factor}}", style.TANGENT_COLOUR)
                )
        return rows


def _with_first(row: dict) -> list:
    return [(i == 0, item) for i, item in enumerate(row.items())]


def _term(coefficient, power: int, first: bool) -> str:
    coefficient = sp.nsimplify(coefficient)
    x = "" if power == 0 else ("x" if power == 1 else f"x^{{{power}}}")
    size = abs(coefficient)
    body = latex_value(size) if (size != 1 or not x) else ""
    body += x
    if first:
        return ("-" if coefficient < 0 else "") + body
    return ("- " if coefficient < 0 else "+ ") + body


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
