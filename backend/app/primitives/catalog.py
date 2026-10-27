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
    PrimitiveInfo(
        "AlgebraBalance",
        "Algebra and graphs",
        "1",
        "Solves an equation or changes the subject by doing the same to both sides.",
    ),
    PrimitiveInfo(
        "ExpansionGrid",
        "Algebra and graphs",
        "1",
        "Expands brackets or factorises with a grid (area) model, like terms coloured alike.",
    ),
    PrimitiveInfo(
        "CompletingSquare",
        "Algebra and graphs",
        "1",
        "Completes the square as an area: x squared plus two strips, with the missing corner.",
    ),
    PrimitiveInfo(
        "QuadraticExplorer",
        "Algebra and graphs",
        "1",
        "Draws a parabola with its roots, discriminant, vertex, axis of symmetry and "
        "completed square form.",
    ),
    PrimitiveInfo(
        "InequalityRegion",
        "Algebra and graphs",
        "1",
        "Shades the regions of linear inequalities in x and y and labels the region R that "
        "satisfies them all.",
    ),
    PrimitiveInfo(
        "SequencePattern",
        "Algebra and graphs",
        "1",
        "Finds the nth term of a linear, quadratic, cubic or geometric sequence from its "
        "differences or ratio.",
    ),
    PrimitiveInfo(
        "ProportionGraph",
        "Algebra and graphs",
        "1",
        "Turns direct or inverse proportion into y = kx^n, finds k from a known pair and "
        "uses the rule.",
    ),
    PrimitiveInfo(
        "CurveSketch",
        "Algebra and graphs",
        "1",
        "Sketches a curve and labels its intercepts, turning points (maximum or minimum) "
        "and asymptotes.",
    ),
    PrimitiveInfo(
        "FunctionMachine",
        "Functions and graphs",
        "1",
        "Shows a function as a machine of operations, traces values through it and runs "
        "it backwards for the inverse.",
    ),
    PrimitiveInfo(
        "GraphicalSolution",
        "Functions and graphs",
        "1",
        "Solves f(x) = g(x) by drawing both graphs and reading off the x-coordinates "
        "where they meet.",
    ),
    PrimitiveInfo(
        "CoordinatePlotter",
        "Coordinate geometry",
        "1",
        "Plots two points and finds the midpoint and the length of the segment joining them.",
    ),
    PrimitiveInfo(
        "LineBuilder",
        "Coordinate geometry",
        "1",
        "Builds y = mx + c from the y-intercept and a gradient step, and rearranges it "
        "to ax + by = c.",
    ),
    PrimitiveInfo(
        "ParallelPerpendicular",
        "Coordinate geometry",
        "1",
        "Finds the line through a point parallel or perpendicular to a line, or the "
        "perpendicular bisector of AB.",
    ),
    PrimitiveInfo(
        "DerivativePanels",
        "Introductory calculus",
        "1",
        "Shows y = f(x) above its gradient function, with a linked cursor, rising and "
        "falling parts and stationary points.",
    ),
    PrimitiveInfo(
        "DifferentiationStepper",
        "Introductory calculus",
        "1",
        "Works a derivative line by line with the power, chain, product or quotient rule.",
    ),
    PrimitiveInfo(
        "TangentNormal",
        "Introductory calculus",
        "1",
        "Draws the tangent and the normal to a curve at a point and finds their equations.",
    ),
    PrimitiveInfo(
        "AreaBetweenCurves",
        "Introductory calculus",
        "1",
        "Finds the area between two graphs as the integral of upper minus lower, shown "
        "as thin strips.",
    ),
    PrimitiveInfo(
        "KinematicsGraphs",
        "Travel graphs and kinematics",
        "1",
        "Stacks displacement, velocity and acceleration against time beside a moving "
        "particle; marks when it is at rest.",
    ),
    PrimitiveInfo(
        "OptimisationScene",
        "Introductory calculus",
        "1",
        "Solves a practical maximum or minimum (open box, fencing, rectangle, cylinder) "
        "with the model beside its graph.",
    ),
    PrimitiveInfo(
        "CoordinateCircle",
        "Coordinate geometry",
        "1",
        "Draws the circle (x - a)^2 + (y - b)^2 = r^2 and finds where a line cuts it, "
        "touches it or misses it.",
    ),
]

PRIMITIVE_IDS = frozenset(info.primitive_id for info in CATALOGUE)
