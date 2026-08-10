# Artifact Classification — Governance Provider Framework

Audit-only. No file was moved, renamed, or modified. Branch
`claude/governance-provider-framework-audit-jzdvbe` @ `1a191629`.

Every source module under `governance_providers/` appears below, plus the
concrete provider packages, the kernel-facade shim, packaging, and freeze/API
evidence that bound the framework.

## Classification legend used

`FRAMEWORK_CORE`, `FRAMEWORK_PUBLIC_API`, `FRAMEWORK_PORT`, `FRAMEWORK_REGISTRY`,
`FRAMEWORK_LIFECYCLE`, `SHARED_GOVERNANCE_CONTRACT`, `CAPABILITY_OWNED_CONTRACT`,
`CAPABILITY_SPECIFIC_PROVIDER`, `CONCRETE_PROVIDER_IMPLEMENTATION`,
`REFERENCE_IMPLEMENTATION`, `APPLICATION_LAYER`, `DOMAIN_EXTENSION`,
`PLATFORM_SERVICE`, `CONTROL_PLANE_COMPONENT`, `ORCHESTRATION_COMPONENT`,
`COMPATIBILITY_LAYER`, `PACKAGING_ONLY`, `TEST_OR_FIXTURE`,
`FREEZE_OR_API_EVIDENCE`, `DOCUMENTATION`, `DUPLICATE_IMPLEMENTATION`,
`DEPRECATED_CANDIDATE`, `OUT_OF_SCOPE`, `UNCLEAR`.

`Public?` = reachable from the frozen public surface (`governance_providers.api`,
or the secondary public surfaces `.conformance` / `.reference` / `.version`).

## 1. `governance_providers/` — every source module

| Artifact | Current path | Classification | Public? | Authority owned | Dependencies | Consumers | Duplicate of | Recommended disposition | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| package root | `governance_providers/__init__.py` | FRAMEWORK_CORE | via `__version__` | none | stdlib; bootstraps `ugence_governance_contracts` on `sys.path` | importers of the package | — | Migrate as canonical package root; keep source-checkout bootstrap | 44 LOC; `_ensure_governance_contracts_importable()` |
| version & compat | `governance_providers/version.py` | FRAMEWORK_CORE | yes (`__version__`, `CONTRACT_VERSION`) | none | stdlib | api, registry, conformance, `provider_heterogeneity_validation` | — | Migrate into framework core | `TARGET_KERNEL_MAJOR=1`, `CONTRACT_VERSION="1.0.0"` |
| registry | `governance_providers/registry/__init__.py` | FRAMEWORK_REGISTRY | yes (`ProviderRegistry`) | none (registration/validation only) | rel: contracts, errors, metadata, version | api, resolution, providers, pilots | — | Migrate into framework core | explicit registration; validates kind/version/default uniqueness |
| resolution | `governance_providers/resolution.py` | FRAMEWORK_CORE | yes (`resolve`, `ResolutionRequest/Record`, `SelectionRule`) | none (deterministic selection only) | rel: contracts, errors, metadata, registry | api, pilots, benchmark | — | Migrate into framework core | fixed precedence; never guesses (F18/F19) |
| configuration | `governance_providers/configuration.py` | FRAMEWORK_CORE | yes (`ProvidersConfiguration`, `ProviderEntry`) | none (declarative config; secret *refs* only) | rel: errors, metadata | api, pilot composition | — | Migrate into framework core | rejects unknown/contradictory config; no secret store |
| observability | `governance_providers/observability.py` | FRAMEWORK_CORE | yes (`ProviderInvocationLog/Record`, `record_invocation`) | none | rel: errors | api | superset consumed by TAP/ActionGate own records (see §3) | Migrate into framework core; consider adopting in providers | frozen-layer records; no vendor payload/secret |
| fingerprint | `governance_providers/fingerprint.py` | FRAMEWORK_CORE | internal util (not in `.api`) | none | stdlib (hashlib/json) | reference providers | — | Migrate into framework core | deterministic SHA-256 over canonical JSON |
| public API | `governance_providers/api/__init__.py` | FRAMEWORK_PUBLIC_API | yes (47 symbols) | none (aggregator) | rel: version, metadata, lifecycle, contracts, registry, resolution, configuration, adapters, observability, errors | ai_hiring, providers, pilots, benchmark, console, freeze | — | Migrate; keep byte-identical export list | snapshot hash `98dd0264…` |
| errors shim | `governance_providers/errors.py` | COMPATIBILITY_LAYER | yes (re-export) | none | `ugence_governance_contracts.errors` | api, legacy-compat suite | canonical in `ugence_governance_contracts` | Keep as identity-preserving shim; removal target 0.2.0 | logic-free re-export |
| lifecycle shim | `governance_providers/lifecycle.py` | COMPATIBILITY_LAYER | yes (re-export) | none | `ugence_governance_contracts.lifecycle` | api, legacy-compat suite | canonical in `ugence_governance_contracts` | Keep as identity-preserving shim; removal target 0.2.0 | logic-free re-export |
| metadata shim | `governance_providers/metadata.py` | COMPATIBILITY_LAYER | yes (re-export) | none | `ugence_governance_contracts.metadata` | api, registry, reference, legacy-compat | canonical in `ugence_governance_contracts` | Keep as identity-preserving shim; removal target 0.2.0 | logic-free re-export |
| contracts pkg shim | `governance_providers/contracts/__init__.py` | COMPATIBILITY_LAYER | yes (re-export) | none | `ugence_governance_contracts.contracts` | api, ai_hiring (deep import), reference | canonical in `ugence_governance_contracts` | Keep as identity-preserving shim; removal target 0.2.0 | logic-free re-export |
| contracts.base shim | `governance_providers/contracts/base.py` | COMPATIBILITY_LAYER | yes | none | `ugence_governance_contracts.contracts.base` | conformance, reference | canonical in contracts leaf | Keep shim | 2 LOC |
| contracts.assertion shim | `governance_providers/contracts/assertion.py` | COMPATIBILITY_LAYER | yes | none | contracts leaf | conformance, ai_hiring | canonical in contracts leaf | Keep shim | 5 LOC |
| contracts.action shim | `governance_providers/contracts/action.py` | COMPATIBILITY_LAYER | yes | none | contracts leaf | conformance, adapters, ai_hiring | canonical in contracts leaf | Keep shim | 5 LOC |
| contracts.execution shim | `governance_providers/contracts/execution.py` | COMPATIBILITY_LAYER | yes | none | contracts leaf | conformance, adapters | canonical in contracts leaf | Keep shim | 5 LOC |
| adapters pkg | `governance_providers/adapters/__init__.py` | FRAMEWORK_PORT | yes | none (translation only) | rel: the 3 adapters | api | — | Migrate; candidate future isolation as a `runtime`/`adapters` sub-package | aggregator |
| action→control-plane | `governance_providers/adapters/action_to_control_plane.py` | FRAMEWORK_PORT | yes (`ActionGovernanceControlPlaneAdapter`) | none — normalizes to fail-safe INDETERMINATE | **`decision_governance.api.common` + `.contracts`**; rel contracts/errors | api, ActionGate e2e | — | Migrate; this is the framework↔kernel bleed (see FREEZE doc) | vendor error never leaks to kernel |
| execution→external | `governance_providers/adapters/execution_to_external_system.py` | FRAMEWORK_PORT | yes (`ExternalExecutionAdapter`) | none — transport/business split preserved | **`decision_governance.api.common/.contracts/.ports`**; rel | api, pilots | — | Migrate; kernel-bound adapter | dispatch failure→transport failure |
| assertion integration | `governance_providers/adapters/assertion_integration.py` | FRAMEWORK_PORT | yes (`AssertionAssessmentIntegration`, `AssertionAssessment`, `AssertionLinkedRecordAdapter`) | none — assessment inputs; optional LinkedRecordPort projection | **`decision_governance.api.ports`**; rel | api, ai_hiring | — | Migrate; kernel-bound adapter | explicitly "not forced through an unrelated kernel port" |
| conformance pkg | `governance_providers/conformance/__init__.py` | FRAMEWORK_CORE (conformance kit, public) | yes (`.conformance`) | none | rel: common/assertion/action/execution | providers, baselines, pilots, packaging verifiers | framework `CheckResult` is re-implemented by TAP/ActionGate (see §3) | Migrate; keep as shipped public kit | "same kits certify TAP and ActionGate without modification" |
| conformance common | `governance_providers/conformance/common.py` | FRAMEWORK_CORE (conformance kit) | yes | none | rel: contracts.base, errors, metadata, version; stdlib ast/inspect | conformance kinds | `CheckResult` dataclass duplicated in provider conformance modules | Migrate | AST check `_no_kernel_internal_imports` |
| conformance assertion | `governance_providers/conformance/assertion.py` | FRAMEWORK_CORE (conformance kit) | yes | none | rel: contracts, metadata, common, reference | TAP tests | — | Migrate | assertion kind kit |
| conformance action | `governance_providers/conformance/action.py` | FRAMEWORK_CORE (conformance kit) | yes | none | rel | ActionGate tests | — | Migrate | action kind kit |
| conformance execution | `governance_providers/conformance/execution.py` | FRAMEWORK_CORE (conformance kit) | yes | none | rel | pilots | — | Migrate | execution kind kit |
| reference pkg | `governance_providers/reference/__init__.py` | REFERENCE_IMPLEMENTATION | yes (`.reference`) | none | rel: the 3 reference providers | ai_hiring, conformance | — | Migrate; keep in package (framework-validation only) | "NOT TAP/ActionGate" |
| reference assertion | `governance_providers/reference/assertion.py` | REFERENCE_IMPLEMENTATION | yes (`DeterministicAssertionProvider`) | none | rel: contracts, errors, fingerprint, metadata | ai_hiring, conformance | — | Migrate | deterministic; framework validation |
| reference action | `governance_providers/reference/action.py` | REFERENCE_IMPLEMENTATION | yes (`DeterministicActionGovernanceProvider`) | none | rel | ai_hiring, conformance | — | Migrate | deterministic |
| reference execution | `governance_providers/reference/execution.py` | REFERENCE_IMPLEMENTATION | yes (`DeterministicExecutionProvider`) | none | rel | conformance | — | Migrate | deterministic |
| tests (9 files) | `governance_providers/tests/*.py` | TEST_OR_FIXTURE | no | none | rel + `decision_governance.api` (test-only) | — | — | Co-locate with canonical package | 42 tests; incl. `test_dependency_boundaries.py`, `test_packaging.py` |

## 2. Bounding artifacts (packaging, freeze, docs, kernel facade)

| Artifact | Current path | Classification | Public? | Notes |
|---|---|---|---|---|
| framework wheel | `packaging/dgm-provider-framework/pyproject.toml` | PACKAGING_ONLY | — | dist `dgm-provider-framework`; symlink to canonical source; deps `decision-governance==1.0.0`, `ugence-governance-contracts>=0.1.0` |
| framework wheel README/LICENSE | `packaging/dgm-provider-framework/{README.md,LICENSE}` | PACKAGING_ONLY | — | one-line descriptor |
| API snapshot | `platform/api-snapshots/governance_providers.api.json` | FREEZE_OR_API_EVIDENCE | — | 47 symbols; hash `98dd0264…` |
| freeze manifest entries | `platform/PLATFORM_FREEZE_V1.json` | FREEZE_OR_API_EVIDENCE | — | `governance_providers` is a frozen core tree (`ab12c026…`); component `dgm-provider-framework:0.1.0` |
| freeze tooling | `platform_freeze/**` | FREEZE_OR_API_EVIDENCE / PLATFORM_SERVICE (tooling) | — | out-of-band release tooling; imports `governance_providers.api` in `invariants.py` |
| framework spec | `docs/DGM_PROVIDER_FRAMEWORK.md` | DOCUMENTATION | — | canonical design doc (Phase 5F) |
| kernel facade | `decision_governance/__init__.py` | COMPATIBILITY_LAYER (out of scope to modify) | — | identity-preserving alias over `ugence_decision_authority`; removal target 2.0.0 |

## 3. Concrete providers and reference/alternative providers (framework consumers, separate packages)

| Artifact | Current path | Classification | Public? | Authority owned | Duplicate of | Recommended disposition |
|---|---|---|---|---|---|---|
| TAP provider | `tap_provider/**` (22 files, 1857 LOC) | CONCRETE_PROVIDER_IMPLEMENTATION / CAPABILITY_SPECIFIC_PROVIDER (assertion) | `tap_provider.api` | assertion admissibility (its own bounded capability) | — | Keep a separate package; already own wheel `dgm-tap-provider` |
| TAP observability | `tap_provider/observability/__init__.py` | DUPLICATE_IMPLEMENTATION (capability-owned superset) | via api | none | framework `ProviderInvocationRecord/Log` | Keep separate OR adopt framework record + extension fields; do NOT consolidate in this phase |
| TAP conformance types | `tap_provider/conformance/__init__.py` (`CheckResult`, `TapConformanceReport`) | DUPLICATE_IMPLEMENTATION | via api | none | framework `conformance.common.CheckResult` + ActionGate twin | Consider a shared conformance-report base in a later phase |
| ActionGate provider | `actiongate_provider/**` (22 files, 1356 LOC) | CONCRETE_PROVIDER_IMPLEMENTATION / CAPABILITY_SPECIFIC_PROVIDER (action) | `actiongate_provider.api` | exact-action authorization (its own bounded capability) | — | Keep separate; own wheel `dgm-actiongate-provider` |
| ActionGate observability | `actiongate_provider/observability.py` | DUPLICATE_IMPLEMENTATION (capability-owned superset) | via api | none | framework `ProviderInvocationRecord/Log` + TAP twin | Keep separate; do NOT consolidate in this phase |
| ActionGate conformance types | `actiongate_provider/conformance/__init__.py` (`CheckResult`, `ActionGateConformanceReport`) | DUPLICATE_IMPLEMENTATION | via api | none | framework kit + TAP twin | Later shared base |
| baseline assertion provider | `baseline_assertion_provider/**` | CONCRETE_PROVIDER_IMPLEMENTATION (alternative/heterogeneity) | api | none | — | Keep separate; own wheel |
| baseline action provider | `baseline_action_provider/**` | CONCRETE_PROVIDER_IMPLEMENTATION (alternative/heterogeneity) | api | none | — | Keep separate; own wheel |

## Classification summary (framework package `governance_providers/`)

| Classification | Non-test modules | Notes |
|---|---|---|
| FRAMEWORK_PUBLIC_API | 1 | `api/__init__.py` |
| FRAMEWORK_CORE | 6 | `__init__`, `version`, `resolution`, `configuration`, `observability`, `fingerprint` |
| FRAMEWORK_REGISTRY | 1 | `registry/__init__.py` |
| FRAMEWORK_CORE (conformance kit) | 5 | `conformance/*` |
| FRAMEWORK_PORT | 4 | `adapters/*` (kernel-bound) |
| REFERENCE_IMPLEMENTATION | 4 | `reference/*` |
| COMPATIBILITY_LAYER | 8 | `errors`, `lifecycle`, `metadata`, `contracts/*` (5) |
| **Total non-test** | **29** | + 9 TEST_OR_FIXTURE |

**No artifact under `governance_providers/` is** `APPLICATION_LAYER`,
`DOMAIN_EXTENSION`, `CONTROL_PLANE_COMPONENT`, `ORCHESTRATION_COMPONENT`,
`PLATFORM_SERVICE`, `DEPRECATED_CANDIDATE`, or `UNCLEAR`. No business/authority
logic and no capability implementation lives in the framework. The only
`DUPLICATE_IMPLEMENTATION` findings live in the **concrete providers**, not in
the framework, and are capability-owned adapter specializations (see
`DUPLICATION_MATRIX.md`).
