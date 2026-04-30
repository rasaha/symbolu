# DurationPolicy — Design Spec (v1)

**Status:** Design / pre-implementation
**Branch:** `claude/agent-runtime-governance-X9zY7`
**Peer document:** `agentic/agentic_framework/token_budget.py` (BudgetPolicy)
**Architecture doc:** `agentic/AGENTIC_ARCHITECTURE.md`

A peer to BudgetPolicy that governs *temporal persistence* of an agent run,
the way BudgetPolicy governs *resource consumption*.

## 1. Executive summary

The Agentic Framework currently governs four runtime dimensions: token/cost
budget, revision count, action-rate, and approvals. None of these bound
*wall-clock time*. Timestamps are captured (`AgentRunTrace.started_at` /
`ended_at`, per-step `duration_ms`) but only for observability — the runtime
never compares them against a threshold.

This spec adds **DurationPolicy** as a frozen dataclass parallel to
`BudgetPolicy`, gating two terminal events:

- `DEADLINE_EXCEEDED` — run-level wall-clock deadline elapsed.
- `ACTION_TIMEOUT` — single action exceeded its per-action budget.

The runtime invariant becomes:

```
cancel → budget → deadline → approve → execute
```

v1 is **two policy fields, two events, one new check site per existing
budget check site**. Approval expiry, session TTL, and memory TTL are
explicitly deferred to v2.

## 2. Why duration is a distinct governance dimension

BudgetPolicy answers: *"Has this run consumed too much?"*
DurationPolicy answers: *"Has this run persisted too long?"*

These are not interchangeable:

| Failure mode | Budget catches? | Duration catches? |
|---|---|---|
| Runaway token generation | yes | sometimes (eventually) |
| LLM provider stall (slow stream) | no | yes |
| Tool/MCP call hang (network, subprocess) | no | yes |
| Approval workflow blocked on absent human | no | yes (v2) |
| Infinite revision loop with cheap output | no | yes |
| Cheap-but-late agent that misses an SLA | no | yes |

A run can be perfectly within budget and still violate operational
expectations (latency SLOs, downstream timeouts, paged on-call). Conversely,
a run can be fast and still over budget. The two dimensions are orthogonal,
and both should be terminal-on-violation.

Duration is also **where benchmarking actually lives** for production agents
— time-to-first-action, time-to-completion, p95 stall — none of which the
current governance model can express.

## 3. Proposed policy object / API shape

New module: `agentic/agentic_framework/duration_policy.py`

Mirrors `token_budget.py` style: frozen dataclass, `is_exceeded(...)` returning
a human-readable reason or `None`, `to_dict()` for serialisation.

```python
@dataclass(frozen=True)
class DurationPolicy:
    """Optional per-run wall-clock limits.

    Set any field to ``None`` (the default) to leave it unconstrained.

    Args:
        max_run_duration_s: Hard cap on wall-clock seconds from RUN_STARTED
            to terminal event. Checked at the same sites as BudgetPolicy.
        max_action_duration_s: Hard cap on wall-clock seconds for a single
            ACTION_STARTED → ACTION_COMPLETED span.
    """

    max_run_duration_s: Optional[float] = None
    max_action_duration_s: Optional[float] = None

    def run_exceeded(self, elapsed_s: float) -> Optional[str]: ...
    def action_exceeded(self, elapsed_s: float) -> Optional[str]: ...
    def to_dict(self) -> Dict[str, Any]: ...
```

Caller-facing API mirrors `budget_policy=`:

```python
agent.run_stream(
    "Hello",
    budget_policy=BudgetPolicy(max_total_tokens=4000),
    duration_policy=DurationPolicy(max_run_duration_s=30.0,
                                   max_action_duration_s=10.0),
)
```

A small helper, `RunClock`, is instantiated per-run inside `agent.run_stream`
and holds `started_monotonic: float` (from `time.monotonic()`). `elapsed_s`
is computed via subtraction at each check site. Wall-clock for traces stays
on `datetime.now(timezone.utc)`; gating uses monotonic to be immune to
NTP/clock jumps.

## 4. Exact runtime insertion points

All sites are in `agentic/agentic_framework/agent.py`. The deadline check is
a near-clone of the budget check and goes immediately after it.

**Site A — after generation (run-level deadline):**
After the `BUDGET_EXCEEDED` block at `agent.py:740-748`. Same pattern at
`agent.py:1054-1062` (the `run_stream_async` mirror).

```python
# --- deadline check: after generation ---
if duration_policy is not None:
    _exceeded = duration_policy.run_exceeded(clock.elapsed_s())
    if _exceeded:
        yield _emit(_evt(DEADLINE_EXCEEDED, {
            "reason": _exceeded,
            "elapsed_s": clock.elapsed_s(),
            "max_run_duration_s": duration_policy.max_run_duration_s,
        }))
        return
```

**Site B — before each action (run-level deadline):**
After the `BUDGET_EXCEEDED` block at `agent.py:820-828`. Same pattern at
`agent.py:1128-1136`. Identical body to Site A.

**Site C — around action execution (per-action timeout):**
Wrap the `SafeMCPGateway` invocation in `asyncio.wait_for(..., timeout=...)`
when `duration_policy.max_action_duration_s` is set. On `asyncio.TimeoutError`
emit `ACTION_TIMEOUT` with `{action_id, action_type, elapsed_s,
max_action_duration_s}`, mark the action as `"timed_out"`, and continue with
the next action — `ACTION_TIMEOUT` is **not** a run-terminal event (it
fails one action; the run-level deadline catches systemic stalls).

The synchronous `run_stream` path uses a thread-pool wrapper for the same
semantics (mirrors how cancellation already works there).

`max_revisions` enforcement in `reflective_loop.py` is **untouched**; the
run-level deadline naturally bounds runaway revision loops.

## 5. Event model additions

In `agentic/agentic_framework/streaming_events.py`, alongside
`USAGE_UPDATED` / `BUDGET_EXCEEDED`:

```python
DEADLINE_EXCEEDED = "deadline_exceeded"   # terminal, run-level
ACTION_TIMEOUT    = "action_timeout"      # non-terminal, action-level
```

`DEADLINE_EXCEEDED` payload:

```json
{
  "reason": "Run elapsed 31.4s exceeds deadline 30.0s",
  "elapsed_s": 31.42,
  "max_run_duration_s": 30.0,
  "phase": "after_generation" | "before_action"
}
```

`ACTION_TIMEOUT` payload:

```json
{
  "action_id": "...",
  "action_type": "...",
  "elapsed_s": 10.05,
  "max_action_duration_s": 10.0
}
```

The terminal-event scan in `agent.py:552`
(`(RUN_ERROR, RUN_CANCELLED, BUDGET_EXCEEDED)`) gains `DEADLINE_EXCEEDED`.
`ACTION_TIMEOUT` is intentionally *not* in that set — it is a per-action
status, not a run terminator.

## 6. Trace model changes

In `agentic/agentic_framework/tracing.py`, `AgentRunTrace` already has
`started_at` and `ended_at` (ISO strings, observability). v1 adds:

```python
deadline_exceeded: bool = False     # mirrors budget_exceeded
action_timeouts: int = 0            # count of ACTION_TIMEOUT events
elapsed_s: float = 0.0              # monotonic-derived run duration
max_run_duration_s: Optional[float] = None
max_action_duration_s: Optional[float] = None
```

`_build_trace` derivations:

- `deadline_exceeded` ← `any(e.event_type == DEADLINE_EXCEEDED for e in events)`
- `action_timeouts`   ← count of `ACTION_TIMEOUT`
- `elapsed_s`         ← from a single `RUN_STARTED`-payload `monotonic_start`
  field (added in v1) compared against the terminal event's monotonic stamp,
  OR fallback to `(ended_at - started_at).total_seconds()` if absent
- Status promotion: if `deadline_exceeded` and `status == "unknown"`,
  set `status = "deadline_exceeded"` (mirrors the existing
  `budget_exceeded` promotion at `tracing.py:198-199`)

`to_dict()` / `summary` gain the four new fields.

## 7. Ordering invariant changes

**Current invariant (`AGENTIC_FRAMEWORK_VC_BRIEF.md:100-106`):**

```
cancel → budget → approve → execute
```

**Proposed invariant:**

```
cancel → budget → deadline → approve → execute
```

**Why this position for `deadline`:**

- *After cancel*: an explicitly-cancelled run is the user's intent and must
  always win — never report `DEADLINE_EXCEEDED` if the user already pulled
  the plug.
- *After budget*: budget is the established gate; placing `deadline` after
  it preserves all existing test assertions about `BUDGET_EXCEEDED` ordering.
  If both fire on the same check, `BUDGET_EXCEEDED` wins, which matches the
  semantic that exhausted budget is a more "permanent" failure (a longer
  deadline can't make it succeed).
- *Before approve*: never issue an approval request for a run that has
  already missed its deadline. This avoids paging humans for work that will
  immediately fail anyway.
- *Before execute*: never start a side-effecting action on a run past its
  deadline.

The ordering is verified by tests, the same way the existing chain is
(`test_token_budget.py` style).

## 8. Backward compatibility / migration

- `duration_policy=` is an **optional kwarg** with default `None`. Omitted →
  no temporal gating, identical behaviour to today.
- No existing event types renamed; no existing payloads modified.
- New trace fields default to safe zero values, so any current consumer of
  `AgentRunTrace.to_dict()` keeps working.
- `BudgetPolicy` is untouched. The two policies are independent and
  composable.
- The terminal-event tuple (`agent.py:552`) gains `DEADLINE_EXCEEDED`. Any
  caller that pattern-matches on terminal events should be audited — there
  is exactly one such site in the framework today, and it already uses a
  tuple, so the change is mechanical.
- Public docstring for `agent.run_stream` / `run_stream_async` adds the new
  kwarg in the same paragraph as `budget_policy`.

No deprecations. No config-file format changes.

## 9. Suggested tests

New file: `agentic/agentic_framework/tests/test_duration_policy.py`,
mirroring the structure of `test_token_budget.py`.

Unit (policy object):

- `DurationPolicy()` with all-`None` fields never reports exceeded.
- `run_exceeded(elapsed_s)` returns reason iff `elapsed_s > max_run_duration_s`.
- `action_exceeded(elapsed_s)` returns reason iff
  `elapsed_s > max_action_duration_s`.
- `to_dict()` round-trips frozen-dataclass fields.

Integration (runtime):

- Run with `max_run_duration_s` smaller than a forced-slow generation emits
  exactly one `DEADLINE_EXCEEDED` and no subsequent `ACTION_STARTED`.
- Run with `max_action_duration_s` smaller than a forced-slow tool emits
  `ACTION_TIMEOUT`, action status is `"timed_out"`, and the run continues
  to the next action.
- Trace fields (`deadline_exceeded`, `action_timeouts`, `elapsed_s`) are
  populated correctly.

Ordering invariants (the load-bearing tests):

- Cancellation issued before deadline elapses → `RUN_CANCELLED`,
  not `DEADLINE_EXCEEDED`.
- Budget exhausted on the same check tick as deadline elapsed →
  `BUDGET_EXCEEDED` (budget wins by ordering).
- Deadline elapsed before an approval-required action →
  `DEADLINE_EXCEEDED`, **no** `APPROVAL_REQUESTED` is emitted.
- Deadline elapsed before any side-effecting action → no `ACTION_STARTED`.

Property/regression:

- Disabled policy (`duration_policy=None`) produces a byte-identical event
  stream to today's behaviour for a fixed seed (snapshot test).

## 10. v1 vs v2 scope

**v1 (this spec):**

- `DurationPolicy(max_run_duration_s, max_action_duration_s)` frozen dataclass
- `RunClock` (monotonic-based) instantiated per run
- Event types: `DEADLINE_EXCEEDED` (terminal), `ACTION_TIMEOUT` (per-action)
- Check sites: after generation, before each action, around action execution
- Trace fields: `deadline_exceeded`, `action_timeouts`, `elapsed_s`,
  `max_run_duration_s`, `max_action_duration_s`
- Ordering invariant updated to `cancel → budget → deadline → approve → execute`
- Tests in `test_duration_policy.py` covering policy, runtime, ordering

**v2 (deferred — separate spec):**

- *Approval expiry*: `DurationPolicy.approval_ttl_s`. New event
  `APPROVAL_EXPIRED` (or repurposed `APPROVAL_RESOLVED` with
  `approved=False, reason="expired"`). Requires changes to
  `approval_workflow.py` which v1 deliberately leaves untouched.
- *Session TTL*: a session-scoped (not run-scoped) field; needs a session
  registry sweep mechanism the framework currently lacks.
- *AgentMemory TTL / eviction*: needs a memory-store eviction policy that
  is its own design discussion (LRU? size-based? per-turn?).
- *Per-revision wall-clock cap*: only worth adding if the run-level deadline
  proves insufficient in practice.

Each v2 item lands cleanly on top of v1 by adding policy fields and new
event types; none of them require revisiting v1's invariants.

## On benchmarking

Yes — duration *should* become a first-class benchmark category, but **not
in v1**. The right sequence is:

1. Land v1 (gating + events + trace fields).
2. Run on the existing benchmark corpus and capture `elapsed_s`,
   `time_to_first_action`, `time_to_first_approval`, `action_timeouts`,
   `deadline_exceeded` per run.
3. *Then* propose a benchmark category in `benchmark_critics.py` with
   real distributions to anchor thresholds against — not invented ones.

Defining time-to-completion / time-to-stall / timeout-handling as
benchmark dimensions before the runtime can measure them produces
unfalsifiable thresholds. Implement first, benchmark second.
