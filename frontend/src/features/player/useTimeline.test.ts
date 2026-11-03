import { describe, expect, it } from "vitest";

import type { components } from "@/lib/api/schema";

import { buildTimeline, formatTime, locate, rewind, seekTarget, toModuleTime } from "./useTimeline";

type ModuleManifest = components["schemas"]["ModuleManifest"];

function manifest(beatCount: number, beats: [index: number, duration: number][]): ModuleManifest {
  return {
    cache_key: "key",
    level: 2,
    voice: "kokoro",
    library_version: "1",
    beat_count: beatCount,
    beats: beats.map(([index, duration_s]) => ({
      index,
      primitive_id: "GradientTriangle",
      video: `beats/${index}.mp4`,
      duration_s,
      steps: [{ start_s: 0, end_s: duration_s, narration: "…" }],
      chips: [],
      concept_ids: [],
    })),
  };
}

const complete = buildTimeline(
  manifest(3, [
    [0, 20],
    [1, 15],
    [2, 25],
  ]),
);

describe("a complete manifest", () => {
  it("lays the beats end to end", () => {
    expect(complete.duration_s).toBe(60);
    expect(complete.complete).toBe(true);
    expect(complete.segments.map((s) => s.start_s)).toEqual([0, 20, 35]);
    expect(complete.segments.every((s) => s.ready)).toBe(true);
  });

  it("converts beat time to module time and back", () => {
    expect(toModuleTime(complete, { beat: 1, time_s: 5 })).toBe(25);
    expect(locate(complete, 25)).toEqual({ beat: 1, time_s: 5 });
  });

  it("gives a boundary to the beat that starts there, and the end to the last beat", () => {
    expect(locate(complete, 20)).toEqual({ beat: 1, time_s: 0 });
    expect(locate(complete, 60)).toEqual({ beat: 2, time_s: 25 });
  });

  it("clamps times outside the module", () => {
    expect(locate(complete, -3)).toEqual({ beat: 0, time_s: 0 });
    expect(locate(complete, 99)).toEqual({ beat: 2, time_s: 25 });
    expect(toModuleTime(complete, { beat: 0, time_s: 21 })).toBe(20);
  });
});

describe("rewind", () => {
  it("goes back within a beat", () => {
    expect(rewind(complete, { beat: 0, time_s: 15 })).toEqual({ beat: 0, time_s: 5 });
  });

  it("crosses beat boundaries", () => {
    expect(rewind(complete, { beat: 2, time_s: 4 })).toEqual({ beat: 1, time_s: 9 });
  });

  it("stops at 0:00", () => {
    expect(rewind(complete, { beat: 0, time_s: 3 })).toEqual({ beat: 0, time_s: 0 });
  });
});

describe("a partial manifest", () => {
  it("estimates beats still rendering and marks them not ready", () => {
    const timeline = buildTimeline(
      manifest(4, [
        [0, 20],
        [1, 10],
      ]),
    );
    expect(timeline.complete).toBe(false);
    expect(timeline.segments.map((s) => [s.duration_s, s.ready])).toEqual([
      [20, true],
      [10, true],
      [15, false],
      [15, false],
    ]);
    expect(timeline.duration_s).toBe(60);
  });

  it("won't seek into a beat that isn't ready", () => {
    const timeline = buildTimeline(manifest(3, [[0, 20]]));
    expect(seekTarget(timeline, 10)).toEqual({ beat: 0, time_s: 10 });
    expect(seekTarget(timeline, 30)).toBeNull();
  });

  it("handles a variant that starts at beat j after an I'm Lost press", () => {
    const timeline = buildTimeline(
      manifest(3, [
        [1, 30],
        [2, 30],
      ]),
    );
    expect(timeline.segments[0]).toEqual({ index: 0, start_s: 0, duration_s: 30, ready: false });
    expect(seekTarget(timeline, 10)).toBeNull();
    expect(seekTarget(timeline, 45)).toEqual({ beat: 1, time_s: 15 });
    // Rewind stops at the start of beat j, the first beat this variant has.
    expect(rewind(timeline, { beat: 1, time_s: 4 })).toEqual({ beat: 1, time_s: 0 });
  });
});

describe("formatTime", () => {
  it("writes m:ss", () => {
    expect(formatTime(0)).toBe("0:00");
    expect(formatTime(20.9)).toBe("0:20");
    expect(formatTime(60)).toBe("1:00");
    expect(formatTime(125)).toBe("2:05");
  });
});
