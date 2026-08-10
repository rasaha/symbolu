# PCAM Phase 3 — Measurement & Benchmark Proof

**Status:** Phase 3 complete for replay-only measurement. Real-runtime execution remains pending.
**Scope:** trace replay benchmark, baseline comparison, vLLM-facing demo, shared reporting helper.
**Contract:** [`docs/design/ADR-0001`](../../../../repository/docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md)
**Depends on:** Phase 0 (vendored reference), Phase 1 (public API), Phase 2 (vLLM adapter + trace replay primitive)

---

## What Phase 3 ships

Three benchmark scripts under `benchmarks/`, one shared reporting
helper under `simulator/pcam/`, and a focused test file:

| File | Role |
|---|---|
| `benchmarks/pcam_trace_replay.py` | Offline replay benchmark. Drives a deterministic trace through `KVCachePolicy` and prints a compact metrics report. |
| `benchmarks/pcam_compare_baselines.py` | Replay comparison of PCAM against inline LRU / LFU baselines on the same trace. |
| `benchmarks/pcam_vllm_demo.py` | Synthetic vLLM-shaped demo that exercises `PCAMEvictor` end-to-end without requiring `vllm` to be installed. |
| `simulator/pcam/_report.py` | Private reporting helper (`section_header`, `format_table`, `emit_json`). Not exported from the package root. |
| `simulator/pcam/tests/test_phase3_benchmarks.py` | 23 deterministic tests covering every script above. |

That's it. No new public API symbols, no new runtime integrations,
no new policies.

## Three realism tiers

The scripts are deliberately split along a honesty axis:

| Script | What it measures | Honesty label |
|---|---|---|
| `pcam_trace_replay.py` | Policy decisions on a deterministic trace | **Replay-only.** Reports what PCAM *would have decided*; does not measure real throughput, latency, or model quality. |
| `pcam_compare_baselines.py` | Side-by-side policy decisions vs inline LRU/LFU on the same trace | **Replay-only, synthetic baselines.** The baselines are minimal, sink-unaware reference heuristics — **not** published LRU/LFU/ARC/H2O/Streaming LLM implementations. |
| `pcam_vllm_demo.py` | `PCAMEvictor` driven through a vLLM-shaped workflow | **Synthetic walkthrough.** Attention events are hand-written, not extracted from a real forward pass. `--real-vllm` flag exists but currently raises `RealVLLMNotAvailable` — that path is Phase 4 work. |

The three labels appear in the scripts' disclaimers, in their
report output, and in every test that exercises them. **Nothing in
Phase 3 claims end-to-end model wins.** Running any of these
scripts prints a banner making the realism tier explicit; an
acquirer-facing demo can build on top of them, but the real-model
story belongs to Phase 4.

## What metrics are currently trustworthy

The following metrics are **real** (they reflect actual policy
behavior on the input trace):

- `evictions` — number of block_ids chosen by `select_victims`
- `filler_evictions` — number of evictions that took the filler fast path
- `sink_evictions` (baselines only) — sink blocks the baseline evicted
  that PCAM by construction never would
- `attention_weighted_cost` — sum of accumulated attention over evicted
  blocks; higher = worse
- `tier_distribution` — HOT/WARM/COLD/EVICT counts across all
  `tier_hints` calls on the trace
- Final `policy.get_stats()` snapshot (evictions, filler_evictions,
  total_blocks, gpu_blocks, pinned_blocks, active_sequences, step)

The following metrics are **not** exposed by Phase 3 and should
not be pulled from these scripts:

- Tokens/second, p50/p95/p99 latency, GPU memory high-water, time
  to first token, quality preservation vs ground truth. All of
  those require real model execution.
- Comparisons against named published systems (ARC, H2O, Streaming
  LLM). The inline baselines in `pcam_compare_baselines.py` are
  deliberately simple reference heuristics; they are not
  production-faithful reimplementations of those papers. The
  richer baselines at `simulator/pcam/baselines/` are built against
  the older controller API and would need a separate adapter pass
  before they can be driven from the Phase 1 trace path. That
  adapter is Phase 4 work.

## Quick start

```bash
# From the repo root — all three scripts work without any extra
# install step if you already have the repo on your PYTHONPATH.

python benchmarks/pcam_trace_replay.py
python benchmarks/pcam_trace_replay.py --max-blocks 512 --json /tmp/replay.json
python benchmarks/pcam_trace_replay.py --trace my_trace.json

python benchmarks/pcam_compare_baselines.py
python benchmarks/pcam_compare_baselines.py --json /tmp/compare.json

python benchmarks/pcam_vllm_demo.py
python benchmarks/pcam_vllm_demo.py --json /tmp/demo.json
python benchmarks/pcam_vllm_demo.py --real-vllm       # currently: error 2
```

All three scripts accept `--quiet` for JSON-only output and have
`--help` for the full CLI.

## Trace format

The scripts that accept `--trace` consume a JSON file shaped as
a list of `TraceEvent` dicts:

```json
[
  {"kind": "register_sequence", "args": {"seq_id": 1}},
  {"kind": "set_phase", "args": {"seq_id": 1, "phase": "DECODE"}},
  {"kind": "ensure_block", "args": {"block_id": 0, "sequence_id": 1, "positions": [0,1,2,3]}},
  {"kind": "on_block_attention", "args": {"block_id": 0, "attention_sum": 0.5, "sequence_id": 1}},
  {"kind": "select_victims", "args": {"count": 2}},
  {"kind": "tier_hints", "args": {"block_ids": [0, 1, 2]}},
  {"kind": "complete_sequence", "args": {"seq_id": 1}}
]
```

The schema is the same one defined in `simulator/pcam/trace.py`
and documented in the Phase 2 runbook. `TraceEvent.from_dict`
does the loading. No custom serializer is required.

If `--trace` is omitted, the built-in `build_demo_trace()` in
`pcam_trace_replay.py` is used. It is deterministic, parameter-free,
and exercises every event kind.

## Baseline comparison — what's apples-to-apples

`pcam_compare_baselines.py` runs PCAM, LRU, and LFU against the
same trace and the same `sink_tokens` threshold. The metrics are
constructed so the comparison is fair in these ways:

- All three sides see the same admission, attention, and
  eviction-request events.
- All three sides use the same notion of "sink block" — positions
  `< sink_tokens`. PCAM auto-derives this via `ensure_block`; the
  inline baselines compute the same set independently.
- `attention_weighted_cost` is summed over the same attention
  events regardless of which side evicted the block.

And **not** apples-to-apples in these ways, by design:

- The inline baselines don't understand phase (PREFILL/DECODE).
  Real-world LRU/LFU variants may or may not track phase.
- The inline baselines are not the published LRU/LFU papers.
  Don't quote "PCAM beats LRU" using these numbers in any context
  that suggests a head-to-head against production implementations.
- The comparison is over a single synthetic trace. Real workload
  traces would produce different relative rankings.

The goal of this script is to land a small, readable comparison
harness that a future phase can extend with real baselines and
real traces — not to generate acquisition-grade benchmark
tables today.

## The vLLM demo — what it proves and what it doesn't

`pcam_vllm_demo.py` instantiates a `PCAMEvictor` via
`PCAMEvictor.from_config(PCAMConfig(...))` and drives it through
a sequence of eight stages that mirror a real vLLM block-manager
workflow:

1. Evictor initialization from a `PCAMConfig`
2. `register_sequence(seq_id, phase=PREFILL)`
3. Sink block admission (positions 0..3) with a tracked fake
   `vllm.block.PhysicalTokenBlock` stand-in
4. Bulk filler-block admission + attention
5. Entity-block admission + high-attention events
6. `set_phase(seq_id, DECODE)` transition
7. `select_victims(count=6)` under memory pressure
8. `tier_hints(probe_ids)` for placement decisions
9. Final `PolicyMetrics.snapshot()`

Every stage is exercised by a test in `test_phase3_benchmarks.py`
and the transcript is deterministic: same inputs always produce
the same stage sequence. A reviewer can diff it byte-for-byte
across commits.

**What the demo proves:**

- `PCAMEvictor` can be driven through a vLLM-shaped workflow
  without importing `vllm`.
- Sink pinning works end-to-end (sink blocks classify as HOT and
  are excluded from victim lists).
- `select_victims_as_blocks` round-trips tracked vLLM block
  objects.
- `tier_hints` produces sensible placement recommendations.

**What the demo does NOT prove:**

- That PCAM improves real-model throughput. No model is executed.
- That the eviction decisions correlate with real attention
  patterns. The attention events are hand-written.
- That the integration bridge to the real `vllm.core.evictor.Evictor`
  ABC works on a specific vLLM release. That bridge is ~20 lines
  of consumer-side code; the docstring of
  `simulator/pcam/integrations/vllm.py` has a reference shape.

The `--real-vllm` flag currently raises `RealVLLMNotAvailable`
with an explicit message rather than silently falling back to the
synthetic path. This is deliberate: a user who asked for real-vLLM
numbers should never wonder whether the numbers came from a real
model or a hand-written trace. If you need real-vLLM execution,
that's Phase 4.

## Phase 3 explicitly does NOT add

- A Prometheus exporter, OpenTelemetry wiring, or any framework-
  specific metrics emitter. `_report.emit_json` is the only writer.
- A new config class. `PCAMConfig` (Phase 1) is the only policy
  config; the scripts take config knobs directly on the CLI.
- A new runtime integration. vLLM is still the only target.
- A benchmark-suite runner, CI integration with external dataset
  fetching, or a reporting dashboard.
- Any change to ADR-0001, the parity harness, the vendored
  reference, the Phase 1 public API, or the Phase 2 integration
  surface.
- A `CTMPlusPCAMBridge` class. Forbidden by ADR-0001.

## What remains after Phase 3

Two workstreams remain open:

1. **Phase 2.5 closure.** The cocotb harness at
   `simulator/pcam/rtl/tests/` is landed but has not yet had a
   live green run. See `FIRST_LIVE_RUN.md` in that directory for
   the closure runbook. Independent of Phase 3.

2. **Phase 4 — real-runtime measurement.** The pieces that would
   turn Phase 3's replay-only measurements into end-to-end
   benchmark claims:

   - Real-vLLM execution path in `pcam_vllm_demo.py` (currently
     the `--real-vllm` error).
   - An `Evictor` ABC bridge shipped as a small reference
     `vllm_bridge.py` alongside the adapter docstring (consumer
     code today, but a reference impl under `benchmarks/` would
     save every integrator from re-deriving it).
   - A real-baseline adapter for `simulator/pcam/baselines/`
     (Sink+LRU, H2O, industry_style) so the comparison script
     can run against production-faithful reimplementations.
   - A trace extractor that captures attention events from a
     real model forward pass. LongBench / PassKey /
     needle-in-a-haystack runs belong here.
   - A published benchmark report (PDF or markdown) that pulls
     all of the above into an acquirer-facing artifact.

   None of Phase 4 is blocked on Phase 3. When Phase 4 lands, the
   replay infrastructure in Phase 3 is what it stands on.
