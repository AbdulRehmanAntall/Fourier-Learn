import { useEffect, useState } from "react";

import { sendEventsBeacon } from "@/lib/api/beacon";
import { ApiError } from "@/lib/api/client";
import { sendEvents } from "@/lib/api/hooks/player";

import { EventLogger, FLUSH_INTERVAL_MS, type LoggedEvent, type SendResult } from "./eventLogger";

// One logger per lesson page: flushes every 10 s, and sends what's left by beacon when the page
// closes, including a pause still open, with its time so far (docs/frontend.md §6.10).

async function send(events: LoggedEvent[]): Promise<SendResult> {
  try {
    await sendEvents(events);
    return "sent";
  } catch (error) {
    // After a 401 the client is already redirecting to log in, so that isn't a refusal.
    const refused =
      error instanceof ApiError &&
      error.status >= 400 &&
      error.status < 500 &&
      error.status !== 401;
    return refused ? "refused" : "failed";
  }
}

export function useEventLogger() {
  const [logger] = useState(() => new EventLogger(send));

  useEffect(() => {
    const timer = setInterval(() => void logger.flush(), FLUSH_INTERVAL_MS);
    const onPageHide = () => {
      logger.endPause();
      for (const batch of logger.takeBatches()) {
        if (!sendEventsBeacon(batch)) logger.restore(batch);
      }
    };
    window.addEventListener("pagehide", onPageHide);
    return () => {
      clearInterval(timer);
      window.removeEventListener("pagehide", onPageHide);
      logger.endPause();
      void logger.flush();
    };
  }, [logger]);

  return logger;
}
