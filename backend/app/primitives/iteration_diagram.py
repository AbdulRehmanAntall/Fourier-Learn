"""IterationDiagram: a root located by a change of sign, then found by the iteration
xₙ₊₁ = F(xₙ), drawn as a staircase or cobweb between y = F(x) and y = x (9709 2.6, 3.6).

A continuous f that changes sign between a and b has a root between them. Rearranging f(x) = 0
as x = F(x), the root is where y = F(x) meets y = x. Each iteration goes up (or down) to the
curve and across to the line: a staircase when F climbs, a cobweb when it falls. The iterates
close in on the root when the curve is shallow there, and run away when it is steep, so an
iteration may fail to converge. The table gives every iterate to (places + 2) decimal places,
and the root is stated once two iterates agree to the required places.
"""

import math
from typing import Annotated

import sympy as sp
from manim import Dot, Line, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import curve, label, make_plot, place_label, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    exact,
    parse_expression,
    written_latex,
)

X = sp.Symbol("x", real=True)
Coordinate = Annotated[float, Field(ge=-20, le=20)]
MAX_STEPS = 12
RUNAWAY = 15
"""An iterate this far from the start has run away: the iteration does not converge."""


class IterationDiagramParams(PrimitiveParams):
    iteration: str = Field(
        min_length=1, max_length=100, description="F(x) in x_{n+1} = F(x_n), e.g. (x + 5)**(1/3)"
    )
    x0: Coordinate = Field(description="The starting value")
    sign_change: tuple[Coordinate, Coordinate] | None = Field(
        default=None, description="Optionally show f(x) = x - F(x) changes sign between these"
    )
    places: Annotated[int, Field(ge=1, le=4)] = Field(
        default=2, description="Give the root to this many decimal places"
    )


class IterationDiagram(StagedPrimitive[IterationDiagramParams]):
    primitive_id = "IterationDiagram"
    version = "1"
    topic = "Numerical solution of equations"
    params_model = IterationDiagramParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[
            ("axes", "*"),
            ("curve", "*"),
            ("line", "*"),
            ("steps", "*"),
            ("start", "*"),
            ("root", "*"),
        ],
    )

    def default_params(self) -> IterationDiagramParams:
        return IterationDiagramParams(iteration="(x + 5)**(1/3)", x0=2, sign_change=(1, 2))

    def validate(self, params: IterationDiagramParams) -> list[PredicateFailure]:
        try:
            parse_expression(params.iteration, {"x"})
        except ExpressionError as error:
            return [_failure("parsing", "expression_parses", str(error), "iteration")]
        run = _Run(params)
        if any(not math.isfinite(v) for v in run.values):
            message = "an iterate is not a real number: F is not defined there"
            return [_failure("domain", "real_and_finite", message, "iteration", "x0")]
        if params.sign_change is not None:
            a, b = params.sign_change
            if a >= b:
                return [_failure("consistency", "interval_ordered", "give the smaller end first")]
            fa, fb = run.f(a), run.f(b)
            if not (math.isfinite(fa) and math.isfinite(fb)) or fa * fb >= 0:
                message = "x - F(x) does not change sign between these values"
                return [_failure("consistency", "sign_changes", message, "sign_change")]
        return []

    def computed_values(self, params: IterationDiagramParams) -> dict[str, str]:
        run = _Run(params)
        values = {f"x_{i}": run.text(v) for i, v in enumerate(run.values)}
        values["converges"] = "yes" if run.root is not None else "no"
        if run.root is not None:
            values["root"] = f"{run.root:.{params.places}f}"
        return values

    def build(self, params: IterationDiagramParams, level):
        run = _Run(params)
        values = run.values
        lo, hi = min(values), max(values)
        if params.sign_change:
            lo, hi = min(lo, params.sign_change[0]), max(hi, params.sign_change[1])
        pad = max(0.5, 0.3 * (hi - lo))
        x_lo, x_hi = lo - pad, hi + pad
        # the same range on both axes: the curve is cut where it leaves it
        plot = make_plot(style.GRAPH_REGION, [x_lo, x_hi], [x_lo, x_hi], equal=True, origin=False)
        F = sp.lambdify(X, run.F, "math")
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "title": text_line(
                rf"x_{{n+1}} = {written_latex(params.iteration).replace('x', 'x_n')}", plot.upper
            ),
            "curve": curve(plot, F, x_lo, x_hi),
            "line": style.line_in_axes(
                plot.axes,
                (0, 0),
                1,
                plot.x_range,
                plot.y_range,
                color=style.RUN_COLOUR,
                stroke_width=3,
            ),
            "start": Dot(plot.point(values[0], 0), color=style.POINT_COLOUR),
        }
        path = VGroup()
        x = values[0]
        previous = plot.point(x, 0)
        for nxt in values[1:]:
            up = plot.point(x, nxt)
            across = plot.point(nxt, nxt)
            path.add(Line(previous, up, color=style.HIGHLIGHT_COLOUR, stroke_width=2.5))
            path.add(Line(up, across, color=style.HIGHLIGHT_COLOUR, stroke_width=2.5))
            previous, x = across, nxt
        parts["steps"] = path
        obstacles = plot.obstacles()
        paths = [parts["curve"], parts["line"], *plot.axis_lines()]
        for name, text, colour, anchor_x in (
            ("curve_label", rf"y = {written_latex(params.iteration)}", style.CURVE_COLOUR, x_hi),
            ("line_label", "y = x", style.RUN_COLOUR, x_lo),
        ):
            mob = label(text, colour=colour)
            y = min(
                max(F(anchor_x) if name == "curve_label" else anchor_x, plot.y_range[0]),
                plot.y_range[1],
            )
            parts[name] = place_label(
                mob, plot.point(anchor_x, y), plot.plot_box, obstacles, paths, wide=True
            )
            obstacles.append(mob)
        if run.root is not None:
            parts["root"] = Dot(
                plot.point(run.root, run.root), color=style.TANGENT_COLOUR, radius=0.1
            )
        else:
            parts["root"] = Dot(plot.point(values[-1], values[-1]), radius=0.001, fill_opacity=0)
        parts["answer"] = text_line(run.answer_latex(), plot.lower, colour=style.HIGHLIGHT_COLOUR)
        rows = run.rows()
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: IterationDiagramParams, level) -> list[Stage]:
        run = _Run(params)
        sign = 2 if params.sign_change else 0
        table = [f"row_{i}" for i in range(sign + 1, sign + 1 + len(run.values))]
        steps = []
        if sign:
            steps.append(
                stage(
                    "sign",
                    "The sign of f changes between these values, so a root lies between them",
                    3.0,
                    ["row_1", "row_2"],
                )
            )
        steps += [
            stage(
                "graphs",
                "The root is where y equals F of x meets y equals x",
                3.0,
                [
                    "axes",
                    "x_label",
                    "y_label",
                    "title",
                    "curve",
                    "line",
                    "curve_label",
                    "line_label",
                ],
            ),
            stage("start", "Start at the first value", 2.0, ["start", table[0]]),
            stage(
                "iterate",
                "Up to the curve, across to the line, again and again"
                + ("" if run.root is not None else ": the steps move away"),
                4.0,
                ["steps", *table[1:]],
            ),
            stage(
                "answer",
                "Two iterates agree to the required places: that is the root"
                if run.root is not None
                else "The iteration does not converge: try another rearrangement",
                3.0,
                ["root", "answer", f"row_{sign + len(run.values) + 1}"],
                emphasise=["answer"],
            ),
        ]

        def standard(s):
            return list(s)

        def concise(s):
            head = s[:-3]
            return [*head, combine("iterate", s[-2].description, 4.0, s[-3], s[-2]), s[-1]]

        return by_level(level, steps, standard, concise)


class _Run:
    def __init__(self, params: IterationDiagramParams):
        self.params = params
        self.F = sp.nsimplify(parse_expression(params.iteration, {"x"}), rational=True)
        numeric = sp.lambdify(X, self.F, "math")

        def F(x):
            try:
                value = complex(numeric(x))
            except (ValueError, ZeroDivisionError, OverflowError, TypeError):
                return math.nan
            return value.real if abs(value.imag) < 1e-12 else math.nan

        self._F = F
        self.values = [float(exact(params.x0))]
        self.root = None
        for _ in range(MAX_STEPS):
            nxt = F(self.values[-1])
            self.values.append(nxt)
            if not math.isfinite(nxt) or abs(nxt - self.values[0]) > RUNAWAY:
                break
            if (
                round(nxt, params.places) == round(self.values[-2], params.places)
                and len(self.values) > 2
            ):
                self.root = round(nxt, params.places)
                break

    def f(self, x: float) -> float:
        return x - self._F(x)

    def text(self, value: float) -> str:
        return f"{value:.{self.params.places + 2}f}" if math.isfinite(value) else "undefined"

    def answer_latex(self) -> str:
        if self.root is None:
            return r"\text{does not converge}"
        places = self.params.places
        return rf"\text{{root}} = {self.root:.{places}f}\ \text{{to {places} d.p.}}"

    def rows(self) -> list[tuple[str, object]]:
        rows = []
        if self.params.sign_change:
            a, b = self.params.sign_change
            fa, fb = self.f(a), self.f(b)
            rows += [
                (rf"f(x) = x - \left({written_latex(self.params.iteration)}\right)", None),
                (rf"f({a:g}) = {fa:.3f},\ f({b:g}) = {fb:.3f}", style.RISE_COLOUR),
            ]
        for i, v in enumerate(self.values):
            rows.append((rf"x_{{{i}}} = {self.text(v)}", None))
        rows.append((self.answer_latex(), style.HIGHLIGHT_COLOUR))
        return rows


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
