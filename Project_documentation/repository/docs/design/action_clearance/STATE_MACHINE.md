# State Machine

Two separate state machines: **evaluation** (transient, in the core) and **durable receipt** (in the
workflow layer). Execution-consumption state is in the ledger, not here.

## Evaluation flow (core, transient)

```text
REQUESTED
  → VALIDATING_AUTHORIZATION      # eligibility (AUTHORIZED/AUTHORIZED_WITH_CONSTRAINTS), expiry, refs
  → VALIDATING_ACTION_IDENTITY    # authorized_action_fingerprint match; target/operation
  → VALIDATING_SIGNALS            # tenant/subject/freshness/integrity; fail-closed on missing mandatory
  → EVALUATING_POLICY             # constraint intersection, profile policy, reason-code assembly
  → CLEAR | HOLD | BLOCK | ESCALATE
```

Ownership: entirely within the pure evaluator. A malformed request or unsupported profile short-circuits
to a **typed exception** (not a state); every expected problem produces one of the four terminal
statuses. Transitions are deterministic given the request.

## Durable receipt states (workflow layer)

```text
ISSUED
  → EXPIRED                      # evaluation_time passes valid_until
  → SUPERSEDED                   # a newer clearance for the same replay key issued
  → REVOKED_BY_UPSTREAM_CHANGE   # authorization/decision superseded, or artifact/identity changed
```

`ISSUED` is set when the Workflow Service persists a `ClearanceReceipt` around a `CLEAR` result. A
non-`CLEAR` result produces **no** `ISSUED` receipt (it may be recorded for audit, but it is not a
usable clearance). The receipt never carries authoritative **execution-consumption** state — that is the
ledger's (only if a future design proves atomic ownership is possible would this change; it is not
proven, so it stays out).

## Transition ownership & retry

| Transition | Owner | Retry semantics |
|---|---|---|
| evaluation `REQUESTED → …` | core evaluator | pure; identical request → identical result |
| `ISSUED` | Workflow Service | on `CLEAR` only |
| `EXPIRED` | Workflow Service (time check at dispatch) | requires a **fresh** clearance request |
| `SUPERSEDED` | Workflow Service | previous receipt unusable; use the new one |
| `REVOKED_BY_UPSTREAM_CHANGE` | Workflow Service (on upstream signal) | requires re-authorization and fresh clearance |
| reservation / consumption | execution ledger | atomic; not a receipt transition |

A `HOLD` result is retried by re-evaluating with refreshed signals (a new evaluation, possibly a new
`CLEAR`). A `BLOCK`/`ESCALATE` is not retried on the same inputs; it requires fixing the mismatch or a
human/upstream action first.
