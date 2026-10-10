# Contracts

The contracts are the data shapes that FourierLearn's components exchange. They are the "defined
interfaces" the report requires between the Prompt Interpreter, Code Generator, Audio Pipeline,
Interactive Playback Layer and Learner State Module (§4.3.5, §6.2.2). They live in
`backend/app/contracts/` as Pydantic models, so a wrong shape fails loudly at the boundary instead
of deep inside another lane's code.

**Rule:** changing a contract changes every lane, so a contract change needs a PR that all three of
us review.

Section numbers (§) refer to the project report.

## Who produces and who consumes what

| Contract                                      | File             | Report         | Produced by           | Consumed by                       |
| --------------------------------------------- | ---------------- | -------------- | --------------------- | --------------------------------- |
| `Level`                                       | `level.py`       | §5.4.1, T. 5.3 | Learner State Module  | everything                        |
| `QueryInterpretation`                         | `scene_plan.py`  | §5.2.2         | Prompt Interpreter    | lesson planner, home screen       |
| `ScenePlan`, `LessonPlan`                     | `scene_plan.py`  | §5.2.3, T. 5.1 | Prompt Interpreter    | Code Generator, scheduler         |
| `Primitive`, `PrimitiveParams`                | `primitive.py`   | §5.3.1–5.3.4   | primitive library (B) | Code Generator, render engine     |
| `ModuleRenderRequest`                         | `render.py`      | §5.3.4, §5.4.4 | scheduler / pipeline  | render engine                     |
| `variant_cache_key()`                         | `render.py`      | §4.2.3, §5.3.4 | render engine         | scheduler, cache                  |
| `ModuleManifest`                              | `render.py`      | §5.4.4         | render engine         | player, Learner State, "I'm Lost" |
| `InteractionEvent`                            | `interaction.py` | §5.6.1, T. 5.4 | player                | Learner State Module              |
| Stream events                                 | `stream.py`      | §6.4.12        | application server    | player                            |
| `LessonStatus`, `RenderStatus`, `ModuleStyle` | `status.py`      | Table 4.8      | —                     | database, API                     |

Two worked examples, which the tests load, are in `backend/examples/`:

- `gradient_of_line.plan.json`: a scene plan with two segments and a worked-example branch.
- `gradient_of_line.render.json`: the render request for that plan at Level 2.

The `params` in the render request are illustrative. Each primitive defines its own parameter
schema in Phase 1, and the example is updated to match.

## What each contract guarantees

### `Level` (§5.4.1)

- Level 1 is supported, Level 2 is standard (the reference), and Level 3 is concise.
- `Level.label` gives the text that MODULE.difficulty_level stores, such as "Level 2" (Table 4.8).
- `Level.lower()` is the level an "I'm Lost" press switches to. It returns `None` at Level 1,
  where a press instead replays the segment with its chips open (§5.6.3).
- The target durations are 90 s at most for Level 1, about 60 s for Level 2, and under 60 s for
  Level 3 (Table 5.3).

### `ScenePlan` and `LessonPlan` (§5.2.3, Table 5.1)

- The fields are exactly those of Table 5.1. A plan has **no difficulty level**, and an unknown
  field such as `level` is rejected, because the same plan is rendered at every level.
- The segment list fixes the number and order of beats for every variant. In-flow substitution
  depends on this.
- `check_items` holds one or two bank items, never repeated (§5.7.3).
- `branch_options` offers theory and/or a worked example, each with its own scene plan (§5.6.4).
  A branch plan offers no branches of its own, because a chosen branch inserts one module and then
  the original plan resumes.
- A `LessonPlan` ends with the target concept, with missing prerequisites placed before it, and
  module ids are unique.
- These models are the **schema check** of §5.2.3. The **reference check** (primitives, glossary
  terms and check items exist, and every expression parses) needs the library and the taxonomy,
  so it belongs to the Prompt Interpreter (Phase 2).

### `QueryInterpretation` (§5.2.2)

The planning model returns either a target concept, or an out-of-scope flag together with the
nearest in-scope concepts to name in the reply.

### `Primitive` (§5.3.1)

A primitive has the four elements the report defines:

| Element               | In code                                                                                                                                |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Parameter schema      | `params_model`, a `PrimitiveParams` subclass with types and ranges. `params_json_schema()` is what constrained decoding uses (§5.3.3). |
| Validation predicates | `validate(params)` returns `PredicateFailure`s of kind parsing, domain or consistency, each with the predicate named (§5.3.3).         |
| Layout contract       | `layout`: the frame region the primitive may occupy, and which of its objects may overlap (§5.3.4).                                    |
| Difficulty hooks      | `steps(params, level)`: the animation steps at that level, with minimum durations and the number of labels and highlights.             |

It also has:

- `default_params()`: the validated defaults, used after three failed attempts (§5.3.3).
- `computed_values(params)`: every number shown on screen, computed by SymPy. The narration
  slots, such as `{gradient}`, are filled from these (§5.4.2).
- `animate(scene, params, level, run_times, carried)`: plays the steps with the run times the
  engine computed from the audio (§5.4.4). After each step it yields the visible objects by name,
  so the engine can run the layout check and record the step's timing.
- `add_final_state(scene, params, level)`: draws the segment's end state without animation. The
  next segment, rendered as its own scene, starts from this state, so the joined video shows no
  break (§5.3.4).
- `primitive_id`, `version` and `topic` (Table 5.2).

Contracts never import Manim at runtime, so they stay light to test.

### `ModuleRenderRequest` (§5.3.4, §5.4.4)

- One module, at one level, with one voice, against one primitive library version.
- Each beat carries a primitive, its validated parameters, and **one narration passage per
  animation step**. Every slot must already be filled, because numbers reach the narration only
  through slots (§5.4.2).
- `render_from_beat`: after an "I'm Lost" press in beat _j_, only beats _j_ onward are rendered at
  the lower level (§5.6.3). The earlier beats only supply the state carried into beat _j_.

### `variant_cache_key()` (§4.2.3, §5.3.4, §6.1.7)

The key is a sha256 hash of **exactly** the primitive identifiers, parameter sets, difficulty
level, narration voice and primitive library version, which is the list the report gives. The
tests check that changing any of these five changes the key, and that nothing else does (module
id, wording, or `render_from_beat`).

### `ModuleManifest` (§5.4.4)

- This is the segment manifest. For each beat it records the video file, duration, the start and
  end of every step with its passage, chip intervals and concept ids.
- Step and chip times are relative to the start of **the beat's own video**. The player plays
  beats as separate files (playback starts when the first beat is ready), and for the joined
  module video `beat_offsets_s()` gives each beat's start.
- A manifest describes a **variant**, identified by its cache key, and not one lesson's module.
  The same variant serves every module that reuses it.
- After an "I'm Lost" press a variant can hold only beats _j_ onward. `is_complete` reports when
  all beats are present, and only a complete variant has a joined `module_video`.

### `InteractionEvent` (§5.6.1, Table 4.8, Table 5.4)

- The event types are exactly those of INTERACTION_EVENT.event_type: rewind, speed change,
  pause, chip view, I'm Lost, and branch choice.
- Every playback event records the beat playing and the position within it. The Learner State
  Module uses the manifest to attribute the event to that beat's concepts.
- **Speed change** keeps one type and records the rate before and after. `slowed` tells
  "playback slowed" (difficulty) from "playback sped up" (ease), the two rows of Table 5.4.
- **Pause** records its duration, sent when playback resumes. Whether it counts as a "prolonged
  dwell" is decided by the Learner State Module's threshold (§5.7.4).
- **Rewind** records where it went back to, because the evidence is for the concepts of the
  beat returned to.
- **Branch choice** is theory, worked example, or the next step.
- Events never carry the student. The server takes the student from the session.
- Check answers are not interaction events. They are stored as CHECK_RESPONSE records.

### Stream events (§6.4.12, Fig. 6.2)

These are Server-Sent Events, one stream per lesson:

| Event                 | Meaning                                                                                                                          |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `generation_progress` | A module reached a stage: planning, parameters, narration or rendering.                                                          |
| `beat_ready`          | A beat is stored. Playback starts on the first one.                                                                              |
| `module_ready`        | Every beat of a module is ready at a level.                                                                                      |
| `module_failed`       | Generation failed after its retries. Also says whether a cached variant or the glossary definition replaced the module (§6.4.6). |

If the stream drops, the browser fetches the lesson status first, then reconnects.

## API sketch

All endpoints are REST over HTTPS, except the event stream (§6.4.12). This sketch fixes what each
endpoint is for. The exact request and response bodies are decided in the phase that builds each
endpoint.

| Method and path                                                                       | Purpose                                                                            | Report           |
| ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------- |
| `POST /api/auth/register`, `/login`, `/logout`                                        | Account, login, logout (password stored as a salted hash)                          | §4.2.1, UC 4.1   |
| `GET /api/diagnostic`, `POST /api/diagnostic/answers`                                 | Onboarding diagnostic, at most 5 items, resumable                                  | UC 4.2, §5.7.2   |
| `POST /api/lessons`                                                                   | Submit a topic query. Out of scope: lists the topics                               | UC 4.3           |
| `GET /api/lessons`, `GET /api/lessons/{id}`                                           | Lesson history; status and position, used to resume a lesson and after an SSE drop | §4.2.1, §6.4.12  |
| `GET /api/lessons/{id}/events`                                                        | Server-Sent Events stream (`stream.py`)                                            | §6.4.12          |
| `GET /api/variants/{cache_key}/manifest`                                              | The `ModuleManifest`; the beat videos are served next to it                        | §5.4.4           |
| `GET /api/glossary/{term}`                                                            | Definition shown in the chip overlay                                               | UC 4.5           |
| `POST /api/events`                                                                    | `InteractionEventBatch` from the player's logger                                   | §5.6.1           |
| `POST /api/lessons/{id}/im-lost`                                                      | "I'm Lost" during a module, with its beat                                          | UC 4.4           |
| `GET /api/lessons/{id}/check`, `POST /api/check-responses`                            | Check after a module, and the answer                                               | UC 4.6           |
| `POST /api/lessons/{id}/branch`                                                       | Option chosen at a branch point                                                    | UC 4.7           |
| `GET /api/progress`                                                                   | Per-concept confidence                                                             | §4.2.1, Fig. 4.6 |
| `/api/admin/primitives`, `/glossary`, `/check-questions`, `/render-jobs`, `/students` | Administrator functions                                                            | §4.2.2           |

## Choices to review

The report does not fix the following details. These are the choices made in the contracts.
Please check them together, because a change later costs more.

1. **Ids are positive integers**, as in the data dictionary (Table 4.8).
2. **Expressions are SymPy-syntax strings**, for example `"x**2"` or `"(8 - 2)/(4 - 1)"`.
3. **A frame region is given in fractions of the frame** (0 to 1 from the bottom left), so it does
   not depend on render resolution. Allowed overlaps are listed as pairs of object names, and `"*"`
   means any object.
4. **Manifest times are relative to each beat's own video**, as described above.
5. **`render_from_beat`** is how a request asks for beats _j_ onward after an "I'm Lost" press.
6. **Playback rates** run from 0.25× to 4×.
7. **An event batch** holds at most 100 events.
