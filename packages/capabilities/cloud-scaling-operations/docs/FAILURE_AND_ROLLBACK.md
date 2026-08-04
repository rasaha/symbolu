# Failure & Rollback

## Execution failures
- Optimistic-concurrency conflicts (observed pre-state != expected) → `FAILED` receipt,
  no mutation, audit event.
- Backend/API errors → `FAILED` receipt with a structured reason (no secrets).
- LIVE precondition failures (missing backend/audit/readiness, insecure TLS) → `DENIED`.

## Rollback
Rollback is never assumed automatically safe. `RollbackCoordinator.rollback` requires:
a known prior state, a valid prior `ExecutionReceipt`, a bounded target (via a
`RollbackPolicy` or a separate rollback `ExecutionAuthorization`), an idempotency key,
a reason, and audit persistence. Unlimited rollback to an unknown historical value is
refused. Rollback runs through the same authority-gated `ControlledScalingExecutor`.

## Idempotency / replay
Each execution is bound to `authorization_id` + `idempotency_key` + target + action. A
repeated completed request returns a `DUPLICATE` receipt without re-applying; a reused
key with an altered request/authorization raises `ExecutionIntegrityError`. The
in-memory store is not sufficient for multi-process production; exactly-once across
distributed processes is **not** guaranteed.
