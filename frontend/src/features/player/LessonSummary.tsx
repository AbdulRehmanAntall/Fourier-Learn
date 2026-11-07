"use client";

import Link from "next/link";

import type { Schemas } from "@/lib/api/client";
import { useProgress } from "@/lib/api/hooks/progress";

// The end of a lesson (docs/frontend.md §6.8): the modules watched, the concepts taught with
// their confidence, and where to go next. Confidence comes from the server (rule 1); turning a
// score into a percentage is only for display.

export function LessonSummary({ lesson }: { lesson?: Schemas["Lesson"] }) {
  const watched = lesson?.modules.filter((module) => module.render_status !== "failed") ?? [];

  return (
    <div className="flex flex-col gap-6 rounded-lg border border-current/15 p-6">
      <div>
        <h1 className="text-2xl font-semibold">You finished the lesson</h1>
        {lesson && <p className="mt-1 opacity-70">{lesson.title}</p>}
      </div>

      {watched.length > 0 && (
        <section>
          <h2 className="font-semibold">Modules watched</h2>
          <ol className="mt-2 list-decimal space-y-1 pl-5">
            {watched.map((module) => (
              <li key={module.id}>{module.title}</li>
            ))}
          </ol>
        </section>
      )}

      {watched.length > 0 && (
        <ConceptsTaught conceptIds={new Set(watched.map((module) => module.concept_id))} />
      )}

      <div className="flex flex-wrap gap-3">
        <Link
          href="/home"
          className="inline-flex h-11 items-center rounded-full bg-blue-600 px-6 font-semibold text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          Home
        </Link>
        <SecondaryLink href="/progress">See progress</SecondaryLink>
        <SecondaryLink href="/home">New lesson</SecondaryLink>
      </div>
    </div>
  );
}

function SecondaryLink({ href, children }: { href: string; children: string }) {
  return (
    <Link
      href={href}
      className="inline-flex h-11 items-center rounded-full border border-current/30 px-6 font-semibold hover:bg-current/10 focus-visible:outline-2 focus-visible:outline-offset-2"
    >
      {children}
    </Link>
  );
}

function ConceptsTaught({ conceptIds }: { conceptIds: Set<number> }) {
  const progress = useProgress();
  const concepts = progress.data?.concepts.filter((c) => conceptIds.has(c.concept_id)) ?? [];

  // Nothing to say is better than a blank heading.
  if (progress.isSuccess && concepts.length === 0) return null;

  return (
    <section>
      <h2 className="font-semibold">Concepts taught</h2>
      {progress.isPending && <p className="mt-2 opacity-70">Loading your confidence…</p>}
      {progress.isError && (
        <p role="alert" className="mt-2">
          We couldn&apos;t load your confidence.{" "}
          <button
            type="button"
            onClick={() => progress.refetch()}
            className="min-h-11 font-semibold underline"
          >
            Try again
          </button>
        </p>
      )}
      {concepts.length > 0 && (
        <ul className="mt-2 flex flex-col gap-3">
          {concepts.map((concept) => (
            <ConceptBar key={concept.concept_id} name={concept.name} score={concept.score} />
          ))}
        </ul>
      )}
    </section>
  );
}

function ConceptBar({ name, score }: { name: string; score: number }) {
  const percent = Math.round(score * 100);

  return (
    <li>
      <div className="flex justify-between gap-3 text-sm">
        <span>{name}</span>
        <span className="tabular-nums opacity-70">{percent}%</span>
      </div>
      <div
        role="progressbar"
        aria-label={`Confidence in ${name}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        className="mt-1 h-2 overflow-hidden rounded-full bg-current/15"
      >
        <div className="h-full bg-blue-600" style={{ width: `${percent}%` }} />
      </div>
    </li>
  );
}
