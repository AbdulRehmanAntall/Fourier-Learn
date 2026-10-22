import path from "node:path";
import type { NextConfig } from "next";

// Where the Next.js server forwards /api and /media. The browser only ever talks to this app's
// own origin, so the session cookie needs no CORS (docs/frontend.md §4).
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` },
      { source: "/media/:path*", destination: `${BACKEND_URL}/media/:path*` },
    ];
  },
  partialPrefetching: true,
  turbopack: {
    // The repo root has its own package-lock.json (for root scripts); pin the app root here.
    root: path.resolve(__dirname),
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
