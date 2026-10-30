"""WorkEnergy: the work-energy principle as two equal stacks of energy, before and after, and
power as the rate of doing work, P = Fv, for a vehicle against resistance (9709 4.5).

Work done by a constant force F over a distance d at angle θ to the motion is Fd cos θ. Energy
in at the start (kinetic energy ½mu², any loss of height mgh, work done by a pulling force)
equals energy at the end (kinetic energy ½mv², any gain of height, work done against
resistance). The two stacks show it: they must be the same height. With power P at speed v the
driving force is P/v, and Newton's second law along the road gives the acceleration
(g = 10 m s⁻²). SymPy solves; answers are to 3 significant figures.
"""

import math
from typing import Annotated, Literal

import sympy as sp
from manim import Arrow, Line, Polygon, Rectangle, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import label, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_sf

G = 10
Value = Annotated[float, Field(ge=0, le=100_000)] | None
NAMES = ("u", "v", "h", "d", "resistance")
COLOURS = {
    "KE": style.CURVE_COLOUR,
    "PE": style.RISE_COLOUR,
    "work_in": style.RUN_COLOUR,
    "work_out": style.TANGENT_COLOUR,
}


class WorkEnergyParams(PrimitiveParams):
    kind: Literal["work_energy", "power"]
    mass: Annotated[float, Field(gt=0, le=5000)] = Field(description="kg")
    u: Value = Field(default=None, description="Speed at the start (m/s)")
    v: Value = Field(default=None, description="Speed at the end (m/s); for power, the speed now")
    h: Annotated[float, Field(ge=-1000, le=1000)] | None = Field(
        default=0, description="Rise in height (m), negative for a drop"
    )
    d: Value = Field(default=None, description="Distance moved (m)")
    resistance: Value = Field(default=0, description="Constant resistance (N)")
    pull_force: Value = Field(default=0, description="work_energy: a pulling force (N)")
    pull_angle: Annotated[float, Field(ge=0, lt=90)] = Field(
        default=0, description="Its angle to the direction of motion (degrees)"
    )
    power: Value = Field(default=None, description="power: the engine's power (W)")
    acceleration: Annotated[float, Field(ge=-50, le=50)] = Field(
        default=0, description="power: the acceleration, when finding the power"
    )
    slope: Annotated[float, Field(ge=-45, le=45)] = Field(
        default=0, description="power: the road's angle, positive uphill (degrees)"
    )
    find: Literal["u", "v", "h", "d", "resistance", "a", "power", "max_speed"]


class WorkEnergy(StagedPrimitive[WorkEnergyParams]):
    primitive_id = "WorkEnergy"
    version = "1"
    topic = "Energy, work and power"
    params_model = WorkEnergyParams
    layout = LayoutContract(
        region=FULL_FRAME, allowed_overlaps=[("bar_*", "*"), ("road", "*"), ("force_*", "*")]
    )

    def default_params(self) -> WorkEnergyParams:
        return WorkEnergyParams(
            kind="work_energy", mass=60, u=2, h=-5, d=40, resistance=20, find="v"
        )

    def validate(self, params: WorkEnergyParams) -> list[PredicateFailure]:
        if params.kind == "work_energy":
            if params.find not in NAMES:
                return [
                    _failure("find_fits", "for work_energy find u, v, h, d or resistance", "find")
                ]
            missing = [n for n in NAMES if n != params.find and getattr(params, n) is None]
            if missing:
                message = f"give every one of u, v, h, d, resistance except {params.find}"
                return [_failure("one_unknown", message, *NAMES)]
        else:
            if params.find not in ("a", "power", "max_speed"):
                return [_failure("find_fits", "for power find a, power or max_speed", "find")]
            if params.find != "power" and params.power is None:
                return [_failure("power_given", "give the power", "power")]
            if params.find != "max_speed" and not params.v:
                return [_failure("speed_given", "give the speed v (not 0)", "v")]
        try:
            work = _Work(params)
        except _NoSolution as problem:
            return [_failure("solvable", str(problem), params.find)]
        if params.kind == "work_energy" and work.value < 0:
            return [
                _failure(
                    "solvable", f"{params.find} comes out negative: check the data", params.find
                )
            ]
        return []

    def computed_values(self, params: WorkEnergyParams) -> dict[str, str]:
        return {params.find: format_sf(_Work(params).value)}

    def build(self, params: WorkEnergyParams, level):
        work = _Work(params)
        box = style.region_box(style.GRAPH_REGION).shrink(style.PADDING)
        parts = {
            "title": text_line(
                work.title_latex(), style.Box(box.left, box.right, box.top - 0.8, box.top)
            )
        }
        if params.kind == "work_energy":
            parts.update(
                self._bars(work, style.Box(box.left, box.right, box.bottom, box.top - 1.1))
            )
        else:
            parts.update(
                self._road(params, work, style.Box(box.left, box.right, box.bottom, box.top - 1.1))
            )
        parts["answer"] = text_line(
            work.answer_latex(),
            style.Box(box.left, box.right, box.bottom, box.bottom + 0.7),
            colour=style.HIGHLIGHT_COLOUR,
        )
        rows = work.rows()
        work_box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], work_box, size=30, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def _bars(self, work, area):
        before, after = work.stacks()
        total = max(sum(v for _, v in before), 1e-9)
        height = area.height - 1.6
        scale = height / total
        parts = {}
        for side, stack, x in (
            ("before", before, area.center[0] - 1.3),
            ("after", after, area.center[0] + 1.3),
        ):
            y = area.bottom + 1.2
            group = VGroup()
            for name, value in stack:
                if value <= 1e-9:
                    continue
                h = value * scale
                rect = Rectangle(
                    width=1.5,
                    height=h,
                    stroke_width=1.5,
                    fill_color=COLOURS[name],
                    fill_opacity=0.6,
                    stroke_color=COLOURS[name],
                )
                rect.move_to([x, y + h / 2, 0])
                group.add(rect)
                text = label(rf"{_short(name)}\ {format_sf(value)}", size=22)
                if text.height > h * 0.9 or text.width > 1.4:
                    text.scale_to_fit_width(min(1.4, text.width))
                    if text.height > h * 0.9:
                        text.next_to(rect, [1 if side == "after" else -1, 0, 0], buff=0.1)
                    else:
                        text.move_to(rect)
                else:
                    text.move_to(rect)
                group.add(text)
                y += h
            group.add(
                label(rf"\text{{{side.capitalize()}}}", size=28).move_to([x, area.bottom + 0.75, 0])
            )
            parts[f"bar_{side}"] = group
        return parts

    def _road(self, params, work, area):
        tilt = math.radians(params.slope)
        centre = area.center
        along = [math.cos(tilt), math.sin(tilt), 0]
        start = [centre[0] - 2.6 * along[0], centre[1] - 2.6 * along[1] - 0.4, 0]
        end = [centre[0] + 2.6 * along[0], centre[1] + 2.6 * along[1] - 0.4, 0]
        car = Rectangle(width=1.3, height=0.6, color=style.CURVE_COLOUR, fill_opacity=0.35).rotate(
            tilt
        )
        car.move_to([centre[0] - 0.3 * math.sin(tilt) * -1, centre[1] - 0.1, 0])
        parts = {"road": VGroup(Line(start, end, stroke_width=3), car)}
        if params.slope:
            parts["road"].add(
                Polygon(
                    start, end, [end[0], start[1], 0], stroke_width=1.5, color=style.SECANT_COLOUR
                )
                if tilt > 0
                else Polygon(
                    start, end, [start[0], end[1], 0], stroke_width=1.5, color=style.SECANT_COLOUR
                )
            )
        c = car.get_center()

        def arrow(direction, length, colour, tex, offset=(0, 0)):
            d = [direction[0], direction[1], 0]
            s0 = [c[0] + offset[0], c[1] + offset[1], 0]
            e0 = [s0[0] + length * d[0], s0[1] + length * d[1], 0]
            mob = VGroup(
                Arrow(
                    s0, e0, buff=0, color=colour, stroke_width=4, max_tip_length_to_length_ratio=0.2
                )
            )
            mob.add(label(tex, colour=colour, size=26).next_to(e0, d, buff=0.08))
            return mob

        parts["force_drive"] = arrow(along, 1.6, style.RISE_COLOUR, r"\tfrac{P}{v}")
        parts["force_resist"] = arrow(
            [-along[0], -along[1]],
            1.4,
            style.TANGENT_COLOUR,
            rf"{format_sf(params.resistance)}",
            (0, -0.15),
        )
        parts["force_weight"] = arrow(
            [0, -1], 1.2, style.TEXT_COLOUR, rf"{format_sf(exact(params.mass) * G)}"
        )
        return parts

    def stages(self, params: WorkEnergyParams, level) -> list[Stage]:
        n = len(_Work(params).rows())
        if params.kind == "work_energy":
            steps = [
                stage(
                    "before",
                    "Energy at the start, and work put in",
                    3.0,
                    ["title", "bar_before", "row_1"],
                ),
                stage(
                    "after",
                    "Energy at the end, and work done against resistance",
                    3.0,
                    ["bar_after", "row_2"],
                ),
                stage(
                    "equal",
                    "Energy in equals energy out: the two stacks are the same height",
                    3.5,
                    ["row_3"],
                    emphasise=["row_3"],
                ),
                stage(
                    "solve",
                    "Substitute and solve",
                    3.0,
                    [f"row_{i}" for i in range(4, n + 1)] + ["answer"],
                    emphasise=["answer"],
                ),
            ]
        else:
            steps = [
                stage(
                    "road",
                    "The vehicle and the forces along the road",
                    3.0,
                    ["title", "road", "force_drive", "force_resist", "force_weight"],
                ),
                stage(
                    "drive",
                    "Power is force times speed, so the driving force is P over v",
                    3.0,
                    ["row_1"],
                ),
                stage("newton", "Newton's second law along the road", 3.5, ["row_2"]),
                stage(
                    "solve",
                    "Solve",
                    3.0,
                    [f"row_{i}" for i in range(3, n + 1)] + ["answer"],
                    emphasise=["answer"],
                ),
            ]

        def standard(s):
            return list(s)

        def concise(s):
            return [
                combine("setup", s[0].description, 3.5, s[0], s[1]),
                combine("solve", "Equate and solve", 4.0, s[2], s[3]),
            ]

        return by_level(level, steps, standard, concise)


class _NoSolution(ValueError):
    pass


def _short(name: str) -> str:
    return {
        "KE": r"\text{KE}",
        "PE": r"\text{PE}",
        "work_in": r"\text{work in}",
        "work_out": r"\text{work out}",
    }[name]


class _Work:
    def __init__(self, params: WorkEnergyParams):
        self.params = params
        self.m = exact(params.mass)
        if params.kind == "work_energy":
            self._energy()
        else:
            self._power()

    def _energy(self):
        p = self.params
        symbols = {n: sp.Symbol(n if n != "resistance" else "R", real=True) for n in NAMES}
        # the quantity to find is unknown whatever value it was given
        q = {n: symbols[n] if n == p.find else exact(getattr(p, n)) for n in NAMES}
        self.q = q
        pull = exact(p.pull_force) * q["d"] * sp.cos(sp.rad(exact(p.pull_angle)))
        self.ke1 = self.m * q["u"] ** 2 / 2
        self.ke2 = self.m * q["v"] ** 2 / 2
        self.pe = self.m * G * q["h"]
        self.work_in = pull
        self.work_out = q["resistance"] * q["d"]
        equation = sp.Eq(self.ke1 + self.work_in, self.ke2 + self.pe + self.work_out)
        target = symbols[p.find]
        roots = [r for r in sp.solve(equation, target) if r.is_real]
        if p.find in ("u", "v", "d", "resistance"):
            roots = [r for r in roots if r >= 0]
        if not roots:
            raise _NoSolution(f"no real value of {p.find} fits: the energy does not balance")
        self.value = float(max(roots))
        self.solved = {n: (float(v) if not v.free_symbols else self.value) for n, v in q.items()}

    def _power(self):
        p = self.params
        a, power, v = sp.symbols("a P v", real=True)
        known_v = exact(p.v) if p.v else v
        known_p = exact(p.power) if p.power is not None else power
        known_a = a if p.find == "a" else exact(p.acceleration if p.find == "power" else 0)
        slope_force = self.m * G * sp.sin(sp.rad(exact(p.slope)))
        self.slope_force = slope_force
        equation = sp.Eq(known_p / known_v - exact(p.resistance) - slope_force, self.m * known_a)
        target = {"a": a, "power": power, "max_speed": v}[p.find]
        roots = [r for r in sp.solve(equation, target) if r.is_real]
        if p.find == "max_speed":
            roots = [r for r in roots if r > 0]
        if not roots:
            raise _NoSolution(
                "the vehicle cannot move: the resistance and gravity exceed the driving force"
            )
        self.value = float(roots[0])

    def stacks(self):
        """(name, joules) before and after, each stack adding to the same total."""
        s = self.solved
        ke1 = float(self.m) * s["u"] ** 2 / 2
        ke2 = float(self.m) * s["v"] ** 2 / 2
        pe = float(self.m) * G * s["h"]
        work_in = (
            float(exact(self.params.pull_force))
            * s["d"]
            * math.cos(math.radians(self.params.pull_angle))
        )
        work_out = s["resistance"] * s["d"]
        before = [("KE", ke1), ("work_in", work_in)]
        after = [("KE", ke2), ("work_out", work_out)]
        if pe >= 0:
            after.append(("PE", pe))
        else:
            before.append(("PE", -pe))
        return before, after

    def title_latex(self) -> str:
        p = self.params
        if p.kind == "work_energy":
            return rf"m = {format_sf(self.m, 6)}\text{{ kg}},\ g = 10"
        return (
            rf"m = {format_sf(self.m, 6)}\text{{ kg}},\ R = {format_sf(p.resistance, 6)}\text{{ N}}"
        )

    def answer_latex(self) -> str:
        units = {
            "u": r"\text{ m s}^{-1}",
            "v": r"\text{ m s}^{-1}",
            "h": r"\text{ m}",
            "d": r"\text{ m}",
            "resistance": r"\text{ N}",
            "a": r"\text{ m s}^{-2}",
            "power": r"\text{ W}",
            "max_speed": r"\text{ m s}^{-1}",
        }
        name = {"resistance": "R", "power": "P", "max_speed": "v_{\\max}"}.get(
            self.params.find, self.params.find
        )
        return rf"{name} = {format_sf(self.value)}{units[self.params.find]}"

    def rows(self) -> list[tuple[str, object]]:
        p = self.params
        if p.kind == "work_energy":

            def tex(expr):
                return sp.latex(sp.nsimplify(expr)) if expr.free_symbols else format_sf(expr)

            pe_side_before = p.find != "h" and p.h is not None and p.h < 0
            has_h = p.find == "h" or bool(p.h)
            before = r"\tfrac{1}{2}mu^2"
            before += " + mgh" if pe_side_before else ""
            before += r" + Fd\cos\theta" if p.pull_force else ""
            after = r"\tfrac{1}{2}mv^2"
            after += " + mgh" if not pe_side_before and has_h else ""
            after += " + Rd" if p.resistance or p.find == "resistance" else ""
            ke1, ke2 = tex(self.ke1), tex(self.ke2)
            pe = tex(-self.pe if pe_side_before else self.pe)
            win, wout = tex(self.work_in), tex(self.work_out)
            numbers_before = (
                ke1 + (f" + {pe}" if pe_side_before else "") + (f" + {win}" if p.pull_force else "")
            )
            numbers_after = (
                ke2
                + (f" + {pe}" if (not pe_side_before and has_h) else "")
                + (f" + {wout}" if p.resistance or p.find == "resistance" else "")
            )
            return [
                (rf"\text{{In: }}{before}", None),
                (rf"\text{{Out: }}{after}", None),
                (rf"{numbers_before} = {numbers_after}", style.RISE_COLOUR),
                (self.answer_latex(), style.HIGHLIGHT_COLOUR),
            ]
        v = format_sf(p.v) if p.v else "v"
        power = format_sf(p.power) if p.power is not None else "P"
        a = {"a": "a", "max_speed": r" \times 0"}.get(
            p.find, rf" \times {format_sf(p.acceleration, 6)}"
        )
        slope = (
            rf" - {format_sf(self.slope_force)}"
            if p.slope > 0
            else (rf" + {format_sf(-self.slope_force)}" if p.slope < 0 else "")
        )
        return [
            (rf"\text{{Driving force}} = \frac{{P}}{{v}} = \frac{{{power}}}{{{v}}}", None),
            (
                rf"\frac{{{power}}}{{{v}}} - {format_sf(p.resistance)}{slope} = "
                rf"{format_sf(self.m, 6)}{a}",
                style.RISE_COLOUR,
            ),
            (self.answer_latex(), style.HIGHLIGHT_COLOUR),
        ]


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
