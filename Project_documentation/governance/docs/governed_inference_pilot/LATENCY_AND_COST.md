# Latency & Cost Study (Phase 20)

*`governed_inference_pilot/cascade_analysis.py`. Latency is measured in **deterministic units**, not
wall-clock — local fixture timings are not production latency, and this study does not present them as
such. Cost is a token-based proxy over fixture prices.*

## Why units, not milliseconds

The runtime is deterministic (no wall-clock, no randomness) so traces reproduce byte-for-byte. Reporting
wall-clock local timings would (a) break determinism and (b) misrepresent production latency, which is
dominated by the model-execution call the pilot deliberately replaces with a fixture. Latency is
therefore a **relative unit cost per stage**, useful for comparing configurations, not for capacity
planning.

## Per-stage latency (units)

Each stage costs a fixed unit count (ExecutionGate/ModelPolicy 1, model execution 2, ClaimIntegrity/
ScopeIntegrity/EvidenceAssurance/AssertionGate/ActionGate 1, audit 1). Full-stack totals:

| Metric | Value (units) |
|---|--:|
| median total | 6 |
| p90 | 7 |
| p95 | 7 |
| max | 7 |

The full stack adds a small, bounded overhead over the minimum configuration; the distinction between
configurations is a handful of units, dominated in production by the (fixture-replaced) model call.

## Cost

Cost is a token proxy: `(tok_in·price_in + tok_out·price_out)/1e6`. In fixture mode over these short
artifacts, the mean per-request cost rounds to **~0** at 8 decimals — the governance stages themselves
carry negligible token cost; the real cost in production is the model call, which the pilot does not
make. The governance overhead cost is therefore **not** the barrier to deployment; latency of the added
stages is small and cost is dominated entirely by the model inference the control plane wraps.

## Storage per trace

A full-stack trace holds ~6–8 immutable event records plus request/version metadata. Storage scales
linearly with stage count and with claim/evidence counts; no super-linear blow-up was observed. The
redacted operator view is a strict subset (source/transformed representations elided).

## Honest caveat

These numbers establish **relative** overhead and determinism, not production latency or cost. A live
pilot must re-measure wall-clock latency with real model calls and real retrieval; that measurement is
explicitly out of scope here (no live provider calls) and is listed as a product-readiness gap
(Phase 28).
