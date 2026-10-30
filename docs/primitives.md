# Writing a primitive

A visual primitive is a parameterised Manim CE component that draws one type of mathematical
visual (report §5.3.1). Manim code is written only in primitives, before deployment. At runtime
a language model chooses a primitive and fills in its parameters, and nothing else (§5.3).

The library started with the seven primitives of Table 5.2 and now covers the Cambridge O Level
Mathematics (4024) syllabus and the calculus of Additional Mathematics (4037 Unit 14), with the
4037 topics that build on it, and the whole of Cambridge International AS & A Level Mathematics
(9709): 105 primitives. [docs/primitive-coverage.md](primitive-coverage.md) maps every visual the syllabus
needs to the primitive that draws it. Lessons combine primitives: a graph primitive on the left
of the frame with a working primitive (`EquationTransform`, `AlgebraBalance`) on the right.

### Table 5.2

| Primitive           | Topic                        | What it shows                                                   | File                                           |
| ------------------- | ---------------------------- | --------------------------------------------------------------- | ---------------------------------------------- |
| `FunctionGraph`     | Functions and graphs         | The graph of f on labelled axes, with marked points             | `backend/app/primitives/function_graph.py`     |
| `GradientTriangle`  | Coordinate geometry          | Rise and run between two points; gradient = rise / run          | `backend/app/primitives/gradient_triangle.py`  |
| `TangentSlide`      | Introductory calculus        | A tangent sliding along a curve, with its gradient read out     | `backend/app/primitives/tangent_slide.py`      |
| `SecantToTangent`   | Introductory calculus        | Secants PQ approaching the tangent at P as h shrinks            | `backend/app/primitives/secant_to_tangent.py`  |
| `TravelGraph`       | Travel graphs and kinematics | Distance-time or speed-time graph; gradients or areas explained | `backend/app/primitives/travel_graph.py`       |
| `AreaUnderCurve`    | Introductory calculus        | The area under a curve between two limits, by integration       | `backend/app/primitives/area_under_curve.py`   |
| `EquationTransform` | All topics                   | A derivation step by step, changed terms highlighted            | `backend/app/primitives/equation_transform.py` |

### Algebra and graphs (4024 Unit 2)

| Primitive               | Syllabus     | What it shows                                                                               |
| ----------------------- | ------------ | ------------------------------------------------------------------------------------------- |
| `AlgebraBalance`        | 2.1–2.3, 2.5 | Solving an equation or changing the subject by doing the same to both sides                 |
| `ExpansionGrid`         | 2.2, 2.5.5   | Expanding brackets or factorising with a grid (area) model                                  |
| `CompletingSquare`      | 2.5.5; AM 2  | Completing the square as an area, with the missing corner                                   |
| `QuadraticExplorer`     | 2.5.5, 2.11  | A parabola's roots, discriminant, vertex, axis of symmetry and completed form; inequalities |
| `InequalityRegion`      | 2.6          | Regions of linear inequalities, unwanted side shaded, region R labelled                     |
| `SequencePattern`       | 2.7          | The nth term from differences or a ratio, with optional dot patterns                        |
| `ProportionGraph`       | 2.8          | Direct and inverse proportion: y = kxⁿ, k from a known pair                                 |
| `CurveSketch`           | 2.11; AM 4.4 | A sketched curve with intercepts, turning points and asymptotes                             |
| `FunctionMachine`       | 2.12; AM 1   | A function as a machine, values traced through it, and its inverse                          |
| `GraphicalSolution`     | 2.10         | Solving f(x) = g(x) by reading where two graphs meet                                        |
| `SimultaneousEquations` | 2.5          | Two equations solved by elimination or substitution, line by line                           |
| `TableOfValues`         | 2.10         | A table of values filled in, then the points plotted and joined                             |
| `InverseGraph`          | 2.12; AM 1   | f and f⁻¹ as reflections in y = x, with a point and its image                               |

### Text on screen (all topics)

| Primitive  | Syllabus   | What it shows                                                                       |
| ---------- | ---------- | ----------------------------------------------------------------------------------- |
| `TextCard` | all topics | A topic heading, a question in the learner's own words, or key points one at a time |

Maths goes between dollar signs (`"Solve $2x + 3 = 7$"`); a dollar sign for money is written
`\$`. The text comes from the language model, so it is checked before it reaches LaTeX: outside
the maths only plain words and punctuation, inside it only a known list of commands with
balanced braces (`\frac`, `\sqrt`, `\theta`, `\le`, ...); anything else, such as `\input`, is
refused. `place: "side"` puts the card in the working region, so a question stays in view while
a graph primitive solves it on the left.

### Number (4024 Unit 1)

| Primitive         | Syllabus                 | What it shows                                                          |
| ----------------- | ------------------------ | ---------------------------------------------------------------------- |
| `NumberLine`      | 1.1, 1.4, 1.5, 1.9, 1.10 | Numbers, intervals and inequalities on a line, open and closed circles |
| `PrimeFactorTree` | 1.1                      | A factor tree, index form, and HCF and LCM from a Venn diagram         |
| `VennDiagram`     | 1.2; 8.3                 | Sets as elements or counts, with a set expression shaded               |
| `FractionModel`   | 1.4, 1.6                 | Fractions as bars and area models: equivalence and the four operations |
| `GrowthDecay`     | 1.13.4, 1.17             | Compound interest, growth and decay as a table of years and a curve    |
| `PercentageBar`   | 1.13                     | Percentages as bars: of an amount, increase, decrease, reverse, change |
| `StandardForm`    | 1.7, 1.8                 | A number written as A × 10ⁿ by hopping the decimal point; × and ÷      |
| `IndexLaws`       | 1.7, 2.4                 | An expression simplified one index law at a time, each law shown       |
| `SurdSimplifier`  | 1.18                     | Surds simplified, collected, and denominators rationalised             |
| `RatioSplitter`   | 1.11, 1.12               | Sharing in a ratio with a bar model; simplifying a ratio               |
| `BoundsInterval`  | 1.10                     | Upper and lower bounds on a number line, and bounds of a calculation   |
| `ClockTimetable`  | 1.15, 1.16               | Clock times, intervals by counting on, timetables, currency exchange   |

### Geometry (4024 Unit 4)

| Primitive             | Syllabus     | What it shows                                                                           |
| --------------------- | ------------ | --------------------------------------------------------------------------------------- |
| `AngleChaser`         | 4.6.1, 4.6.2 | Unknown angles from the angle facts: lines, points, parallel lines, triangles           |
| `PolygonAngles`       | 4.6.3        | Interior angle sums by triangles, exterior angles as one turn, sides from an angle      |
| `CircleTheorems`      | 4.7, 4.8     | The circle theorems drawn true to size, the unknown angle found and named               |
| `SimilarityScaler`    | 4.4          | Similar shapes: the scale factor, a missing length, areas by k² and volumes by k³       |
| `Bearings`            | 4.3          | Three-figure bearings from north, back bearings, east and north parts of a journey      |
| `SymmetryReveal`      | 4.5          | Lines of symmetry and the order of rotational symmetry, found from the vertices         |
| `NetFolder`           | 4.1, 4.2.3   | The net of a solid face by face, its faces, edges and vertices, its surface area        |
| `CompassConstruction` | 4.2          | Ruler-and-compasses constructions arc by arc: bisectors and a triangle from three sides |

### Mensuration (4024 Unit 5)

| Primitive          | Syllabus      | What it shows                                                                         |
| ------------------ | ------------- | ------------------------------------------------------------------------------------- |
| `AreaDissector`    | 5.2           | Area formulas by cutting and moving pieces: parallelogram, triangle, trapezium        |
| `CircleSector`     | 5.3; AM 9     | Arc length, sector area and perimeter, segment area and the angle, degrees or radians |
| `SolidMensuration` | 5.1, 5.4, 5.5 | Volume and surface area of prisms, cylinders, cones, pyramids and spheres             |

### Coordinate geometry (4024 Unit 3)

| Primitive               | Syllabus       | What it shows                                                                   |
| ----------------------- | -------------- | ------------------------------------------------------------------------------- |
| `CoordinatePlotter`     | 3.1, 3.4       | Two points, the midpoint, and the length from the right-angled triangle         |
| `LineBuilder`           | 3.2, 3.3, 3.5  | y = mx + c from the y-intercept and a gradient step; the form ax + by = c       |
| `ParallelPerpendicular` | 3.6, 3.7; AM 7 | The parallel or perpendicular line through a point; the perpendicular bisector  |
| `CoordinateCircle`      | AM 8.1–8.4     | The circle (x − a)² + (y − b)² = r² and where a line cuts, touches or misses it |

### Transformations and vectors (4024 Unit 7)

| Primitive             | Syllabus       | What it shows                                                                  |
| --------------------- | -------------- | ------------------------------------------------------------------------------ |
| `TransformationStage` | 7.1            | Reflection, rotation, translation and enlargement on a grid, described in full |
| `VectorArena`         | 7.2–7.4; AM 13 | Column vectors, magnitude, the triangle law, multiples and vector geometry     |

### Probability (4024 Unit 8)

| Primitive            | Syllabus | What it shows                                                                 |
| -------------------- | -------- | ----------------------------------------------------------------------------- |
| `ProbabilitySpinner` | 8.1, 8.2 | Probability from a spinner, the 0 to 1 scale, P(not A) and expected frequency |
| `TreeDiagram`        | 8.3      | Tree diagrams with or without replacement: multiply along, add the paths      |
| `SampleSpaceGrid`    | 8.1, 8.3 | The possibility diagram for two events, wanted outcomes marked                |

### Statistics (4024 Unit 9)

| Primitive             | Syllabus | What it shows                                                                       |
| --------------------- | -------- | ----------------------------------------------------------------------------------- |
| `ChartBuilder`        | 9.1, 9.4 | Bar charts, pie charts with the angles worked out, stem-and-leaf diagrams           |
| `AveragesVisualizer`  | 9.2, 9.3 | Mean, median, mode and range from a list, a frequency table or grouped data         |
| `ScatterBestFit`      | 9.5      | Scatter graphs: correlation, the line of best fit through the mean point, estimates |
| `CumulativeFrequency` | 9.6      | The cumulative frequency curve: median, quartiles and interquartile range           |
| `Histogram`           | 9.7      | Histograms with unequal widths: frequency density and estimates from areas          |

### Calculus and kinematics (4037 Unit 14)

| Primitive                | Syllabus        | What it shows                                                          |
| ------------------------ | --------------- | ---------------------------------------------------------------------- |
| `DerivativePanels`       | AM 14.6, 14.9   | f above f′ with a linked cursor; rising, falling and stationary points |
| `DifferentiationStepper` | AM 14.3, 14.4   | The power, chain, product and quotient rules, line by line             |
| `TangentNormal`          | AM 14.5         | The tangent and the normal at a point, with their equations            |
| `AreaBetweenCurves`      | AM 14.10–14.13  | The area between two graphs as the integral of upper minus lower       |
| `KinematicsGraphs`       | AM 14.14, 14.15 | s, v and a against t beside a moving particle; when it is at rest      |
| `OptimisationScene`      | AM 14.8         | A practical maximum or minimum with the model beside its graph         |
| `ConnectedRates`         | AM 14.7         | dA/dt = dA/dr × dr/dt for a growing circle, square, sphere or cube     |

### Trigonometry (4024 Unit 6; 4037 Unit 10)

| Primitive           | Syllabus      | What it shows                                                               |
| ------------------- | ------------- | --------------------------------------------------------------------------- |
| `RightTriangleTrig` | 6.1, 6.2      | Pythagoras or SOH CAH TOA, the method chosen from what is known             |
| `SineCosineRule`    | 6.3           | The sine rule, the cosine rule or ½ab sin C, chosen from what is known      |
| `Trig3D`            | 6.4           | Lengths and angles in 3D from right-angled triangles in a cuboid or pyramid |
| `UnitCircleWaves`   | AM 10.2, 10.3 | A point turning round the unit circle tracing y = a sin(bx) + c             |

### AS & A Level: Pure Mathematics (9709 Papers 1, 2 and 3)

| Primitive              | Syllabus      | What it shows                                                                    |
| ---------------------- | ------------- | -------------------------------------------------------------------------------- |
| `GraphTransform`       | 1.2           | y = af(bx + c) + d built from y = f(x) one transformation at a time              |
| `FunctionMapping`      | 1.2           | Domain, range, one-one test, composite and inverse functions, with y = x         |
| `LineMeetsCurve`       | 1.1, 1.3      | A line meeting a curve: the discriminant decides two, one (tangent) or no points |
| `TrigEquationSolver`   | 1.5, 2.3, 3.3 | Every solution of a trigonometric equation in an interval, read from the graph   |
| `BinomialExpansion`    | 1.6, 3.1      | (a + bx)ⁿ term by term, and the series for any n with its validity               |
| `Progression`          | 1.6           | Arithmetic and geometric progressions, sums, and the sum to infinity             |
| `AntiderivativeFamily` | 1.8           | The family y = F(x) + c, and the member through a given point                    |
| `VolumeOfRevolution`   | 1.8           | The solid swept by rotating a region about an axis, V = π∫y² dx                  |
| `ModulusEquation`      | 2.1, 3.1      | Modulus equations and inequalities from the graphs of both sides                 |
| `PolynomialDivision`   | 2.1, 3.1      | Long division of polynomials; the factor and remainder theorems                  |
| `PartialFractions`     | 3.1, 3.5      | Partial fractions for distinct, repeated and quadratic factors                   |
| `LogLinearisation`     | 2.2, 3.2      | y = axⁿ or y = abˣ made a straight line by logarithms, constants read off        |
| `HarmonicForm`         | 2.3, 3.3      | a sin θ + b cos θ as R sin(θ ± α) or R cos(θ ± α), its maximum and equations     |
| `TrapeziumRule`        | 2.5, 3.5      | The trapezium rule with its strips, and whether it over- or under-estimates      |
| `IterationDiagram`     | 2.6, 3.6      | A sign-change interval and the staircase or cobweb of xₙ₊₁ = F(xₙ)               |
| `ParametricCurve`      | 2.4, 3.4      | A curve traced by (x(t), y(t)), with dy/dx = (dy/dt)/(dx/dt) at a point          |
| `ImplicitCurve`        | 2.4, 3.4      | An implicit curve, implicit differentiation and the tangent at a point           |
| `IntegrationMethod`    | 3.5           | Integration by parts, by substitution, or to a logarithm, checked by derivative  |
| `DifferentialEquation` | 3.8           | A separable differential equation solved, with its slope field and solution      |
| `VectorLines3D`        | 3.7           | Two lines in 3D: parallel, intersecting or skew, and the angle between them      |
| `ArgandDiagram`        | 3.9           | Complex numbers on the Argand diagram: arithmetic, modulus and argument          |
| `ComplexLoci`          | 3.9           | Loci (circles, bisectors, half-lines) and the regions they bound                 |

### AS & A Level: Mechanics (9709 Paper 4)

| Primitive            | Syllabus | What it shows                                                                 |
| -------------------- | -------- | ----------------------------------------------------------------------------- |
| `ForceDiagram`       | 4.1, 4.4 | Forces resolved along and across a surface; friction, equilibrium or motion   |
| `SuvatSolver`        | 4.2      | The constant-acceleration equation that fits, beside the v–t graph            |
| `MomentumCollision`  | 4.3      | A collision before and after: momentum conserved, or the particles coalescing |
| `ConnectedParticles` | 4.4      | Particles joined by a string or tow-bar: acceleration and tension             |
| `WorkEnergy`         | 4.5      | The work-energy principle as energy bars, and power P = Fv                    |

### AS & A Level: Probability & Statistics (9709 Papers 5 and 6)

| Primitive              | Syllabus | What it shows                                                                    |
| ---------------------- | -------- | -------------------------------------------------------------------------------- |
| `BoxPlot`              | 5.1      | Stem-and-leaf diagrams (back to back), quartiles and box plots compared          |
| `StandardDeviation`    | 5.1      | Mean and standard deviation from a list, a frequency table, totals or coded data |
| `ArrangementCounter`   | 5.2      | Arrangements with repeats, together or apart, and selections from groups         |
| `DiscreteDistribution` | 5.4, 6.1 | A probability table, B(n, p), Geo(p) or Po(λ) as bars, with E(X) and Var(X)      |
| `NormalDistribution`   | 5.5, 6.1 | Standardising, the inverse normal, finding μ or σ, and approximations            |
| `LinearCombination`    | 6.2      | E and Var of aX + bY + c and of sums of copies; probabilities of combinations    |
| `ContinuousPDF`        | 6.3      | A density curve: k, probabilities as areas, the mean, variance and median        |
| `SamplingEstimation`   | 6.4      | Unbiased estimates, the sample mean's distribution, and confidence intervals     |
| `HypothesisTest`       | 6.5      | Binomial, Poisson and normal-mean tests with the critical region; Type I and II  |

Two O Level primitives have A Level options: `QuadraticExplorer` solves a quadratic inequality
(9709 1.1) and `TreeDiagram` finds a conditional probability (9709 5.3). Many O Level and
Additional Mathematics primitives serve A Level directly; their `SYLLABUS` entries carry the
9709 codes as well, and [primitive-coverage.md](primitive-coverage.md) lists them by topic.

The files are named after the primitive in snake case, in `backend/app/primitives/`.

The three calculus primitives that draw y = f(x) share `backend/app/primitives/curves.py`: the
parameter schema of f and its interval, the parsing, domain and continuity predicates, the
check that f has a gradient (no corners), and drawing the axes, curve and equation. Decimals in
f are made exact first, so 0.5x² differentiates to x, not 1.0x.

New primitives arrive when scene plans show a visual the library cannot draw (§5.3.1). Copy the
closest existing primitive and follow the rules below.

## Building a primitive from stages

Most primitives after Table 5.2 are `StagedPrimitive`s (`backend/app/primitives/staged.py`).
Instead of writing `steps` and `animate` separately, a staged primitive:

1. builds every object of its picture once, by name (`build`), already laid out in its region;
2. lists the steps that reveal them at each level (`stages`): each `stage(...)` shows parts,
   hides them, morphs one into another, or emphasises them. `combine` merges stages into one
   step, and `by_level` writes the Level 2 and 3 steps from the Level 1 ones;
3. names a `motion` method for a step whose picture moves continuously, such as a sliding point.

The step list, the animation and the layout check's object names then come from one plan, so
they cannot disagree. Every step ends on its finished picture for a moment (`FINAL_HOLD_S`), so
a step's last frame is never caught mid-stroke. `tests/test_primitive_library.py` checks every
staged primitive's plan at every level for every harness case.

Shared helpers:

| Module        | What it gives                                                                                                                                                                                                          |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `plotting.py` | Axes from data (`make_plot`, optionally with equal units, or fitted to the data alone without the origin), curves cut where they leave the axes, tables, diagrams, angle marks, labels placed clear of everything else |
| `analysis.py` | Sampling y = f(x), its zeros (exact for rational functions) and its vertical asymptotes                                                                                                                                |
| `symbolic.py` | Safe parsing; numbers exact when simple and to 3 significant figures otherwise (`format_value`, `latex_value`, `format_sf`); expressions in the order a teacher writes them (`tidy_latex`)                             |

## The four elements (§5.3.1)

```python
class TangentSlideParams(PrimitiveParams):           # 1. parameter schema: types and ranges
    expression: str = Field(min_length=1, max_length=120)
    x_start: float = Field(ge=-20, le=20)
    x_end: float = Field(ge=-20, le=20)


class TangentSlide(Primitive[TangentSlideParams]):
    primitive_id = "TangentSlide"
    version = "1"
    topic = "Introductory calculus"
    params_model = TangentSlideParams
    layout = LayoutContract(                         # 3. layout contract
        region=style.GRAPH_REGION, allowed_overlaps=[("axes", "*"), ("curve", "*")]
    )

    def default_params(self): ...                    # the validated fallback (§5.3.3)
    def validate(self, params): ...                  # 2. SymPy predicates
    def computed_values(self, params): ...           # every number shown, by slot name
    def steps(self, params, level): ...              # 4. difficulty hooks
    def animate(self, scene, params, level, run_times, carried): ...
```

## Rules

**Correctness**

1. Parse every expression with `symbolic.parse_expression` (or `parse_equation`). Never use
   `sympify`, `eval` or `parse_expr` directly: parameters come from a language model, and the
   helper refuses anything that is not plain arithmetic.
2. Write the three kinds of predicate (§5.3.3). Parsing: every expression is well formed.
   Domain: every function is real and finite at sampled points of its plotted interval (use
   `sample_points` and `failing_samples`). Consistency: relations between parameters, such as
   the point of tangency lying inside the plotted interval. Name each failure clearly, because
   the message goes back to the model.
3. Every number on screen is computed by SymPy, never taken from the model, and returned by
   `computed_values` under the slot name the narration uses (`{gradient}`). Use `exact()` to turn
   parameters into exact rationals, and `format_number` / `latex_number` to show them.
4. Display expressions with `symbolic.written_latex`, which keeps them as written. SymPy's own
   printer reorders terms and rewrites fractions.

**Timing**

5. `animate` plays exactly one step per entry of `run_times`, and each step lasts exactly its
   run time. Use `style.play_step`, which animates for most of the step and holds the rest.
6. After each step, `yield` every visible object by name, including the carried objects you
   keep. The engine records the step's end time and runs the layout check there.
7. `animate` must draw the same picture whatever run times it is given. The engine replays it,
   unrendered, to rebuild the screen for the next beat (§5.3.4).

**Layout**

8. Draw only inside your layout region (`style.GRAPH_REGION` for graphs,
   `style.WORKING_REGION` for algebra). In the first step, fade out the carried objects that are
   in your region: `fades, kept = style.clear_region(carried, self.layout.region)`.
9. Place labels with `style.place_clear`, giving every object already drawn as an obstacle,
   including `style.axis_numbers(axes)`. The harness found labels landing on other labels and
   on tick numbers when they were placed at a fixed offset.
10. List in `allowed_overlaps` only the overlaps that are meant to happen, such as a point on a
    curve. Everything else that overlaps fails the layout check.
11. Use the colours in `style` (curve blue, points yellow, rise green, run orange), so one
    quantity looks the same in every primitive.

**Levels (Table 5.3)**

12. Level 2 is the reference. Level 1 animates every intermediate step separately, labels and
    highlights every new object, and has longer minimum times; the engine adds a pause after
    each step. Level 3 shows main steps only, with intermediate results shown directly.
13. `steps` and `animate` must agree: build both from one private plan, as the existing
    primitives do with `_plan`.

## Before it enters the library (§5.3.2)

1. Register the class in `PRIMITIVES` in `backend/app/primitives/library.py`, and describe it
   in `backend/app/primitives/catalog.py`, which the API and the admin pages read without
   importing Manim (a test keeps the two in step). Give it its syllabus codes in `SYLLABUS`
   there too, the same codes as its row in the tables above. Bump `LIBRARY_VERSION` in `catalog.py`
   whenever an existing primitive changes how it draws, so cached videos rendered by older code
   are not reused. Adding a new primitive changes no existing video, so it needs no bump.
2. Add a grid of parameter sets to `GRIDS` in `backend/app/primitives/harness.py`, spanning the
   permitted ranges: small and large values, negatives, fractions, and shapes that crowd the
   frame.
3. Run `npm run primitives:check -- TangentSlide`. Every case is rendered at every level, and
   each must finish without an error or layout violation.
4. Open `backend/media/harness/TangentSlide/review.md` and check a sample of the frames against
   the mathematics. The automatic checks cannot tell that a display is misleading; reviewing
   frames found a fraction that SymPy's printer had rewritten.
5. Add tests to `backend/tests/test_primitives.py` for the predicates and computed values.
