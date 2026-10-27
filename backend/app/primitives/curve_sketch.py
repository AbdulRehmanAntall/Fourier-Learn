"""CurveSketch: a curve sketched with its key features labelled as they appear: intercepts,
turning points and asymptotes (4024 2.11; AM 4.4, 6.1; PRIMITIVES.md #20).

Works for the graphs O Level asks candidates to recognise and sketch: linear, quadratic, cubic,
reciprocal (k/x, k/x²) and exponential (ab^x + c), and sums of them. SymPy finds the features:
the roots of f and of f' (exactly for rational functions, by bisection otherwise), whether each
turning point is a maximum or a minimum, the vertical asymptotes where f is unbounded, and the
horizontal ones from the limits at ±∞.
"""

from typing import Annotated

import numpy as np
import sympy as sp
from manim import DashedLine, Dot
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.analysis import samples, vertical_asymptotes, zeros
from app.primitives.plotting import curve, label, make_plot, place_label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    format_value,
    latex_value,
    parse_expression,
    written_latex,
)

X = sp.Symbol("x", real=True)
Coordinate = Annotated[float, Field(ge=-20, le=20)]
MAX_FEATURES = 4


class CurveSketchParams(PrimitiveParams):
    expression: str = Field(min_length=1, max_length=120, description="f(x), e.g. x**3 - 3*x")
    x_min: Coordinate
    x_max: Coordinate


class CurveSketch(StagedPrimitive[CurveSketchParams]):
    primitive_id = "CurveSketch"
    version = "1"
    topic = "Algebra and graphs"
    params_model = CurveSketchParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("axes", "*"),
            ("curve", "*"),
            ("asymptote_*", "*"),
            ("root_*", "root_*"),
            ("root_*", "intercept*"),
            ("turning_*", "root_*"),
            ("turning_*", "intercept*"),
        ],
    )

    def default_params(self) -> CurveSketchParams:
        return CurveSketchParams(expression="x**3 - 3*x", x_min=-2.5, x_max=2.5)

    def validate(self, params: CurveSketchParams) -> list[PredicateFailure]:
        try:
            f = parse_expression(params.expression, {"x"})
        except ExpressionError as error:
            return [_failure("parsing", "expression_parses", str(error), "expression")]
        if params.x_min >= params.x_max:
            return [
                _failure("consistency", "interval_ordered", "x_min must be below x_max", "x_min")
            ]
        if f.is_number:
            message = "f must depend on x"
            return [_failure("consistency", "not_constant", message, "expression")]
        values = samples(f, params.x_min, params.x_max)
        if np.isfinite(values[1]).mean() < 0.8:
            message = "f is not real on most of the interval"
            return [_failure("domain", "real_on_interval", message, "expression", "x_min", "x_max")]
        return []

    def computed_values(self, params: CurveSketchParams) -> dict[str, str]:
        sketch = _Sketch(params)
        values = {
            "roots": ", ".join(format_value(r) for r in sketch.roots) or "none",
            "number_of_roots": str(len(sketch.roots)),
        }
        if sketch.y_intercept is not None:
            values["y_intercept"] = format_value(sketch.y_intercept)
        for i, (x, y, kind) in enumerate(sketch.turning, start=1):
            values[f"turning_{i}"] = f"({format_value(x)}, {format_value(y)})"
            values[f"turning_{i}_kind"] = kind
        for i, x in enumerate(sketch.vertical, start=1):
            values[f"vertical_asymptote_{i}"] = f"x = {format_value(x)}"
        if sketch.horizontal is not None:
            values["horizontal_asymptote"] = f"y = {format_value(sketch.horizontal)}"
        return values

    def build(self, params: CurveSketchParams, level):
        sketch = _Sketch(params)
        f = sketch.numeric
        plot = make_plot(self.layout.region, [params.x_min, params.x_max], sketch.y_values())
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "equation": text_line(f"y = {written_latex(params.expression)}", plot.upper),
            "curve": curve(plot, f, params.x_min, params.x_max),
        }
        obstacles = plot.obstacles()
        paths = [parts["curve"], *plot.axis_lines()]
        for i, x in enumerate(sketch.vertical, start=1):
            line = DashedLine(
                plot.point(float(x), plot.y_range[0]),
                plot.point(float(x), plot.y_range[1]),
                color=style.SECANT_COLOUR,
            )
            parts[f"asymptote_v{i}"] = line
            paths.append(line)
        if sketch.horizontal is not None:
            line = DashedLine(
                plot.point(plot.x_range[0], float(sketch.horizontal)),
                plot.point(plot.x_range[1], float(sketch.horizontal)),
                color=style.SECANT_COLOUR,
            )
            parts["asymptote_h"] = line
            paths.append(line)

        points = []
        for i, root in enumerate(sketch.roots, start=1):
            points.append(
                (f"root_{i}", float(root), 0.0, rf"({latex_value(root)},\ 0)", style.POINT_COLOUR)
            )
        if sketch.y_intercept is not None:
            points.append(
                (
                    "intercept",
                    0.0,
                    float(sketch.y_intercept),
                    rf"(0,\ {latex_value(sketch.y_intercept)})",
                    style.RISE_COLOUR,
                )
            )
        for i, (x, y, _) in enumerate(sketch.turning, start=1):
            points.append(
                (
                    f"turning_{i}",
                    float(x),
                    float(y),
                    rf"({latex_value(x)},\ {latex_value(y)})",
                    style.TANGENT_COLOUR,
                )
            )
        for name, x, y, _, colour in points:
            parts[name] = Dot(plot.point(x, y), color=colour)
            obstacles.append(parts[name])
        for name, x, y, tex, colour in points:
            text = label(tex, colour=colour)
            parts[f"{name}_label"] = place_label(
                text, plot.point(x, y), plot.plot_box, obstacles, paths, wide=True
            )
            obstacles.append(text)
        for i, x in enumerate(sketch.vertical, start=1):
            text = label(f"x = {latex_value(x)}", colour=style.SECANT_COLOUR)
            anchor = plot.point(float(x), plot.y_range[1]) + np.array([0, -0.3, 0])
            parts[f"asymptote_v{i}_label"] = place_label(
                text, anchor, plot.plot_box, obstacles, paths, wide=True
            )
            obstacles.append(text)
        if sketch.horizontal is not None:
            text = label(f"y = {latex_value(sketch.horizontal)}", colour=style.SECANT_COLOUR)
            anchor = plot.point(plot.x_range[1], float(sketch.horizontal)) + np.array([-0.4, 0, 0])
            parts["asymptote_h_label"] = place_label(
                text, anchor, plot.plot_box, obstacles, paths, wide=True
            )
        return parts

    def stages(self, params: CurveSketchParams, level) -> list[Stage]:
        sketch = _Sketch(params)
        intercepts = [
            n for i in range(1, len(sketch.roots) + 1) for n in (f"root_{i}", f"root_{i}_label")
        ]
        if sketch.y_intercept is not None:
            intercepts += ["intercept", "intercept_label"]
        turning = [
            n
            for i in range(1, len(sketch.turning) + 1)
            for n in (f"turning_{i}", f"turning_{i}_label")
        ]
        asymptotes = [
            n
            for i in range(1, len(sketch.vertical) + 1)
            for n in (f"asymptote_v{i}", f"asymptote_v{i}_label")
        ]
        if sketch.horizontal is not None:
            asymptotes += ["asymptote_h", "asymptote_h_label"]
        kinds = sorted({kind for _, _, kind in sketch.turning})
        steps = [
            stage("axes", "Draw and label the axes", 1.5, ["axes", "x_label", "y_label"]),
            stage("equation", "Show the equation of the curve", 1.5, ["equation"]),
            stage("curve", "Sketch the curve from left to right", 3.0, ["curve"]),
        ]
        if intercepts:
            steps.append(
                stage(
                    "intercepts",
                    "Mark where the curve crosses the axes",
                    2.5,
                    intercepts,
                    emphasise=[n for n in intercepts if not n.endswith("label")],
                )
            )
        if turning:
            steps.append(
                stage(
                    "turning",
                    "Mark the turning points: " + " and ".join(f"a {k}" for k in kinds),
                    2.5,
                    turning,
                    emphasise=[n for n in turning if not n.endswith("label")],
                )
            )
        if asymptotes:
            steps.append(
                stage(
                    "asymptotes",
                    "Draw the asymptotes: lines the curve gets closer and closer to but never "
                    "meets",
                    2.5,
                    asymptotes,
                )
            )

        def standard(s):
            out = [combine("graph", "Draw the axes and sketch the curve", 3.0, *s[:3])]
            features = s[3:]
            if len(features) == 3:
                out += [
                    combine("points", "Mark the intercepts and turning points", 3.0, *features[:2]),
                    features[2],
                ]
            else:
                out += features
            return out

        def concise(s):
            out = [combine("graph", "Sketch the curve", 3.0, *s[:3])]
            if len(s) > 3:
                out.append(combine("features", "Label its key features", 3.0, *s[3:]))
            return out

        return by_level(level, steps, standard, concise)


class _Sketch:
    """The features of y = f(x) on [x_min, x_max]."""

    def __init__(self, params: CurveSketchParams):
        self.params = params
        self.f = sp.nsimplify(parse_expression(params.expression, {"x"}), rational=True)
        self.numeric = sp.lambdify(X, self.f, "math")
        lo, hi = params.x_min, params.x_max
        self.vertical = vertical_asymptotes(self.f, lo, hi)
        self.roots = zeros(self.f, lo, hi, self.vertical)[:MAX_FEATURES]
        self.y_intercept = None
        if lo <= 0 <= hi:
            value = self.f.subs(X, 0)
            if value.is_real and value.is_finite and all(r != 0 for r in self.roots):
                self.y_intercept = sp.nsimplify(value)
        derivative = sp.diff(self.f, X)
        self.turning = []
        for x in zeros(derivative, lo, hi, self.vertical)[:MAX_FEATURES]:
            if x in (lo, hi):
                continue
            kind = _kind(self.f, derivative, x)
            if kind:
                y = sp.nsimplify(self.f.subs(X, x)) if not isinstance(x, float) else self.numeric(x)
                self.turning.append((x, y, kind))
        # A root or the y-intercept that is also a turning point is labelled once, as the
        # turning point.
        turning_x = [float(x) for x, _, _ in self.turning]
        self.roots = [r for r in self.roots if all(abs(float(r) - t) > 1e-9 for t in turning_x)]
        if self.y_intercept is not None and any(abs(t) < 1e-9 for t in turning_x):
            self.y_intercept = None
        self.horizontal = None
        if not self.f.is_polynomial(X):
            for end in (sp.oo, -sp.oo):
                try:
                    limit = sp.limit(self.f, X, end)
                except (NotImplementedError, ValueError):
                    continue
                bounded = not isinstance(limit, sp.AccumBounds)  # sin(x) has no limit
                if bounded and limit.is_real and limit.is_finite:
                    self.horizontal = limit
                    break

    def y_values(self) -> list[float]:
        xs, ys = samples(self.f, self.params.x_min, self.params.x_max)
        # Near a vertical asymptote f is unbounded; the plot shows the rest of the curve, and
        # the curve is cut where it leaves the axes.
        near = 0.08 * (self.params.x_max - self.params.x_min)
        keep = np.isfinite(ys)
        for pole in self.vertical:
            keep &= np.abs(xs - float(pole)) > near
        finite = ys[keep] if keep.any() else ys[np.isfinite(ys)]
        low, high = finite.min(), finite.max()
        extra = [float(y) for _, y, _ in self.turning]
        if self.y_intercept is not None:
            extra.append(float(self.y_intercept))
        if self.horizontal is not None:
            extra.append(float(self.horizontal))
        values = [low, high, *extra]
        span = max(values) - min(values) or 2.0
        return [min(values) - 0.1 * span, max(values) + 0.1 * span]


def _kind(f: sp.Expr, derivative: sp.Expr, x) -> str | None:
    """Maximum, minimum, or None for a point of inflection, from the sign of f' either side."""
    numeric = sp.lambdify(X, derivative, "math")
    step = 1e-4
    try:
        left, right = numeric(float(x) - step), numeric(float(x) + step)
    except (ValueError, ZeroDivisionError):
        return None
    if left > 0 > right:
        return "maximum"
    if left < 0 < right:
        return "minimum"
    return None


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
