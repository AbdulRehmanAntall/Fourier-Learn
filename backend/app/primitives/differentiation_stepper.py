"""DifferentiationStepper: a derivative worked line by line with the power, chain, product or
quotient rule (AM 14.3, 14.4; PRIMITIVES.md #54).

Power rule: the function is rewritten as powers of x (1/x as x⁻¹, √x as x^½) and each term
a·xⁿ becomes n·a·xⁿ⁻¹. Chain rule: y = f(u) with u = g(x), then dy/dx = dy/du × du/dx. Product
rule: dy/dx = u dv/dx + v du/dx. Quotient rule: dy/dx = (v du/dx - u dv/dx)/v². The gradient can
then be evaluated at a point. Every line is computed by SymPy, so the working cannot go wrong.
"""

from typing import Annotated, Literal

import sympy as sp
from manim import DOWN, LEFT, MathTex, SurroundingRectangle, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import inline
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    exact,
    format_value,
    latex_value,
    parse_expression,
    tidy_latex,
    written_latex,
)

X, U = sp.Symbol("x", real=True), sp.Symbol("u", real=True)
OMEGA = sp.Symbol("omega", real=True)  # stands for the inside of a chain while printing
Text = Annotated[str, Field(min_length=1, max_length=100)]
DYDX = r"\frac{dy}{dx}"


class DifferentiationStepperParams(PrimitiveParams):
    rule: Literal["power", "chain", "product", "quotient"]
    expression: Text | None = Field(
        default=None, description='Power rule: a sum of terms a*x**n, e.g. "3*x**4 - 2/x"'
    )
    inner: Text | None = Field(default=None, description='Chain rule: u in terms of x, "3*x + 1"')
    outer: Text | None = Field(default=None, description='Chain rule: y in terms of u, "u**5"')
    u: Text | None = Field(default=None, description="Product or quotient rule: u(x)")
    v: Text | None = Field(default=None, description="Product or quotient rule: v(x)")
    at_x: Annotated[float, Field(ge=-100, le=100)] | None = Field(
        default=None, description="Optionally evaluate the gradient at this x"
    )


class DifferentiationStepper(StagedPrimitive[DifferentiationStepperParams]):
    primitive_id = "DifferentiationStepper"
    version = "1"
    topic = "Introductory calculus"
    params_model = DifferentiationStepperParams
    layout = LayoutContract(region=style.WORKING_REGION, allowed_overlaps=[("result_box", "*")])

    def default_params(self) -> DifferentiationStepperParams:
        return DifferentiationStepperParams(rule="power", expression="3*x**4 - 2*x**2 + 5*x - 7")

    def validate(self, params: DifferentiationStepperParams) -> list[PredicateFailure]:
        needed = {
            "power": ["expression"],
            "chain": ["inner", "outer"],
            "product": ["u", "v"],
            "quotient": ["u", "v"],
        }[params.rule]
        missing = [n for n in needed if getattr(params, n) is None]
        if missing:
            message = f"the {params.rule} rule needs {' and '.join(missing)}"
            return [_failure("consistency", "rule_inputs", message, *missing)]
        try:
            work = _Working(params)
        except _Bad as bad:
            return [bad.failure]
        if params.at_x is not None:
            value = work.derivative.subs(X, exact(params.at_x))
            if not (value.is_real and value.is_finite):
                message = f"the gradient is not defined at x = {format_value(exact(params.at_x))}"
                return [_failure("domain", "gradient_defined", message, "at_x")]
        return []

    def computed_values(self, params: DifferentiationStepperParams) -> dict[str, str]:
        work = _Working(params)
        values = {"derivative": str(work.derivative)}
        if params.at_x is not None:
            values["gradient_at_x"] = format_value(work.derivative.subs(X, exact(params.at_x)))
        return values

    def build(self, params: DifferentiationStepperParams, level):
        work = _Working(params)
        box = style.region_box(self.layout.region).shrink(style.PADDING)
        lines = []
        for _, tex in work.lines:
            line = MathTex(inline(tex), font_size=style.FONT_SIZE)
            if line.width > box.width:  # each line keeps the largest size that fits
                line.scale_to_fit_width(box.width)
            lines.append(line)
        group = VGroup(*lines).arrange(DOWN, aligned_edge=LEFT, buff=0.38)
        style.fit_inside(group, box)
        parts = {name: line for (name, _), line in zip(work.lines, lines, strict=True)}
        parts["result_box"] = SurroundingRectangle(
            lines[-1], color=style.HIGHLIGHT_COLOUR, buff=0.1
        )
        return parts

    def stages(self, params: DifferentiationStepperParams, level) -> list[Stage]:
        work = _Working(params)
        steps = [
            stage(name, work.words[name], 2.5, [name], emphasise=[name] if i else [])
            for i, (name, _) in enumerate(work.lines)
        ]
        steps[-1] = combine(
            steps[-1].name,
            steps[-1].description,
            2.5,
            steps[-1],
            stage("box", "", 0.1, ["result_box"]),
        )

        def standard(s):
            if len(s) <= 3:
                return s
            return [
                combine("setup", "Write the function and what the rule needs", 3.0, *s[:2]),
                *s[2:-2],
                combine("result", "Put the pieces together and simplify", 3.0, *s[-2:]),
            ]

        def concise(s):
            return [
                combine("setup", "Write the function", 2.5, s[0]),
                combine("result", f"Apply the {params.rule} rule", 3.5, *s[1:]),
            ]

        return by_level(level, steps, standard, concise)


class _Bad(Exception):
    def __init__(self, failure: PredicateFailure):
        self.failure = failure


def _parse(text: str, variable: str, parameter: str) -> sp.Expr:
    try:
        expr = parse_expression(text, {variable})
    except ExpressionError as error:
        raise _Bad(_failure("parsing", "expression_parses", str(error), parameter)) from None
    if not expr.has(sp.Symbol(variable, real=True)):
        raise _Bad(
            _failure(
                "consistency",
                "depends_on_variable",
                f"{parameter} must contain {variable}",
                parameter,
            )
        )
    return sp.nsimplify(expr, rational=True)


class _Working:
    """The lines of the working as (name, LaTeX), what each step says, and the derivative."""

    def __init__(self, params: DifferentiationStepperParams):
        self.lines: list[tuple[str, str]] = []
        self.words: dict[str, str] = {}
        getattr(self, f"_{params.rule}")(params)
        if params.at_x is not None:
            x = exact(params.at_x)
            value = self.derivative.subs(X, x)
            if not (value.is_real and value.is_finite):
                return  # validate() rejects it: the gradient is not defined there
            self._line(
                "at_x",
                rf"x = {latex_value(x)}:\ {DYDX} = {latex_value(value)}",
                f"Substitute x = {format_value(x)} for the gradient there",
            )

    def _line(self, name: str, tex: str, words: str) -> None:
        self.lines.append((name, tex))
        self.words[name] = words

    def _power(self, params):
        f = _parse(params.expression, "x", "expression")
        terms = sp.Add.make_args(sp.expand(f))
        powers = []
        for term in terms:
            coefficient, rest = term.as_coeff_Mul()
            if rest == 1:
                powers.append((coefficient, sp.Integer(0)))
                continue
            base, exponent = rest.as_base_exp()
            if base != X or exponent.has(X) or not exponent.is_Rational:
                message = (
                    f"{sp.sstr(term)} is not a power of x: use the chain, product or quotient rule"
                )
                raise _Bad(_failure("consistency", "power_terms", message, "expression"))
            powers.append((coefficient, exponent))
        powers.sort(key=lambda t: -t[1])
        self.derivative = sp.diff(f, X)
        self._line("function", f"y = {written_latex(params.expression)}", "Write the function")
        if any(not (n.is_integer and n >= 0) for _, n in powers):
            self._line(
                "powers",
                f"y = {_join([_power_tex(a, n) for a, n in powers])}",
                "Write every term as a power of x",
            )
        derived = [(a, n) for a, n in powers if n != 0]
        working = (
            _join(
                [
                    rf"{_number(n)} \times {_coefficient(a, n - 1)}{_x_power(n - 1)}"
                    if n != 1
                    else latex_value(a)
                    for a, n in derived
                ]
            )
            or "0"
        )
        self._line(
            "rule",
            f"{DYDX} = {working}",
            "Multiply each term by its power, then take one off the power",
        )
        tidy = _join([_power_tex(a * n, n - 1) for a, n in derived]) or "0"
        self._line("result", f"{DYDX} = {tidy}", "Simplify")

    def _chain(self, params):
        inner = _parse(params.inner, "x", "inner")
        outer = _parse(params.outer, "u", "outer")
        if outer == U:
            raise _Bad(_failure("consistency", "outer_not_u", "y = u needs no chain rule", "outer"))
        dy_du, du_dx = sp.diff(outer, U), sp.diff(inner, X)
        self.derivative = sp.simplify(dy_du.subs(U, inner) * du_dx)
        composed = _with_inside(sp.latex(outer.subs(U, OMEGA)), inner)
        self._line("function", f"y = {composed}", "Write the function")
        self._line(
            "split",
            rf"u = {tidy_latex(inner)},\ y = {tidy_latex(outer)}",
            "Let u be the inside, so y is a simple function of u",
        )
        self._line(
            "pieces",
            rf"\frac{{du}}{{dx}} = {tidy_latex(du_dx)},\ "
            rf"\frac{{dy}}{{du}} = {tidy_latex(dy_du)}",
            "Differentiate each one",
        )
        self._line(
            "rule",
            rf"{DYDX} = \frac{{dy}}{{du}} \times \frac{{du}}{{dx}}",
            "Multiply: dy by dx is dy by du times du by dx",
        )
        self._line(
            "substitute",
            rf"= \left({tidy_latex(dy_du)}\right) \times {_bracket(du_dx)}",
            "Put in the two derivatives",
        )
        self._line(
            "result", f"{DYDX} = {_tidy(self.derivative, inner)}", "Put u back in terms of x"
        )

    def _product(self, params):
        u, v = _parse(params.u, "x", "u"), _parse(params.v, "x", "v")
        du, dv = sp.diff(u, X), sp.diff(v, X)
        self.derivative = sp.factor(sp.simplify(u * dv + v * du))
        self._line("function", rf"y = {_bracket(u)}{_bracket(v)}", "Write the function")
        self._line(
            "split",
            rf"u = {tidy_latex(u)},\ v = {tidy_latex(v)}",
            "It is a product: call the two factors u and v",
        )
        self._line(
            "pieces",
            rf"\frac{{du}}{{dx}} = {tidy_latex(du)},\ "
            rf"\frac{{dv}}{{dx}} = {tidy_latex(dv)}",
            "Differentiate each factor",
        )
        self._line(
            "rule",
            rf"{DYDX} = u\frac{{dv}}{{dx}} + v\frac{{du}}{{dx}}",
            "Product rule: u times dv by dx, plus v times du by dx",
        )
        self._line(
            "substitute",
            rf"= {_bracket(u)} \times {_bracket(dv)} + {_bracket(v)} \times {_bracket(du)}",
            "Put in u, v and their derivatives",
        )
        self._line("result", f"{DYDX} = {sp.latex(self.derivative)}", "Simplify")

    def _quotient(self, params):
        u, v = _parse(params.u, "x", "u"), _parse(params.v, "x", "v")
        du, dv = sp.diff(u, X), sp.diff(v, X)
        self.derivative = sp.factor(sp.simplify((v * du - u * dv) / v**2))
        self._line(
            "function", rf"y = \frac{{{tidy_latex(u)}}}{{{tidy_latex(v)}}}", "Write the function"
        )
        self._line(
            "split",
            rf"u = {tidy_latex(u)},\ v = {tidy_latex(v)}",
            "It is a quotient: u on top, v underneath",
        )
        self._line(
            "pieces",
            rf"\frac{{du}}{{dx}} = {tidy_latex(du)},\ "
            rf"\frac{{dv}}{{dx}} = {tidy_latex(dv)}",
            "Differentiate each one",
        )
        self._line(
            "rule",
            rf"{DYDX} = \frac{{v\frac{{du}}{{dx}} - u\frac{{dv}}{{dx}}}}{{v^2}}",
            "Quotient rule: v du by dx minus u dv by dx, all over v squared",
        )
        self._line(
            "substitute",
            rf"= \frac{{{_bracket(v)} \times {_bracket(du)} - {_bracket(u)} \times "
            rf"{_bracket(dv)}}}{{\left({tidy_latex(v)}\right)^2}}",
            "Put in u, v and their derivatives",
        )
        self._line("result", f"{DYDX} = {sp.latex(self.derivative)}", "Simplify")


def _power_tex(a: sp.Expr, n: sp.Expr) -> str:
    """a·xⁿ as LaTeX: 3x^{4}, -x, 5, 2x^{-1}, x^{\\frac{1}{2}}."""
    if n == 0:
        return latex_value(a)
    power = "x" if n == 1 else f"x^{{{sp.latex(n)}}}"
    if a == 1:
        return power
    if a == -1:
        return f"-{power}"
    return f"{latex_value(a)}{power}"


def _join(terms: list[str]) -> str:
    text = ""
    for i, term in enumerate(terms):
        if i == 0:
            text = term
        elif term.startswith("-"):
            text += f" - {term[1:]}"
        else:
            text += f" + {term}"
    return text


def _number(value: sp.Expr) -> str:
    tex = latex_value(value)
    return rf"\left({tex}\right)" if value < 0 else tex


def _coefficient(a: sp.Expr, power: sp.Expr) -> str:
    """The coefficient in front of a power of x: none for 1, unless nothing follows it."""
    if a == 1 and power != 0:
        return ""
    return _number(a)


def _x_power(n: sp.Expr) -> str:
    return "" if n == 0 else ("x" if n == 1 else f"x^{{{sp.latex(n)}}}")


def _bracket(value: sp.Expr) -> str:
    """A factor in a product: in brackets if it is a sum or negative, as written by hand."""
    tex = tidy_latex(value)
    if isinstance(value, sp.Add) or tex.startswith("-"):
        return rf"\left({tex}\right)"
    return tex


def _with_inside(tex: str, inner: sp.Expr) -> str:
    """Put the inside of a chain back where OMEGA stands, in brackets except under a root."""
    inside = tidy_latex(inner)
    tex = tex.replace(r"\sqrt{\omega}", rf"\sqrt{{{inside}}}")
    return tex.replace(r"\omega", rf"\left({inside}\right)")


def _tidy(derivative: sp.Expr, inner: sp.Expr) -> str:
    """The chain rule result with the inside kept together: 15(3x + 1)^4, not expanded."""
    in_terms = sp.simplify(derivative.subs(inner, OMEGA))
    if in_terms.has(X):
        return sp.latex(sp.factor(derivative))
    return _with_inside(sp.latex(in_terms), inner)


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
