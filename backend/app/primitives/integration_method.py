"""IntegrationMethod: an integral worked by parts, by a given substitution, or recognised as
k f'(x)/f(x), definite or indefinite, and checked by differentiating the answer (9709 3.5).

By parts: ∫u (dv/dx) dx = uv − ∫v (du/dx) dx, choosing u to be the factor that gets simpler
when differentiated. By substitution: with u = g(x), dx = du ÷ (du/dx), the integrand is
rewritten in u alone, integrated, and put back in terms of x (or, for a definite integral, the
limits are changed to values of u). A quotient whose top is k times the derivative of its
bottom integrates to k ln|f(x)|. SymPy does each step, and differentiating the answer must give
the integrand back, so a wrong answer cannot be shown.
"""

from typing import Literal

import sympy as sp
from manim import SurroundingRectangle
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import make_table, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    format_sf,
    is_elementary_integral,
    latex_with_pi,
    parse_expression,
    written_latex,
)

X = sp.Symbol("x", real=True)
U = sp.Symbol("u", real=True)


class IntegrationMethodParams(PrimitiveParams):
    method: Literal["parts", "substitution", "log_form"]
    integrand: str = Field(min_length=1, max_length=100, description='e.g. "x*sin(2*x)"')
    u: str | None = Field(
        default=None,
        max_length=60,
        description="Parts: the factor to differentiate (u). Substitution: u in terms of x",
    )
    lower: str | None = Field(
        default=None, max_length=12, description='A limit, e.g. "0" or "pi/2"'
    )
    upper: str | None = Field(default=None, max_length=12)


class IntegrationMethod(StagedPrimitive[IntegrationMethodParams]):
    primitive_id = "IntegrationMethod"
    version = "1"
    topic = "Integration"
    params_model = IntegrationMethodParams
    layout = LayoutContract(region=FULL_FRAME, allowed_overlaps=[("*_box", "*"), ("card", "*")])

    def default_params(self) -> IntegrationMethodParams:
        return IntegrationMethodParams(method="parts", integrand="x*sin(2*x)", u="x")

    def validate(self, params: IntegrationMethodParams) -> list[PredicateFailure]:
        try:
            parse_expression(params.integrand, {"x"})
            if params.u is not None:
                parse_expression(params.u, {"x"})
            for limit in (params.lower, params.upper):
                if limit is not None:
                    _limit(limit)
        except (ExpressionError, ValueError) as error:
            return [_failure("parsing", "expression_parses", str(error), "integrand", "u")]
        if (params.lower is None) != (params.upper is None):
            return [_failure("consistency", "both_limits", "give both limits or neither")]
        if params.lower is not None and _limit(params.lower) >= _limit(params.upper):
            return [_failure("consistency", "limits_ordered", "lower must be below upper")]
        if params.method != "log_form" and params.u is None:
            return [_failure("consistency", "u_given", "this method needs u", "u")]
        try:
            work = _Work(params)
        except _Unsuitable as problem:
            return [_failure("consistency", "method_fits", str(problem), "method", "u")]
        # ln|f| differentiates like ln f, where f is not 0
        plain = work.result.replace(sp.Abs, lambda a: a)
        if sp.simplify(sp.diff(plain, X) - work.f) != 0:
            message = "the method does not give back the integrand when checked"
            return [_failure("consistency", "answer_checks", message, "integrand")]
        if work.definite is not None and not work.definite.is_finite:
            return [_failure("domain", "real_and_finite", "the integral is not finite", "lower")]
        return []

    def computed_values(self, params: IntegrationMethodParams) -> dict[str, str]:
        work = _Work(params)
        values = {"result": str(work.result)}
        if work.definite is not None:
            values["value"] = str(work.definite)
            values["value_3sf"] = format_sf(work.definite)
        return values

    def build(self, params: IntegrationMethodParams, level):
        work = _Work(params)
        left = style.region_box(style.GRAPH_REGION).shrink(style.PADDING)
        title = style.Box(left.left, left.right, left.top - 1.2, left.top)
        card_box = style.Box(left.left + 0.4, left.right - 0.4, left.top - 4.6, left.top - 1.6)
        parts = {"title": text_line(work.title_latex(), title, size=48)}
        table = make_table(work.card(), card_box, font_size=36, pad=0.25)
        parts["card"] = table.group
        answer_box = style.Box(left.left, left.right, left.bottom + 0.3, left.bottom + 1.6)
        parts["answer"] = text_line(
            work.answer_latex(), answer_box, colour=style.HIGHLIGHT_COLOUR, size=44
        )
        parts["answer_box"] = SurroundingRectangle(
            parts["answer"], color=style.HIGHLIGHT_COLOUR, buff=0.12
        )
        rows = work.rows()
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: IntegrationMethodParams, level) -> list[Stage]:
        work = _Work(params)
        n = len(work.rows())
        card_words = {
            "parts": "Choose u, the factor that gets simpler when differentiated; the rest is "
            "d v by d x",
            "substitution": "Write u, find d u by d x, and replace d x",
            "log_form": "The top is a multiple of the derivative of the bottom",
        }[params.method]
        steps = [
            stage("integral", "The integral", 2.0, ["title"]),
            stage("card", card_words, 3.5, ["card"]),
            stage("method", _method_words(params.method), 3.5, ["row_1", "row_2"]),
            stage("integrate", "Integrate", 3.0, [f"row_{i}" for i in range(3, n)]),
            stage(
                "check",
                "Check: differentiating the answer gives the integrand back",
                3.0,
                [f"row_{n}", "answer", "answer_box"],
                emphasise=["answer"],
            ),
        ]

        def standard(s):
            return [combine("card", s[1].description, 3.5, s[0], s[1]), *s[2:]]

        def concise(s):
            return [
                combine("card", s[1].description, 3.5, s[0], s[1]),
                combine("integrate", "Apply the method and integrate", 4.5, s[2], s[3]),
                s[4],
            ]

        return by_level(level, steps, standard, concise)


class _Unsuitable(ValueError):
    pass


def _limit(text: str) -> sp.Expr:
    value = sp.nsimplify(parse_expression(text, set()), [sp.pi], rational=True)
    if not (value.is_real and value.is_finite):
        raise ValueError(f"{text!r} is not a number")
    return value


def _tex(expr) -> str:
    return sp.latex(expr, ln_notation=True, inv_trig_style="power")


class _Work:
    def __init__(self, params: IntegrationMethodParams):
        self.params = params
        self.f = sp.nsimplify(parse_expression(params.integrand, {"x"}), rational=True)
        self.a = _limit(params.lower) if params.lower is not None else None
        self.b = _limit(params.upper) if params.upper is not None else None
        getattr(self, f"_{params.method}")()
        self.definite = None
        if self.a is not None:
            self.definite = sp.nsimplify(
                sp.simplify(self.result.subs(X, self.b) - self.result.subs(X, self.a))
            )

    def _parts(self):
        self.u = sp.nsimplify(parse_expression(self.params.u, {"x"}), rational=True)
        self.dv = sp.simplify(self.f / self.u)
        if self.dv.has(sp.zoo):
            raise _Unsuitable("u must be a factor of the integrand")
        self.v = sp.integrate(self.dv, X)
        self.du = sp.diff(self.u, X)
        if not is_elementary_integral(self.v):
            raise _Unsuitable("dv/dx cannot be integrated: choose the other factor as u")
        self.rest = sp.simplify(self.v * self.du)
        rest_integral = sp.integrate(self.rest, X)
        if not is_elementary_integral(rest_integral):
            raise _Unsuitable("the second integral cannot be done: choose the other factor as u")
        self.rest_integral = rest_integral
        self.result = sp.simplify(self.u * self.v - rest_integral)

    def _substitution(self):
        self.g = sp.nsimplify(parse_expression(self.params.u, {"x"}), rational=True)
        self.dg = sp.diff(self.g, X)
        if self.dg == 0:
            raise _Unsuitable("u must depend on x")
        in_u = None
        for inverse in sp.solve(sp.Eq(U, self.g), X):
            candidate = sp.simplify((self.f / self.dg).subs(X, inverse))
            if not candidate.has(X):
                in_u = candidate
                break
        if in_u is None:
            raise _Unsuitable("the integrand cannot be written in terms of u alone")
        self.in_u = sp.simplify(in_u)
        self.u_integral = sp.integrate(self.in_u, U)
        if not is_elementary_integral(self.u_integral):
            raise _Unsuitable("the integral in u cannot be done")
        self.result = sp.simplify(self.u_integral.subs(U, self.g))

    def _log_form(self):
        written = self.f.replace(sp.tan, lambda a: sp.sin(a) / sp.cos(a)).replace(
            sp.cot, lambda a: sp.cos(a) / sp.sin(a)
        )
        top, bottom = sp.fraction(sp.together(written))
        if not bottom.has(X):
            raise _Unsuitable("the integrand must be a fraction with x in its denominator")
        k = sp.simplify(top / sp.diff(bottom, X))
        if k.has(X):
            raise _Unsuitable("the top is not a multiple of the derivative of the bottom")
        self.bottom, self.k = bottom, k
        self.result = k * sp.log(sp.Abs(bottom))

    def title_latex(self) -> str:
        limits = (
            rf"_{{{latex_with_pi(self.a, approx=False)}}}^{{{latex_with_pi(self.b, approx=False)}}}"
            if self.a is not None
            else ""
        )
        return rf"\int{limits} {written_latex(self.params.integrand)}\,dx"

    def card(self) -> list[list[str]]:
        m = self.params.method
        if m == "parts":
            return [
                [rf"u = {_tex(self.u)}", rf"\frac{{dv}}{{dx}} = {_tex(self.dv)}"],
                [rf"\frac{{du}}{{dx}} = {_tex(self.du)}", rf"v = {_tex(self.v)}"],
            ]
        if m == "substitution":
            rows = [
                [rf"u = {_tex(self.g)}"],
                [rf"\frac{{du}}{{dx}} = {_tex(self.dg)}"],
            ]
            if self.a is not None:
                ua, ub = (sp.simplify(self.g.subs(X, v)) for v in (self.a, self.b))
                rows.append([rf"x = {_lim(self.a)} \to u = {_lim(ua)}"])
                rows.append([rf"x = {_lim(self.b)} \to u = {_lim(ub)}"])
            return rows
        return [
            [rf"f(x) = {_tex(self.bottom)}"],
            [rf"f'(x) = {_tex(sp.diff(self.bottom, X))}"],
            [rf"\text{{top}} = {_times(self.k)}f'(x)"],
        ]

    def rows(self) -> list[tuple[str, object]]:
        m = self.params.method
        c = "" if self.a is not None else " + c"
        if m == "parts":
            rows = [
                (r"\int u\frac{dv}{dx}dx = uv - \int v\frac{du}{dx}dx", None),
                (rf"= {_tex(self.u * self.v)} {_minus_integral(self.rest)}", None),
                (rf"= {_tex(sp.expand(self.u * self.v - self.rest_integral))}{c}", None),
            ]
        elif m == "substitution":
            rows = [
                (rf"dx = \frac{{du}}{{{_tex(self.dg)}}}", None),
                (rf"\int {_tex(self.in_u)}\,du", None),
                (rf"= {_tex(self.u_integral)}{c}", None),
                (rf"= {_tex(self.result)}{c}", None),
            ]
        else:
            rows = [
                (r"\int \frac{f'(x)}{f(x)}dx = \ln|f(x)| + c", None),
                (rf"\int {_tex(self.f)}\,dx = {_times(self.k)}\int \frac{{f'(x)}}{{f(x)}}dx", None),
                (rf"= {_tex(self.result)}{c}", None),
            ]
        if self.definite is not None:
            rows.append(
                (
                    rf"\left[\,\dots\right]_{{{_lim(self.a)}}}^{{{_lim(self.b)}}} = "
                    + _value(self.definite),
                    style.HIGHLIGHT_COLOUR,
                )
            )
        rows.append(
            (
                r"\text{Check: }\frac{d}{dx}\left(\text{answer}\right) = "
                r"\text{integrand}\ \checkmark",
                style.RISE_COLOUR,
            )
        )
        return rows

    def answer_latex(self) -> str:
        if self.definite is not None:
            return rf"= {_value(self.definite)}"
        return rf"= {_tex(self.result)} + c"


def _times(k) -> str:
    """k in front of a product: nothing for 1, a minus sign for -1."""
    return {1: "", -1: "-"}.get(k, _tex(k) + r"\,")


def _minus_integral(rest) -> str:
    """- ∫ rest dx, written + ∫ (-rest) dx when rest is negative, so no double minus."""
    if sp.Add.make_args(rest)[0].as_coeff_Mul()[0] < 0 and len(sp.Add.make_args(rest)) == 1:
        return rf"+ \int {_tex(-rest)}\,dx"
    return rf"- \int {_tex(rest)}\,dx"


def _lim(value) -> str:
    return latex_with_pi(value, approx=False)


def _value(value) -> str:
    value = sp.nsimplify(value)
    if isinstance(value, sp.Rational):
        return sp.latex(value)
    value = sp.expand_log(value, force=True) if value.has(sp.log) else value
    text = _tex(value)
    return text if len(text) > 40 else rf"{text} \approx {format_sf(value)}"


def _method_words(method: str) -> str:
    return {
        "parts": "Integration by parts: u v, take away the integral of v times d u by d x",
        "substitution": "Rewrite the whole integral in terms of u",
        "log_form": "So it is k times the natural log of the bottom",
    }[method]


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
