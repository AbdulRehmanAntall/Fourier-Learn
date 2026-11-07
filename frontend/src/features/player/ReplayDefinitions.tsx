"use client";

import { useQuery } from "@tanstack/react-query";

import { MathText } from "@/components/MathText";
import { definitionOptions } from "@/lib/api/hooks/player";

// After "I'm Lost" at Level 1, there is no simpler version: the beat replays with its concept
// definitions open beside the video (docs/frontend.md §6.7), and they stay until closed.

export function ReplayDefinitions({ terms, onClose }: { terms: string[]; onClose(): void }) {
  return (
    <aside
      aria-label="Definitions for this part"
      className="flex shrink-0 flex-col gap-3 overflow-y-auto rounded-lg border border-current/20 bg-background p-4 text-foreground lg:max-h-[24rem] lg:w-80"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-semibold">Definitions</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close definitions"
          className="-my-2 -mr-2 grid size-11 shrink-0 place-items-center rounded-full text-xl hover:bg-current/10 focus-visible:outline-2"
        >
          ×
        </button>
      </div>
      <dl className="flex flex-col gap-3">
        {terms.map((term) => (
          <Definition key={term} term={term} />
        ))}
      </dl>
    </aside>
  );
}

function Definition({ term }: { term: string }) {
  const definition = useQuery(definitionOptions(term));

  return (
    <div>
      <dt className="font-medium">{definition.data?.term ?? term}</dt>
      <dd className="mt-0.5 text-sm leading-relaxed opacity-90">
        {definition.isPending && "Loading…"}
        {definition.isError && "This definition isn't available right now."}
        {definition.data && <MathText text={definition.data.definition} />}
      </dd>
    </div>
  );
}
