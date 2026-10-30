"""TrigEquationSolver: every solution of sin, cos or tan of (bx + c) = k in an interval, from the
principal value, the symmetry of the graph and its period (9709 1.5, 3.3).

The calculator gives one value, the principal value sin⁻¹k, cos⁻¹k or tan⁻¹k. The graph's
symmetry gives a second in each period: 180° − α for sine, 360° − α (or −α) for cosine; tangent
repeats every 180°. With u = bx + c the interval for u is found first, all the values of u in it
are listed by adding and subtracting periods, and only then is each turned back into x. The
graph shows the line y = k cutting the curve at exactly those solutions. Angles are exact where
the principal value is a standard angle, otherwise to 1 d.p. (degrees) or 3 s.f. (radians).
"""

from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import DashedLine, Dot, MathTex, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import curve, make_plot, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_sf, latex_value

FUNCTIONS = {"sin": sp.sin, "cos": sp.cos, "tan": sp.tan}
INVERSES = {"sin": sp.asin, "cos": sp.acos, "tan": sp.atan}
MAX_SOLUTIONS = 8


class TrigEquationSolverParams(PrimitiveParams):
    function: Literal["sin", "cos", "tan"]
    b: Annotated[float, Field(gt=0, le=4)] = Field(
        default=1, description="The equation is f(bx + c) = k"
    )
    c: Annotated[float, Field(ge=-360, le=360)] = Field(
        default=0, description="Degrees, or a multiple of pi with radians (0.5 means pi/2)"
    )
    k: Annotated[float, Field(ge=-20, le=20)]
    x_min: Annotated[float, Field(ge=-720, le=720)] = Field(
        default=0, description="Degrees, or a multiple of pi with radians (-1 means -pi)"
    )
    x_max: Annotated[float, Field(ge=-720, le=720)] = 360
    radians: bool = False


class TrigEquationSolver(StagedPrimitive[TrigEquationSolverParams]):
    primitive_id = "TrigEquationSolver"
    version = "1"
    topic = "Trigonometry"
    params_model = TrigEquationSolverParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[
            ("axes", "*"),
            ("curve", "*"),
            ("level_line", "*"),
            ("drops", "*"),
            ("dots", "*"),
            ("principal", "*"),
        ],
    )

    def default_params(self) -> TrigEquationSolverParams:
        return TrigEquationSolverParams(function="sin", b=2, c=30, k=0.5, x_min=0, x_max=360)

    def validate(self, params: TrigEquationSolverParams) -> list[PredicateFailure]:
        if params.x_min >= params.x_max:
            return [_failure("interval_ordered", "x_min must be below x_max", "x_min", "x_max")]
        span = params.x_max - params.x_min
        if (params.radians and span > 4) or (not params.radians and span > 720):
            message = "the interval may be at most 720 degrees (4 pi)"
            return [_failure("interval_short", message, "x_min", "x_max")]
        if params.radians and (abs(params.x_min) > 4 or abs(params.x_max) > 4 or abs(params.c) > 4):
            message = "with radians, give the interval and c as multiples of pi, e.g. -1 to 1"
            return [_failure("radians_as_pi", message, "x_min", "x_max", "c")]
        if params.function != "tan" and abs(params.k) > 1:
            message = f"{params.function} only takes values from -1 to 1, so there is no solution"
            return [_failure("value_possible", message, "k")]
        found = _Solution(params)
        if not found.x_values:
            return [_failure("has_solutions", "no solution lies in the interval", "x_min")]
        if len(found.x_values) > MAX_SOLUTIONS:
            message = f"more than {MAX_SOLUTIONS} solutions: shorten the interval"
            return [_failure("solutions_fit", message, "x_min", "x_max")]
        return []

    def computed_values(self, params: TrigEquationSolverParams) -> dict[str, str]:
        found = _Solution(params)
        values = {"principal_value": found.text(found.alpha), "count": str(len(found.x_values))}
        for i, x in enumerate(found.x_values, start=1):
            values[f"x_{i}"] = found.text(x)
        return values

    def build(self, params: TrigEquationSolverParams, level):
        found = _Solution(params)
        lo, hi = found.lo, found.hi
        unit = found.unit
        f = FUNCTIONS[params.function]
        b, c = exact(params.b), found.c

        numeric = sp.lambdify(
            sp.Symbol("t"), f(sp.Float(float(b)) * sp.Symbol("t") * float(unit) + float(c)), "math"
        )
        xs = np.linspace(float(lo), float(hi), 200)
        ys = [numeric(x) for x in xs]
        if params.function == "tan":
            bound = max(3.0, abs(params.k) + 1.5)
            ys = [-bound, bound]
        step = _tick_step(float(hi - lo), params.radians)
        x_axis = (
            float(sp.floor(lo / step) * step),
            float(sp.ceiling(hi / step) * step),
            float(step),
        )
        plot = make_plot(
            style.GRAPH_REGION,
            [float(lo), float(hi)],
            [*ys, float(params.k)],
            x_axis=x_axis,
            y_ticks=5,
        )
        if params.radians:
            _pi_numbers(plot, x_axis)
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "equation": text_line(found.equation_latex(), plot.upper),
            "curve": curve(plot, numeric, float(lo), float(hi), samples=600),
            "level_line": style.line_in_axes(
                plot.axes,
                (0, params.k),
                0,
                plot.x_range,
                plot.y_range,
                color=style.RISE_COLOUR,
                stroke_width=3,
            ),
        }
        k_display = float(params.k)
        points = [plot.point(float(x / unit), k_display) for x in found.x_values]
        parts["dots"] = VGroup(*(Dot(p, color=style.POINT_COLOUR) for p in points))
        parts["drops"] = VGroup(
            *(
                DashedLine(
                    p, plot.point(float(x / unit), 0), color=style.POINT_COLOUR, stroke_width=2
                )
                for p, x in zip(points, found.x_values, strict=True)
            )
        )
        alpha_x = (found.alpha - c) / b
        if lo <= alpha_x / unit <= hi:
            parts["principal"] = Dot(
                plot.point(float(alpha_x / unit), k_display),
                color=style.TANGENT_COLOUR,
                radius=0.11,
            )
        else:
            parts["principal"] = Dot(plot.point(float(lo), k_display), radius=0.001, fill_opacity=0)
        parts["answer"] = text_line(
            "x = " + ",\\ ".join(found.latex(x) for x in found.x_values),
            plot.lower,
            colour=style.HIGHLIGHT_COLOUR,
        )
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        rows = found.rows()
        texts = stack_lines([t for t, _ in rows], box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: TrigEquationSolverParams, level) -> list[Stage]:
        found = _Solution(params)
        substitute = found.substituted()
        rows = [f"row_{i}" for i in range(1, len(found.rows()) + 1)]
        steps = [
            stage(
                "graph",
                "Draw the graph over the interval, and the line y equals k",
                3.0,
                ["axes", "x_label", "y_label", "equation", "curve", "level_line", rows[0]],
            ),
        ]
        at = 1
        if substitute:
            steps.append(
                stage(
                    "interval",
                    "Let u be the whole bracket, and find the interval for u first",
                    3.0,
                    [rows[at]],
                    emphasise=[rows[at]],
                )
            )
            at += 1
        steps.append(
            stage(
                "principal",
                "The calculator gives one value, the principal value",
                3.0,
                [rows[at], "principal"],
                emphasise=["principal"],
            )
        )
        steps.append(
            stage(
                "symmetry",
                {
                    "sin": "The sine graph is symmetrical: 180 degrees take the angle gives "
                    "another",
                    "cos": "The cosine graph is symmetrical: 360 degrees take the angle gives "
                    "another",
                    "tan": "Tangent repeats every 180 degrees, one value in each period",
                }[params.function],
                3.0,
                [rows[at + 1]],
            )
        )
        steps.append(
            stage(
                "all_u",
                "Add and take away whole periods to list every value in the interval",
                3.0,
                [rows[at + 2], "dots"],
                emphasise=["dots"],
            )
        )
        steps.append(
            stage(
                "answer",
                "Turn each value back into x" if substitute else "These are the solutions",
                3.0,
                [*rows[at + 3 :], "drops", "answer"],
                emphasise=["answer"],
            )
        )

        def standard(s):
            return [
                s[0],
                combine("values", "The principal value, then the symmetry", 3.5, *s[1:-2]),
                *s[-2:],
            ]

        def concise(s):
            return [
                s[0],
                combine(
                    "values", "The principal value, then the symmetry and the period", 4.0, *s[1:-1]
                ),
                s[-1],
            ]

        return by_level(level, steps, standard, concise)


class _Solution:
    def __init__(self, params: TrigEquationSolverParams):
        self.params = params
        self.unit = sp.pi if params.radians else sp.pi / 180  # display unit in radians
        self.lo, self.hi = exact(params.x_min), exact(params.x_max)
        self.b = exact(params.b)
        self.c = exact(params.c) * self.unit
        self.k = exact(params.k)
        self.alpha = sp.nsimplify(INVERSES[params.function](self.k))
        u_lo = self.b * self.lo * self.unit + self.c
        u_hi = self.b * self.hi * self.unit + self.c
        self.u_lo, self.u_hi = u_lo, u_hi
        if params.function == "tan":
            bases, period = [self.alpha], sp.pi
            self.second = None
        else:
            self.second = sp.pi - self.alpha if params.function == "sin" else 2 * sp.pi - self.alpha
            bases, period = [self.alpha, self.second], 2 * sp.pi
        values = set()
        for base in bases:
            n_lo = int(sp.floor((u_lo - base) / period)) - 1
            n_hi = int(sp.ceiling((u_hi - base) / period)) + 1
            for n in range(n_lo, n_hi + 1):
                u = sp.nsimplify(base + n * period)
                if float(u_lo) - 1e-9 <= float(u) <= float(u_hi) + 1e-9:
                    values.add(u)
        self.u_values = sorted(values, key=float)
        if len(self.u_values) > 2 * MAX_SOLUTIONS:
            self.u_values = self.u_values[: 2 * MAX_SOLUTIONS]
        self.x_values = [sp.nsimplify((u - self.c) / self.b) for u in self.u_values]

    def substituted(self) -> bool:
        return self.b != 1 or self.c != 0

    def latex(self, angle) -> str:
        if self.params.radians:
            ratio = sp.nsimplify(angle / sp.pi)
            if isinstance(ratio, sp.Rational) and ratio.q <= 24:
                return _pi_latex(ratio)
            return format_sf(angle)
        degrees = sp.nsimplify(angle * 180 / sp.pi)
        if isinstance(degrees, sp.Rational) and (degrees * 10).is_integer:
            text = f"{float(degrees):g}"
        else:
            text = f"{float(degrees):.1f}"
        return text + r"^\circ"

    def text(self, angle) -> str:
        return self.latex(angle).replace(r"^\circ", "").replace(r"\pi", "pi").replace(r"\frac", "")

    def equation_latex(self) -> str:
        return rf"\{self.params.function}\left({self._argument('x')}\right) = {latex_value(self.k)}"

    def _argument(self, name: str) -> str:
        b = "" if self.b == 1 else latex_value(self.b)
        if self.c == 0:
            return f"{b}{name}"
        sign = "+" if self.c > 0 else "-"
        return f"{b}{name} {sign} {self.latex(abs(self.c))}"

    def rows(self) -> list[tuple[str, object]]:
        fn = self.params.function
        rows = [(self.equation_latex(), None)]
        if self.substituted():
            rows.append(
                (
                    rf"u = {self._argument('x')}:\ {self.latex(self.u_lo)} \le u \le "
                    rf"{self.latex(self.u_hi)}",
                    None,
                )
            )
        name = "u" if self.substituted() else "x"
        rows.append(
            (
                rf"{name} = \{fn}^{{-1}}\left({latex_value(self.k)}\right) = "
                + self.latex(self.alpha),
                style.TANGENT_COLOUR,
            )
        )
        alpha = self.latex(self.alpha)
        alpha = rf"\left({alpha}\right)" if self.alpha < 0 else alpha
        if fn == "sin":
            rows.append(
                (
                    rf"{name} = {self.latex(sp.pi)} - {alpha} = " + self.latex(self.second),
                    None,
                )
            )
        elif fn == "cos":
            rows.append(
                (
                    rf"{name} = {self.latex(2 * sp.pi)} - {alpha} = " + self.latex(self.second),
                    None,
                )
            )
        else:
            rows.append(
                (rf"\text{{Period }}{self.latex(sp.pi)}\text{{: add or take away it}}", None)
            )
        listed = self.u_values if self.substituted() else self.x_values
        rows.append((rf"{name} = " + ",\\ ".join(self.latex(u) for u in listed), None))
        if self.substituted():
            rows.append(
                ("x = " + ",\\ ".join(self.latex(x) for x in self.x_values), style.HIGHLIGHT_COLOUR)
            )
        return rows


def _pi_latex(ratio: sp.Rational) -> str:
    if ratio == 0:
        return "0"
    sign = "-" if ratio < 0 else ""
    p, q = abs(ratio.p), ratio.q
    top = r"\pi" if p == 1 else rf"{p}\pi"
    return sign + (top if q == 1 else rf"\frac{{{top}}}{{{q}}}")


def _tick_step(span: float, radians: bool):
    if radians:
        return sp.Rational(1, 2) if span > 1.5 else sp.Rational(1, 4)
    if span > 450:
        return sp.Integer(180)
    if span > 200:
        return sp.Integer(90)
    return sp.Integer(45) if span > 90 else sp.Integer(30)


def _pi_numbers(plot, x_axis) -> None:
    """Replace the x-axis numbers (multiples of pi, drawn as decimals) by pi fractions."""
    axis = plot.axes.x_axis
    axis.remove(axis.numbers)
    start, end, step = x_axis
    numbers = VGroup()
    count = int(round((end - start) / step))
    for i in range(count + 1):
        value = sp.nsimplify(start + i * step)
        if value == 0:
            continue
        tex = MathTex(_pi_latex(sp.Rational(value)).replace(r"\frac", r"\tfrac"), font_size=22)
        tex.next_to(plot.axes.c2p(float(value), 0), [0, -1, 0], buff=0.15)
        numbers.add(tex)
    axis.numbers = numbers
    axis.add(numbers)


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
