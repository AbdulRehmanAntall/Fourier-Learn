"""LineMeetsCurve: for which values of k a line meets a quadratic curve twice, touches it, or
misses it, decided by the discriminant (9709 1.1, 1.3).

Putting the line into the curve's equation gives a quadratic in x whose roots are the
x-coordinates where they meet. Its discriminant b² - 4ac, a polynomial in k, is positive for
two meeting points, zero for a tangent (a repeated root) and negative for none. SymPy expands
the discriminant, solves it equal to 0 for the tangents, and solves the inequality for the
lines that cut the curve twice. One line of each kind is drawn.
"""

import numpy as np
import sympy as sp
from manim import Dot, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import curve, label, make_plot, place_label, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import (
    ExpressionError,
    format_value,
    latex_value,
    parse_expression,
    tidy_latex,
    written_latex,
)

X = sp.Symbol("x", real=True)
K = sp.Symbol("k", real=True)
TWO_COLOUR = style.RISE_COLOUR
NONE_COLOUR = style.SECANT_COLOUR


class LineMeetsCurveParams(PrimitiveParams):
    curve: str = Field(
        min_length=1, max_length=80, description="The quadratic curve y = ..., e.g. x**2 - 4*x + 7"
    )
    line: str = Field(
        min_length=1,
        max_length=60,
        description='The line y = ..., with the unknown k: "x + k", "k*x - 2" or "k*x + 2*k"',
    )


class LineMeetsCurve(StagedPrimitive[LineMeetsCurveParams]):
    primitive_id = "LineMeetsCurve"
    version = "1"
    topic = "Quadratics"
    params_model = LineMeetsCurveParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[
            ("axes", "*"),
            ("curve", "*"),
            ("tangent_*", "*"),
            ("line_*", "*"),
            ("dots_*", "*"),
        ],
    )

    def default_params(self) -> LineMeetsCurveParams:
        return LineMeetsCurveParams(curve="x**2 - 4*x + 7", line="x + k")

    def validate(self, params: LineMeetsCurveParams) -> list[PredicateFailure]:
        try:
            f = parse_expression(params.curve, {"x"})
        except ExpressionError as error:
            return [_failure("parsing", "expression_parses", str(error), "curve")]
        try:
            g = parse_expression(params.line, {"x", "k"})
        except ExpressionError as error:
            return [_failure("parsing", "expression_parses", str(error), "line")]
        if not f.is_polynomial(X) or sp.degree(f, X) != 2:
            return [_failure("consistency", "curve_quadratic", "the curve must be a quadratic")]
        if not g.has(K):
            return [_failure("consistency", "line_has_k", "the line must contain k", "line")]
        if not g.is_polynomial(X, K) or sp.degree(g, X) > 1 or sp.degree(g, K) > 1:
            message = "the line must be straight, with k appearing linearly"
            return [_failure("consistency", "line_linear", message, "line")]
        problem = _Problem(params)
        if not problem.discriminant.has(K):
            message = "k does not change the discriminant, so it decides nothing"
            return [_failure("consistency", "k_matters", message, "line")]
        if not problem.tangents:
            message = "no value of k makes the line a tangent; choose another line"
            return [_failure("consistency", "tangent_exists", message, "line")]
        if problem.k_two is None or problem.k_none is None:
            message = "some k must give two meeting points and some none"
            return [_failure("consistency", "both_cases", message, "line")]
        return []

    def computed_values(self, params: LineMeetsCurveParams) -> dict[str, str]:
        problem = _Problem(params)
        values = {
            "discriminant": str(problem.discriminant),
            "two_points": str(problem.two_set),
            "no_points": str(problem.none_set),
        }
        for i, k in enumerate(problem.tangents, start=1):
            values[f"tangent_k_{i}"] = format_value(k)
            values[f"tangent_point_{i}"] = (
                f"({format_value(problem.touch(k)[0])}, {format_value(problem.touch(k)[1])})"
            )
        return values

    def build(self, params: LineMeetsCurveParams, level):
        problem = _Problem(params)
        f_num = sp.lambdify(X, problem.f, "math")
        lo, hi = problem.x_interval()
        xs = np.linspace(lo, hi, 81)
        plot = make_plot(style.GRAPH_REGION, [lo, hi], [f_num(x) for x in xs])
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "equation": text_line(
                rf"y = {written_latex(params.curve)},\quad y = {written_latex(params.line)}",
                plot.upper,
            ),
            "curve": curve(plot, f_num, lo, hi),
        }
        obstacles = plot.obstacles()
        paths = [parts["curve"], *plot.axis_lines()]
        samples = [("tangent", k, style.TANGENT_COLOUR) for k in problem.tangents]
        samples += [("two", problem.k_two, TWO_COLOUR), ("none", problem.k_none, NONE_COLOUR)]
        lines = {}
        for i, (kind, k, colour) in enumerate(samples, start=1):
            name = f"tangent_{i}" if kind == "tangent" else f"line_{kind}"
            line_expr = problem.g.subs(K, k)
            slope = float(sp.diff(line_expr, X))
            intercept = float(line_expr.subs(X, 0))
            parts[name] = style.line_in_axes(
                plot.axes,
                (0, intercept),
                slope,
                plot.x_range,
                plot.y_range,
                color=colour,
                stroke_width=3.5,
            )
            lines[name] = (k, colour, line_expr)
            paths.append(parts[name])
        for name, (k, colour, line_expr) in lines.items():
            meets = problem.meets(k)
            if name.startswith("tangent") or name == "line_two":
                dots = VGroup(
                    *(
                        Dot(plot.point(float(x), float(line_expr.subs(X, x))), color=colour)
                        for x in meets
                    )
                )
                parts[f"dots_{name}"] = dots
                obstacles.append(dots)
        for name, (k, colour, _) in lines.items():
            start, end = parts[name].get_start(), parts[name].get_end()
            end = end if end[0] > start[0] else start
            text = label(f"k = {latex_value(k)}", colour=colour, size=28)
            parts[f"{name}_label"] = place_label(
                text, end, plot.plot_box, obstacles, paths, wide=True
            )
            obstacles.append(text)
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        rows = problem.rows()
        texts = stack_lines([t for t, _ in rows], box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: LineMeetsCurveParams, level) -> list[Stage]:
        problem = _Problem(params)
        tangents = [
            n
            for i in range(1, len(problem.tangents) + 1)
            for n in (f"tangent_{i}", f"dots_tangent_{i}", f"tangent_{i}_label")
        ]
        steps = [
            stage(
                "graph",
                "Draw the curve; the line moves as k changes",
                2.5,
                ["axes", "x_label", "y_label", "equation", "curve"],
            ),
            stage(
                "substitute",
                "Where they meet, the y values are equal: put the line into the curve",
                3.0,
                ["row_1", "row_2"],
            ),
            stage(
                "discriminant",
                "The roots are the meeting points, so the discriminant counts them",
                3.0,
                ["row_3"],
                emphasise=["row_3"],
            ),
            stage(
                "tangent",
                "Discriminant zero: one repeated root, so the line is a tangent",
                3.0,
                [*tangents, "row_4"],
                emphasise=[t for t in tangents if t.startswith("dots")],
            ),
            stage(
                "two",
                "Discriminant positive: two roots, the line cuts the curve twice",
                3.0,
                ["line_two", "dots_line_two", "line_two_label", "row_5"],
            ),
            stage(
                "none",
                "Discriminant negative: no real roots, the line misses the curve",
                3.0,
                ["line_none", "line_none_label", "row_6"],
            ),
        ]

        def standard(s):
            return [
                s[0],
                combine(
                    "discriminant", "Put the line into the curve: the discriminant", 3.5, *s[1:3]
                ),
                *s[3:],
            ]

        def concise(s):
            return [
                s[0],
                combine(
                    "discriminant", "Put the line into the curve: the discriminant", 3.5, *s[1:3]
                ),
                s[3],
                combine("others", "Positive cuts twice; negative misses", 3.5, *s[4:]),
            ]

        return by_level(level, steps, standard, concise)


class _Problem:
    def __init__(self, params: LineMeetsCurveParams):
        self.params = params
        self.f = sp.nsimplify(parse_expression(params.curve, {"x"}), rational=True)
        self.g = sp.nsimplify(parse_expression(params.line, {"x", "k"}), rational=True)
        self.equation = sp.expand(self.f - self.g)
        poly = sp.Poly(self.equation, X)
        self.a, self.b, self.c = (poly.coeff_monomial(X**p) for p in (2, 1, 0))
        self.discriminant = sp.expand(self.b**2 - 4 * self.a * self.c)
        self.tangents = sorted(
            {sp.nsimplify(r) for r in sp.solve(self.discriminant, K) if r.is_real}, key=float
        )
        self.two_set = sp.solve_univariate_inequality(self.discriminant > 0, K, relational=False)
        self.none_set = sp.solve_univariate_inequality(self.discriminant < 0, K, relational=False)
        self.k_two = self._sample(self.two_set)
        self.k_none = self._sample(self.none_set)

    def _sample(self, interval_set):
        """A tidy k in the set near a tangent value, for drawing: for a line cutting the curve,
        the one whose meeting points are closest together, so the picture stays small."""
        if interval_set == sp.S.EmptySet:
            return None
        candidates = []
        for step in (1, 2, 3, 4, 6, sp.Rational(1, 2)):
            for t in self.tangents:
                for k in (sp.floor(t) + step, sp.ceiling(t) - step, t + step, t - step):
                    if k in interval_set and k not in candidates:
                        candidates.append(sp.nsimplify(k))
        if not candidates:
            return sp.nsimplify(sum(self.tangents) / len(self.tangents))
        if interval_set == self.none_set:
            return min(candidates, key=lambda k: min(abs(k - t) for t in self.tangents))

        def spread(k):
            xs = [float(x) for x in self.meets(k)]
            return max(xs) - min(xs) + 0.1 * max(abs(x) for x in xs)

        whole = [k for k in candidates if k.is_integer] or candidates
        return min(whole[:8], key=spread)

    def meets(self, k) -> list:
        roots = sp.solve(self.equation.subs(K, k), X)
        return sorted({sp.nsimplify(r) for r in roots if r.is_real}, key=float)

    def touch(self, k):
        x = self.meets(k)[0]
        return x, sp.nsimplify(self.f.subs(X, x))

    def x_interval(self) -> tuple[float, float]:
        xs = [
            float(x) for k in [*self.tangents, self.k_two] if k is not None for x in self.meets(k)
        ]
        xs.append(float(sp.solve(sp.diff(self.f, X), X)[0]))
        lo, hi = min(xs), max(xs)
        pad = max(1.5, 0.35 * (hi - lo))
        return lo - pad, hi + pad

    def rows(self) -> list[tuple[str, object]]:
        curve_tex = written_latex(self.params.curve)
        line_tex = written_latex(self.params.line)
        terms = [self.a * X**2, sp.collect(self.b, K) * X, self.c]
        written = _quadratic_latex(terms)
        rows = [
            (f"{curve_tex} = {line_tex}", None),
            (f"{written} = 0", None),
            (rf"b^2 - 4ac = {tidy_latex(self.discriminant)}", None),
        ]
        tangent_values = ",\\ ".join(latex_value(t) for t in self.tangents)
        rows.append(
            (rf"\text{{Tangent: }} b^2 - 4ac = 0,\ k = {tangent_values}", style.TANGENT_COLOUR)
        )
        rows.append((rf"\text{{Two points: }}{_set_latex(self.two_set)}", TWO_COLOUR))
        rows.append((rf"\text{{No points: }}{_set_latex(self.none_set)}", NONE_COLOUR))
        return rows


def _quadratic_latex(terms) -> str:
    """ax² + (b)x + (c) with k kept in brackets, as written in the working."""
    out = ""
    for i, term in enumerate(terms):
        term = sp.expand(term)
        if term == 0:
            continue
        coefficient = sp.expand(term / X ** (2 - i)) if i < 2 else term
        power = {0: "x^2", 1: "x", 2: ""}[i]
        if coefficient.is_number:
            sign = "-" if coefficient < 0 else "+"
            size = abs(coefficient)
            body = (latex_value(size) if size != 1 or not power else "") + power
        else:
            lead = coefficient.as_ordered_terms()[0]
            if len(coefficient.as_ordered_terms()) == 1:
                sign = "-" if lead.as_coeff_Mul()[0] < 0 else "+"
                body = tidy_latex(-coefficient if sign == "-" else coefficient) + power
            else:
                negative = tidy_latex(coefficient).startswith("-")
                sign = "-" if negative else "+"
                inside = tidy_latex(-coefficient if negative else coefficient)
                body = rf"\left({inside}\right){power}"
        out += (("-" if sign == "-" else "") if not out else f" {sign} ") + body
    return out


def _set_latex(found) -> str:
    if found == sp.S.EmptySet:
        return r"\text{no } k"
    pieces = found.args if isinstance(found, sp.Union) else (found,)
    out = []
    for piece in pieces:
        if isinstance(piece, sp.Interval):
            lo, hi = piece.start, piece.end
            if lo == -sp.oo:
                out.append(rf"k {'<' if piece.right_open else r'\le'} {latex_value(hi)}")
            elif hi == sp.oo:
                out.append(rf"k {'>' if piece.left_open else r'\ge'} {latex_value(lo)}")
            else:
                out.append(rf"{latex_value(lo)} < k < {latex_value(hi)}")
    return r",\ ".join(out) if len(out) < 2 else r"\ \text{or}\ ".join(out)


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
