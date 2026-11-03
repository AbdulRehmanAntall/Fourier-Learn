import type { Schemas } from "@/lib/api/client";

import { stepAt } from "./useTimeline";

/** The narration of the step being played, under the video as in the wireframe (§6.5). */
export function Captions({ beat, time_s }: { beat?: Schemas["BeatManifest"]; time_s: number }) {
  return (
    <p className="min-h-14 px-1 text-center text-lg leading-snug">
      {beat && stepAt(beat, time_s).narration}
    </p>
  );
}
