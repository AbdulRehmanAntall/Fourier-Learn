import { describe, expect, it } from "vitest";

import type { Schemas } from "@/lib/api/client";

import {
  initialLessonState,
  lessonReducer,
  type LessonEvent,
  type LessonState,
} from "./lessonMachine";

// Every transition of docs/frontend.md §6.1, plus resume and retry.

const module1: Schemas["ModuleSummary"] = {
  id: 11,
  sequence_no: 1,
  title: "Gradient of a line",
  concept_id: 3,
  style: "default",
  is_review: false,
  render_status: "ready",
  level: 2,
  completed: false,
};

const ready: Schemas["CurrentModule"] = {
  status: "ready",
  module: module1,
  level: 2,
  cache_key: "abc",
};
const preparing: Schemas["CurrentModule"] = {
  status: "preparing",
  module: module1,
  level: null,
  cache_key: null,
  stage: "narration",
};
const failure: Schemas["ModuleFailure"] = {
  fallback: "glossary_definition",
  message: "We couldn't make this module.",
  definition: "The gradient is rise over run.",
};
const failed: Schemas["CurrentModule"] = { ...preparing, status: "failed", failure };
const complete: Schemas["CurrentModule"] = {
  status: "complete",
  module: null,
  level: null,
  cache_key: null,
};

const item: Schemas["CheckItem"] = {
  id: 5,
  concept_id: 3,
  item_type: "true_false",
  question_text: "A horizontal line has gradient 0.",
  options: ["True", "False"],
};
const branch: Schemas["BranchPoint"] = {
  options: [
    { choice: "theory", title: "More theory", description: "Why it works" },
    { choice: "next_step", title: "Next step", description: "Keep going" },
  ],
  default_choice: "next_step",
  timeout_s: 15,
};

const run = (events: LessonEvent[], from: LessonState = initialLessonState) =>
  events.reduce(lessonReducer, from);
const playing = run([{ type: "moduleLoaded", current: ready }]);
const ended = run([{ type: "moduleEnded" }], playing);

describe("loading", () => {
  it("plays a ready module from its first beat", () => {
    expect(playing).toEqual({
      kind: "playing",
      module: module1,
      cacheKey: "abc",
      level: 2,
      start: { beat: 0, time_s: 0 },
      resumed: false,
    });
  });

  it("resumes from the saved position of the same module", () => {
    const position = { module_id: 11, beat_index: 2, position_s: 7.5 };
    const state = run([{ type: "moduleLoaded", current: ready, position }]);
    expect(state).toMatchObject({ start: { beat: 2, time_s: 7.5 }, resumed: true });
  });

  it("ignores a saved position from another module", () => {
    const position = { module_id: 99, beat_index: 2, position_s: 7.5 };
    const state = run([{ type: "moduleLoaded", current: ready, position }]);
    expect(state).toMatchObject({ start: { beat: 0, time_s: 0 }, resumed: false });
  });

  it("shows the generating screen while the first module is made", () => {
    expect(run([{ type: "moduleLoaded", current: preparing }])).toEqual({
      kind: "generating",
      stage: "narration",
    });
  });

  it("shows a failed or finished lesson as it is", () => {
    expect(run([{ type: "moduleLoaded", current: failed }])).toEqual({
      kind: "failed",
      module: module1,
      failure,
    });
    expect(run([{ type: "moduleLoaded", current: complete }])).toEqual({ kind: "complete" });
  });
});

describe("generating and preparing", () => {
  it("follows the stage, then plays once the first beat is ready", () => {
    const generating = run([
      { type: "moduleLoaded", current: preparing },
      { type: "stageChanged", stage: "rendering" },
    ]);
    expect(generating).toEqual({ kind: "generating", stage: "rendering" });
    expect(run([{ type: "moduleLoaded", current: ready }], generating).kind).toBe("playing");
  });

  it("prepares the next module and plays it when it is ready", () => {
    const next = run([{ type: "moduleLoaded", current: preparing }], { kind: "nextModule" });
    expect(next).toEqual({ kind: "preparing", stage: "narration" });
    expect(run([{ type: "moduleLoaded", current: ready }], next).kind).toBe("playing");
  });

  it("ignores a stage change when nothing is being made", () => {
    expect(run([{ type: "stageChanged", stage: "planning" }], playing)).toBe(playing);
  });
});

describe("between modules", () => {
  it("goes to the check when finish returns items, then to the branch", () => {
    const check = run([{ type: "finished", end: { check_items: [item], branch } }], ended);
    expect(check).toEqual({ kind: "check", module: module1, items: [item], branch });
    const choosing = run([{ type: "checkDone" }], check);
    expect(choosing).toEqual({ kind: "branch", module: module1, branch });
    expect(run([{ type: "branchDone" }], choosing)).toEqual({ kind: "nextModule" });
  });

  it("goes from the check to the next module when there is no branch", () => {
    const check = run([{ type: "finished", end: { check_items: [item], branch: null } }], ended);
    expect(run([{ type: "checkDone" }], check)).toEqual({ kind: "nextModule" });
  });

  it("goes straight to the branch when there are no items", () => {
    expect(run([{ type: "finished", end: { check_items: [], branch } }], ended)).toEqual({
      kind: "branch",
      module: module1,
      branch,
    });
  });

  it("goes straight to the next module with neither", () => {
    expect(run([{ type: "finished", end: { check_items: [], branch: null } }], ended)).toEqual({
      kind: "nextModule",
    });
  });

  it("plays the next module, or ends the lesson", () => {
    const next: LessonState = { kind: "nextModule" };
    expect(run([{ type: "moduleLoaded", current: ready }], next).kind).toBe("playing");
    expect(run([{ type: "moduleLoaded", current: complete }], next)).toEqual({
      kind: "complete",
    });
  });

  it("starts the next module at its first beat, even with a saved position", () => {
    const position = { module_id: 11, beat_index: 2, position_s: 7.5 };
    const state = run([{ type: "moduleLoaded", current: ready, position }], {
      kind: "nextModule",
    });
    expect(state).toMatchObject({ start: { beat: 0, time_s: 0 }, resumed: false });
  });
});

describe("a failed module", () => {
  it("fails during playback when the playing module fails", () => {
    expect(run([{ type: "moduleLoaded", current: failed }], playing)).toEqual({
      kind: "failed",
      module: module1,
      failure,
    });
  });

  it("keeps playing when another module's status comes back", () => {
    const other = { ...failed, module: { ...module1, id: 12 } };
    expect(run([{ type: "moduleLoaded", current: other }], playing)).toBe(playing);
    expect(run([{ type: "moduleLoaded", current: ready }], playing)).toBe(playing);
  });

  it("fails when the next module has failed, and Continue finishes it", () => {
    const state = run([{ type: "moduleLoaded", current: failed }], { kind: "nextModule" });
    expect(state.kind).toBe("failed");
    expect(run([{ type: "continueAfterFailure" }], state)).toEqual({
      kind: "moduleEnded",
      module: module1,
    });
  });
});

describe("I'm Lost", () => {
  const lost = run([{ type: "imLostSubstitute", cacheKey: "simpler", level: 1, beat: 1 }], playing);

  it("waits for the simpler variant, then plays it from the start of beat j", () => {
    expect(lost.kind).toBe("imLost");
    expect(run([{ type: "imLostReady" }], lost)).toEqual({
      kind: "playing",
      module: module1,
      cacheKey: "simpler",
      level: 1,
      start: { beat: 1, time_s: 0 },
      resumed: false,
    });
  });

  const keptWatching = run([{ type: "imLostCancelled" }], lost);
  const simpler = { cacheKey: "simpler", level: 1, beat: 1 };

  it("goes back to the old variant when the student keeps watching", () => {
    expect(keptWatching).toEqual({ ...playing, simpler: { target: simpler, ready: false } });
  });

  it("offers the simpler variant when it arrives later, without switching to it", () => {
    const offered = run([{ type: "imLostReady" }], keptWatching);
    expect(offered).toMatchObject({ cacheKey: "abc", simpler: { ready: true } });
    expect(run([{ type: "switchToSimpler" }], offered)).toMatchObject({
      kind: "playing",
      cacheKey: "simpler",
      level: 1,
      start: { beat: 1, time_s: 0 },
    });
  });

  it("does not switch before the simpler variant is ready", () => {
    expect(run([{ type: "switchToSimpler" }], keptWatching)).toBe(keptWatching);
    expect(run([{ type: "switchToSimpler" }], playing)).toBe(playing);
  });

  it("ignores a late ready when nothing is waiting for it", () => {
    expect(run([{ type: "imLostReady" }], playing)).toBe(playing);
  });

  it("fails if the module fails during the wait", () => {
    expect(run([{ type: "moduleLoaded", current: failed }], lost)).toEqual({
      kind: "failed",
      module: module1,
      failure,
    });
  });

  it("keeps waiting when the module is still ready", () => {
    expect(run([{ type: "moduleLoaded", current: ready }], lost)).toBe(lost);
  });

  it("doesn't carry a pending offer into a new press", () => {
    const again = run(
      [{ type: "imLostSubstitute", cacheKey: "other", level: 1, beat: 2 }],
      keptWatching,
    );
    expect(again).toMatchObject({ kind: "imLost", playing: { cacheKey: "abc" } });
    expect(again).not.toHaveProperty("playing.simpler");
  });
});

describe("errors", () => {
  it("stops a failed request with a retry that makes it again", () => {
    const error = run([{ type: "requestFailed", message: "offline" }]);
    expect(error).toEqual({ kind: "error", message: "offline", retry: { kind: "loading" } });
    expect(run([{ type: "retry" }], error)).toEqual({ kind: "loading" });
  });

  it("retries a failed finish for the same module", () => {
    const error = run([{ type: "requestFailed", message: "offline" }], ended);
    expect(run([{ type: "retry" }], error)).toEqual(ended);
  });

  it("doesn't interrupt playback", () => {
    expect(run([{ type: "requestFailed", message: "offline" }], playing)).toBe(playing);
  });
});
