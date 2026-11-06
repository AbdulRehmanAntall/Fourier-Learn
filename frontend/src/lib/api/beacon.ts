import type { Schemas } from "./client";

// sendBeacon helpers for `pagehide` (docs/frontend.md §6.9, §6.10). A beacon outlives the page,
// which a fetch may not, and needs no CORS because the API is same-origin (§4). Each returns
// false if the browser wouldn't queue it, for example past its size limit.

function beacon(url: string, body: unknown) {
  return navigator.sendBeacon(url, new Blob([JSON.stringify(body)], { type: "application/json" }));
}

export const sendEventsBeacon = (events: Schemas["InteractionEventBatch"]["events"]) =>
  beacon("/api/events", { events });

export const sendPositionBeacon = (lessonId: number, position: Schemas["Position"]) =>
  beacon(`/api/lessons/${lessonId}/position`, position);
