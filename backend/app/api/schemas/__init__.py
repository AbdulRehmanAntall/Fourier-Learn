"""Request and response bodies of the HTTP API (docs/frontend.md §7).

These models are the API's contract with the frontend: `npm run api:types` turns them into the
frontend's TypeScript types. Phase 2 serves them from the stub (app/stub); later phases replace
the stub behind each endpoint without changing these shapes. Changing one is a contract change,
so it needs a PR that all three of us review.
"""
