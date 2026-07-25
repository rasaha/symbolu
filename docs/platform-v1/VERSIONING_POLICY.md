# Platform v1.0 — Versioning Policy

The platform version is **1.0.0**. Components carry their own semantic versions
(`decision-governance` 1.0.0; framework/providers 0.1.0) but move together under
the platform freeze.

## Change classes (frozen)

- **PATCH** — correctness/security fixes, documentation corrections, test
  improvements, packaging corrections, semantics-preserving performance. No
  architectural review required.
- **MINOR** — additive optional fields, additive public APIs, new provider
  capabilities, new conformance assertions, backward-compatible observability.
  Allowed only through compatibility review (`COMPATIBILITY_POLICY.md`).
- **MAJOR** — breaking public API, provider-contract redesign, authority-model
  changes, lifecycle changes, dependency-direction changes, altered fail-safe
  behaviour, new provider families, execution-boundary changes. Requires an
  **explicit platform unfreeze** (advance the platform major) and full re-baseline.
- **APPLICATION_LOCAL** — AI-Hiring workflows/ontology/evidence/recommendations/
  policies/composition/UI/APIs. Does **not** affect the platform freeze.

## Bumping rules

- A MINOR platform change bumps the platform minor (1.0.0 → 1.1.0) and the relevant
  component minor; the freeze manifest is regenerated and its digest changes.
- A MAJOR change bumps the platform major (1.x → 2.0.0) and re-baselines the freeze.
- APPLICATION_LOCAL changes never bump the platform version.

## Enforcement

`python -m platform_freeze.classify_change --base <freeze-commit> --head HEAD`
proposes a class and produces evidence; MAJOR and UNCLASSIFIED fail CI unless a
human reviewer passes `--approve`. The tool does not replace architectural review.
