# Import Graph (BEFORE) — Governance Provider Framework

Verified directly at `ed7387f4` by grep/AST over the working tree. Companion:
`IMPORT_GRAPH_AFTER.md` (produced by the migration).

## Outbound (what `governance_providers` imports) — exactly two external roots

```
governance_providers  ──▶  ugence_governance_contracts   (in errors/lifecycle/metadata/contracts shims)
governance_providers  ──▶  decision_governance.api        (ONLY in adapters/*)
```

| Module | External imports | Kind |
|---|---|---|
| `errors.py`, `lifecycle.py`, `metadata.py`, `contracts/*` | `ugence_governance_contracts[.*]` | shim re-export |
| `adapters/action_to_control_plane.py` | `decision_governance.api.common`, `.contracts` | kernel port binding |
| `adapters/execution_to_external_system.py` | `decision_governance.api.common`, `.contracts`, `.ports` | kernel port binding |
| `adapters/assertion_integration.py` | `decision_governance.api.ports` | kernel port binding |
| `registry`, `resolution`, `configuration`, `observability`, `fingerprint`, `version`, `reference/*`, `conformance/*` | none (stdlib + relative only) | pure |

Pure core imports **nothing external**. `conformance/common.py` contains the
string `"decision_governance"` in an AST boundary check (line 103), not an import.

## The "adapters bleed" (unchanged by this migration)

`api/__init__` re-exports the adapters, so importing `governance_providers.api`
transitively pulls `decision_governance.api` (→ pydantic → `ugence_decision_authority`).
Importing the top-level package or any pure-core submodule does **not**. The
migration preserves this exactly (top-level `__init__` imports only `.version`);
it makes the kernel dependency an **optional** distribution extra so the core
installs/imports without Decision Authority.

## Inbound (who imports the framework) — 66 external files, all on `governance_providers`

```
ai_hiring/ .................. 26 sites (heaviest; deep-imports .contracts, .reference)
tap_provider/ .............. concrete provider (.api + .conformance)
actiongate_provider/ ....... concrete provider (.api + .conformance)
baseline_assertion_provider/, baseline_action_provider/ .. (.api + .conformance)
enterprise_validation_pilot/ .. composition, runners, evaluators, tests
provider_heterogeneity_validation/ .. runners + selection (uses .version)
comparative_governance_benchmark/ .. strategies
platform_freeze/ ........... invariants.py + tests
ugence_console_api/ ........ lazy guarded imports (capabilities/*)
packaging/ ................. verify_*_distribution.py
packages/governance-contracts/tests .. legacy-compat matrix (deep shims)
docs/ ...................... PROVIDER_DEVELOPMENT_GUIDE.md example
```

### Deep-import (non-`.api`) paths that MUST resolve post-migration via the shim

| Submodule reached | Consumers |
|---|---|
| `governance_providers.contracts[.action]` | `ai_hiring/**` (12 sites) |
| `governance_providers.reference.{assertion,action}` | `ai_hiring` helpers + `validation/lifecycle.py` |
| `governance_providers.conformance` | tap/actiongate/baseline tests, `enterprise_validation_pilot`, packaging verifiers |
| `governance_providers.version` | `provider_heterogeneity_validation/selection/resolve.py` |
| `governance_providers.{errors,lifecycle,metadata,contracts.*}` | `packages/governance-contracts/tests/compatibility/test_legacy_compat.py` (identity matrix) |

## Dependency direction (correct, acyclic, test-enforced)

```
applications / ai_hiring / domains
        ▼
concrete providers (tap_provider, actiongate_provider, baseline_*)
        ▼
governance_providers  (Governance Provider Framework)
   ├── pure core ───────▶ ugence_governance_contracts  (pure stdlib leaf)
   └── adapters/ ───────▶ decision_governance.api       (kernel facade) ─▶ ugence_decision_authority
```

Zero upward imports (framework → provider/app/domain). Enforced by
`platform_freeze/dependencies.py` `FORBIDDEN_IMPORTS["governance_providers"]`, the
freeze manifest `dependency_rules`, and `test_dependency_boundaries.py`. Freeze
invariant **F20** (acyclic) is green.
