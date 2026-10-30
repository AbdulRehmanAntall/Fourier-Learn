"""LinearCombination: the mean and variance of a linear combination of independent random
variables, such as 3X − 2Y + 5 or X₁ + X₂ + X₃, with each term's share of the variance drawn as a
bar; for normal or Poisson variables, a probability about the combination shaded on its
distribution (9709 6.2).

E(aX + bY + c) = aE(X) + bE(Y) + c always, and for independent X and Y,
Var(aX + bY + c) = a²Var(X) + b²Var(Y): the constant does not spread the values and a negative
coefficient still adds variance, so X − Y varies as much as X + Y. A sum of n independent copies
X₁ + ... + Xₙ has variance nVar(X), while nX has n²Var(X). A linear combination of independent
normal variables is normal, which gives probabilities such as P(X > Y) = P(X − Y > 0); a sum of
independent Poisson variables is Poisson with the sum of the means. Values are to 4 significant
figures where they are not exact.
"""

import math
from typing import Annotated, Literal

import numpy as np
from manim import DashedLine, Polygon, Rectangle, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.normal_distribution import phi
from app.primitives.plotting import axis_range, curve, label, make_plot, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf

Name = Annotated[str, StringConstraints(pattern=r"^[A-Z]$")]
Number = Annotated[float, Field(ge=-10_000, le=10_000)]
COLOURS = [style.CURVE_COLOUR, style.RUN_COLOUR, style.HIGHLIGHT_COLOUR, style.TEXT_COLOUR]


class Term(PrimitiveParams):
    name: Name = Field(description='A capital letter, e.g. "X"')
    mean: Number
    variance: Annotated[float, Field(gt=0, le=1e6)]
    coefficient: Annotated[float, Field(ge=-100, le=100)] = Field(
        default=1, description="The multiple: 3 for 3X, -1 for -X"
    )
    copies: Annotated[int, Field(ge=1, le=20)] = Field(
        default=1, description="Independent copies added: 3 for X1 + X2 + X3"
    )


class LinearCombinationParams(PrimitiveParams):
    terms: list[Term] = Field(min_length=1, max_length=4)
    constant: Number = 0
    distribution: Literal["normal", "poisson", "any"] = Field(
        default="normal", description="What the variables are; any for the mean and variance only"
    )
    low: Number | None = Field(default=None, description="The event P(low < T < high)")
    high: Number | None = Field(default=None, description="Leave out for no upper end")


class LinearCombination(StagedPrimitive[LinearCombinationParams]):
    primitive_id = "LinearCombination"
    version = "1"
    topic = "Linear combinations of random variables"
    params_model = LinearCombinationParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[("axes", "*"), ("curve", "*"), ("area", "*"), ("marks", "*")],
    )

    def default_params(self) -> LinearCombinationParams:
        return LinearCombinationParams(
            terms=[
                Term(name="X", mean=50, variance=16),
                Term(name="Y", mean=45, variance=9, coefficient=-1),
            ],
            low=0,
        )

    def validate(self, params: LinearCombinationParams) -> list[PredicateFailure]:
        names = [t.name for t in params.terms]
        if len(set(names)) != len(names):
            return [_failure("names_distinct", "each variable needs its own letter", "terms")]
        if any(t.coefficient == 0 for t in params.terms):
            return [_failure("coefficient_nonzero", "a coefficient of 0 drops the term", "terms")]
        has_event = params.low is not None or params.high is not None
        if params.low is not None and params.high is not None and params.low >= params.high:
            return [_failure("event_ordered", "low must be below high", "low", "high")]
        if has_event and params.distribution == "any":
            message = "a probability needs the distribution: normal or poisson"
            return [_failure("distribution_known", message, "distribution")]
        if params.distribution == "poisson":
            if params.constant != 0 or any(t.coefficient != 1 for t in params.terms):
                message = "only a plain sum of Poisson variables is Poisson"
                return [_failure("poisson_sum", message, "terms", "constant")]
            if any(t.mean != t.variance or t.mean <= 0 for t in params.terms):
                message = "a Poisson variable's mean and variance are equal"
                return [_failure("poisson_moments", message, "terms")]
            if sum(t.mean * t.copies for t in params.terms) > 40:
                return [_failure("poisson_small", "the total mean must be at most 40", "terms")]
            for v in (params.low, params.high):
                if v is not None and (v != int(v) or v < 0):
                    message = "a Poisson event needs whole numbers"
                    return [_failure("whole_numbers", message, "low", "high")]
        return []

    def computed_values(self, params: LinearCombinationParams) -> dict[str, str]:
        c = _Combination(params)
        values = {"mean": format_sf(c.mean, 6), "variance": format_sf(c.variance, 6)}
        if c.probability is not None:
            values["probability"] = format_sf(c.probability, 4)
        return values

    def build(self, params: LinearCombinationParams, level):
        c = _Combination(params)
        if c.probability is None:
            parts = _variance_bars(c)
        elif params.distribution == "poisson":
            parts = _poisson_plot(c)
        else:
            parts = _normal_plot(c)
        rows = c.rows()
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], box, size=30, colours=[k for _, k in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: LinearCombinationParams, level) -> list[Stage]:
        c = _Combination(params)
        n = len(c.rows())
        rows = [f"row_{i}" for i in range(1, n + 1)]
        steps = [
            stage(
                "combination",
                "The new variable is built from independent ones",
                3.0,
                ["title", rows[0]],
            ),
            stage(
                "mean",
                "Expectations combine just as the variables do",
                3.0,
                [rows[1]],
            ),
            stage(
                "variance",
                "Variances add, with each coefficient squared, even for a difference",
                4.0,
                ["axes", "x_label", "curve", *rows[2 : 3 + c.extra]]
                + (
                    ["y_label"]
                    if params.distribution == "poisson" and c.probability is not None
                    else []
                )
                + (["area", "answer"] if c.probability is None else []),
                emphasise=["answer"] if c.probability is None else [],
            ),
        ]
        if c.probability is not None:
            steps.append(
                stage(
                    "probability",
                    "The combination has a known distribution, so find the probability",
                    4.0,
                    ["area", "marks", *rows[3 + c.extra :], "answer"],
                    emphasise=["answer"],
                )
            )

        def standard(s):
            return list(s)

        def concise(s):
            out = [s[0], combine("moments", "Combine the means and the variances", 5.0, s[1], s[2])]
            return out + s[3:]

        return by_level(level, steps, standard, concise)


class _Combination:
    def __init__(self, params: LinearCombinationParams):
        self.params = params
        terms = params.terms
        self.mean = sum(t.coefficient * t.copies * t.mean for t in terms) + params.constant
        self.shares = [t.coefficient**2 * t.copies * t.variance for t in terms]
        self.variance = sum(self.shares)
        self.sd = math.sqrt(self.variance)
        self.extra = int(any(t.copies > 1 for t in terms))
        self.probability = None
        if params.low is not None or params.high is not None:
            if params.distribution == "poisson":
                lo = int(params.low) if params.low is not None else None
                hi = int(params.high) if params.high is not None else None
                self.event = (lo, hi)
                below = sum(_poisson(self.mean, x) for x in range(0, (hi or 0) + 1))
                upto_low = sum(_poisson(self.mean, x) for x in range(0, lo)) if lo else 0.0
                self.probability = (below if hi is not None else 1.0) - upto_low
            else:
                lo, hi = params.low, params.high
                self.event = (lo, hi)
                self.z = [(v - self.mean) / self.sd if v is not None else None for v in (lo, hi)]
                p_lo = phi(self.z[0]) if lo is not None else 0.0
                p_hi = phi(self.z[1]) if hi is not None else 1.0
                self.probability = p_hi - p_lo

    def term_latex(self, t: Term) -> str:
        if t.copies == 1:
            body = t.name
        elif t.copies <= 4:
            body = " + ".join(f"{t.name}_{i}" for i in range(1, t.copies + 1))
        else:
            body = rf"{t.name}_1 + \dots + {t.name}_{{{t.copies}}}"
        c = abs(t.coefficient)
        if c == 1:
            return body
        return rf"{format_sf(c, 6)}({body})" if t.copies > 1 else rf"{format_sf(c, 6)}{body}"

    def name_latex(self) -> str:
        out = ""
        for i, t in enumerate(self.params.terms):
            sign = "-" if t.coefficient < 0 else ("+" if i else "")
            out += f" {sign} {self.term_latex(t)}" if out or sign == "-" else self.term_latex(t)
        k = self.params.constant
        if k:
            out += f" {'-' if k < 0 else '+'} {format_sf(abs(k), 6)}"
        return out.strip()

    def title_latex(self) -> str:
        d = self.params.distribution
        if d == "normal":
            return rf"T \sim N({format_sf(self.mean, 6)},\ {format_sf(self.variance, 6)})"
        if d == "poisson":
            return rf"T \sim \mathrm{{Po}}({format_sf(self.mean, 6)})"
        return (
            rf"E(T) = {format_sf(self.mean, 6)},\ \mathrm{{Var}}(T) = {format_sf(self.variance, 6)}"
        )

    def event_latex(self) -> str:
        lo, hi = self.event
        if self.params.distribution == "poisson":
            if lo is not None and hi is not None:
                return rf"P({lo} \le T \le {hi})"
            return rf"P(T \le {hi})" if lo is None else rf"P(T \ge {lo})"
        if lo is not None and hi is not None:
            return rf"P({format_sf(lo, 6)} < T < {format_sf(hi, 6)})"
        return rf"P(T < {format_sf(hi, 6)})" if lo is None else rf"P(T > {format_sf(lo, 6)})"

    def rows(self) -> list[tuple[str, object]]:
        p = self.params
        terms = p.terms
        mean_sum = ""
        var_parts = []
        for t in terms:
            k = t.coefficient * t.copies
            m = _bracket_value(t.mean)
            body = m if abs(k) == 1 else rf"{format_sf(abs(k), 6)}\times {m}"
            if k < 0:
                mean_sum += f" - {body}"
            else:
                mean_sum += f" + {body}" if mean_sum else body
            square = (
                "" if abs(t.coefficient) == 1 else rf"{format_sf(abs(t.coefficient), 6)}^2\times "
            )
            copies = "" if t.copies == 1 else rf"{t.copies}\times "
            var_parts.append(rf"{copies}{square}{format_sf(t.variance, 6)}")
        if p.constant:
            mean_sum += f" {'-' if p.constant < 0 else '+'} {format_sf(abs(p.constant), 6)}"
        rows = [
            (rf"T = {self.name_latex()}", None),
            (rf"E(T) = {mean_sum} = {format_sf(self.mean, 6)}", style.RUN_COLOUR),
            (
                rf"\mathrm{{Var}}(T) = {' + '.join(var_parts)} = {format_sf(self.variance, 6)}",
                style.RUN_COLOUR,
            ),
        ]
        if self.extra:
            t = next(t for t in terms if t.copies > 1)
            n = t.copies
            rows.append(
                (
                    rf"{n}\text{{ copies: }}{n}\,\mathrm{{Var}}({t.name}),\ "
                    rf"\text{{not }}{n}^2\,\mathrm{{Var}}({t.name})",
                    None,
                )
            )
        if self.probability is not None:
            rows.append((self.title_latex(), None))
            if p.distribution == "normal":
                for v, z in zip(self.event, self.z, strict=True):
                    if v is not None:
                        rows.append(
                            (
                                rf"z = \frac{{{format_sf(v, 6)} - {format_sf(self.mean, 6)}}}"
                                rf"{{\sqrt{{{format_sf(self.variance, 6)}}}}} = {z:.3f}",
                                None,
                            )
                        )
            rows.append(
                (
                    rf"{self.event_latex()} = {format_sf(self.probability, 4)}",
                    style.HIGHLIGHT_COLOUR,
                )
            )
        return rows


def _bracket_value(v: float) -> str:
    return format_sf(v, 6) if v >= 0 else f"({format_sf(v, 6)})"


def _poisson(lam: float, x: int) -> float:
    return math.exp(-lam + x * math.log(lam) - math.lgamma(x + 1))


def _variance_bars(c: _Combination) -> dict:
    """Each term's share of the variance as a bar: they stack to Var(T)."""
    p = c.params
    names = [rf"{c.term_latex(t)}" for t in p.terms]
    count = len(p.terms)
    _, top, step = axis_range([0, c.variance], ticks=5, origin=True)
    plot = make_plot(
        style.GRAPH_REGION,
        [0, c.variance],
        [0, count + 1],
        x_label=r"\mathrm{Var}",
        y_label="",
        y_ticks=2,
        x_axis=(0, max(top, c.variance), step),
    )
    plot.axes.y_axis.set_opacity(0)
    bars = VGroup()
    start = 0.0
    height = (plot.point(0, 1)[1] - plot.point(0, 0)[1]) * 0.6
    for i, share in enumerate(c.shares):
        y = count - i + 0.5  # the terms above, their total in the bottom row
        left, right = plot.point(start, y), plot.point(start + share, y)
        colour = COLOURS[i % len(COLOURS)]
        bar = Rectangle(
            width=max(right[0] - left[0], 1e-3),
            height=height,
            stroke_color=colour,
            fill_color=colour,
            fill_opacity=0.45,
        ).move_to((left + right) / 2)
        bars.add(bar)
        bars.add(
            label(rf"{names[i]}:\ {format_sf(share, 4)}", colour=colour, size=24).next_to(
                bar, [0, 1, 0], buff=0.06
            )
        )
        start += share
    total = Rectangle(
        width=plot.point(c.variance, 0)[0] - plot.point(0, 0)[0],
        height=height,
        stroke_color=style.HIGHLIGHT_COLOUR,
        fill_color=style.HIGHLIGHT_COLOUR,
        fill_opacity=0.35,
    ).move_to((plot.point(0, 0.5) + plot.point(c.variance, 0.5)) / 2)
    total_label = label(
        rf"\mathrm{{Var}}(T) = {format_sf(c.variance, 4)}", colour=style.HIGHLIGHT_COLOUR, size=26
    )
    if total_label.width > total.width - 0.1:
        total_label.next_to(total, [1, 0, 0], buff=0.1)
    else:
        total_label.move_to(total)
    return {
        "axes": plot.axes,
        "x_label": plot.x_label,
        "title": text_line(rf"T = {c.name_latex()}", plot.upper),
        "curve": bars,
        "area": VGroup(total, total_label),
        "marks": VGroup(),
        "answer": text_line(c.title_latex(), plot.lower, colour=style.HIGHLIGHT_COLOUR),
    }


def _normal_plot(c: _Combination) -> dict:
    mu, sd = c.mean, c.sd
    lo, hi = mu - 4 * sd, mu + 4 * sd
    peak = 1 / (sd * math.sqrt(2 * math.pi))
    plot = make_plot(
        style.GRAPH_REGION,
        [lo, hi],
        [0, peak * 1.15],
        origin=False,
        y_ticks=4,
        y_label="",
        x_label="t",
    )
    plot.axes.y_axis.set_opacity(0)

    def density(x):
        return peak * math.exp(-((x - mu) ** 2) / (2 * sd**2))

    a, b = c.event
    a = max(a, lo) if a is not None else lo
    b = min(b, hi) if b is not None else hi
    xs = np.linspace(a, b, 100)
    outline = [plot.point(a, 0)] + [plot.point(x, density(x)) for x in xs] + [plot.point(b, 0)]
    marks = VGroup()
    for v in c.event:
        if v is not None and lo <= v <= hi:
            marks.add(
                DashedLine(
                    plot.point(v, 0),
                    plot.point(v, density(v)),
                    color=style.HIGHLIGHT_COLOUR,
                    stroke_width=2,
                )
            )
    return {
        "axes": plot.axes,
        "x_label": plot.x_label,
        "title": text_line(rf"T = {c.name_latex()}", plot.upper),
        "curve": curve(plot, density, lo, hi),
        "area": Polygon(*outline, stroke_width=0, fill_color=style.AREA_COLOUR, fill_opacity=0.55),
        "marks": marks,
        "answer": text_line(
            rf"{c.event_latex()} = {format_sf(c.probability, 4)}",
            plot.lower,
            colour=style.HIGHLIGHT_COLOUR,
        ),
    }


def _poisson_plot(c: _Combination) -> dict:
    lam = c.mean
    top = int(lam + 4 * math.sqrt(lam)) + 2
    xs = list(range(0, top + 1))
    ps = [_poisson(lam, x) for x in xs]
    step = 1 if top <= 12 else (2 if top <= 24 else 5)
    plot = make_plot(
        style.GRAPH_REGION,
        [-0.5, top + 0.5],
        [0, max(ps) * 1.1],
        x_label="t",
        y_label="P(T = t)",
        x_axis=(0, top + 1, step),
        y_ticks=5,
    )
    width = (plot.point(1, 0)[0] - plot.point(0, 0)[0]) * 0.7
    bars, area = VGroup(), VGroup()
    lo, hi = c.event
    for x, q in zip(xs, ps, strict=True):
        t, bottom = plot.point(x, q), plot.point(x, 0)
        bar = Rectangle(
            width=width,
            height=max(t[1] - bottom[1], 1e-3),
            stroke_width=1.5,
            stroke_color=style.CURVE_COLOUR,
            fill_color=style.CURVE_COLOUR,
            fill_opacity=0.35,
        ).move_to((t + bottom) / 2)
        bars.add(bar)
        if (lo is None or x >= lo) and (hi is None or x <= hi):
            area.add(
                bar.copy()
                .set_fill(style.HIGHLIGHT_COLOUR, opacity=0.75)
                .set_stroke(style.HIGHLIGHT_COLOUR)
            )
    return {
        "axes": plot.axes,
        "x_label": plot.x_label,
        "y_label": plot.y_label,
        "title": text_line(rf"T = {c.name_latex()}", plot.upper),
        "curve": bars,
        "area": area,
        "marks": VGroup(),
        "answer": text_line(
            rf"{c.event_latex()} = {format_sf(c.probability, 4)}",
            plot.lower,
            colour=style.HIGHLIGHT_COLOUR,
        ),
    }


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
