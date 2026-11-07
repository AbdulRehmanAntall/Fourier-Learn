"use client";

import { Spinner, useElapsedSeconds } from "./GeneratingScreen";

// Over the paused player while a simpler version is made (docs/frontend.md §6.7). The target is
// at most 90 s (§4.4.1). After that the student can go back to watching, and is offered the
// simpler version if it arrives later.

const LONG_WAIT_S = 90;

export function ImLostOverlay({ onKeepWatching }: { onKeepWatching(): void }) {
  const elapsed = useElapsedSeconds();
  const long = elapsed >= LONG_WAIT_S;

  return (
    <div
      role="status"
      className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-4 rounded-lg bg-black/85 p-6 text-center text-white"
    >
      <Spinner />
      <p className="text-xl font-semibold">
        {long ? "This is taking longer than usual" : "Making a simpler version…"}
      </p>
      <p className="text-sm tabular-nums opacity-80" aria-live="off">
        {elapsed} s
      </p>
      {long && (
        <button
          type="button"
          autoFocus
          onClick={onKeepWatching}
          className="h-11 rounded-full bg-white px-6 font-semibold text-black hover:bg-white/85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
        >
          Keep watching at this level
        </button>
      )}
    </div>
  );
}
