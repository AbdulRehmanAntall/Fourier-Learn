"""ModulusEquation: equations and inequalities with |ax + b|, solved algebraically and read from
the V-shaped graphs (9709 2.1, 3.1).

When both sides are moduli, |a| = |b| ⇔ a² = b², so squaring gives a quadratic with no answers
to reject. When one side is not a modulus, |u| splits into two cases, u where u ≥ 0 and −u where
u < 0; each case gives a candidate, which counts only if it satisfies its own case. The graphs
of the two sides meet at exactly the solutions of the equation, and an inequality's solution is
where one graph lies above or below the other, shaded on the x-axis. SymPy solves every case and
the inequality exactly.
"""

from typing import Literal

import numpy as np
import sympy as sp
from manim import Dot, Line, VGroup
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
RELATIONS = {"=": sp.Eq, "<": sp.Lt, ">": sp.Gt, "<=": sp.Le, ">=": sp.Ge}
RELATION_LATEX = {"=": "=", "<": "<", ">": ">", "<=": r"\le", ">=": r"\ge"}
SOLUTION_COLOUR = style.HIGHLIGHT_COLOUR


class ModulusEquationParams(PrimitiveParams):
    left: str = Field(min_length=1, max_length=60, description='e.g. "abs(3*x - 2)"')
    relation: Literal["=", "<", ">", "<=", ">="] = "="
    right: str = Field(
        min_length=1, max_length=60, description='e.g. "abs(2*x + 7)", "2*x + 5" or "4"'
    )


class ModulusEquation(StagedPrimitive[ModulusEquationParams]):
    primitive_id = "ModulusEquation"
    version = "1"
    topic = "Algebra"
    params_model = ModulusEquationParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[
            ("axes", "*"),
            ("left_graph", "*"),
            ("right_graph", "*"),
            ("meets", "*"),
            ("solution_bar", "*"),
        ],
    )

    def default_params(self) -> ModulusEquationParams:
        return ModulusEquationParams(left="abs(3*x - 2)", relation="=", right="abs(2*x + 7)")

    def validate(self, params: ModulusEquationParams) -> list[PredicateFailure]:
        sides = {}
        for name in ("left", "right"):
            try:
                sides[name] = parse_expression(getattr(params, name), {"x"})
            except ExpressionError as error:
                return [_failure("parsing", "expression_parses", str(error), name)]
        moduli = [len(side.atoms(sp.Abs)) for side in sides.values()]
        if sum(moduli) == 0:
            return [_failure("consistency", "has_modulus", "use abs(...) on at least one side")]
        for name, side in sides.items():
            if len(side.atoms(sp.Abs)) > 1:
                message = "at most one modulus on each side"
                return [_failure("consistency", "simple_form", message, name)]
            for modulus in side.atoms(sp.Abs):
                inside = modulus.args[0]
                if not inside.is_polynomial(X) or sp.degree(inside, X) != 1:
                    message = "the inside of a modulus must be linear, ax + b"
                    return [_failure("consistency", "linear_inside", message, name)]
            flat = side.subs({m: sp.Symbol("m") for m in side.atoms(sp.Abs)})
            if not flat.is_polynomial(X, sp.Symbol("m")) or sp.degree(flat, X) > 1:
                message = "each side must be linear apart from the modulus"
                return [_failure("consistency", "linear_sides", message, name)]
        problem = _Problem(params)
        if problem.both and not problem.pure:
            message = "with a modulus on both sides, each side must be k|ax + b| alone"
            return [_failure("consistency", "simple_form", message, "left", "right")]
        if params.relation == "=":
            if not isinstance(problem.solution, sp.FiniteSet) or not problem.solution:
                message = "the equation must have a finite, non-empty set of solutions"
                return [_failure("consistency", "has_solutions", message, "left", "right")]
        elif problem.solution in (sp.S.EmptySet, sp.S.Reals):
            message = "the inequality must hold for some x but not every x"
            return [_failure("consistency", "has_solutions", message, "relation")]
        if not problem.critical:
            message = "the two sides never meet"
            return [_failure("consistency", "has_solutions", message, "left", "right")]
        return []

    def computed_values(self, params: ModulusEquationParams) -> dict[str, str]:
        problem = _Problem(params)
        values = {"solution": str(problem.solution)}
        for i, x in enumerate(problem.critical, start=1):
            values[f"critical_{i}"] = format_value(x)
        return values

    def build(self, params: ModulusEquationParams, level):
        problem = _Problem(params)
        crit = [float(c) for c in problem.critical]
        lo, hi = min(crit), max(crit)
        pad = max(2.0, 0.5 * (hi - lo))
        x_lo, x_hi = lo - pad, hi + pad
        f = sp.lambdify(X, problem.left, "math")
        g = sp.lambdify(X, problem.right, "math")
        xs = np.linspace(x_lo, x_hi, 81)
        plot = make_plot(style.GRAPH_REGION, [x_lo, x_hi], [*map(f, xs), *map(g, xs)])
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "title": text_line(problem.statement_latex(), plot.upper),
            "left_graph": curve(plot, f, x_lo, x_hi),
            "right_graph": curve(plot, g, x_lo, x_hi, colour=style.RUN_COLOUR),
        }
        parts["meets"] = VGroup(*(Dot(plot.point(x, f(x)), color=style.POINT_COLOUR) for x in crit))
        obstacles = [*plot.obstacles(), parts["meets"]]
        paths = [parts["left_graph"], parts["right_graph"], *plot.axis_lines()]
        for name, text, colour, fn in (
            ("left_label", params.left, style.CURVE_COLOUR, f),
            ("right_label", params.right, style.RUN_COLOUR, g),
        ):
            anchor_x = x_hi if name == "left_label" else x_lo
            y = min(max(fn(anchor_x), plot.y_range[0]), plot.y_range[1])
            mob = label(f"y = {written_latex(text)}", colour=colour)
            parts[name] = place_label(
                mob, plot.point(anchor_x, y), plot.plot_box, obstacles, paths, wide=True
            )
            obstacles.append(mob)
        for i, x in enumerate(problem.critical, start=1):
            mob = label(f"x = {latex_value(x)}", colour=style.POINT_COLOUR, size=26)
            parts[f"meet_{i}_label"] = place_label(
                mob, plot.point(float(x), f(float(x))), plot.plot_box, obstacles, paths, wide=True
            )
            obstacles.append(mob)
        bar = VGroup()
        if params.relation != "=":
            for start, end in problem.intervals(plot.x_range[0], plot.x_range[1]):
                bar.add(
                    Line(
                        plot.point(start, 0),
                        plot.point(end, 0),
                        color=SOLUTION_COLOUR,
                        stroke_width=10,
                    )
                )
        parts["solution_bar"] = bar
        parts["answer"] = text_line(problem.answer_latex(), plot.lower, colour=SOLUTION_COLOUR)
        rows = problem.rows()
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: ModulusEquationParams, level) -> list[Stage]:
        problem = _Problem(params)
        rows = [f"row_{i}" for i in range(1, len(problem.rows()) + 1)]
        labels = [f"meet_{i}_label" for i in range(1, len(problem.critical) + 1)]
        algebra_words = (
            "Both sides are moduli, so square both sides: no answers are lost or gained"
            if problem.both
            else "Split the modulus into its two cases, and solve each"
        )
        steps = [
            stage(
                "graphs",
                "Draw both sides: a modulus graph is a V, reflected up where it would go below "
                "the axis",
                3.5,
                [
                    "axes",
                    "x_label",
                    "y_label",
                    "title",
                    "left_graph",
                    "right_graph",
                    "left_label",
                    "right_label",
                    rows[0],
                ],
            ),
            stage("algebra", algebra_words, 3.5, rows[1:-1]),
            stage(
                "meet",
                "The graphs meet at the solutions of the equation",
                2.5,
                ["meets", *labels],
                emphasise=["meets"],
            ),
            stage(
                "answer",
                "So"
                if params.relation == "="
                else "The inequality holds where one graph is above the other: read it off",
                3.0,
                [rows[-1], "solution_bar", "answer"],
                emphasise=["answer"],
            ),
        ]

        def standard(s):
            return list(s)

        def concise(s):
            return [s[0], combine("algebra", s[1].description, 4.0, *s[1:3]), s[3]]

        return by_level(level, steps, standard, concise)


class _Problem:
    def __init__(self, params: ModulusEquationParams):
        self.params = params
        self.left = sp.nsimplify(parse_expression(params.left, {"x"}), rational=True)
        self.right = sp.nsimplify(parse_expression(params.right, {"x"}), rational=True)
        relation = RELATIONS[params.relation]
        self.solution = sp.solveset(relation(self.left, self.right), X, sp.S.Reals)
        meets = sp.solveset(sp.Eq(self.left, self.right), X, sp.S.Reals)
        self.critical = sorted(meets, key=float) if isinstance(meets, sp.FiniteSet) else []
        self.both = bool(self.left.atoms(sp.Abs)) and bool(self.right.atoms(sp.Abs))
        self.pure = self.both and all(_is_pure(side) for side in (self.left, self.right))

    def statement_latex(self) -> str:
        p = self.params
        return f"{written_latex(p.left)} {RELATION_LATEX[p.relation]} {written_latex(p.right)}"

    def intervals(self, lo: float, hi: float) -> list[tuple[float, float]]:
        clipped = sp.Intersection(self.solution, sp.Interval(lo, hi))
        pieces = clipped.args if isinstance(clipped, sp.Union) else (clipped,)
        return [(float(p.start), float(p.end)) for p in pieces if isinstance(p, sp.Interval)]

    def answer_latex(self) -> str:
        return _set_latex(self.solution)

    def rows(self) -> list[tuple[str, object]]:
        rows = [(self.statement_latex(), None)]
        if self.pure:
            a, b = (side.atoms(sp.Abs).pop().args[0] for side in (self.left, self.right))
            ka, kb = (
                sp.simplify(side / side.atoms(sp.Abs).pop()) for side in (self.left, self.right)
            )
            relation = RELATION_LATEX[self.params.relation]
            rows.append((rf"{_squared(ka, a)} {relation} {_squared(kb, b)}", None))
            quadratic = sp.expand(ka**2 * a**2 - kb**2 * b**2)
            rows.append((rf"{tidy_latex(quadratic)} {relation} 0", None))
            if self.params.relation != "=":
                critical = r",\ ".join(latex_value(c) for c in self.critical)
                rows.append((rf"\text{{Critical values: }}x = {critical}", style.POINT_COLOUR))
        else:
            for text, colour in self._cases():
                rows.append((text, colour))
        rows.append((self.answer_latex(), SOLUTION_COLOUR))
        return rows

    def _cases(self) -> list[tuple[str, object]]:
        """Each case of the modulus: its equation, its root, and whether the root is allowed."""
        modulus_side, other = (
            (self.left, self.right) if self.left.atoms(sp.Abs) else (self.right, self.left)
        )
        modulus = modulus_side.atoms(sp.Abs).pop()
        u = modulus.args[0]
        rows = []
        for sign, condition in ((1, "\\ge 0"), (-1, "< 0")):
            equation = sp.Eq(modulus_side.subs(modulus, sign * u), other)
            roots = sp.solve(equation, X)
            inside = rf"{tidy_latex(u)} {condition}"
            written = tidy_latex(sp.expand(modulus_side.subs(modulus, sign * u)))
            if not roots:
                rows.append(
                    (rf"{inside}:\ {written} = {tidy_latex(other)}\text{{, no root}}", None)
                )
                continue
            root = sp.nsimplify(roots[0])
            value = u.subs(X, root)
            ok = value >= 0 if sign == 1 else value < 0
            verdict = r"\checkmark" if ok else r"\text{ rejected}"
            rows.append(
                (
                    rf"{inside}:\ {written} = {tidy_latex(other)},\ "
                    rf"x = {latex_value(root)}\ {verdict}",
                    None if ok else style.TANGENT_COLOUR,
                )
            )
        return rows


def _is_pure(side: sp.Expr) -> bool:
    modulus = side.atoms(sp.Abs).pop()
    return sp.simplify(side / modulus).is_number


def _squared(k, inside) -> str:
    body = rf"\left({tidy_latex(inside)}\right)^2"
    return body if k == 1 else rf"{latex_value(k**2)}{body}"


def _set_latex(found) -> str:
    if isinstance(found, sp.FiniteSet):
        return "x = " + r",\ ".join(latex_value(v) for v in sorted(found, key=float))
    pieces = found.args if isinstance(found, sp.Union) else (found,)
    out = []
    for piece in pieces:
        if not isinstance(piece, sp.Interval):
            continue
        lo, hi = piece.start, piece.end
        left = "<" if piece.left_open else r"\le"
        right = "<" if piece.right_open else r"\le"
        if lo == -sp.oo:
            out.append(rf"x {right} {latex_value(hi)}")
        elif hi == sp.oo:
            out.append(rf"x {'>' if piece.left_open else r'\ge'} {latex_value(lo)}")
        else:
            out.append(rf"{latex_value(lo)} {left} x {right} {latex_value(hi)}")
    return r"\ \text{or}\ ".join(out)


def _failure(kind, predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind=kind, predicate=predicate, message=message, parameters=list(parameters)
    )
