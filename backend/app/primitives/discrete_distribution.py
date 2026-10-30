"""DiscreteDistribution: a discrete random variable's distribution as a bar chart: a probability
table, binomial B(n, p), geometric Geo(p) or Poisson Po(λ); the probability of an event shaded
and worked out, and the expectation and variance (9709 5.4, 6.1).

P(X = r) is ⁿCᵣ pʳ(1 − p)ⁿ⁻ʳ for B(n, p), p(1 − p)ʳ⁻¹ for Geo(p) (r = 1, 2, ...), and
e^(−λ)λʳ/r! for Po(λ). An event is a set of values, and its probability is the sum of their
bars; with no upper end (Geo, Po) the complement 1 − P(X ≤ k − 1) is used. E(X) = Σx P(X = x)
and Var(X) = Σx² P(X = x) − E(X)², which give np and np(1 − p) for the binomial, 1/p for the
geometric and λ for both for the Poisson. Probabilities are exact where they are fractions,
otherwise to 3 (or 4) significant figures.
"""

from typing import Annotated, Literal

import sympy as sp
from manim import Rectangle, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import make_plot, make_table, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_sf, latex_value

Probability = Annotated[
    str, StringConstraints(pattern=r"^\d{1,3}(/\d{1,4})?$|^0?\.\d{1,4}$|^[01]$")
]
MAX_BARS = 15


class DiscreteDistributionParams(PrimitiveParams):
    kind: Literal["table", "binomial", "geometric", "poisson"]
    values: list[Annotated[int, Field(ge=-20, le=50)]] | None = Field(
        default=None, min_length=2, max_length=8, description="table: the values x"
    )
    probabilities: list[Probability] | None = Field(
        default=None, min_length=2, max_length=8, description='table: P(X = x), e.g. ["1/4", "0.3"]'
    )
    n: Annotated[int, Field(ge=1, le=30)] | None = Field(
        default=None, description="binomial: trials"
    )
    p: Probability | None = Field(
        default=None, description="binomial, geometric: success probability"
    )
    lam: Annotated[float, Field(gt=0, le=15)] | None = Field(default=None, description="poisson: λ")
    low: Annotated[int, Field(ge=-20, le=50)] | None = Field(
        default=None, description="The event low <= X <= high; leave out for no lower end"
    )
    high: Annotated[int, Field(ge=-20, le=50)] | None = Field(
        default=None, description="No upper end if left out"
    )


class DiscreteDistribution(StagedPrimitive[DiscreteDistributionParams]):
    primitive_id = "DiscreteDistribution"
    version = "1"
    topic = "Discrete random variables"
    params_model = DiscreteDistributionParams
    layout = LayoutContract(
        region=FULL_FRAME, allowed_overlaps=[("axes", "*"), ("bars", "*"), ("event", "*")]
    )

    def default_params(self) -> DiscreteDistributionParams:
        return DiscreteDistributionParams(kind="binomial", n=8, p="0.3", low=None, high=2)

    def validate(self, params: DiscreteDistributionParams) -> list[PredicateFailure]:
        kind = params.kind
        if kind == "table":
            if params.values is None or params.probabilities is None:
                return [_failure("table_given", "a table needs values and probabilities", "values")]
            if len(params.values) != len(params.probabilities):
                return [_failure("one_each", "one probability per value", "probabilities")]
            if len(set(params.values)) != len(params.values):
                return [_failure("values_distinct", "each value once", "values")]
            if sum(exact(_prob(p)) for p in params.probabilities) != 1:
                return [_failure("sum_one", "the probabilities must add to 1", "probabilities")]
        if kind == "binomial" and (params.n is None or params.p is None):
            return [_failure("parameters_given", "B(n, p) needs n and p", "n", "p")]
        if kind == "geometric" and params.p is None:
            return [_failure("parameters_given", "Geo(p) needs p", "p")]
        if kind == "poisson" and params.lam is None:
            return [_failure("parameters_given", "Po(λ) needs lam", "lam")]
        if kind in ("binomial", "geometric") and not 0 < _prob(params.p) < 1:
            return [_failure("p_between", "p must be between 0 and 1", "p")]
        if params.low is None and params.high is None:
            return [_failure("event_given", "give low, high or both for the event", "low", "high")]
        if params.low is not None and params.high is not None and params.low > params.high:
            return [_failure("event_ordered", "low must not exceed high", "low", "high")]
        if kind == "binomial" and params.high is not None and params.high > params.n + 10:
            return [_failure("event_fits", "the event lies beyond n", "high")]
        return []

    def computed_values(self, params: DiscreteDistributionParams) -> dict[str, str]:
        d = _Dist(params)
        values = {"probability": d.text(d.answer), "mean": d.text(d.mean)}
        if d.variance is not None:
            values["variance"] = d.text(d.variance)
        return values

    def build(self, params: DiscreteDistributionParams, level):
        d = _Dist(params)
        xs = [x for x, _ in d.shown]
        ps = [float(p) for _, p in d.shown]
        plot = make_plot(
            style.GRAPH_REGION,
            [min(xs) - 0.5, max(xs) + 0.5],
            [0, max(ps) * 1.1],
            x_label="x",
            y_label=r"P(X = x)",
            x_axis=(min(min(xs) - 1, 0), max(xs) + 1, 1 if len(xs) <= 12 else 2),
            y_ticks=5,
        )
        width = (plot.point(1, 0)[0] - plot.point(0, 0)[0]) * 0.7
        bars, event = VGroup(), VGroup()
        for x, p in d.shown:
            top = plot.point(x, float(p))
            bottom = plot.point(x, 0)
            bar = Rectangle(
                width=width,
                height=max(top[1] - bottom[1], 1e-3),
                stroke_width=1.5,
                stroke_color=style.CURVE_COLOUR,
                fill_color=style.CURVE_COLOUR,
                fill_opacity=0.35,
            )
            bar.move_to((top + bottom) / 2)
            bars.add(bar)
            if d.in_event(x):
                event.add(
                    bar.copy()
                    .set_fill(style.HIGHLIGHT_COLOUR, opacity=0.75)
                    .set_stroke(style.HIGHLIGHT_COLOUR)
                )
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "title": text_line(d.title_latex(), plot.upper),
            "bars": bars,
            "event": event,
            "answer": text_line(
                rf"{d.event_latex()} = {d.latex(d.answer)}",
                plot.lower,
                colour=style.HIGHLIGHT_COLOUR,
            ),
        }
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        rows = d.rows()
        top_box = box
        if params.kind == "table":
            table = make_table(
                [
                    ["x", *(str(v) for v in params.values)],
                    ["P", *(d.latex(_prob(p)) for p in params.probabilities)],
                ],
                style.Box(box.left, box.right, box.top - 1.3, box.top),
                font_size=28,
                pad=0.12,
            )
            parts["table"] = table.group
            top_box = style.Box(box.left, box.right, box.bottom, table.group.get_bottom()[1] - 0.25)
        texts = stack_lines([r for r, _ in rows], top_box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: DiscreteDistributionParams, level) -> list[Stage]:
        d = _Dist(params)
        n = len(d.rows())
        first = ["axes", "x_label", "y_label", "title", "bars"] + (
            ["table"] if params.kind == "table" else []
        )
        steps = [
            stage("distribution", d.describe(), 3.5, [*first, "row_1"]),
            stage(
                "event",
                "Shade the values in the event: its probability is the sum of their bars",
                3.5,
                ["event", "row_2"],
            ),
            stage(
                "probability",
                "Add them up"
                if not d.complement
                else "There is no top end, so use one minus the complement",
                3.5,
                ["row_3", "answer"],
                emphasise=["answer"],
            ),
            stage(
                "mean",
                "The expectation, and the variance",
                3.0,
                [f"row_{i}" for i in range(4, n + 1)],
            ),
        ]

        def standard(s):
            return [s[0], combine("probability", s[1].description, 4.0, s[1], s[2]), s[3]]

        def concise(s):
            return [
                s[0],
                combine("probability", "The probability of the event, and the mean", 4.5, *s[1:]),
            ]

        return by_level(level, steps, standard, concise)


def _prob(text) -> sp.Rational:
    return sp.nsimplify(str(text), rational=True)


class _Dist:
    def __init__(self, params: DiscreteDistributionParams):
        self.params = params
        kind = params.kind
        self.complement = False
        if kind == "table":
            self.pmf = {
                v: _prob(p) for v, p in zip(params.values, params.probabilities, strict=True)
            }
            self.support = sorted(self.pmf)
            self.mean = sum(x * p for x, p in self.pmf.items())
            self.variance = sum(x**2 * p for x, p in self.pmf.items()) - self.mean**2
        elif kind == "binomial":
            n, p = params.n, _prob(params.p)
            self.pmf = {r: sp.binomial(n, r) * p**r * (1 - p) ** (n - r) for r in range(n + 1)}
            self.support = list(range(n + 1))
            self.mean, self.variance = n * p, n * p * (1 - p)
        elif kind == "geometric":
            p = _prob(params.p)
            self.pmf_f = lambda r: p * (1 - p) ** (r - 1)
            self.support = list(range(1, MAX_BARS + 1))
            self.pmf = {r: self.pmf_f(r) for r in self.support}
            self.mean, self.variance = 1 / p, None
        else:
            lam = exact(params.lam)
            self.pmf = {r: sp.exp(-lam) * lam**r / sp.factorial(r) for r in range(0, MAX_BARS + 1)}
            self.support = list(range(0, MAX_BARS + 1))
            self.mean, self.variance = lam, lam
        self.shown = self._shown()
        self.answer = self._answer()

    def _shown(self):
        if self.params.kind in ("table", "binomial") and len(self.support) <= MAX_BARS + 6:
            return [(x, self.pmf[x]) for x in self.support]
        # the bars that carry nearly all the probability
        out, total = [], 0
        for x in self.support:
            out.append((x, self.pmf[x]))
            total += float(self.pmf[x])
            if total > 0.995 and len(out) >= 4:
                break
        return out

    def in_event(self, x) -> bool:
        low, high = self.params.low, self.params.high
        return (low is None or x >= low) and (high is None or x <= high)

    def _answer(self):
        low, high = self.params.low, self.params.high
        if self.params.kind in ("geometric", "poisson") and high is None:
            self.complement = True
            start = self.support[0]
            below = sum(self.pmf_value(x) for x in range(start, low))
            return 1 - below
        lo = low if low is not None else self.support[0]
        hi = high if high is not None else self.support[-1]
        return sum(
            self.pmf_value(x)
            for x in range(lo, hi + 1)
            if x in self.pmf or self.params.kind in ("geometric", "poisson")
        )

    def pmf_value(self, x):
        if x in self.pmf:
            return self.pmf[x]
        if self.params.kind == "geometric" and x >= 1:
            return _prob(self.params.p) * (1 - _prob(self.params.p)) ** (x - 1)
        if self.params.kind == "poisson" and x >= 0:
            lam = exact(self.params.lam)
            return sp.exp(-lam) * lam**x / sp.factorial(x)
        return 0

    def text(self, value) -> str:
        value = sp.nsimplify(value) if not isinstance(value, float) else value
        if isinstance(value, sp.Rational) and value.q <= 1000:
            return str(value)
        return format_sf(value, 4) if float(value) < 1 else format_sf(value)

    def latex(self, value) -> str:
        value = sp.nsimplify(value) if not isinstance(value, float) else value
        if isinstance(value, sp.Rational) and value.q <= 1000 and self.params.kind == "table":
            return latex_value(value)
        if isinstance(value, sp.Rational) and value.is_integer:
            return str(value)
        return format_sf(value, 4) if abs(float(value)) < 1 else format_sf(value)

    def title_latex(self) -> str:
        p = self.params
        if p.kind == "table":
            return r"\text{A probability distribution}"
        if p.kind == "binomial":
            return rf"X \sim B({p.n},\ {p.p})"
        if p.kind == "geometric":
            return rf"X \sim \mathrm{{Geo}}({p.p})"
        return rf"X \sim \mathrm{{Po}}({format_sf(p.lam, 6)})"

    def describe(self) -> str:
        return {
            "table": "The probabilities of the values, as bars: they add to 1",
            "binomial": "n independent trials, each a success with probability p: the binomial",
            "geometric": "Trials until the first success: the geometric distribution",
            "poisson": "Random events at a constant average rate: the Poisson distribution",
        }[self.params.kind]

    def event_latex(self) -> str:
        low, high = self.params.low, self.params.high
        if low is not None and high is not None:
            return f"P(X = {low})" if low == high else rf"P({low} \le X \le {high})"
        if low is None:
            return rf"P(X \le {high})"
        return rf"P(X \ge {low})"

    def formula(self) -> str:
        p = self.params
        if p.kind == "table":
            return r"P(X = x)\text{ from the table}"
        if p.kind in ("binomial", "geometric"):
            q = latex_value(1 - _prob(p.p))
            if p.kind == "binomial":
                return rf"P(X = r) = \binom{{{p.n}}}{{r}}({p.p})^r({q})^{{{p.n} - r}}"
            return rf"P(X = r) = {p.p}\times({q})^{{r - 1}}"
        lam = format_sf(p.lam, 6)
        return rf"P(X = r) = e^{{-{lam}}}\frac{{{lam}^r}}{{r!}}"

    def rows(self) -> list[tuple[str, object]]:
        low, high = self.params.low, self.params.high
        if self.complement:
            terms = list(range(self.support[0], low))
            pieces = " + ".join(self.latex(self.pmf_value(x)) for x in terms[:5])
            pieces += r" + \dots" if len(terms) > 5 else ""
            rows = [
                (self.formula(), None),
                (rf"{self.event_latex()} = 1 - P(X \le {low - 1})", None),
                (rf"= 1 - ({pieces}) = {self.latex(self.answer)}", style.HIGHLIGHT_COLOUR),
            ]
        else:
            lo = low if low is not None else self.support[0]
            hi = high if high is not None else self.support[-1]
            terms = list(range(lo, hi + 1))
            pieces = " + ".join(self.latex(self.pmf_value(x)) for x in terms[:6])
            pieces += r" + \dots" if len(terms) > 6 else ""
            rows = [
                (self.formula(), None),
                (rf"{self.event_latex()} = {pieces}", None),
                (rf"= {self.latex(self.answer)}", style.HIGHLIGHT_COLOUR),
            ]
        p = self.params
        if p.kind == "table":
            rows.append((rf"E(X) = \Sigma xP = {self.latex(self.mean)}", None))
            rows.append(
                (rf"\mathrm{{Var}}(X) = \Sigma x^2P - E(X)^2 = {self.latex(self.variance)}", None)
            )
        elif p.kind == "binomial":
            rows.append((rf"E(X) = np = {self.latex(self.mean)}", None))
            rows.append((rf"\mathrm{{Var}}(X) = np(1 - p) = {self.latex(self.variance)}", None))
        elif p.kind == "geometric":
            rows.append((rf"E(X) = \frac{{1}}{{p}} = {self.latex(self.mean)}", None))
        else:
            rows.append((rf"E(X) = \mathrm{{Var}}(X) = \lambda = {format_sf(p.lam, 6)}", None))
        return rows


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
