# Agent Runtime — H22 Readiness

This packaging phase ends with a stable, domain-neutral base on which H22
(Multi-Workflow Orchestration) can be built **without importing application
internals**. H22 is **not** implemented here.

## Ordering

```
Independent Agent Runtime package   ← delivered (0.1.0)
        ↓
H22 Multi-Workflow Orchestration    ← future feature phase
        ↓
Runtime-to-Governance integration validation
        ↓
Agentic product workflows
```

## What H22 may build on this base (not now)

- multi-workflow graph definitions;
- dependency resolution across workflows;
- bounded parallelism across workflows;
- cross-workflow state aggregation;
- failure propagation across workflows;
- compensation coordination;
- parent/child workflow relationships;
- multi-workflow recovery;
- orchestration-level audit events.

**None of the above is implemented in this packaging phase.**

## Why the base is ready

- **Single-workflow primitives are neutral and stable.** `WorkflowDefinition` /
  `WorkflowInstance`, `TaskDefinition` / `TaskInstance`, the transition tables, and the
  event model are the building blocks a multi-workflow layer composes.
- **Deterministic, injectable core.** Clock, id generator, provider registry,
  persistence, governance hook, and event sink are all injected — an orchestrator can
  drive many instances with shared, deterministic infrastructure.
- **Recovery is per-instance and side-effect free.** Multi-workflow recovery composes
  per-instance recovery without new external calls.
- **Governance boundary is per-transition and neutral.** Cross-workflow policy remains
  a governance concern behind the same neutral hook — the orchestrator never gains
  governance authority.
- **No application coupling.** The base builds and installs as a clean wheel with no
  monorepo import, so H22 can depend on the distribution, not the application layer.

## Extension points H22 will likely use

- `AgentRuntime` as the per-workflow executor an orchestrator composes.
- `RuntimeStateStore` / `CheckpointStore` for durable multi-workflow state.
- `RuntimeEvent` stream for orchestration-level audit aggregation.
- `GovernanceHook` for cross-workflow / sequence-risk policy (authored **outside** the
  runtime).
