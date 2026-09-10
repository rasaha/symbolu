# Agent Runtime — Limitations

This document records what the runtime deliberately does **not** do, as future
capabilities rather than things built to justify the package. **Corrected 2026-09-08:**
it previously opened by describing the release as "a packaging, boundary-hardening, and
dependency-cleanup phase", which described 0.1.x and had not been revised since. The
package is now `0.7.0` and carries the full H22 ladder through H22-D (0.6.0) plus CM-TA1
provider-attempt telemetry (0.7.0). The exclusions below were re-checked against that
release and stand.

## Not implemented (by design)

- **Distributed multi-workflow orchestration.** **Corrected 2026-09-08:** this entry
  previously excluded multi-workflow orchestration (H22) outright, including
  cross-workflow dependency graphs, cross-workflow state aggregation and compensation
  coordination. The H22 ladder shipped: H22-A bounded advancement (0.3.0), H22-B
  deterministic coordination (0.4.0), H22-C durable orchestration (0.5.0) and H22-D
  bounded concurrency, resource claims, shared budget and compensation coordination
  (0.6.0). What stays excluded is the **distributed** form — no distributed scheduling
  across processes or machines, no distributed locking, no parent/child workflow
  relationships, and no cross-workflow governance authority. Dependencies are limited to
  the two types the runtime can represent durably from committed state
  (`REQUIRES_COMPLETION`, `REQUIRES_SUCCESS`); `REQUIRES_OUTPUT` / `REQUIRES_MILESTONE` /
  `REQUIRES_REVIEW_DECISION` remain unbuilt. See
  [`AGENT_RUNTIME_H22_READINESS.md`](AGENT_RUNTIME_H22_READINESS.md).
- **Agent planning / reasoning / memory.** The neutral coordination core does not
  include a planner, reflector, or memory system. Those remain agent-behavior concerns
  outside this package.
- **LLM routing / provider specifics.** No LLM client, no model routing, no vendor
  provider. Providers are neutral and supplied externally.
- **New provider kinds.** No new `ProviderKind` is introduced.
- **Distributed / cluster execution.** Still out of scope: no distributed cluster
  scheduling, no distributed locking, no cross-process/cross-machine execution, and no
  exactly-once external effects. Resource coordination is portfolio-local.
- **In-process concurrency (H22-D, 0.6.0).** The single-workflow reference engine still
  executes one task at a time per workflow. **H22-D** adds bounded, in-process concurrency
  *across* workflows: the `ConcurrentPortfolioExecutor` runs several independent H22-A quanta
  at once on a thread-pool backend, capped by
  `min(ConcurrencyPolicy.max_concurrent_quanta, AgentRuntimeConfig.max_concurrent_tasks)` — it
  never exceeds the runtime's configured in-flight-task ceiling. **Injected dependency
  thread-safety is a deployment contract, not a guarantee:** when the thread-pool backend is
  selected, the injected providers, governance hooks, persistence/event stores, and event sinks
  are invoked concurrently, so they must satisfy the concurrency/reentrancy contract appropriate
  to the deployment. The package does **not** claim that arbitrary third-party providers, hooks,
  or stores are automatically thread-safe; the synchronous backend (the default) runs quanta one
  at a time and imposes no such contract.
- **Durable persistence backend.** Only in-memory reference stores ship; durable
  backends are supplied externally behind the persistence interfaces.
- **Concrete governance adapters.** The core ships only the neutral boundary and a
  fail-closed default hook (and an explicit unsafe test hook); concrete
  TAP/ActionGate/Action Clearance/Code Governance/StoryGraph
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

## Relationship to the legacy runtime

This package is a **newly created coordination kernel**, not a behavior-preserving
relocation of the legacy `agent_runtime_migration` proposer. The proposer's
planning/reasoning/memory/reflection are **intentionally excluded** (see the fidelity
matrix). The kernel's own semantics (task/workflow state machine, retry/timeout/
cancellation, checkpoint/recovery invariants, and — as of 0.1.1 — fail-closed default
governance and exact-action binding) are internally consistent and covered by the
package suite, but they are **not** claimed to reproduce the legacy loop's behavior.

## Maturity

`IMPLEMENTED_AND_CI_VERIFIED` — the scoped `agent-runtime-ci` workflow was observed green
on the default branch at `26da5f3c`
([run 34040504074](https://github.com/rasaha/symbolu/actions/runs/34040504074),
2026-09-06), all three jobs success, on a head carrying `0.7.0`. **Corrected 2026-09-08:**
this line previously read `IMPLEMENTED_AND_OFFLINE_VERIFIED` (plus a scoped CI job), which
lagged the README and the CHANGELOG. **Not** live-verified, pilot-validated,
distributed-safe, cluster-safe, exactly-once, enforcement-ready, or production-ready.
