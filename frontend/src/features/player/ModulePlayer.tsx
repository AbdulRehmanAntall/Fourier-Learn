"use client";

import { useEffect, useEffectEvent, useRef, useState, type ReactNode } from "react";

import type { Schemas } from "@/lib/api/client";

import { Captions } from "./Captions";
import { ChipBar } from "./ChipBar";
import { ChipOverlay } from "./ChipOverlay";
import { Controls } from "./Controls";
import { ImLostButton } from "./ImLostButton";
import { ReplayDefinitions } from "./ReplayDefinitions";
import { chipsAt, forward, rewind, type BeatPosition, useTimeline } from "./useTimeline";
import { VideoStage, type VideoStageHandle } from "./VideoStage";

// Plays one variant of a module: the video stage, captions and controls, with the keyboard
// shortcuts of docs/frontend.md §6.5. The settings belong to whoever renders it (LessonPlayer),
// so the rate and captions carry over between modules.

export type PlayerSettings = { rate: number; volume: number; muted: boolean; captions: boolean };

export const DEFAULT_SETTINGS: PlayerSettings = {
  rate: 1,
  volume: 1,
  muted: false,
  captions: true,
};

/** What the player reports while a lesson is tracked (event logging, saving the position). The
 * "student" methods are called from the controls and shortcuts, never from <video> events, so
 * pauses and seeks the player makes itself are not mistaken for the student (§6.10). */
export type PlaybackTracker = {
  progress(position: BeatPosition): void;
  playingChanged(playing: boolean): void;
  studentSeeked(from: BeatPosition, to: BeatPosition): void;
  studentPaused(at: BeatPosition): void;
  studentResumed(): void;
  speedChanged(at: BeatPosition, fromRate: number, toRate: number): void;
  chipOpened(at: BeatPosition, term: string): void;
};

/** How an "I'm Lost" press turned out. `substituting` means the page has taken over: it shows
 * `overlay` until the simpler variant is ready or the student keeps watching. */
export type ImLostOutcome =
  | { kind: "substituting" }
  | { kind: "replay"; beat: number; workedExampleAdded: boolean }
  | { kind: "failed"; message: string };

const NOTICE_MS = 6000;

type Props = {
  manifest: Schemas["ModuleManifest"];
  settings: PlayerSettings;
  onSettingsChange(settings: PlayerSettings): void;
  start?: BeatPosition;
  /** Try to start playing at once. The browser may refuse; the stage then shows a Play button. */
  autoPlay?: boolean;
  /** A large button over the video until playback starts, e.g. "Resume" after a reload. */
  startPrompt?: string;
  /** Left of the header, e.g. "Module 2 · Gradient of a curve". Defaults to the beat number. */
  heading?: ReactNode;
  /** Show concept chips. Their definitions need a logged-in student, and study mode has none. */
  chips?: boolean;
  tracker?: PlaybackTracker;
  /** Shows the "I'm Lost" button. Study mode and the developer viewer have none. */
  onImLost?(at: BeatPosition): Promise<ImLostOutcome>;
  /** Covers the player and locks it, keeping the video in place behind it. When it goes away
   * the video plays on from where it stopped. */
  overlay?: ReactNode;
  /** A message above the video. */
  banner?: ReactNode;
  onModuleEnded?(): void;
};

export function ModulePlayer({
  manifest,
  settings,
  onSettingsChange,
  start,
  autoPlay = false,
  startPrompt,
  heading,
  chips = false,
  tracker,
  onImLost,
  overlay,
  banner,
  onModuleEnded,
}: Props) {
  const timeline = useTimeline(manifest);
  const first = start ?? { beat: manifest.beats[0].index, time_s: 0 };
  const stage = useRef<VideoStageHandle>(null);
  const container = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState(first);
  const [playing, setPlaying] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [openChip, setOpenChip] = useState<string | null>(null);
  const [pressingImLost, setPressingImLost] = useState(false);
  const [replayBeat, setReplayBeat] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const locked = overlay != null;
  const wasLocked = useRef(false);
  const { rate, volume, muted, captions } = settings;
  const change = (next: Partial<PlayerSettings>) => onSettingsChange({ ...settings, ...next });

  const beat = manifest.beats.find((b) => b.index === position.beat);
  const replayTerms = [
    ...new Set(manifest.beats.find((b) => b.index === replayBeat)?.chips.map((c) => c.term)),
  ];

  function togglePlay() {
    if (playing) {
      tracker?.studentPaused(position);
      stage.current?.pause();
    } else {
      tracker?.studentResumed();
      stage.current?.play();
    }
  }

  function seekTo(target: BeatPosition) {
    tracker?.studentSeeked(position, target);
    stage.current?.seek(target);
  }

  const back10 = () => seekTo(rewind(timeline, position));
  const on10 = () => seekTo(forward(timeline, position));

  // The pause and the jump are the player's own, so they go straight to the stage and are not
  // logged (§6.10). A pause the student had already made ends here: its length is known.
  async function pressImLost() {
    if (!onImLost || pressingImLost || locked) return;
    const wasPlaying = playing;
    setPressingImLost(true);
    tracker?.studentResumed();
    stage.current?.pause();
    const outcome = await onImLost(position);
    setPressingImLost(false);
    if (outcome.kind === "replay") {
      stage.current?.playFrom({ beat: outcome.beat, time_s: 0 });
      setReplayBeat(outcome.beat);
      if (outcome.workedExampleAdded) setNotice("We'll add a worked example after this module.");
    } else if (outcome.kind === "failed") {
      setNotice(outcome.message);
      if (wasPlaying) stage.current?.play();
    }
  }

  function toggleMute() {
    // Unmuting at volume 0 would stay silent, so bring the sound back too.
    if (volume === 0) change({ volume: 1, muted: false });
    else change({ muted: !muted });
  }

  function toggleFullscreen() {
    if (document.fullscreenElement) void document.exitFullscreen();
    // The whole player, not the <video>, so captions and controls stay visible (§4.4.2).
    else void container.current?.requestFullscreen();
  }

  useEffect(() => {
    const onChange = () => setFullscreen(document.fullscreenElement === container.current);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  const startOnMount = useEffectEvent(() => {
    if (autoPlay) stage.current?.play();
  });
  useEffect(() => startOnMount(), []);

  useEffect(() => {
    if (wasLocked.current && !locked) stage.current?.play();
    wasLocked.current = locked;
  }, [locked]);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), NOTICE_MS);
    return () => clearTimeout(timer);
  }, [notice]);

  const onKeyDown = useEffectEvent((event: KeyboardEvent) => {
    if (locked || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
    const target = event.target as HTMLElement;
    // Never while typing, and leave Space and Enter to a focused button (it presses itself).
    if (target.closest("input, textarea, select, [contenteditable='true']")) return;
    if ((event.key === " " || event.key === "Enter") && target.closest("button")) return;
    switch (event.key.toLowerCase()) {
      case " ":
      case "k":
        togglePlay();
        break;
      case "j":
      case "arrowleft":
        back10();
        break;
      case "arrowright":
        on10();
        break;
      case "c":
        change({ captions: !captions });
        break;
      case "m":
        toggleMute();
        break;
      case "f":
        toggleFullscreen();
        break;
      case "l":
        if (!onImLost) return;
        void pressImLost();
        break;
      default:
        return;
    }
    // Space and the arrows would otherwise scroll the page.
    event.preventDefault();
  });
  useEffect(() => {
    const listener = (event: KeyboardEvent) => onKeyDown(event);
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);

  return (
    <div
      ref={container}
      className={`relative flex flex-col gap-3 ${fullscreen ? "h-full bg-black p-4 text-white" : ""}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="min-w-0 opacity-70">
          {heading ?? `Beat ${position.beat + 1} of ${manifest.beat_count}`}
        </span>
        <span className="flex items-center gap-3">
          <span className="rounded-full border border-current/30 px-3 py-0.5 text-xs font-semibold">
            Level {manifest.level}
          </span>
          {onImLost && (
            <ImLostButton disabled={pressingImLost || locked} onPress={() => void pressImLost()} />
          )}
        </span>
      </div>

      {banner}

      <div
        className={`flex flex-col gap-4 lg:flex-row ${
          fullscreen ? "min-h-0 flex-1 lg:items-stretch" : "lg:items-start"
        }`}
      >
        <VideoStage
          ref={stage}
          manifest={manifest}
          start={first}
          rate={rate}
          volume={volume}
          muted={muted}
          onProgress={(next) => {
            setPosition(next);
            tracker?.progress(next);
          }}
          onPlayingChange={(value) => {
            setPlaying(value);
            tracker?.playingChanged(value);
          }}
          onModuleEnded={() => onModuleEnded?.()}
          startPrompt={startPrompt}
          className={
            fullscreen
              ? "min-h-0 w-full flex-1"
              : "aspect-video w-full min-w-0 rounded-lg lg:w-auto lg:flex-1"
          }
        />
        {replayTerms.length > 0 && (
          <ReplayDefinitions terms={replayTerms} onClose={() => setReplayBeat(null)} />
        )}
      </div>

      {captions && <Captions beat={beat} time_s={position.time_s} />}

      {chips && (
        // Always the height of a chip, so the controls don't jump as chips come and go.
        <div className="relative min-h-11">
          <ChipBar
            chips={beat ? chipsAt(beat, position.time_s) : []}
            open={openChip}
            onToggle={(term) => {
              if (openChip !== term) tracker?.chipOpened(position, term);
              setOpenChip(openChip === term ? null : term);
            }}
          />
          {openChip && <ChipOverlay term={openChip} onClose={() => setOpenChip(null)} />}
        </div>
      )}

      <Controls
        timeline={timeline}
        position={position}
        playing={playing}
        rate={rate}
        volume={volume}
        muted={muted}
        captions={captions}
        fullscreen={fullscreen}
        onPlayPause={togglePlay}
        onSeek={seekTo}
        onRewind={back10}
        onForward={on10}
        onVolume={(next) => change({ volume: next, muted: false })}
        onRate={(next) => {
          tracker?.speedChanged(position, rate, next);
          change({ rate: next });
        }}
        onMute={toggleMute}
        onCaptions={() => change({ captions: !captions })}
        onFullscreen={toggleFullscreen}
      />

      {notice && (
        <p
          role="status"
          className="absolute top-14 left-1/2 z-10 w-max max-w-[90%] -translate-x-1/2 rounded-full bg-black/85 px-4 py-2 text-center text-sm text-white"
        >
          {notice}
        </p>
      )}

      {overlay}
    </div>
  );
}
