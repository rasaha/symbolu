# File Map — Governance Provider Framework relocation

Source of truth: `git ls-files` at `ed7387f4`. Every framework file and its
canonical destination. Strategy: **history-preserving `git mv`** (source → canonical
`src/` tree); tests move into the canonical package's `tests/`; the legacy
`governance_providers/` becomes a single logic-free shim module.

Canonical path: `packages/governance-provider-framework/`
Canonical namespace: `ugence_governance_provider_framework`
Canonical distribution: `ugence-governance-provider-framework`
Legacy namespace (compat shim): `governance_providers`
Legacy distribution (compat shell): `dgm-provider-framework`

## Non-test source (29 modules) → `src/ugence_governance_provider_framework/`

| Current path | Canonical path | Classification |
|---|---|---|
| `governance_providers/__init__.py` | `…/__init__.py` | FRAMEWORK_CORE (package root) |
| `governance_providers/version.py` | `…/version.py` | FRAMEWORK_CORE |
| `governance_providers/registry/__init__.py` | `…/registry/__init__.py` | FRAMEWORK_REGISTRY |
| `governance_providers/resolution.py` | `…/resolution.py` | FRAMEWORK_CORE |
| `governance_providers/configuration.py` | `…/configuration.py` | FRAMEWORK_CORE |
| `governance_providers/observability.py` | `…/observability.py` | FRAMEWORK_CORE |
| `governance_providers/fingerprint.py` | `…/fingerprint.py` | FRAMEWORK_CORE |
| `governance_providers/api/__init__.py` | `…/api/__init__.py` | FRAMEWORK_PUBLIC_API |
| `governance_providers/adapters/__init__.py` | `…/adapters/__init__.py` | FRAMEWORK_PORT |
| `governance_providers/adapters/action_to_control_plane.py` | `…/adapters/action_to_control_plane.py` | FRAMEWORK_PORT (kernel-bound) |
| `governance_providers/adapters/execution_to_external_system.py` | `…/adapters/execution_to_external_system.py` | FRAMEWORK_PORT (kernel-bound) |
| `governance_providers/adapters/assertion_integration.py` | `…/adapters/assertion_integration.py` | FRAMEWORK_PORT (kernel-bound) |
| `governance_providers/conformance/__init__.py` | `…/conformance/__init__.py` | FRAMEWORK_CORE (conformance kit) |
| `governance_providers/conformance/common.py` | `…/conformance/common.py` | FRAMEWORK_CORE (conformance kit) |
| `governance_providers/conformance/assertion.py` | `…/conformance/assertion.py` | FRAMEWORK_CORE (conformance kit) |
| `governance_providers/conformance/action.py` | `…/conformance/action.py` | FRAMEWORK_CORE (conformance kit) |
| `governance_providers/conformance/execution.py` | `…/conformance/execution.py` | FRAMEWORK_CORE (conformance kit) |
| `governance_providers/reference/__init__.py` | `…/reference/__init__.py` | REFERENCE_IMPLEMENTATION |
| `governance_providers/reference/assertion.py` | `…/reference/assertion.py` | REFERENCE_IMPLEMENTATION |
| `governance_providers/reference/action.py` | `…/reference/action.py` | REFERENCE_IMPLEMENTATION |
| `governance_providers/reference/execution.py` | `…/reference/execution.py` | REFERENCE_IMPLEMENTATION |
| `governance_providers/errors.py` | `…/errors.py` | COMPATIBILITY_LAYER (→ `ugence_governance_contracts.errors`) |
| `governance_providers/lifecycle.py` | `…/lifecycle.py` | COMPATIBILITY_LAYER (→ contracts leaf) |
| `governance_providers/metadata.py` | `…/metadata.py` | COMPATIBILITY_LAYER (→ contracts leaf) |
| `governance_providers/contracts/__init__.py` | `…/contracts/__init__.py` | COMPATIBILITY_LAYER (→ contracts leaf) |
| `governance_providers/contracts/base.py` | `…/contracts/base.py` | COMPATIBILITY_LAYER |
| `governance_providers/contracts/assertion.py` | `…/contracts/assertion.py` | COMPATIBILITY_LAYER |
| `governance_providers/contracts/action.py` | `…/contracts/action.py` | COMPATIBILITY_LAYER |
| `governance_providers/contracts/execution.py` | `…/contracts/execution.py` | COMPATIBILITY_LAYER |

The `errors`/`lifecycle`/`metadata`/`contracts/*` modules already re-export the
canonical `ugence_governance_contracts`; they move verbatim (still re-exporting the
same leaf), so Governance Contracts is **not** duplicated.

## Tests (9 files, 42 tests) → `packages/governance-provider-framework/tests/`

| Current path | Canonical path | Notes |
|---|---|---|
| `governance_providers/tests/conftest.py` | `tests/conftest.py` | shared fixtures + kernel lifecycle helper |
| `governance_providers/tests/test_contracts_and_registry.py` | `tests/unit/test_contracts_and_registry.py` | imports rewritten to canonical namespace |
| `governance_providers/tests/test_resolution_and_config.py` | `tests/unit/test_resolution_and_config.py` | " |
| `governance_providers/tests/test_lifecycle_errors_observability.py` | `tests/unit/test_lifecycle_errors_observability.py` | " |
| `governance_providers/tests/test_reference_conformance.py` | `tests/conformance/test_reference_conformance.py` | " |
| `governance_providers/tests/test_adapters.py` | `tests/integration/test_adapters.py` | kernel-bound (needs decision-governance) |
| `governance_providers/tests/test_fixtures.py` | `tests/integration/test_fixtures.py` | kernel lifecycle |
| `governance_providers/tests/test_dependency_boundaries.py` | `tests/boundaries/test_dependency_boundaries.py` | path anchors + core-scan updated |
| `governance_providers/tests/test_packaging.py` | `tests/packaging/test_packaging.py` | rewritten for the new two-distribution model |

## Packaging

| Current | After |
|---|---|
| `packaging/dgm-provider-framework/pyproject.toml` (impl via symlink) | compat shell: depends on `ugence-governance-provider-framework[adapters]==0.1.0`; symlink → root `governance_providers` shim |
| `packaging/dgm-provider-framework/governance_providers -> ../../governance_providers` | re-points to the root shim (still one file) |
| — (new) | `packages/governance-provider-framework/pyproject.toml` → `ugence-governance-provider-framework` |

## New files (added, not moved)

- `packages/governance-provider-framework/{README.md,CHANGELOG.md,MIGRATION.md,LICENSE,.gitignore,conftest.py}`
- `packages/governance-provider-framework/verify_governance_provider_framework_distribution.py`
- `packages/governance-provider-framework/tests/compatibility/test_legacy_namespace.py` (identity shim proof)
- `governance_providers/__init__.py` (rewritten as the logic-free legacy shim)
- `docs/migrations/governance_provider_framework/*` (this evidence set)
- `scripts/gpf_equivalence_capture.py` (equivalence harness)
