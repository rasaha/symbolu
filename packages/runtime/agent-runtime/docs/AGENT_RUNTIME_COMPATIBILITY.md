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

## Compatibility surface

`ugence_agent_runtime.compat` provides identity-preserving aliases so any code that
reaches for a differently-named coordination primitive can import it from one stable
place while migrating to `ugence_agent_runtime.api`.

| Legacy alias | Canonical | Classification |
| --- | --- | --- |
| `compat.Runtime` | `api.AgentRuntime` | `TEMPORARY_COMPATIBILITY_REEXPORT` |
| `compat.Workflow` | `api.WorkflowDefinition` | `TEMPORARY_COMPATIBILITY_REEXPORT` |
| `compat.WorkflowRun` | `api.WorkflowInstance` | `TEMPORARY_COMPATIBILITY_REEXPORT` |
| `compat.Task` | `api.TaskDefinition` | `TEMPORARY_COMPATIBILITY_REEXPORT` |
| `compat.TaskRun` | `api.TaskInstance` | `TEMPORARY_COMPATIBILITY_REEXPORT` |
| `compat.WorkflowCheckpoint` | `api.Checkpoint` | `TEMPORARY_COMPATIBILITY_REEXPORT` |
| `compat.Registry` | `api.ProviderRegistry` | `TEMPORARY_COMPATIBILITY_REEXPORT` |
| `compat.Result` | `api.RuntimeResult` | `TEMPORARY_COMPATIBILITY_REEXPORT` |

Each alias **is** the canonical object (`compat.resolve(alias) is api.<Canonical>`), so
there is no duplicate runtime implementation. Accessing an alias emits a
`DeprecationWarning` pointing at the canonical import.

## Legacy `agent_runtime_migration` classification

| Legacy import | New import | Status | Planned removal |
| --- | --- | --- | --- |
| `agent_runtime_migration.workflow.Workflow` | `ugence_agent_runtime.api.WorkflowDefinition` | `DEPRECATED` | after consumers migrate |
| `agent_runtime_migration.workflow.Checkpoint` | `ugence_agent_runtime.api.Checkpoint` | `DEPRECATED` | after consumers migrate |
| `agent_runtime_migration.runtime.runtime.AgentRuntime` | `ugence_agent_runtime.api.AgentRuntime` | `DEPRECATED` | after consumers migrate |
| `agent_runtime_migration.tracing.events.RuntimeEvent` | `ugence_agent_runtime.models.events.RuntimeEvent` | `DEPRECATED` | after consumers migrate |
| `agent_runtime_migration.control_plane.*` (CER-coupled) | *stays legacy* | `INTERNAL_UNSUPPORTED_IMPORT` | n/a (concrete governance adapter) |
| `agent_runtime_migration.proposal.*` (CER builder) | *stays legacy* | `INTERNAL_UNSUPPORTED_IMPORT` | n/a (concrete governance adapter) |

The legacy package is **not** silently deleted. Its CER-coupled proposer/control-plane
modules are the concrete governance integration and remain where they are; a future
phase can rebuild them on top of this neutral core.

## Migration guidance

New code should import from `ugence_agent_runtime.api`. Existing/legacy code can adopt
the package incrementally via `ugence_agent_runtime.compat`, resolving the deprecation
warnings as it goes.
