# Live Shadow Dry-Run Report (mock-only)

*Phase 15. Implementation validation of the shadow harness — **NOT live scientific evidence.**
No credentials, no network, $0 spend. Reproducible: `python3 -m execution_gate_shadow.dry_run`.*

## Scenarios (8, mock)

healthy · network denial · quota exhaustion · provider degradation · provider recovery (stale
cache) · policy-prohibited-but-successful · stale-evidence false-eligible risk · no-eligible
(not attempted).

## Results (mock)

| Metric | Value |
|---|---|
| predictions / observations / joined | 8 / 8 / 8 |
| attempted (in confusion matrix) | 7 |
| TP / TN / FN / FP | 1 / 4 / 2 / 0 |
| eligibility precision | 1.00 |
| eligibility recall | 0.33 |
| **false-eligible rate** | **0.00** |
| **false-eligible critical (compliance)** | **0** |
| false-ineligible / rate | 2 / 0.286 |
| indeterminate rate | 0.25 |
| spend / live requests / quota calls | $0.00 / 0 / 0 |

## What the dry run validates

- **Prediction/observation separation:** a contradictory observation never alters the recorded
  prediction (separate append-only JSONL logs; verified by test).
- **Critical-policy precedence:** the prohibited-but-successful provider is excluded by the gate
  (TN) → **zero critical false-eligible**; had it been allowed, it would count as critical
  false-eligible.
- **Honest false-ineligibility:** the degraded-but-working and recovered-but-stale providers are
  excluded (INELIGIBLE/INDETERMINATE) → FN=2, recall 0.33 — the real cost of caution, surfaced not
  hidden.
- **NOT_ATTEMPTED handling:** the no-eligible scenario is recorded unverified and excluded from the
  confusion matrix (never presumed success or failure).
- **Determinism:** two runs produce byte-identical prediction-log hashes and identical metrics.
- **Safety:** live calls disabled, $0 spend, 0 live requests; append-only audit; redaction.

## What it does NOT establish

These numbers come from constructed ground truth, not live providers. False-eligible/ineligible
*rates* on real traffic, TTL behavior, detection/recovery lag, and probe cost are all
**unmeasured** until a live study runs under `LIVE_SHADOW_PILOT_PROTOCOL.md`. The dry run proves the
machine works, not that the gate is accurate in production.
