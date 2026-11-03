import { Suspense } from "react";

import { LessonPlayer } from "@/features/player/LessonPlayer";

// The lesson player (docs/frontend.md §5.5, §6). With Cache Components the lesson id is only
// known at request time, so it is read inside a Suspense boundary.

export default function LessonPage({ params }: PageProps<"/lessons/[lessonId]">) {
  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 sm:px-6">
      <Suspense fallback={<p role="status">Loading your lesson…</p>}>
        {params.then(({ lessonId }) =>
          /^[1-9]\d*$/.test(lessonId) ? (
            <LessonPlayer lessonId={Number(lessonId)} />
          ) : (
            <p role="alert">This lesson doesn&apos;t exist.</p>
          ),
        )}
      </Suspense>
    </main>
  );
}
