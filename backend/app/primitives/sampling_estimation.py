"""SamplingEstimation: what a sample says about its population: unbiased estimates of the mean
and variance from sample totals, the distribution of the sample mean (narrower than the
population's, by √n), and confidence intervals for a mean or a proportion drawn on a number line
around the estimate (9709 6.4).

From n values, x̄ = Σx/n estimates μ and s² = (Σx² − (Σx)²/n)/(n − 1) estimates σ²: dividing by
n − 1, not n, makes the estimate unbiased. With coded totals Σ(x − a) and Σ(x − a)², the mean
shifts back by a and the variance is unchanged. The mean of a random sample has
X̄ ~ N(μ, σ²/n) when the population is normal, and approximately so for any population when n is
large (the Central Limit Theorem). An α% confidence interval for μ is x̄ ± z√(σ²/n) with
Φ(z) = ½(1 + α/100), using s for σ when the sample is large; for a proportion it is
p̂ ± z√(p̂(1 − p̂)/n) with p̂ = x/n. Values are to 4 significant figures.
"""

import math
from typing import Annotated, Literal

import numpy as np
from manim import DashedLine, Dot, Line, NumberLine, Polygon, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.normal_distribution import phi, phi_inverse
from app.primitives.plotting import axis_range, curve, label, make_plot, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf

Number = Annotated[float, Field(ge=-1e7, le=1e7)]


class SamplingEstimationParams(PrimitiveParams):
    kind: Literal["estimates", "sample_mean", "mean_interval", "proportion_interval"]
    n: Annotated[int, Field(ge=2, le=100_000)] = Field(description="The sample size")
    sum_x: Number | None = Field(default=None, description="estimates: Σx, or Σ(x − a)")
    sum_x2: Annotated[float, Field(ge=0, le=1e12)] | None = Field(
        default=None, description="estimates: Σx², or Σ(x − a)²"
    )
    a: Number | None = Field(default=None, description="estimates: the a of coded totals")
    mu: Number | None = Field(default=None, description="sample_mean: the population mean")
    sigma: Annotated[float, Field(gt=0, le=1e6)] | None = Field(
        default=None, description="The population standard deviation (or its estimate s)"
    )
    mean: Number | None = Field(default=None, description="mean_interval: the sample mean")
    successes: Annotated[int, Field(ge=1)] | None = Field(
        default=None, description="proportion_interval: how many in the sample have the property"
    )
    level: Annotated[float, Field(ge=50, le=99.9)] = Field(
        default=95, description="The confidence level, in percent"
    )
    low: Number | None = Field(default=None, description="sample_mean: P(low < X̄ < high)")
    high: Number | None = Field(default=None, description="Leave out for no upper end")
    normal_population: bool = Field(
        default=True, description="sample_mean: the population is normal (else n must be large)"
    )


class SamplingEstimation(StagedPrimitive[SamplingEstimationParams]):
    primitive_id = "SamplingEstimation"
    version = "1"
    topic = "Sampling and estimation"
    params_model = SamplingEstimationParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[("axes", "*"), ("curve", "*"), ("area", "*"), ("marks", "*")],
    )

    def default_params(self) -> SamplingEstimationParams:
        return SamplingEstimationParams(kind="mean_interval", n=50, mean=24.3, sigma=4.2)

    def validate(self, params: SamplingEstimationParams) -> list[PredicateFailure]:
        kind = params.kind
        if kind == "estimates":
            if params.sum_x is None or params.sum_x2 is None:
                return [_failure("totals_given", "give sum_x and sum_x2", "sum_x", "sum_x2")]
            if params.sum_x2 - params.sum_x**2 / params.n < -1e-9:
                message = "these totals give a negative variance"
                return [_failure("totals_consistent", message, "sum_x", "sum_x2")]
        if kind == "sample_mean":
            if params.mu is None or params.sigma is None:
                return [_failure("population_given", "give mu and sigma", "mu", "sigma")]
            if params.low is None and params.high is None:
                return [_failure("event_given", "give low, high or both", "low", "high")]
            if params.low is not None and params.high is not None and params.low >= params.high:
                return [_failure("event_ordered", "low must be below high", "low", "high")]
            if not params.normal_population and params.n < 30:
                message = "without a normal population the sample must be large (n ≥ 30)"
                return [_failure("large_sample", message, "n", "normal_population")]
        if kind == "mean_interval" and (params.mean is None or params.sigma is None):
            return [_failure("sample_given", "give the sample mean and sigma", "mean", "sigma")]
        if kind == "proportion_interval":
            if params.successes is None or params.successes >= params.n:
                message = "give a number of successes below n"
                return [_failure("successes_given", message, "successes")]
        return []

    def computed_values(self, params: SamplingEstimationParams) -> dict[str, str]:
        w = _Work(params)
        return {key: format_sf(value, 4) for key, value in w.values.items()}

    def build(self, params: SamplingEstimationParams, level):
        w = _Work(params)
        if params.kind == "sample_mean":
            parts = _two_curves(w)
        else:
            parts = _interval_line(w)
        rows = w.rows()
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: SamplingEstimationParams, level) -> list[Stage]:
        w = _Work(params)
        n = len(w.rows())
        rows = [f"row_{i}" for i in range(1, n + 1)]
        split = 2  # the setup rows; the rest are the result
        first, second = {
            "estimates": (
                "The sample mean estimates the population mean",
                "Dividing by n minus 1 makes the variance estimate unbiased",
            ),
            "sample_mean": (
                "The mean of a sample varies less than one value: its variance is divided by n",
                "Standardise the sample mean to find the probability",
            ),
            "mean_interval": (
                "The standard error measures how much the sample mean varies",
                "Go z standard errors either side of the estimate",
            ),
            "proportion_interval": (
                "The sample proportion estimates the population proportion",
                "Go z standard errors either side of it",
            ),
        }[params.kind]
        steps = [
            stage("setup", first, 3.5, ["axes", "x_label", "title", "curve", *rows[:split]]),
            stage(
                "result",
                second,
                4.0,
                ["area", "marks", *rows[split:], "answer"],
                emphasise=["answer"],
            ),
        ]

        def standard(s):
            return list(s)

        def concise(s):
            return [combine("all", "Estimate from the sample", 5.0, *s)]

        return by_level(level, steps, standard, concise)


class _Work:
    def __init__(self, params: SamplingEstimationParams):
        self.params = params
        p = params
        kind = p.kind
        self.z = phi_inverse(0.5 * (1 + p.level / 100))
        self.values = {}
        if kind == "estimates":
            shift = p.a or 0
            self.mean = p.sum_x / p.n + shift
            self.s2 = (p.sum_x2 - p.sum_x**2 / p.n) / (p.n - 1)
            self.values = {"mean": self.mean, "variance": self.s2}
            self.centre, self.spread = self.mean, math.sqrt(self.s2)
            self.interval = (self.mean - self.spread, self.mean + self.spread)
        elif kind == "sample_mean":
            self.se = p.sigma / math.sqrt(p.n)
            lo, hi = p.low, p.high
            self.zs = [(v - p.mu) / self.se if v is not None else None for v in (lo, hi)]
            p_lo = phi(self.zs[0]) if lo is not None else 0.0
            p_hi = phi(self.zs[1]) if hi is not None else 1.0
            self.probability = p_hi - p_lo
            self.values = {"standard_error": self.se, "probability": self.probability}
        elif kind == "mean_interval":
            self.se = p.sigma / math.sqrt(p.n)
            self.centre = p.mean
            self.interval = (p.mean - self.z * self.se, p.mean + self.z * self.se)
            self.values = {"lower": self.interval[0], "upper": self.interval[1]}
        else:
            self.p_hat = p.successes / p.n
            self.se = math.sqrt(self.p_hat * (1 - self.p_hat) / p.n)
            self.centre = self.p_hat
            self.interval = (self.p_hat - self.z * self.se, self.p_hat + self.z * self.se)
            self.values = {"lower": self.interval[0], "upper": self.interval[1]}

    def title_latex(self) -> str:
        p = self.params
        if p.kind == "estimates":
            return rf"n = {p.n}"
        if p.kind == "sample_mean":
            return (
                rf"X \sim N({format_sf(p.mu, 6)},\ {format_sf(p.sigma, 6)}^2)"
                if p.normal_population
                else (rf"E(X) = {format_sf(p.mu, 6)},\ \sigma = {format_sf(p.sigma, 6)}")
            )
        if p.kind == "mean_interval":
            return rf"n = {p.n},\ \bar x = {format_sf(p.mean, 6)}"
        return rf"{p.successes} \text{{ of }} {p.n}"

    def answer_latex(self) -> str:
        p = self.params
        if p.kind == "estimates":
            return rf"\bar x = {format_sf(self.mean, 4)},\ s^2 = {format_sf(self.s2, 4)}"
        if p.kind == "sample_mean":
            return rf"{self._event()} = {format_sf(self.probability, 4)}"
        lo, hi = self.interval
        return rf"{format_sf(p.level, 6)}\%\ \text{{CI}}: ({format_sf(lo, 4)},\ {format_sf(hi, 4)})"

    def _event(self) -> str:
        p = self.params
        lo, hi = p.low, p.high
        if lo is not None and hi is not None:
            return rf"P({format_sf(lo, 6)} < \bar X < {format_sf(hi, 6)})"
        if lo is None:
            return rf"P(\bar X < {format_sf(hi, 6)})"
        return rf"P(\bar X > {format_sf(lo, 6)})"

    def rows(self) -> list[tuple[str, object]]:
        p = self.params
        n = p.n
        if p.kind == "estimates":
            coded = p.a is not None
            sx = r"\Sigma(x - a)" if coded else r"\Sigma x"
            sx2 = r"\Sigma(x - a)^2" if coded else r"\Sigma x^2"
            mean_row = rf"\bar x = \frac{{{format_sf(p.sum_x, 8)}}}{{{n}}}"
            if coded:
                mean_row += rf" + {format_sf(p.a, 6)}"
            return [
                (rf"{sx} = {format_sf(p.sum_x, 8)},\ {sx2} = {format_sf(p.sum_x2, 8)}", None),
                (rf"{mean_row} = {format_sf(self.mean, 4)}", style.RUN_COLOUR),
                (
                    rf"s^2 = \frac{{1}}{{{n - 1}}}\left({format_sf(p.sum_x2, 8)}"
                    rf" - \frac{{{format_sf(p.sum_x, 8)}^2}}{{{n}}}\right)",
                    None,
                ),
                (rf"s^2 = {format_sf(self.s2, 4)}", style.HIGHLIGHT_COLOUR),
            ]
        if p.kind == "sample_mean":
            mu, sigma, se = format_sf(p.mu, 6), format_sf(p.sigma, 6), format_sf(self.se, 4)
            rows = [
                (
                    rf"\bar X \sim N\!\left({mu},\ \frac{{{sigma}^2}}{{{n}}}\right)"
                    + ("" if p.normal_population else r"\ \text{approx. (CLT)}"),
                    None,
                ),
                (
                    rf"\sqrt{{\frac{{{sigma}^2}}{{{n}}}}} = {se}",
                    None,
                ),
            ]
            for v, z in zip((p.low, p.high), self.zs, strict=True):
                if v is not None:
                    rows.append(
                        (
                            rf"z = \frac{{{format_sf(v, 6)} - {mu}}}{{{se}}}"
                            rf" = {z:.3f}",
                            None,
                        )
                    )
            rows.append(
                (rf"{self._event()} = {format_sf(self.probability, 4)}", style.HIGHLIGHT_COLOUR)
            )
            return rows
        lo, hi = self.interval
        z_row = rf"\Phi(z) = {format_sf(0.5 * (1 + p.level / 100), 6)} \Rightarrow z = {self.z:.3f}"
        if p.kind == "mean_interval":
            return [
                (
                    rf"\text{{s.e.}} = \frac{{{format_sf(p.sigma, 6)}}}{{\sqrt{{{n}}}}}"
                    rf" = {format_sf(self.se, 4)}",
                    None,
                ),
                (z_row, None),
                (
                    rf"{format_sf(p.mean, 6)} \pm {self.z:.3f}\times {format_sf(self.se, 4)}",
                    None,
                ),
                (rf"({format_sf(lo, 4)},\ {format_sf(hi, 4)})", style.HIGHLIGHT_COLOUR),
            ]
        return [
            (
                rf"\hat p = \frac{{{p.successes}}}{{{n}}} = {format_sf(self.p_hat, 4)}",
                style.RUN_COLOUR,
            ),
            (
                rf"\text{{s.e.}} = \sqrt{{\frac{{{format_sf(self.p_hat, 4)}\times "
                rf"{format_sf(1 - self.p_hat, 4)}}}{{{n}}}}} = {format_sf(self.se, 4)}",
                None,
            ),
            (z_row, None),
            (rf"({format_sf(lo, 4)},\ {format_sf(hi, 4)})", style.HIGHLIGHT_COLOUR),
        ]


def _interval_line(w: _Work) -> dict:
    """The estimate as a dot on a number line, with the interval (or one s either side) as a bar."""
    area = style.region_box(style.GRAPH_REGION).shrink(style.PADDING)
    lo, hi = w.interval
    width = hi - lo
    start, stop, step = axis_range([lo - width * 0.6, hi + width * 0.6], ticks=6, origin=False)
    line = NumberLine(
        x_range=[start, stop, step],
        length=area.width - 0.6,
        include_numbers=True,
        font_size=24,
        decimal_number_config={"num_decimal_places": _places(step)},
    )
    line.move_to([area.center[0], area.center[1] - 0.6, 0])
    y = line.get_center()[1] + 0.7
    left, right = line.n2p(lo), line.n2p(hi)
    bar = VGroup(
        Line([left[0], y, 0], [right[0], y, 0], color=style.RUN_COLOUR, stroke_width=6),
        Line([left[0], y - 0.2, 0], [left[0], y + 0.2, 0], color=style.RUN_COLOUR, stroke_width=4),
        Line(
            [right[0], y - 0.2, 0], [right[0], y + 0.2, 0], color=style.RUN_COLOUR, stroke_width=4
        ),
        label(format_sf(lo, 4), colour=style.RUN_COLOUR, size=24).next_to(
            [left[0], y + 0.2, 0], [0, 1, 0], buff=0.08
        ),
        label(format_sf(hi, 4), colour=style.RUN_COLOUR, size=24).next_to(
            [right[0], y + 0.2, 0], [0, 1, 0], buff=0.08
        ),
    )
    centre = line.n2p(w.centre)
    estimate = {
        "estimates": r"\bar x",
        "mean_interval": r"\bar x",
        "proportion_interval": r"\hat p",
    }[w.params.kind]
    marks = VGroup(
        Dot([centre[0], y, 0], color=style.HIGHLIGHT_COLOUR, radius=0.09),
        DashedLine([centre[0], y, 0], centre, color=style.HIGHLIGHT_COLOUR, stroke_width=2),
        label(estimate, colour=style.HIGHLIGHT_COLOUR, size=28)
        .next_to([centre[0], y, 0], [0, -1, 0], buff=0.15)
        .shift([0.25, 0, 0]),
    )
    note = (
        r"\bar x \pm s"
        if w.params.kind == "estimates"
        else rf"{format_sf(w.params.level, 6)}\%\ \text{{interval}}"
    )
    return {
        "axes": line,
        "x_label": label(note, colour=style.RUN_COLOUR, size=26).next_to(bar, [0, 1, 0], buff=0.5),
        "title": text_line(
            w.title_latex(), style.title_lines(style.graph_boxes(style.GRAPH_REGION)[0])[0]
        ),
        "curve": VGroup(),
        "area": bar,
        "marks": marks,
        "answer": text_line(
            w.answer_latex(),
            style.title_lines(style.graph_boxes(style.GRAPH_REGION)[0])[1],
            colour=style.HIGHLIGHT_COLOUR,
        ),
    }


def _places(step: float) -> int:
    return max(0, -math.floor(math.log10(step) + 1e-9)) if step < 1 else 0


def _two_curves(w: _Work) -> dict:
    """The population and the sample mean on one axis: the sample mean's curve is √n narrower."""
    p = w.params
    mu, sigma, se = p.mu, p.sigma, w.se
    # a normal population is drawn faintly behind; otherwise only the sample mean is normal
    reach = 3.5 * sigma if p.normal_population else 4.5 * se
    lo, hi = mu - reach, mu + reach
    peak = 1 / (se * math.sqrt(2 * math.pi))
    plot = make_plot(
        style.GRAPH_REGION, [lo, hi], [0, peak * 1.15], origin=False, y_ticks=4, y_label=""
    )
    plot.axes.y_axis.set_opacity(0)

    def population(x):
        return math.exp(-((x - mu) ** 2) / (2 * sigma**2)) / (sigma * math.sqrt(2 * math.pi))

    def sample(x):
        return peak * math.exp(-((x - mu) ** 2) / (2 * se**2))

    a = max(p.low, lo) if p.low is not None else lo
    b = min(p.high, hi) if p.high is not None else hi
    xs = np.linspace(a, b, 120)
    outline = [plot.point(a, 0)] + [plot.point(x, sample(x)) for x in xs] + [plot.point(b, 0)]
    curves = VGroup(curve(plot, sample, lo, hi))
    marks = VGroup(
        label(r"\bar X", colour=style.CURVE_COLOUR, size=26).next_to(
            plot.point(mu + se, sample(mu + se)), [1, 0.3, 0], buff=0.1
        )
    )
    if p.normal_population:
        curves.add(curve(plot, population, lo, hi).set_stroke(style.TEXT_COLOUR, opacity=0.6))
        tip = plot.point(mu + 1.2 * sigma, population(mu + 1.2 * sigma))
        marks.add(label("X", colour=style.TEXT_COLOUR, size=26).next_to(tip, [1, 1, 0], buff=0.08))
    return {
        "axes": plot.axes,
        "x_label": plot.x_label,
        "title": text_line(w.title_latex(), plot.upper),
        "curve": curves,
        "area": Polygon(*outline, stroke_width=0, fill_color=style.AREA_COLOUR, fill_opacity=0.55),
        "marks": marks,
        "answer": text_line(w.answer_latex(), plot.lower, colour=style.HIGHLIGHT_COLOUR),
    }


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
