# Historical-Replay Readiness Checklist (H1–H8)

Historical replay must not begin until these synthetic readiness gates pass. Run
them with `python3 -m ugence_storygraph.cli readiness`
(`evaluation/readiness.py`). Thresholds are **frozen before the final run** and
are experimental development thresholds — **not** universal enterprise standards.

| Gate | Requirement | How it is checked |
|------|-------------|-------------------|
| **H1 — freeze integrity** | official final evaluation refuses changed inputs; dev profile/thresholds cannot produce an official verdict | `freeze.require_frozen` accepts unchanged, refuses tampered + dev profile |
| **H2 — deterministic replay** | repeated runs produce identical findings + digests | replay a generated corpus twice; compare escalation finding_ids |
| **H3 — durable reconstruction** | restart + recovery preserve reconstructability | durable SQLite audit → reopen → replay-recover → digests match live |
| **H4 — bounded-state safety** | sustained overload is fail-visible and tenant-isolated | per-tenant cap breach → `UNAVAILABLE`; other tenant unaffected |
| **H5 — provider safety** | untrusted/stale/revoked/conflicting/unavailable context never silently neutralizes | provider-failure modes keep the escalation |
| **H6 — ordering safety** | ambiguous/conflicting order cannot satisfy a strict recipe without explicit policy | conflicting order → no escalation, `order_conflicting` counted |
| **H7 — operational performance** | runtime/state within pre-registered dev thresholds | load benchmark p95 ≤ frozen threshold |
| **H8 — realistic benign burden** | enterprise-like prevalence produces false-escalation burden below the pre-registered threshold | alert-volume false-escalation rate ≤ threshold |

## Pre-registered thresholds (frozen — `evaluation/freeze.py`)

- `max_p95_runtime_ms_per_event = 5.0`
- `max_false_escalation_rate = 0.02`
- `max_alerts_per_1000_events_enterprise_like = 60.0`
- `min_true_positive_rate_encoded = 0.90`

These are development thresholds for this experiment only. They must be frozen
before the final run and must not be tuned against the `final` corpus split.

## Verdict

`readiness.run()` returns exactly one verdict. This phase caps at
**`CONTINUE — historical replay ready`** unless actual sanitized historical data
is supplied and evaluated. It never issues production-ready / enterprise-validated
/ threat-detection-validated / enforcement-ready.
