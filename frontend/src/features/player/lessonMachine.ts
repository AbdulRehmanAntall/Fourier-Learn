import type { Schemas } from "@/lib/api/client";

import type { BeatPosition } from "./useTimeline";

// The lesson state machine of docs/frontend.md §6.1, as a plain reducer. Components dispatch
// events to it; the effects (API calls, video commands) run in LessonPlayer's hooks. Every
// decision it makes comes from an API response (rule 1): it never picks a level, a next module
// or an answer itself.

type ModuleSummary = Schemas["ModuleSummary"];
type CurrentModule = Schemas["CurrentModule"];
type Level = Schemas["Level"];
export type GenerationStage = NonNullable<CurrentModule["stage"]>;

/** A variant being played: which module, which render, and where it starts. */
export type Playback = {
  module: ModuleSummary;
  cacheKey: string;
  level: Level;
  start: BeatPosition;
  /** Started from a saved position after a reload: wait for a tap (autoplay is blocked). */
  resumed: boolean;
};

/** The simpler variant "I'm Lost" asked for: where it is, and the beat to start from. */
export type SimplerVariant = { cacheKey: string; level: Level; beat: number };

export type LessonState =
  | { kind: "loading" }
  | { kind: "generating"; stage: GenerationStage | null }
  | ({
      kind: "playing";
      /** The student chose to keep watching while a simpler variant is made. It is offered
       * once it is ready, not switched to (§6.7). */
      simpler?: { target: SimplerVariant; ready: boolean };
    } & Playback)
  | { kind: "imLost"; playing: Playback; target: SimplerVariant }
  | { kind: "moduleEnded"; module: ModuleSummary }
  | {
      kind: "check";
      module: ModuleSummary;
      items: Schemas["CheckItem"][];
      branch: Schemas["BranchPoint"] | null;
    }
  | { kind: "branch"; module: ModuleSummary; branch: Schemas["BranchPoint"] }
  | { kind: "nextModule" }
  | { kind: "preparing"; stage: GenerationStage | null }
  | { kind: "failed"; module: ModuleSummary; failure: Schemas["ModuleFailure"] }
  | { kind: "complete" }
  /** A request failed; `retry` is the state that made it, so Try again makes it again. */
  | { kind: "error"; message: string; retry: LessonState };

export type LessonEvent =
  /** `GET current-module` answered (after loading, a stream event, or a finished module). */
  | { type: "moduleLoaded"; current: CurrentModule; position?: Schemas["Position"] | null }
  | { type: "stageChanged"; stage: GenerationStage }
  | { type: "moduleEnded" }
  /** `finish` answered with the module's check items and branch point. */
  | { type: "finished"; end: Schemas["ModuleEnd"] }
  | { type: "checkDone" }
  | { type: "branchDone" }
  /** The im-lost endpoint chose a simpler variant (Level 2 or 3). */
  | { type: "imLostSubstitute"; cacheKey: string; level: Level; beat: number }
  /** The simpler variant's beat j can be played. */
  | { type: "imLostReady" }
  /** "Keep watching at this level" after the wait ran long. */
  | { type: "imLostCancelled" }
  /** "Switch to the simpler version", when it arrived after the student kept watching. */
  | { type: "switchToSimpler" }
  /** Continue past a failed module: finish it, which returns no checks or branch. */
  | { type: "continueAfterFailure" }
  | { type: "requestFailed"; message: string }
  | { type: "retry" };

export const initialLessonState: LessonState = { kind: "loading" };

export function lessonReducer(state: LessonState, event: LessonEvent): LessonState {
  switch (event.type) {
    case "moduleLoaded":
      return onModuleLoaded(state, event.current, event.position ?? null);

    case "stageChanged":
      return state.kind === "generating" || state.kind === "preparing"
        ? { ...state, stage: event.stage }
        : state;

    case "moduleEnded":
      return state.kind === "playing" ? { kind: "moduleEnded", module: state.module } : state;

    case "finished": {
      if (state.kind !== "moduleEnded") return state;
      const { check_items: items, branch } = event.end;
      if (items.length > 0) return { kind: "check", module: state.module, items, branch };
      if (branch) return { kind: "branch", module: state.module, branch };
      return { kind: "nextModule" };
    }

    case "checkDone":
      if (state.kind !== "check") return state;
      return state.branch
        ? { kind: "branch", module: state.module, branch: state.branch }
        : { kind: "nextModule" };

    case "branchDone":
      return state.kind === "branch" ? { kind: "nextModule" } : state;

    case "imLostSubstitute":
      if (state.kind !== "playing") return state;
      return {
        kind: "imLost",
        playing: withoutKind(state),
        target: { cacheKey: event.cacheKey, level: event.level, beat: event.beat },
      };

    case "imLostReady":
      if (state.kind === "imLost") return playSimpler(state.playing, state.target);
      return state.kind === "playing" && state.simpler
        ? { ...state, simpler: { ...state.simpler, ready: true } }
        : state;

    case "imLostCancelled":
      return state.kind === "imLost"
        ? {
            kind: "playing",
            ...state.playing,
            simpler: { target: state.target, ready: false },
          }
        : state;

    case "switchToSimpler":
      return state.kind === "playing" && state.simpler?.ready
        ? playSimpler(state, state.simpler.target)
        : state;

    case "continueAfterFailure":
      return state.kind === "failed" ? { kind: "moduleEnded", module: state.module } : state;

    case "requestFailed":
      // Only the states whose own request is the lesson's next step stop on a failure.
      return state.kind === "loading" || state.kind === "nextModule" || state.kind === "moduleEnded"
        ? { kind: "error", message: event.message, retry: state }
        : state;

    case "retry":
      return state.kind === "error" ? state.retry : state;
  }
}

function onModuleLoaded(
  state: LessonState,
  current: CurrentModule,
  position: Schemas["Position"] | null,
): LessonState {
  const waiting = state.kind === "generating" || state.kind === "preparing";
  // While a module plays, only its failure changes anything; a ready answer is the module
  // already playing.
  if (state.kind === "playing") {
    return current.status === "failed" && current.module?.id === state.module.id
      ? { kind: "failed", module: state.module, failure: current.failure! }
      : state;
  }
  if (state.kind === "imLost") {
    return current.status === "failed" && current.module?.id === state.playing.module.id
      ? { kind: "failed", module: state.playing.module, failure: current.failure! }
      : state;
  }
  if (state.kind !== "loading" && state.kind !== "nextModule" && !waiting) return state;

  switch (current.status) {
    case "ready": {
      const next = current.module!;
      const resume = state.kind === "loading" && position?.module_id === next.id;
      return {
        kind: "playing",
        module: next,
        cacheKey: current.cache_key!,
        level: current.level!,
        start: resume
          ? { beat: position.beat_index, time_s: position.position_s }
          : { beat: 0, time_s: 0 },
        resumed: resume,
      };
    }
    case "preparing": {
      const stage = current.stage ?? null;
      // The first module is generated with the student watching; later ones while the
      // previous one played.
      if (state.kind === "loading" || state.kind === "generating") {
        return { kind: "generating", stage };
      }
      return { kind: "preparing", stage };
    }
    case "failed":
      return { kind: "failed", module: current.module!, failure: current.failure! };
    case "complete":
      return { kind: "complete" };
  }
}

/** The rest of the module plays at the lower level, from the start of beat j (§6.7). */
function playSimpler({ module }: Playback, target: SimplerVariant): LessonState {
  return {
    kind: "playing",
    module,
    cacheKey: target.cacheKey,
    level: target.level,
    start: { beat: target.beat, time_s: 0 },
    resumed: false,
  };
}

function withoutKind({ module, cacheKey, level, start, resumed }: Playback): Playback {
  return { module, cacheKey, level, start, resumed };
}
