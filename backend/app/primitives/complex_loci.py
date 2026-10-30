"""ComplexLoci: equations and inequalities in z drawn as loci in the Argand diagram: the circle
|z − a| = r, the perpendicular bisector |z − a| = |z − b|, the half-line arg(z − a) = α, the
regions they bound, and where two loci meet (9709 3.9).

|z − a| is the distance from z to the point a, so |z − a| = r is a circle and |z − a| < r its
inside; |z − a| = |z − b| is every point as far from a as from b; arg(z − a) = α is the half-line
leaving a at angle α (a itself excluded), and α ≤ arg(z − a) ≤ β the sector between two of them.
With z = x + iy each locus has a Cartesian equation, which SymPy solves for the points where two
loci meet. A strict inequality's boundary is dashed, as it is not included.
"""

import math
from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import (
    Circle,
    DashedVMobject,
    Difference,
    Dot,
    Intersection,
    Line,
    Polygon,
    VGroup,
    VMobject,
)
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

X, Y = sp.symbols("x y", real=True)
Part = Annotated[float, Field(ge=-10, le=10)]
Complex = tuple[Part, Part]
COLOURS = [style.CURVE_COLOUR, style.RUN_COLOUR]
REACH = 40.0


class Locus(PrimitiveParams):
    kind: Literal["circle", "bisector", "half_line", "sector"]
    relation: Literal["=", "<", "<=", ">", ">="] = Field(
        default="=", description="circle: |z - a| rel r. bisector: |z - a| rel |z - b|"
    )
    a: Complex = Field(description="The point a (centre, first point, or start of the half-line)")
    b: Complex | None = Field(default=None, description="bisector: the second point")
    r: Annotated[float, Field(gt=0, le=10)] | None = Field(
        default=None, description="circle: radius"
    )
    angle: str | None = Field(
        default=None,
        max_length=12,
        description='half_line or sector: an angle in radians, e.g. "pi/4"',
    )
    angle_2: str | None = Field(default=None, max_length=12, description="sector: the larger angle")


class ComplexLociParams(PrimitiveParams):
    loci: list[Locus] = Field(min_length=1, max_length=2)


class ComplexLoci(StagedPrimitive[ComplexLociParams]):
    primitive_id = "ComplexLoci"
    version = "1"
    topic = "Complex numbers"
    params_model = ComplexLociParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[
            ("axes", "*"),
            ("locus_*", "*"),
            ("region", "*"),
            ("points", "*"),
            ("mark_*", "*"),
        ],
    )

    def default_params(self) -> ComplexLociParams:
        return ComplexLociParams(
            loci=[
                Locus(kind="circle", relation="<=", a=(1, 1), r=2),
                Locus(kind="sector", a=(1, 1), angle="0", angle_2="pi/2"),
            ]
        )

    def validate(self, params: ComplexLociParams) -> list[PredicateFailure]:
        for i, locus in enumerate(params.loci, start=1):
            name = f"loci[{i}]"
            if locus.kind == "circle" and locus.r is None:
                return [_failure("radius_given", f"{name}: a circle needs r", name)]
            if locus.kind == "bisector" and (locus.b is None or tuple(locus.b) == tuple(locus.a)):
                return [_failure("two_points", f"{name}: a bisector needs a second point b", name)]
            if locus.kind in ("half_line", "sector"):
                try:
                    low = _angle(locus.angle)
                    high = _angle(locus.angle_2) if locus.kind == "sector" else low
                except (ExpressionError, ValueError, TypeError) as error:
                    return [_failure("angle_parses", f"{name}: {error}", name)]
                if not (-sp.pi < low <= sp.pi and -sp.pi < high <= sp.pi):
                    return [
                        _failure(
                            "angle_range", f"{name}: angles must be in -pi < angle <= pi", name
                        )
                    ]
                if locus.kind == "sector" and low >= high:
                    return [
                        _failure("angles_ordered", f"{name}: angle must be below angle_2", name)
                    ]
            if locus.kind in ("half_line", "sector") and locus.relation != "=":
                return [
                    _failure(
                        "relation_fits", f"{name}: use a sector for a range of arguments", name
                    )
                ]
        return []

    def computed_values(self, params: ComplexLociParams) -> dict[str, str]:
        w = _Work(params)
        values = {f"locus_{i}": str(eq) for i, eq in enumerate(w.equations, start=1)}
        for i, (x, y) in enumerate(w.meets, start=1):
            values[f"meet_{i}"] = f"{x} + {y}i"
        return values

    def build(self, params: ComplexLociParams, level):
        w = _Work(params)
        xs, ys = [0.0], [0.0]
        for locus in params.loci:
            xs.append(locus.a[0])
            ys.append(locus.a[1])
            if locus.r is not None:
                xs += [locus.a[0] - locus.r, locus.a[0] + locus.r]
                ys += [locus.a[1] - locus.r, locus.a[1] + locus.r]
            if locus.b is not None:
                xs.append(locus.b[0])
                ys.append(locus.b[1])
        for x, y in w.meets:
            xs.append(float(x))
            ys.append(float(y))
        span = max(max(xs) - min(xs), max(ys) - min(ys), 4.0)
        pad = 0.12 * span
        plot = make_plot(
            style.GRAPH_REGION,
            [min(xs) - pad, max(xs) + pad],
            [min(ys) - pad, max(ys) + pad],
            equal=True,
            x_label=r"\mathrm{Re}",
            y_label=r"\mathrm{Im}",
        )
        box = [
            plot.point(plot.x_range[0], plot.y_range[0]),
            plot.point(plot.x_range[1], plot.y_range[0]),
            plot.point(plot.x_range[1], plot.y_range[1]),
            plot.point(plot.x_range[0], plot.y_range[1]),
        ]
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "title": text_line(w.title_latex(), plot.upper),
            "answer": text_line(w.answer_latex(), plot.lower, colour=style.HIGHLIGHT_COLOUR),
        }
        obstacles = plot.obstacles()
        regions = []
        for i, locus in enumerate(params.loci, start=1):
            colour = COLOURS[i - 1]
            boundary = _boundary(plot, locus, colour)
            if locus.relation in ("<", ">"):
                boundary = DashedVMobject(boundary, num_dashes=60)
            parts[f"locus_{i}"] = boundary
            a = plot.point(*locus.a)
            marks = VGroup(Dot(a, color=colour, radius=0.06))
            if locus.b is not None:
                marks.add(Dot(plot.point(*locus.b), color=colour, radius=0.06))
            parts[f"mark_{i}"] = marks
            region = _region(plot, locus, box)
            if region is not None:
                regions.append(region)
        if regions:
            shaded = regions[0]
            for other in regions[1:]:
                shaded = Intersection(shaded, other)
            shaded.set_fill(style.AREA_COLOUR, opacity=0.4).set_stroke(width=0)
            parts["region"] = shaded
        if w.meets:
            parts["points"] = VGroup(
                *(
                    Dot(plot.point(float(x), float(y)), color=style.HIGHLIGHT_COLOUR)
                    for x, y in w.meets
                )
            )
        for i, locus in enumerate(params.loci, start=1):
            text = label(w.locus_latex(locus), colour=COLOURS[i - 1], size=26)
            anchor = plot.point(*locus.a)
            parts[f"label_{i}"] = place_label(
                text, anchor, plot.plot_box, obstacles, [*plot.axis_lines()], wide=True
            )
            obstacles.append(text)
        rows = w.rows()
        work_box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], work_box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: ComplexLociParams, level) -> list[Stage]:
        w = _Work(params)
        n = len(w.rows())
        steps = [stage("axes", "The Argand diagram", 2.0, ["axes", "x_label", "y_label", "title"])]
        for i, locus in enumerate(params.loci, start=1):
            steps.append(
                stage(
                    f"locus_{i}",
                    _words(locus),
                    3.5,
                    [f"mark_{i}", f"locus_{i}", f"label_{i}", f"row_{2 * i - 1}", f"row_{2 * i}"],
                )
            )
        last = [f"row_{k}" for k in range(2 * len(params.loci) + 1, n + 1)]
        extra = (["region"] if "region" in _part_names(params) else []) + (
            ["points"] if w.meets else []
        )
        steps.append(
            stage(
                "result",
                "Where they meet" if w.meets else "The region where every condition holds",
                3.0,
                [*extra, *last, "answer"],
                emphasise=["answer"],
            )
        )

        def standard(s):
            return list(s)

        def concise(s):
            return [combine("loci", "Draw each locus", 4.5, *s[:-1]), s[-1]]

        return by_level(level, steps, standard, concise)


def _part_names(params: ComplexLociParams) -> set[str]:
    return {"region"} if any(_has_region(locus) for locus in params.loci) else set()


def _has_region(locus: Locus) -> bool:
    return locus.kind == "sector" or locus.relation != "="


def _angle(text: str | None) -> sp.Expr:
    if text is None:
        raise ValueError("an angle is needed")
    value = sp.nsimplify(parse_expression(text, set()), [sp.pi])
    if not value.is_real:
        raise ValueError(f"{text!r} is not an angle")
    return value


def _boundary(plot, locus: Locus, colour) -> VMobject:
    a = np.array(locus.a, dtype=float)
    if locus.kind == "circle":
        centre = plot.point(*a)
        radius = np.linalg.norm(plot.point(a[0] + locus.r, a[1]) - centre)
        return Circle(radius=radius, color=colour, stroke_width=4).move_to(centre)
    if locus.kind == "bisector":
        b = np.array(locus.b, dtype=float)
        mid, d = (a + b) / 2, b - a
        normal = np.array([-d[1], d[0]]) / np.linalg.norm(d)
        return _clipped(plot, mid - REACH * normal, mid + REACH * normal, colour)
    angles = [float(_angle(locus.angle))]
    if locus.kind == "sector":
        angles.append(float(_angle(locus.angle_2)))
    group = VGroup()
    for t in angles:
        end = a + REACH * np.array([math.cos(t), math.sin(t)])
        group.add(_clipped(plot, a, end, colour))
    return group


def _clipped(plot, p, q, colour) -> Line:
    """The segment pq cut to the plot (Liang-Barsky)."""
    x0, x1 = plot.x_range[0], plot.x_range[1]
    y0, y1 = plot.y_range[0], plot.y_range[1]
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pk, qk in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if pk == 0:
            if qk < 0:
                t0, t1 = 1.0, 0.0
            continue
        t = qk / pk
        if pk < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
    if t0 >= t1:
        return Line(plot.point(*p), plot.point(*p) + [1e-3, 0, 0], color=colour, stroke_width=4)
    start = (p[0] + t0 * dx, p[1] + t0 * dy)
    end = (p[0] + t1 * dx, p[1] + t1 * dy)
    return Line(plot.point(*start), plot.point(*end), color=colour, stroke_width=4)


def _clip_polygon(points, inside, cross):
    """Sutherland-Hodgman: keep the part of a polygon on one side of a line."""
    out = []
    for i, current in enumerate(points):
        previous = points[i - 1]
        if inside(current):
            if not inside(previous):
                out.append(cross(previous, current))
            out.append(current)
        elif inside(previous):
            out.append(cross(previous, current))
    return out


def _region(plot, locus: Locus, box) -> VMobject | None:
    if not _has_region(locus):
        return None
    box_polygon = Polygon(*box)
    if locus.kind == "circle":
        circle = _boundary(plot, locus, style.AREA_COLOUR).copy()
        if locus.relation in ("<", "<="):
            return circle
        return Difference(box_polygon, circle)
    a = np.array(locus.a, dtype=float)
    corners = [
        np.array([plot.x_range[0], plot.y_range[0]]),
        np.array([plot.x_range[1], plot.y_range[0]]),
        np.array([plot.x_range[1], plot.y_range[1]]),
        np.array([plot.x_range[0], plot.y_range[1]]),
    ]
    if locus.kind == "bisector":
        b = np.array(locus.b, dtype=float)
        nearer_a = locus.relation in ("<", "<=")

        def inside(p):
            closer = np.linalg.norm(p - a) <= np.linalg.norm(p - b)
            return closer if nearer_a else not closer

        mid, d = (a + b) / 2, b - a

        def cross(p, q):
            t = np.dot(mid - p, d) / np.dot(q - p, d)
            return p + t * (q - p)

        kept = _clip_polygon(corners, inside, cross)
    else:
        low, high = float(_angle(locus.angle)), float(_angle(locus.angle_2))
        ts = np.linspace(low, high, 60)
        fan = [a] + [a + REACH * np.array([math.cos(t), math.sin(t)]) for t in ts]
        kept = fan
        for edge in range(4):
            c0, c1 = corners[edge], corners[(edge + 1) % 4]
            direction = c1 - c0

            def inside(p, c0=c0, direction=direction):
                return direction[0] * (p[1] - c0[1]) - direction[1] * (p[0] - c0[0]) >= 0

            def cross(p, q, c0=c0, direction=direction):
                n = np.array([-direction[1], direction[0]])
                t = np.dot(c0 - p, n) / np.dot(q - p, n)
                return p + t * (q - p)

            kept = _clip_polygon(kept, inside, cross)
    if len(kept) < 3:
        return None
    return Polygon(*(plot.point(*p) for p in kept))


class _Work:
    def __init__(self, params: ComplexLociParams):
        self.params = params
        self.equations = [self._equation(locus) for locus in params.loci]
        self.meets = []
        equalities = [
            item for item in params.loci if item.relation == "=" and item.kind != "sector"
        ]
        if len(params.loci) == 2 and len(equalities) == 2:
            solutions = sp.solve(self.equations, [X, Y], dict=True)
            for s in solutions:
                x, y = sp.nsimplify(s[X]), sp.nsimplify(s[Y])
                if x.is_real and y.is_real and all(self._on(locus, x, y) for locus in params.loci):
                    self.meets.append((x, y))

    def _equation(self, locus: Locus):
        p, q = exact(locus.a[0]), exact(locus.a[1])
        if locus.kind == "circle":
            return (X - p) ** 2 + (Y - q) ** 2 - exact(locus.r) ** 2
        if locus.kind == "bisector":
            s, t = exact(locus.b[0]), exact(locus.b[1])
            return sp.expand((X - p) ** 2 + (Y - q) ** 2 - (X - s) ** 2 - (Y - t) ** 2)
        angle = _angle(locus.angle)
        return sp.expand((Y - q) * sp.cos(angle) - (X - p) * sp.sin(angle))

    def _on(self, locus: Locus, x, y) -> bool:
        if locus.kind != "half_line":
            return True
        angle = _angle(locus.angle)
        dx, dy = x - exact(locus.a[0]), y - exact(locus.a[1])
        if dx == 0 and dy == 0:
            return False
        return bool(sp.simplify(sp.cos(angle) * dx + sp.sin(angle) * dy) > 0)

    def locus_latex(self, locus: Locus) -> str:
        rel = {"=": "=", "<": "<", "<=": r"\le", ">": ">", ">=": r"\ge"}[locus.relation]
        if locus.kind == "circle":
            return rf"|{_minus_z(locus.a)}| {rel} {latex_value(exact(locus.r))}"
        if locus.kind == "bisector":
            return rf"|{_minus_z(locus.a)}| {rel} |{_minus_z(locus.b)}|"
        if locus.kind == "half_line":
            return rf"\arg({_minus_z(locus.a)}) = {_pi(_angle(locus.angle))}"
        low, high = _pi(_angle(locus.angle)), _pi(_angle(locus.angle_2))
        return rf"{low} \le \arg({_minus_z(locus.a)}) \le {high}"

    def title_latex(self) -> str:
        return r",\quad ".join(self.locus_latex(item) for item in self.params.loci)

    def rows(self) -> list[tuple[str, object]]:
        rows = []
        for i, (locus, equation) in enumerate(zip(self.params.loci, self.equations, strict=True)):
            colour = COLOURS[i]
            a = _c(locus.a)
            p, q = exact(locus.a[0]), exact(locus.a[1])
            if locus.kind == "circle":
                words = (
                    rf"\text{{Circle, centre }}{a}\text{{, radius }}{latex_value(exact(locus.r))}"
                )
                cartesian = (
                    rf"{_shifted('x', p)}^2 + {_shifted('y', q)}^2 = "
                    rf"{latex_value(exact(locus.r) ** 2)}"
                )
            elif locus.kind == "bisector":
                words = rf"\text{{Perpendicular bisector of }}{a}\text{{ and }}{_c(locus.b)}"
                cartesian = _line_latex(equation)
            elif locus.kind == "half_line":
                words = rf"\text{{Half-line from }}{a}\text{{ at angle }}{_pi(_angle(locus.angle))}"
                cartesian = _line_latex(equation)
            else:
                words = rf"\text{{Sector from }}{a}\text{{, between two half-lines}}"
                low, high = _pi(_angle(locus.angle)), _pi(_angle(locus.angle_2))
                cartesian = rf"{low} \le \theta \le {high}"
            rows += [(words, colour), (cartesian, None)]
        if self.meets:
            rows.append((r"\text{Solve together:}", None))
            rows.append((self.answer_latex(), style.HIGHLIGHT_COLOUR))
        return rows

    def answer_latex(self) -> str:
        if self.meets:
            return "z = " + r",\ ".join(_c((x, y)) for x, y in self.meets)
        if any(_has_region(item) for item in self.params.loci):
            return r"\text{the shaded region}"
        if len(self.params.loci) == 2:
            return r"\text{the loci do not meet}"
        only = self.params.loci[0]
        if only.kind == "circle":
            radius = latex_value(exact(only.r))
            return rf"\text{{circle, centre }}{_c(only.a)}\text{{, radius }}{radius}"
        return _line_latex(self.equations[0])


def _c(parts) -> str:
    x, y = (sp.nsimplify(v) if not isinstance(v, float) else exact(v) for v in parts)
    re_tex = _num(x)
    if y == 0:
        return re_tex
    im_tex = {1: "i", -1: "-i"}.get(y, f"{_num(y)}i")
    if x == 0:
        return im_tex
    return f"{re_tex} {'-' if y < 0 else '+'} {im_tex.lstrip('-')}"


def _shifted(name: str, value) -> str:
    """(x - 2), (x + 1), or x for 0."""
    if value == 0:
        return name
    sign = "-" if value > 0 else "+"
    return rf"({name} {sign} {latex_value(abs(value))})"


def _line_latex(equation) -> str:
    """A line's equation as y = mx + c, or x = k when it is vertical."""
    if equation.has(Y):
        return f"y = {sp.latex(sp.expand(sp.solve(equation, Y)[0]))}"
    return f"x = {sp.latex(sp.solve(equation, X)[0])}"


def _num(v) -> str:
    v = sp.nsimplify(v)
    if v.is_Rational:
        return latex_value(v)
    return sp.latex(v) if sp.count_ops(v) <= 4 else format_sf(v)


def _minus_z(parts) -> str:
    """z - a written simply: z, z - 2, z + 2i, z - (1 + i)."""
    x, y = exact(parts[0]), exact(parts[1])
    if x == 0 and y == 0:
        return "z"
    if x == 0 or y == 0:
        text = _c((-x, -y))
        return f"z - {text[1:]}" if text.startswith("-") else f"z + {text}"
    return rf"z - ({_c(parts)})"


def _paren(text: str) -> str:
    return rf"({text})" if (" " in text or text.startswith("-")) else text


def _pi(angle) -> str:
    return latex_with_pi(angle, approx=False) if angle != 0 else "0"


def _words(locus: Locus) -> str:
    if locus.kind == "circle":
        return "Distance from the centre equal to r: a circle" + (
            ""
            if locus.relation == "="
            else "; the inequality shades its inside"
            if locus.relation in ("<", "<=")
            else "; the inequality shades its outside"
        )
    if locus.kind == "bisector":
        return "Equally far from two points: the perpendicular bisector of the line joining them"
    if locus.kind == "half_line":
        return "Constant argument from a point: a half-line starting there"
    return "Arguments between two angles: the sector between two half-lines"


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
