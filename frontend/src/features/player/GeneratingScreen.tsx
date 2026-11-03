"use client";

import { useEffect, useState } from "react";

import type { GenerationStage } from "./lessonMachine";

// Shown while the first module is generated (docs/frontend.md §6.2): the stage it has reached
// and the seconds elapsed. The report's target is at most 90 s to the first beat (§4.4.1).

const STAGES: { stage: GenerationStage; label: string }[] = [
  { stage: "planning", label: "Planning the lesson" },
  { stage: "parameters", label: "Working out the maths" },
  { stage: "narration", label: "Writing the narration" },
  { stage: "rendering", label: "Animating" },
];

export function GeneratingScreen({ stage }: { stage: GenerationStage | null }) {
  const elapsed = useElapsedSeconds();
  const reached = STAGES.findIndex((s) => s.stage === stage);

  return (
    <div className="flex aspect-video flex-col items-center justify-center gap-6 rounded-lg border border-current/15 p-6 text-center">
      <Spinner />
      <div>
        <h1 className="text-xl font-semibold">Preparing your lesson…</h1>
        <p className="mt-1 text-sm tabular-nums opacity-70" aria-live="off">
          {elapsed} s
        </p>
      </div>
      <ol className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm" aria-label="Progress">
        {STAGES.map(({ stage: s, label }, i) => (
          <li
            key={s}
            aria-current={i === reached ? "step" : undefined}
            className={i < reached ? "opacity-60" : i === reached ? "font-semibold" : "opacity-35"}
          >
            {i < reached ? "✓ " : ""}
            {label}
          </li>
        ))}
      </ol>
    </div>
  );
}

export function Spinner({ className = "size-10" }: { className?: string }) {
  return (
    <span
      role="presentation"
      className={`${className} animate-spin rounded-full border-4 border-current/20 border-t-current motion-reduce:animate-none`}
    />
  );
}

function useElapsedSeconds() {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const started = performance.now();
    const timer = setInterval(
      () => setElapsed(Math.floor((performance.now() - started) / 1000)),
      1000,
    );
    return () => clearInterval(timer);
  }, []);
  return elapsed;
}
