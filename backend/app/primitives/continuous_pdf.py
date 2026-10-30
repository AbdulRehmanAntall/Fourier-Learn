"""ContinuousPDF: a continuous random variable's probability density function drawn as a curve,
with the constant k found from the total area being 1, a probability shaded as the area between
two values, and the mean, variance and median found by integration (9709 6.3).

f(x) ≥ 0 on its interval [a, b] (b may be infinite) and is 0 elsewhere, and ∫ₐᵇ f(x) dx = 1;
an unknown constant k in f is fixed by that equation. P(c < X < d) = ∫꜀ᵈ f(x) dx, so a single
value has probability 0 and < and ≤ agree. E(X) = ∫ x f(x) dx and
Var(X) = ∫ x² f(x) dx − E(X)². The median m has ∫ₐᵐ f(x) dx = ½. Everything is integrated
exactly; values are exact when simple, otherwise to 3 significant figures.
"""

from typing import Annotated

import numpy as np
import sympy as sp
from manim import DashedLine, Polygon, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import label, make_plot, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    format_sf,
    latex_value,
    latex_with_pi,
    parse_expression,
    tidy_latex,
)

Limit = Annotated[
    str, Field(min_length=1, max_length=12, description='A number, or "inf" for no upper end')
]
X, K = sp.Symbol("x", real=True), sp.Symbol("k", real=True)  # as parse_expression makes them


class ContinuousPDFParams(PrimitiveParams):
    pdf: str = Field(
        max_length=60,
        description='f(x) on its interval, in x; may hold a constant k, e.g. "k*x*(4 - x)"',
    )
    lower: Limit = Field(description="a: the left end of the interval")
    upper: Limit = Field(description='b: the right end, or "inf"')
    low: Limit | None = Field(default=None, description="The event P(low < X < high)")
    high: Limit | None = Field(default=None, description="Leave out for no upper end")
    median: bool = Field(default=True, description="Find the median")


class ContinuousPDF(StagedPrimitive[ContinuousPDFParams]):
    primitive_id = "ContinuousPDF"
    version = "1"
    topic = "Continuous random variables"
    params_model = ContinuousPDFParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[("axes", "*"), ("curve", "*"), ("area", "*"), ("marks", "*")],
    )

    def default_params(self) -> ContinuousPDFParams:
        return ContinuousPDFParams(pdf="k*x*(4 - x)", lower="0", upper="4", low="1", high="3")

    def validate(self, params: ContinuousPDFParams) -> list[PredicateFailure]:
        try:
            f = parse_expression(params.pdf, {"x", "k"})
            a, b = _limit(params.lower), _limit(params.upper, infinite=True)
            ends = [_limit(v, infinite=True) for v in (params.low, params.high) if v is not None]
        except (ExpressionError, ValueError) as error:
            return [_failure("parsing", "parses", str(error), "pdf", "lower", "upper")]
        if b == sp.oo and params.upper != "inf":
            return [_failure("consistency", "limits_finite", "write inf for no upper end")]
        if a >= b:
            return [
                _failure(
                    "consistency", "limits_ordered", "lower must be below upper", "lower", "upper"
                )
            ]
        if params.low is not None and params.high is not None and ends[0] >= ends[1]:
            return [
                _failure("consistency", "event_ordered", "low must be below high", "low", "high")
            ]
        f = sp.nsimplify(f, rational=True)
        try:
            total = sp.integrate(f, (X, a, b))
        except (ValueError, TypeError, NotImplementedError):
            total = sp.nan
        if not total.is_finite:
            message = "the area under f must be finite"
            return [_failure("consistency", "area_finite", message, "pdf")]
        if K in f.free_symbols:
            solutions = [s for s in sp.solve(sp.Eq(total, 1), K) if s.is_real and s > 0]
            if len(solutions) != 1:
                message = "no single positive k makes the area 1"
                return [_failure("consistency", "k_found", message, "pdf")]
            f = f.subs(K, solutions[0])
        elif sp.simplify(total - 1) != 0:
            message = f"the area under f is {total}, not 1; put a constant k in f to scale it"
            return [_failure("consistency", "area_one", message, "pdf")]
        for power in (1, 2):
            moment = sp.integrate(X**power * f, (X, a, b))
            if not moment.is_finite:
                message = "the mean and variance must be finite"
                return [_failure("consistency", "moments_finite", message, "pdf")]
        top = float(b) if b != sp.oo else float(a) + 50
        for x in np.linspace(float(a), top, 41):
            value = complex(f.subs(X, x).evalf())
            if abs(value.imag) > 1e-9 or value.real < -1e-9:
                message = "f(x) must be real and not negative on its interval"
                return [_failure("consistency", "density_non_negative", message, "pdf")]
        return []

    def computed_values(self, params: ContinuousPDFParams) -> dict[str, str]:
        d = _Density(params)
        values = {"mean": str(d.mean), "variance": str(d.variance)}
        if d.k is not None:
            values["k"] = str(d.k)
        if d.probability is not None:
            values["probability"] = str(d.probability)
        if d.median is not None:
            values["median"] = format_sf(d.median, 4)
        return values

    def build(self, params: ContinuousPDFParams, level):
        d = _Density(params)
        a = float(d.a)
        b = float(d.b) if d.b != sp.oo else d.quantile(0.99)
        margin = (b - a) * 0.15
        left = a - margin if a < 0 or a - margin > 0 else 0.0
        density = sp.lambdify(X, d.f, "numpy")
        xs = np.linspace(a, b, 160)
        ys = np.array([float(density(x)) for x in xs])
        top = float(max(ys)) * 1.15
        plot = make_plot(
            style.GRAPH_REGION, [left, b + margin], [0, top], y_label="f(x)", y_ticks=5
        )
        drawn = [plot.point(left, 0), plot.point(a, 0)]
        drawn += [plot.point(x, y) for x, y in zip(xs, ys, strict=True)]
        if d.b != sp.oo:
            drawn += [plot.point(b, 0), plot.point(b + margin, 0)]
        from manim import VMobject

        curve = VMobject(color=style.CURVE_COLOUR, stroke_width=4).set_points_as_corners(drawn)
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "title": text_line(d.title_latex(), plot.upper),
            "curve": curve,
        }
        area = VGroup()
        if d.event is not None:
            lo, hi = d.event
            lo = max(float(lo), a)
            hi = min(float(hi), b) if hi != sp.oo else b
            pts = np.linspace(lo, hi, 80)
            outline = [plot.point(lo, 0)] + [plot.point(x, float(density(x))) for x in pts]
            outline.append(plot.point(hi, 0))
            area.add(
                Polygon(*outline, stroke_width=0, fill_color=style.AREA_COLOUR, fill_opacity=0.55)
            )
        parts["area"] = area
        marks = VGroup()
        mean = float(d.mean)
        marked = [("E(X)", mean, style.RUN_COLOUR, 1)]
        if d.median is not None:
            if abs(d.median - mean) < 1e-6 * max(1, abs(mean)):
                marked = [("m = E(X)", mean, style.HIGHLIGHT_COLOUR, 1)]
            else:
                # the smaller value's label sits to the left of its line, the other to the right
                side = 1 if d.median > mean else -1
                marked = [
                    ("E(X)", mean, style.RUN_COLOUR, -side),
                    ("m", d.median, style.HIGHLIGHT_COLOUR, side),
                ]
        for name, value, colour, side in marked:
            if not left <= value <= b + margin:
                continue
            height = float(density(value)) if a <= value <= b else 0
            tip = plot.point(value, max(height, top * 0.2))
            marks.add(DashedLine(plot.point(value, 0), tip, color=colour, stroke_width=2))
            marks.add(
                label(name, colour=colour, size=24).next_to(tip, [0.6 * side, 1, 0], buff=0.06)
            )
        parts["marks"] = marks
        parts["answer"] = text_line(d.answer_latex(), plot.lower, colour=style.HIGHLIGHT_COLOUR)
        rows = d.rows()
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: ContinuousPDFParams, level) -> list[Stage]:
        d = _Density(params)
        groups = d.row_groups()
        names = iter(range(1, 100))
        rows = {key: [f"row_{next(names)}" for _ in range(count)] for key, count in groups}
        steps = [
            stage(
                "density",
                "The density curve: the total area under it is 1"
                + (", which fixes k" if d.k is not None else ""),
                3.5,
                ["axes", "x_label", "y_label", "title", "curve", *rows["k"]],
            )
        ]
        if "probability" in rows:
            steps.append(
                stage(
                    "probability",
                    "A probability is the area between the two values",
                    3.5,
                    ["area", *rows["probability"]],
                )
            )
        steps.append(
            stage(
                "mean",
                "The mean is the integral of x times f; the variance subtracts its square",
                4.0,
                rows["mean"],
            )
        )
        if "median" in rows:
            steps.append(stage("median", "The median cuts the area in half", 3.5, rows["median"]))
        steps.append(
            stage(
                "marks", "Mark the mean and median", 2.5, ["marks", "answer"], emphasise=["answer"]
            )
        )

        def standard(s):
            return list(s)

        def concise(s):
            return [s[0], combine("results", "Integrate for each result", 5.0, *s[1:])]

        return by_level(level, steps, standard, concise)


class _Density:
    def __init__(self, params: ContinuousPDFParams):
        self.params = params
        self.written = sp.nsimplify(parse_expression(params.pdf, {"x", "k"}), rational=True)
        self.a = _limit(params.lower)
        self.b = _limit(params.upper, infinite=True)
        self.k = None
        f = self.written
        if K in f.free_symbols:
            self.k_total = sp.simplify(sp.integrate(f, (X, self.a, self.b)))
            self.k = [s for s in sp.solve(sp.Eq(self.k_total, 1), K) if s.is_real and s > 0][0]
            f = f.subs(K, self.k)
        self.f = sp.simplify(f)
        self.mean = sp.simplify(sp.integrate(X * self.f, (X, self.a, self.b)))
        self.ex2 = sp.simplify(sp.integrate(X**2 * self.f, (X, self.a, self.b)))
        self.variance = sp.simplify(self.ex2 - self.mean**2)
        self.event = None
        self.probability = None
        if params.low is not None or params.high is not None:
            lo = _limit(params.low, infinite=True) if params.low is not None else self.a
            hi = _limit(params.high, infinite=True) if params.high is not None else self.b
            lo, hi = sp.Max(lo, self.a), sp.Min(hi, self.b)
            self.event = (lo, hi)
            self.probability = sp.simplify(sp.integrate(self.f, (X, lo, hi))) if lo < hi else 0
        self.median = self.quantile(0.5) if params.median else None

    def cdf(self, t: float) -> float:
        return float(sp.Integral(self.f, (X, self.a, t)).evalf())

    def quantile(self, q: float) -> float:
        lo = float(self.a)
        hi = float(self.b) if self.b != sp.oo else lo + 1
        while self.b == sp.oo and self.cdf(hi) < q:
            hi = lo + (hi - lo) * 2
        for _ in range(60):
            mid = (lo + hi) / 2
            if self.cdf(mid) < q:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    def _bound(self, value) -> str:
        return r"\infty" if value == sp.oo else _exact(value)

    def title_latex(self) -> str:
        a, b = self._bound(self.a), self._bound(self.b)
        return (
            rf"f(x) = {tidy_latex(self.written)},\ {a} \le x \le {b}"
            if self.b != sp.oo
            else (rf"f(x) = {tidy_latex(self.written)},\ x \ge {a}")
        )

    def answer_latex(self) -> str:
        out = [rf"E(X) = {_exact(self.mean)}"]
        if self.median is not None:
            out.append(rf"m = {format_sf(self.median, 3)}")
        return r",\ ".join(out)

    def row_groups(self) -> list[tuple[str, int]]:
        groups = [("k", 1 if self.k is None else 2)]
        if self.probability is not None:
            groups.append(("probability", 1))
        groups.append(("mean", 2))
        if self.median is not None:
            groups.append(("median", 1))
        return groups

    def rows(self) -> list[tuple[str, object]]:
        a, b = self._bound(self.a), self._bound(self.b)
        f = tidy_latex(self.f)
        rows = []
        if self.k is not None:
            rows.append(
                (
                    rf"\int_{{{a}}}^{{{b}}} {tidy_latex(self.written)}\,dx"
                    rf" = {tidy_latex(self.k_total)} = 1",
                    None,
                )
            )
            rows.append((rf"k = {latex_value(self.k)}", style.HIGHLIGHT_COLOUR))
        else:
            rows.append((rf"\int_{{{a}}}^{{{b}}} {f}\,dx = 1", None))
        if self.probability is not None:
            c, d = (self._bound(v) for v in self.event)
            event = rf"P(X > {c})" if self.event[1] == sp.oo else rf"P({c} < X < {d})"
            rows.append(
                (
                    rf"{event} = \int_{{{c}}}^{{{d}}} f\,dx"
                    rf" = {_value(self.probability)}",
                    None,
                )
            )
        rows.append((rf"E(X) = \int x f(x)\,dx = {_value(self.mean)}", style.RUN_COLOUR))
        rows.append(
            (
                rf"\mathrm{{Var}}(X) = {_short(self.ex2)} - \left({_exact(self.mean)}\right)^2"
                rf" = {_value(self.variance)}",
                None,
            )
        )
        if self.median is not None:
            rows.append(
                (
                    rf"\int_{{{a}}}^{{m}} f\,dx = \tfrac12"
                    rf" \Rightarrow m = {format_sf(self.median, 3)}",
                    None,
                )
            )
        return rows


def _value(value) -> str:
    """Exact when simple, with the decimal when the exact form is not a plain fraction."""
    value = sp.nsimplify(value)
    exact = _exact(value)
    if isinstance(value, sp.Rational) or exact != format_sf(value):
        return exact
    written = sp.latex(value)
    return rf"{written} \approx {format_sf(value)}" if len(written) <= 12 else format_sf(value)


def _short(value) -> str:
    """A step in the working: exact when it is a fraction or a short form, else 3 s.f."""
    exact = _exact(value)
    return exact if len(exact) <= 14 else format_sf(value)


def _exact(value) -> str:
    """A multiple of pi as one (pi/3, not 1.05); otherwise exact when simple."""
    value = sp.nsimplify(value)
    if value.has(sp.pi) and isinstance(value / sp.pi, sp.Rational):
        return latex_with_pi(value, approx=False)
    return latex_value(value)


def _limit(text: str, infinite: bool = False) -> sp.Expr:
    if infinite and text == "inf":
        return sp.oo
    value = sp.nsimplify(parse_expression(text, set()), [sp.pi], rational=True)
    if not value.is_real or not value.is_finite:
        raise ValueError(f"{text!r} is not a number")
    return value


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
