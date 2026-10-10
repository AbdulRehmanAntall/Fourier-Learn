import numpy as np
from manim import Square

from app.contracts import LayoutContract, Region
from app.renderer.layout import layout_problems

LEFT_HALF = LayoutContract(
    region=Region(x_min=0, x_max=0.5, y_min=0, y_max=1),
    allowed_overlaps=[("axes", "*"), ("point_*", "curve")],
)


def square(x, y, side=1.0):
    return Square(side_length=side).move_to([x, y, 0])


def test_objects_inside_the_region_and_apart_pass():
    assert layout_problems({"a": square(-5, 0), "b": square(-2, 0)}, LEFT_HALF) == []


def test_objects_outside_the_frame_or_region_are_named():
    problems = layout_problems({"far": square(-20, 0), "right": square(3, 0)}, LEFT_HALF)
    assert problems == ["far extends beyond the frame", "right leaves the primitive's region"]


def test_overlaps_are_rejected_unless_the_contract_allows_them():
    assert layout_problems({"label": square(-3, 0), "title": square(-3, 0.5)}, LEFT_HALF) == [
        "label overlaps title"
    ]
    allowed = {"axes": square(-3, 0, 4), "label": square(-3, 0), "point_1": square(-4, 1)}
    allowed["curve"] = square(-4, 1)
    assert layout_problems(allowed, LEFT_HALF) == []


def test_carried_objects_are_not_held_to_this_primitives_region():
    carried = {"graph": square(3, 0)}
    assert layout_problems({**carried, "a": square(-5, 0)}, LEFT_HALF, carried=carried) == []
    assert layout_problems({**carried, "b": square(3, 0.2)}, LEFT_HALF, carried=carried) == [
        "b leaves the primitive's region",
        "graph overlaps b",
    ]


def test_labels_go_to_the_first_clear_place():
    from manim import Line

    from app.primitives.style import Box, bounding_box, path_points, place_clear

    box = Box(-7, 7, -4, 4)
    candidates = [np.array([0.0, 0, 0]), np.array([3.0, 0, 0]), np.array([-3.0, 0, 0])]

    # Blocked by an obstacle at the first place, so it takes the second.
    label = place_clear(square(9, 9, 0.5), candidates, box, obstacles=[square(0, 0, 0.5)])
    assert np.allclose(label.get_center(), candidates[1])

    # A line through the second place is avoided too, although its box covers everything.
    line = Line([2, -4, 0], [4, 4, 0])
    assert bounding_box(line).intersects(Box(2.7, 3.3, -0.3, 0.3))
    label = place_clear(square(9, 9, 0.5), candidates, box, [square(0, 0, 0.5)], [line])
    assert np.allclose(label.get_center(), candidates[2])

    # A long straight line is sampled densely, not just at its ends.
    assert len(path_points(line)) > 20


def test_when_nothing_is_clear_the_label_takes_the_least_crowded_place():
    from app.primitives.style import Box, place_clear

    box = Box(-7, 7, -4, 4)
    candidates = [np.array([0.0, 0, 0]), np.array([3.0, 0, 0]), np.array([20.0, 0, 0])]
    obstacles = [square(0, 0, 0.5), square(-0.2, 0, 0.5), square(3, 0, 0.5)]
    label = place_clear(square(9, 9, 0.5), candidates, box, obstacles)
    # One clash at the second place beats two at the first; outside the box is worst.
    assert np.allclose(label.get_center(), candidates[1])
