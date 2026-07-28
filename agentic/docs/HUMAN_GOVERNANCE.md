# Human Governance, Interactive Approval & Decision Authority (H19)

Makes **human participants first-class governed runtime actors**. Reviews,
approvals, rejections, change-requests, delegations, and escalations become
explicit, authority-scoped, append-only runtime objects — not out-of-band side
effects. A workflow suspends on a review-gated wait condition; a named human
issues a governed decision; the decision is authority-checked, recorded, and —
if terminal — translated into the H17 event that resolves the wait, delivered
through the **unchanged** H18 durable engine.

```
Execute → WAIT (review gate) → ReviewTask(assigned to a NAMED human)
        → HumanDecision → authority check → record (append-only)
        → [approve|reject|request-changes] → H17 event → H18 deliver → Resume
        → [delegate|escalate] → reassign, stay waiting
```

> **Scope statement.** H19 adds a **governed human-decision layer**: named
> participants, authority-scoped decisions, delegation/escalation chains, and a
> durable, reconstructable audit trail. It is **not** authentication, **not** an
> identity provider, **not** electronic signatures, **not** a legally binding
> approval system, **not** a UI, and it sends no emails or notifications.
> `identity_ref` on a decision is an opaque, caller-supplied reference — a place
> to record *who the caller says decided*, not proof of identity. Those
> capabilities would each need to be separately implemented and verified.

H19 owns **human decision governance only**. It does not modify H10–H18, the
ActionGate, TAP, the authorization/tool-execution path, or the LLM providers —
it composes on their public APIs.

---

## Human actor model

A **`HumanParticipant`** is an immutable authority envelope:

| Field | Meaning |
|-------|---------|
| `participant_id` | stable identifier |
| `display_name` | human-readable label |
| `authority_roles` | named roles (organizational) |
| `permissions` | the granted authority tokens checked against a task |
| `trust_level` | ordinal authority rank (used for escalation direction) |
| `organizational_unit` | org grouping |
| `delegation_limit` | max delegation-chain length this actor may extend |
| `approval_scope` | goal ids this actor may decide (empty = any) |

`ParticipantRegistry` is a **rebindable runtime dependency** (like the H16
capability registry / authority model): checkpoints store participant *ids*, and
the live registry is supplied again at restore time — never serialized into the
durable state.

---

## Review tasks

A **`ReviewTask`** is the explicit, governed object representing "a human must
decide on this goal":

- `task_id`, `workflow_id`, `goal_id`, `condition_id` (the H17 wait it satisfies)
- `assigned_participant` / `original_participant`
- `required_authority` — the permission tokens a decider must hold
- `status` — `ASSIGNED → IN_REVIEW → COMPLETED | CANCELLED | EXPIRED`
- `review_history` — **append-only** audit of every event on the task
- `processed_decision_ids` — decision idempotency set
- `delegation_chain` / `escalation_chain` — append-only reassignment records

Review tasks are opened automatically for any wait condition named in the
`review_specs` passed to `create_workflow`. Because a task is **persisted in
H14 `WorkingMemory`** (under the `__review__:` key prefix), it is checkpointed
and restored by H18 **for free** — H19 adds no separate persistence path.

---

## Governed decision flow (`ReviewManager.submit_decision`)

Decisions are validated and applied in a fixed, deterministic order. **Authority
is checked before any workflow state changes**, so a denied decision leaves the
workflow byte-for-byte unchanged:

1. **Resolve the task.** Unknown or already-terminal → `REVIEW_ALREADY_RESOLVED`
   (no effect).
2. **Idempotency.** A `decision_id` already in `processed_decision_ids` →
   `DUPLICATE_DECISION_IGNORED` (no second effect), and this set is persisted, so
   the guarantee **survives restart**.
3. **Authority validation** (`HumanAuthorityValidator`), *before* any mutation:
   - `can_decide` — participant holds all `required_authority`; goal within
     `approval_scope`.
   - `can_delegate` — decider is authorized, **and** the target is also
     authorized, **and** the delegation chain is within the decider's
     `delegation_limit`.
   - `can_escalate` — the target has **≥** the decider's `trust_level` and holds
     the required authority.
   - A failed check → `AUTHORITY_DENIED` with a reason; **workflow untouched**.
4. **Record the decision** append-only on the task and in the workflow trace.
5. **Dispatch by outcome:**
   - `APPROVED` — build the H17 event that satisfies the wait; deliver via H18;
     the reviewed goal executes and the workflow resumes.
   - `REJECTED` — the reviewed goal transitions to `FAILED`; the wait is then
     resolved (the terminal goal never executes).
   - `REQUEST_CHANGES` — **H15/H12 localized replanning**: `tree.replace_leaf`
     aborts *only* the reviewed leaf and inserts the requested `change_goals`.
     Completed siblings are untouched; the replacement subtree runs.
   - `DELEGATED` / `ESCALATED` — reassign the task, append a chain record, stay
     `WAITING` for the new assignee. No goal state changes.
   - `CANCELLED` — the review is closed `CANCELLED`; no goal state changes.

The `HumanAuthorityValidator` deliberately mirrors the **H16 subset-check
discipline**: an actor may act only within granted authority, evaluated in a
fixed order so denials are deterministic and explainable.

---

## Turning a human decision into an H17 event

H19 does **not** modify H17 waiting semantics. A terminal decision is translated
into a `WorkflowEvent` whose:

- `event_id` = the `decision_id` (so H18's event idempotency and H19's decision
  idempotency are the same guarantee end-to-end),
- `type` / `payload` = the waited-for event type and its `match` (so it resolves
  the exact wait the review gated),
- `memory_writes` always include a `decision:<goal_id>` governance record (the
  outcome, decider, and rationale land in H14 memory),
- `assumption_signals` carry any H13 signals the decision asserts,

and is delivered through the ordinary `DurableWorkflowEngine.deliver`. The wait
resolves, the workflow resumes, and the event effect is checkpointed by H18 —
all through existing public APIs.

---

## Durability & recovery

`ReviewManager.restore(store, workflow_id, registry=…, participants=…,
authority=…)` restores the H18 workflow **and** re-hydrates every pending review
task from the restored memory. A workflow checkpointed while awaiting a human
decision comes back with the same assigned reviewer, the same required
authority, and the same decision-idempotency set — so:

- a pending review **survives process loss** and can be decided post-restart;
- a decision already applied before the crash is a **duplicate** afterward and
  has no second effect;
- the governance **audit trail is continuous** across the restart.

Because review state rides on H14 memory, this inherits H18's canonical-JSON
serialization, integrity digests, and fail-closed corruption detection with no
new persistence code.

---

## Audit & trace

Every review carries an append-only `review_history` (creation, each decision,
authority denials, delegations, escalations), and every governance step is also
recorded on the workflow trace, so a single continuous history reconstructs the
whole decision lineage. `format_review_trace(task)` renders it:

```
Review review:wf:release_review  status=COMPLETED  goal=deploy
assignee=peer (originally lead)
----------------------------------------------------
  CREATED: {'assignee': 'lead', 'goal': 'deploy'}
  DECISION: DELEGATED by lead — cover for me
  DECISION: APPROVED by peer — approved
  delegated lead → peer
```

---

## Interaction with H10–H18

- **H13 assumptions** — a decision may assert `assumption_signals`, carried into
  the resolving event; assumption gating is unchanged.
- **H14 memory** — review tasks and `decision:*` records are ordinary governed
  memory writes; versioning and the operation log are unchanged.
- **H15 hierarchy** — `REQUEST_CHANGES` uses `replace_leaf` for localized
  subtree replanning; completed siblings are preserved.
- **H16 coordination / authority** — the human authority checks reuse H16's
  subset-check pattern; the coordinator assigns non-review work unchanged.
- **H17 workflows** — waiting/resume/event routing are used exactly as-is; a
  human decision is just another well-formed event.
- **H18 durability** — persistence, idempotency, and recovery come entirely from
  the unchanged durable engine; H19 stores review state through H14 memory.

---

## Known limitations

- Not authentication, identity, e-signatures, or a legally binding approval
  system; `identity_ref` is opaque and unverified.
- No UI, email, or notifications — decision *submission* is a programmatic call.
- Deadlines/expiry are recorded on the task but not auto-fired by a scheduler
  (no wall-clock timer here); an external tick would drive expiry.
- Local and deterministic, inheriting H18's non-distributed scope.

---

## Quickstart

```python
from agentic.agentic_framework import (
    WorkingMemory, RunBudget, RunBudgetLimits,
    AgentProfile, CapabilityRegistry, ScriptedWorker, WorkerResult,
    Goal, StaticDecomposer, WaitCondition, WaitKind, InMemoryCheckpointStore,
    HumanParticipant, ParticipantRegistry, HumanDecision, ReviewOutcome,
    ReviewManager,
)

registry = CapabilityRegistry()
registry.register(AgentProfile("bot", capabilities=frozenset({"do"}), trust_level=5),
                  ScriptedWorker(lambda c, m: WorkerResult(success=True,
                      outputs={k: "ok" for k in c.expected_outputs})))

people = ParticipantRegistry([
    HumanParticipant("lead", "Lead", permissions=frozenset({"approve_release"}), trust_level=5),
])

mgr = ReviewManager(registry, InMemoryCheckpointStore(), people)
plan = StaticDecomposer().decompose("release", [
    Goal("deploy", "deploy", required_capabilities=frozenset({"do"}),
         expected_outputs=("release",), priority=1),
])
gate = WaitCondition("rev", "deploy", kind=WaitKind.WAIT_FOR_APPROVAL,
                     event_type="release_approval", match=(("env", "prod"),))
wf = mgr.create_workflow("wf", plan, WorkingMemory(),
                         run_budget=RunBudget(RunBudgetLimits()),
                         wait_conditions=[gate],
                         review_specs={"rev": {"assigned_participant": "lead",
                                               "required_authority": ["approve_release"]}})

task = mgr.tasks_for(wf)[0]                      # assigned to a NAMED reviewer
mgr.submit_decision(wf, task.task_id,
                    HumanDecision("d1", ReviewOutcome.APPROVED, "lead", timestamp=2))
print(wf.status)                                 # COMPLETED
```

See [`examples/human_governance_review.py`](../../examples/human_governance_review.py)
— approval, unauthorized denial, request-changes replanning, delegation,
escalation, checkpoint recovery, duplicate-decision idempotency, and audit-trace
reconstruction, with scripted workers and no API key.
