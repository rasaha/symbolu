# Pilot Observability

> Structured, redacted logs + operator-level metrics, kept separate from
> clearance-quality metrics. Machine-readable companion:
> `docs/operator_metrics_schema.json`.

## Structured logging

Logs are JSON-compatible dicts with stable event types + reason codes and pilot
correlation fields (`pilot_id`, `run_id`, `tenant_id`, `workflow_id`/
`workflow_revision_id` when applicable, `adapter_id`, `source_id`, `event_type`,
`status`, `reason_code`, `correlation`). Central redaction removes credential
values (case- and separator-insensitive; `authorization`, `token`, `access_token`,
`api_key`, `secret`, `private_key`, `credential`, `password`, …) while preserving
legitimate fields like `token_count`, `secret_scanner_result`, and
`credential_policy_ref`. Prohibited payloads (raw GitHub bodies, raw identity
profiles, private incident notes, source code) are dropped entirely.

## Operator metrics

Lifecycle status, evaluations attempted/completed/skipped/stale, adapter
calls/successes/failures/retries, rate-limit events, timeouts, integrity/preflight
failures, review-queue size, feedback completion, average durations, last
successful collection/evaluation, stop-condition and kill-switch activations. These
are a profile, not one blended score, and are kept separate from CLEAR/HOLD/BLOCK/
ESCALATE quality metrics.
