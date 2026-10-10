"""Shared look and helpers of the primitive library.

One colour per mathematical role across every primitive keeps notation consistent from one
segment to the next, the role the symbol ledgers of LLM2Manim play (report §3.2.4).

Frame layout: the graph region holds axes and graphs; the working region holds algebra. Each
primitive's layout contract names one of them, so two primitives on screen never overlap.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from manim import (
    BLUE_C,
    GREEN_C,
    ORANGE,
    WHITE,
    YELLOW,
    Animation,
    Axes,
    FadeOut,
    MathTex,
    Mobject,
    Scene,
    config,
)

from app.contracts import Region

GRAPH_REGION = Region(x_min=0.0, x_max=0.62, y_min=0.0, y_max=1.0)
WORKING_REGION = Region(x_min=0.62, x_max=1.0, y_min=0.0, y_max=1.0)

CURVE_COLOUR = BLUE_C
POINT_COLOUR = YELLOW
RISE_COLOUR = GREEN_C
RUN_COLOUR = ORANGE
HIGHLIGHT_COLOUR = YELLOW
TEXT_COLOUR = WHITE

FONT_SIZE = 40
LABEL_FONT_SIZE = 30
AXIS_NUMBER_FONT_SIZE = 22

PADDING = 0.3
"""Space kept between a region's edge and anything drawn in it, in scene units."""
TITLE_BAND = 1.3
"""Height at the top of the graph region kept for an equation or formula."""


@dataclass(frozen=True)
class Box:
    left: float
    right: float
    bottom: float
    top: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.top - self.bottom

    @property
    def center(self) -> np.ndarray:
        return np.array([(self.left + self.right) / 2, (self.bottom + self.top) / 2, 0.0])

    def shrink(self, amount: float) -> "Box":
        return Box(self.left + amount, self.right - amount, self.bottom + amount, self.top - amount)

    def intersects(self, other: "Box", tolerance: float = 0.0) -> bool:
        return (
            min(self.right, other.right) - max(self.left, other.left) > tolerance
            and min(self.top, other.top) - max(self.bottom, other.bottom) > tolerance
        )


def region_box(region: Region) -> Box:
    """A region of the frame in scene coordinates."""
    width, height = config.frame_width, config.frame_height
    return Box(
        left=-width / 2 + region.x_min * width,
        right=-width / 2 + region.x_max * width,
        bottom=-height / 2 + region.y_min * height,
        top=-height / 2 + region.y_max * height,
    )


def bounding_box(mobject: Mobject) -> Box | None:
    """The box around a mobject and its submobjects, or None if it has no points."""
    if not mobject.get_family() or all(len(m.points) == 0 for m in mobject.get_family()):
        return None
    lower_left = mobject.get_critical_point(np.array([-1, -1, 0]))
    upper_right = mobject.get_critical_point(np.array([1, 1, 0]))
    return Box(lower_left[0], upper_right[0], lower_left[1], upper_right[1])


def fit_inside(mobject: Mobject, box: Box) -> Mobject:
    """Scale `mobject` down if it is larger than `box`, and centre it in the box."""
    if mobject.width > box.width:
        mobject.scale_to_fit_width(box.width)
    if mobject.height > box.height:
        mobject.scale_to_fit_height(box.height)
    return mobject.move_to(box.center)


def play_step(
    scene: Scene, animations: Sequence[Animation], run_time: float, min_run_time: float
) -> None:
    """Play one step so that it lasts exactly `run_time`.

    The animation itself takes most of the step, but no less than the step's minimum, and the
    remainder is held, so long narration does not make the motion crawl.
    """
    animation_time = min(run_time, max(min_run_time, 0.6 * run_time))
    if animations:
        scene.play(*animations, run_time=animation_time)
    else:
        scene.wait(animation_time)
    if run_time - animation_time > 1e-6:
        scene.wait(run_time - animation_time)


def clear_region(
    carried: Mapping[str, Mobject], region: Region
) -> tuple[list[Animation], dict[str, Mobject]]:
    """Fade-outs for the carried objects inside `region`, and the carried objects that stay."""
    box = region_box(region)
    fades, kept = [], {}
    for name, mobject in carried.items():
        mobject_box = bounding_box(mobject)
        if mobject_box is not None and mobject_box.intersects(box, tolerance=0.05):
            fades.append(FadeOut(mobject))
        else:
            kept[name] = mobject
    return fades, kept


def nice_step(span: float, target_ticks: int = 6) -> float:
    """A tick spacing of 1, 2 or 5 times a power of ten giving about `target_ticks` ticks."""
    raw = span / target_ticks
    magnitude = 10 ** math.floor(math.log10(raw))
    for multiple in (1, 2, 5, 10):
        if raw <= multiple * magnitude:
            return multiple * magnitude
    return 10 * magnitude  # pragma: no cover


def axis_range(values: Sequence[float]) -> tuple[float, float, float]:
    """A range with nice ticks that contains `values` and the origin, with a tick of margin."""
    lo, hi = min(0.0, *values), max(0.0, *values)
    if hi - lo < 1e-9:
        lo, hi = lo - 1, hi + 1
    step = nice_step(hi - lo)
    start, end = math.floor(lo / step) * step - step, math.ceil(hi / step) * step + step
    if float(step).is_integer():
        return int(start), int(end), int(step)
    return start, end, step


def make_axes(
    x_range: tuple[float, float, float], y_range: tuple[float, float, float], box: Box
) -> tuple[Axes, Mobject, Mobject]:
    """Axes with numbered ticks filling `box`, and their x and y labels."""
    label_room = 0.6
    axes = Axes(
        x_range=list(x_range),
        y_range=list(y_range),
        x_length=box.width - label_room,
        y_length=box.height - label_room,
        tips=False,
        y_axis_config={
            "decimal_number_config": {"num_decimal_places": _decimal_places(y_range[2])}
        },
        axis_config={
            "include_numbers": True,
            "font_size": AXIS_NUMBER_FONT_SIZE,
            "numbers_to_exclude": [0],
            "decimal_number_config": {"num_decimal_places": _decimal_places(x_range[2])},
        },
    )
    axes.move_to(box.center + np.array([-label_room / 2, -label_room / 2, 0]))
    x_label = axes.get_x_axis_label(MathTex("x", font_size=LABEL_FONT_SIZE))
    y_label = axes.get_y_axis_label(MathTex("y", font_size=LABEL_FONT_SIZE))
    return axes, x_label, y_label


def _decimal_places(step: float) -> int:
    """Decimal places that show every tick of this spacing exactly: 1 -> 0, 0.5 -> 1."""
    places = 0
    while not math.isclose(step * 10**places, round(step * 10**places)) and places < 3:
        places += 1
    return places


def axis_numbers(axes: Axes) -> list[Mobject]:
    """The tick numbers of both axes, one mobject each, for labels to keep clear of."""
    return [number for axis in (axes.x_axis, axes.y_axis) for number in axis.numbers]


def graph_boxes(region: Region) -> tuple[Box, Box]:
    """The title band and the axes area of a graph region."""
    inner = region_box(region).shrink(PADDING)
    title = Box(inner.left, inner.right, inner.top - TITLE_BAND, inner.top)
    plot = Box(inner.left, inner.right, inner.bottom, inner.top - TITLE_BAND)
    return title, plot


def around(anchor: np.ndarray, label: Mobject, gap: float = 0.25) -> list[np.ndarray]:
    """Centres that put `label` beside `anchor`: up-right first, then up-left, down-right,
    down-left."""
    return [
        anchor + np.array([dx * (label.width / 2 + gap), dy * (label.height / 2 + gap), 0])
        for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1))
    ]


def place_clear(
    label: Mobject,
    candidates: Sequence[np.ndarray],
    box: Box,
    obstacles: Sequence[Mobject] = (),
    paths: Sequence[Mobject] = (),
) -> Mobject:
    """Move `label` to the first candidate centre inside `box` that clears every obstacle and
    every path.

    Obstacles are compact objects, compared by bounding box. Paths are lines and curves, whose
    bounding box would cover half the plot, so points sampled along them are checked instead.
    If no candidate is clear, the label goes where it clashes least; leaving the box counts as
    the worst clash, so the layout check never sees a label outside its region from here.
    """
    blocked = [found for obstacle in obstacles if (found := bounding_box(obstacle)) is not None]
    samples = [point for path in paths for point in path_points(path)]
    best, fewest = candidates[0], None
    for centre in candidates:
        label.move_to(centre)
        placed = bounding_box(label)
        if placed is None:
            continue
        outside = not (
            placed.left >= box.left
            and placed.right <= box.right
            and placed.bottom >= box.bottom
            and placed.top <= box.top
        )
        # A negative tolerance demands a gap, so a label never touches what it avoids.
        clashes = sum(placed.intersects(other, -LABEL_GAP) for other in blocked)
        clashes += sum(_contains(placed, point) for point in samples)
        conflicts = 1000 * outside + clashes
        if conflicts == 0:
            return label
        if fewest is None or conflicts < fewest:
            best, fewest = centre, conflicts
    return label.move_to(best)


def path_points(path: Mobject, per_segment: int = 8) -> np.ndarray:
    """Points along a line or curve: its Bézier control points with straight-line points in
    between, so a long straight line is sampled as densely as a plotted curve."""
    points = path.get_all_points()
    if len(points) < 2:
        return points
    t = np.linspace(0, 1, per_segment, endpoint=False)[:, None, None]
    between = points[:-1][None] * (1 - t) + points[1:][None] * t
    return np.concatenate([between.reshape(-1, 3), points[-1:]])


LABEL_GAP = 0.1
"""Smallest space between a placed label and an obstacle, in scene units."""


def _contains(box: Box, point: np.ndarray, margin: float = 0.05) -> bool:
    return (
        box.left - margin <= point[0] <= box.right + margin
        and box.bottom - margin <= point[1] <= box.top + margin
    )
