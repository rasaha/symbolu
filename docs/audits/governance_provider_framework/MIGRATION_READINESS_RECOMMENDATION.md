# Migration-Readiness Recommendation — Governance Provider Framework

Audit-only. This document selects exactly one recommendation and defines the
later (not-now) migration sequence.

## Selected recommendation

> ## READY — migrate one canonical Governance Provider Framework package

## Why Option 1 (and not the others)

| Option | Verdict | Reason |
|---|---|---|
| **1. Migrate one canonical framework package** | **SELECTED** | The framework has a coherent, capability-neutral boundary; neutral contracts are already carved out; it owns no authority; it has one frozen public API; it already builds as an independent private wheel; dependency direction is correct and acyclic. |
| 2. Split provider SDK/framework from concrete providers | Rejected | Its premise ("shared framework code is mixed with capability-specific providers") is **false**. TAP, ActionGate, and the baselines are already separate packages with their own wheels. The `reference/` providers inside the framework are deterministic *framework-validation* references (explicitly "NOT TAP/ActionGate"), not capability implementations. |
| 3. Preserve as compatibility facade, migrate providers separately | Rejected | `governance_providers` is **not** primarily aggregation/compat. ~1,442 non-test LOC of real, single-sourced mechanism (registry, resolution, configuration, observability, fingerprint, adapters, conformance kit) live here. It is `CANONICAL_IMPLEMENTATION`, not a facade. |
| 4. STOP — boundary architecturally unclear | Rejected | The boundary is clear and machine-enforced (F16–F20; `test_dependency_boundaries.py`; conformance AST checks). Authority, contracts, framework logic, and implementations are already cleanly separable — and largely already separated. |
| 5. STOP — dependency direction prevents migration | Rejected | Dependency direction is correct: framework → {`ugence_governance_contracts` pure leaf, `decision_governance.api` kernel facade}. **Zero** upward imports (test-enforced). No cycle (F20 green). The framework→kernel edge is the designed adaptation seam, confined to `adapters/`, not an invalid dependency on a concrete capability. |

## Readiness conditions (all currently met)

1. ✅ Capability-neutral core with a single public API (`governance_providers.api`, 47 symbols, frozen).
2. ✅ Owns no business/governance authority (adapters normalize to fail-safe INDETERMINATE; coordination transfers no authority).
3. ✅ Neutral contracts already extracted to `ugence_governance_contracts`; framework retains only mechanism + kernel adapters + reference/conformance.
4. ✅ Correct, acyclic, test-enforced dependency direction.
5. ✅ Already independently packaged (`dgm-provider-framework`, symlink, no app/capability code, no business logic).
6. ✅ Green baseline: framework 42 tests, providers 38/30, contracts 45, freeze verifier PASS, terminology PASS.
7. ✅ Prior migration pattern proven three times (StoryGraph, Governance Contracts, Decision Authority).

## One caveat carried forward (non-blocking)

The framework's pure core imports nothing external; only `adapters/` bind
`decision_governance.api`, causing `governance_providers.api` to transitively pull
the kernel + pydantic (the "adapters bleed"). This is a **refinement**, not a
blocker. Recommendation: structure the canonical package so the kernel-bound
adapters are an isolated sub-package (e.g. `…/adapters/` or `…/runtime/`),
enabling a *later* optional split into `sdk` (pure) + `runtime` (kernel-bound)
distributions **without another migration**. Do **not** perform that split in the
first migration — it would change more than one variable at once.

## Later migration sequence (do NOT execute now)

Only because the verdict is READY, the future phase should proceed as:

1. **Freeze & baseline capture** — record current `core_tree_hashes[governance_providers]`, `governance_providers.api` snapshot, 42 test IDs, `manifest_digest`; confirm green.
2. **Shared provider-framework extraction** — `git mv governance_providers/** → packages/governance-provider-framework/src/ugence_governance_provider_framework/**` (history-preserving), internally isolating `adapters/` as a sub-package.
3. **Compatibility namespace** — leave `governance_providers` as a logic-free, identity-preserving re-export/redirect shim (same objects; removal target aligned with the 0.2.0 contract-shim removal); add source-checkout bootstrap.
4. **Concrete provider separation** — already done at the distribution layer; only repoint provider wheels' `dgm-provider-framework` dependency if the distribution is renamed.
5. **Independent packaging** — canonical distribution `ugence-governance-provider-framework` (deps: `decision-governance==1.0.0`, `ugence-governance-contracts>=0.1.0`); `verify_governance_provider_framework_distribution.py` clean-venv `--no-index` proof.
6. **Consumer migration** — keep all 66 consumers on the compat path (zero edits) to avoid cascading re-baselines, per the Governance Contracts precedent.
7. **API/freeze re-baseline** — recompute the **two** manifest fields (`core_tree_hashes[governance_providers]`, `manifest_digest`) via `platform_freeze.write_manifest`; confirm `governance_providers.api` snapshot **byte-identical**; `api_compatibility` = PATCH. (Optionally fold `ugence-governance-contracts` into the freeze — a separate, reviewed decision.)
8. **Documentation** — update `docs/DGM_PROVIDER_FRAMEWORK.md` + add a migration report under `docs/migrations/governance_provider_framework/`.
9. **PR & merge** — one PR, PATCH/structural, freeze verifier green.

## Which provider migrates first (for the LATER `ugence_*` provider-naming step)

The **framework itself migrates first** — it is the dependency every provider
rests on. When the concrete providers are later canonicalized to `ugence_*`
names, migrate **ActionGate first**, because it is the smallest and simplest with
the strongest-per-line coverage and cleanest ownership:

- Smallest: 1,356 LOC / 30 tests (vs TAP 1,857 LOC / 38 tests).
- Simplest control flow: raises classified errors and lets the control-plane
  adapter normalize — no `fail_safe` flag, no evidence-resolution layer (TAP has both).
- Bounded, well-frozen authority: exact-action authorization (invariants F5, F7, F13).
- Limited consumers, strong dependency-boundary tests, and **no** unresolved
  contract duplication beyond the shared observability/conformance twins (which
  are deferred and capability-owned).

This choice is on architectural grounds (size, simplicity, coupling), **not**
commercial priority.

## Stop conditions for the future phase

Halt the migration and reassess if any of these appear:
- The `governance_providers.api` snapshot hash would change (indicates a semantic change crept in).
- `platform_freeze.verify` fails after the 2-field re-baseline.
- Any consumer requires a code change to keep importing (indicates the shim is not identity-preserving).
- A new upward import (framework → concrete capability/app) is introduced.
- The adapters can no longer be isolated without touching the pure core.
