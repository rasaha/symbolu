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

`IMPLEMENTED_AND_OFFLINE_VERIFIED` (plus a scoped CI job). **Not** live-verified,
pilot-validated, enforcement-ready, or production-ready.
