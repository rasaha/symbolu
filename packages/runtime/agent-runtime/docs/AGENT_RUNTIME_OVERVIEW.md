# Agent Runtime — Overview

The **Ugence Agent Runtime** is a domain-neutral **execution-coordination kernel** for
agents and workflows. It is packaged as an independent Python distribution
(`ugence-agent-runtime`, namespace `ugence_agent_runtime`) that builds, installs, and
runs without importing the monorepo application layer.

> It is a **newly created kernel**, not a relocation of the legacy
> `agent_runtime_migration` proposer (which owns planning/reasoning/memory and coexists
> separately). Maturity: `IMPLEMENTED_AND_OFFLINE_VERIFIED`. See
> `AGENT_RUNTIME_POST_MERGE_FIDELITY_AUDIT.md`.

## What the runtime does

The runtime turns a **workflow definition** (a dependency graph of tasks) into a
coordinated, resumable, observable execution:

1. It advances tasks in deterministic dependency order.
2. For each *consequential* task it consults an external **governance boundary** and
   obeys the returned disposition.
3. When cleared, it invokes the task's **provider** with retry and timeout accounting.
4. It **checkpoints** coordination state and can **recover** it after a restart —
   without making any external call during recovery.
5. It emits a deterministic, replayable **event stream**.

## What the runtime is not

The runtime **coordinates execution**; it does **not**:

- create governance authority or author policy;
- authorize actions, make ActionGate decisions, or mint Action Clearance;
- own assertion governance, evidence admissibility, or DecisionRecord authority;
- embed any product, GitHub, financial, healthcare, LLM-provider, agent-framework,
  robotics, persistence-backend, or governance-implementation specifics.

Those responsibilities live **outside** this package, behind neutral interfaces.

## Architecture

```
Agent Runtime proposes/reaches a consequential transition
        ↓
governance integration boundary (neutral GovernanceHook)
        ↓
governance returns CLEAR / HOLD / BLOCK / ESCALATE
        ↓
Agent Runtime continues, waits, terminates, or pauses
```

The runtime executes coordination. Governance determines permission. Providers
execute operations. Each concern is a separate, injected boundary.

## Design invariants

- **Stdlib-only core.** No third-party runtime dependency.
- **Side-effect-free import.** `import ugence_agent_runtime` opens nothing, starts
  nothing, and loads no credentials.
- **Deterministic.** No wall clock or randomness in the core control flow; the clock
  and id generator are injected.
- **Fail closed.** An absent or unrecognized governance result never becomes CLEAR;
  a corrupt checkpoint is rejected.
- **Neutral vocabulary.** Governance dispositions and runtime statuses are preserved,
  never reinterpreted.

## Where it fits in the roadmap

```
Independent Agent Runtime package   ← this release (0.1.0)
        ↓
H22 Multi-Workflow Orchestration    ← later feature phase (NOT here)
        ↓
Runtime-to-Governance integration validation
        ↓
Agentic product workflows
```

See [`AGENT_RUNTIME_H22_READINESS.md`](AGENT_RUNTIME_H22_READINESS.md) for what a
future orchestration phase may build on top of this base.
