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
    PrimitiveInfo(
        "TreeDiagram",
        "Probability",
        "1",
        "Probability trees: multiply along the branches, add the outcomes wanted, with "
        "or without replacement",
    ),
    PrimitiveInfo(
        "SampleSpaceGrid",
        "Probability",
        "1",
        "The possibility diagram for two events, the wanted outcomes marked, P = wanted over total",
    ),
    PrimitiveInfo(
        "ProbabilitySpinner",
        "Probability",
        "1",
        "Probability from a spinner of equal sectors, on the 0 to 1 scale, its "
        "complement and expected frequency",
    ),
    PrimitiveInfo(
        "ChartBuilder",
        "Statistics",
        "1",
        "Bar charts, pie charts with the angles worked out, and stem-and-leaf diagrams with a key",
    ),
    PrimitiveInfo(
        "AveragesVisualizer",
        "Statistics",
        "1",
        "Mean, median, mode and range from a list, a frequency table or grouped data",
    ),
    PrimitiveInfo(
        "ScatterBestFit",
        "Statistics",
        "1",
        "Scatter graphs: correlation, the line of best fit through the mean point, and estimates",
    ),
    PrimitiveInfo(
        "CumulativeFrequency",
        "Statistics",
        "1",
        "The cumulative frequency curve: median, quartiles and interquartile range read from it",
    ),
    PrimitiveInfo(
        "Histogram",
        "Statistics",
        "1",
        "Histograms with unequal widths: frequency density, bar areas and an estimate in a range",
    ),
    PrimitiveInfo(
        "TransformationStage",
        "Transformations",
        "1",
        "Reflection, rotation, translation and enlargement on a grid, moved and described in full",
    ),
    PrimitiveInfo(
        "VectorArena",
        "Vectors",
        "1",
        "Column vectors, magnitude, adding by the triangle law, multiples and vector geometry",
    ),
    PrimitiveInfo(
        "Trig3D",
        "Trigonometry",
        "1",
        "Lengths and angles in 3D from right-angled triangles in a cuboid or a pyramid",
    ),
]

PRIMITIVE_IDS = frozenset(info.primitive_id for info in CATALOGUE)

# The syllabus codes each primitive draws: 4024 unless marked AM (4037), as listed in
# docs/primitives.md. A lesson planner can match a learner's topic to primitives by them.
SYLLABUS: dict[str, str] = {
    "AlgebraBalance": "2.1–2.3, 2.5",
    "AngleChaser": "4.6.1, 4.6.2",
    "AreaBetweenCurves": "AM 14.10–14.13",
    "AreaDissector": "5.2",
    "AreaUnderCurve": "AM 14.10–14.13",
    "AveragesVisualizer": "9.2, 9.3",
    "Bearings": "4.3",
    "BoundsInterval": "1.10",
    "ChartBuilder": "9.1, 9.4",
    "CircleSector": "5.3; AM 9",
    "CircleTheorems": "4.7, 4.8",
    "ClockTimetable": "1.15, 1.16",
    "CompassConstruction": "4.2",
    "CompletingSquare": "2.5.5; AM 2",
    "ConnectedRates": "AM 14.7",
    "CoordinateCircle": "AM 8.1–8.4",
    "CoordinatePlotter": "3.1, 3.4",
    "CumulativeFrequency": "9.6",
    "CurveSketch": "2.11; AM 4.4",
    "DerivativePanels": "AM 14.6, 14.9",
    "DifferentiationStepper": "AM 14.3, 14.4",
    "EquationTransform": "2.1–2.5; all topics",
    "ExpansionGrid": "2.2, 2.5.5",
    "FractionModel": "1.4, 1.6",
    "FunctionGraph": "2.10",
    "FunctionMachine": "2.12; AM 1",
    "GradientTriangle": "3.3",
    "GraphicalSolution": "2.10",
    "GrowthDecay": "1.13.4, 1.17",
    "Histogram": "9.7",
    "IndexLaws": "1.7, 2.4",
    "InequalityRegion": "2.6",
    "InverseGraph": "2.12; AM 1",
    "KinematicsGraphs": "AM 14.14, 14.15",
    "LineBuilder": "3.2, 3.3, 3.5",
    "NetFolder": "4.1, 4.2.3",
    "NumberLine": "1.1, 1.4, 1.5, 1.9, 1.10",
    "OptimisationScene": "AM 14.8",
    "ParallelPerpendicular": "3.6, 3.7; AM 7",
    "PercentageBar": "1.13",
    "PolygonAngles": "4.6.3",
    "PrimeFactorTree": "1.1",
    "ProbabilitySpinner": "8.1, 8.2",
    "ProportionGraph": "2.8",
    "QuadraticExplorer": "2.5.5, 2.11",
    "RatioSplitter": "1.11, 1.12",
    "RightTriangleTrig": "6.1, 6.2",
    "SampleSpaceGrid": "8.1, 8.3",
    "ScatterBestFit": "9.5",
    "SecantToTangent": "AM 14.1; 2.10.4",
    "SequencePattern": "2.7",
    "SimilarityScaler": "4.4",
    "SimultaneousEquations": "2.5",
    "SineCosineRule": "6.3",
    "SolidMensuration": "5.1, 5.4, 5.5",
    "StandardForm": "1.7, 1.8",
    "SurdSimplifier": "1.18",
    "SymmetryReveal": "4.5",
    "TableOfValues": "2.10",
    "TangentNormal": "AM 14.5",
    "TangentSlide": "AM 14.1–14.5",
    "TransformationStage": "7.1",
    "TravelGraph": "2.9.3, 2.9.4",
    "TreeDiagram": "8.3",
    "Trig3D": "6.4",
    "UnitCircleWaves": "AM 10.2, 10.3",
    "VectorArena": "7.2–7.4; AM 13",
    "VennDiagram": "1.2; 8.3",
}
