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
3. Leaves the top-level `__init__` importing only `.version`, so
   `import ugence_governance_provider_framework` and the pure-core submodules
   (`registry`, `resolution`, `configuration`, `observability`, `fingerprint`,
   `version`, `conformance`, `reference`, and the contract shims) import **without**
   Decision Authority present.
4. **Optional-dependency boundary correction (PR-validation phase).** The three
   adapters now load Decision Authority **lazily** — module-level kernel imports
   (and the frozen `_OUTCOME_MAP`) moved into a cached `_kernel()` loader, and the
   `__init__` id/clock defaults became lazy wrappers. A centralized
   `adapters/_kernel.py::require_decision_authority()` raises a precise error
   naming `ugence-governance-provider-framework[adapters]` (and only for the
   specific absence of Decision Authority; unrelated import errors propagate).
   Consequently `…/adapters` **and** the `…/api` aggregator now import without
   Decision Authority; only *invoking* an adapter requires the extra. This is
   stricter than the pre-migration `governance_providers.api` (which pulled the
   kernel at import) and is an import-boundary change only.

**No adapter behaviour changes when the `adapters` extra is installed** — public
class names, method signatures, fields, enums, errors, and outcomes are unchanged,
the frozen `governance_providers.api` snapshot stays byte-identical (`98dd0264…`),
and the behavioural fingerprint is unchanged (`a8e3e7e9…`). The core AND the public
API are importable without Decision Authority (proved in the distribution verifier
and `tests/boundaries/test_optional_adapter_dependency.py`).
