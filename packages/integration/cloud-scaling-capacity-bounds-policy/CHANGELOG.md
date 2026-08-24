# Changelog — `ugence-cloud-scaling-capacity-bounds-policy`

All notable changes to this distribution. This package follows the Cloud Scaling
phase numbering; each entry names the phase that produced it.

## 0.1.0 — Cloud Scaling Phase 5B-3 (R-8 subphase): the capacity-bounds family

First release. Makes a capacity bound **issuable** for the first time, and stops
there.

### Added

- **`CapacityBoundsPolicy`** — a declarative, versioned, digest-bound artifact
  carrying one or more `CapacityBound`s, each stating `max_permitted_magnitude`
  and `max_permitted_delta` for one `action_type`, optionally narrowed by
  `resource_class`. At least one bound is required: a bounds artifact that bounds
  nothing would resolve `RESOLVED` and look like coverage.
- **`CapacityBoundsPolicyMetadata`** — this family's own identity envelope, not
  UVI's. Scope and tenant are validated as one fact: a `GLOBAL` policy carries the
  authority's canonical empty tenant component, and a `TENANT` policy must name a
  non-empty tenant. The effective interval is half-open `[from, to)` and an empty
  one is refused rather than issued as unresolvable.
- **`CapacityBoundsPolicyFamilyAdapter`** — the shared Policy Authority's second
  policy family, and the first registered from **outside** the authority's own
  distribution. Recognition is an exact runtime type test, not `isinstance`.
  `policy_type` is a constant rather than `type(artifact).__name__`, so a class
  rename cannot silently move every body digest.
- **Canonical projection** mirroring the UVI adapter's discipline: exactly one
  declared path, `metadata.content_digest`, is removed — by path, not by name, and
  removed rather than blanked, so no sentinel participates and no fixed point is
  involved.
- **Typed, fail-closed construction errors** rooted at
  `CapacityBoundsPolicyError`. `bool` is refused as a ceiling despite subclassing
  `int`: a bound of `True` silently meaning `1` is exactly the coercion a policy
  artifact must not perform. A delta ceiling above the magnitude ceiling is
  refused as incoherent rather than accepted as generous.
- **A measured import boundary.** Exactly one first-party dependency, reached only
  through `ugence_policy_authority.api`; the authority's `core.*` internals are
  never touched. `tests/test_import_boundary.py` asserts every prohibition against
  the shipped source and the packaging metadata.

### Deliberately not done

- **No comparison against a candidate.** This package does not compare a bound
  against a candidate's `max_permitted_magnitude` / `max_permitted_delta`. That
  reconciliation is a later subphase with its own ruling, and this package holds
  no candidate type with which to perform it.
- **No action-type reconciliation.** `action_type` is a free token. Importing
  `ugence-cloud-scaling-authorization-contracts` to borrow the Phase 4C/D-4
  canonical action-type set would place the Risk Authority transitively behind a
  declarative artifact. Recorded as deferred rather than silently assumed.
- **No signing, authorization, evaluation, clock or runtime state.**
- **Not wired.** No composition root registers this adapter today. The family is
  issuable and resolvable; it is not on any runtime path.
