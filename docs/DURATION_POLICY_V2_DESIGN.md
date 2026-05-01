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
## 4. Session TTL (lazy)

### 4.1 Problem

`AgenticLLMWrapper.new_session()` allocates a `session_id` and an
`AgentMemory`. Nothing reaps either. A long-lived process — a chat
backend, an evaluator, a benchmark harness — that calls `new_session()`
on every request grows unbounded until the process restarts. There is no
"this session went stale" signal, no way for an operator to enforce
"close inactive sessions after N minutes."

### 4.2 Scope (lazy-only)

v2 does **not** add a session registry or background sweeper. The
framework currently has neither, and adding them is its own design
exercise (§7 of the v1 spec, deferred to v2.5). v2 ships:

- two policy fields (idle TTL and absolute / max TTL),
- one event (`SESSION_EXPIRED`),
- a **lazy check** at session entry points — `run`, `run_stream`,
  `run_stream_async`, and (a new) `touch_session()`.

When the agent is invoked on a session that has elapsed its TTL, the
runtime emits `SESSION_EXPIRED` *immediately* before doing any other
work, and aborts the call. The caller is expected to allocate a fresh
session via `new_session()` and retry.

This trades cleanup latency (sessions linger in memory until next access)
for a zero-infrastructure surface that fits the existing in-process
single-agent model.

### 4.3 Policy fields

Add to `DurationPolicy`:

```python
session_idle_ttl_s: Optional[float] = None  # seconds since last access
session_max_ttl_s:  Optional[float] = None  # seconds since session start
```

Both default to `None`. Either, both, or neither may be set:

| `idle` | `max` | Behaviour |
|---|---|---|
| `None` | `None` | No session expiry (v1 behaviour) |
| set | `None` | Idle expiry only |
| `None` | set | Absolute expiry only |
| set | set | Earliest of the two wins |

`max` is most useful for "no run lasts longer than 24h"; `idle` is most
useful for "a chat session that hasn't seen a turn in 30 minutes is
done." Setting both gives the union, which is the safe default for
operators who want either guarantee.

### 4.4 Event

```python
SESSION_EXPIRED = "session_expired"   # terminal w.r.t. *this call*
```

Payload:

```jsonc
{
  "session_id": "...",
  "reason": "idle" | "max" | "both",
  "idle_elapsed_s": 1834.2,
  "max_elapsed_s":  3601.5,
  "session_idle_ttl_s": 1800.0,
  "session_max_ttl_s":  3600.0
}
```

`reason` is `"idle"` if only the idle TTL fired, `"max"` if only the
absolute TTL fired, `"both"` if the call happened to cross both
simultaneously. Concrete elapsed values are reported regardless so the
operator can see "how long past the limit" in either dimension.

### 4.5 Storage / state

The agent already holds the per-session state it needs:

- `_memory.session_id` — exists (v1)
- `_memory.created_at` (or equivalent) — derive from
  `MemoryStore` if available; otherwise track a private
  `_session_started_monotonic: float` set by `new_session()`
- `_session_last_touched_monotonic: float` — new, updated at the start
  of every public entry point

Both timestamps are monotonic, consistent with v1's `RunClock`. ISO
strings on the trace remain wall-clock for observability.

### 4.6 Lifecycle / where the check runs

```
run / run_stream / run_stream_async / touch_session
        │
        ▼
    [1] check session_idle_ttl_s and session_max_ttl_s
            │
            ├── expired ──► emit SESSION_EXPIRED, return early
            │
            └── ok       ──► update _session_last_touched_monotonic
                              continue with normal pipeline
```

Step [1] runs **before** RUN_STARTED. A session-expired call therefore
emits exactly one event (`SESSION_EXPIRED`) and nothing else; in
particular, no `RUN_STARTED`, no `GENERATION_STARTED`, no
`USAGE_UPDATED`. This is intentional: it lets downstream consumers
distinguish "the session is dead" from "a run failed."

`new_session()` resets both timestamps and is therefore the canonical
way to recover from `SESSION_EXPIRED`. A `touch_session()` helper is
added so external code can keep a session alive without doing real work.

### 4.7 Behaviour after expiry

After `SESSION_EXPIRED`, the agent's internal state (`_memory`,
`_coherence_state`, `_goal_state`) is **not** discarded automatically.
The call returns; the operator decides whether to call `new_session()`,
`reset()`, or to log and discard the agent instance. This mirrors how
the framework treats `RUN_ERROR` today — the runtime reports the failure
and the caller owns recovery.

If the caller invokes `run` again on the same expired session without
calling `new_session()`, they get another `SESSION_EXPIRED`. There is no
auto-reset.

### 4.8 Trace implications

`AgentRunTrace` does not currently span sessions — it represents a
single run. A session-expired call still produces a trace, with:

```python
sessions_expired: int = 0    # 0 or 1 for a single trace
session_expired_reason: Optional[str] = None
```

(Most non-zero values will be `1`, but the field is an integer for
forward-compat with future per-session-event aggregation. `summary`
includes both fields; `to_dict()` includes them too.)

### 4.9 Backward compatibility

- Both new policy fields default to `None`. Callers who do not set them
  see zero behavioural change.
- `new_session()` signature is unchanged; it transparently resets the
  new monotonic timestamps.
- `touch_session()` is purely additive.
- The new `SESSION_EXPIRED` event is additive; existing callers that
  match on terminal events will not be affected unless they explicitly
  opt in.

### 4.10 Out of scope (deferred to v2.5)

- A session registry that would let an external sweeper enumerate
  sessions and expire them proactively.
- Cross-process session sharing / persistence.
- Per-session policy overrides (e.g. "this session has TTL 5 minutes,
  that one has TTL 1 hour"). v2's TTLs come from the per-call
  `DurationPolicy`, which is enough to express both static and
  per-request policies; a true per-session override needs the registry
  that v2.5 will introduce.
<!-- §5 memory TTL deferral note — coming in batch A3 -->
## 5. AgentMemory TTL / eviction (deferred to v2.5)

`MemoryStore` today is a per-agent **sliding window** of `TurnSnapshot`s
sized by `memory_window` (default 20). Eviction is purely positional:
the oldest turn drops off when the (window + 1)-th turn lands. There is
no notion of *time*, only of *order*.

Adding a TTL surface here is **deliberately out of scope for v2** for
three reasons:

1. **It silently changes semantics for every existing user.** The window
   model is what callers reason about today. A TTL would cause turns to
   disappear "spontaneously" between calls (specifically, between the
   last turn and the next entry point that performs the eviction
   check), which is a different mental model.
2. **The design space is wide and underspecified.** There are at least
   four orthogonal TTL flavours, and each has different invariants:

   | Flavour | What it means | Useful for |
   |---|---|---|
   | per-turn TTL | each turn dies N seconds after it was recorded | sliding-context use cases |
   | idle TTL | the *oldest* turn dies if no new turn has landed for N seconds | cleanup of paused sessions |
   | absolute TTL | every turn older than wall-clock T is gone | regulatory retention |
   | size-based / LRU | bound bytes or tokens, not time | cost control |

   Each interacts differently with `coherence_tracker`,
   `goal_decomposition`, retrieval, and the eventual session registry.
   Picking one without that interaction analysis would create a feature
   that has to be reworked the moment any of those neighbours grows.
3. **Session TTL (§4) already covers the high-value case for v2.** The
   most common reason to want "stale memory" is a stale session — and a
   stale session is reaped wholesale by `SESSION_EXPIRED`. Operators who
   need finer-grained per-turn expiry can wait one release.

### What v2.5 should answer before this lands

- Which flavour (or composition) is the contract — per-turn, idle,
  absolute, or LRU?
- Is eviction lazy (next `append_turn` / next retrieval) or eager
  (handled by the deferred session sweeper)?
- Does eviction emit an event (`MEMORY_EVICTED`) or is it silent? An
  event is consistent with the rest of `streaming_events.py`, but only
  if it carries enough payload to be actionable.
- What does `get_relevant_context()` do with a half-evicted history?
- How does this compose with `embedding_model` / vector retrieval, if
  any, when retrieved turns are already gone?

Until those are answered, v2 leaves `MemoryStore` strictly alone.

### What v2 does *not* do

- Does not add `memory_ttl_s` / similar fields to `DurationPolicy`.
- Does not add a `MEMORY_EVICTED` event to `streaming_events.py`.
- Does not change `MemoryStore.append_turn` semantics in any way.

A v2 caller who needs *any* form of time-bounded memory today should:
1. set `session_idle_ttl_s` (§4) so the entire memory is reset when the
   session goes idle, and/or
2. shrink `memory_window` so the positional sliding-window eviction
   approximates the desired retention.

These are escape hatches, not solutions; the proper solution is v2.5.
<!-- §6 duration metrics — coming in batch A4 -->
## 6. Duration observability / metrics

v1 added `elapsed_s`, `deadline_exceeded`, `action_timeouts`,
`max_run_duration_s`, `max_action_duration_s` to `AgentRunTrace`. v2
extends the surface so operators can answer SLO questions without
re-scanning the event list.

### 6.1 New trace fields

Additive on `AgentRunTrace`:

```python
# v2 — approval expiry (§3)
approvals_expired: int = 0
max_approval_ttl_s: Optional[float] = None

# v2 — session TTL (§4)
sessions_expired: int = 0
session_expired_reason: Optional[str] = None  # "idle" | "max" | "both" | None

# v2 — duration observability
time_to_first_action_s:   Optional[float] = None
time_to_first_approval_s: Optional[float] = None
```

Derivation rules (in `_build_trace`):

- `time_to_first_action_s` ← elapsed seconds from `RUN_STARTED` to the
  first `ACTION_STARTED`; `None` if no action ever started (e.g. the
  run terminated at `BUDGET_EXCEEDED` / `DEADLINE_EXCEEDED` /
  `RUN_CANCELLED` before any action).
- `time_to_first_approval_s` ← elapsed seconds from `RUN_STARTED` to
  the first `APPROVAL_REQUESTED`; `None` if no approval was ever
  requested.
- Both are derived from event `timestamp` ISO strings, consistent with
  the v1 fallback for `elapsed_s`. Monotonic precision is not required
  here — these fields are observability, not gating.

### 6.2 Summary surfacing

`AgentRunTrace.summary` (which is `to_dict()` minus `events`) gains the
same six keys. This is the surface that benchmark harnesses, dashboards,
and structured-logging consumers rely on; including the new fields here
is what makes them actually useful.

### 6.3 No new events for metrics

v2 does **not** add metric-only events. The information is derivable
from the existing event stream; surfacing it on the trace is cheaper and
keeps `streaming_events.py` focused on lifecycle, not telemetry.

### 6.4 No benchmark thresholds in v2

v2 makes the metrics *measurable*. It does **not** propose threshold
values or a benchmark category for `time_to_first_action_s` etc. The v1
spec's closing principle stands: implement first, gather distributions
on real workloads, then anchor benchmarks against measured data rather
than invented numbers.

---

## 7. Policy defaults by tool / risk class — deferred to v2.5

The intuition is real — read-only tools should have looser timeouts than
destructive tools, retrieval should be different from compute — but the
implementation surface is not yet clean enough to ship.

### 7.1 What it would look like

A `DurationPolicyMap` keyed by `action_type`:

```python
DurationPolicyMap({
    "search":      DurationPolicy(max_action_duration_s=30.0),
    "compute":     DurationPolicy(max_action_duration_s=10.0),
    "delete_file": DurationPolicy(max_action_duration_s=5.0,
                                  approval_ttl_s=60.0),
})
```

with a default policy that applies when no key matches. The runtime
resolves the policy at the per-action check sites (Site B / Site C in
v1's spec).

### 7.2 Why it isn't in v2

Three composition problems need agreement first:

1. **Interaction with `ApprovalPolicy.require_approval_for`.** Today,
   approval-required is a property of the action_type. A per-action
   `approval_ttl_s` would let those two surfaces drift unless they share
   a registry. The cleanest answer is "register `(action_type, policy)`
   tuples once and let approval policy + duration policy read from the
   same source," but that's a registry refactor, not a v2 add-on.
2. **Interaction with the safety contract.** `SafetyContract` already
   classifies actions by reversibility / blast radius. A "risk class"
   abstraction probably belongs there, with `DurationPolicyMap`
   reading off it — not as a parallel taxonomy.
3. **Resolution semantics for unmapped action types.** Fall back to the
   default? Refuse? Emit a warning? Emit a new event? Each is defensible
   and each commits the framework to a posture.

v2 keeps `DurationPolicy` as a single object. v2.5 can introduce the map
once the safety-contract / approval-policy / duration-policy triad has
a shared registry — that work is its own design pass.

---

## 8. Runtime ordering / semantics

v1's invariant:

```
cancel  →  budget  →  deadline  →  approve  →  execute
```

v2's invariant:

```
session-expiry → cancel → budget → deadline → approval-expiry → approve → execute
                                                ▲
                                                │ (only when an approval is pending)
```

### 8.1 Where each new gate sits

- **`session-expiry`** runs *first*, at the public entry point, before
  even `RUN_STARTED`. A session that has already expired never produces
  a normal run lifecycle (§4.6). It precedes `cancel` because cancelling
  a dead session is meaningless — the more truthful failure is "the
  session is gone."
- **`approval-expiry`** is a property of the approval gate itself. It
  fires *only* when an approval request is in flight, between
  `APPROVAL_REQUESTED` and (would-be) `APPROVAL_RESOLVED`. In the
  invariant chain it sits immediately before `approve` because it is a
  failure mode of *waiting for approval*, not of executing.

### 8.2 Why this ordering, in one sentence each

- **session-expiry first** — a dead session can't honour any other gate.
- **cancel** — explicit user intent always wins over runtime gates.
- **budget** — established v1 ordering; preserves all existing tests.
- **deadline** — established v1 ordering; same logic.
- **approval-expiry** — failure mode of the approval wait itself,
  resolves the action (not the run).
- **approve** — established gate.
- **execute** — actually do the side-effecting work.

### 8.3 Interactions worth calling out

- If a run-level deadline elapses *while* an approval is pending, the
  approval-expiry timer is moot — `DEADLINE_EXCEEDED` fires and the
  approval is abandoned. That's correct: deadline is the run-level
  guarantee; approval expiry is per-action.
- If both session-TTLs are set (idle + max) and a call straddles both,
  the `SESSION_EXPIRED` payload's `reason` is `"both"` (§4.4), but only
  one event fires.
- `APPROVAL_EXPIRED` and `ACTION_TIMEOUT` are siblings: both
  non-terminal, both resolve a single action, both leave the run free
  to continue. They are intentionally orthogonal — an action can time
  out *during* execution (`ACTION_TIMEOUT`) or *while waiting for
  approval* (`APPROVAL_EXPIRED`), never both.

---

## 9. Backward compatibility

All v2 additions are strictly opt-in. Default behaviour for any caller
who does not set the new fields is byte-identical to v1.

### 9.1 Field-level

| New field | Default | Effect when default |
|---|---|---|
| `DurationPolicy.approval_ttl_s` | `None` | controller blocks indefinitely (v1 behaviour) |
| `DurationPolicy.session_idle_ttl_s` | `None` | session never idles out |
| `DurationPolicy.session_max_ttl_s` | `None` | session has no absolute lifetime |

### 9.2 Event-level

`APPROVAL_EXPIRED` and `SESSION_EXPIRED` are additive constants. The v1
terminal-event tuple in `agent.py` (`run_stream_structured`) gains
`SESSION_EXPIRED` (terminal w.r.t. *the call*); `APPROVAL_EXPIRED` is
intentionally **not** added to that tuple because it is non-terminal.

### 9.3 Trace-level

Six new fields, all defaulting to safe zero / `None`. Any existing
consumer of `AgentRunTrace.to_dict()` keeps working; new fields appear
at the bottom of the dict and are ignorable.

### 9.4 API-level

- `run_stream(... duration_policy=None)` keeps its v1 signature; the
  new behaviour ships through new fields on the `DurationPolicy` value
  the caller already passes.
- `new_session()` signature unchanged; resets the new monotonic
  timestamps internally.
- `touch_session()` is purely additive.
- No deprecations; no config-file format changes.

### 9.5 Test compatibility

v1's `test_duration_policy.py` should pass untouched. v2 tests live in
`test_duration_policy_v2.py` (or extend the existing file with v2
classes — TBD at implementation time). No existing test should require
modification; if one does, that is a regression and must be explained
in the implementing commit.

---

## 10. Recommended implementation order

Per the agreed batching, smallest- and most-localised-change first:

### B1 — approval expiry (first)

Smallest, most-localised, highest-value. Touches:

- `duration_policy.py` — add `approval_ttl_s` + `approval_exceeded()`.
- `streaming_events.py` — add `APPROVAL_EXPIRED`.
- `agent.py` — wrap the controller callback at both approval-gate
  call sites (sync at ~line 847; async at ~line 1155 — the line numbers
  drift with v1; use the existing `_ac.request_approval(pending)` /
  `await asyncio.to_thread(_ac.request_approval, pending)` calls as the
  anchors).
- `tracing.py` — `approvals_expired`, `max_approval_ttl_s`.
- `tests/test_duration_policy_v2.py` — unit + runtime + ordering +
  backward-compat.

### B3 — duration metrics (second)

Pure trace work. Zero runtime risk. Touches:

- `tracing.py` — add `time_to_first_action_s`,
  `time_to_first_approval_s`; populate in `_build_trace`; surface in
  `summary`.
- `tests/test_duration_policy_v2.py` — extend with metric-derivation
  tests.

(Batched second because it depends on `APPROVAL_EXPIRED` already
existing for `time_to_first_approval_s` semantics to be complete; doing
it before B1 would force a second pass.)

### B2 — lazy session TTL (third)

Largest semantic surface. Touches:

- `duration_policy.py` — add `session_idle_ttl_s`,
  `session_max_ttl_s`, `session_exceeded()`.
- `streaming_events.py` — add `SESSION_EXPIRED`.
- `agent.py` — record `_session_started_monotonic` and
  `_session_last_touched_monotonic` in `new_session()`; check at the
  top of `run`, `run_stream`, `run_stream_async`; add
  `touch_session()`.
- `tracing.py` — `sessions_expired`, `session_expired_reason`.
- `tests/test_duration_policy_v2.py` — entry-point gating, idle vs
  max vs both, recovery via `new_session()`, ordering.

### B4 — memory TTL — **NOT in this round**

Per §5. Re-evaluate in v2.5.

### Stop conditions between batches

After each of B1, B3, B2: pause for review. The implementing commit
must include:

1. plan executed (with line/file diff scope)
2. exact files changed
3. behaviour added
4. tests added
5. any deviations from this design
6. regression check vs v1's `test_duration_policy.py`
7. confirmation that the documented ordering invariant still holds
   end-to-end
