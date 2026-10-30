"""NormalDistribution: X ~ N(μ, σ²) as a bell curve: probabilities as shaded areas found by
standardising, the inverse problem (the x with a given probability), finding μ or σ (or both)
from given probabilities, and the normal approximation to a binomial or Poisson distribution
with a continuity correction (9709 5.5, 6.1).

Standardising, Z = (X − μ)/σ turns every normal distribution into N(0, 1), whose cumulative
probabilities Φ(z) are in the tables. P(X > x) = 1 − Φ(z), and Φ(−z) = 1 − Φ(z) by symmetry. For
the inverse, z = Φ⁻¹(p) and x = μ + zσ. Each given probability gives an equation
(x − μ)/σ = z, so one finds μ or σ and two find both. A discrete count is approximated by
N(np, npq) (np and nq > 5) or N(λ, λ) (λ > 15), widening each whole number to ± 0.5. Φ is
computed from the error function; probabilities are to 4 significant figures, z to 3 or 4 d.p.
"""

import math
from typing import Annotated, Literal

import numpy as np
from manim import DashedLine, Polygon, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import curve, label, make_plot, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf

Real = Annotated[float, Field(ge=-10_000, le=10_000)]


class Condition(PrimitiveParams):
    x: Real
    below: Annotated[float, Field(gt=0, lt=1)] = Field(description="P(X < x)")


class NormalDistributionParams(PrimitiveParams):
    kind: Literal["probability", "inverse", "find_parameters", "approximation"]
    mu: Real | None = Field(default=None, description="The mean (leave out to find it)")
    sigma: Annotated[float, Field(gt=0, le=10_000)] | None = Field(
        default=None, description="The standard deviation (leave out to find it)"
    )
    low: Real | None = Field(
        default=None, description="probability, approximation: P(low < X < high)"
    )
    high: Real | None = Field(default=None, description="Leave out for no upper end")
    probability: Annotated[float, Field(gt=0, lt=1)] | None = Field(
        default=None, description="inverse: the probability"
    )
    tail: Literal["below", "above"] = Field(
        default="below", description="inverse: P(X < x) or P(X > x)"
    )
    conditions: list[Condition] | None = Field(
        default=None, min_length=1, max_length=2, description="find_parameters"
    )
    source: Literal["binomial", "poisson"] | None = Field(
        default=None, description="approximation: what is approximated"
    )
    n: Annotated[int, Field(ge=1, le=10_000)] | None = Field(
        default=None, description="approximation: binomial n"
    )
    p: Annotated[float, Field(gt=0, lt=1)] | None = Field(
        default=None, description="approximation: binomial p"
    )
    lam: Annotated[float, Field(gt=0, le=1000)] | None = Field(
        default=None, description="approximation: Poisson λ"
    )


def phi(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def phi_inverse(p: float) -> float:
    lo, hi = -10.0, 10.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if phi(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


class NormalDistribution(StagedPrimitive[NormalDistributionParams]):
    primitive_id = "NormalDistribution"
    version = "1"
    topic = "The normal distribution"
    params_model = NormalDistributionParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[("axes", "*"), ("curve", "*"), ("area", "*"), ("marks", "*")],
    )

    def default_params(self) -> NormalDistributionParams:
        return NormalDistributionParams(kind="probability", mu=50, sigma=8, low=45, high=60)

    def validate(self, params: NormalDistributionParams) -> list[PredicateFailure]:
        kind = params.kind
        if kind in ("probability", "inverse") and (params.mu is None or params.sigma is None):
            return [_failure("parameters_given", "give mu and sigma", "mu", "sigma")]
        if kind in ("probability", "approximation") and params.low is None and params.high is None:
            return [_failure("event_given", "give low, high or both", "low", "high")]
        if params.low is not None and params.high is not None and params.low >= params.high:
            return [_failure("event_ordered", "low must be below high", "low", "high")]
        if kind == "inverse" and params.probability is None:
            return [_failure("probability_given", "give the probability", "probability")]
        if kind == "find_parameters":
            unknown = (params.mu is None) + (params.sigma is None)
            if unknown == 0 or params.conditions is None or len(params.conditions) != unknown:
                message = "leave out mu, sigma or both, and give one condition for each"
                return [_failure("one_condition_each", message, "conditions")]
            if unknown == 2:
                (c1, c2) = params.conditions
                if (c1.x - c2.x) * (c1.below - c2.below) <= 0:
                    message = "a larger x must have a larger probability below it"
                    return [_failure("conditions_consistent", message, "conditions")]
        if kind == "approximation":
            if params.source == "binomial":
                if params.n is None or params.p is None:
                    return [_failure("parameters_given", "give n and p", "n", "p")]
                if params.n * params.p <= 5 or params.n * (1 - params.p) <= 5:
                    message = "the approximation needs np > 5 and nq > 5"
                    return [_failure("approximation_valid", message, "n", "p")]
            elif params.source == "poisson":
                if params.lam is None:
                    return [_failure("parameters_given", "give lam", "lam")]
                if params.lam <= 15:
                    return [
                        _failure("approximation_valid", "the approximation needs λ > 15", "lam")
                    ]
            else:
                return [_failure("source_given", "say what is approximated", "source")]
            for v in (params.low, params.high):
                if v is not None and v != int(v):
                    return [
                        _failure(
                            "whole_numbers", "a count's event needs whole numbers", "low", "high"
                        )
                    ]
        work = _Work(params)
        if work.sigma <= 0:
            return [
                _failure(
                    "sigma_positive",
                    "the conditions give a negative standard deviation",
                    "conditions",
                )
            ]
        return []

    def computed_values(self, params: NormalDistributionParams) -> dict[str, str]:
        work = _Work(params)
        values = {"mu": format_sf(work.mu, 4), "sigma": format_sf(work.sigma, 4)}
        if work.answer is not None:
            values["answer"] = format_sf(work.answer, 4)
        return values

    def build(self, params: NormalDistributionParams, level):
        work = _Work(params)
        mu, sigma = work.mu, work.sigma
        lo, hi = mu - 4 * sigma, mu + 4 * sigma
        peak = 1 / (sigma * math.sqrt(2 * math.pi))
        plot = make_plot(
            style.GRAPH_REGION, [lo, hi], [0, peak * 1.15], origin=False, y_ticks=4, y_label=""
        )
        plot.axes.y_axis.set_opacity(0)

        def density(x):
            return peak * math.exp(-((x - mu) ** 2) / (2 * sigma**2))

        a, b = work.region
        a_draw, b_draw = max(a, lo), min(b, hi)
        xs = np.linspace(a_draw, b_draw, 120)
        outline = (
            [plot.point(a_draw, 0)]
            + [plot.point(x, density(x)) for x in xs]
            + [plot.point(b_draw, 0)]
        )
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "title": text_line(work.title_latex(), plot.upper),
            "curve": curve(plot, density, lo, hi),
            "area": Polygon(
                *outline, stroke_width=0, fill_color=style.AREA_COLOUR, fill_opacity=0.55
            ),
            "answer": text_line(work.answer_latex(), plot.lower, colour=style.HIGHLIGHT_COLOUR),
        }
        marks, labels = VGroup(), []
        for x in work.marked:
            if lo <= x <= hi:
                marks.add(
                    DashedLine(
                        plot.point(x, 0),
                        plot.point(x, density(x)),
                        color=style.HIGHLIGHT_COLOUR,
                        stroke_width=2,
                    )
                )
                labels.append(
                    label(
                        rf"z = {(x - mu) / sigma:.3f}",
                        colour=style.HIGHLIGHT_COLOUR,
                        size=22,
                    ).next_to(plot.point(x, 0), [0, -1, 0], buff=0.45)
                )
        if len(labels) == 2 and labels[0].get_right()[0] + 0.15 > labels[1].get_left()[0]:
            # two close values: each label moves out to its own side of its line
            labels[0].shift([-labels[0].width / 2 - 0.05, 0, 0])
            labels[1].shift([labels[1].width / 2 + 0.05, 0, 0])
        marks.add(*labels)
        parts["marks"] = marks
        rows = work.rows()
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: NormalDistributionParams, level) -> list[Stage]:
        n = len(_Work(params).rows())
        rows = [f"row_{i}" for i in range(1, n + 1)]
        first_words = {
            "probability": "The normal curve: the probability is the area under it",
            "inverse": "Here the area is known; we want the value of x",
            "find_parameters": "The probabilities are known; the mean or standard deviation is not",
            "approximation": "Approximate by a normal curve with the same mean and variance",
        }[params.kind]
        steps = [
            stage("curve", first_words, 3.0, ["axes", "x_label", "title", "curve", rows[0]]),
            stage(
                "standardise",
                "Standardise: z equals x minus mu, over sigma",
                3.5,
                rows[1:-1] + ["marks"],
            ),
            stage(
                "area",
                "Use the table of Phi, and the symmetry of the curve",
                3.5,
                ["area", rows[-1], "answer"],
                emphasise=["answer"],
            ),
        ]

        def standard(s):
            return list(s)

        def concise(s):
            return [s[0], combine("area", "Standardise and use the table", 4.5, s[1], s[2])]

        return by_level(level, steps, standard, concise)


class _Work:
    def __init__(self, params: NormalDistributionParams):
        self.params = params
        self.answer = None
        self.marked = []
        self.extra_rows = []
        kind = params.kind
        if kind == "approximation":
            if params.source == "binomial":
                self.mu = params.n * params.p
                self.var = params.n * params.p * (1 - params.p)
            else:
                self.mu = self.var = params.lam
            self.sigma = math.sqrt(self.var)
            self.cc_low = params.low - 0.5 if params.low is not None else None
            self.cc_high = params.high + 0.5 if params.high is not None else None
            self._probability(self.cc_low, self.cc_high)
        elif kind == "probability":
            self.mu, self.sigma = params.mu, params.sigma
            self._probability(params.low, params.high)
        elif kind == "inverse":
            self.mu, self.sigma = params.mu, params.sigma
            below = params.probability if params.tail == "below" else 1 - params.probability
            self.z = phi_inverse(below)
            self.answer = self.mu + self.z * self.sigma
            self.marked = [self.answer]
            self.region = (
                (-math.inf, self.answer) if params.tail == "below" else (self.answer, math.inf)
            )
        else:
            self._parameters()

    def _probability(self, low, high):
        z_low = (low - self.mu) / self.sigma if low is not None else None
        z_high = (high - self.mu) / self.sigma if high is not None else None
        p_low = phi(z_low) if z_low is not None else 0.0
        p_high = phi(z_high) if z_high is not None else 1.0
        self.z_low, self.z_high = z_low, z_high
        self.answer = p_high - p_low
        self.marked = [v for v in (low, high) if v is not None]
        self.region = (
            low if low is not None else -math.inf,
            high if high is not None else math.inf,
        )

    def _parameters(self):
        p = self.params
        cs = p.conditions
        zs = [round(phi_inverse(c.below), 4) for c in cs]
        self.zs = zs
        if p.mu is None and p.sigma is None:
            (c1, z1), (c2, z2) = zip(cs, zs, strict=True)
            self.sigma = (c2.x - c1.x) / (z2 - z1)
            self.mu = c1.x - z1 * self.sigma
        elif p.mu is None:
            self.sigma = p.sigma
            self.mu = cs[0].x - zs[0] * self.sigma
        else:
            self.mu = p.mu
            self.sigma = (cs[0].x - self.mu) / zs[0] if zs[0] != 0 else 0.0
        self.marked = [c.x for c in cs]
        self.region = (-math.inf, cs[0].x)

    def title_latex(self) -> str:
        p = self.params
        if p.kind == "approximation":
            source = (
                rf"B({p.n},\ {format_sf(p.p, 6)})"
                if p.source == "binomial"
                else rf"\mathrm{{Po}}({format_sf(p.lam, 6)})"
            )
            return rf"X \sim {source} \approx N({format_sf(self.mu, 6)},\ {format_sf(self.var, 6)})"
        if p.kind == "find_parameters":
            mu = r"\mu" if p.mu is None else format_sf(p.mu, 6)
            var = r"\sigma^2" if p.sigma is None else format_sf(p.sigma**2, 6)
            return rf"X \sim N({mu},\ {var})"
        return rf"X \sim N({format_sf(self.mu, 6)},\ {format_sf(self.sigma**2, 6)})"

    def _event(self, low, high, name="X") -> str:
        if low is not None and high is not None:
            return rf"P({format_sf(low, 6)} < {name} < {format_sf(high, 6)})"
        if low is None:
            return rf"P({name} < {format_sf(high, 6)})"
        return rf"P({name} > {format_sf(low, 6)})"

    def answer_latex(self) -> str:
        p = self.params
        if p.kind == "inverse":
            return rf"x = {format_sf(self.answer, 4)}"
        if p.kind == "find_parameters":
            out = []
            if p.mu is None:
                out.append(rf"\mu = {format_sf(self.mu, 4)}")
            if p.sigma is None:
                out.append(rf"\sigma = {format_sf(self.sigma, 4)}")
            return r",\ ".join(out)
        low, high = (p.low, p.high)
        if p.kind == "approximation":
            return rf"{self._discrete_event()} \approx {format_sf(self.answer, 4)}"
        return rf"{self._event(low, high)} = {format_sf(self.answer, 4)}"

    def _discrete_event(self) -> str:
        p = self.params
        low, high = p.low, p.high
        if low is not None and high is not None:
            return rf"P({int(low)} \le X \le {int(high)})"
        if low is None:
            return rf"P(X \le {int(high)})"
        return rf"P(X \ge {int(low)})"

    def rows(self) -> list[tuple[str, object]]:
        p = self.params
        mu, sigma = format_sf(self.mu, 6), format_sf(self.sigma, 4)
        if p.kind == "inverse":
            table = (
                f"{p.probability}"
                if p.tail == "below"
                else f"1 - {p.probability} = {format_sf(1 - p.probability, 6)}"
            )
            return [
                (rf"P(X {'<' if p.tail == 'below' else '>'} x) = {p.probability}", None),
                (rf"\Phi(z) = {table}", None),
                (rf"z = {self.z:.4f}", None),
                (
                    rf"x = {mu} + {self.z:.4f}\times {sigma} = {format_sf(self.answer, 4)}",
                    style.HIGHLIGHT_COLOUR,
                ),
            ]
        if p.kind == "find_parameters":
            rows = [
                (
                    r"\text{Given: }"
                    + r",\ ".join(rf"P(X < {format_sf(c.x, 6)}) = {c.below}" for c in p.conditions),
                    None,
                )
            ]
            m = r"\mu" if p.mu is None else mu
            s = r"\sigma" if p.sigma is None else sigma
            for c, z in zip(p.conditions, self.zs, strict=True):
                rows.append((rf"\frac{{{format_sf(c.x, 6)} - {m}}}{{{s}}} = {z:.4f}", None))
            rows.append((self.answer_latex(), style.HIGHLIGHT_COLOUR))
            return rows
        rows = []
        if p.kind == "approximation":
            check = (
                rf"np = {format_sf(self.mu, 4)} > 5,\ nq = {format_sf(p.n * (1 - p.p), 4)} > 5"
                if p.source == "binomial"
                else rf"\lambda = {format_sf(p.lam, 6)} > 15"
            )
            rows.append((check, None))
            rows.append(
                (
                    rf"{self._discrete_event()} \to {self._event(self.cc_low, self.cc_high)}",
                    style.RUN_COLOUR,
                )
            )
            low, high = self.cc_low, self.cc_high
        else:
            rows.append((self._event(p.low, p.high), None))
            low, high = p.low, p.high
        for value in (low, high):
            if value is not None:
                z = (value - self.mu) / self.sigma
                rows.append(
                    (rf"z = \frac{{{format_sf(value, 6)} - {mu}}}{{{sigma}}} = {z:.3f}", None)
                )
        rows.append((_phi_row(self.z_low, self.z_high), None))
        rows.append((rf"= {format_sf(self.answer, 4)}", style.HIGHLIGHT_COLOUR))
        return rows


def _phi_row(z_low, z_high) -> str:
    """The area from the table: Φ of the upper z, less Φ of the lower, with Φ(−z) = 1 − Φ(z)."""
    if z_low is None:
        if z_high < 0:
            return rf"\Phi({z_high:.3f}) = 1 - \Phi({-z_high:.3f}) = 1 - {phi(-z_high):.4f}"
        return rf"\Phi({z_high:.3f})"
    if z_high is None:
        if z_low < 0:
            return rf"1 - \Phi({z_low:.3f}) = \Phi({-z_low:.3f})"
        return rf"1 - \Phi({z_low:.3f}) = 1 - {phi(z_low):.4f}"
    return rf"\Phi({z_high:.3f}) - \Phi({z_low:.3f}) = {phi(z_high):.4f} - {phi(z_low):.4f}"


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
