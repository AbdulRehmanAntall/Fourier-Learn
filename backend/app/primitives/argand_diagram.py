"""ArgandDiagram: complex numbers as points and arrows in the Argand diagram: modulus and
argument, the conjugate, adding and subtracting (the parallelogram), multiplying and dividing
(moduli multiply or divide, arguments add or subtract), and the two square roots (9709 3.9).

z = x + iy is the point (x, y). Its modulus |z| is the length of the arrow, and its argument
arg z the angle from the positive real axis, in −π < θ ≤ π. The conjugate z* is the reflection
in the real axis. Adding is the parallelogram law, as for vectors. Multiplying by w stretches by
|w| and turns by arg w; dividing undoes that. The square roots of z are ±(a + ib) with
a² − b² = x and 2ab = y, opposite each other. Every value is exact where SymPy can make it so.
"""

from typing import Annotated, Literal

import sympy as sp
from manim import Arc, Arrow, DashedLine, Dot, Polygon, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import label, make_plot, place_label, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    exact,
    format_sf,
    latex_value,
    latex_with_pi,
    parse_expression,
)

Part = float | Annotated[str, Field(max_length=20, description='an exact value, e.g. "sqrt(3)"')]
Complex = tuple[Part, Part]
COLOURS = {"z": style.CURVE_COLOUR, "w": style.RUN_COLOUR, "result": style.HIGHLIGHT_COLOUR}


class ArgandDiagramParams(PrimitiveParams):
    kind: Literal[
        "modulus_argument", "conjugate", "add", "subtract", "multiply", "divide", "square_roots"
    ]
    z: Complex = Field(description="z as (real part, imaginary part)")
    w: Complex | None = Field(default=None, description="w, for add, subtract, multiply, divide")


class ArgandDiagram(StagedPrimitive[ArgandDiagramParams]):
    primitive_id = "ArgandDiagram"
    version = "1"
    topic = "Complex numbers"
    params_model = ArgandDiagramParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[
            ("axes", "*"),
            ("arrow_*", "*"),
            ("arc_*", "*"),
            ("guide*", "*"),
            ("parallelogram", "*"),
            ("dot_*", "*"),
        ],
    )

    def default_params(self) -> ArgandDiagramParams:
        return ArgandDiagramParams(kind="multiply", z=(1, 1), w=(1, 2))

    def validate(self, params: ArgandDiagramParams) -> list[PredicateFailure]:
        try:
            values = [_part(v) for v in (*params.z, *(params.w or ()))]
        except (ExpressionError, ValueError) as error:
            return [_failure("part_parses", str(error), "z", "w")]
        if any(abs(float(v)) > 12 for v in values):
            return [_failure("fits", "keep each part between -12 and 12", "z", "w")]
        two = params.kind in ("add", "subtract", "multiply", "divide")
        if two and params.w is None:
            return [_failure("w_given", "this operation needs w", "w")]
        if _part(params.z[0]) == 0 and _part(params.z[1]) == 0:
            return [_failure("nonzero", "z must not be 0 (it has no argument)", "z")]
        if params.kind in ("multiply", "divide") and all(_part(v) == 0 for v in params.w):
            return [_failure("nonzero", "w must not be 0", "w")]
        w = _Work(params)
        if any(abs(complex(v).real) > 40 or abs(complex(v).imag) > 40 for v in w.points.values()):
            return [_failure("fits", "the result is too large to draw", "z", "w")]
        return []

    def computed_values(self, params: ArgandDiagramParams) -> dict[str, str]:
        w = _Work(params)
        return {k: str(v) for k, v in w.values.items()}

    def build(self, params: ArgandDiagramParams, level):
        w = _Work(params)
        xs = [float(sp.re(v)) for v in w.points.values()] + [0]
        ys = [float(sp.im(v)) for v in w.points.values()] + [0]
        plot = make_plot(
            style.GRAPH_REGION, xs, ys, equal=True, x_label=r"\mathrm{Re}", y_label=r"\mathrm{Im}"
        )
        origin = plot.point(0, 0)
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "title": text_line(w.title_latex(), plot.upper),
            "answer": text_line(w.answer_latex(), plot.lower, colour=style.HIGHLIGHT_COLOUR),
        }
        obstacles = plot.obstacles()
        paths = list(plot.axis_lines())
        for name, value in w.points.items():
            colour = COLOURS.get(name.split("_")[0], style.HIGHLIGHT_COLOUR)
            tip = plot.point(float(sp.re(value)), float(sp.im(value)))
            parts[f"arrow_{name}"] = Arrow(
                origin,
                tip,
                buff=0,
                color=colour,
                stroke_width=4,
                max_tip_length_to_length_ratio=0.12,
            )
            parts[f"dot_{name}"] = Dot(tip, color=colour)
            paths.append(parts[f"arrow_{name}"])
        for name, value in w.points.items():
            colour = COLOURS.get(name.split("_")[0], style.HIGHLIGHT_COLOUR)
            tip = plot.point(float(sp.re(value)), float(sp.im(value)))
            text = label(w.names[name], colour=colour, size=28)
            parts[f"label_{name}"] = place_label(
                text, tip, plot.plot_box, obstacles, paths, wide=True
            )
            obstacles.append(text)
        if params.kind == "modulus_argument":
            z = w.points["z"]
            parts["arc_z"] = _arc(plot, z, style.TANGENT_COLOUR, 0.5)
            parts["guides"] = VGroup(
                DashedLine(
                    plot.point(float(sp.re(z)), 0),
                    plot.point(float(sp.re(z)), float(sp.im(z))),
                    stroke_width=2,
                ),
            )
        if params.kind in ("add", "subtract"):
            z, other, total = (
                w.points["z"],
                w.points["w" if params.kind == "add" else "w_neg"],
                w.points["result"],
            )
            parts["parallelogram"] = Polygon(
                origin,
                plot.point(float(sp.re(z)), float(sp.im(z))),
                plot.point(float(sp.re(total)), float(sp.im(total))),
                plot.point(float(sp.re(other)), float(sp.im(other))),
                stroke_width=1.5,
                stroke_color=style.SECANT_COLOUR,
                fill_color=style.SECANT_COLOUR,
                fill_opacity=0.12,
            )
        if params.kind in ("multiply", "divide"):
            parts["arc_z"] = _arc(plot, w.points["z"], COLOURS["z"], 0.45)
            parts["arc_w"] = _arc(plot, w.points["w"], COLOURS["w"], 0.7)
            parts["arc_result"] = _arc(plot, w.points["result"], COLOURS["result"], 0.95)
        if params.kind == "conjugate":
            z = w.points["z"]
            parts["guides"] = DashedLine(
                plot.point(float(sp.re(z)), float(sp.im(z))),
                plot.point(float(sp.re(z)), -float(sp.im(z))),
                color=style.SECANT_COLOUR,
                stroke_width=2,
            )
        rows = w.rows()
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: ArgandDiagramParams, level) -> list[Stage]:
        w = _Work(params)
        n = len(w.rows())
        rows = [f"row_{i}" for i in range(1, n + 1)]

        def show(name):
            return [f"arrow_{name}", f"dot_{name}", f"label_{name}"]

        first = stage(
            "axes",
            "The Argand diagram: real part across, imaginary part up",
            2.5,
            ["axes", "x_label", "y_label", "title"],
        )
        kind = params.kind
        if kind == "modulus_argument":
            steps = [
                first,
                stage("point", "z is the point with these coordinates", 2.5, show("z")),
                stage(
                    "modulus",
                    "The modulus is the length of the arrow, by Pythagoras",
                    3.0,
                    ["guides", rows[0]],
                ),
                stage(
                    "argument",
                    "The argument is the angle from the positive real axis",
                    3.5,
                    ["arc_z", *rows[1:], "answer"],
                    emphasise=["answer"],
                ),
            ]
        elif kind == "conjugate":
            steps = [
                first,
                stage("point", "z is the point with these coordinates", 2.5, show("z")),
                stage(
                    "conjugate",
                    "The conjugate changes the sign of the imaginary part: a reflection in the "
                    "real axis",
                    3.5,
                    ["guides", *show("result"), *rows, "answer"],
                ),
            ]
        elif kind in ("add", "subtract"):
            extra = (
                []
                if kind == "add"
                else [stage("negate", "Take away w by adding minus w", 2.5, show("w_neg"))]
            )
            steps = [
                first,
                stage("points", "z and w as arrows from the origin", 3.0, [*show("z"), *show("w")]),
                *extra,
                stage(
                    "sum",
                    "Complete the parallelogram: the diagonal is the "
                    + ("sum" if kind == "add" else "difference"),
                    3.5,
                    ["parallelogram", *show("result"), *rows, "answer"],
                    emphasise=["answer"],
                ),
            ]
        elif kind in ("multiply", "divide"):
            words = (
                "multiply, arguments add" if kind == "multiply" else "divide, arguments subtract"
            )
            steps = [
                first,
                stage(
                    "points",
                    "z and w, each with its modulus and argument",
                    3.0,
                    [*show("z"), *show("w"), "arc_z", "arc_w"],
                ),
                stage(
                    "cartesian",
                    "Work it out in Cartesian form"
                    + (": multiply by the conjugate of w" if kind == "divide" else ""),
                    3.5,
                    rows[:-1],
                ),
                stage(
                    "polar",
                    f"In the diagram, moduli {words}",
                    3.5,
                    [*show("result"), "arc_result", rows[-1], "answer"],
                    emphasise=["answer"],
                ),
            ]
        else:
            steps = [
                first,
                stage("point", "The number whose square roots we want", 2.5, show("z")),
                stage(
                    "equations",
                    "Write a root as a plus i b, square it, and compare the parts",
                    3.5,
                    rows[:3],
                ),
                stage(
                    "solve",
                    "Solve: the two roots are opposite each other",
                    3.5,
                    [*show("root_1"), *show("root_2"), *rows[3:], "answer"],
                    emphasise=["answer"],
                ),
            ]

        def standard(s):
            return list(s)

        def concise(s):
            return (
                [combine("start", s[1].description, 3.0, *s[:2]), *s[2:]] if len(s) > 2 else list(s)
            )

        return by_level(level, steps, standard, concise)


def _part(value) -> sp.Expr:
    if isinstance(value, str):
        parsed = sp.nsimplify(parse_expression(value, set()))
        if not parsed.is_real:
            raise ValueError(f"{value!r} is not a real number")
        return parsed
    return exact(value)


def _arc(plot, value, colour, radius) -> Arc:
    angle = float(sp.arg(value))
    return Arc(
        radius=radius,
        start_angle=0,
        angle=angle,
        arc_center=plot.point(0, 0),
        color=colour,
        stroke_width=3,
    )


def _c(value) -> str:
    """x + iy, exactly."""
    value = sp.nsimplify(sp.expand(value))
    re, im = sp.re(value), sp.im(value)
    if im == 0:
        return latex_value(re)
    body = {1: "i", -1: "-i"}.get(im, f"{_n(im)}i")
    if re == 0:
        return body
    return f"{_n(re)} {'-' if im < 0 else '+'} {body.lstrip('-')}"


def _n(v) -> str:
    v = sp.nsimplify(v)
    return sp.latex(v) if v.is_algebraic and not isinstance(v, sp.Float) else latex_value(v)


def _arg(value) -> str:
    angle = sp.nsimplify(sp.arg(value))
    ratio = sp.nsimplify(angle / sp.pi)
    if isinstance(ratio, sp.Rational) and ratio.q <= 12:
        return latex_with_pi(angle, approx=False)
    return format_sf(angle)


def _mod(value) -> str:
    m = sp.nsimplify(sp.Abs(value))
    return (
        sp.latex(m)
        if (m.is_Rational or (m.is_algebraic and sp.count_ops(m) <= 3))
        else format_sf(m)
    )


class _Work:
    def __init__(self, params: ArgandDiagramParams):
        self.params = params
        z = _part(params.z[0]) + sp.I * _part(params.z[1])
        w = _part(params.w[0]) + sp.I * _part(params.w[1]) if params.w is not None else None
        self.z, self.w = z, w
        self.points = {"z": z}
        self.names = {"z": "z", "w": "w", "w_neg": "-w", "result": "", "root_1": "", "root_2": ""}
        self.values: dict = {}
        kind = params.kind
        if kind in ("add", "subtract", "multiply", "divide"):
            self.points["w"] = w
        if kind == "add":
            self.result = sp.expand(z + w)
            self.names["result"] = "z + w"
        elif kind == "subtract":
            self.points["w_neg"] = -w
            self.result = sp.expand(z - w)
            self.names["result"] = "z - w"
        elif kind == "multiply":
            self.result = sp.expand(z * w)
            self.names["result"] = "zw"
        elif kind == "divide":
            self.result = sp.nsimplify(
                sp.expand(z * sp.conjugate(w)) / sp.expand(w * sp.conjugate(w))
            )
            self.names["result"] = r"\tfrac{z}{w}"
        elif kind == "conjugate":
            self.result = sp.conjugate(z)
            self.names["result"] = "z^*"
        elif kind == "square_roots":
            a, b = sp.symbols("a b", real=True)
            roots = sp.solve([a**2 - b**2 - sp.re(z), 2 * a * b - sp.im(z)], [a, b], dict=True)
            real_roots = [r for r in roots if r[a].is_real and r[b].is_real]
            self.roots = sorted(
                (sp.nsimplify(r[a] + sp.I * r[b]) for r in real_roots),
                key=lambda v: -float(sp.re(v)),
            )
            self.result = self.roots[0]
            self.points["root_1"], self.points["root_2"] = self.roots[0], self.roots[1]
            self.names["root_1"], self.names["root_2"] = _c(self.roots[0]), _c(self.roots[1])
        else:
            self.result = None
        if kind not in ("square_roots", "modulus_argument"):
            self.points["result"] = self.result
            self.names["result"] = f"{self.names['result']} = {_c(self.result)}"
        if self.result is not None:
            self.values["result"] = sp.nsimplify(self.result)
        self.values["modulus"] = sp.nsimplify(sp.Abs(z))
        self.values["argument"] = sp.nsimplify(sp.arg(z))

    def title_latex(self) -> str:
        if self.w is None:
            return f"z = {_c(self.z)}"
        return f"z = {_c(self.z)},\\quad w = {_c(self.w)}"

    def answer_latex(self) -> str:
        kind = self.params.kind
        if kind == "modulus_argument":
            return rf"|z| = {_mod(self.z)},\ \arg z = {_arg(self.z)}"
        if kind == "square_roots":
            return r"\pm\left(" + _c(self.roots[0]) + r"\right)"
        return f"{self.names['result']}"

    def rows(self) -> list[tuple[str, object]]:
        z, w, kind = self.z, self.w, self.params.kind
        x, y = sp.re(z), sp.im(z)
        if kind == "modulus_argument":
            return [
                (rf"|z| = \sqrt{{{_sq(x)} + {_sq(y)}}} = {_mod(z)}", None),
                (rf"\tan\alpha = \frac{{{latex_value(abs(y))}}}{{{latex_value(abs(x))}}}", None),
                (rf"\arg z = {_arg(z)}", style.HIGHLIGHT_COLOUR),
            ]
        if kind == "conjugate":
            return [
                (rf"z^* = {_c(sp.conjugate(z))}", style.HIGHLIGHT_COLOUR),
                (r"|z^*| = |z|,\ \arg z^* = -\arg z", None),
            ]
        if kind in ("add", "subtract"):
            sign = "+" if kind == "add" else "-"
            return [
                (rf"z {sign} w = ({_c(z)}) {sign} ({_c(w)})", None),
                (rf"= {_c(self.result)}", style.HIGHLIGHT_COLOUR),
            ]
        if kind == "multiply":
            return [
                (rf"zw = ({_c(z)})({_c(w)})", None),
                (rf"= {_c(self.result)}", style.HIGHLIGHT_COLOUR),
                (rf"|zw| = {_mod(z)}\times {_mod(w)} = {_mod(self.result)}", None),
                (rf"\arg zw = \arg z + \arg w = {_arg(self.result)}", None),
            ]
        if kind == "divide":
            conj = sp.conjugate(w)
            return [
                (
                    rf"\frac{{z}}{{w}} = \frac{{({_c(z)})({_c(conj)})}}{{({_c(w)})({_c(conj)})}}",
                    None,
                ),
                (
                    rf"= \frac{{{_c(sp.expand(z * conj))}}}"
                    rf"{{{latex_value(sp.expand(w * conj))}}} = {_c(self.result)}",
                    style.HIGHLIGHT_COLOUR,
                ),
                (
                    rf"\left|\frac{{z}}{{w}}\right| = \frac{{{_mod(z)}}}{{{_mod(w)}}} = "
                    rf"{_mod(self.result)},\ "
                    rf"\arg\frac{{z}}{{w}} = {_arg(self.result)}",
                    None,
                ),
            ]
        a, b = sp.re(self.roots[0]), sp.im(self.roots[0])
        return [
            (rf"(a + ib)^2 = {_c(z)}", None),
            (rf"a^2 - b^2 = {latex_value(x)}", None),
            (rf"2ab = {latex_value(y)}", None),
            (rf"a = {_n(a)},\ b = {_n(b)}\ \text{{or}}\ a = {_n(-a)},\ b = {_n(-b)}", None),
            (rf"\pm\left({_c(self.roots[0])}\right)", style.HIGHLIGHT_COLOUR),
        ]


def _sq(v) -> str:
    text = _n(v)
    return f"{text}^2" if v >= 0 and v.is_integer else rf"\left({text}\right)^2"


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
