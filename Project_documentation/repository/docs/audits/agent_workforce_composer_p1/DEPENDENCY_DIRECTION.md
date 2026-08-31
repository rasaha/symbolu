# Dependency Direction

AWC is a **leaf capability**. Core runtime dependencies: Python standard library +
`pydantic` only (consistent with the upstream Policy Workflow Compiler).

## Allowed
- `pydantic` (frozen models, validation).
- A **serialized** `workflow_ir.v1` document as data input (no import).
- Optional `compiler-reference` extra (`ugence-policy-workflow-compiler`) used ONLY
  by an optional test to prove contract fidelity — never by core code.

## Forbidden (verified by `tests/test_boundaries.py`)
`agentic.agentic_framework` (H16), `agent_runtime_v2` / `agent_runtime_migration`,
H22, `ugence_model_selection` / `execution_gate`, `ai_hiring`, `ugence_procurement`,
`ugence_actiongate_provider`, `ugence_action_clearance`, `ugence_storygraph`,
`control_plane` / `cloud_controller`, `ugence_policy_workflow_compiler` (in core),
any network/provider SDK (`requests`, `httpx`, `socket`, `openai`, `anthropic`, …).

## Direction
```
Policy Workflow Compiler  ──(serialized WorkflowIR, data-only)──▶  AWC (leaf)
AWC  ──(AgentTeamPlan; P2+)──▶  Agent Runtime / H22    [NOT in P1]
```
Upstream and downstream are represented only through injected data / neutral
serialized contracts. No dependency cycle is introduced. `test_boundaries.py`
statically scans every source file's imports and asserts an isolated subprocess
importing the public API loads none of the forbidden modules.
