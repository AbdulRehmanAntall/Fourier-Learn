"""TravelGraph: a distance-time or speed-time graph with gradients or areas shaded and
interpreted (report Table 5.2, travel graphs and kinematics).

The journey is given as the corners of the graph, from time 0. On a distance-time graph the
gradient of a stage is the speed; on a speed-time graph the gradient is the acceleration and
the area under the graph is the distance travelled. Every value shown is computed exactly by
SymPy from the corners.
"""

from typing import Annotated, Literal

import numpy as np
import sympy as sp
from manim import (
    Create,
    FadeIn,
    Indicate,
    MathTex,
    Polygon,
    Succession,
    VMobject,
    Write,
)
from pydantic import Field

from app.contracts import (
    LayoutContract,
    Level,
    PredicateFailure,
    Primitive,
    PrimitiveParams,
    StepSpec,
)
from app.primitives import style
from app.primitives.symbolic import exact, format_number, latex_number

Time = Annotated[float, Field(ge=0, le=1000)]
Amount = Annotated[float, Field(ge=0, le=1000)]


class TravelGraphParams(PrimitiveParams):
    kind: Literal["distance_time", "speed_time"]
    points: list[tuple[Time, Amount]] = Field(
        min_length=2,
        max_length=6,
        description="Corners of the graph as (time, distance) or (time, speed), from time 0",
    )
    show: Literal["gradients", "areas"] = Field(
        default="gradients",
        description="Interpret the gradients (speed or acceleration) or the areas (distance; "
        "speed-time graphs only)",
    )
    time_unit: Literal["s", "min", "h"] = "s"
    distance_unit: Literal["m", "km"] = "m"


class TravelGraph(Primitive[TravelGraphParams]):
    primitive_id = "TravelGraph"
    version = "1"
    topic = "Travel graphs and kinematics"
    params_model = TravelGraphParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("axes", "*"), ("graph", "*"), ("shade_*", "*")],
    )

    def default_params(self) -> TravelGraphParams:
        return TravelGraphParams(
            kind="speed_time", points=[(0, 0), (4, 8), (10, 8), (12, 0)], show="areas"
        )

    def validate(self, params: TravelGraphParams) -> list[PredicateFailure]:
        times = [t for t, _ in params.points]
        failures = []
        if times[0] != 0:
            failures.append(_failure("starts_at_zero", "the first corner must be at time 0"))
        if any(later <= earlier for earlier, later in zip(times, times[1:], strict=False)):
            failures.append(_failure("time_increases", "time must increase from corner to corner"))
        if params.show == "areas" and params.kind == "distance_time":
            message = "the area under a distance-time graph has no meaning; use gradients"
            failures.append(_failure("areas_need_speed_time", message, "show", "kind"))
        return failures

    def computed_values(self, params: TravelGraphParams) -> dict[str, str]:
        units = _units(params)
        values = {
            "time_unit": params.time_unit,
            "distance_unit": params.distance_unit,
            "speed_unit": units["speed"],
            "acceleration_unit": units["acceleration"],
            "total_time": format_number(exact(params.points[-1][0])),
        }
        for i, segment in enumerate(_segments(params), start=1):
            values[f"segment_{i}_gradient"] = format_number(segment["gradient"])
            if params.kind == "distance_time":
                values[f"segment_{i}_speed"] = format_number(abs(segment["gradient"]))
            else:
                values[f"segment_{i}_acceleration"] = format_number(segment["gradient"])
                values[f"segment_{i}_distance"] = format_number(segment["area"])
        if params.kind == "speed_time":
            values["total_distance"] = format_number(sum(s["area"] for s in _segments(params)))
        return values

    def steps(self, params: TravelGraphParams, level: Level) -> list[StepSpec]:
        return [spec for spec, _ in _plan(params, level)]

    def animate(self, scene, params, level, run_times, carried):
        fades, visible = style.clear_region(carried, self.layout.region)
        parts = self._build(params)
        plan = _plan(params, level)
        for i, ((spec, names), run_time) in enumerate(zip(plan, run_times, strict=True)):
            animations = [_introduce(name, parts[name], level) for name in names]
            style.play_step(
                scene, (fades if i == 0 else []) + animations, run_time, spec.min_run_time_s
            )
            visible.update({name: parts[name] for name in names})
            yield dict(visible)

    def _build(self, params: TravelGraphParams) -> dict:
        units = _units(params)
        title_box, plot_box = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title_box)
        times = [t for t, _ in params.points]
        amounts = [v for _, v in params.points]
        axis_word = "d" if params.kind == "distance_time" else "v"
        axis_unit = params.distance_unit if params.kind == "distance_time" else units["speed"]
        axes, x_label, y_label = style.make_axes(
            style.axis_range(times),
            style.axis_range(amounts),
            plot_box,
            x_label=rf"t\,(\mathrm{{{params.time_unit}}})",
            y_label=rf"{axis_word}\,(\mathrm{{{axis_unit}}})",
        )
        corners = [axes.c2p(t, v) for t, v in params.points]
        graph = VMobject(color=style.CURVE_COLOUR, stroke_width=5).set_points_as_corners(corners)

        if params.show == "areas":
            statement = r"\text{distance travelled} = \text{area under the graph}"
        elif params.kind == "distance_time":
            statement = r"\text{speed} = \text{gradient}"
        else:
            statement = r"\text{acceleration} = \text{gradient}"
        parts = {
            "axes": axes,
            "x_label": x_label,
            "y_label": y_label,
            "graph": graph,
            "statement": style.fit_inside(MathTex(statement, font_size=style.FONT_SIZE), upper),
        }
        obstacles = [x_label, y_label, *style.axis_numbers(axes)]
        paths = [graph, axes.x_axis, axes.y_axis]
        areas = []
        for i, segment in enumerate(_segments(params), start=1):
            (t1, v1), (t2, v2) = segment["start"], segment["end"]
            if params.show == "gradients":
                gradient = segment["gradient"]
                if params.kind == "distance_time":
                    text = rf"{latex_number(abs(gradient))}\ \mathrm{{{units['speed']}}}"
                else:
                    text = rf"{latex_number(gradient)}\ \mathrm{{{units['acceleration_tex']}}}"
                label = MathTex(text, font_size=style.LABEL_FONT_SIZE, color=style.RISE_COLOUR)
                middle = axes.c2p((t1 + t2) / 2, (v1 + v2) / 2)
                normal = _normal(axes.c2p(t1, v1), axes.c2p(t2, v2))
                reach = np.abs(normal[:2]) @ np.array([label.width, label.height]) / 2 + 0.2
                candidates = [middle + normal * reach, middle - normal * reach]
                candidates += style.around(middle, label)
                style.place_clear(label, candidates, plot_box, obstacles, paths)
                obstacles.append(label)
                parts[f"gradient_{i}"] = label
            elif segment["area"] != 0:
                shade = Polygon(
                    axes.c2p(t1, 0),
                    corners[i - 1],
                    corners[i],
                    axes.c2p(t2, 0),
                    color=style.AREA_COLOUR,
                    fill_opacity=style.AREA_OPACITY,
                    stroke_width=2,
                )
                label = MathTex(
                    rf"{latex_number(segment['area'])}\ \mathrm{{{params.distance_unit}}}",
                    font_size=style.LABEL_FONT_SIZE,
                )
                # Inside the stage when it is wide enough: low down first, clear of a sloping
                # line. Otherwise above the stage, or to the right of the last stage, where it
                # cannot be mistaken for the next stage's area.
                middle_t = (t1 + t2) / 2
                width = axes.c2p(t2, 0)[0] - axes.c2p(t1, 0)[0]
                heights = [min(v1, v2) / 2, (v1 + v2) / 4, (v1 + v2) / 6]
                candidates = [axes.c2p(middle_t, h) for h in heights if h > 0]
                if label.width >= 0.9 * width:
                    candidates = []
                above = axes.c2p(middle_t, max(v1, v2)) + np.array([0, label.height / 2 + 0.2, 0])
                if i == len(params.points) - 1:
                    half = axes.c2p(0, (v1 + v2) / 4)[1]
                    candidates.append(
                        np.array([axes.c2p(t2, 0)[0] + label.width / 2 + 0.2, half, 0])
                    )
                candidates += [above, *style.around(above, label)]
                style.place_clear(label, candidates, plot_box, obstacles, paths)
                obstacles.append(label)
                parts[f"shade_{i}"] = shade
                parts[f"area_{i}"] = label
                areas.append(segment["area"])

        if params.show == "areas":
            total = sum(areas, sp.Integer(0))
            unit = rf"\ \mathrm{{{params.distance_unit}}}"
            working = " + ".join(latex_number(a) for a in areas)
            text = (
                rf"\text{{distance}} = {working} = {latex_number(total)}{unit}"
                if len(areas) > 1
                else rf"\text{{distance}} = {latex_number(total)}{unit}"
            )
            parts["total"] = style.fit_inside(MathTex(text, font_size=style.FONT_SIZE), lower)
        return parts


def _segments(params: TravelGraphParams) -> list[dict]:
    segments = []
    for (t1, v1), (t2, v2) in zip(params.points, params.points[1:], strict=False):
        dt, dv = exact(t2) - exact(t1), exact(v2) - exact(v1)
        segments.append(
            {
                "start": (t1, v1),
                "end": (t2, v2),
                "gradient": dv / dt,
                # A trapezium: the mean of the two speeds times the time.
                "area": (exact(v1) + exact(v2)) / 2 * dt,
            }
        )
    return segments


def _units(params: TravelGraphParams) -> dict[str, str]:
    speed = f"{params.distance_unit}/{params.time_unit}"
    return {
        "speed": speed,
        "acceleration": f"{speed}^2",
        "acceleration_tex": f"{speed}^{{2}}",
    }


def _normal(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """The unit vector at right angles to the segment from a to b, pointing up (or right)."""
    direction = b - a
    normal = np.array([-direction[1], direction[0], 0.0])
    normal /= np.linalg.norm(normal) or 1.0
    return normal if normal[1] > 0 or (normal[1] == 0 and normal[0] > 0) else -normal


def _plan(params: TravelGraphParams, level: Level) -> list[tuple[StepSpec, list[str]]]:
    segments = _segments(params)
    axes = ["axes", "x_label", "y_label"]
    stages = [
        i for i, segment in enumerate(segments, start=1)
        if params.show == "gradients" or segment["area"] != 0
    ]  # fmt: skip
    if params.show == "gradients":
        meaning = "speed" if params.kind == "distance_time" else "acceleration"
        per_stage = [
            (
                _step(
                    f"stage_{i}", f"Find the {meaning} in stage {i} from its gradient", 2.0, 1, 1
                ),
                [f"gradient_{i}"],
            )
            for i in stages
        ]
        all_stages = [f"gradient_{i}" for i in stages]
        describe = f"Read the {meaning} of every stage from its gradient"
        finish = []
    else:
        per_stage = [
            (
                _step(f"stage_{i}", f"Shade stage {i} and find its area", 2.0, 1, 1),
                [f"shade_{i}", f"area_{i}"],
            )
            for i in stages
        ]
        all_stages = [name for i in stages for name in (f"shade_{i}", f"area_{i}")]
        describe = "Shade every stage and find its area"
        finish = ["total"]
    total_step = (_step("total", "Add the areas to find the total distance", 2.5, 1), finish)

    graph_kind = "distance" if params.kind == "distance_time" else "speed"
    if level is Level.SUPPORTED:
        plan = [
            (_step("axes", f"Draw the axes: time across, {graph_kind} up", 2.0, labels=2), axes),
            (_step("graph", "Draw the graph one stage at a time", 3.0), ["graph"]),
            (_step("rule", "State what the graph tells us", 2.0, labels=1), ["statement"]),
            *per_stage,
        ]
        return plan + ([total_step] if finish else [])
    if level is Level.STANDARD:
        plan = [
            (_step("graph", f"Draw the {graph_kind}-time graph", 2.5, labels=2), axes + ["graph"]),
            (_step("rule", "State what the graph tells us", 1.5, labels=1), ["statement"]),
            (_step("stages", describe, 3.0, labels=len(stages)), all_stages),
        ]
        return plan + ([total_step] if finish else [])
    return [
        (
            _step("graph", f"Draw the {graph_kind}-time graph and state the rule", 2.5, labels=3),
            axes + ["graph", "statement"],
        ),
        (_step("stages", describe, 2.5, labels=len(stages)), all_stages + finish),
    ]


def _introduce(name: str, mobject, level: Level):
    if name in ("axes", "graph"):
        return Create(mobject)
    if name.startswith("shade_"):
        appear = FadeIn(mobject)
        return Succession(appear, Indicate(mobject)) if level is Level.SUPPORTED else appear
    appear = Write(mobject)
    if level is Level.SUPPORTED and name.startswith(("gradient_", "total")):
        return Succession(appear, Indicate(mobject))
    return appear


def _step(name, description, min_run_time, labels=0, highlights=0) -> StepSpec:
    return StepSpec(
        name=name,
        description=description,
        min_run_time_s=min_run_time,
        labels=labels,
        highlights=highlights,
    )


def _failure(predicate: str, message: str, *parameters: str) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency",
        predicate=predicate,
        message=message,
        parameters=list(parameters) or ["points"],
    )
