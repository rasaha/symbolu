# DurationPolicy v2 — Design Spec

**Status:** Draft / pre-implementation
**Predecessor:** [`docs/DURATION_POLICY_DESIGN.md`](DURATION_POLICY_DESIGN.md)
**Branch:** TBD
**Peer module:** `agentic/agentic_framework/duration_policy.py` (DurationPolicy v1)

v2 extends `DurationPolicy` from "active-execution timing" (the v1 surface) to
the rest of the agent lifecycle — stale approvals, zombie sessions, missing
duration observability — without redesigning the v1 invariant.

---

## 1. Executive summary

`DurationPolicy` v1 governs **active execution**: it bounds the wall-clock
duration of a single `agent.run_stream()` and the wall-clock duration of any
single action inside it. That's the right primitive for "the model stalled"
and "the tool hung," and it is now in production at
`agentic/agentic_framework/duration_policy.py`.

But "active execution" is a small fraction of an agent's *lifecycle*. The v1
surface does not see:

- **Stale approvals** — a `PendingApproval` blocks the run forever waiting on
  a human who left for the day. v1's run-level deadline does fire eventually,
  but that conflates "the human is absent" with "the agent is stalled," and
  the user-visible failure is `DEADLINE_EXCEEDED` rather than the more
  truthful "approval expired."
- **Zombie sessions** — `AgenticLLMWrapper.new_session()` allocates a
  session_id and an `AgentMemory`. Nothing reaps them. A long-lived process
  that creates sessions on every request grows unbounded.
- **Stale memory / context** — even within a live session, `MemoryStore` is a
  fixed-window sliding buffer. There is no notion of "this turn happened too
  long ago to still be relevant." (v2 keeps this out of scope; see §5.)
- **Missing duration metrics** — the runtime can *enforce* deadlines but it
  cannot easily *report* on them. There is no `time_to_first_action`, no
  count of `action_timeouts`, no `approvals_expired`. Operators are flying
  blind on temporal SLOs.

v2 closes the lifecycle gaps with **two new events** (`APPROVAL_EXPIRED`,
`SESSION_EXPIRED`) and **a small set of trace counters**. It does **not**
redesign v1, does **not** introduce new policy objects (still one
`DurationPolicy`), and does **not** add background sweepers, registries, or
memory eviction. Those are deferred to v2.5 (§2, §5, §7).

The runtime invariant gains one stage:

```
cancel  →  budget  →  deadline  →  approval-expiry  →  approve  →  execute
```

Approval-expiry sits between `deadline` and `approve` because it is a
property of the approval gate itself, not of execution.

---

## 2. Scope split

### v2 core (this spec, intended to ship)

1. **Approval expiry** — `DurationPolicy.approval_ttl_s`.
   New event `APPROVAL_EXPIRED`. Resolves the *action* (treated as denied
   with reason `"expired"`), does **not** terminate the run.
2. **Lazy session TTL** — `DurationPolicy.session_idle_ttl_s` and
   `session_max_ttl_s`. New event `SESSION_EXPIRED`. Checked on next
   session access; **no background sweeper** in v2.
3. **Duration metrics / observability** — additive trace counters
   (`time_to_first_action`, `time_to_first_approval`, `approvals_expired`,
   `sessions_expired`, plus existing `action_timeouts` /
   `deadline_exceeded` already from v1). No new events, no benchmark
   thresholds.

### Deferred to v2.5+ (signed-off, not in scope here)

- **Memory TTL / eviction.** Per-turn vs idle vs absolute, LRU vs size,
  compatibility with the existing sliding-window `MemoryStore`. See §5
  for the deferral note.
- **Background session sweeper / multi-process session registry.** v2 is
  lazy-check-only because the framework has no session registry. A real
  registry, a sweeper task, and cross-process lifecycle ownership are
  their own design.
- **Defaults-by-tool / risk-class / `DurationPolicyMap`.** Composing
  per-tool overrides with `ApprovalPolicy.require_approval_for` and the
  safety contract is a separate design. v2 keeps `DurationPolicy` as a
  single object.
- **Per-revision wall-clock cap.** Subsumed by the run-level deadline in
  v1; revisit only if the run-level cap proves insufficient in practice.

---

<!-- §3 approval expiry — coming in batch A1 -->
## 3. Approval expiry

### 3.1 Problem

In v1, `ApprovalController.request_approval(pending)` invokes a callback
*synchronously*. The callback may block (terminal prompt, network call, web
UI wait) until a human responds. There is no upper bound on how long it
blocks. The agent's run-level deadline (v1) does fire eventually, but it
reports the failure as `DEADLINE_EXCEEDED`, which conflates two genuinely
different operator concerns:

- "the model / a tool stalled" → `DEADLINE_EXCEEDED` (correct in v1)
- "we asked a human and they didn't answer" → should be `APPROVAL_EXPIRED`

### 3.2 Policy field

Add to `DurationPolicy` (the same frozen dataclass that holds
`max_run_duration_s` and `max_action_duration_s`):

```python
approval_ttl_s: Optional[float] = None
```

Semantics: the maximum wall-clock seconds a single approval request may
block before being treated as expired. `None` (default) preserves v1
behaviour exactly — the controller blocks indefinitely.

A small helper on the policy:

```python
def approval_exceeded(self, elapsed_s: float) -> Optional[str]:
    """Return a human-readable reason if the approval wait exceeded the
    TTL, or None if still within it."""
```

(Keeps the predicate-returning-reason style established by
`run_exceeded` / `action_exceeded`.)

### 3.3 Event

```python
APPROVAL_EXPIRED = "approval_expired"   # non-terminal, action-level
```

Payload:

```jsonc
{
  "action_id": "...",
  "action_type": "...",
  "elapsed_s": 30.04,
  "approval_ttl_s": 30.0,
  "reason": "Approval wait 30.0s exceeds TTL 30.0s"
}
```

### 3.4 Behaviour

`APPROVAL_EXPIRED` is **non-terminal**. It resolves the *action*, not the
run, mirroring how `ACTION_TIMEOUT` resolves a single action in v1:

1. The runtime emits `APPROVAL_REQUESTED` as today.
2. The runtime invokes the controller callback inside a wait-with-timeout
   wrapper (`asyncio.wait_for(asyncio.to_thread(...), timeout=ttl)` on the
   async path; `ThreadPoolExecutor.submit(...).result(timeout=ttl)` on the
   sync path, with the same `shutdown(wait=False)` runaway-thread caveat
   documented in v1).
3. On timeout:
   - emit `APPROVAL_EXPIRED` with the payload above
   - mark `action.status = "denied"` and
     `action.error = "Approval expired after {ttl}s"`
   - emit `ACTION_COMPLETED` with `status="denied"` (existing event,
     existing payload shape)
   - **continue to the next action** — do *not* return from the run.
4. If the callback returns *after* the timeout fired, the response is
   discarded. The orphan thread leaks per the same v1 rule (Python cannot
   kill threads); it cannot mutate the run's event stream because the
   action has already moved past `ACTION_COMPLETED`.

`APPROVAL_RESOLVED` is **not** emitted on expiry. The action goes
`APPROVAL_REQUESTED → APPROVAL_EXPIRED → ACTION_COMPLETED`, parallel to
the v1 timeout sequence `ACTION_STARTED → ACTION_TIMEOUT →
ACTION_COMPLETED`. This keeps "approval was answered" and "approval timed
out" cleanly separable in downstream consumers.

### 3.5 Trace implications

Two additive fields on `AgentRunTrace`:

```python
approvals_expired: int = 0       # count of APPROVAL_EXPIRED events
max_approval_ttl_s: Optional[float] = None
```

`approvals_expired` increments per event; `max_approval_ttl_s` is lifted
from the first `APPROVAL_EXPIRED` payload (or remains `None` if the policy
never fired).

The existing `approvals_denied` counter already includes the expired
case (the action's terminal `ACTION_COMPLETED` carries `status="denied"`).
v2 keeps that bucket as a superset and adds the dedicated
`approvals_expired` so that "denied because human said no" and "denied
because human didn't respond" can be distinguished without re-scanning the
event list.

### 3.6 Why not terminal

A terminal `APPROVAL_EXPIRED` would be wrong for two reasons:

- A run can have many actions, only some of which need approval. Killing
  the whole run because *one* action's approver was AFK throws away the
  rest of the work, including any already-completed actions and the
  generation output.
- It would collapse with `DEADLINE_EXCEEDED`. If the operator wants
  "stop the run if any approval hangs," they already have v1's
  `max_run_duration_s` — making `APPROVAL_EXPIRED` terminal would be
  redundant and would force an unwanted choice.

Per-action expiry composes cleanly with the run-level deadline: enough
expired approvals will eventually trip `DEADLINE_EXCEEDED` anyway, but
each individual expiry is recorded for forensic clarity.
<!-- §4 session TTL — coming in batch A2 -->
<!-- §5 memory TTL deferral note — coming in batch A3 -->
<!-- §6 duration metrics — coming in batch A4 -->
<!-- §7 defaults by tool/risk class — coming in batch A4 (deferral note) -->
<!-- §8 runtime ordering / semantics — coming in batch A4 -->
<!-- §9 backward compatibility — coming in batch A4 -->
<!-- §10 recommended implementation order — coming in batch A4 -->
