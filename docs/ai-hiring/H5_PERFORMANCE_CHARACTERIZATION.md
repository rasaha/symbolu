# H5 — Performance Characterization (local, descriptive)

Measured with `ai_hiring/validation/performance.py` on a local single process with
deterministic in-memory providers/adapters. **These are not production-scale claims.**

## Full-lifecycle case (evidence → reconciliation), repeats=3–5
| Metric | Value (representative) |
|---|---|
| median | ~0.0024 s |
| p95 | ~0.0026 s |
| max | ~0.0026 s |
| stdev | ~0.0002 s |

## Bounded batch (12-case cohort)
Audit growth is bounded and linear-ish in cases: hiring + kernel audit event counts grow
per case with no unbounded accumulation (`test_batch_audit_growth_is_bounded`).

## Environment & caveats
Local, single-process, in-memory repositories, deterministic providers/adapters, fixed
grants. Sample sizes are small and illustrative. Stage-level latencies (synthesis, claim
evaluation, generation, authorization, execution, reconciliation, reconstruction) are all
sub-millisecond at this scale. **No throughput, concurrency-at-scale, or production-latency
claim is made or implied.**
