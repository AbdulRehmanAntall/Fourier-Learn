"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useReducer, useState } from "react";

import { ApiError } from "@/lib/api/client";
import {
  fetchCurrentModule,
  fetchLesson,
  finishModule,
  playerKeys,
  useManifest,
} from "@/lib/api/hooks/player";
import { useLessonStream } from "@/lib/api/sse";

import { CheckPanel } from "./CheckPanel";
import type { EventLogger } from "./eventLogger";
import { GeneratingScreen, Spinner } from "./GeneratingScreen";
import {
  initialLessonState,
  lessonReducer,
  type LessonState,
  type Playback,
} from "./lessonMachine";
import { LessonSummary } from "./LessonSummary";
import { ModuleFailed } from "./ModuleFailed";
import {
  DEFAULT_SETTINGS,
  ModulePlayer,
  type PlaybackTracker,
  type PlayerSettings,
} from "./ModulePlayer";
import { PreparingNext } from "./PreparingNext";
import { useEventLogger } from "./useEventLogger";
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

  useLessonStream(lessonId, {
    onOpen() {
      // Events from before the stream opened are lost, so look again (§6.11).
      void queryClient.invalidateQueries({ queryKey: playerKeys.lesson(lessonId) });
      if (isWaiting(state) || state.kind === "playing") refresh();
    },
    onEvent(event) {
      switch (event.type) {
        case "generation_progress":
          dispatch({ type: "stageChanged", stage: event.stage });
          break;
        case "beat_ready":
        case "module_ready":
          if (state.kind === "playing" && event.cache_key === state.cacheKey) {
            // A partial manifest grows as beats are stored (§6.2).
            void queryClient.invalidateQueries({ queryKey: playerKeys.manifest(state.cacheKey) });
          } else if (isWaiting(state)) {
            refresh();
          }
          break;
        case "module_failed":
          if (isWaiting(state) || state.kind === "playing") refresh();
          break;
      }
    },
  });

  switch (state.kind) {
    case "loading":
      return <Centered label="Loading your lesson…" />;
    case "generating":
      return <GeneratingScreen stage={state.stage} />;
    case "preparing":
    case "nextModule":
      return <PreparingNext />;
    case "playing":
      return (
        <Playing
          // A new module, or a new variant after "I'm Lost", starts a fresh stage.
          key={`${state.module.id}:${state.cacheKey}`}
          lessonId={lessonId}
          logger={logger}
          playback={state}
          chips={lesson.data?.mode === "adaptive"}
          settings={settings}
          onSettingsChange={setSettings}
          onModuleEnded={() => dispatch({ type: "moduleEnded" })}
        />
      );
    case "imLost":
      // Stands in for ImLostOverlay over the paused video (§6.7) until "I'm Lost" is built.
      return <Centered label="Making a simpler version…" />;
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
        <NotBuiltYet
          title="Where should the lesson go next?"
          onContinue={() => dispatch({ type: "branchDone" })}
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

function isWaiting(state: LessonState) {
  return state.kind === "generating" || state.kind === "preparing";
}

function Playing({
  lessonId,
  logger,
  playback,
  chips,
  settings,
  onSettingsChange,
  onModuleEnded,
}: {
  lessonId: number;
  logger: EventLogger;
  playback: Playback;
  chips: boolean;
  settings: PlayerSettings;
  onSettingsChange(settings: PlayerSettings): void;
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
      chips={chips}
      tracker={tracker}
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

/** Stands in for the branch panel until it's built; Continue moves on without choosing, so
 * nothing is recorded. */
function NotBuiltYet({ title, onContinue }: { title: string; onContinue(): void }) {
  return (
    <div className="flex flex-col items-start gap-4 rounded-lg border border-dashed border-current/30 p-6">
      <h2 className="text-xl font-semibold">{title}</h2>
      <p className="opacity-70">This step isn&apos;t built yet.</p>
      <button
        type="button"
        onClick={onContinue}
        className="h-11 rounded-full bg-blue-600 px-6 font-semibold text-white hover:bg-blue-700"
      >
        Continue
      </button>
    </div>
  );
}
