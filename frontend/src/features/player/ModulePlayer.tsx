"use client";

import { useEffect, useEffectEvent, useRef, useState } from "react";

import type { Schemas } from "@/lib/api/client";

import { Captions } from "./Captions";
import { Controls } from "./Controls";
import { rewind, type BeatPosition, useTimeline } from "./useTimeline";
import { VideoStage, type VideoStageHandle } from "./VideoStage";

// Plays one variant of a module: the video stage, captions and controls, with the keyboard
// shortcuts of docs/frontend.md §6.5. The lesson player (LessonPlayer, with the state machine
// of §6.1) wraps it; the rate and captions setting live there in the end, so they carry over
// between modules.

type Props = {
  manifest: Schemas["ModuleManifest"];
  start?: BeatPosition;
  /** Try to start playing at once. The browser may refuse; the stage then shows a Play button. */
  autoPlay?: boolean;
  onModuleEnded?(): void;
};

export function ModulePlayer({ manifest, start, autoPlay = false, onModuleEnded }: Props) {
  const timeline = useTimeline(manifest);
  const first = start ?? { beat: manifest.beats[0].index, time_s: 0 };
  const stage = useRef<VideoStageHandle>(null);
  const container = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState(first);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);
  const [muted, setMuted] = useState(false);
  const [captions, setCaptions] = useState(true);
  const [fullscreen, setFullscreen] = useState(false);

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
        setCaptions((on) => !on);
        break;
      case "m":
        setMuted((on) => !on);
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
          Beat {position.beat + 1} of {manifest.beat_count}
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
        onRate={setRate}
        onMute={() => setMuted(!muted)}
        onCaptions={() => setCaptions(!captions)}
        onFullscreen={toggleFullscreen}
      />
    </div>
  );
}
