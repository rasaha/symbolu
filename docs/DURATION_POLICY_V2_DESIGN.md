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
<!-- §4 session TTL — coming in batch A2 -->
<!-- §5 memory TTL deferral note — coming in batch A3 -->
<!-- §6 duration metrics — coming in batch A4 -->
<!-- §7 defaults by tool/risk class — coming in batch A4 (deferral note) -->
<!-- §8 runtime ordering / semantics — coming in batch A4 -->
<!-- §9 backward compatibility — coming in batch A4 -->
<!-- §10 recommended implementation order — coming in batch A4 -->
