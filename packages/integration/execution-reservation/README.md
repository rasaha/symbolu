# ugence-execution-reservation

**Reference-grade, shadow-only, not enforcement-ready.** Durable clearance receipts,
atomic one-time execution reservation, and the `PRIOR_CONSUMPTION` trusted signal,
built as the durable backend of the Decision Authority execution ledger. Scoped and
ratified by `docs/architecture/ADR_UGENCE_EXECUTION_RESERVATION_SCOPING.md`; closes
Action Clearance phases E and G from `packages/capabilities/action-clearance/docs/NEXT_PHASES.md`.

> This package reserves, records and reports consumption. It never dispatches,
> observes an external system, or mints authority. `CLEAR` plus `ACQUIRED` is
> still not execution.

## What one adapter implements

| Port | Phase | What it owns |
|---|---|---|
| `ClearanceReceiptRepository` | E | content-addressed receipt records, append-only lifecycle events, derived expiry, supersession by lineage, revocation, invalidation |
| `ExecutionReservationPort` | G | `reserve_once` with exactly one `ACQUIRED` per execution key, the nine-state reservation machine, forward-only observations and reconciliation |
| `PriorConsumptionSource` | G | the `PRIOR_CONSUMPTION` `TrustedSignal` Action Clearance consumes, at trust Level 1 |
| Decision Authority `ExecutionRepository` | — | structural conformance, so intents, attempts, records, reconciliations and compensations live in the same store and no third ledger exists |

Two adapters: `InMemoryExecutionReservationStore` (tests; refused in production
mode; composes the kernel's own reference repository) and
`SqliteExecutionReservationStore` (decision D-3: single-node stdlib `sqlite3`, WAL,
`BEGIN IMMEDIATE`, unique head per key, one append-only hash-linked
`ledger_events` table with triggers refusing UPDATE and DELETE). The shape is
that of the storygraph durable audit log, copied, never imported.

## The execution key

`ExecutionKey(tenant_id, authorization_ref, authorized_action_fingerprint, target_ref, operation)`,
serialized `exec_key.v1:<sha256hex>`. The receipt reference is deliberately not in
it: a re-issued receipt for the same action must map to the same key. Neutral
projection: `IdempotencyKey(key=<serialized>, scope=GLOBAL, partition=tenant_id)`;
`neutral_idempotency_digest()` is what goes in `ExecutionDispatchRequest.idempotency_key`.

## Reservation semantics

`reserve_once(execution_key, clearance_receipt_ref, expected_authorization_ref,
expected_action_fingerprint, reservation_ttl_s, *, as_of)` validates checks 1–9 of
the design over the immutable receipt and the caller's instant (missing, altered,
not CLEAR, wrong tenant / authorization / action / target / operation, never issued,
revoked → `STALE_AUTHORIZATION`, superseded or invalidated, expired →
`EXPIRED_CLEARANCE`) and then makes the only racing decision, the head insert,
inside one write transaction. Results: `ACQUIRED`, `ALREADY_RESERVED`,
`ALREADY_DISPATCHED`, `ALREADY_COMPLETED`, `CONFLICT`, `INVALID_RECEIPT`,
`EXPIRED_CLEARANCE`, `STALE_AUTHORIZATION`. `ReserveOnceOutcome.resolution`
projects to `IdempotencyResolution` (FIRST / DUPLICATE naming the holding
reservation / UNKNOWN); refusals project to `None`.

States: `AVAILABLE → RESERVED → DISPATCHED → {OBSERVED_SUCCESS, OBSERVED_FAILURE,
OUTCOME_UNCERTAIN} → {RECONCILED_SUCCESS, RECONCILED_FAILURE} → RELEASED`.
Observations and reconciliations move a reservation forward only, so any arrival
order converges and a terminal success is never downgraded. `DISPATCHED` and
`OUTCOME_UNCERTAIN` are never released. `RECONCILED_FAILURE` and `RELEASED` free
the key for a new generation. An abandoned pre-dispatch `RESERVED` whose lease
lapsed is released and re-acquired by the next caller.

Every instant is a caller input; nothing in the package reads a clock, and a test
asserts it over the AST.

## Consumption signal mapping

| Head state | `PRIOR_CONSUMPTION` |
|---|---|
| none, AVAILABLE, RELEASED, RECONCILED_FAILURE, abandoned RESERVED | UNUSED |
| RESERVED, DISPATCHED, OBSERVED_FAILURE, OUTCOME_UNCERTAIN | RESERVED |
| OBSERVED_SUCCESS, RECONCILED_SUCCESS | CONSUMED |
| store unavailable | UNKNOWN, and `SignalStatus.UNKNOWN` |

## Maturity (no overclaim)

Reference-grade and shadow-only. Enforcement stays gated (decision D-4): the
signal is Level 1 because no key service exists for Level 2, and reconciliation
beyond the Decision Authority reference reconciler is unbuilt. Persistence is
single-node; distributed strong consistency is disclaimed. No Workflow Service
exists as code, so receipt lifecycle *detection* of upstream events (revocation,
supersession triggers) is a caller responsibility; this package records them.
Prerequisites scenarios 16 (chain reconstruction) and 24 (freeze after issuance)
belong to the execution boundary and the evaluator, not to this package.

Decision Authority conformance is proved **behaviourally**: the kernel's own
conformance kit asserts repositories are kernel types by module, which a foreign
adapter cannot satisfy by construction, so the tests run one operation sequence
against the kernel's `InMemoryExecutionRepository` and both adapters and assert
identical values and exception classes.

## Develop / test

```bash
pip install pytest pydantic   # pydantic is Decision Authority's, not ours
python -m pytest packages/integration/execution-reservation -q
```

Tests cover prerequisites scenarios 11–15, 17–23, 25 and 26–38 on both adapters, a
threads-per-connection and a processes-per-connection proof that exactly one
caller acquires, the ratified consumption mapping, an end-to-end run through the
real Action Clearance evaluator (CLEAR → HOLD on `CONSUMPTION_RESERVED` → BLOCK on
`ALREADY_CONSUMED` → fail closed on outage), Decision Authority parity, the
import boundary, the clock-free rule, production-mode refusal, and the append-only
hash chain.
