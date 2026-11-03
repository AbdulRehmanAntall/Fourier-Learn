import { useEffect, useEffectEvent } from "react";

import type { Schemas } from "./client";

// One event stream per lesson page (docs/frontend.md §6.11). The SSE event name is the stream
// contract's `type` and the data is its JSON. The stream only carries what happens after it
// opens, so `onOpen` runs on every open, the first and each reconnect: the page refetches the
// lesson there before relying on new events.

type StreamEvent = Schemas["StreamEvent"];

const TYPES: StreamEvent["type"][] = [
  "generation_progress",
  "beat_ready",
  "module_ready",
  "module_failed",
];

export type LessonStreamHandlers = {
  onOpen?(): void;
  onEvent(event: StreamEvent): void;
};

export function useLessonStream(lessonId: number, handlers: LessonStreamHandlers) {
  const onOpen = useEffectEvent(() => handlers.onOpen?.());
  const onEvent = useEffectEvent((event: StreamEvent) => handlers.onEvent(event));

  useEffect(() => {
    // EventSource reconnects by itself after an error, and fires `open` again when it does.
    const source = new EventSource(`/api/lessons/${lessonId}/events`, { withCredentials: true });
    source.onopen = () => onOpen();
    const listener = (message: MessageEvent<string>) => {
      try {
        onEvent(JSON.parse(message.data) as StreamEvent);
      } catch {
        // A malformed message is skipped; the next open refetches the lesson anyway.
      }
    };
    for (const type of TYPES) source.addEventListener(type, listener);
    return () => source.close();
  }, [lessonId]);
}
