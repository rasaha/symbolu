# Decision Governance Platform v1.0 — Overview

**Status: FROZEN as Platform v1.0.** Freeze commit `5ae4f70` (Phase 6B), baseline
**1006 tests passing**. This document is the entry point to the Platform v1.0
release set (`docs/platform-v1/`).

## What the platform is

A domain-neutral governance architecture that separates **assertion governance**
(is a claim supported by evidence?), **action governance** (may a prepared action
be authorized?), and **external execution** (dispatch/observe), around a governance
kernel that owns the lifecycle and audit record. It was extracted and hardened out
of the AI-Hiring workstream and validated independently across an enterprise
scenario suite, a comparative benchmark, and a heterogeneity/failover study.

```
Frozen Governance Platform v1.0
      ├── DGM Kernel                (decision_governance)
      ├── Provider Framework        (governance_providers)
      ├── ActionGate Provider       (actiongate_provider)   — action governance
      ├── TAP Provider              (tap_provider)          — assertion governance
      └── Provider Compatibility Contracts
                    │
                    ▼
              AI Hiring Application  (consumer)
```

## Frozen components (core runtime)

| Distribution | Package | Version | Role |
|---|---|---|---|
| `decision-governance` | `decision_governance` | 1.0.0 | governance kernel: lifecycle records, audit, identity, policy, ports |
| `dgm-provider-framework` | `governance_providers` | 0.1.0 | neutral provider contracts, registry, resolution, conformance |
| `dgm-actiongate-provider` | `actiongate_provider` | 0.1.0 | first real action-governance provider |
| `dgm-tap-provider` | `tap_provider` | 0.1.0 | first real assertion-governance provider |

## Frozen architectural behaviour (validation harnesses, not core product)

`enterprise_validation_pilot`, `comparative_governance_benchmark`, and
`provider_heterogeneity_validation` freeze the *validated behaviour* of the
architecture. The `baseline_assertion_provider` / `baseline_action_provider`
packages are **validation components**, not part of the core product architecture.

## Validated capabilities (measured on synthetic scenarios)

- End-to-end cross-provider workflow (assertion → assessment → recommendation →
  decision → action → authorization → constraint enforcement → execution →
  reconciliation), 90/90 scenarios, all safety invariants (Phase 5I).
- Comparative governance value vs simpler strategies: the full architecture
  prevented every unsafe outcome the no-governance baseline allowed (Phase 6A).
- Multiple providers per family, deterministic resolution, capability/compatibility
  enforcement, bounded fail-safe fallback, no governance shopping, 20/20 invariants
  (Phase 6B).

## What v1.0 guarantees

The frozen public APIs, package ownership, dependency direction, lifecycle and
authority boundaries, fail-safe behaviour, execution separation, conformance
expectations, and audit/trace invariants are stable and change only under the
compatibility rules in `COMPATIBILITY_POLICY.md` / `VERSIONING_POLICY.md`.

## What v1.0 does NOT claim

No production-readiness, regulatory compliance, fairness conclusions, or customer
ROI is claimed from synthetic validation. Deterministic reference providers were
measured — not production model accuracy. See `CHANGELOG_PLATFORM_V1.md` §
limitations.

## The freeze is machine-verifiable

`platform/PLATFORM_FREEZE_V1.json` records complete hashes of the public API
snapshots, core package trees, conformance suites, dependency rules, and invariant
register. Verify with:

```
python -m platform_freeze.verify --manifest platform/PLATFORM_FREEZE_V1.json
```
