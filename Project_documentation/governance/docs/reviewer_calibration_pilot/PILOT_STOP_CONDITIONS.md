# Pilot Stop Conditions (Phase 12)

*`reviewer_calibration_pilot/stop_conditions.py`. Immediate conditions halt instantly; cumulative
criteria breach frozen thresholds. Fail-closed. Thresholds frozen before any outcome-bearing review.*

## Immediate stop conditions (any one halts the pilot)

enforcement attempt · external action execution · unauthorized data exposure · sensitive-data leakage ·
audit failure · reviewer identity leakage · unrecorded reviewer override · policy drift · component drift
· kill-switch failure · native ActionGate semantic loss · repeated high-risk unsafe system allows ·
repeated high-risk reviewer disagreement · undeletable pilot data.

`check_immediate` is fail-closed: an unknown or erroring signal is treated as fired.

## Cumulative stop criteria (frozen thresholds)

| Criterion | Threshold |
|---|---|
| unsafe-allow disagreement rate | > 0.02 |
| high-risk obligation agreement | < 0.80 |
| reviewer workload | > 40 artifacts/hour |
| unresolved rate | > 0.20 |
| stricter override rate | > 0.40 |
| explanation usefulness (1–5) | < 2.5 |
| missing-context rate | > 0.25 |

`check_cumulative` fires only when human metrics are `COMPUTED`; with `NOT_ENOUGH_HUMAN_EVIDENCE` there
is nothing to breach, so no cumulative criterion fires.

## Freeze rule

The thresholds above are frozen (Phase 15 `verify_evaluation_freeze.py`) before outcome-bearing review
and are not altered after review begins.

## Dry-run verification

The dry run (`dry_run.py`) exercises the stop machinery on the training set with a **mock** reviewer:
no immediate signal fires, the mock metrics are `NOT_ENOUGH_HUMAN_EVIDENCE` (mock records excluded, never
validation), and `should_stop` is False on the clean run — confirming the machinery evaluates correctly
without ever treating mock output as human evidence.
