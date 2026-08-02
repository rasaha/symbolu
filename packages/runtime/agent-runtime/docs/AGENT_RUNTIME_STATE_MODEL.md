# Agent Runtime — State Model

The runtime owns a small, deterministic state machine for workflows and tasks.
Governance-related waiting is **runtime state**, never governance authority.

Machine-readable form:
[`../artifacts/agent_runtime_state_model.json`](../artifacts/agent_runtime_state_model.json).

## Workflow statuses

`CREATED → READY → RUNNING → { PAUSED | WAITING | COMPLETED | FAILED | CANCELLED }`

| Status | Meaning |
| --- | --- |
| `CREATED` | Instance built; not yet started. |
| `READY` | Admitted to run. |
| `RUNNING` | Actively coordinating tasks. |
| `PAUSED` | Explicit pause **or** governance `ESCALATE` — external authority/review required. |
| `WAITING` | Governance `HOLD` on a task — external resolution required; **no authority created**. |
| `COMPLETED` | All tasks terminal and none failed/cancelled. |
| `FAILED` | A task failed (provider failure or governance `BLOCK`). |
| `CANCELLED` | Cancelled by the caller. |

`COMPLETED`, `FAILED`, `CANCELLED` are terminal.

## Task statuses

`PENDING → READY → RUNNING → { COMPLETED | FAILED | WAITING | CANCELLED }` (with
`READY` re-arm on retry, and `SKIPPED` for unreachable tasks).

| Status | Meaning |
| --- | --- |
| `PENDING` | Declared; dependencies not yet satisfied. |
| `READY` | Dependencies satisfied; eligible to run. |
| `RUNNING` | Provider invocation in progress. |
| `WAITING` | Governance `HOLD`/`ESCALATE` — awaiting external resolution. |
| `COMPLETED` | Provider succeeded. |
| `FAILED` | Provider failed, retries exhausted, timeout, or governance `BLOCK`. |
| `CANCELLED` | Cancelled before completion. |
| `SKIPPED` | Unreachable under deterministic ordering. |

`COMPLETED`, `FAILED`, `CANCELLED`, `SKIPPED` are terminal.

## Governance → runtime mapping

The runtime never reinterprets a governance result. The mapping is fixed:

| Disposition | Task | Workflow | Provider called? |
| --- | --- | --- | --- |
| `CLEAR` | RUNNING → COMPLETED/FAILED | continues | **yes** |
| `HOLD` | → WAITING | → WAITING | no |
| `BLOCK` | → FAILED | → FAILED | no |
| `ESCALATE` | → WAITING | → PAUSED | no |

`HOLD` and `ESCALATE` never become `CLEAR` inside the runtime. Continuation of a
`WAITING`/`PAUSED` workflow requires an explicit `resume_workflow` call — the runtime
does not self-resolve a restrictive disposition.

## Transition enforcement

All transitions are checked against the tables in `models/transitions.py`. An illegal
change raises `InvalidTransitionError`. The tables are the single source of truth and
are exported as an artifact for external auditing.

## Determinism

- Task selection is registration order among dependency-satisfied tasks.
- Events carry a monotonic `seq`, not a timestamp.
- The clock and id generator are injected, so runs are reproducible.
