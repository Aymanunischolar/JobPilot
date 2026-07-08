# JobPilot frontend

React + TypeScript + Vite + Tailwind CSS UI for JobPilot. See the
[repo root README](../README.md) for the full project overview.

## Setup

```bash
npm install
npm run dev
```

Runs on `http://localhost:5173` and proxies `/api/*` to the FastAPI
backend on `http://localhost:8000` (see `vite.config.ts`) — start the
backend first (`backend/`, `uvicorn app.api.main:app --reload`).

## Structure

```
src/
  api/client.ts       Typed fetch wrapper for the backend's /api routes
  types.ts             Mirrors backend/app/schemas/models.py
  components/          One component per UI concern (upload, ATS score
                        ring, tailored-resume diff, approval controls, ...)
  hooks/useTheme.ts    Light/dark theme toggle, persisted to localStorage
  App.tsx              Screen state machine: landing -> loading -> results
```

Sessions are shareable via `?session=<id>` in the URL — useful for
sending a paused (awaiting-approval) session to whoever needs to review
it.

## Scripts

- `npm run dev` — dev server with HMR
- `npm run build` — type-check (`tsc -b`) then production build
- `npm run lint` — oxlint
