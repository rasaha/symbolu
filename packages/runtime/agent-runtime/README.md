# Ugence Agent Runtime (`ugence-agent-runtime`)

A **domain-neutral execution-coordination kernel** for agent and workflow execution.

> **Scope note.** This is a *newly created coordination kernel*, not a relocation of the
> legacy `agent_runtime_migration` proposer (which owns planning, reasoning, and memory
> and remains a separate, coexisting package). The kernel intentionally excludes agent
> planning/reasoning/memory. See
> [`docs/AGENT_RUNTIME_POST_MERGE_FIDELITY_AUDIT.md`](docs/AGENT_RUNTIME_POST_MERGE_FIDELITY_AUDIT.md).
>
> **Maturity:** `0.2.0` (canonical execution state), `0.3.0` (**H22-A bounded workflow
> advancement**), and `0.4.0` (**H22-B deterministic multi-workflow coordination**, incl. the
> smooth-weighted-round-robin fairness correction and portfolio-lifecycle freezing) are
> `IMPLEMENTED_AND_CI_VERIFIED` (observed passing the scoped Agent Runtime GitHub Actions
> workflow: package suite, isolated wheel-install verification, platform-freeze, terminology,
> API-stability registry, and safety-case checks all green). The additive `0.5.0` **H22-C durable
> multi-workflow orchestration** layer (durable portfolio checkpoint/recovery, append-only audit
> event store, bounded failure propagation, cooperative cancellation scopes) is
> `IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED` after its final audit corrections and promotes to
> `IMPLEMENTED_AND_CI_VERIFIED` once scoped CI is observed green on its exact final head. Not
> live-verified, pilot-validated, distributed-safe, enforcement-ready, or production-ready.

The kernel drives task and workflow lifecycle, invokes providers/tools, and applies
retry, timeout, cancellation, checkpointing, and durable recovery. Before any
*consequential* transition it constructs an immutable proposal and asks an external,
neutral **governance boundary** whether that exact proposal may proceed — and it obeys
the answer. **With no governance adapter configured, consequential transitions fail
closed.**

> **The runtime coordinates execution. It never creates governance authority, authors
> policy, authorizes actions, or mints execution clearance.**

```
applications / products
        ↓
optional integration adapters (providers, concrete governance)
        ↓
ugence-agent-runtime           ← this package (stdlib-only, neutral)
        ↓
neutral contracts and utilities
```

## What it is / is not

| Owns (coordination) | Does **not** own |
| --- | --- |
| task & workflow lifecycle, step coordination | policy authorship, binding decisions |
| provider/tool invocation interfaces | ActionGate authorization, Action Clearance |
| retry / timeout / cancellation | assertion governance, evidence admissibility |
| checkpoints & durable recovery | GitHub / financial / healthcare specifics |
| runtime events, tracing, correlation | a particular LLM provider or agent framework |
| the neutral governance-integration boundary | one persistence backend, one governance impl |

## Install

```bash
python -m build packages/runtime/agent-runtime
pip install dist/ugence_agent_runtime-0.5.0-py3-none-any.whl
```

The core has **no third-party dependencies** — it is stdlib-only. Importing it is
side-effect free (no sockets, no threads, no credentials, no scheduler, no recovery).

## Quick start

```python
from ugence_agent_runtime.api import (
    create_runtime, AgentRuntimeConfig, WorkflowDefinition, TaskDefinition,
)
from ugence_agent_runtime.providers.interfaces import ToolResult

class EchoProvider:
    provider_id, version = "echo", "1.0.0"
    def execute(self, invocation):
        return ToolResult(provider_id="echo", operation=invocation.operation,
                          ok=True, output=invocation.arguments)

rt = create_runtime(AgentRuntimeConfig())
rt.config.provider_registry.register(EchoProvider())

wf = WorkflowDefinition(workflow_id="hello", tasks=(
    TaskDefinition(task_id="t1", operation="echo", provider_id="echo",
                   arguments={"msg": "hi"}, consequential=False),
))
inst = rt.start_workflow(wf)
print(inst.status.value)            # COMPLETED
```

## Governance boundary

The runtime asks an injected `GovernanceHook` and maps the disposition — never
broadening it:

| Disposition | Runtime behavior |
| --- | --- |
| `CLEAR` | continue — **only if** the result is bound to the exact proposal (fingerprint + reference, not expired); otherwise fail closed |
| `HOLD` | task `WAITING`, workflow `WAITING` (no provider call, no authority) |
| `BLOCK` | task `FAILED`, workflow `FAILED` (no provider call) |
| `ESCALATE` | task `WAITING`, workflow `PAUSED` (external resolution required) |

The **default** hook (`UnconfiguredGovernanceHook`) **fails closed** — it BLOCKs every
consequential transition with reason `GOVERNANCE_NOT_CONFIGURED`. An always-CLEAR hook
(`AllowAllGovernanceHook`) exists only as an explicit, opt-in, documented-unsafe testing
helper and is never a default. Concrete Ugence governance adapters live in **separate,
optional** packages and are never required to import the core.

## Canonical execution state

The runtime is the **canonical owner of execution-trajectory identity**. For each task
it derives an immutable, versioned, integrity-protected `CanonicalExecutionState`
snapshot — workflow/task identity, correlation/causation, agent/plan lineage
*references*, runtime status, the active `TransitionProposal` fingerprint, external
authority *references* governance produced, artifact lineage *references*, and a SHA-256
`state_digest`. It records the trajectory; it never authors policy, mints authority,
selects agents, or duplicates the proposal's action payload. Read it with
`runtime.execution_state(instance_id, task_id)`. See
[`docs/AGENT_RUNTIME_CANONICAL_EXECUTION_STATE.md`](docs/AGENT_RUNTIME_CANONICAL_EXECUTION_STATE.md).

> Agents may hold independent reasoning contexts, but consequential execution has **one**
> canonical authoritative execution state — owned by the runtime, not the agent brain and
> not the authority engine.

## Bounded workflow advancement (H22-A)

`start_workflow` drives a workflow to its next stable stopping condition in one call. To
let a **future** external orchestrator interleave several independent workflows fairly,
`0.3.0` adds an additive, deterministic seam that separates *creating* a workflow from
*draining* it:

```python
a = rt.prepare_workflow(wf_a)          # created + RUNNING, no task advanced yet
b = rt.prepare_workflow(wf_b)

rt.advance_workflow(a.instance_id)     # A: exactly one bounded quantum
rt.advance_workflow(b.instance_id)     # B: exactly one bounded quantum
rt.advance_workflow(a.instance_id)     # A: the next quantum … A/B/A/B, deterministically
```

A **quantum** is *at most one runtime task transition through one stable, checkpointed
boundary*. `advance_workflow` returns a frozen `WorkflowAdvanceOutcome` describing what
happened (`task_id`, `task_status`, `stop_reason`, `execution_state_digest`,
`checkpoint_digest`, `terminal`/`waiting`/`paused`). The
governance→exact-action→provider→transition→checkpoint chain runs **entirely within a
single quantum** — an orchestrator can never observe or preempt a workflow between a
governance `CLEAR` and the provider invocation it cleared. `advance_workflow` never
self-resolves a governance `HOLD`/`ESCALATE`: a `WAITING`/`PAUSED` workflow reports
`REQUIRES_RESUME` until an explicit `resume_workflow`. `start_workflow` is unchanged — it
is now simply `prepare_workflow` followed by repeated bounded advancement.

**H22-A is not full H22.** It provides *only* the bounded-advancement foundation. See
[`docs/AGENT_RUNTIME_H22_READINESS.md`](docs/AGENT_RUNTIME_H22_READINESS.md).

## Deterministic multi-workflow coordination (H22-B)

`0.4.0` adds the coordination layer that decides **which** prepared workflow receives the
next H22-A quantum, and **why** — a deterministic "team lead" over a shared workflow graph,
without any concurrency. It lives in `ugence_agent_runtime.orchestration` and is re-exported
from the curated API.

```python
p = create_portfolio("delivery")
p.register(a.instance_id, runtime=rt, priority=WorkflowPriority.NORMAL)
p.register(b.instance_id, runtime=rt)
p.register(c.instance_id, runtime=rt)
p.add_dependency(c.instance_id, a.instance_id, DependencyType.REQUIRES_SUCCESS)  # C waits on A

sched = create_portfolio_scheduler(rt)
result = sched.step(p)          # one round: classify → order → grant ONE quantum
result.selected_instance_id     # who was chosen
result.selection_reason         # structured "why B not A" (rank/age/depth/credit/seq)
```

A `WorkflowPortfolio` is **orchestration state only** — it references workflows by
`instance_id` and never duplicates runtime-owned workflow/task/execution state. Each
`step` classifies every workflow (`ELIGIBLE`, `WAITING_DEPENDENCY`, `BLOCKED_DEPENDENCY`,
`WAITING_RUNTIME`, `PAUSED`, `TERMINAL`), orders the eligible ones by a single stable key —
`(effective_rank, dependency_depth, -fairness_credit, registration_sequence, instance_id)`
— applies explicit **priority**, bounded cross-tier starvation-prevention **aging**, and
deterministic **smooth weighted round-robin (SWRR) fairness** within a priority tier, then
grants exactly one quantum through the unchanged `advance_workflow` seam. Registration and
dependencies are frozen once scheduling begins.

**Governance stays entirely below H22-B.** The scheduler *selects* a workflow; it never
authorizes its task, never resumes a `HOLD`/`ESCALATE`, and never calls a provider. Every
consequential quantum still crosses fresh governance and exact-action validation inside
`advance_workflow`. H22-B is deterministic *interleaving*, **not** simultaneous execution —
no threads, no shared budget/resource ledger, no compensation (those are H22-D). See
[`docs/AGENT_RUNTIME_H22B_COORDINATION.md`](docs/AGENT_RUNTIME_H22B_COORDINATION.md).

## Durable multi-workflow orchestration (H22-C)

`0.5.0` makes the H22-B coordinator **durable, reconstructable, auditable, and safely
controllable** across crash/restart, failure, and cancellation — **without changing
single-workflow execution truth**.

```python
ctrl = create_portfolio_controller(rt, p, checkpoint_store=InMemoryPortfolioCheckpointStore())
ctrl.step()                       # scheduler round + audit trace + failure observation
ctrl.checkpoint()                 # durable PortfolioCheckpoint (self-recoverable before write)

# … process crash / restart, a NEW runtime sharing the same durable stores …
result = recover_portfolio(store=store, portfolio_id="delivery",
                           runtime=rt2, definitions=defs)   # NO execution occurs
result.requires_continuation      # True — recovery reconstructs, it does not continue
rt2.continue_workflow(iid)        # explicit, bounded continuation (no drain)
```

A `PortfolioCheckpoint` **references** each workflow's runtime checkpoint by digest and
**never copies** it, and never duplicates Canonical Execution State. It persists exactly what
deterministic reconstruction needs — `round`, per-registration `age` / SWRR `fair_credit` /
priority / weight / sequence, dependencies, failure/cancellation state, and the trace anchor —
under a fail-closed SHA-256 digest, and is validated by the recovery validator **before** any
write (the portfolio self-recoverability invariant). `recover_portfolio` is **side-effect free**
(provider = 0, governance = 0, advancement = 0, auto-resume = 0), cross-binds each referenced
runtime checkpoint (without requiring writer runtime-version equality, so upgrades recover),
and requires **explicit continuation**; committed work never reruns and the next consequential
quantum still crosses **fresh** governance. A separate append-only `PortfolioTrace` (logical
sequence, ids/digests only) records *why* the coordinator acted. Failure propagation is bounded
(`ISOLATE_WORKFLOW` default / `FAIL_DEPENDENTS` / `FAIL_PORTFOLIO`) and never reinterprets *why*
a workflow failed; cancellation is cooperative and idempotent (`WORKFLOW_ONLY` /
`DEPENDENT_SUBGRAPH` / `PORTFOLIO_ALL`) via the runtime's own `cancel_workflow`. See
[`docs/AGENT_RUNTIME_H22C_DURABILITY.md`](docs/AGENT_RUNTIME_H22C_DURABILITY.md).

## Documentation

See [`docs/`](docs/) — overview, package boundary, public API, state model, canonical
execution state, provider interface, persistence, recovery, governance integration,
compatibility, security, limitations, and H22 readiness. Machine-readable contracts are
in [`artifacts/`](artifacts/).

## Status

`0.5.0` — adds **H22-C durable multi-workflow orchestration**: a versioned
`PortfolioCheckpoint` (referencing, never copying, the underlying runtime checkpoints, and never
duplicating canonical execution state), a neutral `PortfolioCheckpointStore` + in-memory
reference, **side-effect-free** `recover_portfolio` with explicit continuation and a bounded
`continue_workflow` seam, an append-only `PortfolioTrace`, bounded failure propagation
(`PortfolioFailurePolicy`), and cooperative idempotent cancellation scopes (`CancellationScope`),
tied together by `PortfolioController` (`create_portfolio_controller`). Additive only: no change
to exact-action semantics, governance ownership, canonical execution state, checkpoint digest
semantics, or single-workflow recovery; recovery performs no execution. SWRR `fair_credit`,
aging, registration order, and dependencies survive recovery, so the next scheduler decision is
exactly the uninterrupted one. Final audit corrections make the audit trace durable via an
append-only `PortfolioEventStore` (crash-safe checkpoint/commit-event sequencing), bind the
**full** runtime checkpoint across both the base and canonical-execution-state extension
integrity domains, add semantic failure/cancellation/lifecycle cross-binding after recovery, and
make the recovered failure policy a typed, first-class continuity contract. Maturity
`IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED` (package suite **234 passed, 2 skipped**; isolated
wheel-install verification **PASS** at `0.5.0`; platform-freeze green) — promotes to
`IMPLEMENTED_AND_CI_VERIFIED` once scoped Agent Runtime CI is observed green on the exact new
head. Not production / pilot / distributed / exactly-once / runtime-assurance validated. **True
concurrency, resource/budget coordination, and compensation remain H22-D, not implemented
here.**

`0.4.0` — adds **H22-B deterministic multi-workflow coordination**: a `WorkflowPortfolio`,
a cross-workflow dependency graph, deterministic eligibility classification, and a
`PortfolioScheduler` that grants one H22-A quantum per round using explicit
priority, bounded aging, and deterministic fairness (`create_portfolio` /
`create_portfolio_scheduler` and the `ugence_agent_runtime.orchestration` types). Additive
only: it consumes the unchanged `advance_workflow` seam and makes **no** change to
exact-action fingerprint semantics, governance ownership, canonical execution state,
checkpoint digest semantics, or recovery behavior. Governance stays entirely below it — the
scheduler selects a workflow, it never authorizes its task. H22-B is deterministic
interleaving, **not** simultaneous execution: no concurrency, no shared budget/resource
ledger, no portfolio checkpoint/recovery, no compensation (H22-C/H22-D). Builds on the
H22-A bounded-advancement seam (0.3.0), canonical execution state (0.2.0), and the
governance-safety/exact-action corrections (0.1.1/0.1.2).

Fairness is **smooth weighted round-robin (SWRR)** within a priority tier — provably
proportional to weight, smooth, and starvation-free for every positive weight — and portfolio
topology is frozen once scheduling begins (an empty portfolio stays `CREATED`/mutable).

Maturity: `IMPLEMENTED_AND_CI_VERIFIED` — the scoped Agent Runtime GitHub Actions workflow
has been observed green on the correction head (package suite **178 passed, 2 skipped**;
isolated wheel-install verification **PASS** at `0.4.0`; platform-freeze, terminology,
API-stability registry, and safety-case checks all green). This does not imply production,
pilot, live-environment, distributed, exactly-once, or enforcement validation. **True bounded
concurrency, resource/budget coordination, portfolio durability, and compensation remain
later phases (H22-C / H22-D), not implemented here.**

`0.3.0` — added the **H22-A bounded workflow advancement** seam (`prepare_workflow` +
`advance_workflow` returning `WorkflowAdvanceOutcome`/`WorkflowAdvanceStop`).
`IMPLEMENTED_AND_CI_VERIFIED`.
