"""The layout check (report §5.3.4).

Before a segment is written to video, the bounding box of every visible object is computed at
the end of each animation step. The segment is rejected if a box extends beyond the frame, if
one of the primitive's own objects leaves its contracted region, or if two boxes intersect that
the layout contract does not allow to overlap.
"""

from collections.abc import Collection, Mapping
from itertools import combinations

from manim import Mobject, config

from app.contracts import LayoutContract
from app.primitives.style import Box, bounding_box, region_box

# Anti-aliasing and stroke widths make boxes slightly larger than the shapes they hold.
TOLERANCE = 0.05


def layout_problems(
    objects: Mapping[str, Mobject], layout: LayoutContract, carried: Collection[str] = ()
) -> list[str]:
    """Every layout problem among the visible `objects`, as readable sentences.

    `carried` names the objects left on screen by the previous segment: they were checked when
    that segment was rendered, so only their overlaps with this segment's objects are checked.
    """
    width, height = config.frame_width, config.frame_height
    frame = Box(-width / 2, width / 2, -height / 2, height / 2)
    region = region_box(layout.region)

    boxes = {name: box for name, mob in objects.items() if (box := bounding_box(mob)) is not None}
    problems = []
    for name, box in boxes.items():
        if not _inside(box, frame):
            problems.append(f"{name} extends beyond the frame")
        elif name not in carried and not _inside(box, region):
            problems.append(f"{name} leaves the primitive's region")
    for (a, box_a), (b, box_b) in combinations(boxes.items(), 2):
        if a in carried and b in carried:
            continue
        if box_a.intersects(box_b, TOLERANCE) and not layout.may_overlap(a, b):
            problems.append(f"{a} overlaps {b}")
    return problems


def _inside(box: Box, outer: Box) -> bool:
    return (
        box.left >= outer.left - TOLERANCE
        and box.right <= outer.right + TOLERANCE
        and box.bottom >= outer.bottom - TOLERANCE
        and box.top <= outer.top + TOLERANCE
    )
