import { beforeEach, describe, expect, it } from "vitest";

import { EventLogger, MAX_BATCH, type LoggedEvent, type SendResult } from "./eventLogger";

const MODULE = 7;
const here = { beat: 1, time_s: 4 };
const START = new Date("2026-11-05T10:00:00.000Z");

let clock: Date;
let sent: LoggedEvent[][];
let answer: SendResult | "throw";
let logger: EventLogger;

beforeEach(() => {
  clock = START;
  sent = [];
  answer = "sent";
  logger = new EventLogger(
    async (events) => {
      sent.push(events);
      if (answer === "throw") throw new Error("offline");
      return answer;
    },
    () => clock,
  );
});

const later = (seconds: number) => {
  clock = new Date(START.getTime() + seconds * 1000);
};

async function loggedEvents() {
  await logger.flush();
  return sent.flat();
}

function logChips(count: number) {
  for (let i = 0; i < count; i++) logger.chipOpened(MODULE, here, `term ${i}`);
}

describe("rewind", () => {
  it("logs a seek backwards with both ends, beat-local", async () => {
    logger.seeked(MODULE, { beat: 2, time_s: 3 }, { beat: 1, time_s: 9 });
    expect(await loggedEvents()).toEqual([
      {
        type: "rewind",
        module_id: MODULE,
        occurred_at: START.toISOString(),
        beat_index: 2,
        position_s: 3,
        to_beat_index: 1,
        to_position_s: 9,
      },
    ]);
  });

  it("logs a seek backwards within a beat", async () => {
    logger.seeked(MODULE, here, { beat: 1, time_s: 1 });
    expect(await loggedEvents()).toHaveLength(1);
  });

  it("doesn't log seeking forwards", async () => {
    logger.seeked(MODULE, here, { beat: 1, time_s: 8 });
    logger.seeked(MODULE, here, { beat: 2, time_s: 0 });
    expect(await loggedEvents()).toEqual([]);
  });

  it("doesn't log a seek to the same point, which the contract refuses (↺ at 0:00)", async () => {
    logger.seeked(MODULE, { beat: 0, time_s: 0 }, { beat: 0, time_s: 0 });
    expect(await loggedEvents()).toEqual([]);
  });
});

describe("speed_change", () => {
  it("logs the rates before and after", async () => {
    logger.speedChanged(MODULE, here, 1, 0.75);
    expect(await loggedEvents()).toMatchObject([
      { type: "speed_change", beat_index: 1, position_s: 4, from_rate: 1, to_rate: 0.75 },
    ]);
  });

  it("doesn't log picking the same rate", async () => {
    logger.speedChanged(MODULE, here, 1, 1);
    expect(await loggedEvents()).toEqual([]);
  });
});

describe("chip_view", () => {
  it("logs the term and where it was opened", async () => {
    logger.chipOpened(MODULE, here, "gradient");
    expect(await loggedEvents()).toMatchObject([
      { type: "chip_view", module_id: MODULE, beat_index: 1, position_s: 4, term: "gradient" },
    ]);
  });
});

describe("pause", () => {
  it("sends nothing until the pause ends, then its length and where it began", async () => {
    logger.paused(MODULE, here);
    later(12.5);
    expect(await loggedEvents()).toEqual([]);
    logger.endPause();
    expect(await loggedEvents()).toEqual([
      {
        type: "pause",
        module_id: MODULE,
        occurred_at: START.toISOString(),
        beat_index: 1,
        position_s: 4,
        duration_s: 12.5,
      },
    ]);
  });

  it("keeps the first start if paused twice", async () => {
    logger.paused(MODULE, here);
    later(5);
    logger.paused(MODULE, { beat: 2, time_s: 0 });
    later(10);
    logger.endPause();
    expect(await loggedEvents()).toMatchObject([{ beat_index: 1, duration_s: 10 }]);
  });

  it("logs nothing when playback starts with no pause open", async () => {
    logger.endPause();
    expect(await loggedEvents()).toEqual([]);
  });

  it("logs a pause once, even if ended twice", async () => {
    logger.paused(MODULE, here);
    logger.endPause();
    logger.endPause();
    expect(await loggedEvents()).toHaveLength(1);
  });
});

describe("batching", () => {
  it("sends by itself when 20 events are waiting", async () => {
    logChips(19);
    expect(sent).toEqual([]);
    logChips(1);
    await logger.flush();
    expect(sent.map((batch) => batch.length)).toEqual([20]);
  });

  it("doesn't call the server with nothing to send", async () => {
    await logger.flush();
    expect(sent).toEqual([]);
  });

  it("splits a long buffer into batches the server accepts", async () => {
    answer = "failed";
    logChips(150);
    await logger.flush();
    answer = "sent";
    sent = [];
    await logger.flush();
    expect(sent.map((batch) => batch.length)).toEqual([MAX_BATCH, 50]);
  });

  it("makes one flush at a time, including events added meanwhile", async () => {
    logChips(1);
    const flushing = logger.flush();
    logChips(1);
    expect(logger.flush()).toBe(flushing);
    await flushing;
    expect(sent.flat()).toHaveLength(2);
  });
});

describe("failures", () => {
  it("keeps events after a network or server error and sends them next time", async () => {
    answer = "throw";
    logChips(2);
    await logger.flush();
    answer = "sent";
    sent = [];
    await logger.flush();
    expect(sent.map((batch) => batch.length)).toEqual([2]);
  });

  it("keeps the order, older events first", async () => {
    answer = "failed";
    logger.chipOpened(MODULE, here, "first");
    await logger.flush();
    answer = "sent";
    sent = [];
    logger.chipOpened(MODULE, here, "second");
    await logger.flush();
    expect(sent.flat().map((event) => (event as { term: string }).term)).toEqual([
      "first",
      "second",
    ]);
  });

  it("drops a batch the server refuses, so it can't block later events", async () => {
    answer = "refused";
    logChips(1);
    await logger.flush();
    answer = "sent";
    sent = [];
    await logger.flush();
    expect(sent).toEqual([]);
  });

  it("never rejects, so the lesson can't wait on it", async () => {
    answer = "throw";
    logChips(1);
    await expect(logger.flush()).resolves.toBeUndefined();
  });

  it("keeps the newest 500 events while offline", async () => {
    answer = "failed";
    for (let i = 0; i < 600; i++) {
      logger.chipOpened(MODULE, here, `term ${i}`);
      await logger.flush();
    }
    const kept = logger.takeBatches().flat();
    expect(kept).toHaveLength(500);
    expect(kept[0]).toMatchObject({ term: "term 100" });
    expect(kept[499]).toMatchObject({ term: "term 599" });
  });
});

describe("when the page closes", () => {
  it("hands over everything in sendBeacon batches and empties the buffer", async () => {
    answer = "failed";
    logChips(150);
    await logger.flush();
    expect(logger.takeBatches().map((batch) => batch.length)).toEqual([MAX_BATCH, 50]);
    expect(logger.takeBatches()).toEqual([]);
  });

  it("can put a batch back if the browser refused the beacon", () => {
    logChips(2);
    const [batch] = logger.takeBatches();
    logger.restore(batch);
    expect(logger.takeBatches()).toEqual([batch]);
  });
});
