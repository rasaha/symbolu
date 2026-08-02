# Adapter-Boundary Classification — Governance Provider Framework

The principal migration-boundary issue (§7): every framework module that imports
`decision_governance.api`. Classified **before** moving source. Verified directly:
`grep` shows the three `adapters/*` modules are the **only** framework modules that
import `decision_governance.api`, and they contain **no** capability-specific
(`tap`/`actiongate`) coupling.

## Classification legend

`GENERIC_FRAMEWORK_ADAPTER` · `DECISION_AUTHORITY_SPECIFIC_ADAPTER` ·
`OPTIONAL_INTEGRATION_MODULE` · `COMPATIBILITY_MODULE` · `REFERENCE_ADAPTER` ·
`OUT_OF_SCOPE` · `UNCLEAR`

## Adapters that import `decision_governance.api`

| Adapter | Current path | Dependency | Consumers | Authority affected | Target disposition | Evidence |
|---|---|---|---|---|---|---|
| `ActionGovernanceControlPlaneAdapter` | `governance_providers/adapters/action_to_control_plane.py` | `decision_governance.api.common`, `.contracts` | `governance_providers.api`, ActionGate e2e | **none** — normalizes any provider failure to fail-safe `INDETERMINATE`; vendor error never leaks to kernel | **GENERIC_FRAMEWORK_ADAPTER** → move to `…/adapters/`; kept in the canonical package, but `decision-governance` is an **optional** extra so it is not a mandatory core dependency | translates *any* action provider onto the kernel control-plane port; no `tap`/`actiongate` symbols |
| `ExternalExecutionAdapter` | `governance_providers/adapters/execution_to_external_system.py` | `decision_governance.api.common`, `.contracts`, `.ports` | `governance_providers.api`, pilots | **none** — transport/business split preserved; dispatch failure → transport failure | **GENERIC_FRAMEWORK_ADAPTER** → `…/adapters/` (optional extra) | translates *any* execution provider onto the kernel external-system port |
| `AssertionAssessmentIntegration`, `AssertionAssessment`, `AssertionLinkedRecordAdapter` | `governance_providers/adapters/assertion_integration.py` | `decision_governance.api.ports` | `governance_providers.api`, `ai_hiring` | **none** — assessment inputs + optional `LinkedRecordPort` projection | **GENERIC_FRAMEWORK_ADAPTER** → `…/adapters/` (optional extra) | provider-neutral assessment integration; explicitly *not* forced through an unrelated kernel port |

No adapter is `DECISION_AUTHORITY_SPECIFIC_ADAPTER`, `OUT_OF_SCOPE`, or `UNCLEAR`.
They are framework **ports** that translate any provider of a *kind* onto a kernel
port without knowing the concrete vendor — the designed framework↔kernel seam.

## Resolution of the boundary (preferred outcome #1 + optional-dependency packaging)

Per §7 preferred outcomes, outcome **#1** applies ("keep capability-neutral adapter
interfaces in the framework") — the adapters are capability-neutral. To satisfy
GPF3/GPF9/§16 ("the core must not acquire a mandatory dependency on Decision
Authority"), the migration:

1. Keeps the three adapters physically **isolated** in `…/adapters/` (already a
   sub-package), so a later optional `sdk`/`runtime` split needs no second migration.
2. Declares `decision-governance` as an **optional** distribution dependency
   (extra `adapters`), **not** a core runtime dependency. The only hard runtime
   dependency of the canonical core is `ugence-governance-contracts`.
3. Leaves the top-level `__init__` importing only `.version` (as today), so
   `import ugence_governance_provider_framework` and the pure-core submodules
   (`registry`, `resolution`, `configuration`, `observability`, `fingerprint`,
   `version`, `conformance`, `reference`, and the contract shims) import **without**
   Decision Authority present.
4. Preserves the existing "adapters bleed": `…/api` and `…/adapters` still import
   the kernel facade, so importing `.api` still requires the `adapters` extra —
   **unchanged behaviour** vs the pre-migration `governance_providers.api`. No
   authority moves; the API snapshot stays byte-identical.

**No adapter behaviour is changed during classification or relocation.** The core
is importable without importing Decision Authority (proved in the distribution
verifier, isolated-env test 3).
