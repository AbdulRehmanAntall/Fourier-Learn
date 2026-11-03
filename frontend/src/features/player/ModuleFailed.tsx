import type { Schemas } from "@/lib/api/client";

// A module that couldn't be made (docs/frontend.md §6.8, "A failed module"). With the glossary
// fallback it shows the concept's definition instead. Continue finishes the module.

export function ModuleFailed({
  failure,
  onContinue,
}: {
  failure: Schemas["ModuleFailure"];
  onContinue(): void;
}) {
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-current/15 p-6">
      <p className="text-lg">{failure.message}</p>
      {failure.fallback === "glossary_definition" && failure.definition && (
        // Plain text until KaTeX is added for the maths in definitions (§9).
        <p className="rounded-md bg-current/5 p-4 leading-relaxed">{failure.definition}</p>
      )}
      <div>
        <button
          type="button"
          onClick={onContinue}
          className="h-11 rounded-full bg-blue-600 px-6 font-semibold text-white hover:bg-blue-700"
        >
          Continue
        </button>
      </div>
    </div>
  );
}
