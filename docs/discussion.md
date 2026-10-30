# Discussion: building the visual primitive library

This document records how the primitive library was built, what went wrong along the way, what
the tests and the validation harness found, and what that means for the design. It is written
as a research artefact for the project report: the issues are real ones met while building the
library, with the fix and the lesson each one taught.

## 1. Aim and scope

The system answers an O Level student's question with a short narrated video. A language model
plans the lesson, but it never writes drawing code: it picks visual primitives and fills in
their parameters, and each primitive is a validated Manim template written before deployment
(report §5.3). The question this work set out to answer was whether a finite library of such
templates can cover the visuals of the whole syllabus while staying correct by construction.

The library was planned from a specification of 58 visuals mapped to Cambridge O Level
Mathematics 4024 (Units 1 to 9) and the calculus of Additional Mathematics 4037 (Unit 14), with
the 4037 topics that build on it. [primitive-coverage.md](primitive-coverage.md) maps each
visual to the primitive that draws it.

| Measure                                         |                                 Result |
| ----------------------------------------------- | -------------------------------------: |
| Primitives in the library                       |                                     69 |
| Visuals of the specification covered            |                                58 / 58 |
| Harness cases (parameter sets)                  |                                    432 |
| Renders checked by the harness (3 levels each)  |                                  1 296 |
| Harness renders failing at the end              |                                      0 |
| Backend tests passing (with Manim)              |                     614 (10 skipped)\* |
| Backend tests passing (fresh machine, no Manim) |                       121 (10 skipped) |
| Source in `backend/app/primitives`              | 79 files, about 24 000 lines of Python |

\* The skipped tests are database tests: they need a Postgres database (`TEST_DATABASE_URL`),
which CI provides.

The seven primitives of Table 5.2 came first. Six batches of ten (eleven in the last) added the
rest, each committed once its harness passed, and `TextCard` was added last for words on
screen.

## 2. Method

**One base class.** All but seven primitives share `StagedPrimitive`. A primitive declares its
parts (`build`) and an ordered plan of stages (`stages`): what each step shows, hides, morphs or
emphasises, its narration and its minimum run time. The three difficulty levels are made from
one plan by `by_level`: Level 1 plays every stage, Levels 2 and 3 merge stages with `combine`.
Writing the plan once and deriving the levels kept the levels consistent with each other.

**Correct by construction.** Every number on screen is computed with SymPy from the
parameters, never typed by the model. Values stay exact where O Level keeps them exact
(fractions, surds, multiples of π) and are otherwise given to 3 significant figures, angles to
1 decimal place and money to the cent. Each primitive has predicates (`validate`) that refuse
parameters that would draw something wrong or meaningless, with a message the planner can act
on.

**Four layers of checking.**

1. _Unit tests_ (`tests/test_primitive_library.py`, 73 test functions with many cases) check
   the computed values and the predicates of every primitive, and that every stage plan is
   consistent at every level (nothing shown twice, hidden before it appears, or morphed from
   something absent).
2. _The validation harness_ (`npm run primitives:check`) renders every grid case at all three
   levels and runs the layout checker on every step: every object inside the frame and its
   region, and no two objects overlapping unless the layout contract allows it.
3. _Visual review_: the last frame of every case was looked at by eye, and the maths on it
   checked by hand against an independent calculation.
4. _CI_: lint, format, the tests with and without Manim, and a fresh-machine setup.

## 3. What went wrong, and what found it

The issues fall into five groups. The table gives representative cases from each; the sections
after it draw out the pattern.

| Group            | Issue                                                                                                                                                | Seen in                   | Fix                                                                                         |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- | ------------------------------------------------------------------------------------------- |
| Mathematics      | Rounding used Python's half-to-even rule: −5.625 became −5.62                                                                                        | Visual review             | Round half up from the exact value with `Decimal`                                           |
| Mathematics      | A rounded answer lost its trailing zero: 18.03 to 3 s.f. showed as 18                                                                                | Visual review             | Keep trailing zeros when a value was rounded, drop them when it is exact (2.5, not 2.50)    |
| Mathematics      | The inverse of y = x³ was drawn only for x ≥ 0: `x**(1/3)` is not real for negative x in floating point                                              | Harness (runtime warning) | Take odd roots as real roots when drawing                                                   |
| Mathematics      | SymPy expands brackets as it parses, so "expand the bracket" was never offered in the algebra balance                                                | Rendered frames           | Check the written line for a bracket, not the parsed expression                             |
| Mathematics      | The limit of sin x at infinity (an `AccumBounds`) was taken for an asymptote                                                                         | Visual review             | Skip limits that are not numbers                                                            |
| Mathematics      | A frequency table with all frequencies equal reported the first value as the mode                                                                    | Value check               | Report no mode when every value is equally common                                           |
| Mathematics      | The sine rule's ambiguous case has two angles                                                                                                        | Design review             | Take the acute angle, as O Level does, and say so on screen                                 |
| Teaching form    | Decimals given by the planner came back as fractions (1.2 shown as 6/5, 0.5 as 1/2)                                                                  | Visual review             | Show numbers in the form they were given                                                    |
| Teaching form    | Surds and conjugates written in SymPy's order (√5 + 3, conjugate −√2 − 1)                                                                            | Visual review             | Keep the written order; a conjugate keeps the first term and changes the sign of the second |
| Teaching form    | Working left a letter where a number was known (tan θ = 5/AC)                                                                                        | Visual review             | Substitute every known value                                                                |
| Degenerate input | A point on the mirror line y = x reflects onto itself, so it was labelled twice                                                                      | Visual review             | A predicate refuses it, with a message asking for another point                             |
| Degenerate input | Equal arcs in the angle bisector construction did not meet for wide angles                                                                           | Geometry check            | The arc radius is always more than half the gap between the two points                      |
| Degenerate input | A parallel-line case asked for the foot of a perpendicular that does not exist (an `IndexError`)                                                     | Preview render (error)    | Compute the foot only for the perpendicular case                                            |
| Layout           | Labels on lines, arcs and other labels (vertex letters on angle arcs, an obtuse angle's label across a flat triangle, "opp" over the working column) | Visual review             | Place labels in the widest free gap, outside obtuse angles, beside dimension lines          |
| Layout           | Axes always included the origin, squashing data far from zero (heights of 150–180 cm)                                                                | Visual review             | `make_plot(origin=False)` fits the axes to the data                                         |
| Layout           | Long lines were shrunk to fit their column until they were unreadable                                                                                | Visual review             | Break long reasons over two lines                                                           |
| Layout           | The last stroke of a step was missing from the step's final frame                                                                                    | Visual review             | Every step ends on a short hold (`FINAL_HOLD_S`)                                            |
| Plan semantics   | A part shown and then morphed in one merged step stayed on screen twice                                                                              | Rendered frames           | `combine` resolves the net effect of the merged stages                                      |
| Plan semantics   | A part emphasised after it was hidden reappeared through the emphasis                                                                                | Rendered frames           | Emphasise only parts still on screen                                                        |
| Infrastructure   | On a machine without Cairo/Pango, pytest failed while collecting the library tests (`No module named 'manim'`)                                       | CI (Full check)           | Skip the Manim-dependent test files there, as for the others                                |
| Infrastructure   | Parallel renders on a laptop ran out of memory in OpenBLAS                                                                                           | User report               | More disk/memory; the thread limit was kept off at the user's request                       |
| Safety           | Free text from the language model would go straight into LaTeX                                                                                       | Design review             | `TextCard` allows plain words outside `$...$` and a known list of commands inside it        |

### 3.1 Layout was the largest class of problems

Most primitives needed at least one layout revision after their first preview, and most of the
fixes in this work were about where a label goes. A label that sits on a line is still
"correct", and no unit test notices it, but a student cannot read it. Three general techniques
came out of these fixes and were reused across primitives: placing a label in the widest angular
gap around its point (bearings, angle chaser), moving it outside the figure with a dimension
line when the figure is too thin (solids, pyramids, 3D trigonometry), and splitting a long line
of working rather than shrinking it.

### 3.2 The layout checker sees geometry, not readability

The harness's layout check found real faults: objects leaving the frame, and overlaps the
contract did not allow. But it also reported overlaps that were intended, and it missed faults
a person sees at once:

- **False alarms.** A group's bounding box spans everything in it. A table's grid lines enclose
  its columns, the two arms of a fraction-label group cover the space between them, and the
  angle marks at one vertex overlap. Several primitives therefore declare overlaps such as
  `("table", "*")`, or split one group into parts so that each part has a tight box.
- **Missed faults.** A label drawn on the wrong point, a fraction too small to read, text
  crossing a dashed line inside an allowed overlap: none of these break a rule the checker
  knows. Only visual review found them.

The lesson is that the checker is necessary but not sufficient. An automated readability check
(a minimum rendered font size, and label-to-line clearance measured on the rendered frame) would
catch some of what review found; it is listed under future work.

### 3.3 Mathematical faults were few but serious

Mathematical faults were rarer than layout ones, because every value comes from SymPy, but each
would have taught something false. Two patterns stand out:

- **Floating point leaking into exact work.** The cube root, the rounding rule and the trailing
  zeros all came from a float where an exact value was available. The fix in each case was to
  keep the exact value (a SymPy expression or a `Decimal`) until the moment of display.
- **The form matters as well as the value.** 6/5 and 1.2 are equal, but a question that says
  1.2 should be answered in decimals. √5 + 3 and 3 + √5 are equal, but a teacher writes the
  second. Several fixes were about showing a correct value in the form a student expects.

### 3.4 Predicates turn degenerate inputs into useful messages

The planner can ask for anything the parameter schema allows, including cases that are
mathematically fine but visually meaningless: a point on the mirror line, a rotation of zero, a
square number to simplify, a spinner of one colour. A predicate that refuses these, with a
message naming the parameter and the reason, is better than a strange video: the planner can
repair its plan. Every primitive has such predicates, and the unit tests check them.

### 3.5 What each layer of checking contributed

| Layer         | Catches                                                    | Misses                                               |
| ------------- | ---------------------------------------------------------- | ---------------------------------------------------- |
| Unit tests    | Wrong values, missing predicates, inconsistent stage plans | Anything visual                                      |
| Harness       | Runtime errors at any level, out-of-frame, banned overlaps | Intended overlaps (false alarms), unreadable layouts |
| Visual review | Collisions, wrong form, tiny text, wrong label placement   | Does not scale; depends on the reviewer              |
| CI            | Environment differences (no Manim, no LaTeX, no database)  | Rendering quality                                    |

No single layer was enough. Running the harness at all three levels mattered as well: the
merged stages of Levels 2 and 3 exposed plan faults that Level 1 alone did not (at Level 3,
the area between two curves once tried to hide strips that had never been shown).

## 4. Design decisions

- **Many specific templates, not one general drawing primitive.** A general "draw these shapes"
  primitive would let the model produce anything, and so would give up correctness by
  construction. Specific templates with mathematical parameters keep every drawing checkable.
  One template still serves many syllabus points through its parameters (`AngleChaser` handles
  lines, points, parallel lines and triangles).
- **Exact first, rounded last.** Values stay exact until displayed, and are shown exact when
  simple (3/4, 2√3, 20π) and to O Level's accuracy otherwise.
- **Regions make primitives combinable.** Graph primitives draw on the left 62% of the frame and
  working primitives on the right. A new primitive only clears what overlaps its own region,
  so a question card on the right stays in view while a graph on the left solves it; this was
  checked with a two-beat render.
- **Levels from one plan.** Writing the Level 1 plan once and deriving Levels 2 and 3 by
  merging stages guaranteed the three levels teach the same thing.
- **Text is data, not code.** Words on screen reach LaTeX only after a whitelist check, so a
  model cannot inject commands such as `\input` through a question.

## 5. Limitations and future work

- **No study with students yet.** Every layout was judged by its developer. Whether the
  visuals help O Level students learn is the question the evaluation phase must answer.
- **Readability is not checked automatically.** See §3.2: a rendered-frame check for minimum
  text size and label clearance would reduce the reliance on review.
- **Some drawings simplify.** Solids are drawn in oblique projection, not true 3D. The line of
  best fit is the least-squares line through the mean point, where a student draws one by
  eye. The cumulative frequency curve is a monotone cubic through the points, where a student
  draws a freehand curve. Each is a faithful model of the hand-drawn version, not a copy.
- **Narration is a first draft.** Each stage carries a description used as default narration,
  and maths read aloud (`_spoken` in `TextCard`) handles common forms only; the lesson planner
  is expected to write the final narration.
- **Coverage is of visuals, not of every question type.** The 58 visuals cover the syllabus
  content, but some questions combine topics in ways that need two or more primitives in
  sequence. How well the planner combines them is untested beyond single examples.
- **A Level is untested with learners and with the planner.** The 9709 primitives were checked
  for correct mathematics and readable frames, as the O Level ones were, but no A Level student
  has used them, and the lesson planner has not yet been prompted with A Level questions.

## 6. Extending the library to AS & A Level (9709)

The same method was then applied to Cambridge International AS & A Level Mathematics (9709,
examinations 2026 and 2027). The syllabus was taken topic by topic from the official document
(Pure Mathematics 1 to 3, Mechanics, Probability & Statistics 1 and 2) and each topic was given a
primitive, an existing one or a new one: 36 new primitives, two A Level options on existing
ones (`QuadraticExplorer` solves inequalities, `TreeDiagram` finds conditional probabilities),
and 9709 codes on 25 O Level and Additional Mathematics primitives that serve A Level directly.
The new primitives have 251 harness parameter sets between them, each rendered at all three
levels, and their values were checked by hand against worked answers and statistical tables.

The O Level library made this faster than the first build: the staged base, the plotting and
table helpers, `stack_lines` for working and the SymPy helpers were reused unchanged, so most
of the effort went into the mathematics. What the A Level work found:

- **A rounding fault in shared code.** `format_sf` wrote a value just below a power of ten,
  such as 0.99996 to 4 significant figures, as 1.0000: rounding carried it into the next power
  of ten, so it gained a figure. A trigonometric solution exposed it. The fix in `symbolic.py`
  corrects every primitive that formats numbers.
- **SymPy can answer in functions the syllabus does not have.** It integrates e^(x²) to an
  expression in erfi, which is correct but no use to a student. `is_elementary_integral` now
  rejects such results, so `IntegrationMethod`, `DifferentialEquation` and
  `AntiderivativeFamily` refuse inputs a student could not integrate by hand, with a message.
  Each integral is also checked by differentiating it back.
- **Symbol assumptions must match.** `ContinuousPDF` first never found the constant k: it made
  k a positive symbol, while the safe parser makes every symbol real, and SymPy treats the two
  as different variables. Tests on the first grid case caught it.
- **Inputs can be mathematically legal and still meaningless.** A density such as k/x² on
  x ≥ 1 integrates to 1 but has no mean; a hypothesis test at a low level may have no critical
  region at all; a normal approximation needs np and nq above 5. Each became a predicate with a
  message, in the same way as the O Level predicates (§3.4).
- **Discrete tests need exact sizes.** The actual significance level of a binomial or Poisson
  test is the probability of its critical region, which is at most the nominal level. Computing
  it exactly gives P(Type I error) directly, where a table-based answer could not.
- **Readability again (§3.2).** Long rows were shrunk to fit and became unreadable: a
  hypothesis test's conclusion, a conditional probability written with its events in full, and
  the variance of a combination with every coefficient squared. They were split into two rows,
  or the events were named A and B in the question. Two z labels close together were first
  stacked, which pushed one off the frame; the harness caught that, and they now move apart
  sideways. As in the O Level work, review of the frames found the problems the layout check
  cannot see.
- **Form follows the syllabus.** Statistics are written as decimals (a median of 19.5, not
  39/2) and angles in radians as multiples of π (π/3, not 1.05); mechanics uses g = 10 m s⁻² as
  the syllabus asks. Each choice was made from the frames, not in advance.
- **Tooling matters.** A helper that converted JSON grids to Python replaced the text "null"
  inside the parameter name `null_value`. It was found at once because the grid failed to
  parse, and the helper now writes Python literals directly.

**Can it teach any 9709 topic?** Every topic of the six components has at least one primitive
(rows 59 to 90 of [primitive-coverage.md](primitive-coverage.md)). A primitive draws the
method on a worked example; the explanation around it (why the method works, a proof the
syllabus asks for, the context of a question) comes from the lesson plan's narration and from
`TextCard`. So a learner who asks "explain hypothesis testing" gets the plan's explanation with
a test drawn and worked step by step, but the quality of that explanation depends on the planner,
which is evaluated separately.

## 7. Conclusion

A finite library of 105 parameterised primitives covers every visual of the specification for
O Level Mathematics and the calculus of Additional Mathematics, and every topic of AS & A Level
Mathematics, with every one rendering without error at all three levels across 691 parameter
sets. Correctness by construction held
for the mathematics: the faults found were about precision and form, and each was fixed at its
root in shared code. The hardest part was not the mathematics but making every frame readable,
and the main finding is that a geometric layout checker is necessary but must be paired with
visual review, or with an automated readability check, before videos reach students.
