import { Spinner } from "./GeneratingScreen";

/** Between modules, while the next one isn't ready yet (docs/frontend.md §6.8). */
export function PreparingNext() {
  return (
    <div
      role="status"
      className="flex aspect-video flex-col items-center justify-center gap-4 rounded-lg border border-current/15 p-6"
    >
      <Spinner />
      <p className="text-lg">Preparing the next module…</p>
    </div>
  );
}
