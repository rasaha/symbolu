# AI Hiring — Freeze Declaration

## Declaration

> **AI Hiring v0.6.0 is frozen at commit `b9a0e3a` with readiness classification
> `PACKAGE_READY_FOR_CONTROLLED_PILOT`. No new architecture, lifecycle semantics,
> provider contracts, execution behavior, or governance behavior may be introduced
> prior to completion of a bounded controlled pilot. Only correctness, security,
> packaging, documentation, or pilot-blocking defects may be addressed during the
> pilot period.**

## Scope of the freeze

Frozen as of this declaration:

- **Source baseline:** commit `b9a0e3a18e57fed5a9a10fbcb231eec9f9cc3973`.
- **Product version:** `0.6.0` (pre-1.0 / controlled-pilot).
- **Platform baseline:** Decision Governance Platform `v1.0` (already frozen;
  substantive digest `8b382d9bfed65b8bcf44f9d6f3f9a7138db08bff411c57297dff5721bc2da703`).

## What may NOT change during the freeze

- New architecture, layers, or composition patterns.
- New domain models or hiring-decision semantics.
- New lifecycle states or transitions.
- New provider contracts or provider implementations.
- New public APIs or changes to the existing public surface (`ai_hiring.product`).
- New execution behavior or external-effect adapters.
- New recommendation logic or authorization semantics.
- New integrations or persistence models.

## What MAY change during the freeze

Only the following, and only when justified by a pilot-blocking need:

- **Correctness defects** — a governance-boundary or lifecycle-correctness fault, if
  discovered, is documented and fixed without expanding scope.
- **Security fixes** — vulnerabilities in the shipped surface.
- **Packaging fixes** — build/install/reproducibility issues.
- **Documentation** — clarifications, corrections, and operational documentation.
- **Pilot-blocking defects** — issues that prevent the controlled pilot from running
  safely.

Any change under this exception must: (a) stay application-local (no frozen-platform
modification), (b) preserve the H0–H6 validation record, (c) keep the freeze
verification PASS and 0 dependency violations, and (d) be recorded in the changelog.

## Change-control gate during the pilot

1. A proposed change is classified against the exception list above.
2. If it is **not** on the exception list, it is **deferred** to a post-pilot phase —
   the freeze holds.
3. If it **is** on the exception list, it is implemented application-local, verified
   against the full battery, and recorded (changelog + a PATCH product-version bump
   per [`../product/VERSIONING.md`](../product/VERSIONING.md)).
4. The controlled pilot's stop/escalation criteria (see
   [`CONTROLLED_PILOT_PLAN.md`](CONTROLLED_PILOT_PLAN.md)) govern whether the pilot
   pauses for a fix.

## Verification at freeze time

| Check | Result |
|---|---|
| AI Hiring tests | 778 passed |
| Platform-relevant tests | 917 passed |
| Platform Freeze | PASS (digest unchanged) |
| Dependency-direction violations | 0 |
| Frozen-platform modifications | none |
| Wheel bit-reproducible | yes (`45b2d935…`) |
| Clean-env install + final validation | PASS |

## Lifting the freeze

The freeze is lifted only by an explicit decision after the bounded controlled pilot
completes and its evidence is reviewed. Lifting the freeze opens a new development
phase (e.g. production adapters toward a future 1.0) and requires a new readiness
assessment; it is **not** implied by the pilot merely finishing.

---

*Recorded as part of the AI Hiring controlled-pilot release. See
[`RELEASE_MANIFEST.md`](RELEASE_MANIFEST.md) for the canonical release record.*
