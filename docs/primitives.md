# Writing a primitive

A visual primitive is a parameterised Manim CE component that draws one type of mathematical
visual (report §5.3.1). Manim code is written only in primitives, before deployment. At runtime
a language model chooses a primitive and fills in its parameters, and nothing else (§5.3).

The library started with the seven primitives of Table 5.2 and is growing to cover the
Cambridge O Level Mathematics (4024) syllabus and the calculus of Additional Mathematics (4037
Unit 14). [docs/primitive-coverage.md](primitive-coverage.md) maps every visual the syllabus
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

| Primitive           | Syllabus     | What it shows                                                                 |
| ------------------- | ------------ | ----------------------------------------------------------------------------- |
| `AlgebraBalance`    | 2.1–2.3, 2.5 | Solving an equation or changing the subject by doing the same to both sides   |
| `ExpansionGrid`     | 2.2, 2.5.5   | Expanding brackets or factorising with a grid (area) model                    |
| `CompletingSquare`  | 2.5.5; AM 2  | Completing the square as an area, with the missing corner                     |
| `QuadraticExplorer` | 2.5.5, 2.11  | A parabola's roots, discriminant, vertex, axis of symmetry and completed form |
| `InequalityRegion`  | 2.6          | Regions of linear inequalities, unwanted side shaded, region R labelled       |
| `SequencePattern`   | 2.7          | The nth term from differences or a ratio, with optional dot patterns          |
| `ProportionGraph`   | 2.8          | Direct and inverse proportion: y = kxⁿ, k from a known pair                   |
| `CurveSketch`       | 2.11; AM 4.4 | A sketched curve with intercepts, turning points and asymptotes               |
| `FunctionMachine`   | 2.12; AM 1   | A function as a machine, values traced through it, and its inverse            |
| `GraphicalSolution` | 2.10         | Solving f(x) = g(x) by reading where two graphs meet                          |

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

| Module        | What it gives                                                                                                                                                                              |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `plotting.py` | Axes from data (`make_plot`, optionally with equal units), curves cut where they leave the axes, tables, diagrams, angle marks, labels placed clear of everything else                     |
| `analysis.py` | Sampling y = f(x), its zeros (exact for rational functions) and its vertical asymptotes                                                                                                    |
| `symbolic.py` | Safe parsing; numbers exact when simple and to 3 significant figures otherwise (`format_value`, `latex_value`, `format_sf`); expressions in the order a teacher writes them (`tidy_latex`) |

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
   importing Manim (a test keeps the two in step). Bump `LIBRARY_VERSION` in `catalog.py`
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
