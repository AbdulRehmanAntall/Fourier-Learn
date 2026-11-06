"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import type { Schemas } from "@/lib/api/client";
import { definitionOptions } from "@/lib/api/hooks/player";

// The concept chips of the current moment, under the captions (docs/frontend.md §6.6). Each
// definition is fetched when its chip first appears, so opening it is instant (≤ 3 s, §4.4.1).

const SEPARATOR = "\n";

export function ChipBar({
  chips,
  open,
  onToggle,
}: {
  chips: Schemas["ChipInterval"][];
  open: string | null;
  onToggle(term: string): void;
}) {
  const queryClient = useQueryClient();
  // The time moves several times a second but the chips rarely change: compare them as text.
  const terms = chips.map((chip) => chip.term).join(SEPARATOR);

  useEffect(() => {
    if (!terms) return;
    for (const term of terms.split(SEPARATOR)) {
      void queryClient.prefetchQuery(definitionOptions(term));
    }
  }, [terms, queryClient]);

  return (
    <div className="flex flex-wrap items-center justify-center gap-2">
      {chips.map(({ term }) => (
        <button
          key={term}
          type="button"
          data-chip
          onClick={() => onToggle(term)}
          aria-haspopup="dialog"
          aria-expanded={open === term}
          className={`min-h-11 rounded-full border px-4 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 ${
            open === term
              ? "border-blue-600 bg-blue-600 text-white"
              : "border-current/30 hover:bg-current/10"
          }`}
        >
          {term}
        </button>
      ))}
    </div>
  );
}
