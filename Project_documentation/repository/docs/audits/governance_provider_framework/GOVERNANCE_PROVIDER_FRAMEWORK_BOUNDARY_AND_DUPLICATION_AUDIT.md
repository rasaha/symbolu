# Governance Provider Framework — Boundary, Duplication, Packaging & Migration-Readiness Audit

**Phase:** audit-only. No source relocated, no public API changed, no provider
behavior altered, no canonical-package migration begun.
**Branch:** `claude/governance-provider-framework-audit-jzdvbe` @ `1a191629`.
**Date:** 2026-08-02.

Companion documents: `ARTIFACT_CLASSIFICATION.md`, `IMPORT_GRAPH.md`,
`PUBLIC_API_AND_CONSUMER_MAP.md`, `CONTRACT_OWNERSHIP_MATRIX.md`,
`DUPLICATION_MATRIX.md`, `PACKAGING_AND_COMPATIBILITY_MAP.md`,
`FREEZE_AND_API_IMPACT_ASSESSMENT.md`, `MIGRATION_READINESS_RECOMMENDATION.md`,
`baseline_manifest.json`, `test_manifest.txt`.

---

## 1. Executive verdict

`governance_providers/` **is** a real, coherent, capability-neutral **Governance
Provider Framework**, not an accidental aggregation. It provides the mechanism to
connect bounded governance capabilities to provider implementations and the DGM
kernel: provider **interfaces** (via the neutral contracts leaf), **registration
& discovery** (registry), **deterministic resolution**, **declarative
configuration**, **lifecycle**, **health**, **observability**, **stable error
translation**, **conformance kits**, and **kernel-port adapters**. It owns **no**
business or governance authority. Its neutral contracts were already extracted to
`ugence_governance_contracts`; its concrete providers (TAP, ActionGate, baselines)
are already separate packages with their own wheels. Dependency direction is
correct, acyclic, and machine-enforced. It already ships as an independent private
wheel.

**Recommendation:** **READY — migrate one canonical Governance Provider Framework
package.**

---

## 2. Current repository state

- **Default branch:** `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`
  (the repo's `HEAD branch`), tip `1a191629` = "Merge PR #1265".
- The last-known merge `1517a71c` (PR #1264, Decision Authority migration) is **no
  longer current** — PR #1265 merged after it; verified directly.
- **Audit branch** `claude/governance-provider-framework-audit-jzdvbe` is at the
  latest default tip (`1a191629`); working tree clean. (This is the harness-mandated
  feature branch; it supersedes the prompt's alternate name.)
- **Integrated completed work — all confirmed present:**
  - StoryGraph canonical package — `packages/capabilities/storygraph` / `ugence_storygraph` ✅
  - StoryGraph documentation canonicalization ✅ (`docs/migrations/storygraph/…`)
  - Governance Contracts canonical package — `packages/governance-contracts` / `ugence_governance_contracts` ✅
  - Terminology foundation — `scripts/validate_terminology.py` **PASS** ✅
  - Decision Authority canonical package — `packages/capabilities/decision-authority` / `ugence_decision_authority`; `decision_governance` is now an identity-preserving shim over it ✅
- **Canonical namespaces confirmed:** `ugence_storygraph`, `ugence_governance_contracts`,
  `ugence_decision_authority`. **`ugence_governance_provider_framework` does not
  exist** — the framework is not yet migrated.
- **Legacy namespaces remain compatibility surfaces:** `decision_governance`
  (→ DA), `governance_providers.{errors,lifecycle,metadata,contracts.*}` (→ contracts leaf),
  `composite_threat_detector` (→ storygraph).
- **Smoke baseline (all green; no pre-existing failures):** platform freeze
  verifier **PASS** (digest `477407…`); terminology validator **PASS**;
  governance-contracts 45, storygraph 316, decision-authority 79,
  governance_providers **42**, tap_provider **38**, actiongate_provider **30**,
  baselines 5+5. (The "42 tests" figure was re-collected directly, not assumed.)
- **Environment:** Linux, Python 3.11.15. Dependency gaps at session start
  (`pytest`, `pydantic`, `numpy`) were pip-installed to run the baseline; **no repo
  files changed** to do so.

---

## 3. Existing responsibilities (what `governance_providers` actually is)

29 non-test modules / 1,442 LOC (+9 test files / 587 LOC). It contains a
combination of exactly these, and nothing else:

| Present | Category | Modules |
|---|---|---|
| ✅ | Provider framework interfaces | via contracts shims → `ugence_governance_contracts` |
| ✅ | Provider registration & discovery | `registry/` |
| ✅ | Provider lifecycle | `ugence_governance_contracts.lifecycle` (shim) + registry lifecycle mgmt |
| ✅ | Shared provider metadata | `metadata` shim (canonical in contracts leaf) |
| ✅ | Deterministic resolution | `resolution.py` |
| ✅ | Declarative configuration | `configuration.py` |
| ✅ | Observability | `observability.py` |
| ✅ | Deterministic fingerprinting | `fingerprint.py` |
| ✅ | Kernel-port adapters | `adapters/` (bind `decision_governance.api`) |
| ✅ | Conformance kits (public) | `conformance/` |
| ✅ | Reference implementations (framework validation) | `reference/` |
| ✅ | Public API aggregator | `api/` |
| ✅ | Compatibility shims | `errors`, `lifecycle`, `metadata`, `contracts/*` |
| ✅ | Packaging glue | `packaging/dgm-provider-framework/` (symlink wheel) |
| ❌ | Capability-specific provider adapters | **none** (TAP/ActionGate are separate packages) |
| ❌ | Concrete provider implementations | **none in this package** |
| ❌ | Console/application code | **none** |
| ❌ | Policy / authority / adjudication logic | **none** |
| ❌ | Duplicated capability implementations | **none in this package** |
| ❌ | Deprecated/historical code | **none** (shims are live compat, not dead code) |

**Answers to the twelve audit questions:**
1. Is there a real capability-neutral framework? **Yes.**
2. Its exact responsibility? Connect bounded capabilities to provider
   implementations and the kernel via neutral contracts, a registry, deterministic
   resolution, config, lifecycle/health, observability, error translation,
   conformance, and kernel-port adapters.
3. One coherent public API? **Yes** — `governance_providers.api` (47 symbols, frozen).
4. Owns any domain/governance authority? **No.**
5. Records belonging in Governance Contracts instead? **Already there** — the full
   neutral closure was extracted; framework paths are shims.
6. Records belonging to individual capabilities? Vendor vocabulary (`Tap*`,
   `ActionGate*`) already lives in the provider packages.
7. Concrete providers that should stay separate packages? TAP, ActionGate,
   baselines — **already separate**.
8. Which files are compatibility surfaces? `errors`, `lifecycle`, `metadata`,
   `contracts/*` (8 modules).
9. Which implementations are duplicated? Only in the **providers** (observability +
   conformance twins) — capability-owned, deferred; none in the framework.
10. Independently packageable without pulling apps/capabilities? **Yes — already is.**
11. Correct dependency direction? framework → {contracts leaf, kernel api}; no
    upward imports.
12. Migration safe now? **Yes — READY (Option 1).**

---

## 4. Actual authority boundary

The framework holds **zero** authority and correctly refuses to become a router,
adjudicator, orchestrator, universal policy engine, or umbrella:

- **No adjudication.** It never decides assertion truth, action authorization,
  clearance, or risk. Those are TAP / ActionGate / ACP / StoryGraph.
- **Coordination ≠ authority.** Resolution is deterministic and auditable (F18),
  never "guesses," and fallback cannot be used for governance shopping (F19).
- **Fail-safe at the seam.** Adapters normalize any provider failure to
  `INDETERMINATE` (action) / `UNKNOWN` (execution); a vendor exception never leaks
  into the kernel (invariant F12).
- **Providers never invoke each other** (F17); they interact only through neutral
  contracts (F16).
- **Kernel never imports the framework**; the framework never imports a consumer,
  product, or vendor SDK.

These are enforced by `platform_freeze` (F16–F20), `governance_providers/tests/
test_dependency_boundaries.py`, and the conformance AST import check.

---

## 5. File-level classification

Full table in `ARTIFACT_CLASSIFICATION.md`. Summary of the 29 non-test framework
modules: 1 `FRAMEWORK_PUBLIC_API`, 6 `FRAMEWORK_CORE`, 1 `FRAMEWORK_REGISTRY`, 5
`FRAMEWORK_CORE` (conformance kit), 4 `FRAMEWORK_PORT` (kernel-bound adapters), 4
`REFERENCE_IMPLEMENTATION`, 8 `COMPATIBILITY_LAYER`. **No** application, domain,
control-plane, orchestration, platform-service, deprecated, or unclear artifact
exists in the package. Every `DUPLICATE_IMPLEMENTATION` finding lives in the
concrete providers, not the framework.

---

## 6. Framework versus implementation separation

The four candidate models were evaluated:

- **Model A (one framework package + separate provider packages): MATCHES REALITY.**
  Framework = `governance_providers`; providers = `tap_provider`,
  `actiongate_provider`, baselines — already separate with their own wheels.
- **Model B (SDK + runtime + providers):** not needed now. The pure core vs
  kernel-bound `adapters/` split is real but internal; splitting into two
  *distributions* is a deferred refinement, not required for the first migration.
- **Model C (no framework; mostly aggregation):** **false** — the package is
  substantive, single-sourced mechanism.
- **Model D (framework + optional registry platform service):** the registry here
  is an in-memory library object, not an operational service; no separate
  provider-registry service exists or is needed. If one is ever built it must stay
  optional and authority-free.

Chosen target: **Model A**, migrating the framework as one canonical package while
keeping the providers as the separate packages they already are.

---

## 7. Duplication findings

Full matrix in `DUPLICATION_MATRIX.md`. Headlines:
- **Contract duplication already resolved** (extracted to contracts leaf; shims remain).
- **Live duplication is provider-side and capability-owned:** TAP and ActionGate
  each ship their own invocation record/log (supersets of the framework's) and a
  `CheckResult`/conformance-report shape (twins). These are adapter
  specializations / small test-harness twins, **safe to leave**, and consolidation
  is deferred, additive (MINOR), and independent of the migration.
- **No duplication of request/result/error envelopes** — the contracts are
  single-sourced and reused by both providers.

---

## 8. Contract ownership

Full matrix in `CONTRACT_OWNERSHIP_MATRIX.md`. Every public model is already in
its correct semantic layer: neutral contracts in Governance Contracts; registry /
resolution / configuration / observability / versioning + kernel adapters in the
framework; vendor vocabulary in the providers; ports in the kernel. **No neutral
contract is trapped in the framework, and no framework mechanism is misfiled into
Governance Contracts.** Documented (do-not-act) contract gaps: a possible neutral
observability-record base, a shared conformance-report base, and GC ownership of
`CONTRACT_VERSION` — all additive future work.

---

## 9. Dependency direction

`applications/ai_hiring/domains → concrete providers → governance_providers →
{ugence_governance_contracts (pure leaf), decision_governance.api (kernel facade) →
ugence_decision_authority}`. Zero upward imports (test-enforced); acyclic (F20).
The framework's only external edges are the neutral contracts leaf and the kernel
public facade — the latter confined to `adapters/`. No framework path grants,
combines, widens, or overrides any bounded authority. See `IMPORT_GRAPH.md`.

---

## 10. Public API

One frozen surface: `governance_providers.api`, 47 symbols, snapshot hash
`98dd0264…`. 32 are re-exports of the neutral contracts leaf; 15 are
framework-owned mechanism. 66 external files consume the framework, all on the
`governance_providers` name; `ai_hiring` additionally deep-imports `.contracts`
and `.reference`. Object identity across the contracts-shim boundary is asserted
by the legacy-compat suite. See `PUBLIC_API_AND_CONSUMER_MAP.md`.

---

## 11. Packaging

Already an independent PRIVATE wheel `dgm-provider-framework` (symlink to one
canonical source tree; deps `decision-governance==1.0.0`,
`ugence-governance-contracts>=0.1.0`; tests excluded; no app/capability/business
code). Concrete providers are already separate wheels depending on it. See
`PACKAGING_AND_COMPATIBILITY_MAP.md`. Recommended future canonical distribution:
`ugence-governance-provider-framework` at
`packages/governance-provider-framework/src/ugence_governance_provider_framework/`
(a framework leaf, not under `packages/capabilities/`).

---

## 12. Freeze implications

`governance_providers` **is** a frozen core tree (unlike StoryGraph), so a physical
move owes a reviewed re-baseline of exactly two manifest fields
(`core_tree_hashes[governance_providers]`, `manifest_digest`) — the same PATCH /
structural operation the Governance Contracts and Decision Authority migrations
performed, with the API snapshot kept byte-identical. `ugence-governance-contracts`
is not yet a frozen component (a gap to address, with review, in the migration
phase). See `FREEZE_AND_API_IMPACT_ASSESSMENT.md`.

---

## 13. Consumer impact

Projected **zero** consumer code changes if the migration keeps the
`governance_providers` namespace as an identity-preserving shim (including the
deep paths `.contracts`, `.reference`, `.version`, `.conformance`). This mirrors
the Governance Contracts migration, which left ~70 consumers untouched.

---

## 14. Recommended target architecture

Model A: one canonical framework package `ugence_governance_provider_framework`
(distribution `ugence-governance-provider-framework`) under
`packages/governance-provider-framework/`, retaining registry, resolution,
configuration, observability, fingerprint, version, conformance, reference, and
adapters; with `adapters/` internally isolated so a *later* optional
`sdk`/`runtime` split needs no second migration. Providers remain the separate
packages they already are. Legacy `governance_providers` becomes an
identity-preserving shim.

---

## 15. Migration sequence

Defined (do-not-execute) in `MIGRATION_READINESS_RECOMMENDATION.md` §"Later
migration sequence": freeze/baseline capture → history-preserving `git mv` to the
canonical tree → identity-preserving compat namespace → (providers already
separated) → independent packaging + clean-venv verify → keep consumers on the
compat path → recompute 2 freeze fields, confirm API snapshot byte-identical
(PATCH) → docs + migration report → single PR.

---

## 16. Risks

- **Frozen-tree re-baseline** must be reviewed; a hidden semantic change would flip
  the API snapshot hash (stop condition).
- **Identity preservation** requires re-export shims, **not** a symlink (a symlink
  creates a second, non-identical class set and breaks compat identity assertions).
- **Adapters bleed**: keep `adapters/` isolated; do not entangle the pure core with
  the kernel dependency during the move.
- **Scope creep**: the observability/conformance consolidation and the SDK/runtime
  split are separate, additive future work — bundling them into the migration would
  change more than one variable at once.
- **Contracts leaf not yet frozen**: folding it into the manifest is a separate
  reviewed decision, not a silent side effect of this migration.

---

## 17. Stop conditions

Halt and reassess if: the `governance_providers.api` snapshot hash would change;
`platform_freeze.verify` fails after re-baseline; any consumer needs a code edit to
keep importing; a new upward import appears; or the adapters can no longer be
isolated from the pure core.

---

## 18. Exact next implementation phase

**Phase: "Governance Provider Framework canonical-package migration" (restructuring
roadmap step 6).** Migrate `governance_providers` → canonical
`ugence_governance_provider_framework` package following the proven three-migration
pattern, with a reviewed two-field freeze re-baseline and a byte-identical API
snapshot. Begin only on receipt of the implementation prompt. Do **not** consolidate
duplication, split SDK/runtime, or modify Governance Contracts in that phase.

---

## Final determination

**READY — migrate one canonical Governance Provider Framework package**
