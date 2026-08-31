# Latency, Cost & Reviewer Burden (Phases 15–16)

*`bounded_shadow_pilot/perf_cost_burden.py` → `eval_results/perf_cost_burden.json`. Governance overhead
on natural artifacts (never the model call, which the pilot does not make) and the human-review burden
the runtime would impose on natural traffic.*

## Governance latency

| Measure | Value |
|---|---|
| Deterministic latency units — median / p95 / max | 6 / 7 / 7 |
| Wall-clock governance (live, not frozen) — median / p95 | 0.72 ms / 1.84 ms |

Governance is **sub-millisecond** per artifact and excludes the model call by construction. The frozen
artifact stores only the deterministic units; wall-clock is live instrumentation (never a decision
input, never frozen) so the JSON stays byte-reproducible.

## Cost & storage

| Measure | Value |
|---|---|
| Governance cost, total / per-artifact | **$0.00** / $0.00 |
| Minimized record size | 272 bytes/artifact |

Governance makes **no provider call**, so its marginal cost is ~$0. The real cost is the **un-made model
call**, which is explicitly out of scope. Shadow records are data-minimized (dispositions + reason codes
+ replay signature only — no artifact text).

## Reviewer burden

| Measure | Value |
|---|---|
| Artifacts routed to human review | **99 / 857 (11.6%)** |
| By disposition | EVIDENCE_UNAVAILABLE 67 · WOULD_ESCALATE 27 · INDETERMINATE 3 · WOULD_QUALIFY(review-required) 2 |

Over-qualified deliveries (85.5%) do **not** add review burden — they deliver with caveats. Burden comes
from withholds, escalations, and indeterminate outcomes. On natural traffic the runtime would send
roughly **1 in 9** artifacts to a human reviewer.

## Reading

The operational picture on natural artifacts is: **negligible latency, negligible governance cost, but a
real 11.6% reviewer burden layered on top of 85.5% over-qualification.** The bottleneck to a useful
natural-artifact pilot is not performance or cost — it is calibration/utility (the over-qualification
finding of Phase 14), which drives both the low clean-allow rate and a non-trivial review load.
