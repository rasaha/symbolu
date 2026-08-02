# Agent Runtime — Public API

The single supported entry point is `ugence_agent_runtime.api` (re-exported at the
top level as `ugence_agent_runtime`). Everything not listed here is internal and may
change without notice. No product-specific class is exposed through the core API.

Machine-readable form: [`../artifacts/agent_runtime_public_api.json`](../artifacts/agent_runtime_public_api.json).

## Types

| Symbol | Kind | Purpose |
| --- | --- | --- |
| `AgentRuntime` | class | Coordinates workflow execution. |
| `AgentRuntimeConfig` | dataclass | Immutable configuration / dependency injection. |
| `AgentDescriptor` | dataclass | Neutral identity of the actor a workflow runs for. |
| `WorkflowDefinition` | dataclass | Immutable declaration of one workflow (task graph). |
| `WorkflowInstance` | dataclass | Mutable runtime state of a running workflow. |
| `WorkflowStatus` | enum | `CREATED/READY/RUNNING/PAUSED/WAITING/COMPLETED/FAILED/CANCELLED`. |
| `TaskDefinition` | dataclass | Immutable declaration of one task. |
| `TaskInstance` | dataclass | Mutable runtime state of a task. |
| `TaskStatus` | enum | `PENDING/READY/RUNNING/WAITING/COMPLETED/FAILED/CANCELLED/SKIPPED`. |
| `RuntimeTransition` | dataclass | A recorded state change. |
| `RuntimeEvent` | dataclass | A deterministic coordination event. |
| `RuntimeResult` | dataclass | Outcome of a run (status, completed tasks, failures). |
| `RuntimeFailure` | dataclass | Classified failure (`FailureCategory`). |
| `FailureCategory` | enum | Neutral failure taxonomy. |
| `Provider` | Protocol | Neutral provider contract. |
| `ProviderRegistry` | class | Explicit provider id → provider map. |
| `ToolInvocation` / `ToolResult` | dataclass | Neutral provider I/O. |
| `Checkpoint` | dataclass | Digest-verified coordination snapshot. |
| `CheckpointStore` / `RuntimeStateStore` / `RuntimeEventStore` | Protocol | Persistence interfaces. |
| `RuntimeRecoveryResult` | dataclass | Result of reconstructing an instance. |
| `GovernanceHook` | Protocol | Neutral governance boundary. |
| `GovernanceEvaluation` | dataclass | Governance result the runtime consumes. |
| `GovernanceDisposition` | enum | `CLEAR/HOLD/BLOCK/ESCALATE`. |
| `NoopGovernanceHook` | class | Default hook (always `CLEAR`; creates no authority). |
| `ExecutionContext` / `CorrelationContext` | dataclass | Neutral context passed to governance. |
| `RetryPolicy` | dataclass | Deterministic attempt-counting policy. |
| `AgentRuntimeError` + subclasses | exception | Curated error taxonomy. |

## Functions

| Function | Purpose |
| --- | --- |
| `create_runtime(config=None)` / `open_runtime(config=None)` | Build a runtime. No I/O. |
| `start_workflow(runtime, definition, correlation_id=None)` | Start and drive a workflow. |
| `resume_workflow(runtime, instance_id)` | Explicitly continue a `WAITING`/`PAUSED` workflow. |
| `pause_workflow(runtime, instance_id)` | Explicitly pause a `RUNNING` workflow. |
| `cancel_workflow(runtime, instance_id)` | Cancel a workflow and its non-terminal tasks. |
| `recover_runtime(runtime, instance_id, definition)` | Reconstruct state from persistence (no external call). |
| `register_provider(runtime, provider)` | Register a provider explicitly. |
| `register_governance_hook(config, hook)` | Return a new config bound to `hook`. |

## Stability

- The names above are the compatibility surface for `0.x`.
- Internal modules (`runtime.engine` internals, `runtime.execution`, etc.) are not
  part of the contract.
- Deprecated legacy aliases live in `ugence_agent_runtime.compat` and emit
  `DeprecationWarning`.
