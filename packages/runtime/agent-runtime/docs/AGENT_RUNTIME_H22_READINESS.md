# Agent Runtime — H22 Readiness

This document describes the stable, domain-neutral base on which H22 (Multi-Workflow
Orchestration) is built **without importing application internals**, and records the H22
phases delivered so far — **H22-A bounded workflow advancement** (0.3.0) and **H22-B
deterministic multi-workflow coordination** (0.4.0). **Full H22 is not implemented here:**
H22-C (portfolio durability / trace / failure propagation / cancellation) and H22-D (true
concurrency / resources / budget / compensation) remain future phases. The dedicated H22-B
document is [`AGENT_RUNTIME_H22B_COORDINATION.md`](AGENT_RUNTIME_H22B_COORDINATION.md).

> **Gate (satisfied).** The post-merge corrections that had to precede any H22 work —
> fail-closed default governance (0.1.1), exact-action proposal binding (0.1.2), honest
> compatibility, and the scoped CI job — are validated and `IMPLEMENTED_AND_CI_VERIFIED`
> as of the canonical-execution-state release (0.2.0). See
> `AGENT_RUNTIME_POST_MERGE_FIDELITY_AUDIT.md`. On that base, **H22-A** (0.3.0) adds only
> the bounded-advancement seam below; it is `IMPLEMENTED_AND_CI_VERIFIED` — the scoped
> Agent Runtime GitHub Actions workflow has been observed passing on the change. Not
> live-verified.

## Ordering

```
Independent Agent Runtime package   ← delivered (0.1.0)
        ↓
Canonical Execution State           ← delivered (0.2.0)
        ↓
H22-A Bounded Workflow Advancement  ← delivered (0.3.0) — foundation only
        ↓
H22-B Deterministic Coordination    ← delivered (0.4.0) — portfolio/deps/priority/fairness/aging
        ↓
H22-C Portfolio durability / trace / failure propagation / cancellation   ← future
        ↓
H22-D True concurrency / resources / budget / compensation                ← future
        ↓
Runtime-to-Governance integration validation
        ↓
Agentic product workflows
```

## H22-A — Bounded Workflow Advancement (delivered, 0.3.0)

H22-A is the **first architectural gate** of H22 and the only part delivered here. It
establishes the compositional seam a future portfolio scheduler needs, and nothing more.

**What H22-A enables.** An external orchestrator can now create a workflow without
draining it (`prepare_workflow`) and advance it **one bounded quantum at a time**
(`advance_workflow`), observing exactly what happened via `WorkflowAdvanceOutcome` and
stopping at a stable, checkpointed boundary. Because each quantum is a *single* runtime
task transition through *one* stable boundary, an orchestrator can fairly interleave
independent workflows deterministically:

```
Round 1                    Round 2
advance(A) → one quantum    A blocked by (future) dependency
advance(B) → one quantum    advance(B) → one quantum
advance(C) → one quantum    advance(C) → one quantum
(portfolio checkpoint)      (portfolio checkpoint)
```

**A quantum** is *at most one runtime task transition through one stable, checkpointed
boundary*: one governed task execution (governance → exact-action check → provider →
transition → checkpoint, indivisibly), OR one finalization (`→ COMPLETED` / `→ WAITING`),
OR one cancellation. The governance→provider chain runs **entirely inside** one quantum,
so the scheduler can never preempt between a governance `CLEAR` and the provider
invocation it cleared, and `advance_workflow` never self-resolves a `HOLD`/`ESCALATE`
(those still require an explicit `resume_workflow`).

**What H22-A does NOT provide.** H22-A is **not** full H22. It contains no portfolio, no
cross-workflow dependency graph, no priority/fairness/aging, no shared budget or resource
ledger, no compensation coordination, no parent/child workflows, no peer-to-peer agent
messaging, and no concurrency (no threads/asyncio/pools). It decides nothing about *which*
workflow advances — it only makes bounded, observable, resumable advancement *possible*.

```
Future H22 portfolio scheduler
        │  decides WHICH workflow may advance, in WHAT order, under budget/fairness
        ▼
runtime.advance_workflow(A) ─┐
runtime.advance_workflow(B) ─┼─ H22-A seam (this release): HOW one workflow executes
runtime.advance_workflow(C) ─┘
        ▼
existing Agent Runtime governance / exact-action / execution / checkpoint boundary
        ▼
governance decides WHETHER each consequential transition is permitted
```

`H22-A != full H22.` H22-A is only the bounded-advancement foundation.

## H22-B — Deterministic Multi-Workflow Coordination (delivered, 0.4.0)

H22-B is the coordination layer that consumes the H22-A seam and answers *which* prepared
workflow receives the next quantum, and *why*. It adds a `WorkflowPortfolio` (orchestration
state only — it references workflows by `instance_id` and duplicates no runtime-owned
state), a cross-workflow dependency graph (`REQUIRES_COMPLETION` / `REQUIRES_SUCCESS`, with
cycles/self-edges/unknown references rejected), deterministic eligibility classification,
and a `PortfolioScheduler` that grants one quantum per round by the stable key
`(effective_rank, dependency_depth, -fairness_deficit, registration_sequence, instance_id)`
with explicit priority, bounded aging, and deterministic fairness. It imports only the
runtime's public contracts (orchestration → runtime; the engine never imports
orchestration). See [`AGENT_RUNTIME_H22B_COORDINATION.md`](AGENT_RUNTIME_H22B_COORDINATION.md).

**Governance stays entirely below H22-B.** The scheduler selects a workflow; it never
authorizes its task, resumes a `HOLD`/`ESCALATE`, or calls a provider. Every consequential
quantum still crosses fresh governance and exact-action validation inside `advance_workflow`.
H22-B is deterministic interleaving, **not** simultaneous execution.

H22-B is `IMPLEMENTED_AND_CI_VERIFIED` — the scoped `agent-runtime-ci` GitHub Actions
workflow (package suite, isolated wheel-install verification, platform-freeze, terminology,
API-stability registry, and safety-case checks) has been observed passing on the change. Not
live-verified, distributed-safe, or exactly-once.

## What later H22 phases build on this base (not now)

- **H22-C:** portfolio checkpoint/recovery, portfolio trace, failure propagation policy,
  cancellation scopes, richer dependency types (output/milestone/review) once the runtime
  exposes a durable public representation for them;
- **H22-D:** true bounded concurrency, resource coordination/ledger, shared budget
  coordination, and compensation coordination.

**None of the above is implemented in this phase.**

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
