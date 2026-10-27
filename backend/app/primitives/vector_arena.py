"""VectorArena: vectors on a grid: column vectors and their magnitude, adding and subtracting by
the triangle law, multiples, and vector geometry, where a route through O gives AB = b − a and
the point dividing AB in a ratio (4024 7.2–7.4; 4037 Unit 13; PRIMITIVES.md #43).

Vectors are drawn as arrows from tip to tail, named in bold; every column vector and magnitude
is computed exactly (√ kept as a surd when it is not whole).
"""

from typing import Annotated, Literal

import sympy as sp
from manim import Arrow, DashedLine, Dot, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, make_plot, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf, latex_approx, latex_value

Component = Annotated[int, Field(ge=-12, le=12)]
Vector = tuple[Component, Component]


class VectorArenaParams(PrimitiveParams):
    kind: Literal["magnitude", "add", "subtract", "scalar", "geometry"]
    a: Vector = (3, 1)
    b: Vector = (1, 3)
    k: Annotated[float, Field(ge=-4, le=4)] = Field(default=2, description="For scalar")
    ratio: tuple[Annotated[int, Field(ge=1, le=9)], Annotated[int, Field(ge=1, le=9)]] = Field(
        default=(1, 1), description="For geometry: P divides AB in this ratio (1:1 = midpoint)"
    )


class VectorArena(StagedPrimitive[VectorArenaParams]):
    primitive_id = "VectorArena"
    version = "1"
    topic = "Vectors"
    params_model = VectorArenaParams
    # the grid on the left, the column-vector working in the working region on the right
    layout = LayoutContract(
        region=style.Region(x_min=0.0, x_max=1.0, y_min=0.0, y_max=1.0),
        allowed_overlaps=[("axes", "*"), ("vec_*", "*"), ("result", "*"), ("guide", "*")],
    )

    def default_params(self) -> VectorArenaParams:
        return VectorArenaParams(kind="add", a=(3, 1), b=(1, 3))

    def validate(self, params: VectorArenaParams) -> list[PredicateFailure]:
        if params.kind == "scalar" and params.k == 0:
            return [_failure("nonzero_k", "0 times a vector is the zero vector", "k")]
        if params.kind in ("add", "subtract", "geometry") and params.a == params.b:
            return [_failure("vectors_differ", "use two different vectors", "b")]
        if params.a == (0, 0):
            return [_failure("nonzero_a", "a is the zero vector", "a")]
        return []

    def computed_values(self, params: VectorArenaParams) -> dict[str, str]:
        result = _result(params)
        values = {"result": f"({_n(result[0])}, {_n(result[1])})"}
        if params.kind == "magnitude":
            values["magnitude"] = str(_magnitude(params.a))
        return values

    def build(self, params: VectorArenaParams, level):
        a, b = (sp.Matrix(v) for v in (params.a, params.b))
        k = sp.nsimplify(params.k)
        result = _result(params)
        # every point the arrows reach, so the grid contains them
        if params.kind == "magnitude":
            route = [(0, 0), tuple(a)]
        elif params.kind == "add":
            route = [(0, 0), tuple(a), tuple(a + b)]
        elif params.kind == "subtract":
            route = [(0, 0), tuple(a), tuple(a - b)]
        elif params.kind == "scalar":
            route = [(0, 0), tuple(a), tuple(k * a)]
        else:
            route = [(0, 0), tuple(a), tuple(b)]
        xs = [float(p[0]) for p in route]
        ys = [float(p[1]) for p in route]
        plot = make_plot(style.GRAPH_REGION, xs, ys, equal=True)
        o = plot.point(0, 0)

        def p(v) -> object:
            return plot.point(float(v[0]), float(v[1]))

        def arrow(start, end, colour, width=5):
            return Arrow(
                start,
                end,
                buff=0,
                color=colour,
                stroke_width=width,
                max_tip_length_to_length_ratio=0.12,
            )

        def name(tex, start, end, colour, side=1):
            mid = (start + end) / 2
            direction = end - start
            normal = side * sp.Matrix([-direction[1], direction[0]])
            length = float(sp.sqrt(normal[0] ** 2 + normal[1] ** 2)) or 1
            offset = [float(normal[0]) / length * 0.3, float(normal[1]) / length * 0.3, 0]
            return label(tex, colour=colour, size=30).move_to(mid + offset)

        parts = {"axes": VGroup(plot.axes, plot.x_label, plot.y_label)}
        A, B = style.CURVE_COLOUR, style.RUN_COLOUR
        R = style.HIGHLIGHT_COLOUR
        if params.kind == "magnitude":
            end = p(a)
            parts["vec_a"] = VGroup(arrow(o, end, A), name(r"\mathbf{a}", o, end, A))
            corner = plot.point(float(a[0]), 0)
            parts["guide"] = VGroup(
                DashedLine(o, corner, color=style.RISE_COLOUR, stroke_width=3),
                DashedLine(corner, end, color=style.RISE_COLOUR, stroke_width=3),
                label(str(abs(params.a[0])), colour=style.RISE_COLOUR, size=26).next_to(
                    (o + corner) / 2, [0, -1 if params.a[1] >= 0 else 1, 0], buff=0.12
                ),
                label(str(abs(params.a[1])), colour=style.RISE_COLOUR, size=26).next_to(
                    (corner + end) / 2, [1 if params.a[0] >= 0 else -1, 0, 0], buff=0.12
                ),
            )
        elif params.kind in ("add", "subtract"):
            second = b if params.kind == "add" else -b
            tip = a + second
            parts["vec_a"] = VGroup(arrow(o, p(a), A), name(r"\mathbf{a}", o, p(a), A))
            tex = r"\mathbf{b}" if params.kind == "add" else r"-\mathbf{b}"
            parts["vec_b"] = VGroup(arrow(p(a), p(tip), B), name(tex, p(a), p(tip), B))
            word = (
                r"\mathbf{a} + \mathbf{b}" if params.kind == "add" else (r"\mathbf{a} - \mathbf{b}")
            )
            parts["result"] = VGroup(arrow(o, p(tip), R, 6), name(word, o, p(tip), R, side=-1))
        elif params.kind == "scalar":
            parts["vec_a"] = VGroup(arrow(o, p(a), A, 7), name(r"\mathbf{a}", o, p(a), A))
            parts["result"] = VGroup(
                arrow(o, p(k * a), R, 4), name(rf"{_k_tex(k)}\mathbf{{a}}", o, p(k * a), R, side=-1)
            )
        else:
            m, n = params.ratio
            point = a + sp.Rational(m, m + n) * (b - a)
            parts["vec_a"] = VGroup(
                arrow(o, p(a), A),
                name(r"\mathbf{a}", o, p(a), A, side=-1),
                label("A", size=28).next_to(p(a), [1, 0, 0], buff=0.1),
            )
            parts["vec_b"] = VGroup(
                arrow(o, p(b), B),
                name(r"\mathbf{b}", o, p(b), B),
                label("B", size=28).next_to(p(b), [0, 1, 0], buff=0.1),
            )
            parts["guide"] = VGroup(
                arrow(p(a), p(b), style.RISE_COLOUR, 4),
                label("O", size=28).next_to(o, [-1, -1, 0], buff=0.08),
            )
            parts["result"] = VGroup(
                Dot(p(point), color=R, radius=0.08),
                label("P", colour=R, size=28).next_to(p(point), [1, 1, 0], buff=0.08),
                DashedLine(o, p(point), color=R, stroke_width=3),
            )
        rows = _working(params)
        mobjects = [label(t, size=30) for t in rows]
        group = VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.25)
        working_box = style.region_box(style.WORKING_REGION).shrink(0.35)
        style.fit_inside(group, working_box)
        for i, mob in enumerate(mobjects, start=1):
            parts[f"row_{i}"] = mob
        question = {
            "magnitude": r"\text{The magnitude of } \mathbf{a}",
            "add": r"\mathbf{a} + \mathbf{b}",
            "subtract": r"\mathbf{a} - \mathbf{b}",
            "scalar": rf"{_k_tex(k)}\mathbf{{a}}",
            "geometry": rf"\overrightarrow{{OA}} = \mathbf{{a}},\ \overrightarrow{{OB}} = "
            rf"\mathbf{{b}},\ AP : PB = {params.ratio[0]} : {params.ratio[1]}",
        }[params.kind]
        parts["question"] = text_line(question, plot.upper)
        if params.kind == "magnitude":
            answer = rf"|\mathbf{{a}}| = {latex_approx(_magnitude(params.a))}"
        elif params.kind == "geometry":
            answer = rf"\overrightarrow{{OP}} = {_combination(params)}"
        else:
            answer = rf"= {_column(result, small=True)}"
        parts["answer"] = text_line(answer, plot.lower, colour=R)
        return parts

    def stages(self, params: VectorArenaParams, level) -> list[Stage]:
        rows = [f"row_{i}" for i in range(1, len(_working(params)) + 1)]
        kind = params.kind
        if kind == "magnitude":
            steps = [
                stage(
                    "vector", "The vector a: across, then up", 2.5, ["question", "axes", "vec_a"]
                ),
                stage(
                    "triangle",
                    "It is the hypotenuse of a right-angled triangle",
                    3.0,
                    ["guide", *rows[:1]],
                ),
                stage("pythagoras", "Pythagoras gives its length", 3.0, rows[1:]),
            ]
        elif kind in ("add", "subtract"):
            words = (
                "Put b on the end of a: tip to tail"
                if kind == "add"
                else "Minus b points the other way: put it on the end of a"
            )
            steps = [
                stage("a", "Draw a", 2.0, ["question", "axes", "vec_a"]),
                stage("b", words, 3.0, ["vec_b"]),
                stage(
                    "result", "The result goes from the start to the finish", 3.0, ["result", *rows]
                ),
            ]
        elif kind == "scalar":
            steps = [
                stage("a", "Draw a", 2.0, ["question", "axes", "vec_a"]),
                stage(
                    "scale",
                    "Multiplying by k stretches it k times; a negative k turns it round",
                    3.5,
                    ["result", *rows],
                ),
            ]
        else:
            steps = [
                stage(
                    "ab",
                    "The position vectors of A and B",
                    2.5,
                    ["question", "axes", "vec_a", "vec_b"],
                ),
                stage("route", "From A to B: back along a, then along b", 3.5, ["guide", rows[0]]),
                stage(
                    "point", "P is that fraction of the way along AB", 3.5, ["result", *rows[1:]]
                ),
            ]
        steps.append(stage("answer", "So", 1.5, ["answer"], emphasise=["answer"]))

        def concise(s):
            return [combine("setup", s[0].description, 3.0, s[0], s[1]), *s[2:]]

        return by_level(level, steps, lambda s: s, concise)


def _n(value) -> str:
    return format_sf(value, 6)


def _column(v, small: bool = False) -> str:
    """A column vector, its entries exact (4/3 stays a fraction); small for a title line."""
    top, bottom = (latex_value(sp.nsimplify(c)) for c in (v[0], v[1]))
    if small:
        return rf"\left(\begin{{smallmatrix}} {top} \\ {bottom} \end{{smallmatrix}}\right)"
    return rf"\begin{{pmatrix}} {top} \\ {bottom} \end{{pmatrix}}"


def _k_tex(k) -> str:
    """k as it was given (1.5, not 3/2), and nothing for 1."""
    if k in (1, -1):
        return "" if k == 1 else "-"
    return _n(k)


def _magnitude(v) -> sp.Expr:
    return sp.sqrt(sp.Integer(v[0]) ** 2 + sp.Integer(v[1]) ** 2)


def _result(params: VectorArenaParams):
    a, b = (sp.Matrix(v) for v in (params.a, params.b))
    if params.kind == "add":
        return a + b
    if params.kind == "subtract":
        return a - b
    if params.kind == "scalar":
        return sp.nsimplify(params.k) * a
    if params.kind == "geometry":
        m, n = params.ratio
        return a + sp.Rational(m, m + n) * (b - a)
    return a


def _combination(params: VectorArenaParams) -> str:
    m, n = params.ratio
    t = sp.Rational(m, m + n)
    ca, cb = 1 - t, t
    parts = []
    for c, name in ((ca, r"\mathbf{a}"), (cb, r"\mathbf{b}")):
        if c == 0:
            continue
        parts.append(name if c == 1 else rf"{sp.latex(c)}{name}")
    return " + ".join(parts)


def _working(params: VectorArenaParams) -> list[str]:
    a, b = params.a, params.b
    if params.kind == "magnitude":
        return [
            rf"\mathbf{{a}} = {_column(a)}",
            rf"|\mathbf{{a}}| = \sqrt{{{_sq(a[0])} + {_sq(a[1])}}}",
            rf"= {latex_approx(_magnitude(a))}",
        ]
    if params.kind in ("add", "subtract"):
        sign = "+" if params.kind == "add" else "-"
        return [rf"{_column(a)} {sign} {_column(b)} = {_column(_result(params))}"]
    if params.kind == "scalar":
        k = sp.nsimplify(params.k)
        return [rf"{_n(k)} \times {_column(a)} = {_column(_result(params))}"]
    m, n = params.ratio
    frac = sp.latex(sp.Rational(m, m + n))
    return [
        r"\overrightarrow{AB} = -\mathbf{a} + \mathbf{b} = \mathbf{b} - \mathbf{a}",
        rf"\overrightarrow{{OP}} = \mathbf{{a}} + {frac}(\mathbf{{b}} - \mathbf{{a}})",
        rf"= {_combination(params)} = {_column(_result(params))}",
    ]


def _sq(value: int) -> str:
    return f"({value})^2" if value < 0 else f"{value}^2"


def _failure(predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=[parameter]
    )
