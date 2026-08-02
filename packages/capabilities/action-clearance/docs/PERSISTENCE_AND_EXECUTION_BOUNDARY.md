# Persistence and Execution Boundary

**The package persists nothing and executes nothing.**

Not implemented here (by design):

- `ClearanceReceiptRepository`, `WorkflowRepository`, `ExecutionReservationRepository`;
- any database model, SQL migration, file store, or network store;
- `reserve_once` or any atomic one-time reservation;
- any dispatch/execute/merge method.

The package may construct the neutral immutable `ClearanceReceiptBody` (the
content-addressed evaluator partition), but it never persists it and never mutates
its lifecycle. Receipt lifecycle states (`ISSUED`/`EXPIRED`/`SUPERSEDED`/`REVOKED`/
`INVALIDATED`) belong to the **Workflow Service**, not the evaluator.

One-time-use is **downstream**. The evaluator reads a `PRIOR_CONSUMPTION` signal
(`UNUSED`/`RESERVED`/`CONSUMED`/`UNKNOWN`) as **advisory** input from the
authoritative execution/idempotency ledger: `UNUSED` may continue, `RESERVED`
holds/blocks by policy, `CONSUMED` blocks, `UNKNOWN` fails closed. The evaluator
never atomically owns consumption.

`CLEAR` is **not execution.** It means: execution *could* proceed later only if the
downstream execution boundary validates a current receipt and acquires a
reservation. Enforcement remains blocked on durable receipt storage and atomic
reservation, which are out of scope for this phase.
