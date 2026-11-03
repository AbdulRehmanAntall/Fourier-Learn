import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema";

// The one client every backend call goes through (docs/frontend.md §4, rule 2). URLs are
// relative: the browser talks only to this app, which forwards /api to the backend, so the
// session cookie needs no CORS.

export type Schemas = components["schemas"];

/** Every failed call, in one shape: FastAPI's `{"detail": "…"}`, a 422's field errors, or a
 * network failure (status 0). */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly fieldErrors: Record<string, string> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }

  get isNetwork() {
    return this.status === 0;
  }
}

type FieldError = { loc: (string | number)[]; msg: string };

function toApiError(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return new ApiError(status, detail);
  if (Array.isArray(detail)) {
    const fieldErrors: Record<string, string> = {};
    for (const { loc, msg } of detail as FieldError[]) fieldErrors[String(loc.at(-1))] = msg;
    return new ApiError(status, "Please check the highlighted fields.", fieldErrors);
  }
  return new ApiError(status, "Something went wrong. Please try again.");
}

// A 401 anywhere but the auth endpoints means the session has ended: send the student to log
// in, and back here afterwards. The auth endpoints answer 401 as part of their normal job
// (`GET /api/auth/me` when nobody is logged in, a wrong password). This is a full page load on
// purpose, not a router push: it drops every query cached for the old session.
const redirectOnUnauthorized: Middleware = {
  onResponse({ request, response }) {
    const { pathname } = new URL(request.url);
    if (
      response.status === 401 &&
      typeof window !== "undefined" &&
      !pathname.startsWith("/api/auth/") &&
      window.location.pathname !== "/login"
    ) {
      const next = window.location.pathname + window.location.search;
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- see above
      window.location.assign(`/login?next=${encodeURIComponent(next)}`);
    }
  },
};

export const client = createClient<paths>({ baseUrl: "", credentials: "include" });
client.use(redirectOnUnauthorized);

/** The data of a call, or an `ApiError` thrown, so TanStack Query sees a failure:
 * `const lesson = await unwrap(client.GET("/api/lessons/{lesson_id}", { params }))`. */
export async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let result: Awaited<typeof call>;
  try {
    result = await call;
  } catch {
    throw new ApiError(0, "Can't reach FourierLearn. Check your connection and try again.");
  }
  if (result.error !== undefined || !result.response.ok) {
    throw toApiError(result.response.status, result.error);
  }
  return result.data as T;
}

/** URL of a file named in a manifest (paths are relative to the variant's directory). */
export const variantFileUrl = (cacheKey: string, path: string) =>
  `/media/variants/${cacheKey}/${path}`;
