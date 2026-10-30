"""SuvatSolver: motion with constant acceleration in a straight line: from three of s, u, v, a, t,
the equation that leaves out the fifth gives the fourth, and the velocity-time graph shows why
(9709 4.2).

The five equations each leave out one quantity: v = u + at (no s), s = ½(u + v)t (no a),
s = ut + ½at² (no v), s = vt − ½at² (no u), v² = u² + 2as (no t). Choose the one without the
quantity that is neither given nor wanted. On the velocity-time graph the line from (0, u) to
(t, v) has gradient a, and the area under it is the displacement s. SymPy solves exactly; a
quadratic in t keeps the first positive time, and v from v² is taken positive.
Units: metres and seconds; answers to 3 significant figures.
"""

import re
from typing import Annotated, Literal

import sympy as sp
from manim import Dot, Line, Polygon, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import label, make_plot, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_sf

S, U, V, A, T = sp.symbols("s u v a t", real=True)
SYMBOLS = {"s": S, "u": U, "v": V, "a": A, "t": T}
EQUATIONS = {
    "s": (sp.Eq(V, U + A * T), r"v = u + at"),
    "a": (sp.Eq(S, (U + V) * T / 2), r"s = \tfrac{1}{2}(u + v)t"),
    "v": (sp.Eq(S, U * T + A * T**2 / 2), r"s = ut + \tfrac{1}{2}at^2"),
    "u": (sp.Eq(S, V * T - A * T**2 / 2), r"s = vt - \tfrac{1}{2}at^2"),
    "t": (sp.Eq(V**2, U**2 + 2 * A * S), r"v^2 = u^2 + 2as"),
}
# the same equations with each quantity a slot, * where two things multiply
TEMPLATES = {
    "s": "{v} = {u} + {a}*{t}",
    "a": r"{s} = \tfrac{1}{2}({u} + {v})*{t}",
    "v": r"{s} = {u}*{t} + \tfrac{1}{2}*{a}*{t}^2",
    "u": r"{s} = {v}*{t} - \tfrac{1}{2}*{a}*{t}^2",
    "t": "{v}^2 = {u}^2 + 2*{a}*{s}",
}
UNITS = {
    "s": r"\text{ m}",
    "u": r"\text{ m s}^{-1}",
    "v": r"\text{ m s}^{-1}",
    "a": r"\text{ m s}^{-2}",
    "t": r"\text{ s}",
}
Value = Annotated[float, Field(ge=-1000, le=1000)] | None


class SuvatSolverParams(PrimitiveParams):
    s: Value = Field(default=None, description="Displacement (m)")
    u: Value = Field(default=None, description="Initial velocity (m/s)")
    v: Value = Field(default=None, description="Final velocity (m/s)")
    a: Value = Field(default=None, description="Acceleration (m/s²)")
    t: Value = Field(default=None, description="Time (s)")
    find: Literal["s", "u", "v", "a", "t"]


class SuvatSolver(StagedPrimitive[SuvatSolverParams]):
    primitive_id = "SuvatSolver"
    version = "1"
    topic = "Kinematics"
    params_model = SuvatSolverParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[
            ("axes", "*"),
            ("line", "*"),
            ("area", "*"),
            ("dots", "*"),
            ("gradient", "*"),
        ],
    )

    def default_params(self) -> SuvatSolverParams:
        return SuvatSolverParams(u=4, a=2, t=5, find="s")

    def validate(self, params: SuvatSolverParams) -> list[PredicateFailure]:
        known = [k for k in SYMBOLS if getattr(params, k) is not None]
        if len(known) != 3:
            message = f"give exactly three of s, u, v, a, t (given: {', '.join(known) or 'none'})"
            return [_failure("three_known", message, *SYMBOLS)]
        if params.find in known:
            return [_failure("find_unknown", "the quantity to find must not be given", "find")]
        if params.t is not None and params.t <= 0:
            return [_failure("time_positive", "the time must be positive", "t")]
        try:
            work = _Work(params)
        except _NoSolution as problem:
            return [_failure("solvable", str(problem), "find")]
        if work.values["t"] <= 0:
            return [_failure("time_positive", "the time comes out zero or negative", "t")]
        return []

    def computed_values(self, params: SuvatSolverParams) -> dict[str, str]:
        work = _Work(params)
        return {k: format_sf(v) for k, v in work.values.items()}

    def build(self, params: SuvatSolverParams, level):
        work = _Work(params)
        u, v, t = (float(work.values[k]) for k in "uvt")
        plot = make_plot(
            style.GRAPH_REGION,
            [0, t],
            [u, v, 0],
            x_label=r"t\text{ (s)}",
            y_label=r"v\text{ (m s}^{-1})",
            x_from_zero=True,
        )
        start, end = plot.point(0, u), plot.point(t, v)
        parts = {
            "axes": plot.axes,
            "x_label": plot.x_label,
            "y_label": plot.y_label,
            "title": text_line(work.known_latex(), plot.upper),
            "line": Line(start, end, color=style.CURVE_COLOUR, stroke_width=5),
            "dots": VGroup(
                Dot(start, color=style.POINT_COLOUR), Dot(end, color=style.POINT_COLOUR)
            ),
            "area": Polygon(
                plot.point(0, 0),
                start,
                end,
                plot.point(t, 0),
                stroke_width=0,
                fill_color=style.AREA_COLOUR,
                fill_opacity=style.AREA_OPACITY,
            ),
            "answer": text_line(work.answer_latex(), plot.lower, colour=style.HIGHLIGHT_COLOUR),
        }
        corner = plot.point(t, u)
        parts["gradient"] = VGroup(
            Line(start, corner, color=style.RUN_COLOUR, stroke_width=2.5),
            Line(corner, end, color=style.RISE_COLOUR, stroke_width=2.5),
        )
        parts["area_label"] = label(
            rf"s = {format_sf(work.values['s'])}", colour=style.AREA_COLOUR
        ).move_to(plot.point(t / 2, (u + v) / 4 if abs(u + v) > 1e-9 else 0.5))
        parts["gradient_label"] = label(
            rf"a = {format_sf(work.values['a'])}", colour=style.RISE_COLOUR, size=26
        ).next_to((corner + end) / 2, [1, 0, 0], buff=0.12)
        parts["u_label"] = label(
            rf"u = {format_sf(work.values['u'])}", colour=style.POINT_COLOUR, size=26
        ).next_to(start, [1, 1 if u >= v else -1, 0], buff=0.1)
        parts["v_label"] = label(
            rf"v = {format_sf(work.values['v'])}", colour=style.POINT_COLOUR, size=26
        ).next_to(end, [-1, 1 if v > u else -1, 0], buff=0.1)
        rows = work.rows()
        box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], box, size=32, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: SuvatSolverParams, level) -> list[Stage]:
        n = len(_Work(params).rows())
        steps = [
            stage("list", "List the five quantities: three are known", 3.0, ["title", "row_1"]),
            stage(
                "choose",
                "Choose the equation that leaves out the quantity we neither know nor want",
                3.5,
                ["row_2"],
                emphasise=["row_2"],
            ),
            stage("solve", "Substitute and solve", 3.5, [f"row_{i}" for i in range(3, n + 1)]),
            stage(
                "graph",
                "On the velocity-time graph the gradient is a, and the area under it is s",
                4.0,
                [
                    "axes",
                    "x_label",
                    "y_label",
                    "line",
                    "dots",
                    "u_label",
                    "v_label",
                    "gradient",
                    "gradient_label",
                    "area",
                    "area_label",
                    "answer",
                ],
                emphasise=["answer"],
            ),
        ]

        def standard(s):
            return [
                s[0],
                combine("solve", "Choose the equation, substitute and solve", 4.0, s[1], s[2]),
                s[3],
            ]

        def concise(s):
            return [
                combine("solve", "The equation without the unwanted quantity, solved", 4.5, *s[:3]),
                s[3],
            ]

        return by_level(level, steps, standard, concise)


class _NoSolution(ValueError):
    pass


class _Work:
    def __init__(self, params: SuvatSolverParams):
        self.params = params
        self.known = {
            k: exact(getattr(params, k)) for k in SYMBOLS if getattr(params, k) is not None
        }
        unknown = [k for k in SYMBOLS if k not in self.known]
        self.find = params.find
        self.other = next(k for k in unknown if k != params.find)
        self.equation, self.equation_tex = EQUATIONS[self.other]
        found = self._solve(self.equation, self.find)
        self.values = dict(self.known)
        self.values[self.find] = found
        # the remaining quantity, from the equation that leaves out the one just found
        second = (
            self._solve(EQUATIONS[self.find][0], self.other) if self.other != self.find else None
        )
        self.values[self.other] = second
        self.values = {k: sp.nsimplify(v) for k, v in self.values.items()}

    def _solve(self, equation, name):
        target = SYMBOLS[name]
        known = {SYMBOLS[k]: v for k, v in getattr(self, "values", self.known).items() if k != name}
        roots = [sp.nsimplify(r) for r in sp.solve(equation.subs(known), target) if r.is_real]
        if name == "t":
            roots = [r for r in roots if r > 0]
        if name == "v":
            roots = sorted(roots, key=lambda r: -float(r))  # from v^2: the positive root
        if not roots:
            raise _NoSolution(f"no real {'positive ' if name == 't' else ''}value of {name} fits")
        return min(roots) if name == "t" else roots[0]

    def known_latex(self) -> str:
        return r",\ ".join(f"{k} = {_number(v)}" for k, v in self.known.items())

    def answer_latex(self) -> str:
        return rf"{self.find} = {format_sf(self.values[self.find])}{UNITS[self.find]}"

    def rows(self) -> list[tuple[str, object]]:
        listed = []
        for k in SYMBOLS:
            if k in self.known:
                listed.append(f"{k} = {_number(self.known[k])}")
            elif k == self.find:
                listed.append(f"{k} = ?")
        substituted = sp.latex(
            self.equation.subs({SYMBOLS[k]: sp.UnevaluatedExpr(v) for k, v in self.known.items()})
        )
        return [
            (r",\ ".join(listed), None),
            (self.equation_tex, style.RISE_COLOUR),
            (substituted, None),
            (
                rf"{self.find} = {format_sf(self.values[self.find])}{UNITS[self.find]}",
                style.HIGHLIGHT_COLOUR,
            ),
        ]


def _number(value) -> str:
    """A given value as written, in decimals: 9.8, not 49/5."""
    return format_sf(value, 6)


def _substitute(template: str, known: dict) -> str:
    """The equation with the known values in their slots: 0^2 = 20^2 + 2 x a x 50."""
    pieces = re.split(r"(\{[suvat]\})", template)
    out = []
    for piece in pieces:
        match = re.fullmatch(r"\{([suvat])\}", piece)
        if not match:
            out.append(piece)
            continue
        name = match.group(1)
        if name not in known:
            out.append(name)
            continue
        value = known[name]
        text = _number(value)
        out.append(rf"\left({text}\right)" if value < 0 else text)
    text = "".join(out)
    # a times sign before a number; a letter is simply written next to what it multiplies
    text = re.sub(r"\*(?=[0-9(]|\\left)", r" \\times ", text)
    return text.replace("*", "")


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
