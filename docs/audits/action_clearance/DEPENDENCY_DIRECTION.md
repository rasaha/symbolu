# ACP Dependency Direction

Classification of every dependency the ACP discipline touches, using the audit's vocabulary.

## Robotics core (`symbolu_robotics/autonomous_control_plane/`)

| Dependency | From → To | Class |
|---|---|---|
| Python standard library | core → stdlib | **REQUIRED_NEUTRAL_DEPENDENCY** |
| `symbolu_robotics.safety.trajectory_validator` | `safety_adapters/*` → real validator | **OPTIONAL_ADAPTER_DEPENDENCY** (on-demand; not in core `__init__`) |
| `cloud_controller.action.{readiness,policy}`, `cloud_controller.recommend.safety` | `cloud/*` → real modules | **OPTIONAL_ADAPTER_DEPENDENCY** (lazy import) |
| numpy | `safety_adapters/*` only | **OPTIONAL_ADAPTER_DEPENDENCY** |
| governance-contracts / control_plane / actiongate | core → (none) | **UNNECESSARY** (core imports none of these) |

**Direction:** strictly inward/downward. The core is a **dependency-clean stdlib leaf**; adapters depend
downward on real deterministic evaluators, loaded on demand. Production code does **not** import the core
(grep-asserted). There is **no dependency inversion** to unwind.

## Console digital clearance (concept #3)

| Dependency | From → To | Class |
|---|---|---|
| `ugence_console_api.models` (pydantic DTOs) | `operational_safety` → models | **PRODUCT_DEPENDENCY** (in-service) |
| pydantic | console → pydantic | **REQUIRED_NEUTRAL_DEPENDENCY** (for the console) |
| robotics core | console → (none) | **UNNECESSARY** (no import; label only) |

## Governance-chain seam

| Dependency | From → To | Class |
|---|---|---|
| `ugence_governance_contracts` | GPF/DA → contracts leaf | **REQUIRED_NEUTRAL_DEPENDENCY** |
| Decision Authority (`decision_governance`) | GPF adapters extra → DA | **OPTIONAL_ADAPTER_DEPENDENCY** (optional extra) |

## Would a future ACP package invert anything? No — but the seam matters

- A canonical `ugence_action_clearance` would most naturally be a **stdlib-only leaf** (like
  `ugence_model_selection`) **or** carry a single downward dependency on `ugence-governance-contracts>=0.1.0`
  (like the provider-framework core) if it consumes the neutral `ActionGovernance*`/`EXPIRED` seam. Both are
  legal, downward directions in the platform layering (contracts is the floor).
- **Do not force ACP to be a standard-library-only leaf** if the live architecture calls for consuming the
  neutral contracts: a valid ACP package may depend downward on `ugence-governance-contracts`.
- The one dependency-shaped concern is not inversion but **surface coupling**: `cer_v0_*` depend on the
  *unfrozen* `.cloud.*` deep-import surface. A migration must convert this to a curated public API + legacy
  shim (`COMPATIBILITY_STRATEGY.md`).

## Platform dependency-direction validator

`platform_freeze.dependencies.dependency_report()` returns **passed=True, 0 violations** at baseline. ACP is
not among the frozen `CORE_TREES` (`decision_governance`, `governance_providers`, `actiongate_provider`,
`tap_provider`), so it is not currently subject to that validator; a future ACP package would add its own
layered dependency rules (as decision-authority does in
`conformance/dependency_rules.py` + `tests/test_platform_boundaries.py`).
