"""The stub's seed data: topics, glossary, item bank, primitives, accounts.

All of it is sample data for building the frontend (docs/frontend.md §8). The syllabus codes are
placeholders until the concept taxonomy is written (Phase 3). The accounts exist only in the
stub and are reset whenever the server restarts.
"""

from dataclasses import dataclass

# Topic areas in the order of the progress wireframe (Fig. 4.6).
TOPIC_AREAS = [
    "Functions and graphs",
    "Coordinate geometry",
    "Travel graphs",
    "Differentiation",
    "Integration",
]


@dataclass(frozen=True)
class ConceptSeed:
    id: int
    name: str
    syllabus_code: str
    topic_area: str


# Concept 12 is the one the example module teaches (backend/examples/gradient_of_line.*).
CONCEPTS = [
    ConceptSeed(1, "Function notation", "FG.1", "Functions and graphs"),
    ConceptSeed(2, "Graphs of linear functions", "FG.2", "Functions and graphs"),
    ConceptSeed(3, "Graphs of quadratic functions", "FG.3", "Functions and graphs"),
    ConceptSeed(10, "Coordinates of points", "CG.1", "Coordinate geometry"),
    ConceptSeed(11, "Length and midpoint of a line segment", "CG.2", "Coordinate geometry"),
    ConceptSeed(12, "Gradient of a straight line", "CG.3", "Coordinate geometry"),
    ConceptSeed(13, "Equation of a straight line", "CG.4", "Coordinate geometry"),
    ConceptSeed(14, "Parallel lines", "CG.5", "Coordinate geometry"),
    ConceptSeed(20, "Distance–time graphs", "TG.1", "Travel graphs"),
    ConceptSeed(21, "Speed–time graphs", "TG.2", "Travel graphs"),
    ConceptSeed(30, "Gradient of a curve", "DF.1", "Differentiation"),
    ConceptSeed(31, "Differentiating powers of x", "DF.2", "Differentiation"),
    ConceptSeed(32, "Stationary points", "DF.3", "Differentiation"),
    ConceptSeed(40, "Integration as reverse differentiation", "IN.1", "Integration"),
    ConceptSeed(41, "Area under a curve", "IN.2", "Integration"),
]

# (id, concept id, term, definition). Covers every chip in the fixture manifests.
GLOSSARY = [
    (
        1,
        2,
        "graph",
        "A picture of how two quantities are related, drawn on axes. Every point $(x, y)$ "
        "on the graph fits its equation.",
    ),
    (
        2,
        10,
        "coordinates",
        "A pair of numbers $(x, y)$ giving the position of a point: $x$ across, then $y$ up.",
    ),
    (
        3,
        12,
        "gradient",
        "How steep a line is: the change in $y$ divided by the change in $x$, "
        "$m = \\frac{y_2 - y_1}{x_2 - x_1}$.",
    ),
    (4, 12, "rise", "How far a line goes up (the change in $y$) between two of its points."),
    (5, 12, "run", "How far a line goes across (the change in $x$) between two of its points."),
    (
        6,
        13,
        "y-intercept",
        "Where a line crosses the $y$-axis. For $y = mx + c$ it is the point $(0, c)$.",
    ),
    (
        7,
        30,
        "tangent",
        "A straight line that just touches a curve at one point and has the same gradient as "
        "the curve there.",
    ),
    (8, 10, "point", "An exact position, given by its coordinates $(x, y)$."),
    (
        9,
        31,
        "derivative",
        "The gradient function of a curve. For $y = x^n$ it is $\\frac{dy}{dx} = nx^{n-1}$.",
    ),
    (
        10,
        20,
        "speed",
        "Distance travelled per unit of time. On a distance–time graph it is the gradient.",
    ),
    (
        11,
        41,
        "area under a curve",
        "The area between a curve and the $x$-axis, found by integration.",
    ),
    (12, 14, "parallel", "Lines that never meet. Parallel lines have the same gradient."),
    (13, 32, "stationary point", "A point on a curve where the gradient is $0$."),
]


@dataclass(frozen=True)
class ItemSeed:
    id: int
    concept_id: int
    item_type: str
    question_text: str
    options: list[str]
    correct_option: str


TF = ["True", "False"]

ITEMS = [
    ItemSeed(1, 12, "true_false", "A line with a gradient of $0$ is horizontal.", TF, "True"),
    ItemSeed(
        2,
        12,
        "mcq",
        "What is the gradient of the line through $(1, 2)$ and $(4, 8)$?",
        ["$2$", "$\\frac{1}{2}$", "$6$", "$3$"],
        "$2$",
    ),
    ItemSeed(
        3,
        12,
        "mcq",
        "A line rises 6 units for every 3 units it runs to the right. What is its gradient?",
        ["$2$", "$3$", "$\\frac{1}{2}$", "$18$"],
        "$2$",
    ),
    ItemSeed(
        4,
        12,
        "true_false",
        "The gradient of a straight line is different at different points on the line.",
        TF,
        "False",
    ),
    ItemSeed(
        5,
        13,
        "mcq",
        "What is the gradient of the line $y = 2x + 3$?",
        ["$2$", "$3$", "$2x$", "$x + 3$"],
        "$2$",
    ),
    ItemSeed(
        6,
        13,
        "mcq",
        "Where does the line $y = 2x + 3$ cross the $y$-axis?",
        ["$(0, 3)$", "$(3, 0)$", "$(0, 2)$", "$(2, 3)$"],
        "$(0, 3)$",
    ),
    ItemSeed(
        7, 14, "true_false", "The lines $y = 3x + 1$ and $y = 3x - 4$ are parallel.", TF, "True"
    ),
    ItemSeed(
        8,
        1,
        "mcq",
        "If $f(x) = 3x - 1$, what is $f(2)$?",
        ["$5$", "$6$", "$7$", "$1$"],
        "$5$",
    ),
    ItemSeed(9, 3, "true_false", "The graph of $y = x^2$ is a straight line.", TF, "False"),
    ItemSeed(
        10,
        20,
        "mcq",
        "On a distance–time graph, what does the gradient show?",
        ["Speed", "Distance", "Time", "Acceleration"],
        "Speed",
    ),
    ItemSeed(
        11,
        21,
        "true_false",
        "The area under a speed–time graph gives the distance travelled.",
        TF,
        "True",
    ),
    ItemSeed(
        12,
        30,
        "true_false",
        "The tangent to a curve at a point has the same gradient as the curve at that point.",
        TF,
        "True",
    ),
    ItemSeed(
        13,
        31,
        "mcq",
        "What is $\\frac{d}{dx}(x^3)$?",
        ["$3x^2$", "$x^2$", "$3x^3$", "$\\frac{x^4}{4}$"],
        "$3x^2$",
    ),
    ItemSeed(
        14, 32, "true_false", "At a stationary point, the gradient of the curve is $0$.", TF, "True"
    ),
    ItemSeed(
        15,
        41,
        "mcq",
        "What is $\\int_0^2 x \\, dx$?",
        ["$2$", "$4$", "$1$", "$\\frac{1}{2}$"],
        "$2$",
    ),
    ItemSeed(
        16,
        11,
        "mcq",
        "What is the midpoint of $(2, 4)$ and $(6, 8)$?",
        ["$(4, 6)$", "$(8, 12)$", "$(4, 4)$", "$(2, 2)$"],
        "$(4, 6)$",
    ),
    ItemSeed(
        17,
        12,
        "mcq",
        "Which line is the steepest?",
        ["$y = 3x + 1$", "$y = x + 5$", "$y = \\frac{1}{2}x$", "$y = 2$"],
        "$y = 3x + 1$",
    ),
    ItemSeed(18, 13, "true_false", "In $y = mx + c$, the number $c$ is the gradient.", TF, "False"),
]

# The onboarding diagnostic: one item per topic area, at most five (UC 4.2). The third is the
# question of the wireframe (Fig. 4.1).
DIAGNOSTIC_ITEMS = [8, 16, 5, 10, 12]

# Mirrors app/primitives/library.py, which needs Manim to import; a test keeps them in step.
PRIMITIVES = [
    (
        "FunctionGraph",
        "Functions and graphs",
        "1",
        "Draws the graph of a function on labelled axes and marks points on it.",
    ),
    (
        "GradientTriangle",
        "Coordinate geometry",
        "1",
        "Draws the rise and run between two points of a line and computes its gradient.",
    ),
    (
        "EquationTransform",
        "All topics",
        "1",
        "Shows an expression being simplified step by step, highlighting what changes.",
    ),
]

STUB_PASSWORD = "password123"

# (email, name, role); every account's password is STUB_PASSWORD.
ACCOUNTS = [
    ("student@fourierlearn.test", "Test Student", "student"),
    ("new@fourierlearn.test", "New Student", "student"),
    ("admin@fourierlearn.test", "Admin", "admin"),
]

# Extra students for the admin pages: (name, days since joining, lessons, disabled).
SAMPLE_STUDENTS = [
    ("Ayesha Khan", 40, 6, False),
    ("Bilal Ahmed", 35, 3, False),
    ("Fatima Noor", 30, 9, False),
    ("Hamza Ali", 28, 1, False),
    ("Zainab Raza", 21, 4, False),
    ("Usman Tariq", 14, 0, True),
    ("Maryam Iqbal", 10, 2, False),
    ("Ali Hassan", 7, 5, False),
    ("Hira Shah", 3, 1, False),
    ("Omar Farooq", 1, 0, False),
]

# Scores of the seeded student, per topic area, as in the progress wireframe (Fig. 4.6).
SEEDED_AREA_SCORES = {
    "Functions and graphs": 0.85,
    "Coordinate geometry": 0.70,
    "Travel graphs": 0.55,
    "Differentiation": 0.40,
    "Integration": 0.25,
}

DEFAULT_PRIOR = 0.3
"""Every concept's score before any evidence (the stub's P(L0))."""

RENDER_ERRORS = [
    "LayoutViolation: label 'B' overlaps 'line' after step 3 of beat 1",
    "InvalidParameters: beat 0 (FunctionGraph): domain: x range must contain the marked points",
    "TTSError: kokoro failed: input text is empty",
]
