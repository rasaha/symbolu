# Time & Freshness

Action Clearance is time-sensitive. All time is explicit and caller-supplied; the core reads no clock.

## Rules

- **Evaluation time is caller-supplied** (`request.evaluation_time`). The core contains **no**
  `datetime.now()` / `time.time()` (only excluded latency telemetry, if any, lives outside the core).
- **Signal capture time** (`captured_at`) and **signal validity window** (`valid_until`) are supplied on
  each `TrustedSignal`.
- **Authorization validity window**: `authorization.issued_at … authorization.expires_at`.
- **Clearance validity window**: `evaluated_at … valid_until`.
- **Maximum clearance lifetime**: `valid_until ≤ evaluated_at + policy.max_clearance_lifetime_s`.

## Bounding relations (enforced)

```text
clearance.valid_until ≤ authorization.expires_at
clearance.valid_until ≤ min(required-signal valid_until)
clearance.valid_until ≤ evaluated_at + policy.max_clearance_lifetime_s
```

Clearance may **shorten** but never **extend** authorization validity. `valid_until` is the minimum of
all three bounds.

## Expiry comparison & boundary behavior

- Expiry is a strict comparison against `evaluation_time`:
  `authorization_expired ⟺ authorization.expires_at < evaluation_time`.
- **Boundary at exact expiry** (`expires_at == evaluation_time`): treated as **expired** (fail closed;
  the instant of expiry is not clear). Same rule for signal `valid_until`.

## Stale-signal policy

A signal is stale when `captured_at < evaluation_time − policy.freshness_window(signal_type)` or when
`valid_until < evaluation_time`. Stale required signals contribute `SIGNAL_STALE` → `HOLD` (policy may
elevate a class to `BLOCK`).

## Clock-skew policy

`policy.clock_skew_tolerance_s` widens only the **freshness** comparisons (a signal captured slightly in
the future within tolerance is accepted), never the **expiry** comparisons — expiry is always strict, so
skew can never make an expired authorization look valid.

## Missing validity bound on a required signal

If a required signal has no trustworthy `valid_until` (and its type is policy-marked time-bounded), the
evaluator **fails closed**: it cannot compute the clearance window safely →
`SIGNAL_STALE` (treated as unbounded-staleness) → `HOLD`. The core never invents a validity bound.
