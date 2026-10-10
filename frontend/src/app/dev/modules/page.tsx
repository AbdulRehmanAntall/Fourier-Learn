"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  API_URL,
  levelLabel,
  variantFileUrl,
  type BeatManifest,
  type ModuleManifest,
  type VariantSummary,
} from "@/lib/contracts";

// Developer viewer for rendered modules (Phase 1): plays a variant beat by beat from its
// manifest, with captions, concept chips and a progress bar split by beat. It is a tool for
// checking renders, not the student's lesson player.

type Load<T> = { kind: "loading" } | { kind: "ok"; value: T } | { kind: "error"; message: string };

const SPEEDS = [0.75, 1, 1.25, 1.5];

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
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
      <Player manifest={manifest.value} />
      <BeatTable beats={manifest.value.beats} />
    </>
  );
}

function Player({ manifest }: { manifest: ModuleManifest }) {
  const beats = manifest.beats;
  const duration = (upTo: number) =>
    beats.slice(0, upTo).reduce((sum, beat) => sum + beat.duration_s, 0);
  const total = duration(beats.length);

  // Two video elements: one plays the current beat while the other preloads the next, so the
  // switch at a beat boundary does not wait for the network.
  const videos = useRef<(HTMLVideoElement | null)[]>([null, null]);
  const [slots, setSlots] = useState<[number, number]>([0, 1]);
  const [active, setActive] = useState(0);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);

  const current = slots[active];
  const beat: BeatManifest | undefined = beats[current];
  const step = beat?.steps.findLast((s) => s.start_s <= time) ?? beat?.steps[0];
  const chips = beat?.chips.filter((chip) => chip.start_s <= time && time <= chip.end_s) ?? [];

  useEffect(() => {
    videos.current.forEach((video) => video && (video.playbackRate = speed));
  });

  const jumpTo = useCallback(
    (position: number) => {
      const next: [number, number] = [0, 0];
      next[active] = position;
      next[1 - active] = position + 1;
      setSlots(next);
      setTime(0);
      setPlaying(true);
    },
    [active],
  );

  useEffect(() => {
    const video = videos.current[active];
    if (!video) return;
    if (playing) void video.play().catch(() => setPlaying(false));
    else video.pause();
  }, [active, slots, playing]);

  const onEnded = () => {
    if (current + 1 >= beats.length) {
      setPlaying(false);
      return;
    }
    const next: [number, number] = [0, 0];
    next[1 - active] = current + 1;
    next[active] = current + 2;
    setSlots(next);
    setActive(1 - active);
    setTime(0);
  };

  return (
    <div className="rounded-lg border border-black/10 p-4 dark:border-white/15">
      <div className="mb-3 flex items-center justify-between text-sm">
        <span>
          <span className="font-semibold">Beat {current + 1}</span>
          <span className="opacity-60"> {beat?.primitive_id}</span>
        </span>
        <span className="rounded-full border px-3 py-0.5 text-xs">
          {levelLabel(manifest.level)}
        </span>
      </div>

      <div className="relative aspect-video overflow-hidden rounded bg-black">
        {[0, 1].map((slot) => {
          const slotBeat = beats[slots[slot]];
          return (
            slotBeat && (
              <video
                key={slot}
                ref={(element) => {
                  videos.current[slot] = element;
                }}
                src={variantFileUrl(manifest.cache_key, slotBeat.video)}
                preload="auto"
                playsInline
                onTimeUpdate={(e) => slot === active && setTime(e.currentTarget.currentTime)}
                onEnded={() => slot === active && onEnded()}
                className={`absolute inset-0 h-full w-full ${slot === active ? "" : "invisible"}`}
              />
            )
          );
        })}
      </div>

      <p className="mt-3 min-h-12 text-sm">{step?.narration}</p>

      <div className="mt-2 flex min-h-8 flex-wrap gap-2">
        {chips.map((chip) => (
          <span key={chip.term} className="rounded-full border px-3 py-1 text-xs">
            {chip.term}
          </span>
        ))}
      </div>

      <div className="mt-3 flex items-center gap-3 text-sm">
        <button onClick={() => setPlaying(!playing)} className="w-16 rounded border px-2 py-1">
          {playing ? "Pause" : "Play"}
        </button>
        <button
          onClick={() => {
            const video = videos.current[active];
            if (video) video.currentTime = 0;
          }}
          aria-label="Restart beat"
          className="rounded border px-2 py-1"
        >
          ↺
        </button>
        <div className="flex flex-1 gap-1" aria-label="Progress by beat">
          {beats.map((b, i) => (
            <button
              key={b.index}
              onClick={() => jumpTo(i)}
              style={{ flexGrow: b.duration_s }}
              aria-label={`Play beat ${i + 1}`}
              className="h-2 basis-0 overflow-hidden rounded bg-black/15 dark:bg-white/20"
            >
              <span
                className="block h-full bg-blue-500"
                style={{
                  width: `${i < current ? 100 : i > current ? 0 : (100 * time) / b.duration_s}%`,
                }}
              />
            </button>
          ))}
        </div>
        <span className="tabular-nums opacity-70">
          {formatTime(duration(current) + time)} / {formatTime(total)}
        </span>
        <button
          onClick={() => setSpeed(SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length])}
          className="w-14 rounded-full border px-2 py-1 text-xs"
        >
          {speed}x
        </button>
      </div>
    </div>
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
