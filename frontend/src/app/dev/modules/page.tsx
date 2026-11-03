"use client";

import { useEffect, useState } from "react";

import { ModulePlayer } from "@/features/player/ModulePlayer";
import {
  levelLabel,
  type BeatManifest,
  type ModuleManifest,
  type VariantSummary,
} from "@/lib/contracts";

// Developer viewer for rendered modules: plays a variant with the lesson player's module player
// (src/features/player), so it can be tried without logging in. It is a tool for checking
// renders, not the student's lesson player.

type Load<T> = { kind: "loading" } | { kind: "ok"; value: T } | { kind: "error"; message: string };

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export default function DevModulesPage() {
  const [variants, setVariants] = useState<Load<VariantSummary[]>>({ kind: "loading" });
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    getJson<VariantSummary[]>("/api/dev/variants")
      .then((value) => {
        setVariants({ kind: "ok", value });
        setSelected((current) => current ?? value[0]?.cache_key ?? null);
      })
      .catch((error: Error) => setVariants({ kind: "error", message: error.message }));
  }, []);

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-10 lg:flex-row">
      <aside className="lg:w-72">
        <h1 className="text-2xl font-bold">Rendered modules</h1>
        <p className="mt-1 mb-4 text-xs opacity-60">
          Render one with <code>npm run render -- &lt;request.json&gt;</code>
        </p>
        {variants.kind === "loading" && <p className="text-sm">Loading…</p>}
        {variants.kind === "error" && (
          <p className="text-sm text-red-600">Backend not reachable ({variants.message})</p>
        )}
        {variants.kind === "ok" && variants.value.length === 0 && (
          <p className="text-sm">Nothing rendered yet.</p>
        )}
        {variants.kind === "ok" && (
          <ul className="space-y-2">
            {variants.value.map((variant) => (
              <li key={variant.cache_key}>
                <button
                  onClick={() => setSelected(variant.cache_key)}
                  className={`w-full rounded-lg border p-3 text-left text-sm ${
                    selected === variant.cache_key
                      ? "border-blue-500"
                      : "border-black/10 dark:border-white/15"
                  }`}
                >
                  <span className="font-semibold">{levelLabel(variant.level)}</span>
                  <span className="opacity-60">
                    {" · "}
                    {variant.duration_s === null
                      ? `${variant.beats_ready}/${variant.beat_count} beats`
                      : formatTime(variant.duration_s)}
                  </span>
                  <span className="mt-1 block text-xs opacity-60">
                    {variant.primitives.join(" → ")}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>
      <section className="flex-1">
        {selected && <VariantView key={selected} cacheKey={selected} />}
      </section>
    </main>
  );
}

function VariantView({ cacheKey }: { cacheKey: string }) {
  const [manifest, setManifest] = useState<Load<ModuleManifest>>({ kind: "loading" });

  useEffect(() => {
    getJson<ModuleManifest>(`/api/variants/${cacheKey}/manifest`)
      .then((value) => setManifest({ kind: "ok", value }))
      .catch((error: Error) => setManifest({ kind: "error", message: error.message }));
  }, [cacheKey]);

  if (manifest.kind === "loading") return <p className="text-sm">Loading manifest…</p>;
  if (manifest.kind === "error") return <p className="text-sm text-red-600">{manifest.message}</p>;
  return (
    <>
      <ModulePlayer manifest={manifest.value} />
      <BeatTable beats={manifest.value.beats} />
    </>
  );
}

function BeatTable({ beats }: { beats: BeatManifest[] }) {
  return (
    <details className="mt-4 text-sm">
      <summary className="cursor-pointer opacity-70">Manifest timings</summary>
      {beats.map((beat) => (
        <div key={beat.index} className="mt-3">
          <p className="font-semibold">
            Beat {beat.index + 1}: {beat.primitive_id} ({beat.duration_s.toFixed(1)} s)
          </p>
          <ol className="mt-1 space-y-1">
            {beat.steps.map((s, i) => (
              <li key={i} className="grid grid-cols-[7rem_1fr] gap-2">
                <span className="tabular-nums opacity-60">
                  {s.start_s.toFixed(2)}–{s.end_s.toFixed(2)} s
                </span>
                <span>{s.narration}</span>
              </li>
            ))}
          </ol>
        </div>
      ))}
    </details>
  );
}

function formatTime(seconds: number) {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}
