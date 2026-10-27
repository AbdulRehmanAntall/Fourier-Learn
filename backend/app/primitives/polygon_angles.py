"""PolygonAngles: the angles of a polygon: the interior angles add to (n − 2) × 180° because
the diagonals from one vertex cut it into n − 2 triangles; the exterior angles add to 360°
because walking round it turns you once; and the number of sides of a regular polygon from one
of its angles (4024 4.6.3; PRIMITIVES.md #28).
"""

import math
from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import Line, Polygon, Sector, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import Diagram, angle_mark, label, split_columns, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import latex_value

NAMES = {
    3: "triangle",
    4: "quadrilateral",
    5: "pentagon",
    6: "hexagon",
    7: "heptagon",
    8: "octagon",
    9: "nonagon",
    10: "decagon",
    12: "dodecagon",
}
FILLS = [
    style.CURVE_COLOUR,
    style.RUN_COLOUR,
    style.RISE_COLOUR,
    style.SECANT_COLOUR,
    style.AREA_COLOUR,
]


class PolygonAnglesParams(PrimitiveParams):
    kind: Literal["interior_sum", "exterior", "find_sides"]
    sides: Annotated[int, Field(ge=3, le=12)] | None = Field(
        default=None, description="For interior_sum and exterior: the number of sides"
    )
    regular: bool = Field(default=True, description="Whether all sides and angles are equal")
    angle: Annotated[float, Field(gt=0, lt=180)] | None = Field(
        default=None, description="For find_sides: one angle of the regular polygon, in degrees"
    )
    given: Literal["interior", "exterior"] = Field(
        default="exterior", description="For find_sides: which angle is given"
    )


class PolygonAngles(StagedPrimitive[PolygonAnglesParams]):
    primitive_id = "PolygonAngles"
    version = "1"
    topic = "Geometry"
    params_model = PolygonAnglesParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("polygon", "*"), ("triangles", "*"), ("exterior", "*"), ("fan", "*")],
    )

    def default_params(self) -> PolygonAnglesParams:
        return PolygonAnglesParams(kind="interior_sum", sides=6)

    def validate(self, params: PolygonAnglesParams) -> list[PredicateFailure]:
        if params.kind == "find_sides":
            if params.angle is None:
                return [_failure("needs_angle", "give the angle", "angle")]
            exterior = _exterior(params)
            n = sp.nsimplify(360 / exterior)
            if not n.is_integer or not 3 <= n <= 36:
                message = f"360 ÷ {latex_value(exterior)} is not a whole number of sides (3 to 36)"
                return [_failure("whole_sides", message, "angle")]
            return []
        if params.sides is None:
            return [_failure("needs_sides", f"{params.kind} needs the number of sides", "sides")]
        if params.kind == "exterior" and not params.regular:
            message = "exterior angles are drawn for a regular polygon"
            return [_failure("exterior_regular", message, "regular")]
        return []

    def computed_values(self, params: PolygonAnglesParams) -> dict[str, str]:
        n = _sides(params)
        values = {
            "sides": str(n),
            "interior_sum": str((n - 2) * 180),
            "exterior_angle": latex_value(sp.Rational(360, n)),
        }
        if params.regular:
            values["interior_angle"] = latex_value(sp.Rational((n - 2) * 180, n))
        return values

    def build(self, params: PolygonAnglesParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        figure_box, working_box = split_columns(area, [1.1, 1], gap=0.3)
        n = _sides(params)
        points = _vertices(n, params.regular)
        diagram = Diagram(points + _extensions(points), figure_box, margin=0.3)
        corners = [diagram.p(*p) for p in points]
        parts = {
            "polygon": Polygon(*corners, color=style.TEXT_COLOUR, stroke_width=4),
            "question": text_line(_question(params), upper),
        }
        name = NAMES.get(n, f"{n}-sided polygon")
        if params.kind == "interior_sum":
            triangles = VGroup()
            for i in range(1, n - 1):
                triangles.add(
                    Polygon(
                        corners[0],
                        corners[i],
                        corners[i + 1],
                        stroke_width=2,
                        color=style.TEXT_COLOUR,
                        fill_color=FILLS[i % len(FILLS)],
                        fill_opacity=0.45,
                    )
                )
            parts["triangles"] = triangles
            rows = [
                rf"\text{{{n - 2} triangles from one vertex}}",
                rf"\text{{sum}} = ({n} - 2) \times 180^\circ",
                rf"= {(n - 2) * 180}^\circ",
            ]
            answer = rf"\text{{Sum of interior angles}} = {(n - 2) * 180}^\circ"
            if params.regular:
                each = latex_value(sp.Rational((n - 2) * 180, n))
                rows.append(rf"\text{{each}} = {(n - 2) * 180}^\circ \div {n} = {each}^\circ")
                answer += rf",\ \text{{each}} = {each}^\circ"
        else:
            exterior = VGroup()
            for i in range(n):
                v, before, after = corners[i], corners[i - 1], corners[(i + 1) % n]
                extended = v + (v - before) / np.linalg.norm(v - before) * 0.8
                exterior.add(Line(v, extended, stroke_width=3, color=style.TEXT_COLOUR))
                exterior.add(
                    angle_mark(v, extended, after, radius=0.45, colour=FILLS[i % len(FILLS)])
                )
            parts["exterior"] = exterior
            centre = sum(corners) / n
            radius = 0.45 * min(np.linalg.norm(c - centre) for c in corners)
            step = 2 * math.pi / n
            parts["fan"] = VGroup(
                *(
                    Sector(
                        radius=radius,
                        angle=step,
                        start_angle=k * step,
                        fill_color=FILLS[k % len(FILLS)],
                        fill_opacity=0.7,
                        stroke_width=1,
                    ).move_arc_center_to(centre)
                    for k in range(n)
                )
            )
            each = latex_value(sp.Rational(360, n))
            if params.kind == "exterior":
                rows = [
                    r"\text{the exterior angles make one turn}",
                    r"\text{sum} = 360^\circ",
                    rf"\text{{each}} = 360^\circ \div {n} = {each}^\circ",
                    rf"\text{{interior}} = 180^\circ - {each}^\circ = "
                    rf"{latex_value(180 - sp.Rational(360, n))}^\circ",
                ]
                answer = rf"\text{{Each exterior angle}} = {each}^\circ"
            else:
                ext = _exterior(params)
                rows = []
                if params.given == "interior":
                    rows.append(
                        rf"\text{{exterior}} = 180^\circ - {latex_value(params.angle)}"
                        rf"^\circ = {latex_value(ext)}^\circ"
                    )
                rows += [
                    rf"n = 360^\circ \div {latex_value(ext)}^\circ",
                    rf"n = {n}",
                ]
                answer = rf"n = {n}\text{{: a {name}}}"
        mobjects = [label(tex, size=32) for tex in rows]
        group = VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.3)
        style.fit_inside(group, working_box)
        for i, mob in enumerate(mobjects, start=1):
            parts[f"row_{i}"] = mob
        parts["answer"] = text_line(answer, lower, colour=style.HIGHLIGHT_COLOUR)
        return parts

    def stages(self, params: PolygonAnglesParams, level) -> list[Stage]:
        n = _sides(params)
        rows = [f"row_{i}" for i in range(1, self._row_count(params) + 1)]
        if params.kind == "interior_sum":
            steps = [
                stage("polygon", "Here is the polygon", 2.0, ["question", "polygon"]),
                stage(
                    "triangles",
                    f"Draw the diagonals from one vertex: {n - 2} triangles",
                    3.0,
                    ["triangles", rows[0]],
                ),
                stage(
                    "sum",
                    "Each triangle's angles add to 180 degrees, and together they "
                    "make the polygon's angles",
                    3.5,
                    rows[1:3],
                ),
            ]
            if params.regular:
                steps.append(
                    stage(
                        "each",
                        "The angles are equal, so divide by the number of angles",
                        2.5,
                        rows[3:],
                    )
                )
        elif params.kind == "exterior":
            steps = [
                stage("polygon", "Here is the regular polygon", 2.0, ["question", "polygon"]),
                stage(
                    "exterior",
                    "Extend each side: the exterior angle is the turn at each corner",
                    3.5,
                    ["exterior"],
                ),
                stage(
                    "turn",
                    "Walking all the way round turns you through one full turn",
                    3.5,
                    ["fan", *rows[:2]],
                ),
                stage("each", "Share 360 degrees between the corners", 3.0, rows[2:]),
            ]
        else:
            first = ["row_1"] if params.given == "interior" else []
            steps = [
                stage("question", "Read the question", 1.5, ["question"]),
                stage(
                    "exterior",
                    "Use the exterior angle: interior and exterior add to 180 degrees"
                    if first
                    else "The exterior angles add up to 360 degrees",
                    3.0,
                    first or ["fan"],
                ),
                stage(
                    "sides",
                    "Divide 360 degrees by one exterior angle",
                    3.0,
                    [r for r in rows if r not in first],
                ),
                stage(
                    "polygon", f"So it has {n} sides", 2.5, ["polygon", *(["fan"] if first else [])]
                ),
            ]
        steps.append(stage("answer", "So", 1.5, ["answer"], emphasise=["answer"]))

        def standard(s):
            return [combine("setup", s[1].description, 3.5, s[0], s[1]), *s[2:]]

        def concise(s):
            return [
                combine("setup", s[1].description, 3.5, s[0], s[1]),
                combine("working", "Work it out", 4.0, *s[2:]),
            ]

        return by_level(level, steps, standard, concise)

    def _row_count(self, params: PolygonAnglesParams) -> int:
        if params.kind == "interior_sum":
            return 4 if params.regular else 3
        if params.kind == "exterior":
            return 4
        return 3 if params.given == "interior" else 2


def _exterior(params: PolygonAnglesParams) -> sp.Expr:
    angle = sp.nsimplify(params.angle)
    return 180 - angle if params.given == "interior" else angle


def _sides(params: PolygonAnglesParams) -> int:
    if params.kind == "find_sides":
        return int(sp.nsimplify(360 / _exterior(params)))
    return params.sides


def _vertices(n: int, regular: bool) -> list[tuple[float, float]]:
    """A regular polygon with a flat base, or a fixed irregular convex one."""
    offset = -math.pi / 2 - math.pi / n
    radii = [1.0] * n if regular else [1.0 + 0.12 * math.sin(2.3 * k + 1) for k in range(n)]
    turns = [k + (0 if regular else 0.1 * math.sin(1.7 * k)) for k in range(n)]
    return [
        (r * math.cos(offset + 2 * math.pi * t / n), r * math.sin(offset + 2 * math.pi * t / n))
        for r, t in zip(radii, turns, strict=True)
    ]


def _extensions(points) -> list[tuple[float, float]]:
    """Where the extended sides reach, so the exterior angles fit in the figure."""
    out = []
    for i, (x, y) in enumerate(points):
        px, py = points[i - 1]
        length = math.hypot(x - px, y - py)
        out.append((x + (x - px) / length * 0.35, y + (y - py) / length * 0.35))
    return out


def _question(params: PolygonAnglesParams) -> str:
    n = _sides(params)
    name = NAMES.get(n, f"{n}-sided polygon")
    kind = "regular " if params.regular else ""
    if params.kind == "interior_sum":
        return rf"\text{{The interior angles of a {kind}{name}}}"
    if params.kind == "exterior":
        return rf"\text{{The exterior angles of a regular {name}}}"
    return (
        rf"\text{{A regular polygon has {params.given} angle }} "
        rf"{latex_value(params.angle)}^\circ\text{{. How many sides?}}"
    )


def _failure(predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=[parameter]
    )
