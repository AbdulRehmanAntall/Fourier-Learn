"use client";

import { useEffect, useEffectEvent, useRef, useState, type ReactNode } from "react";

import type { Schemas } from "@/lib/api/client";

import { Captions } from "./Captions";
import { Controls } from "./Controls";
import { rewind, type BeatPosition, useTimeline } from "./useTimeline";
import { VideoStage, type VideoStageHandle } from "./VideoStage";

// Plays one variant of a module: the video stage, captions and controls, with the keyboard
// shortcuts of docs/frontend.md §6.5. The settings belong to whoever renders it (LessonPlayer),
// so the rate and captions carry over between modules.

export type PlayerSettings = { rate: number; muted: boolean; captions: boolean };

export const DEFAULT_SETTINGS: PlayerSettings = { rate: 1, muted: false, captions: true };

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
  onModuleEnded,
}: Props) {
  const timeline = useTimeline(manifest);
  const first = start ?? { beat: manifest.beats[0].index, time_s: 0 };
  const stage = useRef<VideoStageHandle>(null);
  const container = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState(first);
  const [playing, setPlaying] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const { rate, muted, captions } = settings;
  const change = (next: Partial<PlayerSettings>) => onSettingsChange({ ...settings, ...next });

  const beat = manifest.beats.find((b) => b.index === position.beat);

  const togglePlay = () => (playing ? stage.current?.pause() : stage.current?.play());
  const back10 = () => stage.current?.seek(rewind(timeline, position));

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

  const onKeyDown = useEffectEvent((event: KeyboardEvent) => {
    if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
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
      case "c":
        change({ captions: !captions });
        break;
      case "m":
        change({ muted: !muted });
        break;
      case "f":
        toggleFullscreen();
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
      className={`flex flex-col gap-3 ${fullscreen ? "h-full bg-black p-4 text-white" : ""}`}
    >
      <div className="flex items-center justify-between text-sm">
        <span className="opacity-70">
          {heading ?? `Beat ${position.beat + 1} of ${manifest.beat_count}`}
        </span>
        <span className="rounded-full border border-current/30 px-3 py-0.5 text-xs font-semibold">
          Level {manifest.level}
        </span>
      </div>

      <VideoStage
        ref={stage}
        manifest={manifest}
        start={first}
        rate={rate}
        muted={muted}
        onProgress={setPosition}
        onPlayingChange={setPlaying}
        onModuleEnded={() => onModuleEnded?.()}
        startPrompt={startPrompt}
        className={fullscreen ? "min-h-0 flex-1" : "aspect-video rounded-lg"}
      />

      {captions && <Captions beat={beat} time_s={position.time_s} />}

      <Controls
        timeline={timeline}
        position={position}
        playing={playing}
        rate={rate}
        muted={muted}
        captions={captions}
        fullscreen={fullscreen}
        onPlayPause={togglePlay}
        onSeek={(target) => stage.current?.seek(target)}
        onRewind={back10}
        onRate={(next) => change({ rate: next })}
        onMute={() => change({ muted: !muted })}
        onCaptions={() => change({ captions: !captions })}
        onFullscreen={toggleFullscreen}
      />
    </div>
  );
}
