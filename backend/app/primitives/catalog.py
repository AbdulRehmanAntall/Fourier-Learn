"""The primitive library as data: id, topic, version and a one-line description of each.

app/primitives/library.py holds the classes, which import Manim. This catalogue lets code that
must run without Manim (the API, scene-plan checks, the admin pages) know which primitives
exist. A test keeps the two in step: add a primitive to both.
"""

from typing import NamedTuple

LIBRARY_VERSION = "0.1.0"
"""Bump it whenever an existing primitive changes how it draws: the version is part of the
variant cache key, so changed primitives never reuse videos rendered by older code."""


class PrimitiveInfo(NamedTuple):
    primitive_id: str
    topic: str
    version: str
    description: str


CATALOGUE = [
    PrimitiveInfo(
        "FunctionGraph",
        "Functions and graphs",
        "1",
        "Draws the graph of a function on labelled axes and marks points on it.",
    ),
    PrimitiveInfo(
        "GradientTriangle",
        "Coordinate geometry",
        "1",
        "Draws the rise and run between two points of a line and computes its gradient.",
    ),
    PrimitiveInfo(
        "TangentSlide",
        "Introductory calculus",
        "1",
        "Slides a tangent along a curve with a read-out of its gradient at each position.",
    ),
    PrimitiveInfo(
        "SecantToTangent",
        "Introductory calculus",
        "1",
        "Draws secants through a point that approach the tangent there as h decreases.",
    ),
    PrimitiveInfo(
        "TravelGraph",
        "Travel graphs and kinematics",
        "1",
        "Draws a distance-time or speed-time graph and interprets its gradients or areas.",
    ),
    PrimitiveInfo(
        "AreaUnderCurve",
        "Introductory calculus",
        "1",
        "Shades the area under a curve between two limits and computes it by integration.",
    ),
    PrimitiveInfo(
        "EquationTransform",
        "All topics",
        "1",
        "Shows an expression being simplified step by step, highlighting what changes.",
    ),
]

PRIMITIVE_IDS = frozenset(info.primitive_id for info in CATALOGUE)
