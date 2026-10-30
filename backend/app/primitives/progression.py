"""Progression: arithmetic and geometric progressions as bars, their nth term, the sum of the
first n terms, and the sum to infinity of a convergent geometric progression (9709 1.6).

An arithmetic progression adds d each time: uₙ = a + (n − 1)d. Its sum is seen by writing the
terms forwards and backwards: each pair adds to a + l, so 2Sₙ = n(a + l). A geometric
progression multiplies by r: uₙ = arⁿ⁻¹, Sₙ = a(1 − rⁿ)/(1 − r). When |r| < 1 the terms shrink
and the partial sums close in on S∞ = a/(1 − r), drawn as a line the bars approach. Every value
is exact (SymPy), with 3 significant figures where a fraction would be unwieldy.
"""

from typing import Annotated, Literal

import sympy as sp
from manim import DashedLine, Rectangle, SurroundingRectangle, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import label, make_plot, place_label, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_value, latex_value

MAX_BARS = 20
PAIRED_BARS = 10
LIMIT = 10**6


class ProgressionParams(PrimitiveParams):
    kind: Literal["arithmetic", "geometric"]
    a: Annotated[float, Field(ge=-1000, le=1000)] = Field(description="The first term")
    d: Annotated[float, Field(ge=-1000, le=1000)] = Field(
        default=0, description="Arithmetic: the common difference"
    )
    r: Annotated[float, Field(ge=-10, le=10)] = Field(
        default=1, description="Geometric: the common ratio"
    )
    find: Literal["nth_term", "sum", "sum_to_infinity"]
    n: Annotated[int, Field(ge=1, le=100)] = Field(
        default=10, description="The term number, or how many terms to add"
    )


class Progression(StagedPrimitive[ProgressionParams]):
    primitive_id = "Progression"
    version = "1"
    topic = "Series"
    params_model = ProgressionParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[
            ("axes", "*"),
            ("bars", "*"),
            ("reversed", "*"),
            ("pair_box", "*"),
            ("limit_line", "*"),
            ("highlight", "*"),
        ],
    )

    def default_params(self) -> ProgressionParams:
        return ProgressionParams(kind="arithmetic", a=3, d=2, find="sum", n=8)

    def validate(self, params: ProgressionParams) -> list[PredicateFailure]:
        if params.kind == "geometric":
            if params.a == 0 or params.r == 0:
                return [
                    _failure("nonzero", "a geometric progression needs a and r not 0", "a", "r")
                ]
            if params.find == "sum" and params.r == 1:
                return [_failure("ratio_not_one", "with r = 1 the sum is just na", "r")]
            if params.find == "sum_to_infinity" and abs(params.r) >= 1:
                message = "a sum to infinity exists only when -1 < r < 1"
                return [_failure("convergent", message, "r")]
        elif params.find == "sum_to_infinity":
            message = "an arithmetic progression has no sum to infinity (unless every term is 0)"
            return [_failure("convergent", message, "kind", "find")]
        if params.find != "sum_to_infinity" and params.n < 2:
            return [_failure("enough_terms", "n must be at least 2", "n")]
        p = _Progression(params)
        if any(abs(v) > LIMIT for v in [*p.terms, p.answer]):
            return [_failure("values_fit", "the terms grow too large to draw", "n", "r")]
        return []

    def computed_values(self, params: ProgressionParams) -> dict[str, str]:
        p = _Progression(params)
        return {"answer": format_value(p.answer), "last_bar": format_value(p.heights[-1])}

    def build(self, params: ProgressionParams, level):
        p = _Progression(params)
        heights = p.heights
        m = len(heights)
        pairing = p.pairing()
        top = [h + rh for h, rh in zip(heights, reversed(heights), strict=True)] if pairing else []
        values = [*heights, *top]
        if params.find == "sum_to_infinity":
            values.append(float(p.answer))
        plot = make_plot(
            style.GRAPH_REGION,
            [0.5, m + 0.5],
            values,
            x_label="n",
            y_label=r"S_n" if p.partial else r"u_n",
            x_axis=(0, m + 1, 1 if m <= 10 else 2),
            y_ticks=5,
        )
        width = plot.point(1, 0)[0] - plot.point(0, 0)[0]
        bars = VGroup()
        for i, h in enumerate(heights, start=1):
            bars.add(_bar(plot, i, 0, h, width, style.CURVE_COLOUR))
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "bars": bars,
            "title": text_line(p.title_latex(), plot.upper),
        }
        if pairing:
            parts["reversed"] = VGroup(
                *(
                    _bar(plot, i, h, h + rh, width, style.RUN_COLOUR)
                    for i, (h, rh) in enumerate(zip(heights, reversed(heights), strict=True), 1)
                )
            )
            parts["pair_box"] = SurroundingRectangle(
                VGroup(bars, parts["reversed"]), color=style.HIGHLIGHT_COLOUR, buff=0.02
            )
            parts["pair_label"] = place_label(
                label(rf"a + l = {latex_value(top[0])}", colour=style.HIGHLIGHT_COLOUR),
                parts["pair_box"].get_top(),
                plot.plot_box,
                plot.obstacles(),
                [],
                wide=True,
            )
        if params.find == "nth_term" and params.n <= m:
            parts["highlight"] = SurroundingRectangle(
                bars[params.n - 1], color=style.HIGHLIGHT_COLOUR, buff=0.04
            )
        if params.find == "sum_to_infinity":
            y = float(p.answer)
            parts["limit_line"] = DashedLine(
                plot.point(plot.x_range[0], y),
                plot.point(plot.x_range[1], y),
                color=style.TANGENT_COLOUR,
                stroke_width=3,
            )
            parts["limit_label"] = place_label(
                label(rf"S_\infty = {latex_value(p.answer)}", colour=style.TANGENT_COLOUR),
                plot.point(plot.x_range[1], y),
                plot.plot_box,
                [*plot.obstacles(), bars],
                [],
                wide=True,
            )
        parts["answer"] = text_line(p.answer_latex(), plot.lower, colour=style.HIGHLIGHT_COLOUR)
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        rows = p.rows()
        texts = stack_lines([t for t, _ in rows], box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: ProgressionParams, level) -> list[Stage]:
        p = _Progression(params)
        rows = [f"row_{i}" for i in range(1, len(p.rows()) + 1)]
        kind = "adds the same difference" if params.kind == "arithmetic" else "multiplies by r"
        bars_words = (
            "Each bar is the sum so far, a partial sum"
            if p.partial
            else f"Each term {kind} each time"
        )
        steps = [
            stage("axes", "Draw the axes", 1.5, ["axes", "x_label", "y_label", "title"]),
            stage("bars", bars_words, 3.0, ["bars", rows[0]]),
        ]
        if params.find == "nth_term":
            shown = ["highlight"] if params.n <= len(p.heights) else []
            steps.append(
                stage(
                    "formula",
                    f"Term n: start at a and {kind} n minus 1 times",
                    3.0,
                    [*rows[1:], *shown],
                )
            )
        elif p.pairing():
            steps += [
                stage(
                    "reverse",
                    "Write the terms again in reverse, on top: each pair adds to first plus last",
                    3.5,
                    ["reversed", "pair_box", "pair_label"],
                ),
                stage(
                    "formula",
                    "That rectangle is twice the sum: n pairs of a plus l, halved",
                    3.0,
                    rows[1:],
                ),
            ]
        else:
            words = (
                "The partial sums close in on a limit: the sum to infinity"
                if params.find == "sum_to_infinity"
                else "Use the formula for the sum of the first n terms"
            )
            limit = ["limit_line", "limit_label"] if params.find == "sum_to_infinity" else []
            steps.append(stage("formula", words, 3.5, [*limit, *rows[1:]]))
        steps.append(stage("answer", "So", 1.5, ["answer"], emphasise=["answer"]))

        def standard(s):
            return [combine("bars", s[1].description, 3.0, *s[:2]), *s[2:]]

        def concise(s):
            out = standard(s)
            return [out[0], combine("formula", out[1].description, 4.0, *out[1:])]

        return by_level(level, steps, standard, concise)


class _Progression:
    def __init__(self, params: ProgressionParams):
        self.params = params
        self.a = exact(params.a)
        self.d, self.r = exact(params.d), exact(params.r)
        n = params.n
        self.partial = params.find == "sum_to_infinity" or (
            params.find == "sum" and params.kind == "geometric"
        )
        count = min(n, MAX_BARS) if params.find != "sum_to_infinity" else 10
        self.terms = [self.term(k) for k in range(1, count + 1)]
        if self.partial:
            running, self.heights = 0, []
            for t in self.terms:
                running += t
                self.heights.append(float(running))
        else:
            self.heights = [float(t) for t in self.terms]
        self.answer = self._answer()

    def term(self, k: int) -> sp.Rational:
        if self.params.kind == "arithmetic":
            return self.a + (k - 1) * self.d
        return self.a * self.r ** (k - 1)

    def _answer(self):
        n, a = self.params.n, self.a
        if self.params.find == "nth_term":
            return self.term(n)
        if self.params.find == "sum_to_infinity":
            return a / (1 - self.r)
        if self.params.kind == "arithmetic":
            return sp.Rational(n, 2) * (2 * a + (n - 1) * self.d)
        return a * (1 - self.r**n) / (1 - self.r)

    def pairing(self) -> bool:
        return (
            self.params.kind == "arithmetic"
            and self.params.find == "sum"
            and self.params.n <= PAIRED_BARS
            and all(t > 0 for t in self.terms)
        )

    def title_latex(self) -> str:
        shown = ",\\ ".join(latex_value(t) for t in self.terms[:4])
        return rf"{shown},\ \dots"

    def answer_latex(self) -> str:
        n = self.params.n
        name = {"nth_term": f"u_{{{n}}}", "sum": f"S_{{{n}}}", "sum_to_infinity": r"S_\infty"}
        return rf"{name[self.params.find]} = {_value(self.answer)}"

    def rows(self) -> list[tuple[str, object]]:
        a, n = latex_value(self.a), self.params.n
        if self.params.kind == "arithmetic":
            d = latex_value(self.d)
            rows = [(rf"a = {a},\ d = {d}", None)]
            if self.params.find == "nth_term":
                rows += [
                    (r"u_n = a + (n - 1)d", None),
                    (rf"u_{{{n}}} = {a} + {n - 1} \times {_bracket(self.d)}", None),
                ]
            else:
                last = self.term(n)
                rows += [
                    (r"S_n = \frac{n}{2}\left(a + l\right)", None),
                    (
                        rf"l = u_{{{n}}} = {a} + {n - 1} \times {_bracket(self.d)} = "
                        + latex_value(last),
                        None,
                    ),
                    (rf"S_{{{n}}} = \frac{{{n}}}{{2}}\left({a} + {_bracket(last)}\right)", None),
                ]
        else:
            r = latex_value(self.r)
            rows = [(rf"a = {a},\ r = {r}", None)]
            if self.params.find == "nth_term":
                rows += [
                    (r"u_n = ar^{n - 1}", None),
                    (rf"u_{{{n}}} = {a} \times {_power_base(self.r)}^{{{n - 1}}}", None),
                ]
            elif self.params.find == "sum":
                rows += [
                    (r"S_n = \frac{a(1 - r^n)}{1 - r}", None),
                    (
                        rf"S_{{{n}}} = \frac{{{a}\left(1 - {_power_base(self.r)}^{{{n}}}\right)}}"
                        rf"{{1 - {_bracket(self.r)}}}",
                        None,
                    ),
                ]
            else:
                rows += [
                    (
                        rf"|r| = {latex_value(abs(self.r))} < 1\text{{: it converges}}",
                        style.RISE_COLOUR,
                    ),
                    (r"S_\infty = \frac{a}{1 - r}", None),
                    (rf"S_\infty = \frac{{{a}}}{{1 - {_bracket(self.r)}}}", None),
                ]
        rows.append((rf"= {_value(self.answer)}", style.HIGHLIGHT_COLOUR))
        return rows


def _value(value) -> str:
    value = sp.nsimplify(value)
    if isinstance(value, sp.Rational) and value.q > 100:
        return rf"\frac{{{value.p}}}{{{value.q}}} \approx {format_value(float(value))}"
    return latex_value(value)


def _power_base(value) -> str:
    """r as the base of a power: bracketed unless it is a positive whole number."""
    value = sp.nsimplify(value)
    return (
        latex_value(value)
        if value > 0 and value.is_integer
        else rf"\left({latex_value(value)}\right)"
    )


def _bracket(value) -> str:
    return rf"\left({latex_value(value)}\right)" if value < 0 else latex_value(value)


def _bar(plot, i: int, bottom: float, top: float, width: float, colour) -> Rectangle:
    lo, hi = plot.point(i, bottom), plot.point(i, top)
    bar = Rectangle(
        width=0.7 * width,
        height=max(abs(hi[1] - lo[1]), 1e-3),
        stroke_width=1.5,
        stroke_color=colour,
        fill_color=colour,
        fill_opacity=0.55,
    )
    return bar.move_to((lo + hi) / 2)


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
