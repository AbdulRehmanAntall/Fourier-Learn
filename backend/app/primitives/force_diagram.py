"""ForceDiagram: the forces on a particle, free, on a horizontal surface or on an inclined plane,
resolved in two perpendicular directions to find unknown forces, the coefficient of friction or
the acceleration (9709 4.1, 4.4).

Each force is split into components along and perpendicular to the surface (horizontal and
vertical when there is no slope): F cos θ and F sin θ, θ measured from the "along" direction.
In equilibrium the components in each direction add to zero; otherwise the resultant along the
surface is ma (Newton's second law) and the perpendicular components still balance. Weight is
mg with g = 10 m s⁻², as the syllabus uses; on a plane at angle α it has components mg sin α
down the slope and mg cos α into it. Friction opposes the motion (or its tendency), and in
limiting equilibrium F = μR. SymPy solves the equations; answers are to 3 significant figures.
"""

import math
from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import Arc, Arrow, DashedLine, Polygon, Square, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import label, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_sf, latex_value

G = 10
Name = Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{1,3}$")]
ARROW = 1.7


class Force(PrimitiveParams):
    name: Name = Field(description='A letter for the force, e.g. "P" or "T"')
    magnitude: Annotated[float, Field(gt=0, le=10_000)] | None = Field(
        default=None, description="In newtons; leave out if it is to be found"
    )
    angle: Annotated[float, Field(ge=-180, le=360)] = Field(
        description="Degrees anticlockwise from the 'along' direction: right, or up the slope"
    )


class ForceDiagramParams(PrimitiveParams):
    find: Literal["equilibrium", "acceleration"]
    mass: Annotated[float, Field(gt=0, le=1000)] | None = Field(
        default=None, description="In kg; its weight mg is added (g = 10)"
    )
    surface: Literal["none", "horizontal", "incline"] = "none"
    slope: Annotated[float, Field(gt=0, lt=90)] = Field(default=30, description="Incline angle")
    friction: Literal["none", "limiting", "unknown"] = Field(
        default="none",
        description="limiting: F = μR. unknown: F is found from the equations",
    )
    mu: Annotated[float, Field(gt=0, le=2)] | None = Field(
        default=None, description="The coefficient of friction, if known"
    )
    friction_direction: Literal["down", "up"] = Field(
        default="down", description="Friction acts down the slope (or left), or up it (right)"
    )
    forces: list[Force] = Field(default=[], max_length=4)


class ForceDiagram(StagedPrimitive[ForceDiagramParams]):
    primitive_id = "ForceDiagram"
    version = "1"
    topic = "Forces and equilibrium"
    params_model = ForceDiagramParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[
            ("ground", "*"),
            ("body", "*"),
            ("arrow_*", "*"),
            ("axes_*", "*"),
            ("arc_*", "*"),
        ],
    )

    def default_params(self) -> ForceDiagramParams:
        return ForceDiagramParams(
            find="equilibrium",
            mass=5,
            surface="incline",
            slope=30,
            friction="limiting",
            forces=[Force(name="P", magnitude=40, angle=20)],
        )

    def validate(self, params: ForceDiagramParams) -> list[PredicateFailure]:
        names = [f.name for f in params.forces]
        if len(set(names)) != len(names) or set(names) & {"R", "F", "W"}:
            message = (
                "force names must differ, and R, F and W are kept for reaction, friction, weight"
            )
            return [_failure("names_distinct", message, "forces")]
        if params.find == "acceleration" and params.mass is None:
            return [_failure("mass_given", "finding the acceleration needs the mass", "mass")]
        if params.surface == "none" and params.friction != "none":
            return [_failure("friction_needs_surface", "friction needs a surface", "friction")]
        if params.friction == "unknown" and params.mu is not None:
            message = "with mu known, use limiting friction"
            return [_failure("friction_kind", message, "mu", "friction")]
        problem = _Problem(params)
        if len(problem.unknowns) != len(problem.equations):
            message = (
                f"{len(problem.unknowns)} unknowns ({', '.join(map(str, problem.unknowns))}) but "
                f"{len(problem.equations)} equations: give or ask for exactly as many"
            )
            return [_failure("solvable", message, "forces")]
        if problem.solution is None:
            return [_failure("solvable", "the equations have no single solution", "forces")]
        for symbol, value in problem.solution.items():
            if str(symbol) in ("a",):
                continue
            if value < 0:
                message = f"{symbol} comes out negative: that force acts the other way"
                if str(symbol) == "R":
                    message = "R comes out negative: the particle would leave the surface"
                return [_failure("physical", message, "forces", "friction_direction")]
        return []

    def computed_values(self, params: ForceDiagramParams) -> dict[str, str]:
        problem = _Problem(params)
        return {str(k): format_sf(v) for k, v in problem.solution.items()}

    def build(self, params: ForceDiagramParams, level):
        problem = _Problem(params)
        box = style.region_box(style.GRAPH_REGION).shrink(style.PADDING)
        centre = box.center + np.array([0.0, -0.2, 0])
        tilt = math.radians(params.slope) if params.surface == "incline" else 0.0
        along = np.array([math.cos(tilt), math.sin(tilt), 0])
        across = np.array([-math.sin(tilt), math.cos(tilt), 0])
        parts = {}
        size = 0.9
        body = (
            Square(side_length=size, color=style.TEXT_COLOUR, stroke_width=3)
            .rotate(tilt)
            .move_to(centre)
        )
        if params.surface == "none":
            body = Square(side_length=0.25, color=style.TEXT_COLOUR, fill_opacity=1).move_to(centre)
        parts["body"] = body
        if params.surface != "none":
            foot = centre - across * size / 2
            if params.surface == "horizontal":
                parts["ground"] = VGroup(
                    DashedLine(
                        foot - 3.2 * along, foot + 3.2 * along, stroke_width=3, dash_length=0.15
                    )
                )
            else:
                low = foot - 3.0 * along
                high = foot + 2.4 * along
                corner = np.array([high[0], low[1], 0])
                wedge = Polygon(low, high, corner, stroke_width=3, color=style.TEXT_COLOUR)
                parts["ground"] = VGroup(
                    wedge,
                    Arc(
                        radius=0.7,
                        start_angle=0,
                        angle=tilt,
                        arc_center=low,
                        color=style.HIGHLIGHT_COLOUR,
                    ),
                    label(rf"{_deg(params.slope)}", size=26, colour=style.HIGHLIGHT_COLOUR).move_to(
                        low + 1.05 * np.array([math.cos(tilt / 2), math.sin(tilt / 2), 0])
                    ),
                )
        parts["axes_along"] = DashedLine(
            centre - 2.6 * along, centre + 2.6 * along, stroke_width=1.5, color=style.SECANT_COLOUR
        )
        parts["axes_across"] = DashedLine(
            centre - 2.0 * across,
            centre + 2.0 * across,
            stroke_width=1.5,
            color=style.SECANT_COLOUR,
        )
        for force in problem.forces:
            theta = math.radians(force.angle) + tilt
            direction = np.array([math.cos(theta), math.sin(theta), 0])
            start = centre + direction * (size * 0.55 if params.surface != "none" else 0.12)
            if force.name == "R" and params.surface != "none":
                start = centre + across * size / 2
            if force.name == "F" and params.surface != "none":
                start = centre - across * size / 2 + direction * size / 2
            arrow = Arrow(
                start,
                start + direction * ARROW,
                buff=0,
                color=force.colour,
                stroke_width=5,
                max_tip_length_to_length_ratio=0.15,
            )
            parts[f"arrow_{force.name}"] = arrow
            parts[f"label_{force.name}"] = label(force.tex, colour=force.colour, size=30).next_to(
                arrow.get_end(), direction, buff=0.12
            )
            if force.marked_angle:
                # the acute angle to the nearer "along" direction, the one used when resolving
                theta = force.angle % 360
                base = 0 if math.cos(math.radians(theta)) >= 0 else 180
                sweep = (theta - base + 180) % 360 - 180
                arc = Arc(
                    radius=0.7,
                    start_angle=tilt + math.radians(base),
                    angle=math.radians(sweep),
                    arc_center=start,
                    color=force.colour,
                    stroke_width=2,
                )
                middle = tilt + math.radians(base + sweep / 2)
                mark = label(_deg(sp.nsimplify(abs(sweep))), colour=force.colour, size=24)
                mark.move_to(start + 1.05 * np.array([math.cos(middle), math.sin(middle), 0]))
                parts[f"arc_{force.name}"] = VGroup(arc, mark)
        parts["title"] = text_line(
            problem.title_latex(), style.Box(box.left, box.right, box.top - 0.8, box.top)
        )
        rows = problem.rows()
        work = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([t for t, _ in rows], work, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: ForceDiagramParams, level) -> list[Stage]:
        problem = _Problem(params)
        n = len(problem.rows())
        names = [f.name for f in problem.forces]
        arrows = [p for name in names for p in (f"arrow_{name}", f"label_{name}")]
        arcs = [f"arc_{f.name}" for f in problem.forces if f.marked_angle]
        ground = ["ground"] if params.surface != "none" else []
        steps = [
            stage(
                "body",
                "The particle" + (" on the surface" if ground else ""),
                2.0,
                ["title", "body", *ground],
            ),
            stage("forces", "Mark every force acting on it", 3.5, [*arrows, *arcs]),
            stage(
                "axes",
                "Resolve along the slope and perpendicular to it"
                if params.surface == "incline"
                else "Resolve horizontally and vertically",
                3.0,
                ["axes_along", "axes_across"],
            ),
            stage(
                "along",
                "Along: the components "
                + (
                    "add to zero"
                    if params.find == "equilibrium"
                    else "add to mass times acceleration"
                ),
                3.5,
                ["row_1"],
            ),
            stage("across", "Perpendicular: the components add to zero", 3.0, ["row_2"]),
        ]
        rest = [f"row_{i}" for i in range(3, n + 1)]
        steps.append(stage("solve", "Solve the equations", 3.0, rest, emphasise=[rest[-1]]))

        def standard(s):
            return [combine("forces", "The particle and the forces on it", 3.5, s[0], s[1]), *s[2:]]

        def concise(s):
            return [
                combine("forces", "The particle and the forces on it", 3.5, s[0], s[1]),
                combine("resolve", "Resolve in two directions", 4.0, *s[2:5]),
                s[5],
            ]

        return by_level(level, steps, standard, concise)


class _Force:
    def __init__(self, name, magnitude, angle, tex, colour, marked_angle=0.0):
        self.name, self.magnitude, self.angle = name, magnitude, angle
        self.tex, self.colour, self.marked_angle = tex, colour, marked_angle


class _Problem:
    def __init__(self, params: ForceDiagramParams):
        self.params = params
        slope = params.slope if params.surface == "incline" else 0
        self.forces: list[_Force] = []
        self.unknowns = []
        palette = [style.CURVE_COLOUR, style.RUN_COLOUR, style.RISE_COLOUR, style.SECANT_COLOUR]
        for i, f in enumerate(params.forces):
            magnitude = (
                exact(f.magnitude) if f.magnitude is not None else sp.Symbol(f.name, positive=True)
            )
            if f.magnitude is None:
                self.unknowns.append(magnitude)
            tex = (
                f.name if f.magnitude is None else rf"{latex_value(exact(f.magnitude))}\text{{ N}}"
            )
            marked = f.angle if f.angle % 90 != 0 else 0.0
            self.forces.append(_Force(f.name, magnitude, f.angle, tex, palette[i % 4], marked))
        if params.mass is not None:
            w = exact(params.mass) * G
            self.forces.append(
                _Force("W", w, -90 - slope, rf"{latex_value(w)}\text{{ N}}", style.TEXT_COLOUR)
            )
        if params.surface != "none":
            r = sp.Symbol("R", positive=True)
            self.unknowns.append(r)
            self.forces.append(_Force("R", r, 90, "R", style.HIGHLIGHT_COLOUR))
        self.mu = None
        if params.friction != "none":
            f_sym = sp.Symbol("F", positive=True)
            self.unknowns.append(f_sym)
            direction = 180 if params.friction_direction == "down" else 0
            self.forces.append(_Force("F", f_sym, direction, "F", style.TANGENT_COLOUR))
            self.mu = exact(params.mu) if params.mu is not None else None
            if params.friction == "limiting" and params.mu is None:
                self.mu = sp.Symbol("mu", positive=True)
                self.unknowns.append(self.mu)
        if params.find == "acceleration":
            self.a = sp.Symbol("a", real=True)
            self.unknowns.append(self.a)
        along = sum(f.magnitude * _cos(f.angle) for f in self.forces)
        across = sum(f.magnitude * _sin(f.angle) for f in self.forces)
        mass_a = exact(params.mass) * self.a if params.find == "acceleration" and params.mass else 0
        self.along, self.across, self.mass_a = along, across, mass_a
        self.equations = [sp.Eq(along, mass_a), sp.Eq(across, 0)]
        if params.friction == "limiting":
            self.equations.append(
                sp.Eq(sp.Symbol("F", positive=True), self.mu * sp.Symbol("R", positive=True))
            )
        self.solution = None
        if len(self.unknowns) == len(self.equations):
            relaxed = {u: sp.Symbol(str(u), real=True) for u in self.unknowns}
            eqs = [e.subs(relaxed) for e in self.equations]
            found = sp.solve(eqs, list(relaxed.values()), dict=True)
            if len(found) == 1:
                self.solution = {k: sp.N(v) for k, v in found[0].items()}

    def title_latex(self) -> str:
        if self.params.find == "equilibrium":
            return r"\text{In equilibrium}"
        return r"\text{Find the acceleration}"

    def _sum_latex(self, part) -> str:
        terms = []
        for f in self.forces:
            factor = (_cos if part == "along" else _sin)(f.angle)
            if factor == 0:
                continue
            terms.append(_term(f, factor, f.angle, part))
        text = ""
        for sign, body in terms:
            text += (
                (("-" if sign < 0 else "") + body)
                if not text
                else f" {'-' if sign < 0 else '+'} {body}"
            )
        return text or "0"

    def rows(self) -> list[tuple[str, object]]:
        incline = self.params.surface == "incline"
        along_name = r"\nearrow" if incline else r"\rightarrow"
        across_name = r"\nwarrow" if incline else r"\uparrow"
        rhs = (
            rf"{latex_value(exact(self.params.mass))}a"
            if self.params.find == "acceleration"
            else "0"
        )
        rows = [
            (rf"{along_name}:\ {self._sum_latex('along')} = {rhs}", None),
            (rf"{across_name}:\ {self._sum_latex('across')} = 0", None),
        ]
        if self.params.friction == "limiting":
            mu = r"\mu" if self.params.mu is None else latex_value(exact(self.params.mu))
            rows.append((rf"F = {mu}\,R\text{{ (limiting)}}", None))
        names = {"mu": r"\mu"}
        found = (
            ",\\ ".join(
                rf"{names.get(str(k), str(k))} = {format_sf(v)}" for k, v in self.solution.items()
            )
            if self.solution
            else ""
        )
        rows.append((found, style.HIGHLIGHT_COLOUR))
        return rows


def _cos(angle_degrees) -> sp.Expr:
    return sp.cos(sp.rad(exact(angle_degrees)))


def _sin(angle_degrees) -> sp.Expr:
    return sp.sin(sp.rad(exact(angle_degrees)))


def _deg(value) -> str:
    return f"{latex_value(exact(value))}^\\circ"


def _term(force: _Force, factor, angle, part) -> tuple[int, str]:
    """One component as it is written: P cos 20°, 50 sin 30°, R; with its sign."""
    sign = 1 if float(factor) > 0 else -1
    name = force.name if force.magnitude.free_symbols else latex_value(force.magnitude)
    size = abs(factor)
    if size == 1:
        return sign, name
    # the acute angle the component is taken at, from the nearest axis
    a = float(exact(angle)) % 180
    reference = min(a, 180 - a)
    trig = r"\cos" if part == "along" else r"\sin"
    if force.name == "W":
        trig = r"\sin" if part == "along" else r"\cos"
        reference = 90 - reference
    return sign, rf"{name}{trig}{_deg(sp.nsimplify(reference))}"


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
