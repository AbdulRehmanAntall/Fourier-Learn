"""VectorLines3D: lines r = a + λb in three dimensions: whether two lines are parallel, meet or
are skew (and where they meet), the angle between two lines from the scalar product, and the
foot of the perpendicular from a point to a line (9709 3.7).

Two lines meet if one pair of λ and μ makes all three components equal: two components give
λ and μ, and the third must then agree, or the lines are skew (unless their directions are
parallel). The angle between the lines is the angle between their directions,
cos θ = |b·d| / (|b||d|), taken acute. The foot F of the perpendicular from P is the point
a + λb with PF·b = 0. The picture is an oblique projection of the axes, the lines and the
points; all the arithmetic is exact (SymPy).
"""

from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import Arrow, DashedLine, Dot, Line, MathTex, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import Diagram, label, stack_lines
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, latex_approx, latex_value

Component = Annotated[float, Field(ge=-20, le=20)]
Vector3 = tuple[Component, Component, Component]
# where one unit along each axis goes on the page: x comes out of the page down and left
PROJECTION = np.array([[-0.55, -0.4], [1.0, 0.0], [0.0, 1.0]])


class VectorLines3DParams(PrimitiveParams):
    kind: Literal["intersection", "angle", "foot"]
    a: Vector3 = Field(description="A point on the first line")
    b: Vector3 = Field(description="The first line's direction")
    c: Vector3 | None = Field(default=None, description="A point on the second line")
    d: Vector3 | None = Field(default=None, description="The second line's direction")
    p: Vector3 | None = Field(default=None, description="For foot: the point P")


class VectorLines3D(StagedPrimitive[VectorLines3DParams]):
    primitive_id = "VectorLines3D"
    version = "1"
    topic = "Vectors"
    params_model = VectorLines3DParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[("axes", "*"), ("line_*", "*"), ("perpendicular", "*"), ("dot_*", "*")],
    )

    def default_params(self) -> VectorLines3DParams:
        return VectorLines3DParams(
            kind="intersection", a=(1, 2, 0), b=(1, 0, 1), c=(3, 1, 1), d=(0, 1, 1)
        )

    def validate(self, params: VectorLines3DParams) -> list[PredicateFailure]:
        if all(v == 0 for v in params.b) or (
            params.d is not None and all(v == 0 for v in params.d)
        ):
            return [
                _failure("direction_nonzero", "a direction cannot be the zero vector", "b", "d")
            ]
        if params.kind in ("intersection", "angle") and (params.c is None or params.d is None):
            return [_failure("second_line", "give the second line, c and d", "c", "d")]
        if params.kind == "foot" and params.p is None:
            return [_failure("point_given", "give the point p", "p")]
        if params.kind == "foot" and _on_line(params):
            message = "P is on the line, so it is its own foot"
            return [_failure("point_off_line", message, "p")]
        return []

    def computed_values(self, params: VectorLines3DParams) -> dict[str, str]:
        w = _Work(params)
        return {k: str(v) for k, v in w.values.items()}

    def build(self, params: VectorLines3DParams, level):
        w = _Work(params)
        lines = w.segments()
        points = [pt for seg in lines.values() for pt in seg] + [np.zeros(3)]
        points += [np.array(v, dtype=float) for v in w.marked.values()]
        reach = max(np.abs(np.array(points)).max(), 1.0)
        axis_ends = {name: reach * 1.15 * np.eye(3)[i] for i, name in enumerate("xyz")}
        flat = [_project(p) for p in [*points, *axis_ends.values()]]
        diagram = Diagram(
            flat, style.region_box(style.GRAPH_REGION).shrink(style.PADDING), margin=0.5
        )

        def at(v):
            x, y = _project(np.array(v, dtype=float))
            return diagram.p(x, y)

        origin = at((0, 0, 0))
        axes = VGroup()
        for name, end in axis_ends.items():
            axes.add(
                Arrow(
                    origin,
                    at(end),
                    buff=0,
                    stroke_width=2,
                    color=style.TEXT_COLOUR,
                    tip_length=0.15,
                )
            )
            axes.add(
                MathTex(name, font_size=28).next_to(at(end), _unit(at(end) - origin), buff=0.1)
            )
        parts = {"axes": axes}
        colours = {"line_1": style.CURVE_COLOUR, "line_2": style.RUN_COLOUR}
        for name, (start, end) in lines.items():
            parts[name] = Line(at(start), at(end), color=colours[name], stroke_width=4)
            parts[f"{name}_label"] = label(
                "l_1" if name == "line_1" else "l_2", colour=colours[name]
            ).next_to(at(end), _unit(at(end) - at(start)), buff=0.12)
        for name, v in w.marked.items():
            parts[f"dot_{name}"] = Dot(at(v), color=style.POINT_COLOUR)
            parts[f"{name}_label"] = label(name, colour=style.POINT_COLOUR).next_to(
                at(v), [0.6, 0.8, 0], buff=0.08
            )
        if params.kind == "foot":
            parts["perpendicular"] = DashedLine(
                at(w.marked["P"]), at(w.marked["F"]), color=style.TANGENT_COLOUR
            )
        rows = w.rows()
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: VectorLines3DParams, level) -> list[Stage]:
        w = _Work(params)
        n = len(w.rows())
        line_parts = [p for name in w.segments() for p in (name, f"{name}_label")]
        dots = [p for name in w.marked for p in (f"dot_{name}", f"{name}_label")]
        intro = stage(
            "lines",
            "The lines: a point on each, then a multiple of the direction",
            3.0,
            ["axes", *line_parts, "row_1"],
        )
        if params.kind == "intersection":
            steps = [
                intro,
                stage(
                    "equate",
                    "If they meet, the two position vectors are equal there",
                    3.0,
                    ["row_2"],
                ),
                stage(
                    "solve",
                    "Solve two of the components for lambda and mu",
                    3.5,
                    [f"row_{i}" for i in range(3, n)],
                ),
                stage(
                    "check",
                    w.verdict_words(),
                    3.5,
                    [f"row_{n}", *dots],
                    emphasise=[d for d in dots if d.startswith("dot")],
                ),
            ]
        elif params.kind == "angle":
            steps = [
                intro,
                stage("dot", "Use the directions: their scalar product", 3.0, ["row_2", "row_3"]),
                stage(
                    "angle",
                    "Divide by the lengths: the cosine of the angle, taken acute",
                    3.5,
                    [f"row_{i}" for i in range(4, n + 1)],
                    emphasise=[f"row_{n}"],
                ),
            ]
        else:
            steps = [
                intro,
                stage("point", "The point P, off the line", 2.0, ["dot_P", "P_label"]),
                stage(
                    "general",
                    "F is on the line, so F is a plus lambda b for some lambda",
                    3.0,
                    ["row_2", "row_3"],
                ),
                stage(
                    "perpendicular",
                    "PF is perpendicular to the line: its scalar product with b is zero",
                    3.5,
                    [f"row_{i}" for i in range(4, n)],
                ),
                stage(
                    "foot",
                    "So the foot of the perpendicular",
                    3.0,
                    ["dot_F", "F_label", "perpendicular", f"row_{n}"],
                    emphasise=["dot_F"],
                ),
            ]

        def standard(s):
            return list(s)

        def concise(s):
            return (
                [s[0], combine("work", "Work it out", 4.5, *s[1:-1]), s[-1]]
                if len(s) > 3
                else [s[0], combine("work", s[-1].description, 4.5, *s[1:])]
            )

        return by_level(level, steps, standard, concise)


def _project(v) -> np.ndarray:
    return np.asarray(v, dtype=float) @ PROJECTION


def _unit(v) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n else np.array([1.0, 0, 0])


def _vec(values) -> sp.Matrix:
    return sp.Matrix([exact(v) for v in values])


def _col(m) -> str:
    entries = (sp.latex(v) if v.free_symbols else latex_value(v) for v in m)
    return r"\begin{pmatrix}" + r"\\".join(entries) + r"\end{pmatrix}"


def _on_line(params) -> bool:
    a, b, p = _vec(params.a), _vec(params.b), _vec(params.p)
    return (p - a).cross(b) == sp.zeros(3, 1)


class _Work:
    def __init__(self, params: VectorLines3DParams):
        self.params = params
        self.a, self.b = _vec(params.a), _vec(params.b)
        self.values: dict = {}
        self.marked: dict = {}
        self.lam_range = (-1.5, 2.5)
        if params.c is not None:
            self.c, self.d = _vec(params.c), _vec(params.d)
        getattr(self, f"_{params.kind}")()

    def _intersection(self):
        lam, mu = sp.symbols("lambda mu")
        eqs = list(self.a + lam * self.b - self.c - mu * self.d)
        self.eqs = eqs
        if self.b.cross(self.d) == sp.zeros(3, 1):
            same = (self.c - self.a).cross(self.b) == sp.zeros(3, 1)
            self.relation = "same" if same else "parallel"
            self.pair, self.solution = None, None
        else:
            self.pair = next(
                (i, j)
                for i, j in ((0, 1), (0, 2), (1, 2))
                if sp.Matrix([[self.b[i], -self.d[i]], [self.b[j], -self.d[j]]]).det() != 0
            )
            i, j = self.pair
            self.solution = sp.solve([eqs[i], eqs[j]], [lam, mu], dict=True)[0]
            k = 3 - i - j
            self.check = eqs[k].subs(self.solution)
            self.relation = "meet" if self.check == 0 else "skew"
            if self.relation == "meet":
                point = self.a + self.solution[lam] * self.b
                self.marked["X"] = [float(v) for v in point]
                self.values["point"] = tuple(point)
                self.lam_range = (
                    min(-1.0, float(self.solution[lam]) - 1),
                    max(2.0, float(self.solution[lam]) + 1),
                )
                self.mu_range = (
                    min(-1.0, float(self.solution[mu]) - 1),
                    max(2.0, float(self.solution[mu]) + 1),
                )
        self.values["relation"] = self.relation

    def _angle(self):
        dot = self.b.dot(self.d)
        lengths = sp.sqrt(self.b.dot(self.b)) * sp.sqrt(self.d.dot(self.d))
        self.dot, self.lengths = dot, lengths
        self.cos = sp.nsimplify(abs(dot) / lengths)
        self.theta = float(sp.deg(sp.acos(self.cos)))
        self.values["angle"] = f"{self.theta:.1f}"

    def _foot(self):
        p = _vec(self.params.p)
        self.lam = sp.nsimplify((p - self.a).dot(self.b) / self.b.dot(self.b))
        self.foot = self.a + self.lam * self.b
        self.p_vec = p
        self.distance = sp.sqrt((p - self.foot).dot(p - self.foot))
        self.marked["P"] = [float(v) for v in p]
        self.marked["F"] = [float(v) for v in self.foot]
        self.values["foot"] = tuple(self.foot)
        self.values["distance"] = self.distance
        self.lam_range = (min(-1.0, float(self.lam) - 1), max(2.0, float(self.lam) + 1))

    def segments(self) -> dict:
        lo, hi = self.lam_range
        out = {
            "line_1": (
                np.array(self.a + lo * self.b, dtype=float).ravel(),
                np.array(self.a + hi * self.b, dtype=float).ravel(),
            )
        }
        if self.params.kind in ("intersection", "angle"):
            mlo, mhi = getattr(self, "mu_range", (-1.5, 2.5))
            out["line_2"] = (
                np.array(self.c + mlo * self.d, dtype=float).ravel(),
                np.array(self.c + mhi * self.d, dtype=float).ravel(),
            )
        return out

    def verdict_words(self) -> str:
        return {
            "meet": "The third component agrees, so the lines meet",
            "skew": "The third component does not agree, and they are not parallel: skew",
            "parallel": "The directions are multiples of each other: the lines are parallel",
            "same": "Parallel, and a point of one lies on the other: the same line",
        }[self.relation]

    def rows(self) -> list[tuple[str, object]]:
        r1 = rf"\mathbf{{r}} = {_col(self.a)} + \lambda{_col(self.b)}"
        kind = self.params.kind
        if kind == "foot":
            p = self.p_vec
            general = self.a + sp.Symbol("lambda") * self.b
            return [
                (r1, style.CURVE_COLOUR),
                (rf"P = {_col(p)}", style.POINT_COLOUR),
                (rf"\overrightarrow{{PF}} = {_col(sp.simplify(general - p))}", None),
                (rf"\overrightarrow{{PF}}\cdot{_col(self.b)} = 0", None),
                (
                    rf"\lambda = {latex_value(self.lam)},\ |PF| = {latex_approx(self.distance)}",
                    None,
                ),
                (rf"F = {_col(self.foot)}", style.HIGHLIGHT_COLOUR),
            ]
        r2 = rf"\mathbf{{r}} = {_col(self.c)} + \mu{_col(self.d)}"
        if kind == "angle":
            return [
                (rf"{r1},\ {r2}", None),
                (rf"{_col(self.b)}\cdot{_col(self.d)} = {latex_value(self.dot)}", None),
                (rf"|\mathbf{{b}}||\mathbf{{d}}| = {latex_approx(self.lengths)}", None),
                (
                    rf"\cos\theta = \frac{{{latex_value(abs(self.dot))}}}"
                    rf"{{{sp.latex(self.lengths)}}}",
                    None,
                ),
                (rf"\theta = {self.theta:.1f}^\circ", style.HIGHLIGHT_COLOUR),
            ]
        rows = [
            (rf"{r1},\ {r2}", None),
            (rf"{_col(self.a)} + \lambda{_col(self.b)} = {_col(self.c)} + \mu{_col(self.d)}", None),
        ]
        if self.relation in ("parallel", "same"):
            rows.append((rf"{_col(self.d)} = {latex_value(self._ratio())}{_col(self.b)}", None))
            rows.append(
                (
                    r"\text{Parallel}" if self.relation == "parallel" else r"\text{The same line}",
                    style.HIGHLIGHT_COLOUR,
                )
            )
            return rows
        lam, mu = sp.symbols("lambda mu")
        i, j = self.pair
        rows.append((rf"{self._component(i)},\ {self._component(j)}", None))
        rows.append(
            (
                rf"\lambda = {latex_value(self.solution[lam])},\ "
                rf"\mu = {latex_value(self.solution[mu])}",
                None,
            )
        )
        k = 3 - i - j
        if self.relation == "meet":
            point = self.a + self.solution[lam] * self.b
            rows.append((rf"\text{{Third: }}{self._component(k)}\ \checkmark", None))
            rows.append((rf"\text{{They meet at }}{_col(point)}", style.HIGHLIGHT_COLOUR))
        else:
            left = self.a[k] + self.solution[lam] * self.b[k]
            right = self.c[k] + self.solution[mu] * self.d[k]
            rows.append((rf"\text{{Third: }}{self._component(k)}", None))
            rows.append(
                (
                    rf"{latex_value(left)} \ne {latex_value(right)}\text{{: skew}}",
                    style.HIGHLIGHT_COLOUR,
                )
            )
        return rows

    def _component(self, i: int) -> str:
        lam, mu = sp.symbols("lambda mu")
        return rf"{sp.latex(self.a[i] + lam * self.b[i])} = {sp.latex(self.c[i] + mu * self.d[i])}"

    def _ratio(self):
        for u, v in zip(self.b, self.d, strict=True):
            if u != 0:
                return v / u
        return 1


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
