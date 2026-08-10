# Governed External Actions & Resource State (H20)

Adds a **safe, durable execution boundary for external side effects** on top of
the H19 human-governed, H18-durable workflow runtime. The runtime now cleanly
separates five things that were previously conflated:

```
propose  →  authorize  →  execute  →  observe  →  commit
```

An authorized *goal* does not automatically authorize every external side effect
inside it. **Every external action crosses its own governed execution boundary**:
its intent is recorded, its actor authority and policy (ActionGate) are checked,
resource preconditions are validated immediately before mutation, execution is
duplicate-suppressed by a stable idempotency key, and the result is durably
recorded *before* the goal may complete. An action interrupted after the adapter
ran but before its result was durably obtained becomes `UNKNOWN` — never silently
replayed — and is resolved by reconciliation.

```
Agent proposes external action
  → intent recorded → authority + ActionGate validated
  → resource preconditions checked → idempotency reserved
  → adapter invoked → result durably recorded → workflow continues
```

> **Scope statement.** H20 adds governed, durable external-action execution with
> resource preconditions, durable duplicate suppression, and unknown-outcome
> reconciliation, behind deterministic in-memory adapters. It is **not** a
> distributed transaction coordinator, does **not** provide universal
> exactly-once execution across arbitrary external systems, does **not**
> automatically roll back irreversible operations, and is **not** production
> external-system fault tolerance. Duplicate suppression is durable *within the
> governed runtime and cooperating adapters*. Real cloud/database integrations,
> distributed locks, and queues are out of scope; the reference adapters are
> in-memory and deterministic.

H20 owns **execution-state control** — lifecycle, preconditions, idempotency,
optimistic concurrency, durable action records, unknown-outcome reconciliation,
and compensation linkage. It does **not** author policy. It does not modify
H10–H19, the governance layer, authorization, TAP, tool execution, or the model
providers — it composes on their public APIs and persists its state through H14
memory so H18 checkpoints and restores it.

---

## External resource model

An **`ExternalResourceRef`** is an immutable, stable reference. Identity is the
`(provider, tenant_id, namespace, resource_id)` tuple — exposed as `.key` — and
is deliberately **independent of mutable display names, attributes, and version**
so it survives checkpoint restoration.

A **`ResourceSnapshot`** is an observed, immutable point-in-time view:
`observed_version`, `observed_state`, a `content_digest`, and observation
provenance. Every external write declares the version (and/or precondition
state) it expects; a mismatch fails closed with `RESOURCE_VERSION_CONFLICT` or
`PRECONDITION_FAILED`. **The runtime never silently overwrites newer external
state.**

---

## Action intent

An **`ExternalActionIntent`** is an immutable *proposal* — what the runtime
proposes to do, not proof it was authorized or executed. It carries the target
resource, operation, structured parameters, `expected_resource_version`,
preconditions, `authority_requirements`, policy context, `idempotency_key`,
`reversibility`, and optional `compensation` metadata. Its `parameter_digest()`
is a canonical SHA-256 over the *material* action `(operation, parameters,
resource key, expected version)` — this is what a human approval binds to.

---

## Action lifecycle

Append-only, reconstructable:

```
PROPOSED → VALIDATING → AUTHORIZED → READY_TO_EXECUTE → EXECUTING
        → SUCCEEDED | FAILED | DENIED | CONFLICTED | UNKNOWN
        → RECONCILED | COMPENSATED
```

- `DENIED` — governance/authority refused execution.
- `CONFLICTED` — resource preconditions no longer hold.
- `UNKNOWN` — execution may have occurred but no trustworthy result was durably
  obtained.
- `RECONCILED` — resolves an `UNKNOWN` action using external evidence.
- `COMPENSATED` — a separate compensating action ran; **history is never
  rewritten**, only appended.

---

## Governed execution pipeline (`ExternalActionExecutor.execute`)

The order is deterministic; **no adapter call occurs before governance,
authority, approval, precondition, and idempotency checks complete**:

1. **Load/record intent.** A terminal action re-submitted is a duplicate; an
   `UNKNOWN` action re-submitted is refused pending reconciliation.
2. **Schema / adapter support** — unsupported operation → `OPERATION_UNSUPPORTED`.
3. **Actor execution authority** (subset check) — *before any state change*;
   failure → `AUTHORITY_DENIED`, no mutation.
4. **Approval binding** — an approval only counts for the exact
   `parameter_digest`; a materially changed action → `APPROVAL_BINDING_VIOLATION`.
5. **ActionGate** (authoritative policy) — `DENY` → `GATE_DENIED`;
   `REQUIRE_HUMAN_REVIEW` → workflow waits for an `ActionApproval`;
   `REQUIRE_ADDITIONAL_EVIDENCE` → waits for evidence; `ALLOW` /
   `ALLOW_WITH_CONSTRAINTS` → proceed.
6. **Resource read + version/precondition checks** — immediately pre-mutation;
   mismatch → `RESOURCE_VERSION_CONFLICT` / `PRECONDITION_FAILED`.
7. **Idempotency reservation** — a key already executed by another action →
   `DUPLICATE_ACTION_SUPPRESSED`; otherwise reserve, mark `EXECUTING`, and
   **checkpoint the reservation** (so process loss here restores to `UNKNOWN`).
8. **Adapter invocation** — the actual external side effect.
9. **Durable result** — record the result and post-snapshot into H14 memory
   *before* the goal may complete, then resume the workflow via the unchanged
   H18 `deliver`.

---

## ActionGate boundary

`ActionGate` is a **strategy interface** evaluated at the real external-execution
boundary over the actor, operation, resource, parameters, sensitivity, workflow
& policy context, approval evidence, and current resource state. Its outcomes —
`ALLOW`, `ALLOW_WITH_CONSTRAINTS`, `DENY`, `REQUIRE_HUMAN_REVIEW`,
`REQUIRE_ADDITIONAL_EVIDENCE` — are **authoritative**: H20 treats the gate's
verdict as the decision on *whether and under what constraints* an action may
proceed. **H20 does not author policy** — supply a governance-backed gate in
production. The shipped `RuleBasedActionGate` and `AllowAllActionGate` are
deterministic reference adapters for tests and examples.

---

## Authority & human approval

Actor execution authority uses the same subset-check discipline as H16/H19: an
actor may execute only if it holds every token in the intent's
`authority_requirements`. When the gate returns `REQUIRE_HUMAN_REVIEW`, the
workflow waits; a human submits an **`ActionApproval`** bound to the action's
current `parameter_digest`. The approver's authority is validated with the H19
`HumanParticipant` model, and the approval **cannot** authorize a materially
different action — changing any parameter invalidates the prior approval.

---

## Idempotency & the exactly-once claim boundary

Every action carries a stable `idempotency_key`. The executor persists
`key → status → external request/result refs`. A **first** execution runs the
adapter; a **repeat** (same key) yields `DUPLICATE_ACTION_SUPPRESSED` and does
**not** re-invoke the adapter. Idempotency state lives in H14 memory, so it is
checkpointed and **survives restart** — a resubmission after process loss is
still suppressed.

Precise terminology: H20 provides **durable duplicate suppression within the
governed runtime and cooperating adapters** — not universal exactly-once
execution across arbitrary external systems.

---

## Resource concurrency & leases

Optimistic concurrency is the primary mechanism: `expected_resource_version` must
equal the observed version immediately before mutation, else
`RESOURCE_VERSION_CONFLICT`. A `ResourceLease` models bounded execution
coordination metadata only — **it is not a distributed lock and never overrides
the external resource-version check.**

---

## Durable execution record

An **`ExternalActionRecord`** captures the whole lifecycle: intent, append-only
`lifecycle_history`, gate decision, approval references, pre/post resource
snapshots, adapter invocation reference, result payload, error info, idempotency
status, reconciliation status, compensation references, logical sequences, and an
integrity digest. Records are stored in H14 memory so **H18 checkpoints and
restores them**. A workflow may not mark an external-action goal `COMPLETED`
unless its result is durably recorded.

---

## Adapter contract

`ExternalResourceAdapter` is strategy-agnostic: `read`, `supports`, `execute`,
`query_status`, `reconcile`, `describe_compensation`. Adapters return **structured
`AdapterResult`s** — never raw provider responses or arbitrary exceptions. Two
deterministic references ship: `InMemoryResourceAdapter` (optimistic-versioned
store with adapter-side idempotency) and `ScriptedResourceAdapter` (fully
scripted results + an explicit external-evidence channel for reconciliation).

---

## Unknown outcomes & reconciliation

An action can be interrupted after the external system received the request but
before the runtime durably recorded the result. This is represented explicitly as
`UNKNOWN`. For an `UNKNOWN` action the runtime does **not** auto-repeat a
non-idempotent action, does **not** mark the goal succeeded or failed without
evidence, **blocks** the affected subtree, and requires reconciliation.

`ActionReconciler.reconcile` consults durable external evidence (via the
adapter's explicit reconcile channel) and yields `CONFIRMED_SUCCEEDED` (the
workflow continues **without re-executing**), `CONFIRMED_FAILED` (only the
affected subtree follows failure behaviour), `STILL_UNKNOWN`, or
`MANUAL_REVIEW_REQUIRED`.

---

## Compensation

Compensation is modeled as a **new governed action**, never a mutation or erasure
of the original. A `CompensationPlan` describes the compensating operation,
required authority/approval, applicability conditions, and known limitations. A
compensating action passes ActionGate, receives its own idempotency key, and is
linked back to the original — which transitions to `COMPENSATED` (append-only)
only after the compensating action succeeds. **H20 does not claim rollback
semantics for inherently irreversible operations.**

---

## Recovery protocol

The durable execution protocol — intent → governance decision → preconditions →
idempotency reservation → `EXECUTING` → adapter → result → snapshot → commit —
has deterministic recovery rules, exercised by `ActionFaultInjector` at every
boundary:

- **before adapter invocation** — safe to retry.
- **after adapter, no durable result** — `UNKNOWN` (reconcile, never blind
  replay).
- **after durable result** — do not repeat.
- **after result save, before workflow update** — continue the commit without
  re-executing.

`ExternalActionExecutor.restore` restores the H18 workflow and re-hydrates action
records; any action durably left in `EXECUTING` becomes `UNKNOWN` with its goal
blocked, awaiting reconciliation.

---

## Interaction with H13–H19

- **H13 assumptions** — a successful action's resume event carries
  `assumption_effects` from the durable observation, applied before dependent
  execution proceeds.
- **H14 memory** — action records, idempotency state, resource snapshots, and
  results are ordinary governed writes with provenance and version continuity.
- **H15 hierarchy** — a failed/conflicted/unknown action affects only the
  smallest dependent subtree; `replan_action_goal` uses `replace_leaf`.
- **H16 coordination** — the coordinator selects the worker; H20 independently
  validates *execution* authority.
- **H17 workflows** — external-action goals suspend on wait conditions and resume
  via the unchanged event machinery.
- **H18 durability** — all records, idempotency, reconciliation, and resource
  references are persisted and restored through the unchanged durable engine.
- **H19 human governance** — a `REQUIRE_HUMAN_REVIEW` gate is satisfied by an
  `ActionApproval` bound to the exact action intent, validated with the H19
  participant model.

---

## Known limitations

- Local and deterministic; no distributed transactions, universal exactly-once,
  automatic rollback of arbitrary operations, or production external-system fault
  tolerance.
- Duplicate suppression requires cooperating adapters (idempotency-key aware).
- Reconciliation depends on the adapter exposing durable external evidence.
- Reference adapters are in-memory; real integrations are out of scope.

---

## Quickstart

```python
from agentic.agentic_framework import (
    WorkingMemory, RunBudget, RunBudgetLimits,
    AgentProfile, CapabilityRegistry, ScriptedWorker, WorkerResult,
    Goal, StaticDecomposer, WaitCondition, WaitKind, InMemoryCheckpointStore,
    ExternalResourceRef, ExternalActionIntent, ExternalActionExecutor,
    RuleBasedActionGate, InMemoryResourceAdapter, ActionAuthorityValidator,
    ExecutionResultCode,
)

registry = CapabilityRegistry()
registry.register(AgentProfile("bot", capabilities=frozenset({"do"}), trust_level=5),
                  ScriptedWorker(lambda c, m: WorkerResult(success=True,
                      outputs={k: "ok" for k in c.expected_outputs})))

ref = ExternalResourceRef("prod-api", resource_type="deployment", sensitivity="high")
adapter = InMemoryResourceAdapter(); adapter.seed(ref, 5, {})

ex = ExternalActionExecutor(registry, InMemoryCheckpointStore(), RuleBasedActionGate(),
                            default_adapter=adapter,
                            authority_validator=ActionAuthorityValidator({"bot": frozenset({"deploy"})}))
plan = StaticDecomposer().decompose("m", [
    Goal("deploy", "deploy", required_capabilities=frozenset({"do"}),
         expected_outputs=("rel",), priority=1)])
gate = WaitCondition("w", "deploy", kind=WaitKind.WAIT_FOR_EVENT, event_type="done", match=(("env", "prod"),))
wf = ex.create_workflow("wf", plan, WorkingMemory(),
                        run_budget=RunBudget(RunBudgetLimits()), wait_conditions=[gate])

intent = ExternalActionIntent("a1", "wf", "deploy", "bot", "deploy", ref, "set:version",
                              parameters=(("value", "v2"),), expected_resource_version=5,
                              authority_requirements=frozenset({"deploy"}), idempotency_key="idem-1")
res = ex.execute(wf, intent, timestamp=1)
print(res.code)        # ACTION_EXECUTED
print(wf.status)       # COMPLETED
```

See [`examples/governed_external_actions.py`](../../examples/governed_external_actions.py)
— authorized execution, authority/gate denial, version conflict, duplicate
suppression, human-review approval binding, unknown-outcome reconciliation, and
compensation, with deterministic adapters and no API key.
