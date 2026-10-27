"""GrowthDecay: an amount changing by the same percentage each period, compared with simple
interest (4024 1.13.4, 1.17, 2.10.3; PRIMITIVES.md #6).

Compound growth multiplies by (1 + r/100) each period, so the points lie on an exponential curve;
simple interest adds the same amount each period, so its points lie on a straight line. A
negative rate is decay or depreciation. The value after each period is computed exactly by SymPy
and shown to 3 significant figures when it is not a whole number of cents.
"""

from typing import Annotated, Literal

import sympy as sp
from manim import DashedLine, Dot, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import curve, label, make_plot, place_label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_sf, latex_value

N = sp.Symbol("n", real=True)


class GrowthDecayParams(PrimitiveParams):
    initial: Annotated[float, Field(gt=0, le=1_000_000)] = Field(
        description="The amount at the start"
    )
    rate: Annotated[float, Field(gt=-100, le=100)] = Field(
        description="Percentage change per period: 5 for 5% growth, -20 for 20% depreciation"
    )
    periods: Annotated[int, Field(ge=1, le=30)] = Field(description="Number of periods (years)")
    compare_simple: bool = Field(
        default=False, description="Also show simple interest at the same rate"
    )
    unit: Literal["$", "", "people", "kg"] = Field(default="$", description="The amount's unit")


class GrowthDecay(StagedPrimitive[GrowthDecayParams]):
    primitive_id = "GrowthDecay"
    version = "1"
    topic = "Number"
    params_model = GrowthDecayParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("axes", "*"),
            ("curve", "*"),
            ("simple*", "*"),
            ("points", "*"),
            ("guide", "*"),
        ],
    )

    def default_params(self) -> GrowthDecayParams:
        return GrowthDecayParams(initial=1000, rate=5, periods=10, compare_simple=True)

    def validate(self, params: GrowthDecayParams) -> list[PredicateFailure]:
        if params.rate == 0:
            return [
                PredicateFailure(
                    kind="consistency",
                    predicate="rate_nonzero",
                    message="a rate of 0% does not change the amount",
                    parameters=["rate"],
                )
            ]
        if params.compare_simple and params.rate < 0:
            return [
                PredicateFailure(
                    kind="consistency",
                    predicate="simple_needs_growth",
                    message="simple interest is compared with compound growth, not decay",
                    parameters=["compare_simple"],
                )
            ]
        return []

    def computed_values(self, params: GrowthDecayParams) -> dict[str, str]:
        g = _Growth(params)
        values = {
            "multiplier": format_sf(g.multiplier, 4),
            "final": _amount(g.amount(params.periods), params.unit),
            "change": _amount(g.amount(params.periods) - g.p, params.unit),
        }
        for k in range(1, min(params.periods, 3) + 1):
            values[f"after_{k}"] = _amount(g.amount(k), params.unit)
        if params.compare_simple:
            values["simple_final"] = _amount(g.simple(params.periods), params.unit)
        return values

    def build(self, params: GrowthDecayParams, level):
        g = _Growth(params)
        n = params.periods
        heights = [float(g.amount(k)) for k in range(n + 1)]
        if params.compare_simple:
            heights += [float(g.simple(n))]
        money = r"\$" if params.unit == "$" else ""
        after = rf"\text{{ {params.unit}}}" if params.unit not in ("$", "") else ""
        y_label = (
            r"\text{amount}"
            if not params.unit
            else (
                r"\text{amount (\$)}" if params.unit == "$" else rf"\text{{amount ({params.unit})}}"
            )
        )
        plot = make_plot(
            self.layout.region,
            [0, n],
            [0, *heights],
            x_label=r"\text{year}",
            y_label=y_label,
            x_from_zero=True,
        )
        f = sp.lambdify(N, g.formula, "math")
        points = VGroup(
            *(
                Dot(plot.point(k, heights[k]), color=style.POINT_COLOUR, radius=0.06)
                for k in range(n + 1)
            )
        )
        final = plot.point(n, heights[n])
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "formula": text_line(
                rf"A = {latex_value(g.p)} \times {_decimal(g.multiplier)}^{{n}}", plot.upper
            ),
            "multiplier": text_line(
                rf"{'+' if g.r > 0 else '-'}{latex_value(abs(g.r))}\%\ "
                rf"\Rightarrow\ \times {_decimal(g.multiplier)} \text{{ each year}}",
                plot.lower,
            ),
            "points": points,
            "curve": curve(plot, f, 0, n),
            "guide": DashedLine(plot.point(n, 0), final, color=style.TANGENT_COLOUR),
            "answer": text_line(
                rf"\text{{after }} {n} \text{{ years: }} {money}{_amount(g.amount(n), params.unit)}"
                rf"{after}",
                plot.lower,
            ),
        }
        obstacles = [*plot.obstacles(), points]
        paths = [parts["curve"], *plot.axis_lines(), parts["guide"]]
        if params.compare_simple:
            simple = sp.lambdify(N, g.simple_formula, "math")
            parts["simple"] = curve(plot, simple, 0, n, colour=style.RUN_COLOUR)
            paths.append(parts["simple"])
            text = label(r"\text{simple}", colour=style.RUN_COLOUR)
            parts["simple_label"] = place_label(
                text, plot.point(n, float(g.simple(n))), plot.plot_box, obstacles, paths, wide=True
            )
            obstacles.append(text)
        text = label(rf"{money}{_amount(g.amount(n), params.unit)}", colour=style.TANGENT_COLOUR)
        parts["final_label"] = place_label(text, final, plot.plot_box, obstacles, paths, wide=True)
        return parts

    def stages(self, params: GrowthDecayParams, level) -> list[Stage]:
        g = _Growth(params)
        word = "grows" if g.r > 0 else "falls"
        steps = [
            stage(
                "axes",
                "Draw the axes: years across, the amount up",
                1.5,
                ["axes", "x_label", "y_label"],
            ),
            stage(
                "multiplier",
                f"The amount {word} by the same percentage each year: multiply "
                "by the same number each time",
                3.0,
                ["multiplier"],
                emphasise=["multiplier"],
            ),
            stage("points", "Multiply year after year and plot each amount", 3.0, ["points"]),
            stage(
                "curve",
                "The points lie on a curve: the formula raises the multiplier to the power n",
                3.0,
                ["curve", "formula"],
            ),
            stage(
                "answer",
                f"After {params.periods} years",
                2.5,
                ["guide", "final_label"],
                morph=[("multiplier", "answer")],
                emphasise=["final_label"],
            ),
        ]
        if params.compare_simple:
            steps.append(
                stage(
                    "simple",
                    "Simple interest adds the same amount each year: a "
                    "straight line, below the compound curve",
                    3.0,
                    ["simple", "simple_label"],
                )
            )

        def standard(s):
            out = [
                combine("setup", s[1].description, 3.0, s[0], s[1]),
                combine(
                    "growth", "Plot the amounts year by year; they lie on a curve", 3.5, s[2], s[3]
                ),
                s[4],
            ]
            return out + s[5:]

        def concise(s):
            return [
                combine("growth", "Compound growth year by year", 3.5, *s[:4]),
                combine("answer", "The amount at the end", 3.0, *s[4:]),
            ]

        return by_level(level, steps, standard, concise)


class _Growth:
    def __init__(self, params: GrowthDecayParams):
        self.p = exact(params.initial)
        self.r = exact(params.rate)
        self.multiplier = 1 + self.r / 100
        self.formula = self.p * self.multiplier**N
        self.simple_formula = self.p * (1 + self.r * N / 100)

    def amount(self, k: int) -> sp.Expr:
        return self.formula.subs(N, k)

    def simple(self, k: int) -> sp.Expr:
        return self.simple_formula.subs(N, k)


def _amount(value: sp.Expr, unit: str) -> str:
    """Money to the nearest cent, people to a whole number, anything else to 3 s.f."""
    number = float(sp.N(value))
    if unit == "$":
        return f"{number:.2f}"
    if unit == "people":
        return str(round(number))
    return format_sf(number)


def _decimal(value: sp.Expr) -> str:
    """A multiplier as a decimal, as O Level writes it: 1.05, 0.8."""
    return format_sf(value, 6)
