"""ConnectedParticles: two particles joined by a light inextensible string over a smooth pulley,
or a car towing a trailer, with Newton's second law written for each to find the acceleration
and the tension (9709 4.4).

The string is light and inextensible and the pulley smooth, so both particles have the same
acceleration and the tension is the same all along the string. For each particle, along its own
direction of motion, resultant force = mass × acceleration; the two equations give a and T.
Weight is mg with g = 10 m s⁻²; on a rough surface the friction is μR, opposing the motion. A car
and trailer share one acceleration, and the tow-bar pulls the trailer forward with the same
force it pulls the car back. SymPy solves; answers are to 3 significant figures.
"""

import math
from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import Arrow, Circle, Line, Polygon, Rectangle, Square, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import label, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_sf

G = 10
Mass = Annotated[float, Field(gt=0, le=5000)]
Force = Annotated[float, Field(ge=0, le=50_000)]
T_SYM, A_SYM = sp.symbols("T a", real=True)


class ConnectedParticlesParams(PrimitiveParams):
    setup: Literal["table_pulley", "two_hanging", "incline_pulley", "towing"]
    m_a: Mass = Field(description="kg: on the table or slope, the left hanging mass, or the car")
    m_b: Mass = Field(description="kg: the hanging mass, the right hanging mass, or the trailer")
    mu: Annotated[float, Field(ge=0, le=2)] = Field(
        default=0, description="Friction on A (0 if smooth)"
    )
    slope: Annotated[float, Field(gt=0, lt=90)] = Field(
        default=30, description="incline_pulley: angle"
    )
    driving_force: Force = Field(default=0, description="towing: the car's driving force (N)")
    resistance_a: Force = Field(default=0, description="towing: resistance on the car (N)")
    resistance_b: Force = Field(default=0, description="towing: resistance on the trailer (N)")


class ConnectedParticles(StagedPrimitive[ConnectedParticlesParams]):
    primitive_id = "ConnectedParticles"
    version = "1"
    topic = "Newton's laws of motion"
    params_model = ConnectedParticlesParams
    layout = LayoutContract(
        region=FULL_FRAME,
        allowed_overlaps=[("scene", "*"), ("force_*", "*"), ("motion", "*")],
    )

    def default_params(self) -> ConnectedParticlesParams:
        return ConnectedParticlesParams(setup="table_pulley", m_a=4, m_b=2, mu=0.2)

    def validate(self, params: ConnectedParticlesParams) -> list[PredicateFailure]:
        if params.setup == "towing" and params.driving_force == 0:
            return [_failure("driving_force", "towing needs a driving force", "driving_force")]
        if params.setup != "towing" and (
            params.driving_force or params.resistance_a or params.resistance_b
        ):
            message = "driving force and resistances are for towing only"
            return [_failure("towing_only", message, "setup")]
        if params.setup == "two_hanging" and params.mu:
            return [_failure("no_friction", "hanging particles have no friction", "mu")]
        work = _Work(params)
        if work.a_value <= 0:
            message = (
                "the system does not move: friction (or the balance of weights) holds it at rest"
            )
            return [_failure("moves", message, "m_a", "m_b", "mu")]
        return []

    def computed_values(self, params: ConnectedParticlesParams) -> dict[str, str]:
        work = _Work(params)
        return {"a": format_sf(work.a_value), "T": format_sf(work.t_value)}

    def build(self, params: ConnectedParticlesParams, level):
        work = _Work(params)
        box = style.region_box(style.GRAPH_REGION).shrink(style.PADDING)
        title = text_line(
            work.title_latex(), style.Box(box.left, box.right, box.top - 0.8, box.top)
        )
        area = style.Box(box.left, box.right, box.bottom + 0.3, box.top - 1.2)
        draw = {
            "table_pulley": self._draw_table,
            "two_hanging": self._draw_hanging,
            "incline_pulley": self._draw_incline,
            "towing": self._draw_towing,
        }[params.setup]
        scene, forces, motion = draw(params, work, area)
        parts = {"title": title, "scene": scene, "motion": motion}
        for name, mob in forces.items():
            parts[f"force_{name}"] = mob
        rows = work.rows()
        work_box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], work_box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def _arrow(self, start, direction, length, colour, tex, size=26):
        direction = np.array(direction, dtype=float)
        direction = direction / np.linalg.norm(direction)
        end = np.array(start) + direction * length
        arrow = Arrow(
            start, end, buff=0, color=colour, stroke_width=4, max_tip_length_to_length_ratio=0.2
        )
        text = label(tex, colour=colour, size=size).next_to(end, direction, buff=0.08)
        return VGroup(arrow, text)

    def _draw_table(self, params, work, area):
        top_y = area.center[1] + 0.6
        edge_x = area.center[0] + 1.4
        table = VGroup(
            Line([area.left + 0.2, top_y, 0], [edge_x, top_y, 0], stroke_width=4),
            Line([edge_x, top_y, 0], [edge_x, area.bottom + 0.2, 0], stroke_width=3),
        )
        pulley = Circle(radius=0.22, color=style.TEXT_COLOUR).move_to(
            [edge_x + 0.22, top_y + 0.22, 0]
        )
        block_a = Square(0.8, color=style.CURVE_COLOUR, fill_opacity=0.3).move_to(
            [edge_x - 2.4, top_y + 0.4, 0]
        )
        hang_x = edge_x + 0.44
        block_b = Square(0.7, color=style.RUN_COLOUR, fill_opacity=0.3).move_to(
            [hang_x, top_y - 1.9, 0]
        )
        string = VGroup(
            Line(block_a.get_right(), [edge_x + 0.22, top_y + 0.44, 0], stroke_width=2),
            Line([hang_x, top_y + 0.22, 0], block_b.get_top(), stroke_width=2),
        )
        scene = VGroup(
            table,
            pulley,
            block_a,
            block_b,
            string,
            label("A", size=26).move_to(block_a),
            label("B", size=26).move_to(block_b),
        )
        forces = {
            "T_a": self._arrow(
                block_a.get_right() + [0, 0.15, 0], [1, 0, 0], 0.9, style.HIGHLIGHT_COLOUR, "T"
            ),
            "W_a": self._arrow(
                block_a.get_bottom(),
                [0, -1, 0],
                0.8,
                style.TEXT_COLOUR,
                rf"{format_sf(work.ma * G)}",
            ),
            "R_a": self._arrow(block_a.get_top(), [0, 1, 0], 0.8, style.HIGHLIGHT_COLOUR, "R"),
            "T_b": self._arrow(
                block_b.get_top() + [0.18, 0, 0], [0, 1, 0], 0.7, style.HIGHLIGHT_COLOUR, "T"
            ),
            "W_b": self._arrow(
                block_b.get_bottom(),
                [0, -1, 0],
                0.8,
                style.TEXT_COLOUR,
                rf"{format_sf(work.mb * G)}",
            ),
        }
        if work.mu:
            forces["F_a"] = self._arrow(
                block_a.get_left() + [0, -0.25, 0], [-1, 0, 0], 0.9, style.TANGENT_COLOUR, "F"
            )
        motion = self._arrow(
            block_a.get_top() + [0.9, 0.55, 0], [1, 0, 0], 0.7, style.RISE_COLOUR, "a"
        )
        return scene, forces, motion

    def _draw_hanging(self, params, work, area):
        cx, top = area.center[0], area.top - 0.3
        pulley = Circle(radius=0.45, color=style.TEXT_COLOUR).move_to([cx, top - 0.5, 0])
        beam = Line([cx - 1.2, top, 0], [cx + 1.2, top, 0], stroke_width=4)
        left_x, right_x = cx - 0.45, cx + 0.45
        drop_a, drop_b = (2.6, 1.6) if work.ma <= work.mb else (1.6, 2.6)
        block_a = Square(0.6, color=style.CURVE_COLOUR, fill_opacity=0.3).move_to(
            [left_x, top - 0.5 - drop_a, 0]
        )
        block_b = Square(0.6, color=style.RUN_COLOUR, fill_opacity=0.3).move_to(
            [right_x, top - 0.5 - drop_b, 0]
        )
        string = VGroup(
            Line([left_x, top - 0.5, 0], block_a.get_top(), stroke_width=2),
            Line([right_x, top - 0.5, 0], block_b.get_top(), stroke_width=2),
        )
        scene = VGroup(
            beam,
            pulley,
            string,
            block_a,
            block_b,
            label("A", size=24).move_to(block_a),
            label("B", size=24).move_to(block_b),
        )
        forces = {
            "T_a": self._arrow(
                block_a.get_top() + [-0.18, 0, 0], [0, 1, 0], 0.6, style.HIGHLIGHT_COLOUR, "T"
            ),
            "W_a": self._arrow(
                block_a.get_bottom(),
                [0, -1, 0],
                0.7,
                style.TEXT_COLOUR,
                rf"{format_sf(work.ma * G)}",
            ),
            "T_b": self._arrow(
                block_b.get_top() + [0.18, 0, 0], [0, 1, 0], 0.6, style.HIGHLIGHT_COLOUR, "T"
            ),
            "W_b": self._arrow(
                block_b.get_bottom(),
                [0, -1, 0],
                0.7,
                style.TEXT_COLOUR,
                rf"{format_sf(work.mb * G)}",
            ),
        }
        heavier = block_b if work.mb > work.ma else block_a
        motion = self._arrow(
            heavier.get_center() + [1.1 if heavier is block_b else -1.1, 0.3, 0],
            [0, -1, 0],
            0.7,
            style.RISE_COLOUR,
            "a",
        )
        return scene, forces, motion

    def _draw_incline(self, params, work, area):
        tilt = math.radians(params.slope)
        low = np.array([area.left + 0.3, area.center[1] - 1.2, 0])
        length = min(area.width - 1.6, 4.6)
        high = low + length * np.array([math.cos(tilt), math.sin(tilt), 0])
        corner = np.array([high[0], low[1], 0])
        along = np.array([math.cos(tilt), math.sin(tilt), 0])
        normal = np.array([-math.sin(tilt), math.cos(tilt), 0])
        wedge = Polygon(low, high, corner, stroke_width=3, color=style.TEXT_COLOUR)
        block_a = (
            Square(0.7, color=style.CURVE_COLOUR, fill_opacity=0.3)
            .rotate(tilt)
            .move_to(low + 0.55 * length * along + 0.35 * normal)
        )
        pulley_centre = high + 0.2 * normal + 0.1 * along
        pulley = Circle(radius=0.2, color=style.TEXT_COLOUR).move_to(pulley_centre)
        hang_x = pulley_centre[0] + 0.2
        block_b = Square(0.6, color=style.RUN_COLOUR, fill_opacity=0.3).move_to(
            [hang_x, corner[1] + 0.9, 0]
        )
        string = VGroup(
            Line(block_a.get_center() + 0.35 * along, pulley_centre + 0.2 * normal, stroke_width=2),
            Line([hang_x, pulley_centre[1], 0], block_b.get_top(), stroke_width=2),
        )
        scene = VGroup(
            wedge,
            pulley,
            string,
            block_a,
            block_b,
            label("A", size=24).move_to(block_a),
            label("B", size=24).move_to(block_b),
            label(
                rf"{format_sf(params.slope)}^\circ", size=24, colour=style.HIGHLIGHT_COLOUR
            ).move_to(low + 0.9 * np.array([math.cos(tilt / 2), math.sin(tilt / 2), 0])),
        )
        sign = 1 if work.b_falls else -1
        forces = {
            "T_a": self._arrow(
                block_a.get_center() + 0.4 * along + 0.25 * normal,
                along,
                0.8,
                style.HIGHLIGHT_COLOUR,
                "T",
            ),
            "W_a": self._arrow(
                block_a.get_center(),
                [0, -1, 0],
                0.9,
                style.TEXT_COLOUR,
                rf"{format_sf(work.ma * G)}",
            ),
            "R_a": self._arrow(
                block_a.get_center() + 0.35 * normal, normal, 0.8, style.HIGHLIGHT_COLOUR, "R"
            ),
            "T_b": self._arrow(
                block_b.get_top() + [-0.15, 0, 0], [0, 1, 0], 0.5, style.HIGHLIGHT_COLOUR, "T"
            ),
            "W_b": self._arrow(
                block_b.get_bottom(),
                [0, -1, 0],
                0.6,
                style.TEXT_COLOUR,
                rf"{format_sf(work.mb * G)}",
            ),
        }
        if work.mu:
            forces["F_a"] = self._arrow(
                block_a.get_center() - 0.4 * along - 0.3 * normal,
                -sign * along,
                0.8,
                style.TANGENT_COLOUR,
                "F",
            )
        motion = self._arrow(
            block_a.get_center() + 0.9 * normal - 0.3 * along,
            sign * along,
            0.7,
            style.RISE_COLOUR,
            "a",
        )
        return scene, forces, motion

    def _draw_towing(self, params, work, area):
        y = area.center[1]
        road = Line([area.left, y - 0.5, 0], [area.right, y - 0.5, 0], stroke_width=3)
        trailer = Rectangle(
            width=1.4, height=0.8, color=style.RUN_COLOUR, fill_opacity=0.3
        ).move_to([area.center[0] - 1.6, y - 0.1, 0])
        car = Rectangle(width=1.6, height=0.8, color=style.CURVE_COLOUR, fill_opacity=0.3).move_to(
            [area.center[0] + 0.9, y - 0.1, 0]
        )
        bar = Line(trailer.get_right(), car.get_left(), stroke_width=4)
        scene = VGroup(
            road,
            trailer,
            car,
            bar,
            label(r"\text{trailer}", size=22).move_to(trailer),
            label(r"\text{car}", size=22).move_to(car),
        )
        forces = {
            "D": self._arrow(
                car.get_right(),
                [1, 0, 0],
                0.9,
                style.RISE_COLOUR,
                rf"{format_sf(params.driving_force)}",
            ),
            "T_a": self._arrow(
                car.get_left() + [0, 0.25, 0], [-1, 0, 0], 0.6, style.HIGHLIGHT_COLOUR, "T"
            ),
            "T_b": self._arrow(
                trailer.get_right() + [0, 0.25, 0], [1, 0, 0], 0.6, style.HIGHLIGHT_COLOUR, "T"
            ),
        }
        if params.resistance_a:
            forces["R_a"] = self._arrow(
                car.get_center() + [0, -0.6, 0],
                [-1, 0, 0],
                0.8,
                style.TANGENT_COLOUR,
                rf"{format_sf(params.resistance_a)}",
            )
        if params.resistance_b:
            forces["R_b"] = self._arrow(
                trailer.get_left(),
                [-1, 0, 0],
                0.8,
                style.TANGENT_COLOUR,
                rf"{format_sf(params.resistance_b)}",
            )
        motion = self._arrow(car.get_top() + [0, 0.5, 0], [1, 0, 0], 0.7, style.RISE_COLOUR, "a")
        return scene, forces, motion

    def stages(self, params: ConnectedParticlesParams, level) -> list[Stage]:
        work = _Work(params)
        n = len(work.rows())
        names = work.force_names()
        steps = [
            stage("scene", work.scene_words(), 3.0, ["title", "scene"]),
            stage(
                "forces",
                "Mark the forces on each particle; the tension is the same all along the string"
                if params.setup != "towing"
                else "Mark the forces: the tow-bar pulls the trailer forward and the car back",
                3.5,
                [f"force_{n_}" for n_ in names],
            ),
            stage("motion", "Both move with the same acceleration", 2.5, ["motion"]),
            stage(
                "a_equation",
                "Newton's second law for A: resultant force equals mass times acceleration",
                3.5,
                ["row_1"],
            ),
            stage("b_equation", "And for B", 3.0, ["row_2"]),
            stage(
                "solve",
                "Add the equations to find a, then T",
                3.5,
                [f"row_{i}" for i in range(3, n + 1)],
                emphasise=[f"row_{n}"],
            ),
        ]

        def standard(s):
            return [
                s[0],
                combine("forces", s[1].description, 4.0, s[1], s[2]),
                combine("equations", "Newton's second law for each", 4.0, s[3], s[4]),
                s[5],
            ]

        def concise(s):
            out = standard(s)
            return [combine("picture", "The system and its forces", 4.0, out[0], out[1]), *out[2:]]

        return by_level(level, steps, standard, concise)


class _Work:
    def __init__(self, params: ConnectedParticlesParams):
        self.params = params
        self.ma, self.mb = exact(params.m_a), exact(params.m_b)
        self.mu = exact(params.mu)
        a, t = A_SYM, T_SYM
        setup = params.setup
        self.b_falls = True
        if setup == "table_pulley":
            friction = self.mu * self.ma * G
            self.eq_a = sp.Eq(t - friction, self.ma * a)
            self.eq_b = sp.Eq(self.mb * G - t, self.mb * a)
        elif setup == "two_hanging":
            heavy_b = self.mb >= self.ma
            self.b_falls = heavy_b
            if heavy_b:
                self.eq_a = sp.Eq(t - self.ma * G, self.ma * a)
                self.eq_b = sp.Eq(self.mb * G - t, self.mb * a)
            else:
                self.eq_a = sp.Eq(self.ma * G - t, self.ma * a)
                self.eq_b = sp.Eq(t - self.mb * G, self.mb * a)
        elif setup == "incline_pulley":
            angle = sp.rad(exact(params.slope))
            down = self.ma * G * sp.sin(angle)
            reaction = self.ma * G * sp.cos(angle)
            friction = self.mu * reaction
            self.b_falls = self.mb * G > down
            if self.b_falls:
                self.eq_a = sp.Eq(t - down - friction, self.ma * a)
                self.eq_b = sp.Eq(self.mb * G - t, self.mb * a)
            else:
                self.eq_a = sp.Eq(down - t - friction, self.ma * a)
                self.eq_b = sp.Eq(t - self.mb * G, self.mb * a)
        else:
            d = exact(params.driving_force)
            ra, rb = exact(params.resistance_a), exact(params.resistance_b)
            self.eq_a = sp.Eq(d - t - ra, self.ma * a)
            self.eq_b = sp.Eq(t - rb, self.mb * a)
        solution = sp.solve([self.eq_a, self.eq_b], [a, t], dict=True)[0]
        self.a_value = float(solution[a])
        self.t_value = float(solution[t])

    def title_latex(self) -> str:
        return (
            rf"m_A = {format_sf(self.ma, 6)}\text{{ kg}},\ "
            rf"m_B = {format_sf(self.mb, 6)}\text{{ kg}}"
            + (rf",\ \mu = {format_sf(self.mu, 6)}" if self.mu else "")
        )

    def scene_words(self) -> str:
        return {
            "table_pulley": "A on the table, joined over a smooth pulley to B hanging",
            "two_hanging": "Two particles hanging over a smooth pulley",
            "incline_pulley": "A on the slope, joined over a smooth pulley at the top to B hanging",
            "towing": "A car towing a trailer by a light rigid tow-bar",
        }[self.params.setup]

    def force_names(self) -> list[str]:
        setup = self.params.setup
        if setup == "towing":
            names = ["D", "T_a", "T_b"]
            names += ["R_a"] if self.params.resistance_a else []
            names += ["R_b"] if self.params.resistance_b else []
            return names
        names = ["T_a", "W_a", "T_b", "W_b"]
        if setup in ("table_pulley", "incline_pulley"):
            names.append("R_a")
            if self.mu:
                names.append("F_a")
        return names

    def rows(self) -> list[tuple[str, object]]:
        def side(eq):
            return f"{_tidy(eq.lhs)} = {_tidy(eq.rhs)}"

        rows = [
            (rf"\text{{A: }}{side(self.eq_a)}", style.CURVE_COLOUR),
            (rf"\text{{B: }}{side(self.eq_b)}", style.RUN_COLOUR),
        ]
        if self.params.setup in ("table_pulley", "incline_pulley") and self.mu:
            reaction = "R = " + format_sf(
                self.ma
                * G
                * (
                    sp.cos(sp.rad(exact(self.params.slope)))
                    if self.params.setup == "incline_pulley"
                    else 1
                )
            )
            rows.append((rf"{reaction},\ F = \mu R", None))
        rows.append((rf"a = {format_sf(self.a_value)}\text{{ m s}}^{{-2}}", style.HIGHLIGHT_COLOUR))
        rows.append((rf"T = {format_sf(self.t_value)}\text{{ N}}", style.HIGHLIGHT_COLOUR))
        return rows


def _tidy(expr) -> str:
    """A side of a Newton's-law equation with its numbers evaluated to 3 s.f.: T - 8 = 4a."""
    expr = sp.expand(sp.N(expr))
    # T first, then a, then numbers; but a positive term leads, as written: 20 - T, not -T + 20
    terms = sorted(sp.Add.make_args(expr), key=lambda t: (not t.has(T_SYM), not t.has(A_SYM)))
    if terms and terms[0].as_coeff_Mul()[0] < 0:
        positive = [t for t in terms if t.as_coeff_Mul()[0] > 0]
        if positive:
            terms.remove(positive[0])
            terms.insert(0, positive[0])
    out = ""
    for term in terms:
        coefficient, rest = term.as_coeff_Mul()
        number = float(coefficient) if coefficient.is_number else 1.0
        if rest == 1:
            body = format_sf(abs(number))
        else:
            body = ("" if abs(number) == 1 else format_sf(abs(number))) + sp.latex(rest)
        sign = "-" if number < 0 else "+"
        out += (("-" if sign == "-" else "") + body) if not out else f" {sign} {body}"
    return out or "0"


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
