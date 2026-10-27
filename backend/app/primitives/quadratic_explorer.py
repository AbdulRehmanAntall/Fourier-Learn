"""QuadraticExplorer: the parabola y = ax² + bx + c with its roots, vertex, axis of symmetry,
y-intercept and discriminant (4024 2.5.5, 2.11; AM 2.1 to 2.5; PRIMITIVES.md #15).

The discriminant b² - 4ac decides the roots: two where the curve crosses the x-axis, one where it
touches it, none where it misses it. The vertex comes from the completed-square form
a(x - h)² + k, and the axis of symmetry is x = h. Every value is computed exactly by SymPy;
roots that are surds are shown exactly with a decimal beside them.
"""

from typing import Annotated

import sympy as sp
from manim import DashedLine, Dot
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import curve, label, make_plot, place_label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_value, latex_value, tidy_latex

X = sp.Symbol("x", real=True)
Coefficient = Annotated[float, Field(ge=-50, le=50)]


class QuadraticExplorerParams(PrimitiveParams):
    a: Coefficient = Field(description="Coefficient of x²; not 0")
    b: Coefficient = Field(description="Coefficient of x")
    c: Coefficient = Field(description="Constant term")


class QuadraticExplorer(StagedPrimitive[QuadraticExplorerParams]):
    primitive_id = "QuadraticExplorer"
    version = "1"
    topic = "Algebra and graphs"
    params_model = QuadraticExplorerParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("axes", "*"),
            ("curve", "*"),
            ("axis_line", "*"),
            ("root_*", "root_*"),
            ("vertex", "root_*"),
            ("intercept", "root_*"),
        ],
    )

    def default_params(self) -> QuadraticExplorerParams:
        return QuadraticExplorerParams(a=1, b=-2, c=-3)

    def validate(self, params: QuadraticExplorerParams) -> list[PredicateFailure]:
        if params.a == 0:
            return [
                PredicateFailure(
                    kind="consistency",
                    predicate="a_nonzero",
                    message="a must not be 0, or the graph is a straight line",
                    parameters=["a"],
                )
            ]
        return []

    def computed_values(self, params: QuadraticExplorerParams) -> dict[str, str]:
        q = _Quadratic(params)
        values = {
            "discriminant": format_value(q.discriminant),
            "number_of_roots": str(len(q.roots)),
            "vertex_x": format_value(q.h),
            "vertex_y": format_value(q.k),
            "vertex": f"({format_value(q.h)}, {format_value(q.k)})",
            "axis_of_symmetry": f"x = {format_value(q.h)}",
            "y_intercept": format_value(q.c),
            "turning_point": "minimum" if q.a > 0 else "maximum",
            "completed_square": q.completed_text(),
        }
        for i, root in enumerate(q.roots, start=1):
            values[f"root_{i}"] = format_value(root)
        return values

    def build(self, params: QuadraticExplorerParams, level):
        q = _Quadratic(params)
        f = sp.lambdify(X, q.f, "math")
        lo, hi = q.x_interval()
        samples = [lo + (hi - lo) * i / 60 for i in range(61)]
        plot = make_plot(self.layout.region, [lo, hi], [f(x) for x in samples])
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "equation": text_line(f"y = {tidy_latex(q.f)}", plot.upper),
            "curve": curve(plot, f, lo, hi),
        }
        d = q.discriminant
        verdict = (
            r"> 0:\ \text{two roots}"
            if d > 0
            else (r"= 0:\ \text{one repeated root}" if d == 0 else r"< 0:\ \text{no real roots}")
        )
        parts["discriminant"] = text_line(
            rf"b^2 - 4ac = {latex_value(d)} {verdict}", plot.lower, size=34
        )
        parts["completed"] = text_line(f"y = {q.completed_latex()}", plot.lower)

        obstacles = plot.obstacles()
        paths = [parts["curve"], *plot.axis_lines()]
        vertex = plot.point(float(q.h), float(q.k))
        axis_line = DashedLine(
            plot.point(float(q.h), plot.y_range[0]),
            plot.point(float(q.h), plot.y_range[1]),
            color=style.SECANT_COLOUR,
        )
        parts["axis_line"] = axis_line
        paths.append(axis_line)
        parts["vertex"] = Dot(vertex, color=style.TANGENT_COLOUR)
        obstacles.append(parts["vertex"])

        for i, root in enumerate(q.roots if d > 0 else [], start=1):
            dot = Dot(plot.point(float(root), 0), color=style.POINT_COLOUR)
            parts[f"root_{i}"] = dot
            obstacles.append(dot)
        for i, root in enumerate(q.roots if d > 0 else [], start=1):
            text = label(rf"({latex_value(root)},\ 0)", colour=style.POINT_COLOUR)
            parts[f"root_{i}_label"] = place_label(
                text, plot.point(float(root), 0), plot.plot_box, obstacles, paths, wide=True
            )
            obstacles.append(text)
        vertex_text = label(
            rf"({latex_value(q.h)},\ {latex_value(q.k)})", colour=style.TANGENT_COLOUR
        )
        parts["vertex_label"] = place_label(
            vertex_text, vertex, plot.plot_box, obstacles, paths, wide=True
        )
        obstacles.append(vertex_text)
        axis_text = label(f"x = {latex_value(q.h)}", colour=style.SECANT_COLOUR)
        top = plot.point(float(q.h), plot.y_range[1])
        parts["axis_label"] = place_label(
            axis_text, top + [0, -0.35, 0], plot.plot_box, obstacles, paths, wide=True
        )
        obstacles.append(axis_text)
        if q.has_separate_intercept():
            point = plot.point(0, float(q.c))
            parts["intercept"] = Dot(point, color=style.RISE_COLOUR)
            text = label(rf"(0,\ {latex_value(q.c)})", colour=style.RISE_COLOUR)
            parts["intercept_label"] = place_label(
                text, point, plot.plot_box, obstacles, paths, wide=True
            )
        return parts

    def stages(self, params: QuadraticExplorerParams, level) -> list[Stage]:
        q = _Quadratic(params)
        roots = [n for i in range(1, len(q.roots) + 1) for n in (f"root_{i}", f"root_{i}_label")]
        roots = roots if q.discriminant > 0 else []
        root_words = {
            True: "Mark where the curve crosses the x-axis: the roots",
            False: "The curve does not cross the x-axis",
        }[bool(roots)]
        steps = [
            stage("axes", "Draw and label the axes", 1.5, ["axes", "x_label", "y_label"]),
            stage("equation", "Show the equation of the quadratic", 1.5, ["equation"]),
            stage("curve", "Draw the parabola", 2.5, ["curve"]),
            stage(
                "discriminant",
                "Work out the discriminant, b squared minus 4 a c, to count the roots",
                3.0,
                ["discriminant"],
                emphasise=["discriminant"],
            ),
            stage(
                "roots", root_words, 2.0, roots, emphasise=[r for r in roots if "label" not in r]
            ),
            stage(
                "vertex",
                f"Mark the vertex, the {'lowest' if q.a > 0 else 'highest'} point of the curve",
                2.0,
                ["vertex", "vertex_label"],
                emphasise=["vertex"],
            ),
            stage(
                "axis",
                "Draw the axis of symmetry through the vertex",
                2.0,
                ["axis_line", "axis_label"],
            ),
            stage(
                "completed",
                "Write the completed square form, which gives the vertex",
                2.5,
                morph=[("discriminant", "completed")],
            ),
        ]
        if q.has_separate_intercept():
            steps.append(
                stage(
                    "intercept",
                    "The curve crosses the y-axis at c",
                    1.5,
                    ["intercept", "intercept_label"],
                )
            )
        if not roots:
            steps = [s for s in steps if s.name != "roots"]
            # With no roots to mark, the discriminant step says so.

        def find(s, name):
            return next(x for x in s if x.name == name)

        def standard(s):
            out = [
                combine("graph", "Draw the axes and the parabola with its equation", 2.5, *s[:3])
            ]
            first = [find(s, "discriminant")] + [x for x in s if x.name == "roots"]
            out.append(combine("roots", "Use the discriminant to find the roots", 3.0, *first))
            out.append(
                combine(
                    "vertex",
                    "Complete the square to find the vertex and the axis of symmetry",
                    3.0,
                    find(s, "vertex"),
                    find(s, "axis"),
                    find(s, "completed"),
                )
            )
            out += [x for x in s if x.name == "intercept"]
            return out

        def concise(s):
            graph = combine("graph", "Draw the parabola", 2.5, *s[:3])
            rest = [x for x in s[3:] if x.name != "intercept"]
            features = combine(
                "features", "Show the roots, the vertex and the axis of symmetry", 3.5, *rest
            )
            intercept = [x for x in s if x.name == "intercept"]
            if intercept:
                features = combine(
                    features.name,
                    features.description + ", and the y-intercept",
                    3.5,
                    features,
                    intercept[0],
                )
            return [graph, features]

        return by_level(level, steps, standard, concise)


class _Quadratic:
    def __init__(self, params: QuadraticExplorerParams):
        self.a, self.b, self.c = exact(params.a), exact(params.b), exact(params.c)
        self.f = self.a * X**2 + self.b * X + self.c
        self.discriminant = self.b**2 - 4 * self.a * self.c
        self.h = -self.b / (2 * self.a)
        self.k = self.f.subs(X, self.h)
        if self.discriminant > 0:
            root = sp.sqrt(self.discriminant)
            self.roots = sorted(
                [(-self.b - root) / (2 * self.a), (-self.b + root) / (2 * self.a)], key=float
            )
        elif self.discriminant == 0:
            self.roots = [self.h]
        else:
            self.roots = []

    def x_interval(self) -> tuple[float, float]:
        h = float(self.h)
        spread = 3.0
        if self.roots:
            spread = max(spread, max(abs(float(r) - h) for r in self.roots) + 1.5)
        lo, hi = min(h - spread, -0.5), max(h + spread, 0.5)
        return max(lo, -40.0), min(hi, 40.0)

    def has_separate_intercept(self) -> bool:
        return self.c != 0 and self.h != 0

    def completed_latex(self) -> str:
        inner = tidy_latex(X - self.h)
        square = rf"\left({inner}\right)^2" if self.h != 0 else "x^2"
        lead = "" if self.a == 1 else ("-" if self.a == -1 else latex_value(self.a))
        tail = (
            ""
            if self.k == 0
            else (f" + {latex_value(self.k)}" if self.k > 0 else f" - {latex_value(-self.k)}")
        )
        return f"{lead}{square}{tail}"

    def completed_text(self) -> str:
        return str(self.a * (X - self.h) ** 2 + self.k)
