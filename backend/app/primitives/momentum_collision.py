"""MomentumCollision: two particles colliding directly in a line, before and after, with total
momentum conserved, to find an unknown velocity or mass; the particles may coalesce
(9709 4.3).

Momentum is mass times velocity, with a direction: velocities to the right are positive, to the
left negative. In a collision the total momentum before equals the total after:
m₁u₁ + m₂u₂ = m₁v₁ + m₂v₂, or (m₁ + m₂)v if they stick together. A negative answer means that
particle moves to the left: its direction has reversed if it was moving right. SymPy solves
exactly; answers are to 3 significant figures.
"""

from typing import Annotated

import sympy as sp
from manim import Arrow, Circle, Line, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.plotting import label, stack_lines, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_sf

Mass = Annotated[float, Field(gt=0, le=5000)] | None
Velocity = Annotated[float, Field(ge=-100, le=100)] | None
NAMES = ("m1", "m2", "u1", "u2", "v1", "v2")


class MomentumCollisionParams(PrimitiveParams):
    m1: Mass = Field(default=None, description="Mass of A (kg)")
    m2: Mass = Field(default=None, description="Mass of B (kg)")
    u1: Velocity = Field(default=None, description="A's velocity before (m/s, right positive)")
    u2: Velocity = Field(default=None, description="B's velocity before")
    v1: Velocity = Field(
        default=None, description="A's velocity after (the common one if they coalesce)"
    )
    v2: Velocity = Field(default=None, description="B's velocity after (not used if they coalesce)")
    coalesce: bool = Field(default=False, description="The particles stick together")


class MomentumCollision(StagedPrimitive[MomentumCollisionParams]):
    primitive_id = "MomentumCollision"
    version = "1"
    topic = "Momentum"
    params_model = MomentumCollisionParams
    layout = LayoutContract(region=FULL_FRAME, allowed_overlaps=[("track_*", "*")])

    def default_params(self) -> MomentumCollisionParams:
        return MomentumCollisionParams(m1=3, m2=2, u1=6, u2=-4, v2=5)

    def validate(self, params: MomentumCollisionParams) -> list[PredicateFailure]:
        names = [n for n in NAMES if not (params.coalesce and n == "v2")]
        missing = [n for n in names if getattr(params, n) is None]
        if len(missing) != 1:
            message = (
                f"leave out exactly one quantity to find (missing: {', '.join(missing) or 'none'})"
            )
            return [_failure("one_unknown", message, *names)]
        if params.coalesce and params.v2 is not None:
            return [_failure("coalesce_one_velocity", "coalescing particles share v1", "v2")]
        work = _Work(params)
        if work.value is None:
            return [
                _failure("solvable", "momentum cannot be conserved with these values", missing[0])
            ]
        if missing[0].startswith("m") and work.value <= 0:
            return [_failure("positive_mass", "the mass comes out zero or negative", missing[0])]
        if work.solved["u1"] <= work.solved["u2"]:
            message = "A must be catching or meeting B: u1 must be greater than u2"
            return [_failure("they_meet", message, "u1", "u2")]
        return []

    def computed_values(self, params: MomentumCollisionParams) -> dict[str, str]:
        work = _Work(params)
        return {work.unknown: format_sf(work.value)}

    def build(self, params: MomentumCollisionParams, level):
        work = _Work(params)
        box = style.region_box(style.GRAPH_REGION).shrink(style.PADDING)
        top, bottom = box.top - 2.3, box.bottom + 1.6
        parts = {
            "title": text_line(
                r"\text{Momentum before} = \text{momentum after}",
                style.Box(box.left, box.right, box.top - 0.8, box.top),
            )
        }
        for row, (y, word) in enumerate(((top, "Before"), (bottom, "After"))):
            parts[f"track_{row}"] = Line(
                [box.left, y - 0.5, 0],
                [box.right, y - 0.5, 0],
                stroke_width=2,
                color=style.SECANT_COLOUR,
            )
            parts[f"heading_{row}"] = label(rf"\text{{{word}}}", size=30).move_to(
                [box.left + 0.8, y + 0.9, 0]
            )
        centres = {"A": box.center[0] - 1.3, "B": box.center[0] + 1.3}
        before = {"A": (work.m1, work.u1), "B": (work.m2, work.u2)}
        after = {"A": (work.m1, work.v1), "B": (work.m2, work.v2)}
        for key, y, data, offset in (("before", top, before, 0), ("after", bottom, after, 0)):
            group = VGroup()
            for name, (m, v) in data.items():
                x = centres[name] + offset
                if work.coalesce and key == "after":
                    x = box.center[0] + (-0.45 if name == "A" else 0.45)
                colour = style.CURVE_COLOUR if name == "A" else style.RUN_COLOUR
                ball = Circle(radius=0.42, color=colour, fill_opacity=0.35).move_to([x, y, 0])
                mass_text = label(rf"{_q(m)}\text{{ kg}}", size=24).move_to(ball)
                if mass_text.width > 0.75:
                    mass_text.scale_to_fit_width(0.75)
                group.add(ball, mass_text)
                if work.coalesce and key == "after" and name == "B":
                    continue
                arrow_x = box.center[0] if (work.coalesce and key == "after") else x
                direction = 1 if (v is not None and not v.free_symbols and v >= 0) else -1
                if v is not None and v.free_symbols:
                    direction = 1
                if v == 0:
                    group.add(
                        label(r"\text{at rest}", size=24, colour=colour).move_to(
                            [arrow_x, y + 0.75, 0]
                        )
                    )
                    continue
                start = [arrow_x - 0.6 * direction, y + 0.75, 0]
                end = [arrow_x + 0.6 * direction, y + 0.75, 0]
                group.add(
                    Arrow(
                        start,
                        end,
                        buff=0,
                        color=colour,
                        stroke_width=4,
                        max_tip_length_to_length_ratio=0.25,
                    )
                )
                group.add(
                    label(
                        rf"{_q(abs(v) if not v.free_symbols else v)}\text{{ m s}}^{{-1}}",
                        colour=colour,
                        size=24,
                    ).move_to([arrow_x, y + 1.15, 0])
                )
            parts[key] = group
        rows = work.rows()
        work_box = style.region_box(style.WORKING_REGION).shrink(style.PADDING)
        texts = stack_lines([r for r, _ in rows], work_box, size=32, colours=[c for _, c in rows])
        for i, text in enumerate(texts, start=1):
            parts[f"row_{i}"] = text
        return parts

    def stages(self, params: MomentumCollisionParams, level) -> list[Stage]:
        n = len(_Work(params).rows())
        steps = [
            stage(
                "before",
                "Before the collision: take to the right as positive",
                3.0,
                ["title", "track_0", "heading_0", "before"],
            ),
            stage(
                "after",
                "After: they move together" if params.coalesce else "After the collision",
                2.5,
                ["track_1", "heading_1", "after"],
            ),
            stage(
                "equation",
                "Total momentum before equals total momentum after",
                3.5,
                ["row_1", "row_2"],
            ),
            stage(
                "solve",
                "Solve; a negative velocity means moving to the left",
                3.0,
                [f"row_{i}" for i in range(3, n + 1)],
                emphasise=[f"row_{n}"],
            ),
        ]

        def standard(s):
            return [combine("picture", "Before and after the collision", 3.5, s[0], s[1]), *s[2:]]

        def concise(s):
            return [
                combine("picture", "Before and after the collision", 3.5, s[0], s[1]),
                combine("solve", "Momentum is conserved: solve", 4.0, s[2], s[3]),
            ]

        return by_level(level, steps, standard, concise)


class _Work:
    def __init__(self, params: MomentumCollisionParams):
        self.coalesce = params.coalesce
        symbols = {n: sp.Symbol(n.replace("1", "_1").replace("2", "_2")) for n in NAMES}
        values = {
            n: exact(getattr(params, n)) if getattr(params, n) is not None else symbols[n]
            for n in NAMES
        }
        if params.coalesce:
            values["v2"] = values["v1"]
        self.m1, self.m2, self.u1, self.u2, self.v1, self.v2 = (values[n] for n in NAMES)
        names = [n for n in NAMES if not (params.coalesce and n == "v2")]
        self.unknown = next(n for n in names if getattr(params, n) is None)
        target = symbols[self.unknown]
        before = self.m1 * self.u1 + self.m2 * self.u2
        after = (
            (self.m1 + self.m2) * self.v1
            if params.coalesce
            else self.m1 * self.v1 + self.m2 * self.v2
        )
        self.before, self.after = before, after
        found = sp.solve(sp.Eq(before, after), target)
        self.value = sp.nsimplify(found[0]) if len(found) == 1 else None
        if self.value is not None:
            values[self.unknown] = self.value
            if params.coalesce and self.unknown == "v1":
                values["v2"] = self.value
            self.solved = values
        self.target_tex = "v" if params.coalesce and self.unknown == "v1" else sp.latex(target)

    def rows(self) -> list[tuple[str, object]]:
        if self.coalesce:
            law = r"m_1u_1 + m_2u_2 = (m_1 + m_2)v"
        else:
            law = r"m_1u_1 + m_2u_2 = m_1v_1 + m_2v_2"
        rows = [
            (law, style.RISE_COLOUR),
            (
                rf"{_product(self.m1, self.u1)} + {_product(self.m2, self.u2)} = "
                + self._after_tex(),
                None,
            ),
        ]
        rows.append((rf"{self.target_tex} = {format_sf(self.value)}", style.HIGHLIGHT_COLOUR))
        if self.unknown.startswith(("u", "v")) and self.value < 0:
            rows.append((r"\text{Negative: it moves to the left}", None))
        return rows

    def _after_tex(self) -> str:
        if self.coalesce:
            v = "v" if self.v1.free_symbols else _q(self.v1, bracket=True)
            return rf"({_q(self.m1)} + {_q(self.m2)}){v}"
        return rf"{_product(self.m1, self.v1)} + {_product(self.m2, self.v2)}"


def _q(value, bracket: bool = False) -> str:
    if value.free_symbols:
        return sp.latex(value)
    text = format_sf(value, 6)
    return rf"({text})" if bracket and value < 0 else text


def _product(m, v) -> str:
    if v.free_symbols:
        return f"{_q(m)}{sp.latex(v)}"
    if m.free_symbols:
        return f"{_q(v, bracket=True)}{sp.latex(m)}"
    return rf"{_q(m)} \times {_q(v, bracket=True)}"


def _failure(predicate, message, *parameters) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=list(parameters)
    )
