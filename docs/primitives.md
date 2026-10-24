# Writing a primitive

A visual primitive is a parameterised Manim CE component that draws one type of mathematical
visual (report §5.3.1). Manim code is written only in primitives, before deployment. At runtime
a language model chooses a primitive and fills in its parameters, and nothing else (§5.3).

The library holds the seven primitives of Table 5.2:

| Primitive           | Topic                        | What it shows                                                   | File                                           |
| ------------------- | ---------------------------- | --------------------------------------------------------------- | ---------------------------------------------- |
| `FunctionGraph`     | Functions and graphs         | The graph of f on labelled axes, with marked points             | `backend/app/primitives/function_graph.py`     |
| `GradientTriangle`  | Coordinate geometry          | Rise and run between two points; gradient = rise / run          | `backend/app/primitives/gradient_triangle.py`  |
| `TangentSlide`      | Introductory calculus        | A tangent sliding along a curve, with its gradient read out     | `backend/app/primitives/tangent_slide.py`      |
| `SecantToTangent`   | Introductory calculus        | Secants PQ approaching the tangent at P as h shrinks            | `backend/app/primitives/secant_to_tangent.py`  |
| `TravelGraph`       | Travel graphs and kinematics | Distance-time or speed-time graph; gradients or areas explained | `backend/app/primitives/travel_graph.py`       |
| `AreaUnderCurve`    | Introductory calculus        | The area under a curve between two limits, by integration       | `backend/app/primitives/area_under_curve.py`   |
| `EquationTransform` | All topics                   | A derivation step by step, changed terms highlighted            | `backend/app/primitives/equation_transform.py` |

The three calculus primitives that draw y = f(x) share `backend/app/primitives/curves.py`: the
parameter schema of f and its interval, the parsing, domain and continuity predicates, the
check that f has a gradient (no corners), and drawing the axes, curve and equation. Decimals in
f are made exact first, so 0.5x² differentiates to x, not 1.0x.

New primitives arrive when scene plans show a visual the library cannot draw (§5.3.1). Copy the
closest existing primitive and follow the rules below.

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

1. Register the class in `PRIMITIVES` in `backend/app/primitives/library.py`, and add it to
   the admin stub's list in `backend/app/stub/seed.py` (a test keeps the two in step). Bump
   `LIBRARY_VERSION` whenever an existing primitive changes how it draws, so cached videos
   rendered by older code are not reused. Adding a new primitive changes no existing video, so
   it needs no bump.
2. Add a grid of parameter sets to `GRIDS` in `backend/app/primitives/harness.py`, spanning the
   permitted ranges: small and large values, negatives, fractions, and shapes that crowd the
   frame.
3. Run `npm run primitives:check -- TangentSlide`. Every case is rendered at every level, and
   each must finish without an error or layout violation.
4. Open `backend/media/harness/TangentSlide/review.md` and check a sample of the frames against
   the mathematics. The automatic checks cannot tell that a display is misleading; reviewing
   frames found a fraction that SymPy's printer had rewritten.
5. Add tests to `backend/tests/test_primitives.py` for the predicates and computed values.
