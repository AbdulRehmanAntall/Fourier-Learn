import { useEffect, useRef } from "react";

import { sendPositionBeacon } from "@/lib/api/beacon";
import { savePosition } from "@/lib/api/hooks/player";

import type { BeatPosition } from "./useTimeline";

// Saves where the student is, so a lesson can be resumed (docs/frontend.md §6.9): every 10 s
// while playing, whenever playback stops (a pause or the end of the module), and by beacon when
// the page closes. Nothing is saved before playback reports a position, so opening a lesson
// never overwrites its saved place. A failed save is ignored: the next one replaces it.

const SAVE_INTERVAL_MS = 10_000;

const toBody = (moduleId: number, { beat, time_s }: BeatPosition) => ({
  module_id: moduleId,
  beat_index: beat,
  position_s: Math.max(time_s, 0),
});

function save(lessonId: number, moduleId: number, position: BeatPosition | null) {
  if (position) savePosition(lessonId, toBody(moduleId, position)).catch(() => {});
}

export function usePositionSaver(lessonId: number, moduleId: number) {
  const latest = useRef<BeatPosition | null>(null);
  const playing = useRef(false);

  useEffect(() => {
    const timer = setInterval(() => {
      if (playing.current) save(lessonId, moduleId, latest.current);
    }, SAVE_INTERVAL_MS);
    const onPageHide = () => {
      if (latest.current) sendPositionBeacon(lessonId, toBody(moduleId, latest.current));
    };
    window.addEventListener("pagehide", onPageHide);
    return () => {
      clearInterval(timer);
      window.removeEventListener("pagehide", onPageHide);
    };
  }, [lessonId, moduleId]);

  return {
    progress(position: BeatPosition) {
      latest.current = position;
    },
    playingChanged(value: boolean) {
      playing.current = value;
      if (!value) save(lessonId, moduleId, latest.current);
    },
  };
}
