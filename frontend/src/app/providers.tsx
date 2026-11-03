"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { ApiError } from "@/lib/api/client";

// One query client in the browser, a fresh one for each server render, so requests on the
// server never share a cache (Next.js guide: client-side data fetching with TanStack Query).

let browserQueryClient: QueryClient | undefined;

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Retry network failures and server errors, not answers like 404 or 409: asking again
        // won't change them.
        retry: (failures, error) =>
          failures < 2 && (!(error instanceof ApiError) || error.isNetwork || error.status >= 500),
      },
    },
  });
}

function getQueryClient() {
  if (typeof window === "undefined") return makeQueryClient();
  browserQueryClient ??= makeQueryClient();
  return browserQueryClient;
}

export function Providers({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={getQueryClient()}>{children}</QueryClientProvider>;
}
