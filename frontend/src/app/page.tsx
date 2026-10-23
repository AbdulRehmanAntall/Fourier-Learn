"use client";

import { useEffect, useState } from "react";

// Placeholder home page: shows the backend health checks. No features yet.

type Health = {
  status: string;
  version: string;
  checks: Record<string, boolean>;
};

type PanelState = { kind: "loading" } | { kind: "ok"; health: Health } | { kind: "error" };

export default function Home() {
  const [state, setState] = useState<PanelState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;

    fetch("/api/health", { signal: AbortSignal.timeout(5000), cache: "no-store" })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<Health>;
      })
      .then((health) => !cancelled && setState({ kind: "ok", health }))
      .catch(() => !cancelled && setState({ kind: "error" }));

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-8 px-6 py-16">
      <header>
        <h1 className="text-4xl font-bold tracking-tight">FourierLearn</h1>
        <p className="mt-2 text-sm opacity-70">
          Lessons are not generated yet. Rendered modules can be played in the{" "}
          <a href="/dev/modules" className="underline">
            developer viewer
          </a>
          .
        </p>
      </header>

      <section className="rounded-lg border border-black/10 p-5 dark:border-white/15">
        <h2 className="mb-3 text-lg font-semibold">System status</h2>
        <p className="mb-4 text-xs opacity-60">/api/health</p>

        {state.kind === "loading" && <p className="text-sm">Checking backend…</p>}

        {state.kind === "error" && (
          <p className="flex items-center gap-2 text-sm font-medium text-red-600">
            <Dot ok={false} /> Backend not reachable
          </p>
        )}

        {state.kind === "ok" && (
          <ul className="space-y-2 text-sm">
            <li className="flex items-center gap-2">
              <Dot ok={state.health.status === "ok"} />
              backend <span className="opacity-60">v{state.health.version}</span>
            </li>
            {Object.entries(state.health.checks).map(([name, ok]) => (
              <li key={name} className="flex items-center gap-2">
                <Dot ok={ok} />
                {name}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

function Dot({ ok }: { ok: boolean }) {
  return (
    <span
      aria-label={ok ? "ok" : "failing"}
      className={`inline-block h-2.5 w-2.5 rounded-full ${ok ? "bg-green-500" : "bg-red-500"}`}
    />
  );
}
