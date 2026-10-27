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
    PrimitiveInfo(
        "GrowthDecay",
        "Number",
        "1",
        "Shows compound growth or decay year by year on an exponential curve, against "
        "simple interest.",
    ),
    PrimitiveInfo(
        "UnitCircleWaves",
        "Trigonometry",
        "1",
        "Generates sine or cosine from a radius turning round the unit circle, then "
        "shows y = a sin(bx) + c.",
    ),
    PrimitiveInfo(
        "ConnectedRates",
        "Introductory calculus",
        "1",
        "Links the rate a shape's size changes to the rate its area or volume changes, "
        "with the chain rule.",
    ),
    PrimitiveInfo(
        "InverseGraph",
        "Functions and graphs",
        "1",
        "Reflects a one-to-one function in y = x to give its inverse, and finds the "
        "inverse's formula.",
    ),
    PrimitiveInfo(
        "SimultaneousEquations",
        "Algebra and graphs",
        "1",
        "Solves two simultaneous equations by elimination or by substitution, including "
        "a linear and a quadratic.",
    ),
    PrimitiveInfo(
        "TableOfValues",
        "Functions and graphs",
        "1",
        "Completes a table of values for y = f(x), plots the points and joins them with "
        "a smooth curve.",
    ),
    PrimitiveInfo(
        "NumberLine",
        "Number",
        "1",
        "Places numbers in order on a number line and shows an inequality as an interval "
        "with open or closed circles.",
    ),
    PrimitiveInfo(
        "PrimeFactorTree",
        "Number",
        "1",
        "Splits numbers into primes with factor trees, writes them in index form, and "
        "finds the HCF and LCM from a Venn diagram.",
    ),
    PrimitiveInfo(
        "VennDiagram",
        "Number",
        "1",
        "Draws two or three sets in a Venn diagram, places elements or counts, and "
        "shades and counts a region in set notation.",
    ),
    PrimitiveInfo(
        "FractionModel",
        "Number",
        "1",
        "Shows fractions as bars and grids: equivalent fractions, adding, subtracting, "
        "multiplying and dividing.",
    ),
    PrimitiveInfo(
        "PercentageBar",
        "Number",
        "1",
        "Shows percentages as bars: a percentage of an amount, increase and decrease, "
        "reverse percentage and percentage change.",
    ),
    PrimitiveInfo(
        "StandardForm",
        "Number",
        "1",
        "Writes a number in standard form by moving the decimal point place by place, "
        "and multiplies or divides in standard form.",
    ),
    PrimitiveInfo(
        "IndexLaws",
        "Number",
        "1",
        "Simplify with the laws of indices, each step labelled with the law it uses",
    ),
    PrimitiveInfo(
        "SurdSimplifier",
        "Number",
        "1",
        "Surds simplified with the largest square factor, collected, and denominators rationalised",
    ),
    PrimitiveInfo(
        "RatioSplitter",
        "Number",
        "1",
        "Sharing in a ratio with a bar model: one unit from what is known, then each share",
    ),
    PrimitiveInfo(
        "BoundsInterval",
        "Number",
        "1",
        "Upper and lower bounds on a zoomed number line, and the bounds of a calculation",
    ),
    PrimitiveInfo(
        "ClockTimetable",
        "Number",
        "1",
        "12- and 24-hour clock times, time intervals by counting on, timetables and "
        "currency exchange",
    ),
    PrimitiveInfo(
        "AngleChaser",
        "Geometry",
        "1",
        "Unknown angles from the angle facts: lines, points, parallel lines and triangles",
    ),
    PrimitiveInfo(
        "PolygonAngles",
        "Geometry",
        "1",
        "Interior angle sums by triangles, exterior angles as one turn, and sides from an angle",
    ),
    PrimitiveInfo(
        "CircleTheorems",
        "Geometry",
        "1",
        "The circle theorems drawn true to size, the unknown angle found and the theorem named",
    ),
    PrimitiveInfo(
        "RightTriangleTrig",
        "Trigonometry",
        "1",
        "Pythagoras or SOH CAH TOA in a right-angled triangle, the method chosen from "
        "what is known",
    ),
    PrimitiveInfo(
        "SineCosineRule",
        "Trigonometry",
        "1",
        "The sine rule, the cosine rule or the area formula, chosen from what is known",
    ),
    PrimitiveInfo(
        "CircleSector",
        "Mensuration",
        "1",
        "Arc length, sector area and perimeter, segment area and the angle, in degrees or radians",
    ),
    PrimitiveInfo(
        "SolidMensuration",
        "Mensuration",
        "1",
        "Volume and surface area of prisms, cylinders, cones, pyramids and spheres",
    ),
    PrimitiveInfo(
        "Bearings",
        "Geometry",
        "1",
        "Three-figure bearings from north, back bearings, and the east and north parts "
        "of a journey",
    ),
    PrimitiveInfo(
        "SimilarityScaler",
        "Geometry",
        "1",
        "Similar shapes: the scale factor, a missing length, and areas by k squared and "
        "volumes by k cubed",
    ),
    PrimitiveInfo(
        "SymmetryReveal",
        "Geometry",
        "1",
        "Lines of symmetry and the order of rotational symmetry, found from the vertices",
    ),
    PrimitiveInfo(
        "AreaDissector",
        "Mensuration",
        "1",
        "Area formulas by cutting and moving pieces: parallelogram, triangle and trapezium",
    ),
    PrimitiveInfo(
        "NetFolder",
        "Geometry",
        "1",
        "The net of a solid face by face, its faces, edges and vertices, and its surface area",
    ),
    PrimitiveInfo(
        "CompassConstruction",
        "Geometry",
        "1",
        "Ruler-and-compasses constructions arc by arc: bisectors and a triangle from three sides",
    ),
]

PRIMITIVE_IDS = frozenset(info.primitive_id for info in CATALOGUE)
