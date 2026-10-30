"""HarmonicForm: a sin θ + b cos θ written as R sin(θ ± α) or R cos(θ ± α), with the right-angled
triangle that gives R and α, and the single wave it describes (9709 2.3, 3.3).

Expanding R sin(θ + α) = R cos α sin θ + R sin α cos θ and matching coefficients gives
R cos α = a and R sin α = b, so R = √(a² + b²) (Pythagoras) and tan α = b/a. The sum of a sine
and a cosine wave is a single wave of amplitude R, shifted by α, so its greatest value is R and
its least −R. Optionally the equation a sin θ + b cos θ = c is solved for 0° ≤ θ ≤ 360°.
Angles are in degrees to 1 d.p.; R is exact where it is a surd.
"""

import math
from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import DashedLine, Dot, Polygon, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams, Region
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import (
    Diagram,
    angle_mark,
    curve,
    label,
    make_plot,
    stack_lines,
)
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, latex_approx, latex_value

Coefficient = Annotated[float, Field(ge=-20, le=20)]
Form = Literal["R sin(t + a)", "R sin(t - a)", "R cos(t + a)", "R cos(t - a)"]
TRIANGLE = Region(x_min=0.0, x_max=0.62, y_min=0.55, y_max=1.0)
WAVE = Region(x_min=0.0, x_max=0.62, y_min=0.0, y_max=0.55)


class HarmonicFormParams(PrimitiveParams):
    a: Coefficient = Field(description="The coefficient of sin θ; not 0")
    b: Coefficient = Field(description="The coefficient of cos θ; not 0")
    form: Form = Field(description="t stands for θ and a for α, with 0° < α < 90°")
    solve_for: Coefficient | None = Field(
        default=None, description="Optionally solve a sin θ + b cos θ = this, for 0 to 360°"
    )


class HarmonicForm(StagedPrimitive[HarmonicFormParams]):
    primitive_id = "HarmonicForm"
    version = "1"
    topic = "Trigonometry"
    params_model = HarmonicFormParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[
            ("triangle", "*"),
            ("angle", "*"),
            ("axes", "*"),
            ("wave", "*"),
            ("peak*", "*"),
            ("level_line", "*"),
            ("solutions", "*"),
        ],
    )

    def default_params(self) -> HarmonicFormParams:
        return HarmonicFormParams(a=3, b=4, form="R sin(t + a)")

    def validate(self, params: HarmonicFormParams) -> list[PredicateFailure]:
        if params.a == 0 or params.b == 0:
            return [_failure("both_terms", "a and b must both be non-zero", "a", "b")]
        right = _matching_form(params.a, params.b, params.form[2:5])
        if right is None:
            other = "cos" if params.form[2:5] == "sin" else "sin"
            right = _matching_form(params.a, params.b, other)
        if params.form != right:
            message = (
                f"with these signs α is acute only in the form {right}"
                if right
                else "a and b are both negative: write it as -(R sin(θ + α)) instead"
            )
            return [_failure("form_matches", message, "form")]
        if params.solve_for is not None and abs(params.solve_for) > _Harmonic(params).r_value:
            message = "the value is beyond the greatest value R, so there is no solution"
            return [_failure("value_possible", message, "solve_for")]
        return []

    def computed_values(self, params: HarmonicFormParams) -> dict[str, str]:
        h = _Harmonic(params)
        values = {
            "R": str(h.r),
            "alpha": f"{h.alpha:.1f}",
            "maximum": str(h.r),
            "maximum_at": f"{h.peak:.1f}",
        }
        for i, theta in enumerate(h.solutions(), start=1):
            values[f"theta_{i}"] = f"{theta:.1f}"
        return values

    def build(self, params: HarmonicFormParams, level):
        h = _Harmonic(params)
        # the triangle: legs |a| and |b|, the angle α at the vertex beside the cos-side
        near, far = (
            (abs(params.a), abs(params.b)) if h.kind == "sin" else (abs(params.b), abs(params.a))
        )
        box = style.region_box(TRIANGLE).shrink(style.PADDING)
        diagram = Diagram([(0, 0), (near, 0), (near, far)], box, margin=0.6)
        o, p, q = diagram.p(0, 0), diagram.p(near, 0), diagram.p(near, far)
        parts = {
            "triangle": Polygon(o, p, q, color=style.TEXT_COLOUR, stroke_width=3),
            "angle": angle_mark(o, p, q, radius=0.5, colour=style.TANGENT_COLOUR),
            "near_label": label(latex_value(exact(near)), colour=style.RUN_COLOUR).next_to(
                (o + p) / 2, [0, -1, 0], buff=0.15
            ),
            "far_label": label(latex_value(exact(far)), colour=style.RISE_COLOUR).next_to(
                (p + q) / 2, [1, 0, 0], buff=0.15
            ),
            "r_label": label(f"R = {latex_approx(h.r)}", colour=style.HIGHLIGHT_COLOUR).next_to(
                (o + q) / 2, [-0.6, 1, 0], buff=0.15
            ),
            "alpha_label": label(r"\alpha", colour=style.TANGENT_COLOUR).move_to(
                o + 0.8 * _unit((p - o) / np.linalg.norm(p - o) + (q - o) / np.linalg.norm(q - o))
            ),
        }
        plot = make_plot(
            WAVE,
            [0, 360],
            [h.r_value, -h.r_value],
            title=False,
            x_axis=(0, 360, 90),
            y_ticks=4,
            x_label=r"\theta",
        )

        def wave(t):
            r = math.radians(t)
            return params.a * math.sin(r) + params.b * math.cos(r)

        parts["axes"] = VGroup(plot.axes, plot.x_label, plot.y_label)
        parts["wave"] = curve(plot, wave, 0, 360)
        peak = plot.point(h.peak, h.r_value)
        parts["peak"] = Dot(peak, color=style.HIGHLIGHT_COLOUR)
        parts["peak_line"] = DashedLine(
            plot.point(0, h.r_value),
            plot.point(360, h.r_value),
            color=style.HIGHLIGHT_COLOUR,
            stroke_width=2,
        )
        if params.solve_for is not None:
            parts["level_line"] = style.line_in_axes(
                plot.axes,
                (0, params.solve_for),
                0,
                plot.x_range,
                plot.y_range,
                color=style.RISE_COLOUR,
                stroke_width=3,
            )
            parts["solutions"] = VGroup(
                *(
                    Dot(plot.point(t, params.solve_for), color=style.POINT_COLOUR)
                    for t in h.solutions()
                )
            )
        rows = h.rows()
        work = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([t for t, _ in rows], work, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: HarmonicFormParams, level) -> list[Stage]:
        h = _Harmonic(params)
        steps = [
            stage(
                "expand",
                "Expand the form and match the coefficients of sine and cosine",
                3.5,
                ["row_1", "row_2"],
            ),
            stage(
                "triangle",
                "The two matched values are the sides of a right-angled triangle",
                3.0,
                ["triangle", "near_label", "far_label"],
            ),
            stage(
                "r",
                "R is the hypotenuse, by Pythagoras",
                3.0,
                ["r_label", "row_3"],
                emphasise=["r_label"],
            ),
            stage(
                "alpha",
                "And tan alpha is opposite over adjacent",
                3.0,
                ["angle", "alpha_label", "row_4", "row_5"],
            ),
            stage(
                "wave",
                "Together they are one wave, of height R: greatest value R",
                3.5,
                ["axes", "wave", "peak", "peak_line", "row_6"],
                emphasise=["peak"],
            ),
        ]
        if params.solve_for is not None:
            n = len(h.rows())
            steps.append(
                stage(
                    "solve",
                    "To solve, use the single wave: one inverse, then the symmetry",
                    3.5,
                    ["level_line", "solutions", *[f"row_{i}" for i in range(7, n + 1)]],
                    emphasise=["solutions"],
                )
            )

        def standard(s):
            return [
                s[0],
                combine("triangle", "The triangle gives R and alpha", 4.0, *s[1:4]),
                *s[4:],
            ]

        def concise(s):
            return [
                combine(
                    "triangle", "Match coefficients: the triangle gives R and alpha", 4.5, *s[:4]
                ),
                *s[4:],
            ]

        return by_level(level, steps, standard, concise)


def _matching_form(a: float, b: float, kind: str) -> str | None:
    """The form of this kind with R > 0 and α acute, if there is one."""
    if kind == "sin":
        return None if a < 0 else ("R sin(t + a)" if b > 0 else "R sin(t - a)")
    return None if b < 0 else ("R cos(t - a)" if a > 0 else "R cos(t + a)")


def _coefficient(value) -> str:
    """A coefficient in front of sin or cos: 1 is not written, -1 is written as -."""
    return {1: "", -1: "-"}.get(value, latex_value(value))


def _squared(value) -> str:
    text = latex_value(value)
    return f"{text}^2" if sp.nsimplify(value).is_integer else rf"\left({text}\right)^2"


def _unit(v):
    return v / np.linalg.norm(v)


class _Harmonic:
    def __init__(self, params: HarmonicFormParams):
        self.params = params
        a, b = exact(params.a), exact(params.b)
        self.kind = params.form[2:5]
        self.sign = "+" if "+" in params.form else "-"
        self.r = sp.sqrt(a**2 + b**2)
        self.r_value = float(self.r)
        # sin form: R cos α = |a| side, R sin α = |b| side; cos form: R cos α = |b|, R sin α = |a|
        near, far = (abs(a), abs(b)) if self.kind == "sin" else (abs(b), abs(a))
        self.near, self.far = near, far
        self.alpha = math.degrees(math.atan2(float(far), float(near)))
        shift = self.alpha if self.sign == "+" else -self.alpha
        # the peak: sin(θ + shift) = 1 at θ = 90 − shift; cos(θ + shift) = 1 at θ = −shift
        self.peak = (90 - shift if self.kind == "sin" else -shift) % 360
        self.shift = shift

    def form_latex(self, alpha_text: str) -> str:
        return rf"R\{self.kind}(\theta {self.sign} {alpha_text})"

    def solutions(self) -> list[float]:
        c = self.params.solve_for
        if c is None:
            return []
        principal = math.degrees(
            math.asin(c / self.r_value) if self.kind == "sin" else math.acos(c / self.r_value)
        )
        second = 180 - principal if self.kind == "sin" else 360 - principal
        out = set()
        for u in (principal, second):
            for n in range(-2, 3):
                theta = u + 360 * n - self.shift
                if -1e-9 <= theta <= 360 + 1e-9:
                    out.add(round(theta, 6))
        return sorted(out)

    def rows(self) -> list[tuple[str, object]]:
        a = _coefficient(exact(self.params.a))
        b = _coefficient(abs(exact(self.params.b)))
        lhs = rf"{a}\sin\theta {'+' if self.params.b > 0 else '-'} {b}\cos\theta"
        near, far = latex_value(self.near), latex_value(self.far)
        near2, far2 = _squared(self.near), _squared(self.far)
        alpha = f"{self.alpha:.1f}^\\circ"
        if self.kind == "sin":
            expanded = rf"R\cos\alpha\sin\theta {self.sign} R\sin\alpha\cos\theta"
        else:
            other = "-" if self.sign == "+" else "+"
            expanded = rf"R\cos\alpha\cos\theta {other} R\sin\alpha\sin\theta"
        rows = [
            (rf"{lhs} = {expanded}", None),
            (rf"R\cos\alpha = {near},\ R\sin\alpha = {far}", None),
            (rf"R = \sqrt{{{near2} + {far2}}} = {latex_approx(self.r)}", style.HIGHLIGHT_COLOUR),
            (rf"\tan\alpha = \frac{{{far}}}{{{near}}},\ \alpha = {alpha}", style.TANGENT_COLOUR),
            (
                rf"{lhs} = {sp.latex(self.r)}\{self.kind}(\theta {self.sign} {alpha})",
                style.HIGHLIGHT_COLOUR,
            ),
            (
                rf"\text{{Greatest }}{latex_approx(self.r)}\text{{ at }}\theta = "
                rf"{self.peak:.1f}^\circ",
                None,
            ),
        ]
        c = self.params.solve_for
        if c is not None:
            fn = self.kind
            u = rf"\theta {self.sign} {self.alpha:.1f}^\circ"
            rows.append(
                (
                    rf"\{fn}({u}) = {'-' if c < 0 else ''}"
                    rf"\frac{{{latex_value(abs(exact(c)))}}}{{{sp.latex(self.r)}}}",
                    None,
                )
            )
            listed = r",\ ".join(f"{t:.1f}^\\circ" for t in self.solutions())
            rows.append((rf"\theta = {listed}", style.POINT_COLOUR))
        return rows


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
