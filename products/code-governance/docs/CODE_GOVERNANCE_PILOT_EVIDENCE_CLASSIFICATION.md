# Pilot Evidence Classification

> Every pilot evaluation and metric identifies the evidence class used. Supplied
> snapshots and synthetic scenarios are NEVER described as real enterprise
> evidence. Machine-readable companion: `docs/pilot_evidence_classes.json`.

## Classes

`LIVE_GITHUB_METADATA` · `LIVE_ENTERPRISE_SIGNAL` · `SUPPLIED_ENTERPRISE_SNAPSHOT` ·
`HISTORICAL_REPLAY` · `SYNTHETIC_CONTROL` · `REVIEWER_FEEDBACK` ·
`OPERATIONAL_OBSERVATION`.

Only `LIVE_GITHUB_METADATA` and `LIVE_ENTERPRISE_SIGNAL` count as *live* enterprise
performance. `analyze_pilot_results` keeps a live clearance distribution strictly
separate from a non-live one; synthetic/supplied/replay results are never folded
into a live metric.

## Reporting separation

Reports separate real GitHub metadata, real external enterprise signals, supplied
snapshots, historical replay, synthetic control scenarios, and reviewer feedback.
`LIVE_ENTERPRISE_SIGNAL_COUNT` and `SUPPLIED_ENTERPRISE_SNAPSHOT_COUNT` are reported
distinctly. A pilot using only live GitHub plus supplied enterprise snapshots
validates GitHub integration + workflow usability but does not fully validate
cross-system enterprise reliability, and says so.
