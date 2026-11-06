import type { Schemas } from "@/lib/api/client";

import type { BeatPosition } from "./useTimeline";

// The interaction event logger of docs/frontend.md §6.10: the rules and the batching, with no
// React or API code, so they can be tested alone (useEventLogger connects it to the page).
//
// It is told only what the student did. Pauses and seeks the player makes itself (the end of a
// module, waiting for a beat, resuming, the "I'm Lost" jump) never reach it, because they would
// corrupt the learner model. `im_lost` and `branch_choice` have no method here on purpose: their
// endpoints record them, and POST /api/events refuses them.

export type LoggedEvent =
  | Schemas["RewindEvent"]
  | Schemas["SpeedChangeEvent"]
  | Schemas["PauseEvent"]
  | Schemas["ChipViewEvent"];

/** `refused`: the server rejected the batch (a 4xx), so sending it again can't help. One bad
 * event fails its whole batch, and keeping it would block every event behind it. `failed`: a
 * network or server error, so the events are kept for the next flush. */
export type SendResult = "sent" | "refused" | "failed";

export const FLUSH_INTERVAL_MS = 10_000;
const FLUSH_AT = 20;
export const MAX_BATCH = 100;
const MAX_BUFFER = 500;

type OpenPause = { moduleId: number; at: BeatPosition; startedAt: Date };

export class EventLogger {
  private buffer: LoggedEvent[] = [];
  private pause: OpenPause | null = null;
  private flushing: Promise<void> | null = null;

  constructor(
    private readonly send: (events: LoggedEvent[]) => Promise<SendResult>,
    private readonly now: () => Date = () => new Date(),
  ) {}

  /** The student moved the playhead. Only going backwards is evidence of anything, and the
   * contract refuses a rewind that doesn't (pressing ↺ at 0:00, or seeking forwards). */
  seeked(moduleId: number, from: BeatPosition, to: BeatPosition) {
    const backwards = to.beat < from.beat || (to.beat === from.beat && to.time_s < from.time_s);
    if (!backwards) return;
    this.add({
      ...this.during(moduleId, from),
      type: "rewind",
      to_beat_index: to.beat,
      to_position_s: to.time_s,
    });
  }

  speedChanged(moduleId: number, at: BeatPosition, fromRate: number, toRate: number) {
    if (fromRate === toRate) return;
    this.add({
      ...this.during(moduleId, at),
      type: "speed_change",
      from_rate: fromRate,
      to_rate: toRate,
    });
  }

  chipOpened(moduleId: number, at: BeatPosition, term: string) {
    this.add({ ...this.during(moduleId, at), type: "chip_view", term });
  }

  /** The student paused. Nothing is sent until the pause ends, when its length is known. */
  paused(moduleId: number, at: BeatPosition) {
    this.pause ??= { moduleId, at, startedAt: this.now() };
  }

  /** The pause is over: the student played on, or the page is closing (the time so far). */
  endPause() {
    if (!this.pause) return;
    const { moduleId, at, startedAt } = this.pause;
    this.pause = null;
    const duration = (this.now().getTime() - startedAt.getTime()) / 1000;
    this.add({
      ...this.during(moduleId, at),
      occurred_at: startedAt.toISOString(),
      type: "pause",
      duration_s: Math.max(duration, 0),
    });
  }

  /** Sends everything waiting, in batches. Never rejects: the lesson doesn't wait on logging. */
  flush(): Promise<void> {
    this.flushing ??= this.sendAll().finally(() => {
      this.flushing = null;
    });
    return this.flushing;
  }

  /** Empties the buffer into batches for `sendBeacon`, when the page is closing. */
  takeBatches(): LoggedEvent[][] {
    const batches: LoggedEvent[][] = [];
    while (this.buffer.length > 0) batches.push(this.buffer.splice(0, MAX_BATCH));
    return batches;
  }

  /** Puts a batch back at the front, to be sent again. */
  restore(batch: LoggedEvent[]) {
    this.buffer.unshift(...batch);
    this.trim();
  }

  private async sendAll() {
    while (this.buffer.length > 0) {
      const batch = this.buffer.splice(0, MAX_BATCH);
      const result = await this.send(batch).catch((): SendResult => "failed");
      if (result === "failed") {
        this.restore(batch);
        return;
      }
    }
  }

  private add(event: LoggedEvent) {
    this.buffer.push(event);
    this.trim();
    if (this.buffer.length >= FLUSH_AT) void this.flush();
  }

  /** Memory stays bounded while offline: the oldest events go first. */
  private trim() {
    if (this.buffer.length > MAX_BUFFER) this.buffer.splice(0, this.buffer.length - MAX_BUFFER);
  }

  private during(moduleId: number, { beat, time_s }: BeatPosition) {
    return {
      module_id: moduleId,
      occurred_at: this.now().toISOString(),
      beat_index: beat,
      position_s: Math.max(time_s, 0),
    };
  }
}
