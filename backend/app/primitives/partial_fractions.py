"""PartialFractions: a proper rational function split into partial fractions, for denominators
of the three syllabus types (9709 3.1, 3.5).

The form is chosen from the denominator: A/(ax + b) for each linear factor, A/(cx + d) +
B/(cx + d)² for a repeated one, and (Bx + C)/(cx² + d) for a quadratic factor that does not
factorise. Multiplying up gives an identity true for every x, so substituting the root of each
linear factor finds its constant at once, and comparing coefficients finds the rest. SymPy finds
every constant exactly and checks the answer recombines to the original fraction.
"""

import sympy as sp
from manim import SurroundingRectangle
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import ExpressionError, latex_value, parse_expression, tidy_latex

X = sp.Symbol("x", real=True)
LETTERS = sp.symbols("A B C", real=True)
UNKNOWN_COLOUR = style.RISE_COLOUR


class PartialFractionsParams(PrimitiveParams):
    numerator: str = Field(min_length=1, max_length=60, description='e.g. "5*x + 1"')
    denominator: str = Field(
        min_length=1,
        max_length=60,
        description='Factorised: "(x + 1)*(x - 2)", "(2*x + 1)*(x - 1)**2" or "(x + 2)*(x**2 + 1)"',
    )


class PartialFractions(StagedPrimitive[PartialFractionsParams]):
    primitive_id = "PartialFractions"
    version = "1"
    topic = "Algebra"
    params_model = PartialFractionsParams
    layout = LayoutContract(region=FULL_FRAME, allowed_overlaps=[("*_box", "*")])

    def default_params(self) -> PartialFractionsParams:
        return PartialFractionsParams(numerator="5*x + 1", denominator="(x + 1)*(x - 2)")

    def validate(self, params: PartialFractionsParams) -> list[PredicateFailure]:
        try:
            top = parse_expression(params.numerator, {"x"})
            bottom = parse_expression(params.denominator, {"x"})
        except ExpressionError as error:
            return [_failure("parsing", "expression_parses", str(error), "numerator")]
        if not top.is_polynomial(X) or not bottom.is_polynomial(X):
            message = "numerator and denominator must be polynomials"
            return [_failure("consistency", "polynomials", message, "numerator", "denominator")]
        factors = _factors(bottom)
        if factors is None:
            message = (
                "the denominator must be (ax + b)(cx + d), (ax + b)(cx + d)(ex + f), "
                "(ax + b)(cx + d)^2 or (ax + b)(cx^2 + d)"
            )
            return [_failure("consistency", "denominator_type", message, "denominator")]
        if sp.degree(top, X) >= sp.degree(sp.expand(bottom), X):
            message = "the numerator's degree must be below the denominator's"
            return [_failure("consistency", "proper", message, "numerator")]
        if sp.gcd(sp.expand(top), sp.expand(bottom)).has(X):
            message = "numerator and denominator share a factor: cancel it first"
            return [_failure("consistency", "no_common_factor", message, "numerator")]
        return []

    def computed_values(self, params: PartialFractionsParams) -> dict[str, str]:
        p = _Problem(params)
        values = {str(k): str(v) for k, v in p.solution.items()}
        values["result"] = str(p.result)
        return values

    def build(self, params: PartialFractionsParams, level):
        p = _Problem(params)
        left = style.region_box(style.GRAPH_REGION).shrink(style.PADDING)
        parts = {}
        setup = stack_lines(
            [
                rf"\dfrac{{{tidy_latex(p.top)}}}{{{p.bottom_latex()}}}",
                rf"= {p.form_latex()}",
            ],
            style.Box(left.left, left.right, left.top - 3.2, left.top),
            size=44,
            buff=0.5,
        )
        parts["fraction"], parts["form"] = setup
        result = text_line(
            rf"= {p.result_latex()}",
            style.Box(left.left, left.right, left.bottom, left.bottom + 1.6),
            colour=style.HIGHLIGHT_COLOUR,
            size=44,
        )
        parts["result"] = result
        parts["result_box"] = SurroundingRectangle(result, color=style.HIGHLIGHT_COLOUR, buff=0.12)
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        rows = p.rows()
        texts = stack_lines([t for t, _ in rows], box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: PartialFractionsParams, level) -> list[Stage]:
        p = _Problem(params)
        steps = [
            stage("fraction", "The fraction to split", 2.0, ["fraction"]),
            stage("form", p.form_words(), 3.5, ["form"], emphasise=["form"]),
            stage(
                "identity",
                "Multiply both sides by the denominator: an identity, true for every x",
                3.0,
                ["row_1"],
            ),
        ]
        for i, (_, words) in enumerate(p.finding, start=2):
            steps.append(stage(f"find_{i}", words, 3.0, [f"row_{i}"]))
        steps.append(
            stage(
                "result",
                "Put the values back in",
                2.5,
                ["result", "result_box"],
                emphasise=["result"],
            )
        )

        def standard(s):
            return [
                s[0],
                s[1],
                combine("solve", "Multiply up, then substitute and compare", 4.5, *s[2:-1]),
                s[-1],
            ]

        def concise(s):
            return [combine("form", s[1].description, 3.5, s[0], s[1]), *standard(s)[2:]]

        return by_level(level, steps, standard, concise)


def _factors(bottom: sp.Expr):
    """The denominator's factors [(factor, power)] if it is one of the syllabus types."""
    _, factors = sp.factor_list(sp.expand(bottom), X)
    linear = [(f, k) for f, k in factors if sp.degree(f, X) == 1]
    quadratic = [(f, k) for f, k in factors if sp.degree(f, X) == 2]
    if len(linear) + len(quadratic) != len(factors):
        return None
    powers = sorted(k for _, k in linear)
    if quadratic:
        ok = len(quadratic) == 1 and quadratic[0][1] == 1 and powers == [1]
    else:
        ok = powers in ([1, 1], [1, 1, 1], [1, 2])
    return factors if ok else None


class _Problem:
    def __init__(self, params: PartialFractionsParams):
        self.top = sp.nsimplify(parse_expression(params.numerator, {"x"}), rational=True)
        self.bottom = sp.nsimplify(parse_expression(params.denominator, {"x"}), rational=True)
        factors = _factors(self.bottom)
        constant = sp.cancel(sp.expand(self.bottom) / sp.prod([f**k for f, k in factors]))
        # the terms of the form: (numerator with unknowns, denominator)
        self.terms = []
        letters = iter(LETTERS)
        written = params.denominator.replace(" ", "")

        def position(fk):  # keep the factors in the order they were written
            found = written.find(sp.sstr(fk[0]).replace(" ", ""))
            return found if found >= 0 else len(written)

        ordered = sorted(factors, key=lambda fk: (sp.degree(fk[0], X), position(fk), fk[1]))
        for f, k in ordered:
            if sp.degree(f, X) == 2:
                b, c = next(letters), next(letters)
                self.terms.append((b * X + c, f))
            else:
                for power in range(1, k + 1):
                    self.terms.append((next(letters), f**power))
        self.top_scaled = self.top / constant
        self.unknowns = [s for t, _ in self.terms for s in t.free_symbols if s != X]
        self.unknowns = sorted(set(self.unknowns), key=str)
        common = sp.prod([f**k for f, k in factors])
        self.identity_rhs = sp.Add(
            *(numerator * sp.cancel(common / denominator) for numerator, denominator in self.terms)
        )
        self.solution = sp.solve(
            sp.Poly(sp.expand(self.identity_rhs - self.top_scaled), X).coeffs(), self.unknowns
        )
        self.result = sp.Add(
            *(
                numerator.subs(self.solution) / (constant * denominator)
                for numerator, denominator in self.terms
            )
        )
        self.constant = constant
        self.factors = ordered
        self.finding = self._finding()

    def bottom_latex(self) -> str:
        return sp.latex(sp.factor(self.bottom))

    def form_latex(self) -> str:
        pieces = []
        for numerator, denominator in self.terms:
            pieces.append(
                rf"\dfrac{{{sp.latex(numerator)}}}{{{_den_latex(denominator, self.constant)}}}"
            )
        return " + ".join(pieces)

    def form_words(self) -> str:
        kinds = []
        for f, k in self.factors:
            if sp.degree(f, X) == 2:
                kinds.append("a quadratic factor takes B x plus C on top")
            elif k == 2:
                kinds.append("a repeated factor takes two fractions, one over its square")
        extra = ("; " + "; ".join(kinds)) if kinds else ""
        return "Choose the form: one fraction for each linear factor" + extra

    def _finding(self) -> list[tuple[str, str]]:
        """Each line that finds a constant: substitute a root, or compare coefficients."""
        known: dict = {}
        out = []
        difference = sp.expand(self.identity_rhs - self.top_scaled)
        for f, _ in self.factors:
            if sp.degree(f, X) != 1:
                continue
            root = sp.solve(f, X)[0]
            equation = sp.Eq(self.top_scaled.subs(X, root), self.identity_rhs.subs(X, root))
            unknowns = [u for u in self.unknowns if equation.has(u) and u not in known]
            if len(unknowns) == 1:
                value = sp.solve(equation, unknowns[0])[0]
                known[unknowns[0]] = value
                out.append(
                    (
                        rf"x = {latex_value(root)}:\ {latex_value(equation.lhs)} = "
                        rf"{sp.latex(sp.expand(equation.rhs))},\ "
                        rf"{unknowns[0]} = {latex_value(value)}",
                        f"Put x equal to {_spoken(root)}, so that bracket is zero: only "
                        f"{unknowns[0]} is left",
                    )
                )
        degree = sp.degree(sp.expand(self.identity_rhs.subs(known)), X)
        for power in range(int(degree), -1, -1):
            if len(known) == len(self.unknowns):
                break
            coefficient = sp.Poly(difference.subs(known), X).coeff_monomial(X**power)
            unknowns = [u for u in self.unknowns if coefficient.has(u)]
            if len(unknowns) == 1:
                value = sp.solve(coefficient, unknowns[0])[0]
                known[unknowns[0]] = value
                term = (
                    f"x^{{{power}}}" if power > 1 else ("x" if power == 1 else r"\text{constants}")
                )
                out.append(
                    (
                        rf"\text{{Compare }}{term}:\ {sp.latex(sp.expand(coefficient))} = 0,\ "
                        rf"{unknowns[0]} = {latex_value(value)}",
                        "Compare the coefficients on both sides for the rest",
                    )
                )
        return out

    def rows(self) -> list[tuple[str, object]]:
        written = " + ".join(
            _times(numerator, sp.cancel(sp.prod([f**k for f, k in self.factors]) / denominator))
            for numerator, denominator in self.terms
        )
        rows = [(rf"{tidy_latex(self.top_scaled)} \equiv {written}", None)]
        rows += [(text, UNKNOWN_COLOUR) for text, _ in self.finding]
        return rows

    def result_latex(self) -> str:
        pieces = []
        for numerator, denominator in self.terms:
            value = sp.expand(numerator.subs(self.solution) / self.constant)
            if value == 0:
                continue
            # clear fractions in the numerator into the denominator: 11/3 over (x - 2) is
            # written 11 over 3(x - 2)
            top, scale = sp.fraction(sp.together(value))
            sign = "+"
            if (top.is_number and top < 0) or (not top.is_number and _leading_negative(top)):
                sign, top = "-", -top
            den = _den_latex(denominator, scale)
            body = rf"\dfrac{{{latex_value(top) if top.is_number else tidy_latex(top)}}}{{{den}}}"
            pieces.append((sign, body))
        text = ""
        for i, (sign, body) in enumerate(pieces):
            text += (("-" if sign == "-" else "") + body) if i == 0 else f" {sign} {body}"
        return text


def _leading_negative(expr) -> bool:
    return all(term.as_coeff_Mul()[0] < 0 for term in sp.Add.make_args(expr))


def _den_latex(denominator, constant) -> str:
    body = sp.latex(denominator)
    if constant != 1:
        body = rf"{latex_value(constant)}{body if denominator.is_Pow else rf'\left({body}\right)'}"
    return body


def _times(numerator, rest) -> str:
    rest_tex = sp.latex(sp.factor(rest))
    rest_tex = rest_tex if rest_tex.startswith(r"\left(") else rf"\left({rest_tex}\right)"
    top = sp.latex(numerator)
    top = rf"\left({top}\right)" if numerator.is_Add else top
    return f"{top}{rest_tex}"


def _spoken(value) -> str:
    return str(value).replace("/", " over ").replace("-", "minus ")


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
