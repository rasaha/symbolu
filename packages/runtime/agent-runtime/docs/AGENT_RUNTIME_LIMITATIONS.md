# Agent Runtime — Limitations

This release is a **packaging, boundary-hardening, and dependency-cleanup** phase. It
deliberately does the minimum needed to make the runtime an independent, neutral,
installable capability. The following are **not** implemented here and are recorded as
future capabilities rather than built to justify the package.

## Not implemented (by design)

- **Multi-workflow orchestration (H22).** No cross-workflow dependency graphs, no
  distributed scheduling, no cross-workflow state aggregation, no compensation
  coordination, no parent/child workflow relationships. See
  [`AGENT_RUNTIME_H22_READINESS.md`](AGENT_RUNTIME_H22_READINESS.md).
- **Agent planning / reasoning / memory.** The neutral coordination core does not
  include a planner, reflector, or memory system. Those remain agent-behavior concerns
  outside this package.
- **LLM routing / provider specifics.** No LLM client, no model routing, no vendor
  provider. Providers are neutral and supplied externally.
- **New provider kinds.** No new `ProviderKind` is introduced.
- **Distributed / parallel execution.** The reference engine executes tasks
  sequentially and deterministically. `max_concurrent_tasks` bounds concurrency but the
  reference engine never exceeds one in-flight task; a concurrent executor is future work.
- **Durable persistence backend.** Only in-memory reference stores ship; durable
  backends are supplied externally behind the persistence interfaces.
- **Concrete governance adapters.** The core ships only the neutral boundary and a
  no-op hook; concrete TAP/ActionGate/Action Clearance/Code Governance/StoryGraph
  adapters live outside the package.
- **Enforcement.** The runtime coordinates; it does not enforce policy or mint
  execution authority.
- **GitHub execution, external database, SaaS control plane.** None added.

## Behavioral scope

- A workflow is a **single** dependency graph of tasks. Composition across workflows is
  H22.
- Retry timing is attempt-counted and deterministic; wall-clock backoff requires an
  injected scheduler (not shipped).
- Timeout is measured against the injected clock; the reference engine does not preempt
  an in-flight synchronous provider call — it classifies a timeout after the call
  returns based on elapsed logical time.

## Explicitly preserved

Runtime **behavior** (task/workflow state machine semantics, retry/timeout/cancellation,
checkpoint/recovery invariants, governance disposition handling) is preserved and
consistent with the established runtime; this phase did not redesign it.
