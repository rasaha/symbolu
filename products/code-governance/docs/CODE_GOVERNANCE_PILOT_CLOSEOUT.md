# Pilot Closeout

> An explicit closeout stops further evaluations, persists final state, and
> produces an offline-verifiable report + operator metrics. Closeout does **not**
> enable enforcement.

## What closeout does

`op.closeout(at)`:

1. transitions ACTIVE/PAUSED → STOPPING,
2. calculates final clearance-quality metrics + exports the deterministic pilot
   report and verifies it offline,
3. persists an operator-metrics snapshot,
4. transitions STOPPING → COMPLETED,
5. inventories unresolved reviewer-queue items + missing feedback,
6. records limitations and reports `execution_status == "DISABLED"`.

## Readiness indicators (configurable, not universal)

100% execution-disabled invariant · 100% audit reconstruction completeness · 0
credential leaks · 0 read-only boundary violations · 0 unexplained integrity
failures · acceptable adapter source-failure and stale-signal rates · reviewer
feedback coverage above the configured minimum · reviewer disagreement categorized
and investigated · all escalations routed to a configured authority. There is no
single universal acceptance threshold, and a pilot that meets thresholds remains
shadow-only.
