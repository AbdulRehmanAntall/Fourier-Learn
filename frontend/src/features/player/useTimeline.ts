import { useMemo } from "react";

import type { components } from "@/lib/api/schema";

// Beat ↔ module time for one variant (docs/frontend.md §6.4). Every time comes from the manifest
// (rule 6). A manifest may be partial (§6.2): its beats run in order without gaps, but after an
// "I'm Lost" press they may start at beat j, and while rendering they stop before beat_count.
// Beats not in the manifest yet have no duration, so their segments take the mean duration of
// the beats that are, and are marked not ready: the bar stripes them and seeking skips them.

type ModuleManifest = components["schemas"]["ModuleManifest"];
type BeatManifest = components["schemas"]["BeatManifest"];

export type Segment = {
  index: number;
  start_s: number;
  duration_s: number;
  /** In the manifest, so playable. */
  ready: boolean;
};

export type Timeline = {
  segments: Segment[];
  duration_s: number;
  complete: boolean;
};

/** A point in the variant: a beat and seconds from the start of that beat's own video. */
export type BeatPosition = { beat: number; time_s: number };

export function buildTimeline(manifest: ModuleManifest): Timeline {
  const known = new Map(manifest.beats.map((beat) => [beat.index, beat.duration_s]));
  const estimate = [...known.values()].reduce((sum, d) => sum + d, 0) / known.size;
  const segments: Segment[] = [];
  let start = 0;
  for (let index = 0; index < manifest.beat_count; index++) {
    const duration = known.get(index);
    segments.push({
      index,
      start_s: start,
      duration_s: duration ?? estimate,
      ready: duration !== undefined,
    });
    start += duration ?? estimate;
  }
  return { segments, duration_s: start, complete: known.size === manifest.beat_count };
}

export function useTimeline(manifest: ModuleManifest): Timeline {
  return useMemo(() => buildTimeline(manifest), [manifest]);
}

export function toModuleTime(timeline: Timeline, position: BeatPosition): number {
  const segment = timeline.segments[position.beat];
  return segment.start_s + Math.min(Math.max(position.time_s, 0), segment.duration_s);
}

/** The beat playing at module time `t` (clamped to the module). A boundary belongs to the beat
 * that starts there, except the very end, which is the end of the last beat. */
export function locate(timeline: Timeline, t: number): BeatPosition {
  const { segments } = timeline;
  const clamped = Math.min(Math.max(t, 0), timeline.duration_s);
  const segment =
    segments.findLast((s) => s.start_s <= clamped && clamped < s.start_s + s.duration_s) ??
    segments[segments.length - 1];
  return { beat: segment.index, time_s: clamped - segment.start_s };
}

/** Where a seek to module time `t` lands, or null when it falls in a beat that isn't ready. */
export function seekTarget(timeline: Timeline, t: number): BeatPosition | null {
  const position = locate(timeline, t);
  return timeline.segments[position.beat].ready ? position : null;
}

/** `seconds` back from `position`, across beat boundaries (§6.5). Not before 0:00, nor before
 * the variant's first beat when it starts at beat j. */
export function rewind(timeline: Timeline, position: BeatPosition, seconds = 10): BeatPosition {
  const first = timeline.segments.find((s) => s.ready)!;
  return locate(timeline, Math.max(toModuleTime(timeline, position) - seconds, first.start_s));
}

/** The step being narrated `time_s` into a beat: the last one started, or the first before it
 * starts. Between two steps the earlier one's caption stays up. */
export function stepAt(beat: BeatManifest, time_s: number) {
  return beat.steps.findLast((step) => step.start_s <= time_s) ?? beat.steps[0];
}

/** "m:ss", as in the wireframe ("0:20 / 1:00"). */
export function formatTime(seconds: number): string {
  const whole = Math.floor(Math.max(seconds, 0));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}
