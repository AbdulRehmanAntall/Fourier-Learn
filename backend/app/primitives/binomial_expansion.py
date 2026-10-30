"""BinomialExpansion: (a + bx)ⁿ expanded term by term, with Pascal's triangle for a positive
whole n, and for a rational n the series for (1 + y)ⁿ with the values of x it is valid for
(9709 1.6, 3.1).

For a positive whole n the term in xʳ is ⁿCᵣ a^(n−r) (bx)^r, and the coefficients ⁿCᵣ are row n
of Pascal's triangle. For any other rational n, a is taken outside first:
(a + bx)ⁿ = aⁿ(1 + (b/a)x)ⁿ, then (1 + y)ⁿ = 1 + ny + n(n − 1)/2! y² + ..., an infinite series
that is valid only while |y| < 1, that is |x| < |a/b|. Every coefficient is exact (SymPy).
"""

from typing import Annotated

import sympy as sp
from manim import MathTex, SurroundingRectangle, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_value, latex_value

X = sp.Symbol("x", real=True)
Number = Annotated[float, Field(ge=-20, le=20)]


class BinomialExpansionParams(PrimitiveParams):
    a: Number = Field(description="The constant in (a + bx)^n; not 0, positive if n is not whole")
    b: Number = Field(description="The coefficient of x; not 0")
    n: Annotated[float, Field(ge=-5, le=8)] = Field(
        description="A positive whole number up to 8, or a fraction or negative number"
    )
    terms: Annotated[int, Field(ge=2, le=5)] = Field(
        default=4, description="How many terms to find (a whole n has at most n + 1)"
    )
    find_power: Annotated[int, Field(ge=1, le=8)] | None = Field(
        default=None, description="Optionally pick out the coefficient of x to this power"
    )


class BinomialExpansion(StagedPrimitive[BinomialExpansionParams]):
    primitive_id = "BinomialExpansion"
    version = "1"
    topic = "Series"
    params_model = BinomialExpansionParams
    layout = LayoutContract(region=FULL_FRAME, allowed_overlaps=[("*_box", "*")])

    def default_params(self) -> BinomialExpansionParams:
        return BinomialExpansionParams(a=2, b=3, n=5, terms=4, find_power=2)

    def validate(self, params: BinomialExpansionParams) -> list[PredicateFailure]:
        if params.a == 0 or params.b == 0:
            return [_failure("nonzero", "a and b must not be 0", "a", "b")]
        n = exact(params.n)
        whole = n.is_integer and n > 0
        if n == 0:
            return [_failure("power_nonzero", "n must not be 0", "n")]
        if not whole and n.q > 4:
            message = "a fractional n should have a small denominator, such as 1/2 or -2/3"
            return [_failure("simple_power", message, "n")]
        if not whole and params.a < 0:
            message = "with n not a positive whole number, a must be positive"
            return [_failure("a_positive", message, "a")]
        if whole and params.terms > n + 1:
            message = f"(a + bx)^{n} has only {n + 1} terms"
            return [_failure("terms_exist", message, "terms")]
        if params.find_power is not None and params.find_power >= params.terms:
            message = "find_power must be one of the terms shown: below terms"
            return [_failure("power_shown", message, "find_power", "terms")]
        return []

    def computed_values(self, params: BinomialExpansionParams) -> dict[str, str]:
        e = _Expansion(params)
        values = {f"coefficient_{r}": str(c) for r, c in enumerate(e.coefficients)}
        values["expansion"] = " + ".join(str(c * X**r) for r, c in enumerate(e.coefficients))
        if not e.whole:
            values["valid_for"] = f"|x| < {format_value(e.radius)}"
        return values

    def build(self, params: BinomialExpansionParams, level):
        e = _Expansion(params)
        left = style.region_box(style.GRAPH_REGION).shrink(style.PADDING)
        title = style.Box(left.left, left.right, left.top - 0.9, left.top)
        body = style.Box(left.left, left.right, left.bottom, left.top - 1.1)
        parts = {"title": text_line(rf"\left({e.inner_latex()}\right)^{{{e.n_latex}}}", title)}
        if e.whole:
            rows = VGroup()
            for m in range(int(e.n) + 1):
                row = VGroup(
                    *(
                        MathTex(
                            str(sp.binomial(m, r)),
                            font_size=34,
                            color=style.HIGHLIGHT_COLOUR if m == e.n else style.TEXT_COLOUR,
                        )
                        for r in range(m + 1)
                    )
                ).arrange([1, 0, 0], buff=0.45)
                rows.add(row)
            rows.arrange([0, -1, 0], buff=0.25)
            style.fit_inside(rows, body)
            parts["pascal"] = VGroup(*rows[:-1])
            parts["row_n"] = rows[-1]
            parts["row_n_box"] = SurroundingRectangle(rows[-1], color=style.HIGHLIGHT_COLOUR)
        else:
            general = [
                r"(1 + y)^n = 1 + ny + \frac{n(n - 1)}{2!}y^2",
                r"\quad + \frac{n(n - 1)(n - 2)}{3!}y^3 + \dots",
                r"\text{valid only for } |y| < 1",
            ]
            lines = stack_lines(general, body, size=36, buff=0.35)
            parts["formula"] = VGroup(*lines[:2])
            parts["validity"] = lines[2]
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        rows_tex = e.rows()
        texts = stack_lines(
            [t for t, _ in rows_tex], box, size=30, colours=[c for _, c in rows_tex]
        )
        for i, text in enumerate(texts):
            parts[f"work_{i}"] = text
        if params.find_power is not None:
            index = e.term_row(params.find_power)
            parts["find_box"] = SurroundingRectangle(
                texts[index], color=style.TANGENT_COLOUR, buff=0.08
            )
        return parts

    def stages(self, params: BinomialExpansionParams, level) -> list[Stage]:
        e = _Expansion(params)
        rows = e.rows()
        count = len(rows)
        steps = []
        if e.whole:
            steps.append(
                stage(
                    "pascal",
                    "The coefficients come from row n of Pascal's triangle",
                    3.0,
                    ["title", "pascal", "row_n", "row_n_box"],
                    emphasise=["row_n"],
                )
            )
            first = 0
        else:
            steps.append(
                stage(
                    "formula",
                    "For a power that is not a positive whole number, use the series for 1 plus "
                    "y to the n",
                    3.5,
                    ["title", "formula", "validity"],
                )
            )
            words = (
                "The bracket already starts with 1: y is the rest"
                if e.a == 1
                else "First take a to the n outside, so the bracket starts with 1"
            )
            steps.append(stage("factor", words, 3.0, ["work_0"]))
            first = 1
        term_rows = list(range(first, first + params.terms))
        for r, index in enumerate(term_rows):
            steps.append(
                stage(
                    f"term_{r}",
                    _term_words(r, e.whole),
                    2.5,
                    [f"work_{index}"],
                )
            )
        steps.append(
            stage(
                "result",
                "Add the terms" if e.whole else "Multiply each by a to the n, and add",
                2.5,
                [f"work_{first + params.terms}"],
                emphasise=[f"work_{first + params.terms}"],
            )
        )
        if not e.whole:
            steps.append(
                stage(
                    "valid",
                    "The series is valid only while the y in the bracket is between minus 1 and 1",
                    3.0,
                    [f"work_{count - 1}"],
                    emphasise=[f"work_{count - 1}"],
                )
            )
        if params.find_power is not None:
            steps.append(
                stage(
                    "find",
                    f"The coefficient of x to the power {params.find_power} is in this term",
                    2.5,
                    ["find_box"],
                )
            )
        lead = 1 if e.whole else 2
        terms_end = lead + params.terms

        def standard(s):
            return [
                *s[:lead],
                combine("terms", "Work out each term", 4.0, *s[lead:terms_end]),
                *s[terms_end:],
            ]

        def concise(s):
            out = standard(s)
            if e.whole:
                return [
                    combine("terms", "Each term from Pascal's triangle", 4.5, *out[:2]),
                    *out[2:],
                ]
            return [
                out[0],
                combine("terms", "Take a out, then each term", 4.5, *out[1:3]),
                *out[3:],
            ]

        return by_level(level, steps, standard, concise)


class _Expansion:
    def __init__(self, params: BinomialExpansionParams):
        self.params = params
        self.a, self.b, self.n = exact(params.a), exact(params.b), exact(params.n)
        self.whole = bool(self.n.is_integer and self.n > 0)
        self.n_latex = latex_value(self.n)
        expr = (self.a + self.b * X) ** self.n
        series = sp.series(expr, X, 0, params.terms).removeO()
        self.coefficients = [sp.nsimplify(series.coeff(X, r)) for r in range(params.terms)]
        self.y = self.b / self.a
        self.radius = abs(self.a / self.b)

    def inner_latex(self) -> str:
        return _sum_latex(self.a, self.b * X)

    def term_row(self, power: int) -> int:
        return power if self.whole else power + 1

    def rows(self) -> list[tuple[str, object]]:
        rows = []
        if not self.whole and self.a == 1:
            rows.append((rf"y = {_monomial(self.y, 1)}", None))
        elif not self.whole:
            rows.append(
                (
                    rf"= {latex_value(self.a)}^{{{self.n_latex}}}\left({_sum_latex(1, self.y * X)}"
                    rf"\right)^{{{self.n_latex}}}",
                    None,
                )
            )
        for r in range(self.params.terms):
            coefficient = self.coefficients[r]
            if self.whole:
                a_part = (
                    ""
                    if self.a == 1 or r == self.n
                    else rf"\left({latex_value(self.a)}\right)^{{{self.n - r}}}"
                )
                bx = _monomial(self.b, 1)
                b_part = (
                    ""
                    if r == 0
                    else rf"\left({bx}\right)^{{{r}}}"
                    if r > 1
                    else rf"\left({bx}\right)"
                )
                choose = rf"\binom{{{self.n}}}{{{r}}}"
                rows.append((rf"{choose}{a_part}{b_part} = {_monomial(coefficient, r)}", None))
            else:
                falling = "".join(rf"\left({latex_value(self.n - j)}\right)" for j in range(r))
                factor = (
                    "1"
                    if r == 0
                    else rf"\frac{{{falling}}}{{{r}!}}\left({_monomial(self.y, 1)}\right)^{{{r}}}"
                    if r > 1
                    else rf"{falling}\left({_monomial(self.y, 1)}\right)"
                )
                inside = coefficient / self.a**self.n
                rows.append((factor if r == 0 else rf"{factor} = {_monomial(inside, r)}", None))
        series = _series_latex(self.coefficients)
        prefix = rf"\left({self.inner_latex()}\right)^{{{self.n_latex}}}"
        tail = "" if self.whole and self.params.terms == self.n + 1 else r" + \dots"
        rows.append((rf"{prefix} = {series}{tail}", style.HIGHLIGHT_COLOUR))
        if not self.whole:
            rows.append(
                (
                    rf"\left|{_monomial(self.y, 1)}\right| < 1:\ |x| < {latex_value(self.radius)}",
                    style.RISE_COLOUR,
                )
            )
        return rows


def _fraction(value) -> str:
    """A rational exactly, however large its denominator: binomial coefficients are exact."""
    value = sp.nsimplify(value)
    if isinstance(value, sp.Rational) and value.q != 1:
        sign = "-" if value < 0 else ""
        return rf"{sign}\frac{{{abs(value.p)}}}{{{value.q}}}"
    return latex_value(value)


def _monomial(coefficient, power: int) -> str:
    coefficient = sp.nsimplify(coefficient)
    if power == 0:
        return _fraction(coefficient)
    x = "x" if power == 1 else f"x^{{{power}}}"
    if coefficient == 1:
        return x
    if coefficient == -1:
        return "-" + x
    return _fraction(coefficient) + x


def _sum_latex(constant, term) -> str:
    coefficient = sp.nsimplify(term / X)
    sign = "-" if coefficient < 0 else "+"
    return f"{latex_value(constant)} {sign} {_monomial(abs(coefficient), 1)}"


def _series_latex(coefficients) -> str:
    out = ""
    for r, c in enumerate(coefficients):
        if c == 0:
            continue
        term = _monomial(abs(c), r)
        if not out:
            out = term if c > 0 else "-" + term
        else:
            out += f" {'-' if c < 0 else '+'} {term}"
    return out


def _term_words(r: int, whole: bool) -> str:
    if r == 0:
        return "The first term" if whole else "The first term of the bracket is 1"
    if whole:
        return f"The term in x to the power {r}: n choose {r}, times the powers of a and b x"
    return f"The term in y to the power {r}, from the formula"


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
