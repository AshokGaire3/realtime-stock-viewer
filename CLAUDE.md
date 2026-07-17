# Project instructions

Monorepo: `frontend/` (React 18 + TS + Vite + Tailwind + Recharts), `backend/` (FastAPI).
See [README.md](README.md) for architecture and [backend/.env.example](backend/.env.example) for config.

## Verifying every feature change

**No feature change is done until it has been run and observed.** Type-checking, tests
passing, and "the code looks right" are not verification — they prove nothing about whether
the feature works.

For every feature change:

1. **Run the real thing.** Boot the app and drive the actual surface — click the UI, hit the
   HTTP endpoint. Not an import-and-call of the changed function.
2. **Take a screenshot** of the affected UI and *inspect it*. Don't just capture it and move
   on — look at it and say what you see. Attach/reference it in the report.
3. **Check for errors.** Browser console, network tab, and the backend log. A clean-looking
   screen with red console errors is a failing change.
4. **Probe the edges, not just the happy path.** Empty/invalid input, wrong method, unknown
   symbol, stale state, doing it twice. A happy-path replay is half a verification.
5. **Report improvements, not just pass/fail.** Anything that made you pause — friction, odd
   defaults, slowness, confusing errors — gets written down. You're the only one who ran it.

Report honestly: if something is broken or was skipped, say so with the raw output. Never
report a change as working when it hasn't been observed working.

## Frontend practices

Write the **least code that does the job**, using current best-practice APIs:

- **Prefer less code.** No wrapper/abstraction until there are ≥2 real callers. Delete dead
  code rather than commenting it out. If a component needs a long explanation, simplify it.
- **Use the modern version of the API.** Current React (function components + hooks, no class
  components, no legacy lifecycle), current TS (no `any` — use `unknown` + narrowing), native
  platform APIs (`fetch`, `Intl.NumberFormat`) over hand-rolled helpers or a new dependency.
- **Don't add a dependency** for something the stack already does. Check `package.json` first.
- **Type it properly.** Shared API shapes live in `frontend/src/types/financial.ts` and must
  mirror the backend Pydantic schemas in `backend/app/schemas.py` — no client-side reshaping.
- **Reuse what's there.** Match surrounding naming, comment density, and idiom. Tailwind
  utilities over new CSS files; existing components over near-duplicates.
- **Never call upstream market APIs from the browser.** All market data goes through the
  backend proxy (`/api/*`) — putting keys in the client is the exact bug this backend exists
  to fix. No `VITE_*_API_KEY` for upstream providers.

## Backend practices

- Upstream API keys and the Anthropic key stay server-side, loaded via `app/config.py`.
- Upstream calls go through the TTL cache (`app/services/cache.py`) to respect rate limits.
- Fall back gracefully when a provider errors or no key is set — but the response must make
  clear the data is synthetic; never present fallback data as live.
