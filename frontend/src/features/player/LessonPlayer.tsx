"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useReducer, useRef, useState, type ReactNode } from "react";

import { ApiError } from "@/lib/api/client";
import {
  fetchCurrentModule,
  fetchLesson,
  fetchManifest,
  finishModule,
  playerKeys,
  pressImLost,
  useManifest,
} from "@/lib/api/hooks/player";
import { useLessonStream } from "@/lib/api/sse";

import { BranchPanel } from "./BranchPanel";
import { CheckPanel } from "./CheckPanel";
import type { EventLogger } from "./eventLogger";
import { GeneratingScreen, Spinner } from "./GeneratingScreen";
import {
  initialLessonState,
  lessonReducer,
  type LessonState,
  type Playback,
  type SimplerVariant,
} from "./lessonMachine";
import { ImLostOverlay } from "./ImLostOverlay";
import { LessonSummary } from "./LessonSummary";
import { ModuleFailed } from "./ModuleFailed";
import {
  DEFAULT_SETTINGS,
  ModulePlayer,
  type ImLostOutcome,
  type PlaybackTracker,
  type PlayerSettings,
} from "./ModulePlayer";
import { PreparingNext } from "./PreparingNext";
import { useEventLogger } from "./useEventLogger";
import type { BeatPosition } from "./useTimeline";
import { usePositionSaver } from "./usePositionSaver";

// The lesson page's top component (docs/frontend.md §6): runs the state machine of §6.1 and
// makes the request each state needs. The event stream (§6.11) moves it on while a module is
// being made, and keeps a partial manifest up to date while one plays.

const messageOf = (error: unknown) =>
  error instanceof ApiError ? error.message : "Something went wrong. Please try again.";

export function LessonPlayer({ lessonId }: { lessonId: number }) {
  const queryClient = useQueryClient();
  const [state, dispatch] = useReducer(lessonReducer, initialLessonState);
  const logger = useEventLogger();
  // Beats stored while an "I'm Lost" request is in flight: its beat_ready can arrive before its
  // reply does, and would otherwise be missed.
  const beatsSeen = useRef(new Set<string>());
  // Kept for the whole lesson, so the rate and captions carry over between modules (§6.5).
  const [settings, setSettings] = useState<PlayerSettings>(DEFAULT_SETTINGS);
  const lesson = useQuery({
    queryKey: playerKeys.lesson(lessonId),
    queryFn: () => fetchLesson(lessonId),
  });

  // The request each state is waiting on. A state that needs one makes it once, on entry.
  useEffect(() => {
    let cancelled = false;
    const failed = (error: unknown) =>
      cancelled || dispatch({ type: "requestFailed", message: messageOf(error) });

    if (state.kind === "loading") {
      Promise.all([
        queryClient.fetchQuery({
          queryKey: playerKeys.lesson(lessonId),
          queryFn: () => fetchLesson(lessonId),
          staleTime: 0,
        }),
        fetchCurrentModule(lessonId),
      ]).then(([loaded, current]) => {
        if (!cancelled) dispatch({ type: "moduleLoaded", current, position: loaded.position });
      }, failed);
    } else if (state.kind === "nextModule") {
      fetchCurrentModule(lessonId).then((current) => {
        if (!cancelled) dispatch({ type: "moduleLoaded", current });
      }, failed);
    } else if (state.kind === "moduleEnded") {
      // Events first: finishing applies the learning transition, which reads them (§6.8).
      const moduleId = state.module.id;
      logger
        .flush()
        .then(() => finishModule(lessonId, moduleId))
        .then((end) => {
          if (!cancelled) dispatch({ type: "finished", end });
        }, failed);
    }
    return () => {
      cancelled = true;
    };
  }, [state, lessonId, queryClient, logger]);

  // Ask again where the lesson is, after a stream event or a reconnect. A failure here is not
  // shown: the next event or reconnect asks again.
  function refresh() {
    fetchCurrentModule(lessonId).then(
      (current) => dispatch({ type: "moduleLoaded", current }),
      () => {},
    );
  }

  async function imLost(moduleId: number, at: BeatPosition): Promise<ImLostOutcome> {
    beatsSeen.current.clear();
    try {
      const result = await pressImLost(lessonId, {
        module_id: moduleId,
        beat_index: at.beat,
        position_s: at.time_s,
      });
      if (result.action === "replay") {
        // A worked example may have been added, which the lesson summary lists.
        void queryClient.invalidateQueries({ queryKey: playerKeys.lesson(lessonId) });
        return {
          kind: "replay",
          beat: result.resume_beat_index,
          workedExampleAdded: result.worked_example_added,
        };
      }
      const beat = result.resume_beat_index;
      dispatch({
        type: "imLostSubstitute",
        cacheKey: result.cache_key,
        level: result.level,
        beat,
      });
      if (result.ready || beatsSeen.current.has(beatKey(moduleId, result.cache_key, beat))) {
        dispatch({ type: "imLostReady" });
      }
      return { kind: "substituting" };
    } catch (error) {
      return { kind: "failed", message: messageOf(error) };
    }
  }

  useLessonStream(lessonId, {
    onOpen() {
      // Events from before the stream opened are lost, so look again (§6.11).
      void queryClient.invalidateQueries({ queryKey: playerKeys.lesson(lessonId) });
      if (isWaiting(state) || state.kind === "playing" || state.kind === "imLost") refresh();
      const target = awaitedVariant(state);
      if (target) {
        fetchManifest(target.cacheKey).then(
          ({ beats }) => {
            if (beats.some((beat) => beat.index === target.beat)) {
              dispatch({ type: "imLostReady" });
            }
          },
          () => {},
        );
      }
    },
    onEvent(event) {
      switch (event.type) {
        case "generation_progress":
          dispatch({ type: "stageChanged", stage: event.stage });
          break;
        case "beat_ready":
        case "module_ready": {
          const target = awaitedVariant(state);
          if (event.type === "beat_ready") {
            beatsSeen.current.add(beatKey(event.module_id, event.cache_key, event.beat_index));
            if (
              event.module_id === target?.moduleId &&
              event.cache_key === target.cacheKey &&
              event.beat_index === target.beat
            ) {
              dispatch({ type: "imLostReady" });
            }
          }
          if (state.kind === "playing" && event.cache_key === state.cacheKey) {
            // A partial manifest grows as beats are stored (§6.2).
            void queryClient.invalidateQueries({ queryKey: playerKeys.manifest(state.cacheKey) });
          } else if (isWaiting(state)) {
            refresh();
          }
          break;
        }
        case "module_failed":
          if (isWaiting(state) || state.kind === "playing" || state.kind === "imLost") refresh();
          break;
      }
    },
  });

  const adaptive = lesson.data?.mode === "adaptive";
  const playing = (playback: Playback, overlay?: ReactNode, banner?: ReactNode) => (
    <Playing
      // A new module, or a new variant after "I'm Lost", starts a fresh stage. The same variant
      // keeps its stage, so the video stays in place behind the "I'm Lost" overlay.
      key={`${playback.module.id}:${playback.cacheKey}`}
      lessonId={lessonId}
      logger={logger}
      playback={playback}
      adaptive={adaptive}
      settings={settings}
      onSettingsChange={setSettings}
      onImLost={imLost}
      overlay={overlay}
      banner={banner}
      onModuleEnded={() => dispatch({ type: "moduleEnded" })}
    />
  );

  switch (state.kind) {
    case "loading":
      return <Centered label="Loading your lesson…" />;
    case "generating":
      return <GeneratingScreen stage={state.stage} />;
    case "preparing":
    case "nextModule":
      return <PreparingNext />;
    case "playing":
      return playing(
        state,
        undefined,
        state.simpler?.ready && (
          <div
            role="status"
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-current/20 px-4 py-2"
          >
            <p>The simpler version is ready.</p>
            <button
              type="button"
              onClick={() => dispatch({ type: "switchToSimpler" })}
              className="h-11 rounded-full bg-blue-600 px-5 font-semibold text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2"
            >
              Switch to the simpler version
            </button>
          </div>
        ),
      );
    case "imLost":
      return playing(
        state.playing,
        <ImLostOverlay onKeepWatching={() => dispatch({ type: "imLostCancelled" })} />,
      );
    case "moduleEnded":
      return <Centered label="Saving your progress…" />;
    case "check":
      return (
        <CheckPanel
          moduleId={state.module.id}
          items={state.items}
          onDone={() => dispatch({ type: "checkDone" })}
        />
      );
    case "branch":
      return (
        <BranchPanel
          lessonId={lessonId}
          moduleId={state.module.id}
          branch={state.branch}
          onDone={() => {
            // A chosen option may add a module, which the lesson summary lists.
            void queryClient.invalidateQueries({ queryKey: playerKeys.lesson(lessonId) });
            dispatch({ type: "branchDone" });
          }}
        />
      );
    case "failed":
      return (
        <ModuleFailed
          failure={state.failure}
          onContinue={() => dispatch({ type: "continueAfterFailure" })}
        />
      );
    case "complete":
      return <LessonSummary lesson={lesson.data} />;
    case "error":
      return <ErrorPanel message={state.message} onRetry={() => dispatch({ type: "retry" })} />;
  }
}

const beatKey = (moduleId: number, cacheKey: string, beat: number) =>
  `${moduleId}:${cacheKey}:${beat}`;

/** The simpler variant an "I'm Lost" press is still waiting for, if any, and for which module:
 * the stream carries other modules' beats too, and variants can be shared between modules. */
function awaitedVariant(state: LessonState): (SimplerVariant & { moduleId: number }) | null {
  if (state.kind === "imLost") return { ...state.target, moduleId: state.playing.module.id };
  if (state.kind === "playing" && state.simpler && !state.simpler.ready) {
    return { ...state.simpler.target, moduleId: state.module.id };
  }
  return null;
}

function isWaiting(state: LessonState) {
  return state.kind === "generating" || state.kind === "preparing";
}

function Playing({
  lessonId,
  logger,
  playback,
  adaptive,
  settings,
  onSettingsChange,
  onImLost,
  overlay,
  banner,
  onModuleEnded,
}: {
  lessonId: number;
  logger: EventLogger;
  playback: Playback;
  adaptive: boolean;
  settings: PlayerSettings;
  onSettingsChange(settings: PlayerSettings): void;
  onImLost(moduleId: number, at: BeatPosition): Promise<ImLostOutcome>;
  overlay?: ReactNode;
  banner?: ReactNode;
  onModuleEnded(): void;
}) {
  const manifest = useManifest(playback.cacheKey);
  const { id: moduleId, sequence_no, title } = playback.module;
  const saver = usePositionSaver(lessonId, moduleId);
  const tracker: PlaybackTracker = {
    progress: saver.progress,
    playingChanged: saver.playingChanged,
    studentSeeked: (from, to) => logger.seeked(moduleId, from, to),
    studentPaused: (at) => logger.paused(moduleId, at),
    studentResumed: () => logger.endPause(),
    speedChanged: (at, from, to) => logger.speedChanged(moduleId, at, from, to),
    chipOpened: (at, term) => logger.chipOpened(moduleId, at, term),
  };

  if (manifest.isPending) return <Centered label="Loading the video…" />;
  if (manifest.isError) {
    return <ErrorPanel message={messageOf(manifest.error)} onRetry={() => manifest.refetch()} />;
  }
  return (
    <ModulePlayer
      manifest={manifest.data}
      settings={settings}
      onSettingsChange={onSettingsChange}
      start={playback.start}
      // After a reload the browser blocks sound until a tap, so ask for one (§6.2).
      autoPlay={!playback.resumed}
      startPrompt={playback.resumed ? "Resume" : undefined}
      chips={adaptive}
      tracker={tracker}
      onImLost={adaptive ? (at) => onImLost(moduleId, at) : undefined}
      overlay={overlay}
      banner={banner}
      heading={
        <>
          <span className="font-semibold">Module {sequence_no}</span> · {title}
        </>
      }
      onModuleEnded={onModuleEnded}
    />
  );
}

function Centered({ label }: { label: string }) {
  return (
    <div
      role="status"
      className="flex aspect-video flex-col items-center justify-center gap-4 rounded-lg border border-current/15"
    >
      <Spinner />
      <p>{label}</p>
    </div>
  );
}

function ErrorPanel({ message, onRetry }: { message: string; onRetry(): void }) {
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-4 rounded-lg border border-current/15 p-6"
    >
      <p className="text-lg">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="h-11 rounded-full border border-current/30 px-6 font-semibold hover:bg-current/10"
      >
        Try again
      </button>
    </div>
  );
}
