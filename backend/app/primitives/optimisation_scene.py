"""OptimisationScene: a practical maximum or minimum, with the physical model drawn beside the
graph of the quantity being optimised (AM 14.8; PRIMITIVES.md #55).

Four classic situations: an open box folded from a square sheet with squares cut from its
corners (maximum volume); a fence on three sides of a rectangle against a wall, and a rectangle
of fixed perimeter (maximum area); a closed cylinder of fixed volume (minimum surface area). The
quantity is written in terms of x, differentiated, and set to zero; the optimum is marked on the
graph and the model is drawn at the optimum. Every value is computed by SymPy.
"""

from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import DashedLine, DashedVMobject, Dot, Ellipse, Line, Rectangle, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PrimitiveParams, Region
from app.primitives import style
from app.primitives.plotting import curve, label, make_plot, place_label, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_value, latex_value, tidy_latex

X = sp.Symbol("x", positive=True)
MODEL = Region(x_min=0.0, x_max=0.62, y_min=0.42, y_max=0.82)
GRAPH = Region(x_min=0.0, x_max=0.62, y_min=0.0, y_max=0.44)


class OptimisationSceneParams(PrimitiveParams):
    scenario: Literal["open_box", "fence_wall", "rectangle", "cylinder"] = Field(
        description="open_box: square sheet of side L; fence_wall: fence of length L on three "
        "sides against a wall; rectangle: perimeter L; cylinder: closed, volume L"
    )
    size: Annotated[float, Field(gt=0, le=1000)] = Field(
        description="L: the sheet's side, the fence's length, the perimeter or the volume"
    )


class OptimisationScene(StagedPrimitive[OptimisationSceneParams]):
    primitive_id = "OptimisationScene"
    version = "1"
    topic = "Introductory calculus"
    params_model = OptimisationSceneParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("axes", "*"), ("curve", "*"), ("guides", "*"), ("model*", "model*")],
    )

    def default_params(self) -> OptimisationSceneParams:
        return OptimisationSceneParams(scenario="open_box", size=12)

    def validate(self, params: OptimisationSceneParams):
        return []

    def computed_values(self, params: OptimisationSceneParams) -> dict[str, str]:
        p = _Problem(params)
        return {
            "quantity": str(p.q),
            "derivative": str(p.dq),
            "best_x": format_value(p.best),
            "best_value": format_value(p.value),
            "kind": p.kind,
        }

    def build(self, params: OptimisationSceneParams, level):
        p = _Problem(params)
        title, _ = style.graph_boxes(style.GRAPH_REGION)
        upper, lower = style.title_lines(title)
        lo, hi = p.domain
        q_num = sp.lambdify(X, p.q, "math")
        xs = np.linspace(lo + (hi - lo) * 0.01, hi - (hi - lo) * 0.01, 121)
        values = [q_num(x) for x in xs]
        if p.kind == "minimum":
            values = [v for v in values if v < 4 * float(p.value)]
        plot = make_plot(
            GRAPH, [0, hi], [0, *values], x_label=p.x_name, y_label=p.symbol, title=False, y_ticks=3
        )
        best = plot.point(float(p.best), float(p.value))
        parts = {
            "quantity": text_line(f"{p.symbol} = {p.q_latex}", upper),
            "derivative": text_line(
                rf"\frac{{d{p.symbol}}}{{d{p.x_name}}} = {tidy_latex(p.dq)} = 0"
                rf"\ \Rightarrow\ {p.x_name} = {latex_value(p.best)}",
                lower,
            ),
            "answer": text_line(
                rf"{p.x_name} = {latex_value(p.best)}:\ "
                rf"{p.symbol}_{{\{'max' if p.kind == 'maximum' else 'min'}}} = "
                rf"{latex_value(p.value)}",
                lower,
            ),
            "axes": VGroup(plot.axes, plot.x_label, plot.y_label),
            "curve": curve(plot, q_num, float(lo) + 1e-6, float(hi) - 1e-6),
            "best": Dot(best, color=style.TANGENT_COLOUR),
            "guides": VGroup(
                DashedLine(plot.point(float(p.best), 0), best, color=style.TANGENT_COLOUR),
                DashedLine(plot.point(0, float(p.value)), best, color=style.TANGENT_COLOUR),
            ),
        }
        text = label(
            rf"({latex_value(p.best)},\ {latex_value(p.value)})", colour=style.TANGENT_COLOUR
        )
        parts["best_label"] = place_label(
            text,
            best,
            plot.plot_box,
            [*plot.obstacles(), parts["best"]],
            [parts["curve"], *plot.axis_lines(), parts["guides"]],
            wide=True,
        )
        model, model_labels = _model(params, p, style.region_box(MODEL).shrink(0.35))
        parts["model"] = model
        parts["model_labels"] = model_labels
        return parts

    def stages(self, params: OptimisationSceneParams, level) -> list[Stage]:
        p = _Problem(params)
        what = {"maximum": "largest", "minimum": "smallest"}[p.kind]
        steps = [
            stage("model", p.story, 3.0, ["model", "model_labels"]),
            stage(
                "quantity",
                f"Write the {p.word} in terms of {p.x_name}",
                3.0,
                ["quantity"],
                emphasise=["quantity"],
            ),
            stage("graph", f"Its graph has a {p.kind}", 2.5, ["axes", "curve"]),
            stage(
                "derivative",
                f"Differentiate and set the derivative to zero for the {what} {p.word}",
                3.5,
                ["derivative"],
                emphasise=["derivative"],
            ),
            stage(
                "best",
                "Mark the turning point on the graph",
                2.0,
                ["best", "guides", "best_label"],
                emphasise=["best"],
            ),
            stage(
                "answer",
                f"Substitute back for the {kind_word(p.kind)} {p.word}",
                2.5,
                morph=[("derivative", "answer")],
                emphasise=["answer"],
            ),
        ]

        def standard(s):
            return [
                combine("model", s[0].description, 3.5, s[0], s[1]),
                s[2],
                combine("solve", "Differentiate, set to zero and find the optimum", 4.0, *s[3:]),
            ]

        def concise(s):
            return [
                combine("model", "The situation and its graph", 3.5, *s[:3]),
                combine("solve", "Set the derivative to zero for the optimum", 4.0, *s[3:]),
            ]

        return by_level(level, steps, standard, concise)


def kind_word(kind: str) -> str:
    return "maximum" if kind == "maximum" else "minimum"


class _Problem:
    def __init__(self, params: OptimisationSceneParams):
        size = exact(params.size)
        self.scenario = params.scenario
        self.size = size
        self.x_name = "x"
        if params.scenario == "open_box":
            self.q = X * (size - 2 * X) ** 2
            self.q_latex = rf"x\left({latex_value(size)} - 2x\right)^2"
            self.domain = (sp.Integer(0), size / 2)
            self.symbol, self.word, self.kind = "V", "volume", "maximum"
            self.story = (
                f"A square sheet of side {format_value(size)} has a square of side x cut from "
                "each corner, and the sides are folded up into an open box"
            )
        elif params.scenario == "fence_wall":
            self.q = X * (size - 2 * X)
            self.q_latex = rf"x\left({latex_value(size)} - 2x\right)"
            self.domain = (sp.Integer(0), size / 2)
            self.symbol, self.word, self.kind = "A", "area", "maximum"
            self.story = (
                f"{format_value(size)} metres of fence make three sides of a rectangle; a wall "
                "is the fourth"
            )
        elif params.scenario == "rectangle":
            self.q = X * (size / 2 - X)
            self.q_latex = rf"x\left({latex_value(size / 2)} - x\right)"
            self.domain = (sp.Integer(0), size / 2)
            self.symbol, self.word, self.kind = "A", "area", "maximum"
            self.story = f"A rectangle has a perimeter of {format_value(size)}"
        else:
            self.x_name = "r"
            self.q = 2 * sp.pi * X**2 + 2 * size / X
            self.q_latex = rf"2\pi r^2 + \frac{{{latex_value(2 * size)}}}{{r}}"
            self.domain = (sp.Integer(0), (size / sp.pi) ** sp.Rational(1, 3) * 2)
            self.symbol, self.word, self.kind = "S", "surface area", "minimum"
            self.story = (
                f"A closed cylinder holds a volume of {format_value(size)}; its height is fixed "
                "by its radius r"
            )
        self.dq = sp.diff(self.q, X)
        critical = [c for c in sp.solve(sp.Eq(self.dq, 0), X) if c.is_real and c > 0]
        lo, hi = self.domain
        critical = [c for c in critical if lo < c < hi]
        self.best = critical[0]
        self.value = sp.simplify(self.q.subs(X, self.best))
        if self.scenario != "cylinder":
            self.dq = sp.expand(self.dq)


def _model(params, p: _Problem, box: style.Box) -> tuple[VGroup, VGroup]:
    """The situation drawn at its optimum, with its sides labelled."""
    best = float(p.best)
    size = float(p.size)
    labels = VGroup()
    colour = style.CURVE_COLOUR
    if params.scenario == "open_box":
        scale = min(box.width, box.height) / size
        side, cut = size * scale, best * scale
        sheet = Rectangle(width=side, height=side, color=colour, fill_opacity=0.15)
        sheet.move_to(box.center)
        corners = VGroup()
        left, top = sheet.get_left()[0], sheet.get_top()[1]
        for cx in (0, side - cut):
            for cy in (0, side - cut):
                square = Rectangle(
                    width=cut,
                    height=cut,
                    color=style.TANGENT_COLOUR,
                    fill_opacity=0.5,
                    stroke_width=2,
                )
                square.move_to([left + cx + cut / 2, top - cy - cut / 2, 0])
                corners.add(square)
        folds = VGroup(
            *(
                DashedVMobject(Line(a, b), num_dashes=12)
                for a, b in (
                    ([left + cut, top, 0], [left + cut, top - side, 0]),
                    ([left + side - cut, top, 0], [left + side - cut, top - side, 0]),
                    ([left, top - cut, 0], [left + side, top - cut, 0]),
                    ([left, top - side + cut, 0], [left + side, top - side + cut, 0]),
                )
            )
        )
        labels.add(label("x", colour=style.TANGENT_COLOUR).next_to(corners[0], [-1, 0, 0], 0.1))
        labels.add(label(latex_value(p.size)).next_to(sheet, [0, -1, 0], 0.1))
        labels.add(label(f"{latex_value(p.size)} - 2x").move_to(sheet))
        return VGroup(sheet, corners, folds), labels
    if params.scenario in ("fence_wall", "rectangle"):
        width = size - 2 * best if params.scenario == "fence_wall" else size / 2 - best
        scale = min(box.width / width, (box.height - 0.5) / best) * 0.8
        w, h = width * scale, best * scale
        rect = Rectangle(width=w, height=h, color=colour, fill_opacity=0.15)
        rect.move_to(box.center + [0, -0.2, 0])
        group = VGroup(rect)
        if params.scenario == "fence_wall":
            wall = Line(
                rect.get_corner([-1, 1, 0]) + [-0.4, 0.05, 0],
                rect.get_corner([1, 1, 0]) + [0.4, 0.05, 0],
                color=style.TEXT_COLOUR,
                stroke_width=8,
            )
            group.add(wall)
            labels.add(label(r"\text{wall}").next_to(wall, [0, 1, 0], 0.1))
            labels.add(label(f"{latex_value(p.size)} - 2x").next_to(rect, [0, -1, 0], 0.1))
        else:
            labels.add(label(f"{latex_value(p.size / 2)} - x").next_to(rect, [0, -1, 0], 0.1))
        labels.add(label("x").next_to(rect, [-1, 0, 0], 0.1))
        return group, labels
    # Cylinder: an upright drawing with its radius and height.
    height_value = size / (np.pi * best**2)
    scale = min(box.width / (2 * best) * 0.7, (box.height - 0.6) / (height_value + best))
    r, hgt = best * scale, height_value * scale
    centre = box.center
    top = Ellipse(width=2 * r, height=0.5 * r, color=colour).move_to(centre + [0, hgt / 2, 0])
    bottom = Ellipse(width=2 * r, height=0.5 * r, color=colour).move_to(centre - [0, hgt / 2, 0])
    sides = VGroup(
        Line(centre + [-r, hgt / 2, 0], centre + [-r, -hgt / 2, 0], color=colour),
        Line(centre + [r, hgt / 2, 0], centre + [r, -hgt / 2, 0], color=colour),
    )
    radius = Line(centre + [0, hgt / 2, 0], centre + [r, hgt / 2, 0], color=style.TANGENT_COLOUR)
    labels.add(label("r", colour=style.TANGENT_COLOUR).next_to(radius, [0, 1, 0], 0.15))
    labels.add(label("h").next_to(sides[1], [1, 0, 0], 0.1))
    return VGroup(top, bottom, sides, radius), labels
