# Decision Governance Platform — v1.0.0 Release Notes

**Freeze commit:** `5ae4f70` · **Baseline:** 1006 tests passing · **Status:** FROZEN.

## Components (frozen core)

- `decision-governance` 1.0.0 — governance kernel (lifecycle records, audit,
  identity, policy, ports, services, vocabulary).
- `dgm-provider-framework` 0.1.0 — neutral provider contracts, registry,
  deterministic resolution, conformance kits.
- `dgm-actiongate-provider` 0.1.0 — first real action-governance provider.
- `dgm-tap-provider` 0.1.0 — first real assertion-governance provider.

## Frozen architectural behaviour (validation, not core product)

- `dgm-enterprise-validation-pilot` 0.1.0, `dgm-comparative-governance-benchmark`
  0.1.0, `dgm-provider-heterogeneity-validation` 0.1.0.
- `dgm-baseline-assertion-provider` / `dgm-baseline-action-provider` 0.1.0 —
  validation providers, not core product.

## Validated capabilities (synthetic scenarios)

- Full cross-provider workflow, 90/90 scenarios, all safety invariants (Phase 5I).
- Comparative governance value: the full architecture prevented every unsafe
  outcome the no-governance baseline allowed (27→0); TAP and ActionGate additive
  (Phase 6A).
- Heterogeneity: multiple providers per family, deterministic resolution,
  capability/compatibility enforcement, bounded fail-safe fallback, no governance
  shopping, 20/20 invariants (Phase 6B).

## Compatibility guarantees

- The four `*.api` public surfaces are frozen; breaking changes fail
  `platform_freeze` verification unless the platform major is advanced.
- Dependency direction, package ownership, lifecycle/authority boundaries,
  fail-safe behaviour, execution separation, and audit/trace invariants are frozen
  (F1–F20).
- Change classes: PATCH / MINOR / MAJOR / APPLICATION_LOCAL (see VERSIONING_POLICY).

## Maintenance rules

Verify with `python -m platform_freeze.verify`; classify changes with
`python -m platform_freeze.classify_change`. MAJOR/UNCLASSIFIED changes are blocked
pending explicit architectural review.

## Known limitations

- Single-process, in-memory repositories; a single offline deterministic execution
  adapter; deterministic reference providers (not production models).
- No concurrent provider contention, rolling upgrades, live integrations, UI,
  multi-tenancy redesign, or public package publishing.
- The neutral request contract carries no `tenant` field (a candidate for a future
  backward-compatible MINOR extension once multiple real providers require it).

## Out-of-scope claims (explicitly NOT made)

Production readiness, regulatory compliance/certification, fairness conclusions,
and customer ROI. All validation is synthetic; scenario prevalence affects
aggregate rates.
