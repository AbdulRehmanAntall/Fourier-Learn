import Link from "next/link";

import type { Schemas } from "@/lib/api/client";

// The end of a lesson (docs/frontend.md §6.8). For now: the modules watched and a way home.
// Still to come: the concepts taught with their confidence (GET /api/progress), and the
// See progress and New lesson buttons once those screens exist.

export function LessonSummary({ lesson }: { lesson?: Schemas["Lesson"] }) {
  return (
    <div className="flex flex-col gap-5 rounded-lg border border-current/15 p-6">
      <h1 className="text-2xl font-semibold">You finished the lesson</h1>
      {lesson && (
        <div>
          <h2 className="text-sm font-semibold opacity-70">{lesson.title}</h2>
          <ol className="mt-2 list-decimal space-y-1 pl-5">
            {lesson.modules.map((module) => (
              <li key={module.id}>{module.title}</li>
            ))}
          </ol>
        </div>
      )}
      <div>
        <Link
          href="/"
          className="inline-flex h-11 items-center rounded-full bg-blue-600 px-6 font-semibold text-white hover:bg-blue-700"
        >
          Home
        </Link>
      </div>
    </div>
  );
}
