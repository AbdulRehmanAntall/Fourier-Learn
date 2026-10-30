"""StandardDeviation: the mean and standard deviation of data, a frequency table, grouped data, or
from totals Σx and Σx² (or coded totals Σ(x − a) and Σ(x − a)²), with the spread shown as the
band from the mean minus one standard deviation to the mean plus one (9709 5.1).

The mean is Σx ÷ n; the variance is the mean of the squares take away the square of the mean,
Σx²/n − x̄², and the standard deviation is its square root. A frequency table weights each value
by its frequency (Σfx, Σfx²); grouped data use the midpoints. Coding by x − a moves every value
by a: the mean moves by a and the standard deviation does not change. SymPy keeps the
arithmetic exact; answers are to 3 significant figures.
"""

from typing import Annotated, Literal

import sympy as sp
from manim import Dot, Line, NumberLine, Rectangle, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import axis_range, label, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_sf

Number = Annotated[float, Field(ge=-10_000, le=10_000)]
Count = Annotated[int, Field(ge=0, le=1000)]


class StandardDeviationParams(PrimitiveParams):
    kind: Literal["list", "frequency", "grouped", "totals", "coded"]
    data: list[Number] | None = Field(default=None, min_length=2, max_length=20, description="list")
    values: list[Number] | None = Field(
        default=None, min_length=2, max_length=8, description="frequency: the values x"
    )
    bounds: list[Number] | None = Field(
        default=None,
        min_length=3,
        max_length=9,
        description="grouped: class boundaries, e.g. [0, 10, 20, 30]",
    )
    frequencies: list[Count] | None = Field(default=None, min_length=2, max_length=8)
    n: Annotated[int, Field(ge=2, le=10_000)] | None = Field(
        default=None, description="totals, coded"
    )
    sum_x: Annotated[float, Field(ge=-1e7, le=1e7)] | None = Field(
        default=None, description="totals: Σx; coded: Σ(x − a)"
    )
    sum_x2: Annotated[float, Field(ge=0, le=1e9)] | None = Field(
        default=None, description="totals: Σx²; coded: Σ(x − a)²"
    )
    a: Number | None = Field(default=None, description="coded: the a in x − a")


class StandardDeviation(StagedPrimitive[StandardDeviationParams]):
    primitive_id = "StandardDeviation"
    version = "1"
    topic = "Representation of data"
    params_model = StandardDeviationParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[("scale", "*"), ("band", "*"), ("dots", "*"), ("mean_line", "*")],
    )

    def default_params(self) -> StandardDeviationParams:
        return StandardDeviationParams(kind="list", data=[4, 7, 7, 8, 10, 12])

    def validate(self, params: StandardDeviationParams) -> list[PredicateFailure]:
        needs = {
            "list": ["data"],
            "frequency": ["values", "frequencies"],
            "grouped": ["bounds", "frequencies"],
            "totals": ["n", "sum_x", "sum_x2"],
            "coded": ["n", "sum_x", "sum_x2", "a"],
        }[params.kind]
        missing = [k for k in needs if getattr(params, k) is None]
        if missing:
            return [_failure("inputs_given", f"{params.kind} needs {', '.join(missing)}", *missing)]
        if params.kind == "frequency" and len(params.values) != len(params.frequencies):
            return [_failure("one_each", "one frequency per value", "frequencies")]
        if params.kind == "grouped":
            if len(params.bounds) != len(params.frequencies) + 1:
                return [
                    _failure(
                        "one_each",
                        "one frequency per class (bounds has one more entry)",
                        "frequencies",
                    )
                ]
            if any(b2 <= b1 for b1, b2 in zip(params.bounds, params.bounds[1:], strict=False)):
                return [_failure("bounds_increase", "class boundaries must increase", "bounds")]
        if params.kind in ("frequency", "grouped") and sum(params.frequencies) < 2:
            return [
                _failure("enough_data", "the frequencies must add to at least 2", "frequencies")
            ]
        if _Stats(params).variance < 0:
            message = "the totals are impossible: they give a negative variance"
            return [_failure("variance_positive", message, "sum_x", "sum_x2")]
        return []

    def computed_values(self, params: StandardDeviationParams) -> dict[str, str]:
        s = _Stats(params)
        return {
            "mean": format_sf(s.mean),
            "variance": format_sf(s.variance),
            "standard_deviation": format_sf(s.sd),
        }

    def build(self, params: StandardDeviationParams, level):
        s = _Stats(params)
        area = style.region_box(style.GRAPH_REGION).shrink(style.PADDING)
        mean, sd = float(s.mean), float(s.sd)
        points = [float(v) for v in s.points] or [mean - 2 * sd, mean + 2 * sd]
        lo, hi, step = axis_range(
            [min(points), max(points), mean - sd, mean + sd], ticks=8, origin=False
        )
        scale = NumberLine(
            x_range=[lo, hi, step], length=area.width - 0.6, include_numbers=True, font_size=22
        )
        base_y = area.bottom + 1.0
        scale.move_to([area.center[0], base_y, 0])
        parts = {
            "scale": scale,
            "title": text_line(
                s.title_latex(), style.Box(area.left, area.right, area.top - 0.9, area.top)
            ),
        }
        dots = VGroup()
        stacks: dict[float, int] = {}
        for value, count in s.dot_counts():
            for _ in range(min(count, 12)):
                k = stacks.get(value, 0)
                stacks[value] = k + 1
                dots.add(
                    Dot(
                        scale.n2p(value) + [0, 0.3 + 0.24 * k, 0],
                        radius=0.09,
                        color=style.CURVE_COLOUR,
                    )
                )
        parts["dots"] = dots
        top = base_y + 0.3 + 0.24 * max([*stacks.values(), 4]) + 0.3
        x_mean = scale.n2p(mean)[0]
        left, right = scale.n2p(mean - sd)[0], scale.n2p(mean + sd)[0]
        parts["band"] = Rectangle(
            width=right - left,
            height=top - base_y,
            stroke_width=0,
            fill_color=style.AREA_COLOUR,
            fill_opacity=0.3,
        ).move_to([(left + right) / 2, (top + base_y) / 2, 0])
        parts["mean_line"] = Line(
            [x_mean, base_y, 0], [x_mean, top, 0], color=style.HIGHLIGHT_COLOUR, stroke_width=4
        )
        parts["mean_label"] = label(
            rf"\bar{{x}} = {format_sf(s.mean)}", colour=style.HIGHLIGHT_COLOUR, size=28
        ).next_to([x_mean, top, 0], [0, 1, 0], buff=0.1)
        parts["band_label"] = label(
            r"\bar{x} \pm \sigma", colour=style.AREA_COLOUR, size=26
        ).next_to([right, top, 0], [1, 1, 0], buff=0.05)
        rows = s.rows()
        work = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], work, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: StandardDeviationParams, level) -> list[Stage]:
        n = len(_Stats(params).rows())
        steps = [
            stage("data", "The data", 2.5, ["title", "scale", "dots"]),
            stage(
                "sums",
                "Find the totals: the sum and the sum of the squares",
                3.5,
                ["row_1", "row_2"],
            ),
            stage(
                "mean",
                "The mean is the total over n",
                3.0,
                ["row_3", "mean_line", "mean_label"],
                emphasise=["mean_line"],
            ),
            stage(
                "variance",
                "The variance is the mean of the squares take away the square of the mean",
                3.5,
                [f"row_{i}" for i in range(4, n)],
            ),
            stage(
                "sd",
                "Its square root is the standard deviation: much of the data lies within one of "
                "the mean",
                3.5,
                [f"row_{n}", "band", "band_label"],
                emphasise=[f"row_{n}"],
            ),
        ]

        def standard(s):
            return [combine("data", "The data and their totals", 3.5, s[0], s[1]), *s[2:]]

        def concise(s):
            return [
                combine("data", "The data and their totals", 3.5, s[0], s[1]),
                s[2],
                combine("sd", "Variance, then standard deviation", 4.0, s[3], s[4]),
            ]

        return by_level(level, steps, standard, concise)


class _Stats:
    def __init__(self, params: StandardDeviationParams):
        self.params = params
        kind = params.kind
        self.points = []
        self.pairs = []  # (value, frequency)
        if kind == "list":
            self.pairs = [(exact(v), 1) for v in params.data]
        elif kind == "frequency":
            self.pairs = [
                (exact(v), f) for v, f in zip(params.values, params.frequencies, strict=True)
            ]
        elif kind == "grouped":
            b = [exact(v) for v in params.bounds]
            self.pairs = [((b[i] + b[i + 1]) / 2, f) for i, f in enumerate(params.frequencies)]
        if self.pairs:
            self.n = sum(f for _, f in self.pairs)
            self.sx = sum(v * f for v, f in self.pairs)
            self.sx2 = sum(v**2 * f for v, f in self.pairs)
            self.points = [v for v, f in self.pairs if f]
            self.shift = 0
        else:
            self.n = params.n
            self.sx, self.sx2 = exact(params.sum_x), exact(params.sum_x2)
            self.shift = exact(params.a) if kind == "coded" else 0
        coded_mean = self.sx / self.n
        self.variance = sp.nsimplify(self.sx2 / self.n - coded_mean**2)
        self.mean = sp.nsimplify(coded_mean + self.shift)
        self.sd = sp.sqrt(self.variance) if self.variance >= 0 else sp.nan

    def dot_counts(self) -> list[tuple[float, int]]:
        if self.params.kind == "grouped":
            return [(float(v), f) for v, f in self.pairs]
        return [(float(v), f) for v, f in self.pairs]

    def title_latex(self) -> str:
        p = self.params
        if p.kind in ("totals", "coded"):
            name = "x" if p.kind == "totals" else rf"(x - {_num(exact(p.a))})"
            sx, sx2 = _num(self.sx), _num(self.sx2)
            return rf"n = {p.n},\ \Sigma {name} = {sx},\ \Sigma {name}^2 = {sx2}"
        if p.kind == "list":
            return ",\\ ".join(_num(exact(v)) for v in p.data)
        return rf"n = {self.n}"

    def rows(self) -> list[tuple[str, object]]:
        p = self.params
        f = "f" if p.kind in ("frequency", "grouped") else ""
        sx, sx2, n = _num(self.sx), _num(self.sx2), self.n
        mean, variance, sd = format_sf(self.mean), format_sf(self.variance), format_sf(self.sd)
        if p.kind == "coded":
            a = _num(exact(p.a))
            return [
                (rf"\Sigma(x - {a}) = {sx}", None),
                (rf"\Sigma(x - {a})^2 = {sx2}", None),
                (rf"\bar{{x}} = {a} + \frac{{{sx}}}{{{n}}} = {mean}", style.HIGHLIGHT_COLOUR),
                (rf"\sigma^2 = \frac{{{sx2}}}{{{n}}} - \left(\frac{{{sx}}}{{{n}}}\right)^2", None),
                (rf"\sigma^2 = {variance}", None),
                (rf"\sigma = {sd}", style.AREA_COLOUR),
            ]
        mid = r"\ (\text{midpoints})" if p.kind == "grouped" else ""
        return [
            (rf"n = {n},\ \Sigma {f}x = {sx}{mid}", None),
            (rf"\Sigma {f}x^2 = {sx2}", None),
            (rf"\bar{{x}} = \frac{{{sx}}}{{{n}}} = {mean}", style.HIGHLIGHT_COLOUR),
            (rf"\sigma^2 = \frac{{{sx2}}}{{{n}}} - {mean}^2", None),
            (rf"\sigma^2 = {variance}", None),
            (rf"\sigma = {sd}", style.AREA_COLOUR),
        ]


def _num(value) -> str:
    """Data and totals as decimals, the way they are given: 1.2, not 6/5."""
    return format_sf(value, 8)


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
