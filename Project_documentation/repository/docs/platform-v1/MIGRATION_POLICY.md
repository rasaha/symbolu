# Platform v1.0 — Migration Policy

## Consuming the platform

Applications depend on the frozen public APIs:

- `decision_governance.api` — governance kernel.
- `governance_providers.api` — provider framework (registry, resolution, adapters).
- `tap_provider` / `actiongate_provider` — concrete providers, wired via the
  framework registry and control-plane / assessment-integration adapters.

Applications never import the frozen trees' internal modules and never edit them.

## Migrating an existing consumer (AI Hiring)

AI Hiring predates the frozen `*.api` surfaces and currently imports several kernel
modules directly (e.g. `decision_governance.audit`, `.services`). Migration to the
frozen public API is **APPLICATION_LOCAL** and does not require a platform change:

1. Replace direct kernel-internal imports with `decision_governance.api` equivalents.
2. Introduce provider governance where the application wants AI assertion checks
   (TAP) or action authorization (ActionGate), through the framework registry — see
   `AI_HIRING_INTEGRATION_GUIDE.md`.
3. Keep hiring vocabulary/evidence/rubrics in `domains.hiring`; keep composition in
   `applications.ai_hiring`.

## When a migration reveals a platform gap

If a real application workflow exposes a reproducible platform defect, do **not**
patch around it silently. File it with: failing scenario, expected vs actual,
root cause, why an additive provider or application-layer fix is insufficient, and
compatibility impact (per the phase freeze rules). Only a proven defect justifies a
MAJOR platform change.

## Version pinning

Pin exact component versions (`decision-governance==1.0.0`,
`dgm-provider-framework==0.1.0`, `dgm-tap-provider==0.1.0`,
`dgm-actiongate-provider==0.2.0`). A platform minor upgrade is additive and
backward compatible; a major upgrade requires re-validation.
