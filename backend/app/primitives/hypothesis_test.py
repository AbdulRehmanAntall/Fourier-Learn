"""HypothesisTest: a significance test drawn as the distribution under the null hypothesis with
its critical region shaded and the observed value marked: a test for a binomial proportion p, a
Poisson mean λ, or a population mean μ using the sample mean, one-tailed or two-tailed, with the
probabilities of Type I and Type II errors (9709 6.5).

H₀ fixes the parameter; H₁ says it is smaller, larger, or different. Under H₀ the test statistic
has a known distribution: B(n, p₀), Po(λ₀), or N(μ₀, σ²/n) for the mean of a sample of n (normal
population, or a large sample by the Central Limit Theorem). The p-value is the probability, under
H₀, of a result at least as extreme as the one observed; H₀ is rejected when it is at most the
significance level (half of it in each tail of a two-tailed test). The critical region is the set
of results that would reject H₀. For a discrete statistic its actual probability under H₀, the
probability of a Type I error, is at most the stated level; a Type II error, accepting a false
H₀, has the probability of the acceptance region under an alternative value. Probabilities are to
4 significant figures.
"""

import math
from typing import Annotated, Literal

import numpy as np
from manim import DashedLine, Polygon, Rectangle, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.normal_distribution import phi, phi_inverse
from app.primitives.plotting import curve, label, make_plot, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf

MAX_BARS = 31
SYMBOL = {"binomial": "p", "poisson": r"\lambda", "normal_mean": r"\mu"}


class HypothesisTestParams(PrimitiveParams):
    kind: Literal["binomial", "poisson", "normal_mean"]
    null_value: Annotated[float, Field(ge=-10_000, le=10_000)] = Field(
        description="The parameter under H0: p, λ or μ"
    )
    tail: Literal["lower", "upper", "two"] = Field(description="H1: smaller, larger or different")
    significance: Annotated[float, Field(gt=0, lt=50)] = Field(
        default=5, description="The significance level, in percent"
    )
    observed: Annotated[float, Field(ge=-10_000, le=10_000)] = Field(
        description="The observed count (binomial, Poisson) or sample mean (normal_mean)"
    )
    n: Annotated[int, Field(ge=1, le=10_000)] | None = Field(
        default=None, description="binomial: the trials; normal_mean: the sample size"
    )
    sigma: Annotated[float, Field(gt=0, le=10_000)] | None = Field(
        default=None,
        description="normal_mean: the population standard deviation (or its estimate from a "
        "large sample)",
    )
    alternative: Annotated[float, Field(ge=-10_000, le=10_000)] | None = Field(
        default=None, description="A true value of the parameter, for P(Type II error)"
    )


class HypothesisTest(StagedPrimitive[HypothesisTestParams]):
    primitive_id = "HypothesisTest"
    version = "1"
    topic = "Hypothesis tests"
    params_model = HypothesisTestParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[("axes", "*"), ("curve", "*"), ("region", "*"), ("observed", "*")],
    )

    def default_params(self) -> HypothesisTestParams:
        return HypothesisTestParams(kind="binomial", null_value=0.3, tail="lower", observed=2, n=20)

    def validate(self, params: HypothesisTestParams) -> list[PredicateFailure]:
        kind, value = params.kind, params.null_value
        if kind == "binomial":
            if params.n is None or params.n > 30:
                return [_failure("trials_given", "give n, at most 30", "n")]
            if not 0 < value < 1:
                return [_failure("probability_range", "p must be between 0 and 1", "null_value")]
            if params.alternative is not None and not 0 < params.alternative < 1:
                return [_failure("probability_range", "p must be between 0 and 1", "alternative")]
        if kind == "poisson" and not 0 < value <= 20:
            return [_failure("mean_range", "λ must be positive, at most 20", "null_value")]
        if kind == "poisson" and params.alternative is not None and params.alternative <= 0:
            return [_failure("mean_range", "λ must be positive", "alternative")]
        if kind in ("binomial", "poisson"):
            top = params.n if kind == "binomial" else 60
            if params.observed != int(params.observed) or not 0 <= params.observed <= top:
                message = "the observed value must be a possible count"
                return [_failure("whole_count", message, "observed")]
        if kind == "normal_mean" and (params.n is None or params.sigma is None):
            return [_failure("sample_given", "give the sample size and sigma", "n", "sigma")]
        if params.alternative is not None and params.alternative == value:
            message = "the alternative value must differ from the null value"
            return [_failure("alternative_differs", message, "alternative")]
        test = _Test(params)
        if params.tail != "two" and params.alternative is not None:
            wrong = (
                (params.alternative > value)
                if params.tail == "lower"
                else (params.alternative < value)
            )
            if wrong:
                message = "the alternative value must lie on the side H1 claims"
                return [_failure("alternative_side", message, "alternative")]
        if kind != "normal_mean" and not test.region:
            message = "no result is extreme enough to reject H0 at this level"
            return [_failure("critical_region_exists", message, "significance", "n")]
        return []

    def computed_values(self, params: HypothesisTestParams) -> dict[str, str]:
        test = _Test(params)
        values = {
            "p_value": format_sf(test.p_value, 4),
            "decision": "reject" if test.reject else "accept",
            "critical_region": test.region_text(),
            "type_1": format_sf(test.type_1, 4),
        }
        if params.kind == "normal_mean":
            values["z"] = f"{test.z:.3f}"
        if test.type_2 is not None:
            values["type_2"] = format_sf(test.type_2, 4)
        return values

    def build(self, params: HypothesisTestParams, level):
        test = _Test(params)
        if params.kind == "normal_mean":
            parts = _normal_plot(test)
        else:
            parts = _bar_plot(test)
        rows = test.rows()
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: HypothesisTestParams, level) -> list[Stage]:
        test = _Test(params)
        rows = [f"row_{i}" for i in range(1, len(test.rows()) + 1)]
        errors = 1 + (test.type_2 is not None)
        steps = [
            stage(
                "hypotheses",
                "State the hypotheses, and the distribution if the null hypothesis is true",
                3.5,
                ["axes", "x_label", "title", "curve", *rows[:3]],
            ),
            stage(
                "region",
                "Shade the results extreme enough to reject the null hypothesis",
                3.5,
                ["region", rows[3]],
            ),
            stage(
                "compare",
                "Find how likely a result at least this extreme is, and compare with the level",
                3.5,
                ["observed", *rows[4 : -2 - errors]],
            ),
            stage(
                "conclude",
                "Conclude in context, with the level of significance",
                3.0,
                [*rows[-2 - errors : -errors], "answer"],
                emphasise=["answer"],
            ),
            stage(
                "errors",
                "A Type I error rejects a true null hypothesis; Type II accepts a false one",
                3.5,
                rows[-errors:],
            ),
        ]

        def standard(s):
            return [
                s[0],
                combine("region", "Critical region and the observed result", 4.5, s[1], s[2]),
                s[3],
                s[4],
            ]

        def concise(s):
            return [s[0], combine("test", "Carry out the test", 5.0, s[1], s[2], s[3]), s[4]]

        return by_level(level, steps, standard, concise)


class _Test:
    def __init__(self, params: HypothesisTestParams):
        self.params = params
        self.alpha = params.significance / 100
        kind, tail = params.kind, params.tail
        if kind == "normal_mean":
            self.se = params.sigma / math.sqrt(params.n)
            self.z = (params.observed - params.null_value) / self.se
            self.z_crit = phi_inverse(1 - (self.alpha / 2 if tail == "two" else self.alpha))
            side = tail if tail != "two" else ("lower" if self.z < 0 else "upper")
            self.side = side
            one = phi(self.z) if side == "lower" else 1 - phi(self.z)
            self.p_value = one
            self.reject = one <= (self.alpha / 2 if tail == "two" else self.alpha)
            self.type_1 = self.alpha
            self.bounds = self._normal_bounds()
            self.region = True
            self.type_2 = self._normal_type_2()
            return
        top = params.n if kind == "binomial" else _poisson_top(params.null_value, params.observed)
        self.support = list(range(0, top + 1))
        self.pmf = [self._pmf(params.null_value, x) for x in self.support]
        expected = params.n * params.null_value if kind == "binomial" else params.null_value
        observed = int(params.observed)
        side = tail if tail != "two" else ("lower" if observed < expected else "upper")
        self.side = side
        if side == "lower":
            self.p_value = sum(self.pmf[: observed + 1])
        else:
            self.p_value = 1 - sum(self.pmf[:observed])
        level = self.alpha / 2 if tail == "two" else self.alpha
        self.reject = self.p_value <= level
        self.lower_c = self.upper_c = None
        if tail in ("lower", "two"):
            total = 0.0
            for x, p in zip(self.support, self.pmf, strict=True):
                if total + p > level:
                    break
                total += p
                self.lower_c = x
        if tail in ("upper", "two"):
            self.upper_c = self._upper_critical(level)
        self.region = [x for x in self._full_support() if self.in_region(x)]
        self.type_1 = sum(self._pmf(params.null_value, x) for x in self.region)
        self.type_2 = None
        if params.alternative is not None and self.region:
            self.type_2 = 1 - sum(self._pmf(params.alternative, x) for x in self.region)

    def _full_support(self):
        if self.params.kind == "binomial":
            return range(0, self.params.n + 1)
        return range(0, 200)

    def _upper_critical(self, level):
        """The smallest c with P(X ≥ c) ≤ level, found from the top (or, for the Poisson, up)."""
        null = self.params.null_value
        c = None
        x = self.params.n if self.params.kind == "binomial" else 199
        tail = 0.0
        while x >= 0:
            tail += self._pmf(null, x)
            if tail > level:
                break
            c = x
            x -= 1
        return c

    def _pmf(self, value, x):
        if self.params.kind == "binomial":
            n = self.params.n
            return math.comb(n, x) * value**x * (1 - value) ** (n - x)
        return math.exp(-value + x * math.log(value) - math.lgamma(x + 1))

    def in_region(self, x) -> bool:
        return (self.lower_c is not None and x <= self.lower_c) or (
            self.upper_c is not None and x >= self.upper_c
        )

    def _normal_bounds(self):
        mu, se, zc = self.params.null_value, self.se, self.z_crit
        tail = self.params.tail
        lower = mu - zc * se if tail in ("lower", "two") else None
        upper = mu + zc * se if tail in ("upper", "two") else None
        return lower, upper

    def _normal_type_2(self):
        alt = self.params.alternative
        if alt is None:
            return None
        lower, upper = self.bounds
        hi = phi((upper - alt) / self.se) if upper is not None else 1.0
        lo = phi((lower - alt) / self.se) if lower is not None else 0.0
        return hi - lo

    def region_text(self) -> str:
        p = self.params
        if p.kind == "normal_mean":
            lower, upper = self.bounds
            out = []
            if lower is not None:
                out.append(f"z <= -{self.z_crit:.3f}")
            if upper is not None:
                out.append(f"z >= {self.z_crit:.3f}")
            return " or ".join(out)
        out = []
        if self.lower_c is not None:
            out.append(f"X <= {self.lower_c}")
        if self.upper_c is not None:
            out.append(f"X >= {self.upper_c}")
        return " or ".join(out)

    def region_latex(self) -> str:
        return (
            self.region_text()
            .replace("<=", r"\le")
            .replace(">=", r"\ge")
            .replace(" or ", r"\ \text{or}\ ")
        )

    def distribution_latex(self) -> str:
        p = self.params
        v = format_sf(p.null_value, 6)
        if p.kind == "binomial":
            return rf"X \sim B({p.n},\ {v})"
        if p.kind == "poisson":
            return rf"X \sim \mathrm{{Po}}({v})"
        return rf"\bar X \sim N\!\left({v},\ \tfrac{{{format_sf(p.sigma, 6)}^2}}{{{p.n}}}\right)"

    def hypotheses(self) -> tuple[str, str]:
        p = self.params
        s, v = SYMBOL[p.kind], format_sf(p.null_value, 6)
        sign = {"lower": "<", "upper": ">", "two": r"\ne"}[p.tail]
        return rf"H_0: {s} = {v}", rf"H_1: {s} {sign} {v}"

    def conclusion(self) -> tuple[str, str]:
        p = self.params
        s, v = SYMBOL[p.kind], format_sf(p.null_value, 6)
        level = format_sf(p.significance, 6)
        sign = {"lower": "<", "upper": ">", "two": r"\ne"}[p.tail]
        verdict = r"\text{Reject }H_0" if self.reject else r"\text{Accept }H_0"
        evidence = "Evidence" if self.reject else "No evidence"
        return verdict, rf"\text{{{evidence} at the {level}\% level that }}{s} {sign} {v}"

    def rows(self) -> list[tuple[str, object]]:
        p = self.params
        h0, h1 = self.hypotheses()
        level = self.alpha / 2 if p.tail == "two" else self.alpha
        compare = "<" if self.reject else ">"
        if p.kind == "normal_mean":
            obs = format_sf(p.observed, 6)
            se = rf"\sqrt{{{format_sf(p.sigma, 6)}^2/{p.n}}}"
            tail_p = rf"P(Z {'<' if self.side == 'lower' else '>'} {self.z:.3f})"
            rows = [
                (rf"{h0},\quad {h1}", None),
                (self.distribution_latex(), None),
                (
                    rf"\text{{Level }}{format_sf(p.significance, 6)}\%"
                    + (r"\text{, two-tailed}" if p.tail == "two" else ""),
                    None,
                ),
                (rf"\text{{Critical region: }}{self.region_latex()}", style.RUN_COLOUR),
                (
                    rf"z = \frac{{{obs} - {format_sf(p.null_value, 6)}}}{{{se}}} = {self.z:.3f}",
                    None,
                ),
                (rf"{tail_p} = {format_sf(self.p_value, 4)} {compare} {format_sf(level, 4)}", None),
            ]
        else:
            obs = int(p.observed)
            relation = r"\le" if self.side == "lower" else r"\ge"
            event = rf"P(X {relation} {obs})"
            rows = [
                (rf"{h0},\quad {h1}", None),
                (self.distribution_latex(), None),
                (
                    rf"\text{{Level }}{format_sf(p.significance, 6)}\%"
                    + (r"\text{, two-tailed}" if p.tail == "two" else ""),
                    None,
                ),
                (rf"\text{{Critical region: }}{self.region_latex()}", style.RUN_COLOUR),
                (rf"{event} = {format_sf(self.p_value, 4)} {compare} {format_sf(level, 4)}", None),
            ]
        rows += [(line, style.HIGHLIGHT_COLOUR) for line in self.conclusion()]
        rows.append((rf"P(\text{{Type I}}) = {format_sf(self.type_1, 4)}", None))
        if self.type_2 is not None:
            s = SYMBOL[p.kind]
            rows.append(
                (
                    rf"P(\text{{Type II}} \mid {s} = {format_sf(p.alternative, 6)})"
                    rf" = {format_sf(self.type_2, 4)}",
                    None,
                )
            )
        return rows


def _poisson_top(lam, observed) -> int:
    top = int(observed) + 2
    while top < 200 and math.exp(-lam + top * math.log(lam) - math.lgamma(top + 1)) > 5e-4:
        top += 1
    return max(top, int(lam * 2) + 1)


def _bar_plot(test: _Test) -> dict:
    p = test.params
    shown = list(zip(test.support, test.pmf, strict=True))
    if len(shown) > MAX_BARS:
        keep = [x for x, q in shown if q > 5e-4 or x == int(p.observed) or test.in_region(x)]
        lo, hi = min(keep), max(keep)
        lo = max(lo, hi - MAX_BARS + 1)
        shown = [(x, q) for x, q in shown if lo <= x <= hi]
    xs = [x for x, _ in shown]
    top = max(q for _, q in shown)
    span = max(xs) - min(xs)
    step = 1 if span <= 12 else (2 if span <= 24 else 5)
    start = 0 if min(xs) <= 1 else (min(xs) - 1) // step * step
    plot = make_plot(
        style.GRAPH_REGION,
        [min(xs) - 0.5, max(xs) + 0.5],
        [0, top * 1.1],
        x_label="x",
        y_label=r"P(X = x)",
        x_axis=(start, max(xs) + 1, step),
        y_ticks=5,
        origin=start == 0,
    )
    width = (plot.point(1, 0)[0] - plot.point(0, 0)[0]) * 0.7
    bars, region = VGroup(), VGroup()
    observed = None
    for x, q in shown:
        top_point, bottom = plot.point(x, q), plot.point(x, 0)
        bar = Rectangle(
            width=width,
            height=max(top_point[1] - bottom[1], 1e-3),
            stroke_width=1.5,
            stroke_color=style.CURVE_COLOUR,
            fill_color=style.CURVE_COLOUR,
            fill_opacity=0.35,
        ).move_to((top_point + bottom) / 2)
        bars.add(bar)
        if test.in_region(x):
            region.add(
                bar.copy().set_fill(style.RUN_COLOUR, opacity=0.75).set_stroke(style.RUN_COLOUR)
            )
        if x == int(p.observed):
            observed = VGroup(
                DashedLine(
                    bottom,
                    bottom + [0, max(top_point[1] - bottom[1], 0) + 0.5, 0],
                    color=style.HIGHLIGHT_COLOUR,
                    stroke_width=2,
                ),
                label(rf"x = {x}", colour=style.HIGHLIGHT_COLOUR, size=24).next_to(
                    bottom + [0, max(top_point[1] - bottom[1], 0) + 0.5, 0], [0, 1, 0], buff=0.08
                ),
            )
    return {
        "axes": plot.axes,
        "x_label": plot.x_label,
        "y_label": plot.y_label,
        "title": text_line(test.distribution_latex() + r"\ \text{under } H_0", plot.upper),
        "curve": bars,
        "region": region,
        "observed": observed if observed is not None else VGroup(),
        "answer": text_line(
            r"\text{Reject } H_0" if test.reject else r"\text{Accept } H_0",
            plot.lower,
            colour=style.HIGHLIGHT_COLOUR,
        ),
    }


def _normal_plot(test: _Test) -> dict:
    p = test.params
    mu, se = p.null_value, test.se
    reach = max(4 * se, abs(p.observed - mu) + se)
    lo, hi = mu - reach, mu + reach
    peak = 1 / (se * math.sqrt(2 * math.pi))
    plot = make_plot(
        style.GRAPH_REGION,
        [lo, hi],
        [0, peak * 1.15],
        origin=False,
        y_ticks=4,
        y_label="",
        x_label=r"\bar x",
    )
    plot.axes.y_axis.set_opacity(0)

    def density(x):
        return peak * math.exp(-((x - mu) ** 2) / (2 * se**2))

    def area(a, b):
        xs = np.linspace(a, b, 80)
        outline = [plot.point(a, 0)] + [plot.point(x, density(x)) for x in xs] + [plot.point(b, 0)]
        return Polygon(*outline, stroke_width=0, fill_color=style.RUN_COLOUR, fill_opacity=0.65)

    lower, upper = test.bounds
    region = VGroup()
    if lower is not None and lower > lo:
        region.add(area(lo, lower))
    if upper is not None and upper < hi:
        region.add(area(upper, hi))
    x = p.observed
    observed = VGroup(
        DashedLine(
            plot.point(x, 0),
            plot.point(x, peak * 0.75),
            color=style.HIGHLIGHT_COLOUR,
            stroke_width=2,
        ),
        label(rf"\bar x = {format_sf(x, 6)}", colour=style.HIGHLIGHT_COLOUR, size=24).next_to(
            plot.point(x, peak * 0.75), [0, 1, 0], buff=0.08
        ),
    )
    return {
        "axes": plot.axes,
        "x_label": plot.x_label,
        "title": text_line(test.distribution_latex() + r"\ \text{under } H_0", plot.upper),
        "curve": curve(plot, density, lo, hi),
        "region": region,
        "observed": observed,
        "answer": text_line(
            r"\text{Reject } H_0" if test.reject else r"\text{Accept } H_0",
            plot.lower,
            colour=style.HIGHLIGHT_COLOUR,
        ),
    }


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
