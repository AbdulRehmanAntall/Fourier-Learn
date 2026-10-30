# Primitive coverage of the syllabus

Which primitive draws each visual the syllabus needs. The list of visuals is the primitive
specification mapped against the official Cambridge syllabi:

- **Cambridge O Level Mathematics (Syllabus D) 4024**, examinations 2025 to 2027 (Units 1 to 9).
- **Cambridge O Level Additional Mathematics 4037**, examinations 2025 to 2027 (Unit 14 calculus,
  and the units marked AM).
- **Cambridge International AS & A Level Mathematics 9709**, examinations 2026 and 2027 (all six
  components; sections K to P below).

Syllabus codes refer to 4024 unless they start with AM (4037) or 9709.

Design rules, from the specification and the report (§5.3):

1. **Parameterised templates.** A primitive is a validated Manim template. The model supplies
   parameters only (the function, the point, the data); it never writes layout or drawing code.
   One template serves many syllabus points through its parameters.
2. **Three levels.** Every primitive renders at Level 1 (slower, more labels, smaller steps),
   Level 2 (the reference) and Level 3 (terser). The level is a parameter, not a new primitive.
3. **Correct by construction.** Every number on screen is computed by SymPy and checked against
   the primitive's predicates before rendering. The model proposes; SymPy verifies.

Scope: `CORE` is inside the FYP build scope (functions and graphs, coordinate geometry, travel
graphs and kinematics, introductory calculus). `EXT` is the rest of 4024. `AM-EXT` is Additional
Mathematics beyond 4024. `A-LEVEL` is 9709.

Status: **done** means the primitive is in the library and passes the validation harness at every
level; **planned** means it is not built yet.

## A. Number (4024 Unit 1) `EXT`

| #   | Visual                 | Syllabus                 | Primitive         | Status |
| --- | ---------------------- | ------------------------ | ----------------- | ------ |
| 1   | Number line            | 1.1, 1.4, 1.5, 1.9, 1.10 | `NumberLine`      | done   |
| 2   | Prime factor tree      | 1.1                      | `PrimeFactorTree` | done   |
| 3   | Venn diagram           | 1.2, 8.3                 | `VennDiagram`     | done   |
| 4   | Fraction area model    | 1.4, 1.6                 | `FractionModel`   | done   |
| 5   | Percentage bar         | 1.13                     | `PercentageBar`   | done   |
| 6   | Growth and decay curve | 1.13.4, 1.17, 2.10.3     | `GrowthDecay`     | done   |
| 7   | Powers-of-ten zoom     | 1.7, 1.8                 | `StandardForm`    | done   |
| 8   | Index laws stepper     | 1.7, 2.4                 | `IndexLaws`       | done   |
| 9   | Surd simplifier        | 1.18                     | `SurdSimplifier`  | done   |
| 10  | Ratio bar splitter     | 1.11, 1.12               | `RatioSplitter`   | done   |
| 11  | Bounds interval        | 1.10                     | `BoundsInterval`  | done   |
| 12  | Clock and timetable    | 1.15, 1.16               | `ClockTimetable`  | done   |

## B. Algebra and graphs (4024 Unit 2) `CORE`

| #   | Visual                  | Syllabus                | Primitive                                                      | Status |
| --- | ----------------------- | ----------------------- | -------------------------------------------------------------- | ------ |
| 13  | Algebra balance stepper | 2.1, 2.2, 2.3, 2.5      | `AlgebraBalance`, `EquationTransform`, `SimultaneousEquations` | done   |
| 14  | Expansion grid          | 2.2, 2.5.5              | `ExpansionGrid`, `CompletingSquare`                            | done   |
| 15  | Quadratic explorer      | 2.5.5, 2.11; AM 2.1–2.5 | `QuadraticExplorer`                                            | done   |
| 16  | Inequality region       | 2.6                     | `InequalityRegion`                                             | done   |
| 17  | Sequence pattern        | 2.7                     | `SequencePattern`                                              | done   |
| 18  | Proportion grapher      | 2.8                     | `ProportionGraph`                                              | done   |
| 19  | Function grapher        | 2.10, 2.9.1             | `FunctionGraph`, `GraphicalSolution`, `TableOfValues`          | done   |
| 20  | Curve sketcher          | 2.11; AM 4.4, AM 6.1    | `CurveSketch`                                                  | done   |
| 21  | Function machine        | 2.12; AM 1.1–1.8        | `FunctionMachine`, `InverseGraph`                              | done   |
| 22  | Travel graph            | 2.9.3, 2.9.4            | `TravelGraph`                                                  | done   |

## C. Coordinate geometry (4024 Unit 3) `CORE`

| #   | Visual                           | Syllabus              | Primitive                               | Status |
| --- | -------------------------------- | --------------------- | --------------------------------------- | ------ |
| 23  | Coordinate plotter               | 3.1, 3.4, links 6.1   | `CoordinatePlotter`, `GradientTriangle` | done   |
| 24  | Line builder                     | 3.2, 3.3, 3.5         | `LineBuilder`, `GradientTriangle`       | done   |
| 25  | Parallel and perpendicular lines | 3.6, 3.7; AM 7.2, 7.3 | `ParallelPerpendicular`                 | done   |
| 26  | Coordinate circle `AM-EXT`       | AM 8.1–8.4            | `CoordinateCircle`                      | done   |

## D. Geometry (4024 Unit 4) `EXT`

| #   | Visual               | Syllabus       | Primitive             | Status |
| --- | -------------------- | -------------- | --------------------- | ------ |
| 27  | Angle chaser         | 4.6.1, 4.6.2   | `AngleChaser`         | done   |
| 28  | Polygon angle walker | 4.6.3          | `PolygonAngles`       | done   |
| 29  | Circle theorem stage | 4.7, 4.8       | `CircleTheorems`      | done   |
| 30  | Similarity scaler    | 4.4, links 7.1 | `SimilarityScaler`    | done   |
| 31  | Bearings navigator   | 4.3            | `Bearings`            | done   |
| 32  | Symmetry reveal      | 4.5            | `SymmetryReveal`      | done   |
| 33  | Net folder           | 4.1, 4.2.3     | `NetFolder`           | done   |
| 34  | Compass construction | 4.2            | `CompassConstruction` | done   |

## E. Mensuration (4024 Unit 5) `EXT`

| #   | Visual                 | Syllabus      | Primitive          | Status |
| --- | ---------------------- | ------------- | ------------------ | ------ |
| 35  | Area dissector         | 5.2, 5.5      | `AreaDissector`    | done   |
| 36  | Circle, arc and sector | 5.3; AM 9.1   | `CircleSector`     | done   |
| 37  | Solid mensurator       | 5.1, 5.4, 5.5 | `SolidMensuration` | done   |

## F. Trigonometry (4024 Unit 6) `EXT`

| #   | Visual                         | Syllabus            | Primitive           | Status |
| --- | ------------------------------ | ------------------- | ------------------- | ------ |
| 38  | Right-triangle trigonometry    | 6.1, 6.2            | `RightTriangleTrig` | done   |
| 39  | Sine and cosine rule solver    | 6.3                 | `SineCosineRule`    | done   |
| 40  | Trigonometry in 3D             | 6.4                 | `Trig3D`            | done   |
| 41  | Unit circle and waves `AM-EXT` | AM 10.2, 10.3; 2.11 | `UnitCircleWaves`   | done   |

## G. Transformations and vectors (4024 Unit 7) `EXT`

| #   | Visual               | Syllabus       | Primitive             | Status |
| --- | -------------------- | -------------- | --------------------- | ------ |
| 42  | Transformation stage | 7.1            | `TransformationStage` | done   |
| 43  | Vector arena         | 7.2–7.4; AM 13 | `VectorArena`         | done   |

## H. Probability (4024 Unit 8) `EXT`

| #   | Visual                        | Syllabus | Primitive            | Status |
| --- | ----------------------------- | -------- | -------------------- | ------ |
| 44  | Probability scale and spinner | 8.1, 8.2 | `ProbabilitySpinner` | done   |
| 45  | Tree diagram                  | 8.3      | `TreeDiagram`        | done   |
| 46  | Sample space grid             | 8.3      | `SampleSpaceGrid`    | done   |

## I. Statistics (4024 Unit 9) `EXT`

| #   | Visual                           | Syllabus | Primitive             | Status |
| --- | -------------------------------- | -------- | --------------------- | ------ |
| 47  | Chart builder                    | 9.1, 9.4 | `ChartBuilder`        | done   |
| 48  | Averages visualiser              | 9.2, 9.3 | `AveragesVisualizer`  | done   |
| 49  | Scatter and best fit             | 9.5      | `ScatterBestFit`      | done   |
| 50  | Cumulative frequency ogive       | 9.6      | `CumulativeFrequency` | done   |
| 51  | Histogram with frequency density | 9.7      | `Histogram`           | done   |

## J. Calculus and kinematics (4037 Unit 14) `CORE`

| #   | Visual                          | Syllabus             | Primitive                                          | Status |
| --- | ------------------------------- | -------------------- | -------------------------------------------------- | ------ |
| 52  | Secant to tangent               | AM 14.1–14.5; 2.10.4 | `SecantToTangent`, `TangentSlide`, `TangentNormal` | done   |
| 53  | Function-derivative twin panels | AM 14.6, 14.9        | `DerivativePanels`                                 | done   |
| 54  | Differentiation stepper         | AM 14.3, 14.4        | `DifferentiationStepper`                           | done   |
| 55  | Optimisation scene              | AM 14.8              | `OptimisationScene`                                | done   |
| 56  | Connected rates                 | AM 14.7              | `ConnectedRates`                                   | done   |
| 57  | Area under a curve              | AM 14.10–14.13       | `AreaUnderCurve`, `AreaBetweenCurves`              | done   |
| 58  | Kinematics triple graph         | AM 14.14, 14.15      | `KinematicsGraphs`, `TravelGraph`                  | done   |

## K. AS & A Level: Pure Mathematics 1 (9709 Paper 1) `A-LEVEL`

| #   | Topic               | Syllabus | Primitive                                                                                                           | Status |
| --- | ------------------- | -------- | ------------------------------------------------------------------------------------------------------------------- | ------ |
| 59  | Quadratics          | 1.1      | `QuadraticExplorer` (with inequalities), `CompletingSquare`, `LineMeetsCurve`, `SimultaneousEquations`              | done   |
| 60  | Functions           | 1.2      | `FunctionMapping`, `GraphTransform`, `FunctionMachine`, `InverseGraph`                                              | done   |
| 61  | Coordinate geometry | 1.3      | `ParallelPerpendicular`, `CoordinateCircle`, `LineMeetsCurve`                                                       | done   |
| 62  | Circular measure    | 1.4      | `CircleSector`                                                                                                      | done   |
| 63  | Trigonometry        | 1.5      | `TrigEquationSolver`, `UnitCircleWaves`                                                                             | done   |
| 64  | Series              | 1.6      | `BinomialExpansion`, `Progression`                                                                                  | done   |
| 65  | Differentiation     | 1.7      | `DifferentiationStepper`, `TangentNormal`, `DerivativePanels`, `OptimisationScene`, `ConnectedRates`, `CurveSketch` | done   |
| 66  | Integration         | 1.8      | `AntiderivativeFamily`, `AreaUnderCurve`, `AreaBetweenCurves`, `VolumeOfRevolution`                                 | done   |

## L. AS & A Level: Pure Mathematics 2 and 3 (9709 Papers 2 and 3) `A-LEVEL`

Paper 2 (2.1 to 2.6) is a subset of Paper 3 (3.1 to 3.9), so each row gives both codes.

| #   | Topic                                 | Syllabus | Primitive                                                                        | Status |
| --- | ------------------------------------- | -------- | -------------------------------------------------------------------------------- | ------ |
| 67  | Algebra                               | 2.1, 3.1 | `ModulusEquation`, `PolynomialDivision`, `PartialFractions`, `BinomialExpansion` | done   |
| 68  | Logarithmic and exponential functions | 2.2, 3.2 | `LogLinearisation`, `GrowthDecay`                                                | done   |
| 69  | Trigonometry                          | 2.3, 3.3 | `HarmonicForm`, `TrigEquationSolver`                                             | done   |
| 70  | Differentiation                       | 2.4, 3.4 | `DifferentiationStepper`, `ParametricCurve`, `ImplicitCurve`                     | done   |
| 71  | Integration                           | 2.5, 3.5 | `IntegrationMethod`, `PartialFractions`, `TrapeziumRule`                         | done   |
| 72  | Numerical solution of equations       | 2.6, 3.6 | `IterationDiagram`                                                               | done   |
| 73  | Vectors                               | 3.7      | `VectorLines3D`                                                                  | done   |
| 74  | Differential equations                | 3.8      | `DifferentialEquation`                                                           | done   |
| 75  | Complex numbers                       | 3.9      | `ArgandDiagram`, `ComplexLoci`                                                   | done   |

## M. AS & A Level: Mechanics (9709 Paper 4) `A-LEVEL`

Mechanics uses g = 10 m s⁻², as the syllabus asks.

| #   | Topic                                   | Syllabus | Primitive                            | Status |
| --- | --------------------------------------- | -------- | ------------------------------------ | ------ |
| 76  | Forces and equilibrium                  | 4.1      | `ForceDiagram`                       | done   |
| 77  | Kinematics of motion in a straight line | 4.2      | `SuvatSolver`, `KinematicsGraphs`    | done   |
| 78  | Momentum                                | 4.3      | `MomentumCollision`                  | done   |
| 79  | Newton's laws of motion                 | 4.4      | `ConnectedParticles`, `ForceDiagram` | done   |
| 80  | Energy, work and power                  | 4.5      | `WorkEnergy`                         | done   |

## N. AS & A Level: Probability & Statistics 1 (9709 Paper 5) `A-LEVEL`

| #   | Topic                         | Syllabus | Primitive                                                                      | Status |
| --- | ----------------------------- | -------- | ------------------------------------------------------------------------------ | ------ |
| 81  | Representation of data        | 5.1      | `BoxPlot`, `StandardDeviation`, `Histogram`, `CumulativeFrequency`             | done   |
| 82  | Permutations and combinations | 5.2      | `ArrangementCounter`                                                           | done   |
| 83  | Probability                   | 5.3      | `TreeDiagram` (with conditional probability), `VennDiagram`, `SampleSpaceGrid` | done   |
| 84  | Discrete random variables     | 5.4      | `DiscreteDistribution`                                                         | done   |
| 85  | The normal distribution       | 5.5      | `NormalDistribution`                                                           | done   |

## O. AS & A Level: Probability & Statistics 2 (9709 Paper 6) `A-LEVEL`

| #   | Topic                                   | Syllabus | Primitive                                                    | Status |
| --- | --------------------------------------- | -------- | ------------------------------------------------------------ | ------ |
| 86  | The Poisson distribution                | 6.1      | `DiscreteDistribution`, `NormalDistribution` (approximation) | done   |
| 87  | Linear combinations of random variables | 6.2      | `LinearCombination`                                          | done   |
| 88  | Continuous random variables             | 6.3      | `ContinuousPDF`                                              | done   |
| 89  | Sampling and estimation                 | 6.4      | `SamplingEstimation`                                         | done   |
| 90  | Hypothesis tests                        | 6.5      | `HypothesisTest`                                             | done   |

Every 9709 topic has at least one primitive. A primitive draws the method on a worked example;
the narration and the lesson plan carry the explanation and any proof the syllabus asks for (for
example, why dividing by n − 1 makes s² unbiased), using `TextCard` for words that are not part of
a visual.

## Text on screen

Every visual above is drawn by a primitive. Words that are not part of a visual (a topic heading
at the start of a lesson, a question in the learner's own words, key points to remember) are
drawn by `TextCard`, which checks the text before it reaches LaTeX. With `place: "side"` it sits
in the working region, so a question stays in view while a graph primitive solves it.
