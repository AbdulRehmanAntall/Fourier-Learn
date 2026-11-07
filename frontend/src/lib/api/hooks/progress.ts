import { useQuery } from "@tanstack/react-query";

import { client, unwrap } from "../client";

/** The student's confidence per concept (docs/frontend.md §7, Progress). */
export function useProgress() {
  return useQuery({
    queryKey: ["progress"],
    queryFn: () => unwrap(client.GET("/api/progress")),
  });
}
