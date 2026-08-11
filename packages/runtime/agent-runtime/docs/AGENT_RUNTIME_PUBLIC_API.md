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
| `WorkflowAdvanceOutcome` | dataclass | Frozen result of one bounded advancement quantum (H22-A): before/after status, `stop_reason`, advanced task, `execution_state_digest`, `checkpoint_digest`, terminal/waiting/paused. References state by digest; never a second copy of it. |
| `WorkflowAdvanceStop` | enum | Stable stop-reason for a quantum (`TASK_ADVANCED`, `WORKFLOW_COMPLETED/FAILED/WAITING/PAUSED/CANCELLED`, `ALREADY_TERMINAL`, `REQUIRES_RESUME`). |
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
| `UnconfiguredGovernanceHook` | class | **Default** hook (BLOCK; fail closed when no adapter configured). |
| `AllowAllGovernanceHook` | class | Explicit, opt-in, **unsafe** testing hook (CLEAR bound to fingerprint). Never a default. |
| `NoopGovernanceHook` | class | Deprecated alias of `AllowAllGovernanceHook`; emits `DeprecationWarning`. |
| `TransitionProposal` | dataclass | Immutable exact-invocation description + deterministic fingerprint. |
| `validate_clearance` | function | Exact-action clearance gate (fail closed). |
| `CanonicalExecutionState` | dataclass | Deterministic, versioned, integrity-protected, runtime-owned execution-trajectory snapshot (SHA-256 `state_digest`). References the proposal fingerprint; never a second action payload. |
| `ExecutionLineage` | dataclass | Optional, typed, neutral seam for causation/parent/agent-plan/artifact **references** supplied at workflow boundaries. Never fabricated; never used for agent selection. |
| `ExecutionContext` / `CorrelationContext` | dataclass | Neutral context passed to governance. |
| `RetryPolicy` | dataclass | Deterministic attempt-counting policy. |
| `AgentRuntimeError` + subclasses | exception | Curated error taxonomy. |

### Multi-workflow coordination (H22-B)

| Symbol | Kind | Purpose |
| --- | --- | --- |
| `WorkflowPortfolio` | class | Orchestration-state aggregate; references workflows by `instance_id`, duplicates no runtime state. |
| `PortfolioWorkflowEntry` | dataclass | One registration's orchestration metadata (priority/weight/sequence/age/`fair_credit`). |
| `PortfolioStatus` | enum | `CREATED/ACTIVE/COMPLETED/FAILED/CANCELLED`. |
| `WorkflowPriority` / `priority_rank` | enum / fn | Orchestration priority (never governance authority). |
| `DependencyGraph` / `WorkflowDependency` / `DependencyType` / `DependencyState` | class / dataclass / enum | Deterministic cross-workflow DAG (`REQUIRES_COMPLETION` / `REQUIRES_SUCCESS`). |
| `PortfolioScheduler` | class | Grants one bounded H22-A quantum per round (priority / SWRR fairness / bounded aging). |
| `SchedulingPolicy` / `SelectionReason` / `PortfolioStepResult` / `PortfolioStepReason` / `WorkflowEligibility` | dataclass / enum | Scheduler policy, structured "why", and step outcome. |

### Durable orchestration (H22-C)

| Symbol | Kind | Purpose |
| --- | --- | --- |
| `PortfolioCheckpoint` | dataclass | Versioned, self-verifying portfolio orchestration snapshot; **references** runtime checkpoints by digest, never copies them or Canonical Execution State. |
| `WorkflowCheckpointRef` | dataclass | Reference binding a registration to its runtime checkpoint across **both** integrity domains: identity + base `checkpoint_digest` + `checkpoint_version` + canonical-execution-state `extension_digest`. |
| `PortfolioCheckpointStore` | Protocol | Neutral portfolio checkpoint store interface. |
| `InMemoryPortfolioCheckpointStore` | class | Reference store (monotonic `generation`, optional compare-and-save). |
| `PortfolioCheckpointConflict` | exception | Stale compare-and-save write. |
| `PortfolioRecoveryResult` | dataclass | Side-effect-free recovery outcome (`requires_continuation`, recovered ids, trace, typed `failure_policy`, metadata). |
| `PortfolioTrace` / `PortfolioTraceEntry` / `PortfolioEventType` | class / dataclass / enum | Append-only orchestration audit trace (logical sequence; ids/digests only). |
| `PortfolioEventStore` / `InMemoryPortfolioEventStore` | Protocol / class | Neutral durable append-only, portfolio-scoped trace event store (contiguous sequence; immutable canonical-JSON records; reference impl). Makes pre-crash audit history survive recovery. |
| `PortfolioTraceSequenceError` | exception | Duplicate / out-of-order trace event rejected by the event store. |
| `PortfolioTraceEncodingError` | exception | Non-serializable (opaque) or NaN/±Inf trace-event detail rejected fail-closed. |
| `PortfolioController` | class | Ties scheduler + trace + failure policy + cancellation + durable checkpoint. |
| `PortfolioFailurePolicy` | enum | Bounded failure propagation (`ISOLATE_WORKFLOW` default / `FAIL_DEPENDENTS` / `FAIL_PORTFOLIO`). |
| `CancellationScope` / `PortfolioCancellationResult` | enum / dataclass | Cooperative, idempotent cancellation (`WORKFLOW_ONLY` / `DEPENDENT_SUBGRAPH` / `PORTFOLIO_ALL`). |

## Functions

| Function | Purpose |
| --- | --- |
| `create_runtime(config=None)` / `open_runtime(config=None)` | Build a runtime. No I/O. |
| `start_workflow(runtime, definition, correlation_id=None, lineage=None, task_lineage=None)` | Start and drive a workflow to its next stable stopping condition (optional workflow-common and per-task `ExecutionLineage`). |
| `prepare_workflow(runtime, definition, correlation_id=None, lineage=None, task_lineage=None)` | Create/register a workflow **without draining it** (H22-A); advance it with `advance_workflow`. |
| `advance_workflow(runtime, instance_id)` | Advance a prepared/running workflow by **one bounded quantum**; returns `WorkflowAdvanceOutcome` (H22-A). |
| `execution_state(runtime, instance_id, task_id=None)` | Read the latest canonical execution-state snapshot (read-only). |
| `execution_state_by_digest(runtime, instance_id, state_digest)` | Resolve a historical snapshot by its digest (read-only). |
| `resume_workflow(runtime, instance_id)` | Explicitly continue a `WAITING`/`PAUSED` workflow (drains to a stable state). |
| `continue_workflow(runtime, instance_id)` | Bounded continuation seam (H22-C): re-arm a `WAITING`/`PAUSED` workflow to `RUNNING` for one-quantum-at-a-time advancement **without draining it**. |
| `pause_workflow(runtime, instance_id)` | Explicitly pause a `RUNNING` workflow. |
| `cancel_workflow(runtime, instance_id)` | Cancel a workflow and its non-terminal tasks. |
| `recover_runtime(runtime, instance_id, definition)` | Reconstruct one instance from persistence (no external call). |
| `register_provider(runtime, provider)` | Register a provider explicitly. |
| `register_governance_hook(config, hook)` | Return a new config bound to `hook`. |
| `create_portfolio(portfolio_id)` | Create an empty `WorkflowPortfolio` (H22-B). |
| `create_portfolio_scheduler(runtime, policy=None)` | Create a deterministic `PortfolioScheduler` (H22-B). |
| `create_portfolio_controller(runtime, portfolio, *, policy=…, checkpoint_store=None, …)` | Create an H22-C `PortfolioController` (scheduler + trace + failure policy + cancellation + durable checkpoint). |
| `recover_portfolio(*, store, portfolio_id, runtime, definitions, trace=None)` | **Side-effect-free** portfolio recovery (H22-C); reconstructs the portfolio and returns `PortfolioRecoveryResult` requiring explicit continuation. |

## Stability

- The names above are the compatibility surface for `0.x`.
- Internal modules (`runtime.engine` internals, `runtime.execution`, etc.) are not
  part of the contract.
- Deprecated legacy aliases live in `ugence_agent_runtime.compat` and emit
  `DeprecationWarning`.

## Attempt telemetry (CM-TA1, 0.7.0)

Additive, opt-in: `ProviderAttempt`, `ProviderAttemptStatus`, `AttemptContext`,
`AttemptObserver`, `RecordingAttemptObserver`, and `PROVIDER_USAGE_METADATA_KEY`, plus
the optional `AgentRuntimeConfig.attempt_observer` field (`None` = no behavior change).
The observer is notified once per actual `provider.execute` invocation with the
runtime-authoritative attempt number; a governance/exact-action rejection or a
provider-not-found produces no attempt. See
[`AGENT_RUNTIME_ATTEMPT_TELEMETRY.md`](AGENT_RUNTIME_ATTEMPT_TELEMETRY.md).
