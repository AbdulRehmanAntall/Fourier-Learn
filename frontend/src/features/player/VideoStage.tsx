"use client";

import { useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";

import { variantFileUrl, type Schemas } from "@/lib/api/client";

import type { BeatPosition } from "./useTimeline";

// Two <video> elements that take turns (docs/frontend.md §6.3). The visible one plays beat i
// while the hidden one loads beat i + 1 and nothing further (§6.4.7). On `ended` the hidden one
// starts playing before it is shown, so there is no black frame between beats. Both stay
// mounted; the hidden one is only transparent, so it keeps loading.
//
// Which beat each element holds is derived, not stored: the active element holds `current` and
// the other holds `current + 1` if the manifest has it. Moving to the next beat is a swap of
// `active`; jumping elsewhere changes the active element's source.

type ModuleManifest = Schemas["ModuleManifest"];

export type VideoStageHandle = {
  play(): void;
  pause(): void;
  seek(position: BeatPosition): void;
};

type Slot = 0 | 1;

type Props = {
  manifest: ModuleManifest;
  /** Where playback begins. Give the stage a new `key` to begin again somewhere else. */
  start: BeatPosition;
  rate: number;
  muted: boolean;
  onProgress(position: BeatPosition): void;
  onPlayingChange(playing: boolean): void;
  onModuleEnded(): void;
  /** Show a large button with this label until playback first starts (e.g. "Resume"). */
  startPrompt?: string;
  className?: string;
  ref?: Ref<VideoStageHandle>;
};

export function VideoStage({
  manifest,
  start,
  rate,
  muted,
  onProgress,
  onPlayingChange,
  onModuleEnded,
  startPrompt,
  className = "",
  ref,
}: Props) {
  const videos = useRef<(HTMLVideoElement | null)[]>([null, null]);
  // Where to seek each element once its new beat's metadata has loaded.
  const pendingTime = useRef<(number | null)[]>([start.time_s, null]);
  const [active, setActive] = useState<Slot>(0);
  const [current, setCurrent] = useState(start.beat);
  const [playing, setPlaying] = useState(false);
  const [ended, setEnded] = useState(false);
  // Playback reached a beat that isn't in the manifest yet (§6.2). Not a student pause.
  const [waitingForBeat, setWaitingForBeat] = useState(false);
  const [buffering, setBuffering] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [started, setStarted] = useState(false);

  const beats = new Map(manifest.beats.map((beat) => [beat.index, beat]));
  const other: Slot = active === 0 ? 1 : 0;
  const nextReady = beats.has(current + 1);
  const beatIn = (slot: Slot) => beats.get(slot === active ? current : current + 1);

  function changePlaying(value: boolean) {
    setPlaying(value);
    onPlayingChange(value);
  }

  function startVideo(video: HTMLVideoElement) {
    video
      .play()
      .then(() => {
        setBlocked(false);
        setStarted(true);
      })
      .catch((error: DOMException) => {
        // A pause or a new source interrupts play() with an AbortError; only a refusal matters.
        // Browsers refuse playback with sound until the student has tapped the page.
        if (error.name === "NotAllowedError") {
          setBlocked(true);
          changePlaying(false);
        }
      });
  }

  function goTo({ beat, time_s }: BeatPosition, andPlay: boolean) {
    if (!beats.has(beat)) return;
    const video = videos.current[active];
    const hidden = videos.current[other];
    setEnded(false);
    setWaitingForBeat(false);
    if (beat === current && video) {
      video.currentTime = time_s;
      if (andPlay) startVideo(video);
    } else if (beat === current + 1 && hidden) {
      video?.pause();
      hidden.currentTime = time_s;
      if (andPlay) startVideo(hidden);
      setActive(other);
      setCurrent(beat);
    } else {
      // The active element gets the new beat on the next render; onLoadedMetadata seeks it.
      video?.pause();
      pendingTime.current[active] = time_s;
      setCurrent(beat);
    }
    onProgress({ beat, time_s });
  }

  function play() {
    changePlaying(true);
    if (ended) {
      goTo({ beat: manifest.beats[0].index, time_s: 0 }, true);
      return;
    }
    const video = videos.current[active];
    if (video && !waitingForBeat) startVideo(video);
  }

  function pause() {
    changePlaying(false);
    videos.current[active]?.pause();
  }

  useImperativeHandle(ref, () => ({ play, pause, seek: (position) => goTo(position, playing) }));

  function onEnded() {
    if (current + 1 >= manifest.beat_count) {
      setEnded(true);
      changePlaying(false);
      onModuleEnded();
    } else if (!nextReady) {
      setWaitingForBeat(true);
    } else {
      const hidden = videos.current[other];
      if (hidden) {
        hidden.currentTime = 0;
        startVideo(hidden);
      }
      setActive(other);
      setCurrent(current + 1);
    }
  }

  // The beat we were waiting for has arrived: start it while it is still hidden, and show it
  // once it is playing (onPlay below).
  useEffect(() => {
    const hidden = videos.current[other];
    if (!waitingForBeat || !nextReady || !playing || !hidden?.paused) return;
    hidden.currentTime = 0;
    hidden.play().catch((error: DOMException) => {
      if (error.name === "NotAllowedError") {
        // The Play button sets `playing` again, which runs this effect again.
        setBlocked(true);
        setPlaying(false);
        onPlayingChange(false);
      }
    });
  }, [waitingForBeat, nextReady, playing, other, onPlayingChange]);

  // The rate is kept across beats: a new source resets playbackRate to defaultPlaybackRate.
  useEffect(() => {
    videos.current.forEach((video) => {
      if (!video) return;
      video.defaultPlaybackRate = rate;
      video.playbackRate = rate;
      video.muted = muted;
    });
  });

  // Free the hidden element when there is no next beat to load, and both when we're done.
  const hiddenEmpty = !nextReady;
  useEffect(() => {
    const hidden = videos.current[other];
    if (hiddenEmpty && hidden?.getAttribute("src") === null) hidden.load();
  }, [hiddenEmpty, other]);
  useEffect(() => {
    const elements = videos.current;
    return () => {
      for (const video of elements) {
        video?.removeAttribute("src");
        video?.load();
      }
    };
  }, []);

  return (
    <div className={`relative overflow-hidden bg-black ${className}`}>
      {([0, 1] as const).map((slot) => {
        const beat = beatIn(slot);
        const isActive = slot === active;
        return (
          <video
            key={slot}
            ref={(element) => {
              videos.current[slot] = element;
            }}
            src={beat && variantFileUrl(manifest.cache_key, beat.video)}
            preload="auto"
            playsInline
            controls={false}
            aria-hidden={!isActive}
            onLoadedMetadata={(event) => {
              const time = pendingTime.current[slot];
              if (time !== null) {
                event.currentTarget.currentTime = time;
                pendingTime.current[slot] = null;
              }
              if (isActive && playing) startVideo(event.currentTarget);
            }}
            onTimeUpdate={(event) => {
              if (isActive) onProgress({ beat: current, time_s: event.currentTarget.currentTime });
            }}
            onEnded={() => isActive && onEnded()}
            onPlay={() => {
              if (!isActive && waitingForBeat) {
                setActive(slot);
                setCurrent(current + 1);
                setWaitingForBeat(false);
              }
            }}
            onWaiting={() => isActive && setBuffering(true)}
            onPlaying={() => isActive && setBuffering(false)}
            className={`absolute inset-0 h-full w-full object-contain ${
              isActive ? "opacity-100" : "pointer-events-none opacity-0"
            }`}
          />
        );
      })}

      {playing && (waitingForBeat || buffering) && (
        <div className="absolute inset-0 grid place-items-center" role="status">
          <span className="flex items-center gap-2 rounded-full bg-black/70 px-4 py-2 text-sm text-white">
            <span className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white motion-reduce:animate-none" />
            Preparing…
          </span>
        </div>
      )}

      {(blocked || (startPrompt && !started)) && (
        <button
          onClick={play}
          className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/40 text-white"
          aria-label={startPrompt && !started ? startPrompt : "Play"}
        >
          <span className="grid size-20 place-items-center rounded-full bg-white/90 text-black">
            <svg viewBox="0 0 24 24" className="ml-1 size-9" fill="currentColor" aria-hidden>
              <path d="M8 5v14l11-7z" />
            </svg>
          </span>
          {startPrompt && !started && (
            <span className="text-lg font-semibold" aria-hidden>
              {startPrompt}
            </span>
          )}
        </button>
      )}
    </div>
  );
}
