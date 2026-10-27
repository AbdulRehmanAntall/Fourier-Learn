"""InequalityRegion: the region of the plane that satisfies linear inequalities in x and y
(4024 2.6; PRIMITIVES.md #16).

Each boundary line is drawn solid for ≤ or ≥ and broken for < or >, and the side that does not
satisfy the inequality is shaded, as O Level questions ask ("shade the unwanted region"); the
region R left unshaded is labelled. With shade="wanted" the region itself is shaded instead.
The regions are found exactly by clipping the plotted rectangle with each half-plane, and the
points with integer coordinates in R are counted by SymPy.
"""

import itertools
import math
import re
from typing import Annotated, Literal

import sympy as sp
from manim import DashedLine, Dot, Line, Polygon, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, make_plot, place_label, ring_candidates
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import ExpressionError, exact, format_number, parse_expression

X, Y = sp.Symbol("x", real=True), sp.Symbol("y", real=True)
Inequality = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=60)]
Bound = Annotated[float, Field(ge=-20, le=20)]
_OPERATOR = re.compile(r"(<=|>=|<|>)")
_TEX = {"<=": r"\leq", ">=": r"\geq", "<": "<", ">": ">"}


class InequalityRegionParams(PrimitiveParams):
    inequalities: list[Inequality] = Field(
        min_length=1,
        max_length=4,
        description='Linear inequalities in x and y, e.g. ["y <= 2*x + 1", "x > -1", "x + y < 6"]',
    )
    shade: Literal["unwanted", "wanted"] = Field(
        default="unwanted", description="Shade the side that fails each inequality, or R itself"
    )
    x_range: tuple[Bound, Bound] | None = Field(
        default=None, description="Plotted x interval; chosen from the lines if omitted"
    )
    y_range: tuple[Bound, Bound] | None = Field(
        default=None, description="Plotted y interval; chosen from the lines if omitted"
    )
    show_integer_points: bool = Field(
        default=False, description="Mark the points with integer coordinates inside R"
    )


class InequalityRegion(StagedPrimitive[InequalityRegionParams]):
    primitive_id = "InequalityRegion"
    version = "1"
    topic = "Algebra and graphs"
    params_model = InequalityRegionParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[
            ("axes", "*"),
            ("shade_*", "*"),
            ("line_*", "*"),
            ("region", "*"),
            ("points", "*"),
        ],
    )

    def default_params(self) -> InequalityRegionParams:
        return InequalityRegionParams(inequalities=["y <= 2*x + 1", "x + y < 6", "y >= 1"])

    def validate(self, params: InequalityRegionParams) -> list[PredicateFailure]:
        failures = []
        for i, text in enumerate(params.inequalities):
            try:
                _parse(text)
            except _Bad as bad:
                failures.append(
                    PredicateFailure(
                        kind="parsing",
                        predicate="inequality_parses",
                        message=str(bad),
                        parameters=[f"inequalities[{i}]"],
                    )
                )
        if failures:
            return failures
        for name in ("x_range", "y_range"):
            bounds = getattr(params, name)
            if bounds is not None and bounds[0] >= bounds[1]:
                return [_failure("consistency", "range_ordered", f"{name} must increase", name)]
        view = _view(params)
        if len(_region(params, view)) < 3:
            message = "no point of the plotted area satisfies every inequality"
            return [_failure("consistency", "region_not_empty", message, "inequalities")]
        return []

    def computed_values(self, params: InequalityRegionParams) -> dict[str, str]:
        view = _view(params)
        region = _region(params, view)
        points = _integer_points(params, view)
        values = {
            "integer_points": str(len(points)),
            "integer_point_list": ", ".join(f"({x}, {y})" for x, y in points[:20]),
            "vertices": ", ".join(
                f"({format_number(exact(round(x, 6)))}, {format_number(exact(round(y, 6)))})"
                for x, y in region
            ),
        }
        for i, text in enumerate(params.inequalities, start=1):
            values[f"boundary_{i}"] = _boundary_text(_parse(text))
            values[f"line_{i}_style"] = "broken" if _parse(text)[1] in "<>" else "solid"
        return values

    def build(self, params: InequalityRegionParams, level):
        view = _view(params)
        (x_lo, x_hi), (y_lo, y_hi) = view
        plot = make_plot(self.layout.region, [x_lo, x_hi], [y_lo, y_hi], equal=True)
        # Clip to the drawn axes, which may extend past the view to the next tick.
        box = ((plot.x_range[0], plot.x_range[1]), (plot.y_range[0], plot.y_range[1]))
        parts = {"axes": plot.axes, "x_label": plot.x_label, "y_label": plot.y_label}
        obstacles = plot.obstacles()
        lines = []
        for i, text in enumerate(params.inequalities, start=1):
            parsed = _parse(text)
            ends = _clip_line(parsed, box)
            start, end = plot.point(*ends[0]), plot.point(*ends[1])
            line_class = DashedLine if parsed[1] in "<>" else Line
            line = line_class(start, end, color=_colour(i), stroke_width=4)
            parts[f"line_{i}"] = line
            lines.append(line)
            side = _rectangle(box) if params.shade == "wanted" else _half_plane(parsed, box, False)
            if params.shade == "unwanted":
                parts[f"shade_{i}"] = Polygon(
                    *(plot.point(x, y) for x, y in side),
                    stroke_width=0,
                    fill_color=_colour(i),
                    fill_opacity=0.3,
                )
        if params.shade == "wanted":
            region = _region(params, box)
            parts["shade_region"] = Polygon(
                *(plot.point(x, y) for x, y in region),
                stroke_width=0,
                fill_color=style.AREA_COLOUR,
                fill_opacity=0.45,
            )
        paths = [*lines, *plot.axis_lines()]
        for i, text in enumerate(params.inequalities, start=1):
            parsed = _parse(text)
            ends = _clip_line(parsed, box)
            # Label near the end of the line that is furthest inside the plot box.
            anchor = plot.point(*_label_anchor(ends))
            tex = label(_inequality_latex(parsed), colour=_colour(i))
            parts[f"line_{i}_label"] = place_label(
                tex, anchor, plot.plot_box, obstacles, paths, wide=True
            )
            obstacles.append(tex)
        region = _region(params, box)
        cx = sum(x for x, _ in region) / len(region)
        cy = sum(y for _, y in region) / len(region)
        if params.show_integer_points:
            dots = [
                Dot(plot.point(x, y), radius=0.06, color=style.POINT_COLOUR)
                for x, y in _integer_points(params, view)
            ]
            parts["points"] = VGroup(*dots)
            obstacles.extend(dots)
        # The region is convex, so the mean of its corners lies inside it.
        centre = plot.point(cx, cy)
        r_label = label("R", size=style.FONT_SIZE)
        candidates = [centre, *ring_candidates(centre, r_label)[:32]]
        parts["region"] = style.place_clear(r_label, candidates, plot.plot_box, obstacles, paths)
        return parts

    def stages(self, params: InequalityRegionParams, level) -> list[Stage]:
        n = len(params.inequalities)
        axes = stage("axes", "Draw the x and y axes", 1.5, ["axes", "x_label", "y_label"])
        per_line = []
        for i, text in enumerate(params.inequalities, start=1):
            parsed = _parse(text)
            kind = (
                "a broken line, because the boundary is not included"
                if parsed[1] in "<>"
                else "a solid line, because the boundary is included"
            )
            line = stage(
                f"line_{i}",
                f"Draw the boundary {_boundary_text(parsed)} as {kind}",
                2.5,
                [f"line_{i}", f"line_{i}_label"],
            )
            if params.shade == "unwanted":
                shade = stage(
                    f"shade_{i}",
                    "Shade the side that does not satisfy the inequality",
                    2.0,
                    [f"shade_{i}"],
                    emphasise=[f"shade_{i}"],
                )
            else:
                shade = None
            per_line.append((line, shade))
        last = ["region"] + (["shade_region"] if params.shade == "wanted" else [])
        region_words = (
            "The region R left unshaded satisfies every inequality"
            if params.shade == "unwanted"
            else "Shade the region R that satisfies every inequality"
        )
        region = stage("region", region_words, 2.5, last, emphasise=["region"])
        steps = [axes] + [s for pair in per_line for s in pair if s is not None] + [region]
        if params.show_integer_points:
            steps.append(
                stage(
                    "points",
                    "Mark the points with whole-number coordinates inside R",
                    2.0,
                    ["points"],
                )
            )

        def standard(s):
            out = [axes]
            for i, (line, shade) in enumerate(per_line, start=1):
                pieces = [line] + ([shade] if shade else [])
                out.append(
                    combine(
                        f"inequality_{i}",
                        line.description + (", and shade the side that fails it" if shade else ""),
                        3.0,
                        *pieces,
                    )
                )
            out.append(region)
            if params.show_integer_points:
                out[-1] = combine(
                    "region", region_words + "; mark its whole-number points", 3.0, region, s[-1]
                )
            return out

        def concise(s):
            lines = [line for line, _ in per_line]
            shades = [shade for _, shade in per_line if shade]
            first = combine(
                "lines",
                f"Draw the {'boundary' if n == 1 else f'{n} boundaries'}",
                3.0,
                axes,
                *lines,
            )
            rest = [*shades, region] + ([s[-1]] if params.show_integer_points else [])
            return [first, combine("region", "Shade and find the region R", 3.0, *rest)]

        return by_level(level, steps, standard, concise)


class _Bad(ValueError):
    pass


def _parse(text: str) -> tuple[sp.Expr, str]:
    """An inequality as (expression, operator) meaning `expression operator 0`, with the
    expression linear in x and y."""
    pieces = _OPERATOR.split(text)
    if len(pieces) != 3:
        raise _Bad(f"use one of <, >, <= or >= exactly once: {text!r}")
    left, operator, right = pieces
    try:
        lhs = parse_expression(left, {"x", "y"})
        rhs = parse_expression(right, {"x", "y"})
    except ExpressionError as error:
        raise _Bad(str(error)) from None
    expr = sp.nsimplify(sp.expand(lhs - rhs), rational=True)  # 0.5*x is x/2
    poly = sp.Poly(expr, X, Y) if expr.free_symbols else None
    if poly is None or poly.total_degree() != 1:
        raise _Bad(f"not a linear inequality in x and y: {text!r}")
    return expr, operator


def _coefficients(parsed) -> tuple[float, float, float]:
    """a, b, c with the boundary a x + b y + c = 0."""
    expr, _ = parsed
    return (
        float(expr.coeff(X)),
        float(expr.coeff(Y)),
        float(expr.subs({X: 0, Y: 0})),
    )


def _satisfied(parsed, x: float, y: float) -> bool:
    a, b, c = _coefficients(parsed)
    value = a * x + b * y + c
    operator = parsed[1]
    return {
        "<": value < -1e-9,
        "<=": value <= 1e-9,
        ">": value > 1e-9,
        ">=": value >= -1e-9,
    }[operator]


def _view(params: InequalityRegionParams) -> tuple[tuple[float, float], tuple[float, float]]:
    if params.x_range and params.y_range:
        return tuple(params.x_range), tuple(params.y_range)
    parsed = [_parse(t) for t in params.inequalities]
    points = [(0.0, 0.0)]
    for p in parsed:
        a, b, c = _coefficients(p)
        if abs(a) > 1e-12:
            points.append((-c / a, 0.0))
        if abs(b) > 1e-12:
            points.append((0.0, -c / b))
    for p, q in itertools.combinations(parsed, 2):
        a1, b1, c1 = _coefficients(p)
        a2, b2, c2 = _coefficients(q)
        det = a1 * b2 - a2 * b1
        if abs(det) > 1e-12:
            points.append(((b1 * c2 - b2 * c1) / det, (a2 * c1 - a1 * c2) / det))
    points = [(x, y) for x, y in points if abs(x) <= 20 and abs(y) <= 20]
    xs, ys = [x for x, _ in points], [y for _, y in points]
    x_view = params.x_range or (max(min(xs) - 2, -20), min(max(xs) + 2, 20))
    y_view = params.y_range or (max(min(ys) - 2, -20), min(max(ys) + 2, 20))
    return (float(x_view[0]), float(x_view[1])), (float(y_view[0]), float(y_view[1]))


def _rectangle(view) -> list[tuple[float, float]]:
    (x_lo, x_hi), (y_lo, y_hi) = view
    return [(x_lo, y_lo), (x_hi, y_lo), (x_hi, y_hi), (x_lo, y_hi)]


def _clip(polygon, parsed, keep: bool) -> list[tuple[float, float]]:
    """Sutherland-Hodgman: the part of `polygon` on the side of the boundary where the
    inequality holds (keep) or fails (not keep). The boundary itself counts as both."""
    a, b, c = _coefficients(parsed)
    sign = 1 if parsed[1] in ("<", "<=") else -1
    if not keep:
        sign = -sign

    def inside(point):
        return sign * (a * point[0] + b * point[1] + c) <= 1e-9

    out = []
    for i, current in enumerate(polygon):
        previous = polygon[i - 1]
        if inside(current):
            if not inside(previous):
                out.append(_intersection(previous, current, a, b, c))
            out.append(current)
        elif inside(previous):
            out.append(_intersection(previous, current, a, b, c))
    return out


def _intersection(p, q, a, b, c):
    fp = a * p[0] + b * p[1] + c
    fq = a * q[0] + b * q[1] + c
    t = fp / (fp - fq)
    return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))


def _half_plane(parsed, view, keep: bool):
    return _clip(_rectangle(view), parsed, keep)


def _region(params: InequalityRegionParams, view) -> list[tuple[float, float]]:
    polygon = _rectangle(view)
    for text in params.inequalities:
        polygon = _clip(polygon, _parse(text), True)
        if not polygon:
            return []
    area = 0.5 * abs(
        sum(
            polygon[i - 1][0] * polygon[i][1] - polygon[i][0] * polygon[i - 1][1]
            for i in range(len(polygon))
        )
    )
    return polygon if area > 1e-6 else []


def _clip_line(parsed, view) -> list[tuple[float, float]]:
    """The two ends of the boundary line inside the view rectangle."""
    a, b, c = _coefficients(parsed)
    (x_lo, x_hi), (y_lo, y_hi) = view
    points = []
    if abs(b) > 1e-12:
        for x in (x_lo, x_hi):
            y = -(a * x + c) / b
            if y_lo - 1e-9 <= y <= y_hi + 1e-9:
                points.append((x, y))
    if abs(a) > 1e-12:
        for y in (y_lo, y_hi):
            x = -(b * y + c) / a
            if x_lo - 1e-9 <= x <= x_hi + 1e-9:
                points.append((x, y))
    unique = []
    for point in points:
        if all(math.dist(point, other) > 1e-6 for other in unique):
            unique.append(point)
    if len(unique) < 2:  # the line misses the view; draw nothing visible but keep two ends
        return [(x_lo, y_lo), (x_lo, y_lo)]
    return sorted(unique)[:1] + sorted(unique)[-1:]


def _label_anchor(ends):
    (x1, y1), (x2, y2) = ends
    return (x1 + 0.85 * (x2 - x1), y1 + 0.85 * (y2 - y1))


def _integer_points(params: InequalityRegionParams, view) -> list[tuple[int, int]]:
    (x_lo, x_hi), (y_lo, y_hi) = view
    parsed = [_parse(t) for t in params.inequalities]
    return [
        (x, y)
        for x in range(math.ceil(x_lo), math.floor(x_hi) + 1)
        for y in range(math.ceil(y_lo), math.floor(y_hi) + 1)
        if all(_satisfied(p, x, y) for p in parsed)
    ][:200]


def _boundary_text(parsed) -> str:
    expr, _ = parsed
    if expr.coeff(Y) != 0:
        solved = sp.solve(expr, Y)[0]
        return f"y = {solved}"
    return f"x = {sp.solve(expr, X)[0]}"


def _inequality_latex(parsed) -> str:
    """The inequality solved for y (or for x if it has no y), as it is usually written."""
    expr, operator = parsed
    flip = {"<": ">", ">": "<", "<=": ">=", ">=": "<="}
    for symbol in (Y, X):
        coefficient = expr.coeff(symbol)
        if coefficient != 0:
            rhs = sp.solve(expr, symbol)[0]
            op = operator if coefficient > 0 else flip[operator]
            return rf"{symbol} {_TEX[op]} {sp.latex(rhs)}"
    raise ValueError("not linear")  # pragma: no cover


def _colour(i: int):
    return [style.CURVE_COLOUR, style.RUN_COLOUR, style.RISE_COLOUR, style.SECANT_COLOUR][
        (i - 1) % 4
    ]


def _failure(kind, predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(kind=kind, predicate=predicate, message=message, parameters=[parameter])
