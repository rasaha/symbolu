# Public API & Consumer Map — Governance Provider Framework

Audit-only. Branch `claude/governance-provider-framework-audit-jzdvbe` @ `1a191629`.

## 1. Public API surface

The single, frozen public surface is **`governance_providers.api`** — snapshot
`platform/api-snapshots/governance_providers.api.json`, hash
`98dd02649e5fbb37879ef05e1b06afce1abd0cc10b5692b81974437d59f7a59b` (a frozen
platform component). Three secondary public surfaces exist by convention:
`governance_providers.conformance` (provider-author kit),
`governance_providers.reference` (deterministic reference providers), and
`governance_providers.version` (compat predicates).

### 1.1 `governance_providers.api` — 47 exported symbols

Grouped by origin (post-Governance-Contracts-migration):

**Re-exported from `ugence_governance_contracts` (shims, identity preserved):**
`ProviderKind`, `ProviderDescriptor`, `ProviderCapabilities`,
`ProviderCompatibility`, `ProviderHealth`, `ProviderLifecycleState`, `Provider`,
`BaseProvider`, `AssertionGovernanceProvider`, `AssertionGovernanceRequest`,
`AssertionGovernanceResult`, `AssertionCoverage`, `ActionGovernanceProvider`,
`ActionGovernanceRequest`, `ActionGovernanceResult`, `ActionGovernanceOutcome`,
`ExternalExecutionProvider`, `ExecutionDispatchRequest`,
`ExecutionDispatchResult`, `ExecutionObservation`, `ExecutionBusinessOutcome`,
`ProviderError`, `ProviderRegistrationError`, `ProviderResolutionError`,
`ProviderCompatibilityError`, `ProviderConfigurationError`,
`ProviderUnavailableError`, `ProviderTimeoutError`, `ProviderProtocolError`,
`ProviderResultValidationError`, `FailureClass`, `CONTRACT_VERSION` (partly).

**Owned by the framework (real logic, would move with the framework):**
`ProviderRegistry`, `resolve`, `ResolutionRequest`, `ResolutionRecord`,
`SelectionRule`, `ProvidersConfiguration`, `ProviderEntry`,
`ActionGovernanceControlPlaneAdapter`, `ExternalExecutionAdapter`,
`AssertionAssessmentIntegration`, `AssertionAssessment`,
`AssertionLinkedRecordAdapter`, `ProviderInvocationLog`,
`ProviderInvocationRecord`, `record_invocation`, `__version__`,
`CONTRACT_VERSION`.

Constructor/signature note: all framework-owned public models are frozen
dataclasses (deterministic fields); `resolve()` and `ProviderRegistry` methods
carry stable keyword signatures captured in the snapshot. A migration that keeps
the export list and dataclass fields byte-identical produces an **unchanged** API
snapshot (the pattern the three prior migrations achieved).

## 2. External consumers (66 files) — file:line evidence

### ai_hiring/ (application layer — heaviest consumer, 26 sites)
- `ai_hiring/recommendations/tap_integration.py:23` `from governance_providers.api import (…)`
- `ai_hiring/actions/actiongate_integration.py:17` `from governance_providers.api import (…)`
- `ai_hiring/actions/execution_port.py:17` `from governance_providers.api import (…)`
- `ai_hiring/services/hiring_action_execution_service.py:17` `… import ExecutionBusinessOutcome, ExecutionDispatchRequest`
- `ai_hiring/services/hiring_reconciliation_service.py:15` `… import ExecutionBusinessOutcome`
- `ai_hiring/validation/lifecycle.py:16-19` `.api` + `.contracts` + `.reference.action` + `.reference.assertion`
- `ai_hiring/validation/pilot.py:13` `.contracts import AssertionCoverage`
- `ai_hiring/product/demo.py:21` `.contracts import AssertionCoverage`
- `ai_hiring/tests/h2_helpers.py:9-11`, `h3_helpers.py:17`, `h4_helpers.py:7`, and `tests/test_h2_*`, `test_h3_*`, `test_h4_*`, `test_h5_*` (`.api`, `.contracts`, `.contracts.action`, `.reference.*`)

### Concrete + baseline providers (framework's primary clients)
- `tap_provider/{provider.py:23, conformance/__init__.py:15, health/__init__.py:12, errors/__init__.py:19, mapping/request.py:20, mapping/result.py:25, configuration/__init__.py:12}` + tests
- `actiongate_provider/{provider.py:14, conformance/__init__.py:12, health/__init__.py:6, errors/__init__.py:10, mapping/request.py:15, mapping/result.py:21, configuration/__init__.py:7}` + tests
- `baseline_assertion_provider/{provider.py:17, conformance/__init__.py:6, configuration.py:7}` + tests
- `baseline_action_provider/{provider.py:18, conformance/__init__.py:6, configuration.py:7}` + tests

### Validation pilots / benchmark
- `enterprise_validation_pilot/{composition/root.py:28, composition/config.py:9, composition/manifest.py:61, runners/workflow.py:19, evaluators/failure_injection.py:12,133, tests/*}`
- `provider_heterogeneity_validation/{runners/workflow.py:19, selection/resolve.py:19 (uses governance_providers.version)}`
- `comparative_governance_benchmark/strategies/{_tap_support.py:8, assertion_only.py:13, action_only.py:15, _actiongate_support.py:12}`

### Platform / console / packaging / docs
- `platform_freeze/invariants.py:27,40,50` and `platform_freeze/tests/test_freeze.py:83`
- `ugence_console_api/capabilities/{action_control.py:26, truth_evidence.py:18}` (lazy, inside try/except)
- `packaging/verify_tap_provider_distribution.py:50,65,68`; `packaging/verify_provider_heterogeneity_distribution.py:56,64`
- `packages/governance-contracts/tests/compatibility/test_legacy_compat.py:16-24` (deep-import compat matrix)
- `docs/platform-v1/PROVIDER_DEVELOPMENT_GUIDE.md:32` (documentation example)

## 3. Consumer reliance characteristics (migration impact)

| Reliance | Present? | Consequence for migration |
|---|---|---|
| On module NAME `governance_providers` | Yes — all 66 files | Legacy namespace must survive as an identity-preserving shim |
| On deep submodule paths (`.contracts`, `.reference`, `.version`, `.conformance`) | Yes — ai_hiring, heterogeneity, compat suite | Those exact submodule paths must resolve post-migration |
| On object identity (`is` / isinstance across the boundary) | Yes — legacy-compat suite asserts same objects | Requires re-export shims, **not** a second namespace/symlink that would create distinct classes |
| On serialization by module path (pickle) | Not observed | Frozen dataclasses compare by value; no pickle-by-path dependency found |
| On the frozen API snapshot | Yes — `platform_freeze` | Keep export list + dataclass fields byte-identical → PATCH |

## 4. Console / application coupling note

`ugence_console_api` reaches the framework **only** through lazy, guarded imports
inside capability methods (try/except blocks), and reaches concrete providers'
`build_*_provider` factories the same way. No console or application code lives
inside the framework, and the framework never imports console/application code —
consistent with the AI Control Plane / Console being **optional and bypassable**.
