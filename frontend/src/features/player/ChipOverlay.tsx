"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useEffectEvent, useRef } from "react";

import { MathText } from "@/components/MathText";
import { definitionOptions } from "@/lib/api/hooks/player";

// A chip's definition (docs/frontend.md §6.6, UC 4.5): a non-modal popover, so the video keeps
// playing and the player's controls still work. It closes with ×, Esc or a click outside, and
// stays open if its chip's interval ends, so a student can finish reading.

export function ChipOverlay({ term, onClose }: { term: string; onClose(): void }) {
  const panel = useRef<HTMLDivElement>(null);
  const definition = useQuery(definitionOptions(term));
  const close = useEffectEvent(onClose);

  useEffect(() => {
    // Focus moves here for keyboard and screen-reader users, and back to the chip afterwards.
    const opener = document.activeElement as HTMLElement | null;
    panel.current?.focus({ preventScroll: true });

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Element;
      // A chip handles its own click: toggling this overlay, or switching to its term.
      if (!panel.current?.contains(target) && !target.closest("[data-chip]")) close();
    };
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown);
      if (opener?.isConnected) opener.focus({ preventScroll: true });
    };
  }, []);

  return (
    <div
      ref={panel}
      role="dialog"
      aria-modal="false"
      aria-labelledby="chip-overlay-title"
      tabIndex={-1}
      className="absolute bottom-full left-1/2 z-10 mb-2 max-h-72 w-full max-w-md -translate-x-1/2 overflow-y-auto rounded-lg border border-current/20 bg-background p-4 text-foreground shadow-lg outline-none"
    >
      <div className="flex items-start justify-between gap-2">
        <h2 id="chip-overlay-title" className="pt-2 text-lg font-semibold">
          {definition.data?.term ?? term}
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="-mt-1 -mr-1 grid size-11 shrink-0 place-items-center rounded-full text-xl hover:bg-current/10 focus-visible:outline-2"
        >
          ×
        </button>
      </div>
      <div className="mt-1 leading-relaxed">
        {definition.isPending && <p className="opacity-70">Loading…</p>}
        {definition.isError && (
          <p role="alert">
            {definition.error.message}{" "}
            <button
              type="button"
              onClick={() => definition.refetch()}
              className="min-h-11 font-semibold underline"
            >
              Try again
            </button>
          </p>
        )}
        {definition.data && (
          <p>
            <MathText text={definition.data.definition} />
          </p>
        )}
      </div>
    </div>
  );
}
