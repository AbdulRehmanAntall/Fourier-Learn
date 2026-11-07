import { describe, expect, it, vi } from "vitest";

import { retryInBackground } from "./retry";

// Lets the background attempts run: each one awaits a few promises.
const settle = async () => {
  for (let i = 0; i < 40; i++) await Promise.resolve();
};

const noWait = () => Promise.resolve();

describe("retryInBackground", () => {
  it("gives the first attempt's result and doesn't try again", async () => {
    const attempt = vi.fn().mockResolvedValue("saved");
    await expect(retryInBackground(attempt, { wait: noWait })).resolves.toBe("saved");
    await settle();
    expect(attempt).toHaveBeenCalledTimes(1);
  });

  it("rejects at once on a failure, while the retries carry on", async () => {
    const attempt = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce("saved");
    await expect(retryInBackground(attempt, { wait: noWait })).rejects.toThrow("offline");
    await settle();
    expect(attempt).toHaveBeenCalledTimes(2);
  });

  it("gives up after three retries, without an unhandled rejection", async () => {
    const attempt = vi.fn().mockRejectedValue(new Error("offline"));
    await expect(retryInBackground(attempt, { wait: noWait })).rejects.toThrow();
    await settle();
    expect(attempt).toHaveBeenCalledTimes(4);
  });

  it("doesn't retry an answer that won't change", async () => {
    const attempt = vi.fn().mockRejectedValue(new Error("refused"));
    const options = { wait: noWait, retryable: () => false };
    await expect(retryInBackground(attempt, options)).rejects.toThrow();
    await settle();
    expect(attempt).toHaveBeenCalledTimes(1);
  });

  it("stops when a retry gets an answer that won't change", async () => {
    const attempt = vi.fn().mockRejectedValueOnce("temporary").mockRejectedValue("refused");
    const options = { wait: noWait, retryable: (error: unknown) => error === "temporary" };
    await expect(retryInBackground(attempt, options)).rejects.toBe("temporary");
    await settle();
    expect(attempt).toHaveBeenCalledTimes(2);
  });

  it("waits longer before each retry", async () => {
    const waits: number[] = [];
    const wait = async (ms: number) => {
      waits.push(ms);
    };
    const attempt = vi.fn().mockRejectedValue(new Error("offline"));
    await expect(retryInBackground(attempt, { wait, delayMs: 100 })).rejects.toThrow();
    await settle();
    expect(waits).toEqual([100, 200, 300]);
  });
});
