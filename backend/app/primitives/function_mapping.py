"""FunctionMapping: a function's domain and range, whether it is one-one, and the composite gf
with the condition that the range of f lies inside the domain of g (9709 1.2).

The range is read from the graph: the least and greatest values of f on its domain, at the
ends or at turning points, which SymPy finds from f'(x) = 0. A function is one-one when every
horizontal line meets its graph at most once; one that turns can be made one-one by cutting the
domain at the turning point. gf(x) = g(f(x)) means f first: it exists only when every output of
f is an allowed input of g, shown on three number lines from x to f(x) to gf(x).
"""

from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import Arrow, DashedLine, Dot, Line, MathTex, NumberLine, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.analysis import samples, zeros
from app.primitives.plotting import (
    curve,
    label,
    make_plot,
    place_label,
    stack_boxes,
    stack_lines,
    text_line,
)
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    exact,
    failing_samples,
    format_value,
    latex_value,
    parse_expression,
    sample_points,
    tidy_latex,
    written_latex,
)

X = sp.Symbol("x", real=True)
Coordinate = Annotated[float, Field(ge=-20, le=20)]
DOMAIN_COLOUR = style.RUN_COLOUR
RANGE_COLOUR = style.RISE_COLOUR


class FunctionMappingParams(PrimitiveParams):
    kind: Literal["range", "one_one", "composite"]
    f: str = Field(min_length=1, max_length=100, description="f(x), e.g. (x - 2)**2 + 1")
    f_min: Coordinate = Field(description="Domain of f: f_min <= x <= f_max")
    f_max: Coordinate
    g: str | None = Field(default=None, max_length=100, description="For composite: g(x)")
    g_min: Coordinate | None = Field(
        default=None, description="For composite: the domain of g starts here (none: no limit)"
    )
    g_max: Coordinate | None = Field(default=None, description="For composite: domain end")


class FunctionMapping(StagedPrimitive[FunctionMappingParams]):
    primitive_id = "FunctionMapping"
    version = "1"
    topic = "Functions"
    params_model = FunctionMappingParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[
            ("axes", "*"),
            ("curve", "*"),
            ("*_bar", "*"),
            ("*_guide*", "*"),
            ("test_line", "*"),
            ("hits", "*"),
            ("piece", "*"),
            ("arrows_*", "*"),
            ("line_*", "*_bar"),
        ],
    )

    def default_params(self) -> FunctionMappingParams:
        return FunctionMappingParams(kind="range", f="(x - 2)**2 + 1", f_min=0, f_max=5)

    def validate(self, params: FunctionMappingParams) -> list[PredicateFailure]:
        try:
            f = parse_expression(params.f, {"x"})
        except ExpressionError as error:
            return [_failure("parsing", "expression_parses", str(error), "f")]
        if params.f_min >= params.f_max:
            return [_failure("consistency", "domain_ordered", "f_min must be below f_max")]
        if failing_samples(f, X, sample_points(params.f_min, params.f_max)):
            message = "f must be real and finite on its whole domain"
            return [_failure("domain", "real_and_finite", message, "f")]
        if params.kind != "composite":
            return []
        if params.g is None:
            return [_failure("consistency", "g_given", "a composite needs g", "g")]
        try:
            g = parse_expression(params.g, {"x"})
        except ExpressionError as error:
            return [_failure("parsing", "expression_parses", str(error), "g")]
        if params.g_min is not None and params.g_max is not None and params.g_min >= params.g_max:
            return [_failure("consistency", "domain_ordered", "g_min must be below g_max")]
        low, high = _extremes(_f(params), exact(params.f_min), exact(params.f_max))
        if _inside(params, low[1], high[1]) and failing_samples(
            g, X, sample_points(float(low[1]), float(high[1]))
        ):
            message = "g must be real and finite on the range of f"
            return [_failure("domain", "real_and_finite", message, "g")]
        return []

    def computed_values(self, params: FunctionMappingParams) -> dict[str, str]:
        f = _f(params)
        a, b = exact(params.f_min), exact(params.f_max)
        low, high = _extremes(f, a, b)
        values = {"range_min": format_value(low[1]), "range_max": format_value(high[1])}
        if params.kind == "one_one":
            values["one_one"] = "yes" if _monotonic(f, a, b) else "no"
            if not _monotonic(f, a, b):
                values["restricted_domain"] = _restriction_text(f, a, b)
        if params.kind == "composite":
            exists = _inside(params, low[1], high[1])
            values["composite_exists"] = "yes" if exists else "no"
            if exists:
                gf = _gf(params)
                g_low, g_high = _extremes(gf, a, b)
                values["gf"] = str(gf)
                values["gf_range_min"] = format_value(g_low[1])
                values["gf_range_max"] = format_value(g_high[1])
        return values

    def build(self, params: FunctionMappingParams, level):
        if params.kind == "composite":
            return self._build_composite(params)
        f = _f(params)
        a, b = exact(params.f_min), exact(params.f_max)
        low, high = _extremes(f, a, b)
        f_num = sp.lambdify(X, f, "math")
        _, ys = samples(f, float(a), float(b), 201)
        plot = make_plot(style.GRAPH_REGION, [float(a), float(b)], list(ys))
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "equation": text_line(
                rf"\mathrm{{f}}(x) = {written_latex(params.f)},\quad "
                rf"{latex_value(a)} \le x \le {latex_value(b)}",
                plot.upper,
            ),
            "curve": curve(plot, f_num, float(a), float(b)),
        }
        parts["domain_bar"] = Line(
            plot.point(float(a), 0), plot.point(float(b), 0), color=DOMAIN_COLOUR, stroke_width=9
        )
        parts["range_bar"] = Line(
            plot.point(0, float(low[1])),
            plot.point(0, float(high[1])),
            color=RANGE_COLOUR,
            stroke_width=9,
        )
        for name, (x, y) in (("low", low), ("high", high)):
            point = plot.point(float(x), float(y))
            parts[f"{name}_dot"] = Dot(point, color=style.POINT_COLOUR)
            parts[f"{name}_guide"] = DashedLine(
                point, plot.point(0, float(y)), color=RANGE_COLOUR, stroke_width=2
            )
        obstacles = [*plot.obstacles(), parts["low_dot"], parts["high_dot"]]
        paths = [parts["curve"], *plot.axis_lines()]
        for name, (x, y) in (("low", low), ("high", high)):
            text = label(
                rf"({latex_value(x)},\ {latex_value(y)})", colour=style.POINT_COLOUR, size=26
            )
            parts[f"{name}_label"] = place_label(
                text, plot.point(float(x), float(y)), plot.plot_box, obstacles, paths, wide=True
            )
            obstacles.append(text)
        rows = [
            (rf"\text{{Domain: }} {latex_value(a)} \le x \le {latex_value(b)}", DOMAIN_COLOUR),
            (_turning_row(f, a, b), None),
            (
                rf"\text{{Least }} \mathrm{{f}}({latex_value(low[0])}) = {latex_value(low[1])}",
                None,
            ),
            (
                rf"\text{{Greatest }} \mathrm{{f}}({latex_value(high[0])}) = "
                rf"{latex_value(high[1])}",
                None,
            ),
            (
                rf"\text{{Range: }} {latex_value(low[1])} \le \mathrm{{f}}(x) \le "
                rf"{latex_value(high[1])}",
                RANGE_COLOUR,
            ),
        ]
        if params.kind == "one_one":
            rows += self._one_one(params, plot, parts)
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        lines = stack_lines([t for t, _ in rows], box, size=30, colours=[c for _, c in rows])
        for i, line in enumerate(lines, start=1):
            parts[f"row_{i}"] = line
        return parts

    def _one_one(self, params, plot, parts) -> list[tuple[str, object]]:
        f = _f(params)
        a, b = exact(params.f_min), exact(params.f_max)
        f_num = sp.lambdify(X, f, "math")
        if _monotonic(f, a, b):
            y0 = float(f.subs(X, (a + b) / 2))
            hits = [float((a + b) / 2)]
            verdict = r"\text{Each line meets it once: one-one}"
        else:
            turns = _turning_points(f, a, b)
            t = float(turns[0])
            ft = f_num(t)
            ends = [f_num(float(a)), f_num(float(b))]
            nearer = min(ends, key=lambda v: abs(v - ft) if (v - ft) != 0 else np.inf)
            y0 = ft + 0.3 * (nearer - ft)
            hits = [float(r) for r in zeros(sp.nsimplify(f - sp.Float(y0, 12)), a, b, [])]
            verdict = r"\text{A line meets it twice: not one-one}"
            lo, hi = _monotone_piece(f, a, b)
            parts["piece"] = curve(plot, f_num, float(lo), float(hi), colour=style.HIGHLIGHT_COLOUR)
        parts["test_line"] = Line(
            plot.point(plot.x_range[0], y0),
            plot.point(plot.x_range[1], y0),
            color=style.SECANT_COLOUR,
            stroke_width=3,
        )
        parts["hits"] = VGroup(
            *(Dot(plot.point(x, f_num(x)), color=style.SECANT_COLOUR) for x in hits)
        )
        rows = [(verdict, style.SECANT_COLOUR)]
        if "piece" in parts:
            rows.append((_restriction_latex(f, a, b), style.HIGHLIGHT_COLOUR))
        return rows

    def _build_composite(self, params: FunctionMappingParams):
        f, gf = _f(params), None
        a, b = exact(params.f_min), exact(params.f_max)
        low, high = _extremes(f, a, b)
        exists = _inside(params, low[1], high[1])
        if exists:
            gf = _gf(params)
            g_low, g_high = _extremes(gf, a, b)
        area = style.region_box(style.GRAPH_REGION).shrink(style.PADDING)
        title, body = (
            style.Box(area.left, area.right, area.top - 0.7, area.top),
            style.Box(area.left, area.right, area.bottom, area.top - 0.9),
        )
        bands = stack_boxes(body, 3, gap=0.5) if exists else stack_boxes(body, 2, gap=0.9)
        parts = {
            "equation": text_line(
                rf"\mathrm{{f}}(x) = {written_latex(params.f)},\ "
                rf"\mathrm{{g}}(x) = {written_latex(params.g)}",
                title,
            )
        }
        g_dom = (params.g_min, params.g_max)
        first = [float(a), float(b)]
        second = [float(low[1]), float(high[1])] + [v for v in g_dom if v is not None]
        specs = [
            ("x", first, (a, b), DOMAIN_COLOUR),
            ("f(x)", second, (low[1], high[1]), RANGE_COLOUR),
        ]
        if exists:
            specs.append(
                (
                    "gf(x)",
                    [float(g_low[1]), float(g_high[1])],
                    (g_low[1], g_high[1]),
                    style.TANGENT_COLOUR,
                )
            )
        lines = []
        for i, (name, values, (lo, hi), colour) in enumerate(specs, start=1):
            number_line, bar = _number_line(values, bands[i - 1], lo, hi, colour)
            parts[f"line_{i}"] = number_line
            parts[f"line_{i}_bar"] = bar
            tag = MathTex(rf"\mathrm{{{name[0]}}}{name[1:]}" if name != "x" else "x", font_size=30)
            tag.next_to(number_line, [-1, 0, 0], buff=0.25)
            parts[f"line_{i}_name"] = tag
            lines.append(number_line)
        # the domain of g drawn under the range of f, on the same line
        g_lo = params.g_min if params.g_min is not None else lines[1].x_range[0]
        g_hi = params.g_max if params.g_max is not None else lines[1].x_range[1]
        offset = np.array([0, 0.3, 0])
        parts["gdomain_bar"] = Line(
            lines[1].n2p(g_lo) + offset,
            lines[1].n2p(g_hi) + offset,
            color=style.SECANT_COLOUR,
            stroke_width=6,
        )
        f_num = sp.lambdify(X, f, "math")
        xs = [float(a), float((a + b) / 2), float(b)]
        parts["arrows_1"] = VGroup(
            *(
                Arrow(
                    lines[0].n2p(x),
                    lines[1].n2p(f_num(x)) + [0, 0.12, 0],
                    buff=0.08,
                    stroke_width=2.5,
                    color=style.TEXT_COLOUR,
                    max_tip_length_to_length_ratio=0.12,
                )
                for x in xs
            )
        )
        if exists:
            gf_num = sp.lambdify(X, gf, "math")
            parts["arrows_2"] = VGroup(
                *(
                    Arrow(
                        lines[1].n2p(f_num(x)) + [0, -0.4, 0],
                        lines[2].n2p(gf_num(x)),
                        buff=0.08,
                        stroke_width=2.5,
                        color=style.TEXT_COLOUR,
                        max_tip_length_to_length_ratio=0.12,
                    )
                    for x in xs
                )
            )
        g_text = _interval_latex(params.g_min, params.g_max, "x")
        rows = [
            (
                rf"\text{{Range of f: }}{latex_value(low[1])} \le \mathrm{{f}}(x) \le "
                rf"{latex_value(high[1])}",
                RANGE_COLOUR,
            ),
            (rf"\text{{Domain of g: }}{g_text}", style.SECANT_COLOUR),
        ]
        if exists:
            rows += [
                (r"\text{Range of f is inside it: gf exists}", None),
                (
                    rf"\mathrm{{gf}}(x) = \mathrm{{g}}(\mathrm{{f}}(x)) = {tidy_latex(gf)}",
                    None,
                ),
                (
                    rf"\text{{Range: }}{latex_value(g_low[1])} \le \mathrm{{gf}}(x) \le "
                    rf"{latex_value(g_high[1])}",
                    style.TANGENT_COLOUR,
                ),
            ]
        else:
            rows.append((r"\text{Range of f is not inside it: no gf}", style.TANGENT_COLOUR))
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([t for t, _ in rows], box, size=30, colours=[c for _, c in rows])
        for i, line in enumerate(texts, start=1):
            parts[f"row_{i}"] = line
        return parts

    def stages(self, params: FunctionMappingParams, level) -> list[Stage]:
        if params.kind == "composite":
            return self._composite_stages(params, level)
        steps = [
            stage("axes", "Draw the axes", 1.5, ["axes", "x_label", "y_label", "equation"]),
            stage(
                "domain",
                "The domain is the set of inputs: these x values",
                2.5,
                ["domain_bar", "row_1"],
                emphasise=["domain_bar"],
            ),
            stage("graph", "Draw f over its domain only", 2.5, ["curve"]),
            stage(
                "extremes",
                "Find the least and greatest values, at the ends or at a turning point",
                3.5,
                ["low_dot", "high_dot", "low_label", "high_label", "row_2", "row_3", "row_4"],
            ),
            stage(
                "range",
                "The range is every output in between, on the y-axis",
                3.0,
                ["low_guide", "high_guide", "range_bar", "row_5"],
                emphasise=["range_bar"],
            ),
        ]
        if params.kind == "one_one":
            f = _f(params)
            monotonic = _monotonic(f, exact(params.f_min), exact(params.f_max))
            steps.append(
                stage(
                    "test",
                    "Draw horizontal lines: one-one means no line meets the graph twice",
                    3.0,
                    ["test_line", "hits", "row_6"],
                    emphasise=["hits"],
                )
            )
            if not monotonic:
                steps.append(
                    stage(
                        "restrict",
                        "Cut the domain at the turning point and it becomes one-one",
                        3.0,
                        ["piece", "row_7"],
                        emphasise=["piece"],
                    )
                )

        def standard(s):
            return [combine("graph", "Draw f over its domain", 3.0, *s[:3]), *s[3:]]

        def concise(s):
            out = [
                combine("graph", "Draw f over its domain", 3.0, *s[:3]),
                combine("range", "Its least and greatest values give the range", 3.5, *s[3:5]),
            ]
            if len(s) > 5:
                out.append(combine("one_one", "Test whether it is one-one", 3.5, *s[5:]))
            return out

        return by_level(level, steps, standard, concise)

    def _composite_stages(self, params: FunctionMappingParams, level) -> list[Stage]:
        f = _f(params)
        low, high = _extremes(f, exact(params.f_min), exact(params.f_max))
        exists = _inside(params, low[1], high[1])
        steps = [
            stage(
                "domain",
                "Start with the domain of f",
                2.5,
                ["equation", "line_1", "line_1_bar", "line_1_name"],
            ),
            stage(
                "f",
                "f sends it to the range of f",
                3.0,
                ["arrows_1", "line_2", "line_2_bar", "line_2_name", "row_1"],
            ),
            stage(
                "check",
                "gf means f first, then g: every output of f must be an input g allows",
                3.5,
                ["gdomain_bar", "row_2", "row_3"],
                emphasise=["gdomain_bar"],
            ),
        ]
        if exists:
            steps += [
                stage("formula", "Put f of x into g", 3.0, ["row_4"]),
                stage(
                    "g",
                    "g sends the range of f to the range of gf",
                    3.0,
                    ["arrows_2", "line_3", "line_3_bar", "line_3_name", "row_5"],
                    emphasise=["line_3_bar"],
                ),
            ]

        def standard(s):
            out = [combine("f", "f sends its domain to its range", 3.0, *s[:2]), s[2]]
            if exists:
                out.append(combine("g", "Then g: gf of x and its range", 3.5, *s[3:]))
            return out

        def concise(s):
            out = standard(s)
            return [combine("f", "f, then the domain of g", 3.5, *out[:2]), *out[2:]]

        return by_level(level, steps, standard, concise)


def _f(params: FunctionMappingParams) -> sp.Expr:
    return sp.nsimplify(parse_expression(params.f, {"x"}), rational=True)


def _gf(params: FunctionMappingParams) -> sp.Expr:
    g = sp.nsimplify(parse_expression(params.g, {"x"}), rational=True)
    gf = sp.simplify(g.subs(X, _f(params)))
    return sp.expand(gf) if gf.is_polynomial(X) else gf


def _turning_points(f: sp.Expr, a, b) -> list:
    return [t for t in zeros(sp.diff(f, X), float(a), float(b), []) if a < t < b and _turns(f, t)]


def _turns(f: sp.Expr, t) -> bool:
    d = sp.lambdify(X, sp.diff(f, X), "math")
    eps = 1e-4
    return d(float(t) - eps) * d(float(t) + eps) < 0


def _extremes(f: sp.Expr, a, b):
    """(x, f(x)) at the least and greatest values of f on [a, b]."""
    candidates = [a, b, *_turning_points(f, a, b)]
    points = [(sp.nsimplify(x), sp.nsimplify(sp.simplify(f.subs(X, x)))) for x in candidates]
    return min(points, key=lambda p: float(p[1])), max(points, key=lambda p: float(p[1]))


def _monotonic(f: sp.Expr, a, b) -> bool:
    return not _turning_points(f, a, b)


def _monotone_piece(f: sp.Expr, a, b):
    """The longest part of [a, b] between turning points, where f is one-one."""
    cuts = [a, *_turning_points(f, a, b), b]
    pieces = list(zip(cuts, cuts[1:], strict=False))
    return max(pieces, key=lambda p: float(p[1] - p[0]))


def _restriction_latex(f, a, b) -> str:
    lo, hi = _monotone_piece(f, a, b)
    return rf"\text{{One-one for }}{latex_value(lo)} \le x \le {latex_value(hi)}"


def _restriction_text(f, a, b) -> str:
    lo, hi = _monotone_piece(f, a, b)
    return f"{format_value(lo)} <= x <= {format_value(hi)}"


def _turning_row(f, a, b) -> str:
    turns = _turning_points(f, a, b)
    if not turns:
        return r"\mathrm{f}'(x) \ne 0\text{: no turning point}"
    return r"\mathrm{f}'(x) = 0\text{ at }x = " + ",\\ ".join(latex_value(t) for t in turns)


def _inside(params: FunctionMappingParams, low, high) -> bool:
    if params.g_min is not None and low < exact(params.g_min):
        return False
    return not (params.g_max is not None and high > exact(params.g_max))


def _interval_latex(lo, hi, name) -> str:
    if lo is None and hi is None:
        return r"\text{all real }" + name
    if lo is None:
        return rf"{name} \le {latex_value(exact(hi))}"
    if hi is None:
        return rf"{name} \ge {latex_value(exact(lo))}"
    return rf"{latex_value(exact(lo))} \le {name} \le {latex_value(exact(hi))}"


def _number_line(values, box, lo, hi, colour):
    """A number line across `box` covering `values`, with [lo, hi] drawn as a thick bar."""
    from app.primitives.plotting import axis_range

    start, end, step = axis_range(values, ticks=6)
    number_line = NumberLine(
        x_range=[start, end, step],
        length=box.width - 1.4,
        include_numbers=True,
        font_size=22,
        stroke_width=2,
    )
    number_line.move_to(box.center + np.array([0.6, 0, 0]))
    bar = Line(number_line.n2p(float(lo)), number_line.n2p(float(hi)), color=colour, stroke_width=9)
    bar.add(
        Dot(number_line.n2p(float(lo)), color=colour), Dot(number_line.n2p(float(hi)), color=colour)
    )
    return number_line, bar


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
