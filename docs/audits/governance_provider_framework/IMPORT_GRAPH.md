# Import Graph & Dependency Direction — Governance Provider Framework

Audit-only. Evidence gathered by AST/grep sweep of the working tree at
`1a191629`. Nothing modified.

## 1. Outbound dependencies of `governance_providers/` (what the framework imports)

The framework imports **exactly two** external roots — everything else is Python
stdlib or package-relative:

```
governance_providers  ──▶  ugence_governance_contracts      (in the compat shims)
governance_providers  ──▶  decision_governance.api          (ONLY in adapters/)
```

Per-module (non-test) external imports:

| Module | Imports | Kind |
|---|---|---|
| `contracts/__init__.py`,`contracts/base.py`,`contracts/action.py`,`contracts/assertion.py`,`contracts/execution.py` | `ugence_governance_contracts.contracts[.*]` | shim re-export |
| `errors.py` | `ugence_governance_contracts.errors` | shim re-export |
| `lifecycle.py` | `ugence_governance_contracts.lifecycle` | shim re-export |
| `metadata.py` | `ugence_governance_contracts.metadata` | shim re-export |
| `adapters/action_to_control_plane.py` | `decision_governance.api.common`, `decision_governance.api.contracts` | kernel port binding |
| `adapters/execution_to_external_system.py` | `decision_governance.api.common`, `decision_governance.api.contracts`, `decision_governance.api.ports` | kernel port binding |
| `adapters/assertion_integration.py` | `decision_governance.api.ports` | kernel port binding |
| `registry`, `resolution`, `configuration`, `observability`, `fingerprint`, `version`, `reference/*`, `conformance/*` | **none** (stdlib + relative only) | pure |

**Critical structural fact:** the framework's pure core (registry, resolution,
configuration, observability, fingerprint, version) imports **nothing external**.
The *only* dependency on the kernel (`decision_governance.api`) is confined to the
three modules under `adapters/`. `conformance/common.py` mentions the string
`"decision_governance"` only inside an AST boundary-check, not as an import.

Every kernel import uses the **public facade `decision_governance.api`** — never a
deeper submodule. This is asserted by
`governance_providers/tests/test_dependency_boundaries.py`.

## 2. The transitive "adapters bleed"

Because `governance_providers/api/__init__.py` re-exports the adapters, importing
`governance_providers.api` transitively pulls in `decision_governance.api` (and,
through it, `pydantic` and — post-Decision-Authority-migration — the
`ugence_decision_authority` package that now backs the `decision_governance`
namespace). This is the boundary bleed flagged in
`UGENCE_MODULARITY_AND_PACKAGING_AUDIT.md` and the restructuring plan:

> `governance_providers.api` transitively drags `decision_governance`+`pydantic`
> via `adapters/__init__` (boundary bleed, not business need) — split contracts
> from adapters so contracts are a leaf.

Half of that recommendation is already done: the **neutral contracts** were
extracted to the pure leaf `ugence_governance_contracts` (imports nothing but
stdlib). A consumer that needs only contracts/metadata/errors can import
`ugence_governance_contracts` and avoid the kernel entirely. The remaining half —
isolating the kernel-bound `adapters/` from the pure framework core — is a
refinement, **not** a dependency-direction violation (see §4).

## 3. Inbound dependencies (who imports the framework) — 66 external files

Grouped by area. Full file:line list in `PUBLIC_API_AND_CONSUMER_MAP.md`.

```
ai_hiring/ ................ 26 import sites (application layer; heaviest consumer)
tap_provider/ ............. concrete provider (via .api + .conformance)
actiongate_provider/ ...... concrete provider (via .api + .conformance)
baseline_assertion_provider/ .. via .api + .conformance
baseline_action_provider/ ..... via .api + .conformance
enterprise_validation_pilot/ .. composition/root, runners, evaluators, tests
provider_heterogeneity_validation/ .. runners + selection (uses .version)
comparative_governance_benchmark/ .. strategies
platform_freeze/ .......... invariants.py + tests (release tooling)
ugence_console_api/ ....... lazy imports inside try-blocks (capabilities/*)
packaging/ ................ verify_*_distribution.py scripts
packages/governance-contracts/tests .. legacy-compat matrix (deep import shims)
docs/ ..................... PROVIDER_DEVELOPMENT_GUIDE.md (doc example)
```

No consumers in `applications/`, `domains/`, root `tests/`, `scripts/`, or
`decision_governance/`.

## 4. Dependency-direction verdict

Correct and acyclic layering (arrows = "depends on"):

```
applications / ai_hiring / domains
        │
        ▼
concrete providers ── tap_provider, actiongate_provider, baseline_*
        │  (import governance_providers.api + .conformance)
        ▼
governance_providers  (Governance Provider Framework)
   ├── pure core ─────────────▶ ugence_governance_contracts   (pure stdlib leaf)
   └── adapters/ ─────────────▶ decision_governance.api        (kernel public facade)
                                        │
                                        ▼
                                 ugence_decision_authority      (Decision Authority)
```

- The framework depends **downward** only: on the neutral contracts leaf and on
  the kernel's public API facade. It never imports a concrete provider, an
  application, a domain, or a product. **Verified: zero upward imports.**
- The rule is machine-enforced three ways: `platform_freeze/dependencies.py`
  `FORBIDDEN_IMPORTS["governance_providers"]`, the freeze manifest
  `dependency_rules`, and `governance_providers/tests/test_dependency_boundaries.py`
  (`forbidden_roots = {"ai_hiring","domains","applications"}`).
- No cycle exists (freeze invariant **F20** "dependency direction remains
  acyclic" verifies green).
- The framework→`decision_governance.api` edge is the **designed** framework↔kernel
  adaptation, not an invalid dependency on a concrete capability: only `adapters/`
  carries it, and the pure core has no such edge. A future step can lift the
  adapters into an isolated sub-module/distribution without touching the core.

## 5. Deep-import (non-`.api`) consumers — migration-relevant coupling

These external modules bypass `governance_providers.api` and reach submodules
directly; a physical migration must preserve these exact module paths (via the
identity-preserving legacy shim) or update the consumer:

| Submodule reached | Consumers |
|---|---|
| `governance_providers.contracts[.action]` | `ai_hiring/**` (12 sites — `demo.py`, `validation/*`, many `tests/*`) |
| `governance_providers.reference.{assertion,action}` | `ai_hiring/tests/h2_helpers.py`, `h4_helpers.py`, `ai_hiring/validation/lifecycle.py` |
| `governance_providers.conformance` | tap/actiongate/baseline tests, `enterprise_validation_pilot`, packaging verifiers |
| `governance_providers.version` | `provider_heterogeneity_validation/selection/resolve.py` |
| `governance_providers.{errors,lifecycle,metadata,contracts.*}` | `packages/governance-contracts/tests/compatibility/test_legacy_compat.py` (deliberate compat matrix) |

`ai_hiring` is the only application-layer package reaching into framework
submodules (`.contracts`, `.reference`) rather than `.api`; this is legacy usage
that the extracted contracts leaf now makes redundant, but it is compatible and
must be preserved by shims during any migration.
