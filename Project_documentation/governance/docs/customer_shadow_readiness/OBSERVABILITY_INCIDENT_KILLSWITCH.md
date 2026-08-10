# Observability, Incident Response & Kill Switches (M7)

*`customer_shadow_readiness/observability.py`, `incident.py`, `killswitch.py`. Tenant-scoped metrics and
alerting over shadow runs, an incident taxonomy that ties detection to the kill switches, and pilot-wide
+ tenant-level kill switches. All in-memory, no external sink, no PII, shadow-only.*

## Observability

`Metrics` aggregates **dispositions and reason-code namespaces per tenant** — never artifact text. It
exposes `tenant_summary` (totals, disposition mix, allow-rate, top reason namespaces) and
`pilot_summary`. Events carry only `{tenant, disposition, accepted}`. This gives operators a live picture
of the shadow runtime without touching customer content — observability that respects the data controls.

`alerts(metrics, tenant)` emits detection signals:

- `ALERT.HIGH_ALLOW_RATE` — ≥10 runs and >90% allow (possible governance bypass or risk mis-tiering);
- `ALERT.HIGH_CONTRACT_ERROR` — >20% contract errors (integration/adapter problem);
- `ALERT.PIPELINE_ERROR` — any pipeline error.

## Incident taxonomy & response

`incident.py` maps a signal to a **severity** and a **response**:

| Signal | Severity | Response |
|---|---|---|
| `SEC.CROSS_TENANT_DENIED` / `SEC.CROSS_TENANT_CASE` | SEV1 (isolation breach) | **trip tenant kill** |
| `unsafe_action_escape` | SEV1 (safety) | **trip pilot-wide kill** |
| `ALERT.HIGH_ALLOW_RATE` | SEV2 (governance degradation) | page on-call |
| `ALERT.HIGH_CONTRACT_ERROR` / `ALERT.PIPELINE_ERROR` | SEV3 (integration) | page on-call |
| `replay_nondeterminism` | SEV2 | freeze & investigate |

`handle(signal, tenant)` executes the response — a SEV1 isolation signal **disables the offending
tenant**, and a SEV1 safety signal **engages the pilot-wide kill**. Detection is wired to containment,
not just logging.

## Kill switches (fail-closed)

`killswitch.py` provides `trip_pilot` / `restore_pilot` and `trip_tenant` / `restore_tenant`. The pilot
API checks them **first**, before authentication — a tripped switch refuses all new work with `KILL.*`
and the runtime accepts nothing. This is the operator's emergency stop: one call halts a single tenant or
the entire pilot, fail-closed.

## Runbook (shadow pilot)

1. **SEV1 isolation** (cross-tenant): tenant auto-disabled → confirm scope → purge tenant data
   (`data_controls.TenantDataStore.delete_tenant`) → root-cause the reference → restore only after fix.
2. **SEV1 safety** (unsafe action/assertion escape): pilot-wide kill auto-engaged → freeze, capture the
   trace (deterministic replay signature) → diff against the frozen baseline → restore only after the
   escape is explained and closed.
3. **SEV2/3**: page on-call, investigate via the audit trace + replay; the pilot keeps running unless the
   rate crosses a kill threshold.

## Scope honesty

This is **shadow-pilot** observability and incident response: in-memory metrics, rule-based alerts, and
kill switches sufficient to run and safely halt a bounded pilot. It is **not** production observability —
no metrics backend, tracing system, SIEM, PagerDuty integration, or 24/7 on-call. Those are
NOT-EVALUATED production dimensions; the kill switches and runbook make the *containment* story real for
a bounded pilot.
