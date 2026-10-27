"""AngleChaser: finding unknown angles with the angle facts, each step labelled with its reason
(4024 4.6.1, 4.6.2; PRIMITIVES.md #27).

Layouts: angles on a straight line (sum 180°), angles round a point (sum 360°), two crossing
lines and a transversal across parallel lines (vertically opposite, corresponding, alternate and
co-interior angles), and a triangle (sum 180°, isosceles base angles, the exterior angle). Angles
may be written in x, e.g. "2*x" and "x + 30"; SymPy solves for x and the figure is drawn with
the true angles. For parallel lines the reason is worked out from where the two angles are.
"""

import math
from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import Line, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import (
    Diagram,
    angle_label_position,
    angle_mark,
    label,
    split_columns,
    text_line,
)
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import ExpressionError, latex_value, parse_expression

AngleText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
Position = Literal[
    "upper_tr", "upper_tl", "upper_bl", "upper_br", "lower_tr", "lower_tl", "lower_bl", "lower_br"
]
X = sp.Symbol("x", real=True)
TOTAL = {"line": 180, "point": 360, "triangle": 180}
REASON = {
    "line": r"\text{angles on a straight line add to } 180^\circ",
    "point": r"\text{angles round a point add to } 360^\circ",
    "triangle": r"\text{angles in a triangle add to } 180^\circ",
    "exterior": r"\begin{array}{l}\text{exterior angle} = \text{sum of the}\\"
    r"\text{interior opposite angles}\end{array}",
    "vertically_opposite": r"\text{vertically opposite angles are equal}",
    "straight": r"\text{angles on a straight line add to } 180^\circ",
    "corresponding": r"\text{corresponding angles are equal}",
    "alternate": r"\text{alternate angles are equal}",
    "co_interior": r"\text{co-interior angles add to } 180^\circ",
}
QUADRANTS = ["tr", "tl", "bl", "br"]
COLOURS = [
    style.CURVE_COLOUR,
    style.RUN_COLOUR,
    style.RISE_COLOUR,
    style.SECANT_COLOUR,
    style.AREA_COLOUR,
]


class AngleChaserParams(PrimitiveParams):
    layout: Literal["line", "point", "crossing", "parallel", "triangle"]
    angles: list[AngleText] | None = Field(
        default=None,
        max_length=5,
        description="For line, point, triangle: the angles in degrees, in order, written in x "
        'where unknown, e.g. ["2*x", "x + 30", "60"]',
    )
    exterior: bool = Field(
        default=False, description="Triangle: the third angle is the exterior angle at C"
    )
    isosceles: bool = Field(default=False, description="Triangle: mark CA = CB")
    given: Annotated[float, Field(gt=10, lt=170)] | None = Field(
        default=None, description="For crossing and parallel: the known angle in degrees"
    )
    given_at: Position = "upper_tr"
    find_at: Position = "lower_bl"


class AngleChaser(StagedPrimitive[AngleChaserParams]):
    primitive_id = "AngleChaser"
    version = "1"
    topic = "Geometry"
    params_model = AngleChaserParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("figure", "*"), ("given", "find"), ("step_*", "*")],
    )

    def default_params(self) -> AngleChaserParams:
        return AngleChaserParams(layout="line", angles=["2*x", "x + 30", "60"])

    def validate(self, params: AngleChaserParams) -> list[PredicateFailure]:
        if params.layout in ("crossing", "parallel"):
            if params.given is None:
                return [_failure("needs_given", "give the known angle", "given")]
            if params.given_at == params.find_at:
                return [_failure("positions_differ", "find a different angle", "find_at")]
            if params.layout == "crossing" and (
                params.given_at.startswith("lower") or params.find_at.startswith("lower")
            ):
                message = "two crossing lines have one crossing: use upper_ positions"
                return [_failure("one_crossing", message, "given_at", "find_at")]
            return []
        if params.angles is None:
            return [_failure("needs_angles", "give the angles", "angles")]
        count = len(params.angles)
        if params.layout == "triangle" and count != 3:
            return [_failure("three_angles", "a triangle needs three angles", "angles")]
        if count < 2:
            return [_failure("two_angles", "give at least two angles", "angles")]
        try:
            exprs = [parse_expression(a, {"x"}) for a in params.angles]
        except ExpressionError as error:
            return [_failure("angles_parse", str(error), "angles")]
        if not any(e.has(X) for e in exprs):
            return [_failure("has_unknown", "write the unknown angle as x", "angles")]
        solutions = sp.solve(sp.Eq(*_equation(params, exprs)), X)
        if len(solutions) != 1 or not solutions[0].is_real:
            return [_failure("one_solution", "the angles do not give one value of x", "angles")]
        values = [e.subs(X, solutions[0]) for e in exprs]
        if any(v <= 3 for v in values):
            return [_failure("positive_angles", "an angle would be 3° or less", "angles")]
        if params.layout == "line" and max(values) >= 180:
            return [_failure("angles_fit", "an angle on a line must be under 180°", "angles")]
        if params.layout == "triangle":
            interior = values[:2] + [180 - values[2] if params.exterior else values[2]]
            if any(v <= 3 for v in interior):
                return [_failure("triangle_exists", "these angles make no triangle", "angles")]
            if params.isosceles and interior[0] != interior[1]:
                message = "isosceles with CA = CB needs equal angles at A and B"
                return [_failure("isosceles_equal", message, "angles")]
        return []

    def computed_values(self, params: AngleChaserParams) -> dict[str, str]:
        if params.layout in ("crossing", "parallel"):
            return {"x": _plain(_chain(params)[-1][3])}
        exprs, x = _solved(params)
        values = {"x": _plain(x)}
        for i, e in enumerate(exprs):
            values[f"angle_{i + 1}"] = _plain(e.subs(X, x))
        return values

    def build(self, params: AngleChaserParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        figure_box, working_box = split_columns(area, [1.1, 1], gap=0.3)
        if params.layout in ("crossing", "parallel"):
            parts = _lines_figure(params, figure_box)
            steps = _chain(params)
            rows = []
            for i, (_, _, reason, value) in enumerate(steps, start=1):
                name = "x" if i == len(steps) else f"a_{i}"
                rows.append((f"reason_{i}", REASON[reason], 26))
                rows.append((f"value_{i}", rf"{_name_tex(name)} = {_plain(value)}^\circ", 34))
            answer = rf"x = {_plain(steps[-1][3])}^\circ"
            question = r"\text{Find the angle } x"
        else:
            parts = _sum_figure(params, figure_box)
            exprs, x = _solved(params)
            left, right = _equation(params, exprs)
            simplified = sp.expand(left)
            rows = [("reason_1", _reason(params), 26)]
            rows.append(("equation", rf"{_sum_tex(params, exprs)} = {sp.latex(right)}", 34))
            if _combines(params, exprs):
                rows.append(("simplified", rf"{sp.latex(simplified)} = {sp.latex(right)}", 34))
            rows.append(("value_1", rf"x = {_plain(x)}", 34))
            answer = rf"x = {_plain(x)}"
            question = r"\text{Find } x"
        mobjects = [label(tex, size=size) for _, tex, size in rows]
        group = VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.25)
        for mob in mobjects:
            if mob.width > working_box.width:
                mob.scale_to_fit_width(working_box.width)
        style.fit_inside(group.arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.25), working_box)
        for (name, _, _), mob in zip(rows, mobjects, strict=True):
            parts[name] = mob
            if name.startswith("reason"):
                mob.set_color(style.HIGHLIGHT_COLOUR)
        parts["question"] = text_line(question, upper)
        parts["answer"] = text_line(answer, lower, colour=style.HIGHLIGHT_COLOUR)
        return parts

    def stages(self, params: AngleChaserParams, level) -> list[Stage]:
        figure = stage(
            "figure", "Here is the diagram", 2.5, ["question", "figure", "given", "find"]
        )
        if params.layout in ("crossing", "parallel"):
            steps = [figure]
            chain = _chain(params)
            for i, (_, _, reason, _) in enumerate(chain, start=1):
                words = REASON_WORDS[reason]
                show = [f"reason_{i}", f"value_{i}"] + ([f"step_{i}"] if i < len(chain) else [])
                steps.append(stage(f"step_{i}", words, 3.0, show, emphasise=[f"value_{i}"]))
            steps.append(stage("answer", "So", 1.5, ["answer"]))
        else:
            work = [n for n in ("equation", "simplified") if n in self._names(params)]
            steps = [
                figure,
                stage(
                    "reason",
                    REASON_WORDS[_reason_key(params)],
                    3.0,
                    ["reason_1"],
                    emphasise=["reason_1"],
                ),
                stage("equation", "Write it as an equation", 3.0, work),
                stage("solve", "Solve for x", 2.5, ["value_1", "answer"], emphasise=["answer"]),
            ]

        def standard(s):
            return [s[0], combine("reason", s[1].description, 4.0, s[1], s[2]), *s[3:]]

        def concise(s):
            return [s[0], combine("working", "Use the angle facts", 4.5, *s[1:])]

        return by_level(level, steps, standard, concise)

    def _names(self, params: AngleChaserParams) -> set[str]:
        exprs, _ = _solved(params)
        left, _ = _equation(params, exprs)
        names = {"equation"}
        if _combines(params, exprs):
            names.add("simplified")
        return names


REASON_WORDS = {
    "line": "Angles on a straight line add up to 180 degrees",
    "point": "Angles round a point add up to 360 degrees",
    "triangle": "The angles in a triangle add up to 180 degrees",
    "exterior": "The exterior angle equals the sum of the two interior opposite angles",
    "isosceles": "The base angles of an isosceles triangle are equal, and the angles add up "
    "to 180 degrees",
    "vertically_opposite": "Vertically opposite angles are equal",
    "straight": "Angles on a straight line add up to 180 degrees",
    "corresponding": "Corresponding angles are equal",
    "alternate": "Alternate angles are equal",
    "co_interior": "Co-interior angles add up to 180 degrees",
}


def _equation(params: AngleChaserParams, exprs: list[sp.Expr]) -> tuple[sp.Expr, sp.Expr]:
    if params.layout == "triangle" and params.exterior:
        return exprs[0] + exprs[1], exprs[2]
    return sp.Add(*exprs), sp.Integer(TOTAL[params.layout])


def _solved(params: AngleChaserParams) -> tuple[list[sp.Expr], sp.Expr]:
    exprs = [parse_expression(a, {"x"}) for a in params.angles]
    return exprs, sp.solve(sp.Eq(*_equation(params, exprs)), X)[0]


def _combines(params: AngleChaserParams, exprs: list[sp.Expr]) -> bool:
    """Whether collecting like terms shortens the written sum, so it is worth a line."""
    written = sum(len(sp.Add.make_args(e)) for e in _equation_terms(params, exprs))
    return len(sp.Add.make_args(_equation(params, exprs)[0])) < written


def _equation_terms(params: AngleChaserParams, exprs: list[sp.Expr]) -> list[sp.Expr]:
    return exprs[:2] if params.layout == "triangle" and params.exterior else exprs


def _reason_key(params: AngleChaserParams) -> str:
    if params.layout == "triangle":
        if params.exterior:
            return "exterior"
        return "isosceles" if params.isosceles else "triangle"
    return params.layout


def _reason(params: AngleChaserParams) -> str:
    key = _reason_key(params)
    return REASON["triangle"] if key == "isosceles" else REASON[key]


def _plain(value) -> str:
    return latex_value(sp.nsimplify(value))


def _angle_tex(expr: sp.Expr) -> str:
    if isinstance(expr, sp.Add):
        return rf"({sp.latex(expr)})^\circ"
    return rf"{sp.latex(expr)}^\circ"


def _sum_tex(params: AngleChaserParams, exprs: list[sp.Expr]) -> str:
    terms = _equation_terms(params, exprs)
    return " + ".join(rf"({sp.latex(e)})" if isinstance(e, sp.Add) else sp.latex(e) for e in terms)


def _name_tex(name: str) -> str:
    return "x" if name == "x" else rf"a_{{{name[2:]}}}"


def _sum_figure(params: AngleChaserParams, box) -> dict:
    exprs, x = _solved(params)
    values = [float(e.subs(X, x)) for e in exprs]
    if params.layout == "triangle":
        return _triangle_figure(params, exprs, values, box)
    total = TOTAL[params.layout]
    directions = [0.0]
    for v in values[:-1]:
        directions.append(directions[-1] + v)
    rays = [(math.cos(math.radians(d)), math.sin(math.radians(d))) for d in directions]
    extent = [(0, 0), (1, 0), (-1, 0)] + ([(0, 1)] if total == 180 else [(0, 1), (0, -1)])
    diagram = Diagram(extent, box, margin=0.6)
    o = diagram.p(0, 0)
    figure = VGroup()
    if total == 180:
        figure.add(Line(diagram.p(-1, 0), diagram.p(1, 0), stroke_width=4))
    for i, (dx, dy) in enumerate(rays):
        if total == 180 and i == 0:
            continue
        figure.add(Line(o, diagram.p(dx, dy), stroke_width=4))
    parts = {"figure": figure}
    given, find = VGroup(), VGroup()
    for i, (expr, value) in enumerate(zip(exprs, values, strict=True)):
        start = math.radians(directions[i])
        end = start + math.radians(value)
        a = o + np.array([math.cos(start), math.sin(start), 0])
        b = o + np.array([math.cos(end), math.sin(end), 0])
        radius = 0.45 + 0.18 * (i % 2)
        colour = COLOURS[i % len(COLOURS)]
        reflex = value > 180
        arc = angle_mark(o, a, b, radius=radius, colour=colour, reflex=reflex)
        text = label(_angle_tex(expr), colour=colour, size=28)
        distance = radius + 0.25 + max(text.width, text.height) / 2
        text.move_to(angle_label_position(o, a, b, distance, reflex=reflex))
        (find if expr.has(X) else given).add(VGroup(arc, text))
    parts["given"] = given
    parts["find"] = find
    return parts


def _triangle_figure(params, exprs, values, box) -> dict:
    a_angle = values[0]
    b_angle = values[1]
    c_interior = 180 - values[2] if params.exterior else values[2]
    # base AB of length 1; C from the angles at A and B (sine rule)
    side_ac = math.sin(math.radians(b_angle)) / math.sin(math.radians(c_interior))
    c = (side_ac * math.cos(math.radians(a_angle)), side_ac * math.sin(math.radians(a_angle)))
    points = [(0.0, 0.0), (1.0, 0.0), c]
    direction = np.array([c[0], c[1]]) / max(math.hypot(*c), 1e-9)
    beyond = (c[0] + 0.45 * direction[0], c[1] + 0.45 * direction[1])
    diagram = Diagram(points + ([beyond] if params.exterior else []), box, margin=0.7)
    pa, pb, pc = (diagram.p(*pt) for pt in points)
    figure = VGroup(diagram.polygon(points, color=style.TEXT_COLOUR, stroke_width=4))
    rays = {"A": [pb, pc], "B": [pa, pc], "C": [pa, pb]}
    if params.exterior:
        figure.add(Line(pc, diagram.p(*beyond), stroke_width=4))
        rays["C"].append(diagram.p(*beyond))
    for name, point in (("A", pa), ("B", pb), ("C", pc)):
        figure.add(label(name, size=30).move_to(point + 0.35 * _widest_gap(point, rays[name])))
    if params.isosceles:
        for p, q in ((pa, pc), (pb, pc)):
            mid = (p + q) / 2
            normal = np.array([-(q - p)[1], (q - p)[0], 0])
            normal = normal / np.linalg.norm(normal) * 0.12
            figure.add(Line(mid - normal, mid + normal, stroke_width=3))
    corners = [(pa, pb, pc), (pb, pc, pa)]
    corners.append((pc, diagram.p(*beyond), pb) if params.exterior else (pc, pa, pb))
    given, find = VGroup(), VGroup()
    for i, (expr, (vertex, p, q)) in enumerate(zip(exprs, corners, strict=True)):
        colour = COLOURS[i]
        arc = angle_mark(vertex, p, q, radius=0.4, colour=colour)
        text = label(_angle_tex(expr), colour=colour, size=28)
        distance = 0.65 + max(text.width, text.height) / 2
        text.move_to(angle_label_position(vertex, p, q, distance))
        (find if expr.has(X) else given).add(VGroup(arc, text))
    return {"figure": figure, "given": given, "find": find}


def _widest_gap(vertex: np.ndarray, ends: list[np.ndarray]) -> np.ndarray:
    """The unit direction from a vertex that bisects the widest gap between its lines."""
    angles = sorted(math.atan2(e[1] - vertex[1], e[0] - vertex[0]) for e in ends)
    following = angles[1:] + [angles[0] + 2 * math.pi]
    width, start = max((b - a, a) for a, b in zip(angles, following, strict=True))
    middle = start + width / 2
    return np.array([math.cos(middle), math.sin(middle), 0.0])


def _phi(params: AngleChaserParams) -> float:
    """The angle the transversal makes with the lines, measured anticlockwise from the right."""
    quadrant = params.given_at.split("_")[1]
    return params.given if quadrant in ("tr", "bl") else 180 - params.given


def _value_at(params: AngleChaserParams, position: str) -> float:
    quadrant = position.split("_")[1]
    phi = _phi(params)
    return phi if quadrant in ("tr", "bl") else 180 - phi


def _relation(a: str, b: str) -> str:
    """The angle fact linking two positions one step apart."""
    (ia, qa), (ib, qb) = a.split("_"), b.split("_")
    if ia == ib:
        opposite = {"tr": "bl", "bl": "tr", "tl": "br", "br": "tl"}
        return "vertically_opposite" if opposite[qa] == qb else "straight"
    if qa == qb:
        return "corresponding"
    interior = {("upper", "bl"), ("upper", "br"), ("lower", "tl"), ("lower", "tr")}
    if (ia, qa) in interior and (ib, qb) in interior:
        same_side = qa[1] == qb[1]  # both on the left (l) or both on the right (r)
        return "co_interior" if same_side else "alternate"
    raise ValueError("not one step")


def _chain(params: AngleChaserParams) -> list[tuple[str, str, str, float]]:
    """Steps (from, to, reason, value) from the given angle to x, at most two."""
    start, end = params.given_at, params.find_at
    try:
        return [(start, end, _relation(start, end), _value_at(params, end))]
    except ValueError:
        middle = f"{end.split('_')[0]}_{start.split('_')[1]}"
        return [
            (start, middle, "corresponding", _value_at(params, middle)),
            (middle, end, _relation(middle, end), _value_at(params, end)),
        ]


def _lines_figure(params: AngleChaserParams, box) -> dict:
    phi = math.radians(_phi(params))
    crossing = params.layout == "crossing"
    t = (math.cos(phi), math.sin(phi))
    centres = (
        {"upper": (0.0, 0.0)}
        if crossing
        else {"upper": (1 / math.tan(phi), 1.0), "lower": (-1 / math.tan(phi), -1.0)}
    )
    reach = 1.9
    ends = [(-2.4, 0), (2.4, 0)] if crossing else [(-2.6, 1), (2.6, 1), (-2.6, -1), (2.6, -1)]
    low, high = centres["upper" if crossing else "lower"], centres["upper"]
    span = [
        (low[0] - reach * t[0], low[1] - reach * t[1]),
        (high[0] + reach * t[0], high[1] + reach * t[1]),
    ]
    diagram = Diagram(ends + span, box, margin=0.3)
    figure = VGroup()
    if crossing:
        figure.add(Line(diagram.p(-2.4, 0), diagram.p(2.4, 0), stroke_width=4))
    else:
        for y in (1, -1):
            figure.add(Line(diagram.p(-2.6, y), diagram.p(2.6, y), stroke_width=4))
            for k in (0, 1):  # arrows marking the lines as parallel
                tip = diagram.p(-1.9 + 0.18 * k, y)
                figure.add(Line(tip, tip + np.array([-0.15, 0.12, 0]), stroke_width=3))
                figure.add(Line(tip, tip + np.array([-0.15, -0.12, 0]), stroke_width=3))
    first, last = span[0], span[-1]
    figure.add(Line(diagram.p(*first), diagram.p(*last), stroke_width=4))

    def mark(position, text, colour, radius=0.5):
        where, quadrant = position.split("_")
        o = diagram.p(*centres[where])
        rays = [0.0, math.degrees(phi), 180.0, 180 + math.degrees(phi), 360.0]
        k = QUADRANTS.index(quadrant)
        a0, a1 = math.radians(rays[k]), math.radians(rays[k + 1])
        a = o + np.array([math.cos(a0), math.sin(a0), 0])
        b = o + np.array([math.cos(a1), math.sin(a1), 0])
        arc = angle_mark(o, a, b, radius=radius, colour=colour)
        tex = label(text, colour=colour, size=28)
        tex.move_to(angle_label_position(o, a, b, radius + 0.2 + max(tex.width, tex.height) / 2))
        return VGroup(arc, tex)

    parts = {
        "figure": figure,
        "given": mark(params.given_at, rf"{_plain(params.given)}^\circ", style.CURVE_COLOUR),
        "find": mark(params.find_at, "x", style.HIGHLIGHT_COLOUR),
    }
    chain = _chain(params)
    for i, (_, to, _, _) in enumerate(chain[:-1], start=1):
        parts[f"step_{i}"] = mark(to, rf"a_{{{i}}}", style.RISE_COLOUR, radius=0.42)
    return parts


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
