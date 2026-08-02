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

---

# Pilot Study Metrics (MVP 1F)

The MVP 1F validation study extends these pilot metrics with study-level analysis
that keeps evidence classes strictly separate and produces no unsupported
statistics.

## Groups (reported separately, never blended)

- **Coverage** — candidates identified/selected, evaluations attempted/completed,
  reviewer feedback requested/completed/missing, evidence-class + cohort coverage.
- **Clearance distribution** — CLEAR/HOLD/BLOCK/ESCALATE, kept separate for **live**
  (`LIVE_GITHUB_METADATA` / `LIVE_ENTERPRISE_SIGNAL`) vs **non-live** evidence.
- **Intervention quality** — reviewer disagreement rate, possible unnecessary /
  possible missed intervention counts, wrong-authority count, unresolved count.
- **Source quality** — failures, stale signals, conflicts, identity mismatches,
  supplied-snapshot dependence.
- **Policy quality** — policy defects, possible overly strict/lenient, before/after
  amendment separation.
- **Incremental value** — unique-signal cases (with evidence), duplicate-CI-control
  cases, no-incremental-value cases.
- **Operational quality** — latency/retry/timeout/restart/integrity/kill-switch,
  report verification, credential-leak count, write-boundary violations.

## No unsupported statistical claims

No precision/recall/false-positive-rate/sensitivity/specificity/accuracy is produced
without a defensible ground-truth protocol, explicit denominators, documented
sampling, handled missing data, and reported uncertainty. Synthetic and supplied-
snapshot results are never aggregated into a metric presented as live enterprise
performance. Small-sample findings are not overstated: every output carries
numerator, denominator, missing data, excluded cases, evidence class, cohort,
protocol, and limitations.
