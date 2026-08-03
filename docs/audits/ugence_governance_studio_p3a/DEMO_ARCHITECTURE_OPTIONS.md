# Demo Architecture Options

The Governance Studio is a **presentation and orchestration layer** over the
installed AWC package. It must never re-implement adaptation, disposition,
eligibility, ranking, composition, permission bounding, fallback planning, plan
fingerprinting, replay, or comparison. This note records the options considered for
the overall shape (decided in P3A; implemented across P3B–P3E).

## Fixed constraints

- Frontend must not import Python logic; it talks to the demo API over HTTP.
- The demo API must not duplicate AWC policy logic; it selects scenarios, validates
  request envelopes, calls public AWC functions, serializes canonical results, and
  provides view projections.
- Everything is offline and deterministic — no external model APIs, no live
  registry, no runtime execution.

## Option A — Single deployable container (frontend + API + fixtures) — CHOSEN direction

```
Browser
   ↓ HTTPS
Thin web frontend (static build)
   ↓ HTTP (same origin)
Deterministic demo API (Python)
   ↓ in-process import
ugence-agent-workforce-composer (installed package)  +  packaged demo_data/
```

- **Pros:** matches the P3E "prefer a single deployable container initially"
  guidance; simplest to reason about for determinism and security; one image to
  scan and promote; fits the 1 vCPU / 2 GB target.
- **Cons:** frontend and API scale together (acceptable for a 5–20 user demo).

## Option B — Separate frontend and API services

- **Pros:** independent scaling; clean CORS story.
- **Cons:** more moving parts, two images, more deployment surface than a private
  investor demo needs. Deferred; the API keeps a configurable-CORS + auth seam so
  this remains possible later.

## Option C — Static frontend calling pre-baked JSON (no API)

- **Pros:** trivially cheap; no server.
- **Cons:** loses the live "validate → call real AWC → serialize" story, the
  what-if perturbations (P3D), replay, and plan comparison; can't demonstrate typed
  failure envelopes as API responses. Rejected as the primary architecture, but the
  frozen `expected_outputs/` do double as a fixture-smoke oracle for the API.

## Monorepo conventions observed

- Web apps live under `apps/` (existing `apps/console` is a Vite + React + TS SPA).
  Governance Studio takes `apps/ugence-governance-studio/`.
- Python capabilities live under `packages/` with per-package `pyproject.toml`,
  `tests/`, and an isolated distribution verifier; CI is path-scoped under
  `.github/workflows/<name>-ci.yml` and every capability CI ends with a blocking
  `platform-freeze` job. The demo API (P3B) will follow the same CI shape.
- Frontend stack for a greenfield surface: **Next.js + React + TypeScript** (P3C),
  with API types generated from the frozen OpenAPI contract (P3B).

## P3A scope of this decision

P3A commits only the **boundary and contracts**: the app root, `ARCHITECTURE.md`,
the demo scenario fixtures in real AWC schemas, frozen expected outputs, narratives,
and tests. No backend or frontend application code is created in this stage.
