"""SurdSimplifier: surds in their simplest form, added and subtracted, and denominators made
rational (4024 1.18; PRIMITIVES.md #9).

Simplify: the square factors of n are listed and the largest, k², is taken out:
√n = √(k² × m) = √(k²) × √m = k√m. Combine: each surd is simplified on the right, then like
surds are collected on the left. Rationalise: the fraction is multiplied by a form of 1, √c/√c
for a single surd or the conjugate for a + b√c, using (a + b)(a − b) = a² − b². SymPy works out
every line.
"""

import re
from typing import Annotated, Literal

import sympy as sp
from manim import DOWN, LEFT, MathTex, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, split_columns, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import ExpressionError, parse_expression

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
TERM = re.compile(r"\s*([+-]?)\s*(\d+)?\s*\*?\s*sqrt\(\s*(\d+)\s*\)")
MAX_FACTOR_ROWS = 5


class SurdSimplifierParams(PrimitiveParams):
    kind: Literal["simplify", "combine", "rationalise"]
    number: Annotated[int, Field(ge=8, le=2000)] | None = Field(
        default=None, description="For simplify: n in √n"
    )
    expression: Text | None = Field(
        default=None, description='For combine: e.g. "2*sqrt(12) + sqrt(27) - sqrt(3)"'
    )
    numerator: Text | None = Field(default=None, description='For rationalise: e.g. "6"')
    denominator: Text | None = Field(
        default=None, description='For rationalise: e.g. "sqrt(3)", "2*sqrt(5)", "3 - sqrt(5)"'
    )


class SurdSimplifier(StagedPrimitive[SurdSimplifierParams]):
    primitive_id = "SurdSimplifier"
    version = "1"
    topic = "Number"
    params_model = SurdSimplifierParams
    layout = LayoutContract(region=style.GRAPH_REGION, allowed_overlaps=[("factor_box", "*")])

    def default_params(self) -> SurdSimplifierParams:
        return SurdSimplifierParams(kind="simplify", number=72)

    def validate(self, params: SurdSimplifierParams) -> list[PredicateFailure]:
        if params.kind == "simplify":
            if params.number is None:
                return [_failure("needs_number", "simplify needs a number", "number")]
            n = params.number
            if sp.sqrt(n).is_integer:
                return [_failure("not_square", f"{n} is a square number: no surd", "number")]
            if _largest_square(n) == 1:
                return [_failure("has_square_factor", f"√{n} is already simplest", "number")]
            return []
        if params.kind == "combine":
            if params.expression is None:
                return [_failure("needs_expression", "combine needs an expression", "expression")]
            terms = _terms(params.expression)
            if terms is None:
                message = 'write it as terms like "2*sqrt(12) + sqrt(27)"'
                return [_failure("expression_parses", message, "expression")]
            if len(terms) < 2:
                return [_failure("two_terms", "give at least two surds", "expression")]
            if any(n < 2 for _, n in terms):
                return [_failure("radicand_at_least_2", "each surd needs n ≥ 2", "expression")]
            return []
        if params.numerator is None or params.denominator is None:
            message = "rationalise needs a numerator and a denominator"
            return [_failure("needs_fraction", message, "numerator", "denominator")]
        try:
            top, bottom = _parse(params.numerator), _parse(params.denominator)
        except ExpressionError as error:
            return [_failure("fraction_parses", str(error), "numerator", "denominator")]
        if bottom == 0 or top == 0:
            return [_failure("nonzero", "neither part may be 0", "numerator", "denominator")]
        if not _surds(bottom):
            message = "the denominator has no surd to remove"
            return [_failure("surd_denominator", message, "denominator")]
        if isinstance(bottom, sp.Add) and (
            len(bottom.args) != 2 or _split(params.denominator) is None
        ):
            message = "use b√c or two terms, as in a + b√c"
            return [_failure("two_terms", message, "denominator")]
        return []

    def computed_values(self, params: SurdSimplifierParams) -> dict[str, str]:
        return {"answer": str(_answer(params))}

    def build(self, params: SurdSimplifierParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        left, right = split_columns(area, [1.25, 1], gap=0.4)
        lines, side, question = _working(params)
        parts = {"question": text_line(question, upper)}
        rows = [MathTex(tex, font_size=style.FONT_SIZE) for tex in lines]
        VGroup(*rows).arrange(DOWN, aligned_edge=LEFT, buff=0.35)
        style.fit_inside(VGroup(*rows), left)
        for i, row in enumerate(rows, start=1):
            parts[f"line_{i}"] = row
        heading, side_rows, chosen = side

        def colour(i):
            return style.HIGHLIGHT_COLOUR if i == chosen else style.TEXT_COLOUR

        notes = [label(heading, size=30)] + [
            MathTex(tex, font_size=34, color=colour(i)) for i, tex in enumerate(side_rows, start=1)
        ]
        VGroup(*notes).arrange(DOWN, aligned_edge=LEFT, buff=0.3)
        style.fit_inside(VGroup(*notes), right)
        parts["side_heading"] = notes[0]
        for i, note in enumerate(notes[1:], start=1):
            parts[f"side_{i}"] = note
        result = lines[-1].removeprefix("= ")
        parts["answer"] = text_line(rf"{lines[0]} = {result}", lower, colour=style.HIGHLIGHT_COLOUR)
        return parts

    def stages(self, params: SurdSimplifierParams, level) -> list[Stage]:
        lines, side, _ = _working(params)
        side_names = ["side_heading", *(f"side_{i}" for i in range(1, len(side[1]) + 1))]
        last = f"line_{len(lines)}"
        if params.kind == "simplify":
            k = _largest_square(params.number) ** 2
            steps = [
                stage("question", "Write the surd", 1.5, ["question", "line_1"]),
                stage(
                    "factors",
                    f"Look for square numbers that divide {params.number}; the largest is {k}",
                    3.5,
                    side_names,
                    emphasise=[f"side_{side[2]}"],
                ),
                stage("split", f"Write {params.number} as {k} times what is left", 2.5, ["line_2"]),
                stage(
                    "roots",
                    "The square root of a product is the product of the roots",
                    2.5,
                    ["line_3"],
                ),
                stage(
                    "answer",
                    "Take the square root of the square",
                    2.5,
                    [last, "answer"],
                    emphasise=["answer"],
                ),
            ]
        elif params.kind == "combine":
            steps = [
                stage("question", "Here are the surds", 1.5, ["question", "line_1"]),
                stage("each", "Simplify each surd first", 3.5, side_names),
                stage("rewrite", "Write them with the same surd", 2.5, ["line_2"]),
                stage(
                    "collect",
                    "Collect like surds, as you collect like terms",
                    2.5,
                    [last, "answer"],
                    emphasise=["answer"],
                ),
            ]
        else:
            steps = [
                stage("question", "A surd in the denominator", 1.5, ["question", "line_1"]),
                stage(
                    "multiply",
                    "Multiply top and bottom by the same thing: that is multiplying by 1",
                    3.5,
                    ["line_2", *side_names],
                ),
                stage("expand", "Multiply out; the denominator has no surd now", 3.0, ["line_3"]),
                stage(
                    "answer",
                    "Simplify",
                    2.0,
                    ["answer", *(["line_4"] if len(lines) > 3 else [])],
                    emphasise=["answer"],
                ),
            ]

        def standard(s):
            return [combine("setup", s[1].description, 4.0, s[0], s[1]), *s[2:]]

        def concise(s):
            return [
                combine("setup", s[1].description, 4.0, s[0], s[1]),
                combine("working", "Work it through", 3.5, *s[2:]),
            ]

        return by_level(level, steps, standard, concise)


def _parse(text: str) -> sp.Expr:
    return parse_expression(text, set())


def _surds(expr: sp.Expr) -> set[sp.Expr]:
    return {p for p in expr.atoms(sp.Pow) if p.exp == sp.Rational(1, 2)}


def _largest_square(n: int) -> int:
    """The largest k with k² dividing n."""
    k = 1
    for prime, power in sp.factorint(n).items():
        k *= prime ** (power // 2)
    return k


def _terms(text: str) -> list[tuple[int, int]] | None:
    """[(coefficient, n)] for terms written like 2*sqrt(12) - sqrt(3), or None."""
    terms, position = [], 0
    while position < len(text):
        match = TERM.match(text, position)
        if not match or (terms and not match.group(1)):
            return None
        sign = -1 if match.group(1) == "-" else 1
        terms.append((sign * int(match.group(2) or 1), int(match.group(3))))
        position = match.end()
        if not text[position:].strip():
            break
    return terms or None


def _simplest(n: int) -> tuple[int, int]:
    k = _largest_square(n)
    return k, n // (k * k)


def _surd_latex(coefficient: int, n: int, first: bool) -> str:
    sign = "-" if coefficient < 0 else ("" if first else "+")
    size = abs(coefficient)
    if n == 1:
        return f"{sign} {size}"
    return rf"{sign} {'' if size == 1 else size}\sqrt{{{n}}}"


def _answer(params: SurdSimplifierParams) -> sp.Expr:
    if params.kind == "simplify":
        return sp.sqrt(params.number)
    if params.kind == "combine":
        return sp.Add(*(c * sp.sqrt(n) for c, n in _terms(params.expression)))
    return sp.radsimp(_parse(params.numerator) / _parse(params.denominator))


def _working(params: SurdSimplifierParams):
    """(left lines, (side heading, side rows, highlighted row), question)."""
    if params.kind == "simplify":
        n = params.number
        k = _largest_square(n)
        m = n // (k * k)
        squares = [j * j for j in range(2, k + 1) if n % (j * j) == 0]
        if len(squares) > MAX_FACTOR_ROWS:
            squares = squares[: MAX_FACTOR_ROWS - 1] + squares[-1:]
        rows = [rf"{n} = {s} \times {n // s}" for s in squares]
        lines = [
            rf"\sqrt{{{n}}}",
            rf"= \sqrt{{{k * k} \times {m}}}",
            rf"= \sqrt{{{k * k}}} \times \sqrt{{{m}}}",
            rf"= {k}\sqrt{{{m}}}" if m > 1 else f"= {k}",
        ]
        heading = rf"\text{{Square factors of }} {n}"
        return lines, (heading, rows, len(rows)), rf"\text{{Simplify }} \sqrt{{{n}}}"
    if params.kind == "combine":
        terms = _terms(params.expression)
        written = " ".join(_surd_latex(c, n, i == 0).strip() for i, (c, n) in enumerate(terms))
        simplified = []
        rows = []
        for c, n in terms:
            k, m = _simplest(n)
            simplified.append((c * k, m))
            if k > 1:
                rows.append(
                    rf"\sqrt{{{n}}} = \sqrt{{{k * k}}}\sqrt{{{m}}} = "
                    rf"{k}\sqrt{{{m}}}"
                    if m > 1
                    else rf"\sqrt{{{n}}} = {k}"
                )
            else:
                rows.append(rf"\sqrt{{{n}}} \text{{ is simplest}}")
        rows = list(dict.fromkeys(rows))
        rewritten = " ".join(
            _surd_latex(c, m, i == 0).strip() for i, (c, m) in enumerate(simplified)
        )
        collected: dict[int, int] = {}
        for c, m in simplified:
            collected[m] = collected.get(m, 0) + c
        kept = [(c, m) for m, c in collected.items() if c != 0]
        total = " ".join(_surd_latex(c, m, i == 0).strip() for i, (c, m) in enumerate(kept))
        lines = [written, f"= {rewritten}", f"= {total or '0'}"]
        return lines, (r"\text{Each surd}", rows, -1), rf"\text{{Simplify }} {written}"
    top, bottom = _parse(params.numerator), _parse(params.denominator)
    if isinstance(bottom, sp.Add):
        first, second = _split(params.denominator)
        multiplier = first - second
        m = _sum_latex([first, -second])
        rows = [
            r"(a + b)(a - b) = a^2 - b^2",
            rf"= {_square(first)} - {_square(second)}",
            rf"= {sp.latex(first**2)} - {sp.latex(second**2)} = "
            rf"{sp.latex(sp.expand(first**2 - second**2))}",
        ]
        heading = r"\text{Multiply by the conjugate}"
        b = _sum_latex([first, second])
    else:
        multiplier = sp.Mul(*_surds(bottom))
        m = sp.latex(multiplier)
        rows = [rf"{m} \times {m} = {sp.latex(multiplier**2)}"]
        heading = rf"\text{{Multiply by }} {m}"
        b = sp.latex(bottom)
    t = _sum_latex(sp.Add.make_args(top)) if isinstance(top, sp.Add) else sp.latex(top)
    new_top, new_bottom = sp.expand(top * multiplier), sp.expand(bottom * multiplier)
    product = _fraction_latex(new_top, new_bottom)
    lines = [
        rf"\frac{{{t}}}{{{b}}}",
        rf"= \frac{{{t}}}{{{b}}} \times \frac{{{m}}}{{{m}}}",
        f"= {product}",
    ]
    numerator, denominator = sp.fraction(sp.factor_terms(sp.radsimp(top / bottom)))
    final = _fraction_latex(sp.expand(numerator), denominator)
    if final != product:
        lines.append(f"= {final}")
    question = rf"\text{{Rationalise }} \frac{{{t}}}{{{b}}}"
    return lines, (heading, rows, -1), question


def _sum_latex(terms) -> str:
    """Terms joined in the order given: 3 - \\sqrt{5}, not -\\sqrt{5} + 3."""
    out = []
    for i, term in enumerate(terms):
        text = sp.latex(term)
        if text.startswith("-"):
            out.append(("- " if i else "-") + text[1:].strip())
        else:
            out.append(("+ " if i else "") + text)
    return " ".join(out)


def _split(text: str) -> tuple[sp.Expr, sp.Expr] | None:
    """The two terms of a + b as written, so the conjugate keeps the first term."""
    depth = 0
    for i, ch in enumerate(text):
        depth += (ch == "(") - (ch == ")")
        if ch in "+-" and depth == 0 and text[:i].strip():
            first, second = _parse(text[:i]), _parse(text[i + 1 :])
            second = -second if ch == "-" else second
            if isinstance(first, sp.Add) or isinstance(second, sp.Add):
                return None
            return first, second
    return None


def _ordered(expr: sp.Expr) -> str:
    terms = sorted(
        sp.Add.make_args(sp.expand(expr)),
        key=lambda t: (bool(_surds(t)), t.could_extract_minus_sign()),
    )
    return _sum_latex(terms)


def _fraction_latex(top: sp.Expr, bottom: sp.Expr) -> str:
    if bottom == 1:
        return _ordered(top)
    if bottom == -1:
        return _ordered(-top)
    return rf"\frac{{{_ordered(top)}}}{{{_ordered(bottom)}}}"


def _square(term: sp.Expr) -> str:
    size = -term if term.could_extract_minus_sign() else term
    return f"{size}^2" if size.is_Integer else rf"\left({sp.latex(size)}\right)^2"


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
