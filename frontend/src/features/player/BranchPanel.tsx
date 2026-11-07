"use client";

import { useEffect, useEffectEvent, useRef, useState } from "react";

import { ApiError, type Schemas } from "@/lib/api/client";
import { chooseBranch } from "@/lib/api/hooks/player";

// The choice after a module (docs/frontend.md §6.8, Fig. 4.5, UC 4.7): one card per option, with
// a countdown that takes the default when it runs out. The endpoint records the branch_choice
// event, so the logger stays out of it. The choice decides what plays next, so unlike a check
// answer the panel waits for it. Even so, it can't trap the student: an answer that won't change
// (a 409 means the choice is already saved) moves on, and any other failure offers Continue.

type Choice = Schemas["BranchOptionOut"]["choice"];
type Chosen = { choice: Choice; timedOut: boolean };

export function BranchPanel({
  lessonId,
  moduleId,
  branch,
  onDone,
}: {
  lessonId: number;
  moduleId: number;
  branch: Schemas["BranchPoint"];
  onDone(): void;
}) {
  const title = useRef<HTMLHeadingElement>(null);
  const [chosen, setChosen] = useState<Chosen | null>(null);
  const [failed, setFailed] = useState(false);
  const [remaining, setRemaining] = useState(branch.timeout_s);
  const fallback = branch.options.find((option) => option.choice === branch.default_choice);

  function send(next: Chosen) {
    setChosen(next);
    setFailed(false);
    chooseBranch(lessonId, {
      module_id: moduleId,
      choice: next.choice,
      timed_out: next.timedOut,
    }).then(onDone, (error: unknown) => {
      if (error instanceof ApiError && !error.isTemporary) onDone();
      else setFailed(true);
    });
  }

  const timeOut = useEffectEvent(() => send({ choice: branch.default_choice, timedOut: true }));
  const waiting = chosen === null;

  // The focus starts here, so keyboard and screen-reader users land on the question.
  useEffect(() => title.current?.focus(), []);

  useEffect(() => {
    if (!waiting) return;
    const started = performance.now();
    const timer = setInterval(() => {
      const left = branch.timeout_s - (performance.now() - started) / 1000;
      setRemaining(Math.max(Math.ceil(left), 0));
      if (left <= 0) {
        clearInterval(timer);
        timeOut();
      }
    }, 250);
    return () => clearInterval(timer);
  }, [waiting, branch.timeout_s]);

  return (
    <section className="flex flex-col gap-5 rounded-lg border border-current/15 p-6">
      <h2 ref={title} tabIndex={-1} className="text-xl font-semibold outline-none">
        Where should the lesson go next?
      </h2>

      <div
        className={`grid gap-3 ${branch.options.length === 3 ? "sm:grid-cols-3" : "sm:grid-cols-2"}`}
      >
        {branch.options.map((option) => (
          <button
            key={option.choice}
            type="button"
            disabled={chosen !== null}
            onClick={() => send({ choice: option.choice, timedOut: false })}
            className={`flex min-h-11 flex-col gap-1 rounded-lg border-2 p-4 text-left focus-visible:outline-2 focus-visible:outline-offset-2 ${
              chosen?.choice === option.choice
                ? "border-blue-600 bg-blue-600/10"
                : chosen
                  ? "border-current/15 opacity-60"
                  : "border-current/25 hover:bg-current/10"
            }`}
          >
            <span className="font-semibold">{option.title}</span>
            <span className="text-sm opacity-80">{option.description}</span>
          </button>
        ))}
      </div>

      {waiting && (
        <div>
          <div className="h-1 overflow-hidden rounded-full bg-current/15">
            <div
              className="h-full bg-blue-600 transition-[width] duration-1000 ease-linear motion-reduce:transition-none"
              style={{ width: `${(100 * remaining) / branch.timeout_s}%` }}
            />
          </div>
          <p className="mt-2 text-sm tabular-nums opacity-70">
            {fallback?.title ?? "Continuing"} in {remaining} s
          </p>
        </div>
      )}

      {chosen && !failed && (
        <p role="status" className="text-sm opacity-70">
          Saving your choice…
        </p>
      )}

      {chosen && failed && (
        <div role="alert" className="flex flex-wrap items-center gap-3">
          <p className="basis-full">We couldn&apos;t save your choice.</p>
          <button
            type="button"
            // The options are disabled now, so the focus needs somewhere to go.
            autoFocus
            onClick={() => send(chosen)}
            className="h-11 rounded-full bg-blue-600 px-6 font-semibold text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            Try again
          </button>
          <button
            type="button"
            onClick={onDone}
            className="h-11 rounded-full border border-current/30 px-6 font-semibold hover:bg-current/10 focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            Continue
          </button>
        </div>
      )}
    </section>
  );
}
