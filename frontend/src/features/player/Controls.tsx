"use client";

import { useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";

import {
  CaptionsIcon,
  ExitFullscreenIcon,
  FullscreenIcon,
  MutedIcon,
  PauseIcon,
  PlayIcon,
  RewindIcon,
  VolumeIcon,
} from "./icons";
import {
  formatTime,
  seekTarget,
  toModuleTime,
  type BeatPosition,
  type Timeline,
} from "./useTimeline";

// The player's control bar (docs/frontend.md §6.4, §6.5, Fig. 4.3).

export const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2];

type Props = {
  timeline: Timeline;
  position: BeatPosition;
  playing: boolean;
  rate: number;
  muted: boolean;
  captions: boolean;
  fullscreen: boolean;
  onPlayPause(): void;
  onSeek(position: BeatPosition): void;
  onRewind(): void;
  onRate(rate: number): void;
  onMute(): void;
  onCaptions(): void;
  onFullscreen(): void;
};

export function Controls(props: Props) {
  const { timeline, position, playing, rate, muted, captions, fullscreen } = props;
  const now = toModuleTime(timeline, position);

  return (
    <div className="flex flex-col gap-2">
      <SeekBar timeline={timeline} now={now} onSeek={props.onSeek} />
      <div className="flex flex-wrap items-center gap-1">
        <ControlButton label={playing ? "Pause" : "Play"} onClick={props.onPlayPause}>
          {playing ? <PauseIcon /> : <PlayIcon />}
        </ControlButton>
        <ControlButton label="Back 10 seconds" onClick={props.onRewind}>
          <RewindIcon />
        </ControlButton>
        <ControlButton label={muted ? "Unmute" : "Mute"} onClick={props.onMute}>
          {muted ? <MutedIcon /> : <VolumeIcon />}
        </ControlButton>
        <span className="px-2 text-sm tabular-nums">
          {formatTime(now)} / {formatTime(timeline.duration_s)}
        </span>
        <span className="flex-1" />
        <label className="sr-only" htmlFor="player-speed">
          Playback speed
        </label>
        <select
          id="player-speed"
          value={rate}
          onChange={(event) => props.onRate(Number(event.target.value))}
          className="h-11 rounded-full border border-current/20 bg-transparent px-3 text-sm"
        >
          {SPEEDS.map((speed) => (
            // The open list is drawn by the browser, which doesn't follow the select's
            // transparent background: give it the app's colours so it matches in dark mode.
            <option key={speed} value={speed} className="bg-background text-foreground">
              {speed}x
            </option>
          ))}
        </select>
        <ControlButton label="Captions" pressed={captions} onClick={props.onCaptions}>
          <CaptionsIcon className={`size-6 ${captions ? "" : "opacity-50"}`} />
        </ControlButton>
        <ControlButton
          label={fullscreen ? "Exit fullscreen" : "Fullscreen"}
          onClick={props.onFullscreen}
        >
          {fullscreen ? <ExitFullscreenIcon /> : <FullscreenIcon />}
        </ControlButton>
      </div>
    </div>
  );
}

function ControlButton({
  label,
  pressed,
  onClick,
  children,
}: {
  label: string;
  pressed?: boolean;
  onClick(): void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-pressed={pressed}
      title={label}
      className="grid size-11 place-items-center rounded-full hover:bg-current/10 focus-visible:outline-2 focus-visible:outline-offset-2"
    >
      {children}
    </button>
  );
}

/** One segment per beat, as wide as the beat is long (Fig. 4.3). Beats still rendering are
 * striped and can't be seeked into. Dragging shows where you'll land and seeks on release, so
 * a drag across beats loads one beat, not every beat it passes. */
function SeekBar({
  timeline,
  now,
  onSeek,
}: {
  timeline: Timeline;
  now: number;
  onSeek(position: BeatPosition): void;
}) {
  const bar = useRef<HTMLDivElement>(null);
  const [scrub, setScrub] = useState<number | null>(null);
  const shown = scrub ?? now;
  const { duration_s: duration } = timeline;
  const percent = (t: number) => `${(100 * t) / duration}%`;

  function timeAt(event: PointerEvent) {
    const rect = bar.current!.getBoundingClientRect();
    return (Math.min(Math.max(event.clientX - rect.left, 0), rect.width) / rect.width) * duration;
  }

  function seek(t: number) {
    const target = seekTarget(timeline, t);
    if (target) onSeek(target);
  }

  function onKeyDown(event: KeyboardEvent) {
    const moves: Record<string, number> = {
      ArrowLeft: now - 5,
      ArrowRight: now + 5,
      Home: 0,
      End: duration,
    };
    if (!(event.key in moves)) return;
    // Handled here, so the player's own shortcuts (← rewinds 10 s) don't also run.
    event.preventDefault();
    seek(moves[event.key]);
  }

  return (
    <div
      ref={bar}
      role="slider"
      tabIndex={0}
      aria-label="Seek"
      aria-valuemin={0}
      aria-valuemax={Math.round(duration)}
      aria-valuenow={Math.round(shown)}
      aria-valuetext={`${formatTime(shown)} of ${formatTime(duration)}`}
      onKeyDown={onKeyDown}
      onPointerDown={(event) => {
        event.currentTarget.setPointerCapture(event.pointerId);
        setScrub(timeAt(event));
      }}
      onPointerMove={(event) => scrub !== null && setScrub(timeAt(event))}
      onPointerUp={(event) => {
        seek(timeAt(event));
        setScrub(null);
      }}
      onPointerCancel={() => setScrub(null)}
      className="relative h-6 cursor-pointer touch-none rounded focus-visible:outline-2 focus-visible:outline-offset-2"
    >
      {timeline.segments.map((segment) => {
        const played = Math.min(Math.max(shown - segment.start_s, 0), segment.duration_s);
        return (
          <span
            key={segment.index}
            className="absolute inset-y-2 px-px"
            style={{ left: percent(segment.start_s), width: percent(segment.duration_s) }}
          >
            <span
              className="block h-full overflow-hidden rounded-sm bg-current/20"
              style={
                segment.ready
                  ? undefined
                  : {
                      backgroundImage:
                        "repeating-linear-gradient(45deg, transparent 0 4px, rgb(127 127 127 / 0.45) 4px 8px)",
                    }
              }
            >
              <span
                className="block h-full bg-blue-600"
                style={{ width: `${(100 * played) / segment.duration_s}%` }}
              />
            </span>
          </span>
        );
      })}
    </div>
  );
}
