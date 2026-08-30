# KaiOPS Web

The operator console for KaiOPS — an AI SRE copilot that correlates multi-cloud
telemetry to find root causes, grounded in a service registry you control.

This is a ground-up rewrite of `kaiops-ui/`. It talks to the same FastAPI
backend in `../sre-agent-backend`.

---

## Quick start

```bash
npm install
cp .env.example .env      # defaults work against a backend on :8000
npm run dev               # http://localhost:5173
```

The dev server proxies `/api`, `/run`, `/apps` and `/list-apps` to
`VITE_PROXY_TARGET` (default `http://localhost:8000`), so there is no CORS
setup and no hardcoded backend anywhere in the source.

| Script | What it does |
|---|---|
| `npm run dev` | Dev server with HMR |
| `npm run build` | Typecheck (`tsc -b`) then production bundle |
| `npm run typecheck` | Types only |
| `npm run preview` | Serve the built bundle locally |
| `npm run lint` | ESLint, zero-warning policy |

---

## Architecture

```
src/
  lib/
    api/          One axios client, typed endpoints, wire types
    auth/         Session provider — the server owns identity
    queryClient   React Query config + centralised query keys
    motion.ts     Shared animation vocabulary
  components/
    ui/           Primitives (Radix-backed, accessible by construction)
    layout/       Shell, sidebar, top bar, ⌘K palette
    chat/         Console: markdown, reasoning timeline, approval gate
    charts/       Chart furniture + the validated palette
    three/        WebGL — ambient field, service topology, error boundary
  pages/          One file per route
```

### Where state lives

Server state lives in **React Query only**. There is no parallel copy in
`localStorage`. The previous build treated `localStorage` as the source of
truth for chat sessions while the backend held its own copy, and the two drifted
silently — a cleared session would reappear on the next sync. The only things
persisted client-side are the auth token and two UI preferences.

### Identity

`AuthProvider` calls `GET /auth/me` on every boot and takes the role from that
response. A cached user object is never trusted for authorisation decisions.
This matters: the previous build read `role` straight out of `localStorage`, so
editing one storage key granted the full admin UI.

Client-side role gates (`ProtectedRoute`, conditional nav) are UX only — the
backend authorises every request independently.

---

## Conventions worth keeping

**Colour lives in tokens.** No hex values in components. Every colour is an HSL
triplet in a CSS variable (`src/styles/globals.css`) so Tailwind's `/alpha`
modifier works and themes can change without a rebuild.

**Chart colours are validated, not chosen.** The eight categorical series steps
were snapped so the whole ramp clears, against the dark chart surface:
OKLCH lightness inside the dark band, chroma ≥ 0.10, adjacent-pair separation
under simulated protanopia/deuteranopia (worst pair ΔE 9.4), and ≥ 3:1 contrast.
**Re-run a palette validator before changing them** — brightening them for "pop"
is exactly what breaks CVD separation.

Status colours (`ok` / `warn` / `danger`) are reserved for state and never
reused as "series 4". Every status is conveyed by shape or label as well as
hue, so nothing depends on colour alone.

**Accessibility is structural.** Dialogs, dropdowns, tooltips, tabs and switches
are Radix-backed, so focus trapping, focus restore, Escape handling and ARIA
wiring come for free rather than being remembered per-component. All form
controls go through `<Field>`/`<TextField>`, which wire `htmlFor`/`id` and
`aria-describedby` automatically. There is no `window.alert` or
`window.confirm` anywhere — `ConfirmDialog` and toasts replace them.

**Motion respects the OS.** `prefers-reduced-motion` is honoured globally in CSS
and individually by the WebGL layer.

---

## The WebGL layer

Two canvases, both lazily loaded so `three` (~840 kB) never blocks first paint:

- `AmbientField` — shader-driven particle field on the auth screens. All motion
  happens in the vertex shader; the CPU only uploads a time uniform.
- `ServiceTopology` — the registry as an orbital graph. Ring = cloud provider,
  node size = configuration completeness. Clicking a node opens that service.

Both sit inside `CanvasBoundary`. `<Canvas>` throws synchronously when a GL
context can't be created, and without a boundary that blanks the whole app —
which is a real failure mode on machines with a GPU blocklist, in VDI, and in
headless browsers. With the boundary, the ambient field silently disappears and
the topology view offers the grid instead.

---

## Backend contract notes

Traps this client already accounts for — worth knowing before adding calls:

- **Trailing slashes are load-bearing.** `POST /applications/` and
  `POST /feedback/` require one; `POST /metadata` must *not* have one.
- **Team routes double the segment**: `/api/v1/teams/teams`.
- **Two enum casing families.** Feedback types and statuses are UPPERCASE
  (`THUMBS_UP`, `PENDING`); everything else is lowercase (`admin`, `active`,
  `gcp`). Do not normalise casing across modules.
- **Some scalars are query params, not body fields** — `role`, `is_active`,
  `is_team_lead` on their respective `PUT`s. Sending them as JSON yields a 422.
- **Assistant metadata keys are absent, not false.** Test with
  `'requires_confirmation' in meta`, never `=== false`. On the agent-error path
  metadata is `{error}` only, with no `reasoning_steps`.
- **Timestamps come in two flavours** — chat is UTC-aware (`+00:00`), everything
  else is naive local server time. `parseDate()` in `lib/utils` handles both.

---

## Honest limitations

- **The approval gate sends a follow-up turn.** The backend signals
  `requires_confirmation` but exposes no endpoint to resume a paused tool call,
  so approving posts an explicit confirmation message rather than resuming.
  The UI says so. It does not claim an action succeeded that didn't.
- **The live reasoning panel is an estimate.** `POST /chat/messages` is
  synchronous with no progress channel, so the phase indicator advances on a
  timer. It is labelled "Investigating", not presented as a per-tool trace.
- **Agent answers for AWS and Azure may be fabricated.** That is a backend
  issue, not a UI one — those MCP clients return mock data. The composer
  carries a standing "verify before acting" caveat for that reason.

---

## Verification

Every route was checked in headless Chrome — authenticated and unauthenticated,
with WebGL both enabled (software rasteriser) and disabled — asserting real DOM
output and zero console errors. Worth repeating after significant changes; a
type-clean build does not prove a component renders.
