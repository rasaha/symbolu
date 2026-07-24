# Performance & Load (M10)

*`customer_shadow_readiness/perf_load.py` → `results/perf_load.json` (not hash-pinned — wall-clock
varies per run). Actual wall-clock latency of the governance stages, bounded cost/storage, and a
load/concurrency test that verifies throughput **and tenant isolation under concurrent load**.*

## Wall-clock latency (the pilot's flagged gap, now measured)

The completed pilot reported latency in deterministic units and flagged real wall-clock as PARTIAL.
Measured here over 200 requests through the full read-only runtime via the pilot API:

| Metric | Value |
|---|--:|
| median | 0.40 ms |
| p90 | ~0.5 ms |
| p95 | 0.53 ms |
| p99 | ~1 ms |
| max | 2.9 ms |

**Governance-stage latency is sub-millisecond at the median.** This is the actual overhead the control
plane adds. Critically, it **excludes the model call** — in production, latency and cost are dominated by
the model inference the pilot deliberately does not make (fixture mode). The governance overhead is not
the latency barrier.

## Cost & storage

- **Mean minimized+redacted record: ~422 bytes** → ~0.4 MB per 1000 requests. Storage scales linearly
  and is bounded by the per-tenant retention cap (M5).
- **Governance token cost ≈ $0** — the stages carry no token cost; production cost is the model call,
  which is not made here.

## Load & concurrency (the pilot's missing dimension)

100 requests across **two tenants** submitted concurrently through 8 workers:

| Metric | Value |
|---|--:|
| throughput | ~2120 req/s |
| cross-tenant leaks | **0** |
| isolation held under concurrency | **yes** |
| all accepted | yes |

The isolation check is the important one: under concurrent multi-tenant load, **no response was scoped
to the wrong tenant** — the tenant isolation (M4) holds under concurrency, not just serially. Throughput
(~2k rps on governance stages) is far above any bounded-pilot load; the real ceiling in production is
model-call concurrency, out of scope here.

## Scope honesty

These are **local, single-process** measurements of the governance stages in fixture mode. They are
**not** production capacity numbers: no distributed deployment, no real model latency, no network, no
sustained soak test. What they establish for a bounded pilot: governance overhead is sub-millisecond,
storage is small and bounded, and tenant isolation survives concurrent load. Real end-to-end latency and
throughput (with model calls and network) remain a NOT-EVALUATED production dimension, stated as such.
