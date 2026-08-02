# Pilot Calibration

> Calibration produces *recommendations*, never automatic policy changes. Machine-
> readable companion: `docs/pilot_calibration_schema.json`.

## Recommendations

`generate_calibration_recommendations` groups recurring reviewer disagreements by
root cause into a `PilotCalibrationRecommendation` bound to its supporting
evaluations, with a proposed adjustment (signal-requirement / freshness-window /
trust-threshold / status-precedence / intervention-routing / authority-mapping /
cohort-specific / adapter-repair / more-evidence-required), an expected effect, a
stated risk, and `requires_new_pilot_revision = True`. It does **not** modify active
policy and has no `apply` method.

## Replay

`replay_pilot_policy` re-scores completed evaluations against a proposed policy
candidate using **persisted facts only**. It never overwrites the original results,
makes no external call, records the policy-candidate fingerprint, reports original
vs replayed side by side, and is always labelled `HISTORICAL_REPLAY` — never
presented as a real operational outcome.
