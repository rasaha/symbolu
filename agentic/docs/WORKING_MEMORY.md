# Governed Working Memory & State Continuity (H14)

Run-scoped, governed working memory that lets an autonomous workflow retain,
update, retrieve, and expire execution state across iterations, replanning,
and agent handoffs. **State continuity, not long-term learning** — memory
exists only for the lifetime of one workflow.

```
Goal → Working Memory → Plan → Observation → Memory Update
    → Validity → Decision → Execution
```

Memory becomes the shared execution context. Records are **append-only** and
**versioned** — an update never overwrites, it creates a new version and
supersedes the prior one, so history is never lost. Retrieval is fully
**deterministic**. Excluded by design: vector databases, semantic search,
embeddings, long-term memory, learning/RL, user profiling, external storage.

This layer is **additive and planning-strategy agnostic**. It does not modify
RunBudget, replanning, plan validity, governance, authorization, ActionGate,
TAP, routing, tool execution, or LLM providers. It integrates through the
observation-builder seam `ReplanningRunner` already exposes
(`MemoryAwareObservationBuilder`) and links to H13 assumptions through their
public API only (`MemoryAssumptionBridge`).

---

## Working memory lifecycle

A **`WorkingMemory`** is created once per workflow and shared by reference —
sequential agents use the same instance, no copies. Its governed operations
are all deterministic and traceable:

| Operation | Effect |
|-----------|--------|
| `create(key, value, ...)` | version 1 (or a new version if the key exists) |
| `update(key, value, ...)` | a **new** version; the prior ACTIVE version is superseded |
| `retrieve(key, consuming_step=, now=)` | the current ACTIVE version (deterministic), recording consumption |
| `invalidate(key, ...)` | ACTIVE version(s) → `INVALIDATED` |
| `expire(key)` / `expire_due(now)` / `expire_on_step(step_id)` | ACTIVE → `EXPIRED` |
| `archive(key)` | ACTIVE → `ARCHIVED` |

Record states: `ACTIVE` (selectable) · `SUPERSEDED` (replaced by a newer
version) · `EXPIRED` · `INVALIDATED` · `ARCHIVED`. Only `ACTIVE` records are
ever selected.

---

## Versioning model

Each `MemoryRecord` is one **immutable** versioned snapshot:

```
customer_profile v1 (SUPERSEDED)  ← history, reconstructable
customer_profile v2 (SUPERSEDED)  ← history, reconstructable
customer_profile v3 (ACTIVE)      ← current
```

`value` and `version` are immutable. Only `status` transitions over the
version's lifecycle (append-only `status_history`), and `consuming_steps`
grows as the record is read. A new value is always a new version — never an
overwrite. `records(key)` returns all versions; `versions(key)` returns
lightweight `MemoryVersion` views.

---

## Retrieval algorithm (deterministic)

`DeterministicSelectionPolicy` selects among a key's versions in a fixed
priority order:

1. **ACTIVE** records only (expired / superseded / invalidated / archived are
   never selectable);
2. highest **version**;
3. highest **confidence**;
4. most recent **timestamp** (then `record_id` as a final tiebreak).

No probabilistic retrieval. `retrieve(...)` first TTL-expires any ACTIVE
record whose window has lapsed (so it is never selected), then applies the
policy and records the consuming step.

---

## Expiration policy

`ExpirationPolicy(kind=...)` supports deterministic expiration:

- `TTL` — expires once `now - created_at >= ttl`;
- `ON_STEP` — expires when a named step completes (`expire_on_step`);
- `ON_ASSUMPTION` — expires when a named assumption fails
  (`expire_on_assumption`);
- `WORKFLOW_END` / `EXPLICIT` — driven by the caller.

Expired records are never retrieved.

---

## Step memory access

Plan steps declare their memory needs via `PlanStep.metadata["memory"]` (so
`PlanStep`/`Plan` are used unmodified):

```python
PlanStep("risk", "risk assessment", "assess",
         metadata={"memory": {"requires": ["customer_profile"],
                              "produces": ["risk_score"],
                              "optional": ["prior_history"]}})
```

`MemoryAccess.from_step(step)` reads these declarations.

---

## Runtime integration

`MemoryAwareObservationBuilder(memory, base_builder)` wraps any observation
builder. Per step it:

1. reads the step's **required + optional** memory (recording consumption),
   attaching the read record ids to the observation;
2. delegates to the base builder for the observation itself;
3. writes the values the step **produced** as new memory versions;
4. applies any memory **invalidations** the observation reported;
5. **expires** records whose policy fires on this step's completion.

Being an `ObservationBuilder`, it drops straight into `ReplanningRunner`
(H12) or `build_assumption_aware_runner` (H13) — no runner changes.

A **`MemoryObservation`** (a `PlanObservation` subclass) carries the effects:
`memory_writes: List[MemoryWrite]`, `memory_invalidations: List[str]`, and a
`memory_reads` field the builder fills in.

---

## Interaction with replanning

Replanning consumes the current working memory and does **not** clear it. On
a revision, memory produced before the change survives intact (it lives in
`WorkingMemory`, independent of the plan's `future`/`history` lists). A
memory-conditioned replanner strategy can read the store to choose its
revision — the same observation can yield different revised plans depending
on stored state.

---

## Interaction with assumptions (H13)

`MemoryAssumptionBridge(memory, assumption_context, links={key: [assumption_ids]})`
registers a listener on the memory. When a linked record is invalidated (or
expired), the bridge transitions the dependent assumptions to `INVALID` via
their own append-only `transition()` — **H13's public API**. H13's existing
plan-validity evaluation picks the change up on its next `decide()`, so a
corrupted dataset can invalidate `dataset_valid` and drive an
`PLAN_IMPOSSIBLE` / abort. The H13 architecture is not modified. Both the
memory version history and the assumption transition history are preserved.

---

## Interaction with RunBudget (H11)

All memory operations are deterministic and add nothing to the budget. The
memory-aware builder is passed to a runner that already carries the shared
`RunBudget`, so every executed step consumes from the same cumulative budget
and no new budget objects are created. If a future implementation used
model-assisted retrieval it would consume the same budget via the budgeted
adapter.

---

## Trace reconstruction

Every operation appends a `MemoryOperation` to `memory.trace`
(`CREATE / UPDATE / SUPERSEDE / READ / INVALIDATE / EXPIRE / ARCHIVE`), with
the key, version, step, and timestamp. `memory.snapshot()` reconstructs every
key with all its versions and the full operation log.

Because the builder attaches `memory_reads` to each observation, **every
runtime decision identifies the memory records that influenced it** — the H12
/ H13 decision trace stores the observation dict, which now includes the read
record ids. `format_working_memory(memory)` and `format_memory_trace(memory)`
render the state and lifecycle.

---

## Deterministic guarantees

- Selection, expiration evaluation, and versioning are pure functions of the
  stored records and the supplied timestamps (iteration indices).
- Identical workflows produce identical memory histories and operation logs.
- No wall-clock time, randomness, or probabilistic ranking is used.

---

## Quickstart

```python
from agentic.agentic_framework import (
    build_agent, MockLLMAdapter, Plan, PlanStep, ObservationStatus,
    ScriptedObservationBuilder, ReplanningRunner,
    WorkingMemory, MemoryObservation, MemoryWrite, MemoryAwareObservationBuilder,
)

memory = WorkingMemory()
plan = Plan.from_steps("assess", [
    PlanStep("collect", "collect", "do", metadata={"memory": {"produces": ["profile"]}}),
    PlanStep("risk", "risk", "do", metadata={"memory": {"requires": ["profile"]}}),
])

builder = MemoryAwareObservationBuilder(memory, ScriptedObservationBuilder([
    MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=0.5,
                      memory_writes=[MemoryWrite("profile", {"tier": "premium"})]),
    MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
]))

ReplanningRunner(build_agent(adapter=MockLLMAdapter(default_response="ok"),
                             use_llm_for_decomposition=False, max_revisions=0),
                 observation_builder=builder, max_iterations=6).run(plan.goal, plan)

print(memory.peek("profile").value)              # {'tier': 'premium'}
print(memory.records("profile")[0].consuming_steps)  # ['risk']
```

See [`examples/working_memory_continuity.py`](../../examples/working_memory_continuity.py)
— proves state-driven outcomes, versioning, cross-agent sharing, and the
memory→assumption bridge, with mock adapters and no API key.
