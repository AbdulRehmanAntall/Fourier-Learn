"""Drawing helpers shared by the primitives: axes, curves that stay on their axes, tables,
diagrams in their own coordinates, and angle marks.

`style` holds the look (colours, sizes, regions); this module builds the recurring pieces from
it, so each primitive only says what its picture is.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from manim import (
    Arc,
    Axes,
    Line,
    MathTex,
    Mobject,
    Polygon,
    VGroup,
    VMobject,
)

from app.contracts import Region
from app.primitives import style
from app.primitives.style import Box


@dataclass
class Plot:
    """Axes in a graph region, with the title band above them split into two lines."""

    axes: Axes
    x_label: Mobject
    y_label: Mobject
    x_range: tuple[float, float, float]
    y_range: tuple[float, float, float]
    plot_box: Box
    upper: Box
    """The first line of the title band: an equation."""
    lower: Box
    """The second line: a result or a read-out."""

    def point(self, x: float, y: float) -> np.ndarray:
        return self.axes.c2p(x, y)

    def obstacles(self) -> list[Mobject]:
        """What a label must keep clear of on these axes: the axis labels and tick numbers."""
        return [self.x_label, self.y_label, *style.axis_numbers(self.axes)]

    def axis_lines(self) -> list[Mobject]:
        return [self.axes.x_axis, self.axes.y_axis]


def make_plot(
    region: Region,
    x_values: Sequence[float],
    y_values: Sequence[float],
    *,
    x_label: str = "x",
    y_label: str = "y",
    equal: bool = False,
    title: bool = True,
) -> Plot:
    """Axes whose ranges contain the values and the origin, filling the region below the title
    band. With `equal`, one unit is the same length on both axes, so right angles and circles
    look right."""
    if title:
        title_box, plot_box = style.graph_boxes(region)
    else:
        plot_box = style.region_box(region).shrink(style.PADDING)
        title_box = Box(plot_box.left, plot_box.right, plot_box.top, plot_box.top)
    upper, lower = style.title_lines(title_box)
    x_range = style.axis_range(list(x_values))
    y_range = style.axis_range(list(y_values))
    if equal:
        step = max(x_range[2], y_range[2])
        x_range = _aligned(x_range, step)
        y_range = _aligned(y_range, step)
    x_tex = MathTex(x_label, font_size=style.LABEL_FONT_SIZE)
    y_tex = MathTex(y_label, font_size=style.LABEL_FONT_SIZE)
    room_x = max(0.6, x_tex.width + 0.3)
    room_y = max(0.6, y_tex.height + 0.3)
    width, height = plot_box.width - room_x, plot_box.height - room_y
    x_span, y_span = x_range[1] - x_range[0], y_range[1] - y_range[0]
    if equal:
        unit = min(width / x_span, height / y_span)
        width, height = unit * x_span, unit * y_span
    axes = Axes(
        x_range=list(x_range),
        y_range=list(y_range),
        x_length=width,
        y_length=height,
        tips=False,
        y_axis_config={
            "decimal_number_config": {"num_decimal_places": style._decimal_places(y_range[2])}
        },
        axis_config={
            "include_numbers": True,
            "font_size": style.AXIS_NUMBER_FONT_SIZE,
            "numbers_to_exclude": [0],
            "decimal_number_config": {"num_decimal_places": style._decimal_places(x_range[2])},
        },
    )
    centre = plot_box.center + np.array([-room_x / 2, -room_y / 2, 0])
    axes.move_to(centre)
    return Plot(
        axes,
        axes.get_x_axis_label(x_tex),
        axes.get_y_axis_label(y_tex),
        x_range,
        y_range,
        plot_box,
        upper,
        lower,
    )


def _aligned(axis: tuple[float, float, float], step: float) -> tuple[float, float, float]:
    start = math.floor(axis[0] / step) * step
    end = math.ceil(axis[1] / step) * step
    if float(step).is_integer():
        return int(start), int(end), int(step)
    return start, end, step


def curve(
    plot: Plot,
    f: Callable[[float], float],
    lo: float,
    hi: float,
    *,
    colour=style.CURVE_COLOUR,
    samples: int = 400,
    stroke_width: float = 4,
) -> VGroup:
    """The graph of f on [lo, hi], cut where it leaves the y-range or is undefined, so a curve
    with an asymptote never runs off its axes. One piece per unbroken run."""
    y_lo, y_hi = plot.y_range[0], plot.y_range[1]
    xs = np.linspace(lo, hi, samples)
    ys = np.array([_safe(f, x) for x in xs])
    pieces, run = [], []

    def close():
        if len(run) >= 2:
            piece = VMobject(color=colour, stroke_width=stroke_width)
            piece.set_points_as_corners([plot.point(x, y) for x, y in run])
            pieces.append(piece)
        run.clear()

    for i, (x, y) in enumerate(zip(xs, ys, strict=True)):
        inside = math.isfinite(y) and y_lo <= y <= y_hi
        if inside:
            if not run and i > 0 and math.isfinite(ys[i - 1]):
                run.append(_edge(xs[i - 1], ys[i - 1], x, y, y_lo, y_hi))
            run.append((x, y))
        else:
            if run and math.isfinite(y):
                run.append(_edge(xs[i - 1], ys[i - 1], x, y, y_lo, y_hi))
            close()
    close()
    return VGroup(*pieces)


def _safe(f: Callable[[float], float], x: float) -> float:
    try:
        value = complex(f(x))
    except (ValueError, ZeroDivisionError, OverflowError, TypeError):
        return math.nan
    return value.real if abs(value.imag) < 1e-9 else math.nan


def _edge(x0, y0, x1, y1, y_lo, y_hi) -> tuple[float, float]:
    """Where the segment from (x0, y0) to (x1, y1) crosses the edge of [y_lo, y_hi]."""
    target = y_hi if max(y0, y1) > y_hi else y_lo
    if y1 == y0:
        return x1, min(max(y1, y_lo), y_hi)
    t = (target - y0) / (y1 - y0)
    t = min(max(t, 0.0), 1.0)
    return x0 + t * (x1 - x0), target


@dataclass
class Table:
    group: VGroup
    cells: list[list[MathTex]]
    lines: VGroup

    def row(self, r: int) -> VGroup:
        return VGroup(*self.cells[r])

    def column(self, c: int) -> VGroup:
        return VGroup(*(row[c] for row in self.cells))


def make_table(
    rows: Sequence[Sequence[str]],
    box: Box,
    *,
    font_size: float = style.LABEL_FONT_SIZE,
    pad: float = 0.22,
    colours: Sequence[Sequence[object | None]] | None = None,
) -> Table:
    """A grid of LaTeX cells with ruled lines, scaled to fit `box` and centred in it."""
    cells = [
        [
            MathTex(
                text,
                font_size=font_size,
                color=(colours[r][c] if colours else None) or style.TEXT_COLOUR,
            )
            if text
            else MathTex(r"\,", font_size=font_size)
            for c, text in enumerate(row)
        ]
        for r, row in enumerate(rows)
    ]
    n_cols = max(len(row) for row in rows)
    widths = [max(row[c].width for row in cells if c < len(row)) + 2 * pad for c in range(n_cols)]
    heights = [max(cell.height for cell in row) + 2 * pad for row in cells]
    total_w, total_h = sum(widths), sum(heights)
    left, top = -total_w / 2, total_h / 2
    for r, row in enumerate(cells):
        y = top - sum(heights[:r]) - heights[r] / 2
        for c, cell in enumerate(row):
            x = left + sum(widths[:c]) + widths[c] / 2
            cell.move_to([x, y, 0])
    lines = VGroup()
    for r in range(len(cells) + 1):
        y = top - sum(heights[:r])
        lines.add(Line([left, y, 0], [left + total_w, y, 0], stroke_width=2))
    for c in range(n_cols + 1):
        x = left + sum(widths[:c])
        lines.add(Line([x, top, 0], [x, top - total_h, 0], stroke_width=2))
    group = VGroup(lines, *(cell for row in cells for cell in row))
    style.fit_inside(group, box)
    return Table(group, cells, lines)


class Diagram:
    """Maths coordinates mapped into a box with the same scale on both axes, for figures drawn
    without axes: triangles, circles, nets, trees."""

    def __init__(self, points: Sequence[Sequence[float]], box: Box, margin: float = 0.5):
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        x_lo, x_hi, y_lo, y_hi = min(xs), max(xs), min(ys), max(ys)
        span_x = max(x_hi - x_lo, 1e-9)
        span_y = max(y_hi - y_lo, 1e-9)
        inner = box.shrink(margin)
        self.scale = min(inner.width / span_x, inner.height / span_y)
        self.centre_maths = ((x_lo + x_hi) / 2, (y_lo + y_hi) / 2)
        self.centre_scene = box.center
        self.box = box

    def p(self, x: float, y: float) -> np.ndarray:
        cx, cy = self.centre_maths
        return self.centre_scene + np.array([(x - cx) * self.scale, (y - cy) * self.scale, 0.0])

    def length(self, maths_length: float) -> float:
        return maths_length * self.scale

    def polygon(self, points: Sequence[Sequence[float]], **config) -> Polygon:
        return Polygon(*(self.p(*pt) for pt in points), **config)


def angle_mark(
    vertex: np.ndarray,
    a: np.ndarray,
    b: np.ndarray,
    radius: float = 0.45,
    *,
    colour=style.HIGHLIGHT_COLOUR,
    reflex: bool = False,
) -> VMobject:
    """The arc marking the angle AVB at `vertex`, the smaller one unless `reflex`; a square for
    a right angle."""
    u = (a - vertex) / np.linalg.norm(a - vertex)
    v = (b - vertex) / np.linalg.norm(b - vertex)
    start = math.atan2(u[1], u[0])
    sweep = math.atan2(v[1], v[0]) - start
    sweep = (sweep + math.pi) % (2 * math.pi) - math.pi
    if reflex:
        sweep = sweep - math.copysign(2 * math.pi, sweep)
    if not reflex and abs(abs(sweep) - math.pi / 2) < 1e-3:
        size = radius * 0.7
        corner = [vertex + size * u, vertex + size * (u + v), vertex + size * v]
        mark = VMobject(color=colour, stroke_width=3)
        mark.set_points_as_corners(corner)
        return mark
    return Arc(
        radius=radius, start_angle=start, angle=sweep, arc_center=vertex, color=colour,
        stroke_width=3,
    )  # fmt: skip


def angle_label_position(
    vertex: np.ndarray, a: np.ndarray, b: np.ndarray, distance: float, reflex: bool = False
) -> np.ndarray:
    """A point on the bisector of angle AVB at `distance` from the vertex, for its label."""
    u = (a - vertex) / np.linalg.norm(a - vertex)
    v = (b - vertex) / np.linalg.norm(b - vertex)
    bisector = u + v
    if np.linalg.norm(bisector) < 1e-6:
        bisector = np.array([-u[1], u[0], 0.0])
    bisector = bisector / np.linalg.norm(bisector)
    if reflex:
        bisector = -bisector
    return vertex + distance * bisector


def label(tex: str, *, colour=style.TEXT_COLOUR, size: float = style.LABEL_FONT_SIZE) -> MathTex:
    """A label; fractions at text size, so a coordinate pair stays one line high."""
    return MathTex(inline(tex), font_size=size, color=colour)


def inline(tex: str) -> str:
    return tex.replace(r"\frac", r"\tfrac")


def place_label(
    mobject: Mobject,
    anchor: np.ndarray,
    box: Box,
    obstacles: Sequence[Mobject] = (),
    paths: Sequence[Mobject] = (),
    *,
    wide: bool = False,
) -> Mobject:
    """Put a label beside `anchor`, clear of the obstacles and paths: the four corners close by
    first, then rings further out (all of them with `wide`)."""
    candidates = style.around(anchor, mobject)
    if wide:
        candidates = candidates + ring_candidates(anchor, mobject)
    return style.place_clear(mobject, candidates, box, obstacles, paths)


def ring_candidates(anchor: np.ndarray, mobject: Mobject) -> list[np.ndarray]:
    """Centres for a label on rings around `anchor`, nearest first, 16 directions each."""
    half_w, half_h = mobject.width / 2, mobject.height / 2
    out = []
    for gap in (0.25, 0.55, 0.9, 1.3, 1.8, 2.4):
        for k in range(16):
            angle = 2 * math.pi * k / 16 + math.pi / 4
            dx, dy = math.cos(angle), math.sin(angle)
            out.append(anchor + np.array([dx * (half_w + gap), dy * (half_h + gap), 0.0]))
    return out


def text_line(tex: str, box: Box, *, colour=style.TEXT_COLOUR, size=style.FONT_SIZE) -> MathTex:
    """One line of LaTeX fitted into a box, fractions at text size so the line stays readable."""
    return style.fit_inside(MathTex(inline(tex), font_size=size, color=colour), box)


def stack_boxes(box: Box, count: int, gap: float = 0.15) -> list[Box]:
    """`box` cut into `count` equal horizontal bands, top first."""
    height = (box.height - gap * (count - 1)) / count
    return [
        Box(box.left, box.right, box.top - (i + 1) * height - i * gap, box.top - i * (height + gap))
        for i in range(count)
    ]


def split_columns(box: Box, fractions: Sequence[float], gap: float = 0.2) -> list[Box]:
    """`box` cut into vertical columns with the given width fractions, left first."""
    usable = box.width - gap * (len(fractions) - 1)
    boxes, left = [], box.left
    for fraction in fractions:
        width = usable * fraction / sum(fractions)
        boxes.append(Box(left, left + width, box.bottom, box.top))
        left += width + gap
    return boxes
