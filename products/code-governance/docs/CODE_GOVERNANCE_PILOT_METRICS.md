# Pilot Metrics

> Deterministic metrics over a **fixed** pilot record set. Metrics are a *profile*,
> never a single blended safety score, and mandatory failures stay individually
> visible. Machine-readable companion: `docs/pilot_metrics_schema.json`.

## Metric profile

- **Clearance distribution** — CLEAR / HOLD / BLOCK / ESCALATE counts + rates.
- **Intervention** — human-intervention-required count + rate.
- **Adapter reliability** — success / failure counts + failure rate.
- **Source-data quality** — stale-signal rate, source-conflict rate,
  artifact-mismatch rate.
- **Human agreement** — reviewer-feedback coverage, agreement rate, status- and
  intervention-disagreement rates.
- **Policy quality** — source-data-error rate, policy-configuration-issue rate.
- **Possible error categories** — possible false HOLD / BLOCK / ESCALATE and
  possible missed escalation.

## Honest reporting

- No single aggregate "safety score" is produced.
- No precision/recall/accuracy is claimed — there is no independently established
  labelled outcome set in MVP 1D, so reviewer-derived error categories are prefixed
  **possible** until ground truth is established.
- `INSUFFICIENT_DATA` is reported honestly when the record set is too small.

## Thresholds + status

`PilotThresholds` are configuration, not universal truth. `evaluate_pilot_status`
maps a profile to one of:

- `INSUFFICIENT_DATA`
- `MEETS_CONFIGURED_THRESHOLDS`
- `DOES_NOT_MEET_CONFIGURED_THRESHOLDS`
- `INTEGRITY_FAILURE`

A successful pilot does **not** enable execution automatically. The metric
fingerprint is content-addressed and stable for a fixed record set, so the same
inputs always yield the same profile.
