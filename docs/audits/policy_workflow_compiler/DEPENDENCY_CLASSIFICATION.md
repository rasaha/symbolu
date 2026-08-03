# Dependency classification

## Core dependencies (mandatory)
- `pydantic>=2` — the only core dependency. Typed, frozen, deterministically
  serializable object model.

The compiler core imports **no** governance runtime. Capability targets are
represented by stable identifiers and resolved from registry **metadata**; an
optional `importlib.util.find_spec` probe can check installability but is never
required for compilation.

## Optional dependencies (extras)
- `procurement-reference = ["ugence-procurement>=0.1.0"]` — used **only** by the
  Procurement equivalence harness (`reference/procurement_equivalence.py`), which
  imports `ugence_procurement` lazily and raises `ReferenceUnavailable` if absent.
  Pulling in `ugence-procurement` transitively provides `ugence-decision-authority`.
- `dev = ["pytest>=7.0", "build>=1.0"]`.

### Why an extra (not a repo fixture)
The equivalence harness compares against the **live** `ugence-procurement`
behavior (its `BudgetAuthorityAdapter`, `ProcurementAssessmentService`, mapping
constants). Binding to the real package — not a frozen fixture — is what makes the
equivalence claim meaningful: if Procurement's behavior changes, the harness
notices. The extra keeps this dependency out of the core install.

## Deliberately NOT dependencies
Per the spec's scope discipline, none of the following are core dependencies:
`ugence-tap-provider`, `ugence-actiongate-provider`, `ugence-action-clearance`,
`ugence-decision-authority` (core), StoryGraph, Model Selection, FastAPI, database
drivers, cloud SDKs, model SDKs, ERP SDKs. The compiler emits *references* to
capabilities without importing their runtimes.

## Legacy → canonical mapping (compiler uses canonical only)
| Legacy alias | Canonical distribution | Canonical namespace |
|---|---|---|
| `decision_governance` | `ugence-decision-authority` | `ugence_decision_authority` |
| `tap_provider` | `ugence-tap-provider` | `ugence_tap_provider` |
| `actiongate_provider` | `ugence-actiongate-provider` | `ugence_actiongate_provider` |
| `acp` (conceptual "Action Clearance") | `ugence-action-clearance` | `ugence_action_clearance` |
| `composite_threat_detector` | `ugence-storygraph` | `ugence_storygraph` |
| `execution_gate` / `model_selection_pilot` | `ugence-model-selection` | `ugence_model_selection` |

Note: the repo-root `acp/` directory is documentation-only, and the robotics
`autonomous_control_plane` package is a separate subsystem — neither is a
governance capability the compiler depends on. The compiler's "Action Clearance"
target maps to the canonical `ugence-action-clearance` capability.
