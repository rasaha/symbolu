# Dependency Direction — Code Governance

> Documentation only. Authoritative source: `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` v0.2 (§1, §11, §18).
> Verified against live dependency-direction validators at commit `3ec11e4e` (all green).

## 1. Intended dependency graph

```
Code Governance product (products/code-governance)
    ↓ (public surfaces only)
TAP · Decision Authority · ActionGate · ACP · StoryGraph · Model Selection
    ↓
Governance Contracts (neutral) + other neutral contracts
                                   ▲
Governance Provider Framework ─────┘ (depends on neutral contracts; adapts onto DA kernel ports)
    ↓
GitHub Execution Provider (providers/github-execution)

Code Governance product ↓ GitHub Evidence Connector (product connector; no upstream deps)
Code Governance product ↓ GPF ↓ GitHub Execution Provider
```

Direction is strictly **downward**: product → capabilities → neutral contracts; product → connector;
product → GPF → execution provider. Neutral contracts import **only stdlib** (leaf).

## 2. Invariants to preserve (and how they are verified)

| Invariant | Verified by | Status |
|---|---|---|
| providers do not depend upward on products | GPF `conformance` `_no_kernel_internal_imports`; provider `tests/test_dependency_boundaries.py` | ✅ live tests pass |
| governance authorities do not depend on GitHub | DA/StoryGraph/contracts `FORBIDDEN_ROOTS` boundary tests (also bar `cer_v0_1/2/3`) | ✅ pass |
| GitHub-specific types do not enter neutral contracts | neutral contracts are stdlib-only leaf; evidence subsystem has zero GitHub types | ✅ confirmed |
| Workflow Service is not an authority | design §4A; product code (not yet built) | ✅ by design |
| GPF is not a policy engine | GPF owns no ALLOW/DENY; freeze invariants `PLATFORM_FREEZE_V1.json:171-186` | ✅ confirmed |
| Model Selection stays separate | `packages/capabilities/model-selection`; `execution_gate/` is its legacy namespace | ✅ |
| Agent Runtime stays separate unless consumed via public API | not consumed by governance in MVP 1 (§9.1) | ✅ |

## 3. Live validator results (baseline, re-run after docs — §26)

- Platform freeze verifier `dependency_direction` check: **ok**.
- `packages/governance-provider-framework/tests/boundaries/test_dependency_boundaries.py`,
  `packages/capabilities/decision-authority/tests/test_platform_boundaries.py`,
  `packages/governance-contracts/tests/packaging/test_leaf_dependency.py`: **15 passed**.
- Provider dependency-boundary tests (`tap_provider`, `actiongate_provider`): pass within their suites.

Because this audit adds **only documentation** under `docs/audits/`, it cannot change any import edge;
the dependency-direction validators remain green (re-confirmed in §26 / `TEST_AND_VALIDATION_PLAN.md`).

## 4. Risks to the direction (to enforce during implementation)

- The GitHub Execution Provider must depend **only** on neutral contracts + GPF, never on the product
  or on GitHub types leaking into neutral contracts — model on `actiongate_provider/` (pure offline
  core).
- The GitHub Evidence Connector must not import capability internals; it emits neutral `evidence_refs`.
- The Workflow Service must consume capabilities via public surfaces
  (`ugence_decision_authority.api`, `ugence_governance_provider_framework.api`,
  `ugence_governance_contracts`, `tap_provider`, `actiongate_provider`, `ugence_storygraph`) and must
  not be imported by any capability or provider.
- Run the dependency-direction validator (and the freeze verifier's `dependency_direction` check) on
  every implementation PR.
