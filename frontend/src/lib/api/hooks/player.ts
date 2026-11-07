import { queryOptions, useQuery } from "@tanstack/react-query";

import { ApiError, client, unwrap, type Schemas } from "../client";
import { retryInBackground } from "../retry";

// The lesson player's calls (docs/frontend.md §6, §7). LessonPlayer's effects call the
// fetchers directly, because the state machine decides when each is needed; the manifest is a
// query, so a `beat_ready` can refresh it by invalidating its key.

export const playerKeys = {
  lesson: (lessonId: number) => ["lesson", lessonId] as const,
  currentModule: (lessonId: number) => ["lesson", lessonId, "current-module"] as const,
  manifest: (cacheKey: string) => ["manifest", cacheKey] as const,
  definition: (term: string) => ["glossary", term] as const,
};

const lessonPath = (lessonId: number) => ({ params: { path: { lesson_id: lessonId } } });

export const fetchLesson = (lessonId: number) =>
  unwrap(client.GET("/api/lessons/{lesson_id}", lessonPath(lessonId)));

export const fetchCurrentModule = (lessonId: number) =>
  unwrap(client.GET("/api/lessons/{lesson_id}/current-module", lessonPath(lessonId)));

export const finishModule = (lessonId: number, moduleId: number) =>
  unwrap(
    client.POST("/api/lessons/{lesson_id}/modules/{module_id}/finish", {
      params: { path: { lesson_id: lessonId, module_id: moduleId } },
    }),
  );

export const savePosition = (lessonId: number, position: Schemas["Position"]) =>
  unwrap(
    client.POST("/api/lessons/{lesson_id}/position", { ...lessonPath(lessonId), body: position }),
  );

/** A check answer. It resolves or rejects with the first attempt, so the panel never waits on
 * a failure, and is retried up to 3 times behind it (§6.8). */
export const answerCheck = (body: Schemas["CheckResponseRequest"]) =>
  retryInBackground(() => unwrap(client.POST("/api/check-responses", { body })), {
    retryable: (error) => error instanceof ApiError && error.isTemporary,
  });

export const chooseBranch = (lessonId: number, body: Schemas["BranchRequest"]) =>
  unwrap(client.POST("/api/lessons/{lesson_id}/branch", { ...lessonPath(lessonId), body }));

export const sendEvents = (events: Schemas["InteractionEventBatch"]["events"]) =>
  unwrap(client.POST("/api/events", { body: { events } }));

/** A chip's definition. Shared by the prefetch and the overlay, so a prefetched chip opens
 * instantly (§6.6); definitions hardly change during a lesson, so it stays fresh for a while. */
export const definitionOptions = (term: string) =>
  queryOptions({
    queryKey: playerKeys.definition(term),
    queryFn: () => unwrap(client.GET("/api/glossary/{term}", { params: { path: { term } } })),
    staleTime: 10 * 60 * 1000,
  });

/** A variant's manifest. It may be partial while beats render (§6.2). */
export function useManifest(cacheKey: string) {
  return useQuery({
    queryKey: playerKeys.manifest(cacheKey),
    queryFn: () =>
      unwrap(
        client.GET("/api/variants/{cache_key}/manifest", {
          params: { path: { cache_key: cacheKey } },
        }),
      ),
  });
}
