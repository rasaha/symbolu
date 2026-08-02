# Shadow Pilot

> A bounded, manually/batch-invoked pilot that evaluates read-only enterprise
> signals against the *unchanged* Action Clearance shadow stage, records durable
> pilot results, and produces an offline-verifiable report. It is **allowlist-based**
> and a successful pilot does **not** enable execution. Machine-readable companion:
> `docs/pilot_config_schema.json`.

## Configuration (allowlist-based)

`ShadowPilotConfig` binds pilot identity, allowed repositories/branches/workflow
modes/adapters, required signal types, the evaluation profile + intervention
routing refs, the evaluation window, `maximum_evaluations`, retention category,
reviewer-feedback settings, reporting interval, and acceptance thresholds. A
repository not explicitly allowed is never evaluated.

## Execution model

`ShadowPilotRunner.run_evaluation` (and `run_batch`) for a workflow already at
`ACTION_EVALUATED`:

1. build a read-only `AdapterRequest` from `pilot_change_context`,
2. collect each allowed, registered adapter (read-only, data only),
3. normalize results into the existing snapshot + source projection,
4. persist the adapter request + results durably,
5. drive the unchanged clearance stage (`record_operational_snapshot` →
   `evaluate_action_clearance_shadow` → `assess_human_intervention`),
6. build + persist an immutable `ShadowPilotEvaluationRecord`.

The runner never creates the binding DecisionRecord, overrides ActionGate, executes
a merge, mutates GitHub, auto-retries authoritative governance decisions, or changes
policy. Execution stays `DISABLED`.

## Durable persistence

Pilot records live in the **same** 1C durable store (no second database), under a
dedicated hash-linked `pilot:<pilot_id>` lineage: adapter requests, adapter
results, evaluation records, reviewer feedback, metric snapshots, and reports. Same
id + same content is idempotent; same id + different content is an integrity error.

## Restart safety + staleness

Pilot collection is restart-safe: an unpersisted source call is never assumed to
have succeeded, external calls are never auto-repeated on restart, prior adapter
attempts are preserved, and continuation is an explicit caller action. Before/after
collection the requested repository/PR/base/head/prepared-action identity is
verified; a changed GitHub head marks the pilot evaluation **stale** and requires a
new workflow revision while preserving the historical chain.

## Reporting

`snapshot_metrics` and `export_report` compute + durably persist a metric snapshot
and a deterministic, offline-verifiable pilot report (see
`CODE_GOVERNANCE_PILOT_METRICS.md`). A pilot status of
`MEETS_CONFIGURED_THRESHOLDS` is a *configured-threshold* result, not enforcement
readiness.
