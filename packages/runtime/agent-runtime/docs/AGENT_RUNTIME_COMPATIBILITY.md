# Agent Runtime — Compatibility

This is the first independent distribution of the Agent Runtime. The runtime
previously lived inside the monorepo package `agent_runtime_migration`, which
remains in place as the legacy, CER-coupled proposer.

Machine-readable form:
[`../artifacts/agent_runtime_compatibility_map.json`](../artifacts/agent_runtime_compatibility_map.json).

## Consumer inventory

A repository-wide search found **zero code consumers** of `agent_runtime_migration`
outside the package itself. Every other reference is a *forbidden-import assertion*
(boundary tests confirming other packages do **not** depend on the runtime):

- `packages/governance-contracts/tests/packaging/test_leaf_dependency.py`
- `packages/capabilities/storygraph/tests/compatibility/test_dependencies.py`
- `packages/capabilities/decision-authority/tests/test_platform_boundaries.py`
- `evidence_obligation/dataset.py`, `reviewer_calibration_pilot/dataset.py`
  (string references in "excluded modules" lists)

Because there are no runtime consumers to break, migration risk is minimal. The legacy
package is left untouched (its 74 tests still pass) and is **not** deleted.

## Outcome B — honest coexistence (corrected in 0.1.1)

**This is NOT a runtime-compatibility shim.** The legacy runtime
`agent_runtime_migration.runtime.runtime.AgentRuntime` is a *different implementation*
with an *incompatible API*:

| | Legacy proposer | Kernel |
| --- | --- | --- |
| Construct | `AgentRuntime(*, executor, planner=…, reflector=…, memory=…)` | `AgentRuntime(config)` |
| Drive | `run(goal: Goal, …) -> RunOutcome` | `start_workflow(definition) -> WorkflowInstance` |
| Owns | planning, reasoning, memory, reflection | workflow/task coordination |

Neither can substitute for the other. The 0.1.0 `ugence_agent_runtime.compat` aliases
(`Runtime`, `Workflow`, …) were **new-package aliases**, not legacy compatibility, and
the "identity-preserving / no duplicate implementation" claim was inaccurate. Those
aliases have been **removed**.

`ugence_agent_runtime.compat` now provides **migration guidance only**:

- `MIGRATION_MAP` — legacy import path → `{new target | None, classification, note}`.
- `classify(legacy_path)` / `new_target(legacy_path)`.

| Legacy import | Kernel target | Classification |
| --- | --- | --- |
| `agent_runtime_migration.runtime.runtime.AgentRuntime` | *(none — different impl)* | `PRESENT_CHANGED` |
| `agent_runtime_migration.workflow.Workflow` | `ugence_agent_runtime.api.WorkflowDefinition` | `PRESENT_CHANGED` |
| `agent_runtime_migration.workflow.Checkpoint` | `ugence_agent_runtime.api.Checkpoint` | `PRESENT_CHANGED` |
| `agent_runtime_migration.tracing.events.RuntimeEvent` | `ugence_agent_runtime.models.events.RuntimeEvent` | `PRESENT_CHANGED` |
| `agent_runtime_migration.tools.registry` | `ugence_agent_runtime.api.ProviderRegistry` | `PRESENT_CHANGED` |
| `agent_runtime_migration.planning` / `reasoning` / `memory` | *(none)* | `INTENTIONALLY_EXCLUDED` |
| `agent_runtime_migration.control_plane` / `proposal` | *(none)* | `LEGACY_INTEGRATION_ONLY` |

`tests/test_compatibility.py` imports the **actual** legacy path and asserts the two
runtimes are distinct implementations (skipped when the monorepo is absent, e.g. the
isolated-wheel run). The legacy package is retained (its 74 tests still pass) and is
**not** deleted; a future migration phase disposes of it.

## Migration guidance

New code should import from `ugence_agent_runtime.api`. Because the kernel is not
API-compatible with the legacy proposer, "migration" means **rewriting** planning/memory
concerns to live outside the kernel and mapping legacy workflow/tool concepts to the
kernel's models using `ugence_agent_runtime.compat.MIGRATION_MAP` — not swapping an
import. Consult `classify(legacy_path)` for the fidelity classification of each legacy
subsystem.
