# One-Time-Use & Replay Ownership

The audit concluded one-time-use belongs **downstream**. The core never atomically owns consumption.

## Handoff

```text
current ClearanceReceipt (status CLEAR, unexpired)
        ↓
execution boundary validates the receipt (unexpired, unconsumed, chain reconstructs)
        ↓
atomically reserves the replay key in the execution/idempotency ledger
        ↓
dispatch (exactly once)
        ↓
record observation
        ↓
reconcile uncertain outcome
```

## The authoritative replay key

Owned by the execution/idempotency ledger. It binds at least:

```text
replay_key = ( tenant_id,
               authorization_ref,
               authorized_action_fingerprint,
               target_ref,
               operation )
```

This maps onto the existing `execution_idempotency_key` in `ugence_decision_authority`
(`repositories/execution_repository.py::lookup_by_execution_idempotency_key`) and the neutral
`ActionGovernanceRequest.idempotency_key` / `ExecutionDispatchRequest.idempotency_key`. Action Clearance
does **not** define a new ledger; it aligns with this one.

## Action Clearance's role

Action Clearance **receives** prior-consumption as a `TrustedSignal` (`signal_type =
PRIOR_CONSUMPTION`). If that signal says the replay key is already consumed → `ALREADY_CONSUMED` →
`BLOCK`. But this is an **advisory** read: it does not, and cannot, prevent a race by itself. Atomic
prevention is the ledger's job.

## Race behavior (two dispatches, one valid clearance)

```text
Dispatch attempt 1 ── reserve(replay_key) ──▶ ledger: key free → reserved → PROCEED → dispatch
Dispatch attempt 2 ── reserve(replay_key) ──▶ ledger: key taken → DUPLICATE → no dispatch
```

The ledger's reservation is atomic (compare-and-set on the replay key). Exactly one attempt wins;
the other observes `ExecutionBusinessOutcome.DUPLICATE`. The `ClearanceResult` may be `CLEAR` for both —
clearance authorizes *readiness*, not *consumption*; consumption is decided at reservation time. This is
why one-time-use cannot live in the core: the core is a pure function and has no atomic state.

## Open prerequisite

Confirming the execution-ledger owner and the exact atomic-reservation contract is a P0 item scoped to
the **execution** layer (not the clearance core). Until then, Phases A–F of
[`IMPLEMENTATION_SEQUENCE.md`](IMPLEMENTATION_SEQUENCE.md) run in shadow with no real dispatch; Phase G
introduces the ledger integration. See [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) Q4.
