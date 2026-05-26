# Phase 4 Extended Pinning Policy — measured finding

> **Status:** Phase 4 closed. Three GPU runs at seed=42 on
> Qwen2.5-7B + A100-80GB + vLLM 0.7.3 returned an **inconclusive
> result**: the pinning mechanism is mechanically correct, but
> had **no opportunity to act** because vLLM's stock LRU + prefix
> caching already handles cohort-shared workloads natively.
>
> **VC brief: unchanged.** Extended pinning was never in the brief;
> it stays roadmap-only.
>
> **Code disposition:** all components stay in-tree per the
> Phase 3 + Phase 4 + TurboQuant precedent. Both CLI flags
> (`--extended-pinning`, `--pin-first-n-blocks`,
> `--pin-tokens-file`, `--pin-max-budget-blocks`) and the three-cell
> bench script are retained as **experimental measurement
> utilities** with independent value.
>
> **`PHASE4F_PRIORITY_LRU_DESIGN.md` is now archaeology** — its
> gating condition (Phase 4C ship signal) did not materialize.

## TL;DR

| Item | Status |
|---|---|
| Pinning mechanism (install + manager + evictor wrap) | ✓ Mechanically correct (A1-A14 CPU + G1-G6/G9/G10 GPU gates pass) |
| `pinned_evictions_avoided > 0` (load-bearing G7 gate) | ✗ Zero across **all three GPU runs** |
| C-vs-B latency improvement attributable to pinning | None measurable |
| Root cause | Cohort-shared workload + vLLM's existing prefix caching is sufficient → cache never fills → evictor never fires → pinning has no opportunity to act |
| Operational outcome | Not productionized; experimental flags retained; code in-tree; brief unchanged |

## The measurement

### Workload (per the approved Phase 4 design)

* Model: `Qwen/Qwen2.5-7B-Instruct`
* GPU: A100-SXM4-80GB
* Engine: vLLM 0.7.3 V0
* Workload: 4 cohorts × N requests each, 256-token shared prefix per cohort + per-request unique tail of 32 / 64 / 128 / 256 tokens

### Cells

| Cell | `enable_prefix_caching` | `extended_pinning` | `pin_first_n_blocks` | Role |
|---|:-:|:-:|:-:|---|
| A | OFF | OFF | n/a | sanity floor |
| B | ON | OFF | n/a | stock vLLM competitor |
| C | ON | ON | 8 | the proposal |

### Three runs at seed=42

**Run 1 — loose memory** (`gpu_memory_utilization=0.5`, 100 reqs, max_decode=32):

```
A: TPS 185.69, TTFT p50 42.0 / p99 83.2 ms,  E2E p50 678 / p99 914 ms
B: TPS 183.31, TTFT p50 28.0 / p99 49.1 ms,  E2E p50 721 / p99 836 ms
C: TPS 185.90, TTFT p50 20.8 / p99 44.5 ms,  E2E p50 445 / p99 522 ms
   Cell C: pinned_blocks_total=32, pinned_evictions_avoided=0,
           evictor_path=v2_block_allocator._allocators[GPU].evictor
           swap_out_blocks=0, preemption_events=0 (all cells)
```
B-vs-C ratios appeared favorable (e.g., E2E p99 0.62×) — see "Root cause" below for why this was artifact.

**Run 2 — tight memory** (`gpu_memory_utilization=0.25, max_model_len=4096`):

```
A: TPS 185.83, TTFT p50 36.5 / p99 70.0 ms,  E2E p50 497 / p99 624 ms
B: TPS 185.95, TTFT p50 20.7 / p99 43.1 ms,  E2E p50 441 / p99 533 ms
C: TPS 186.02, TTFT p50 20.9 / p99 41.3 ms,  E2E p50 441 / p99 521 ms
   Cell C: pinned_blocks_total=32, pinned_evictions_avoided=0
           swap_out_blocks=0, preemption_events=0 (all cells)
```
B-vs-C ratios collapsed to **C ≈ B** (TPS 1.000, E2E p99 0.98). Run 1's apparent improvement vanished.

**Run 3 — recompute + cranked-up pressure** (`gpu_memory_utilization=0.27, max_model_len=4096, n_requests=500, arrival_rate=20, max_decode_tokens=256, preemption_mode=recompute`):

```
A: completed=500, preempt=96,  swap_out=0, wall=39.4s
B: completed=500, preempt=0,   swap_out=0, wall=36.2s
C: completed=500, preempt=0,   swap_out=0, wall=41.0s
```

Cell A's `preempt=96` confirms the workload **does** produce real memory pressure when prefix caching is OFF. But cells B and C — with prefix caching ON — experienced **zero** preemption events at the same workload size. vLLM's content-hash dedupe absorbs the demand.

## What survived to claim

**Pinning mechanism is correct.** Verified by:
* CPU acceptance gates A1-A14 (32 tests) all pass.
* GPU acceptance gates G1-G6 + G9 + G10 all pass across all three runs.
* The evictor wrap resolves to a documented vLLM 0.7.3 V2 path
  (`v2_block_allocator._allocators[GPU].evictor`) on real hardware.
* The pinning manager correctly identifies and marks exactly 32 blocks
  (4 cohorts × 8 first-blocks), matching the expected value for the
  workload + spec.
* `forced_pin_evictions=0` and `pin_budget_rejections=0` in all runs
  (no over-pinning, no budget saturation).

This is partner-shareable as "infrastructure / proof of compatibility,"
not as "operating-point algorithm win."

## What didn't survive to claim

**`pinned_evictions_avoided > 0` (the load-bearing G7 gate)**.
Zero across all three GPU runs:

| Run | gpu_mem | n_reqs | decode | preempt mode | preempt events | pinned_evictions_avoided |
|---|---:|---:|---:|---|---:|---:|
| Loose  | 0.50 | 100  | 32  | swap      | 0 | 0 |
| Tight  | 0.25 | 100  | 32  | swap      | 0 | 0 |
| Recompute+pressure | 0.27 | 500 | 256 | recompute | 0 in B/C, 96 in A | 0 |

The pinning evictor wrap never had a chance to filter candidates,
because cells B and C never experienced memory pressure that triggered
the LRU evictor.

**The apparent ship signal at Run 1 was artifact.** Run 1's
C-vs-B E2E p99 ratio of 0.62 (38% improvement) did not replicate
in Run 2 (ratio 0.98, i.e., neutral) or Run 3 (no relevant pressure).
Most likely cause: run-order warmup (cells A → B → C run sequentially
in a single Python process; later cells benefit from warmed CUDA
context + JIT compiles) and/or Pareto-arrival pattern variance at
the small N=100 sample size.

## Root cause — why pinning had nothing to do

**vLLM's stock LRU + prefix caching is already doing the job
that pinning would do, for this class of workload.**

* The shared-prefix workload (4 cohorts × 256-token system
  prefix) produces only **32 unique prefix blocks** total
  (4 cohorts × 8 blocks each, before tails).
* vLLM's content-hash dedupe maps every cohort-mate request to
  the **same physical block_ids** for the shared prefix.
* Those 32 blocks stay alive across the entire workload because
  they're constantly referenced by in-flight cohort-mate requests
  (refcount > 0).
* The cache (1,310-24,000 blocks depending on config) is **far
  bigger** than the working set of unique blocks needed.
* **Result:** the cache never fills → `LRUEvictor.evict()` never
  fires → the pinning evictor wrap (which intercepts that method)
  has no opportunity to act.

Cell A (no prefix caching) confirms the workload **can** produce
pressure when there's no caching to absorb it: 96 preemption
events under the cranked-up Run 3 settings. But that's the
"no cache at all" baseline, not a meaningful comparison for
pinning's claim — pinning operates **on top of** prefix caching,
not as an alternative to it.

## Honest scope

* **Workload scope.** Synthetic 4-cohort shared-prefix workload
  with Pareto-bursty arrivals. Production chat workloads with
  realistic cohort distributions (e.g., long-tail system prompts
  + per-tenant prefixes + dynamic tool schemas) may produce a
  different picture; we did not measure those.
* **Sample size.** One seed × three configurations. The
  cross-configuration consistency (B ≈ C in Runs 2 and 3) is
  strong evidence the artifact in Run 1 doesn't reflect real
  pinning value, but 2-seed Tier-A replication was not run
  because there was no ship signal to replicate.
* **Model scope.** Qwen-7B only. Not measured on Mistral, Llama,
  or larger Qwen scales.
* **vLLM version scope.** vLLM 0.7.3 V0 engine on A100. (Phase
  3C ran on H100; Phase 4C was rescheduled to A100 for
  availability. The cross-hardware difference does not affect
  the directional conclusion since all three Phase 4 runs are
  internally consistent on A100.)
* **Cache size scope.** Three configurations tested (24K, 1.3K,
  and ~1.5K cuda blocks). All produced the same negative result
  on G7.

## Known issue identified by audit

The post-Phase-3 audit identified a **stale-pinning bug** in the
Phase 4A `PinningManager`: there is no `unmark_pinned()` on
block-free. Under sustained eviction pressure with allocator
churn, the pinned set would grow monotonically as freed-and-
reallocated cohort prefixes accumulate stale block_ids. The
manager would eventually waste pinning budget on blocks holding
unrelated content.

**This bug did not affect any Phase 4 measurement** because no
pressure ever produced churn in the runs we did. But any future
revisit of pinning should fix this (add a free-wrap mirroring
the cache_aware install's free wrap, ~30 lines + 3-4 CPU tests)
before relying on the numbers under real production pressure.

Documented in `V2_CACHE_REUSE_PHASE1_INTEGRATION_NOTE.md`
§"Post-closure audit fixes" → "Eight MEDIUM findings deferred."

## Code disposition

Following the Phase 3 + TurboQuant precedent — **keep code in-tree,
preserve operational utilities as documentation, no destructive
removals**.

### Kept as-is

* `KVPolicy/kv_policy/extended_pinning.py` — PinSpec, PinningManager,
  ExtendedPinningInstall, install_extended_pinning. ~430 lines.
* `Bench/ctm_bench/runner_vllm_streaming.py` — driver wiring for
  extended pinning (constructor params, install in `run()`,
  teardown, stats snapshot).
* `Bench/ctm_bench/scripts/run_streaming.py` — single-cell CLI
  with `--extended-pinning`, `--pin-first-n-blocks`,
  `--pin-tokens-file`, `--pin-max-budget-blocks`, `--max-model-len`,
  `--preemption-mode`.
* `Bench/ctm_bench/scripts/bench_phase4_extended_pinning.py` —
  three-cell bench harness. **Partner-credible measurement
  utility; retained as v2 tool.**
* `Bench/tests/test_extended_pinning.py` — 32 CPU tests on the
  install + manager.
* `Bench/tests/test_bench_phase4_extended_pinning.py` — 17 CPU
  tests on the bench orchestration + dry-run.
* `Bench/scripts/PHASE4_VLLM_EVICTOR_HOOK_RESEARCH.md` — research
  note on V1/V2 evictor paths + recovery options.

### Documented as experimental

* All CLI flags above are retained but documented as experimental
  in `--help`. The `--extended-pinning` flag's help text already
  references this finding doc + the operationally-honest summary
  "DO NOT ENABLE IN PRODUCTION."

### Made archaeology

* `Bench/scripts/PHASE4F_PRIORITY_LRU_DESIGN.md` — the v2.1
  priority-LRU design proposal. Its gating condition (Phase 4C
  ship signal) did not materialize. Kept in-tree as design
  archaeology for any future revisit; not a workstream.

### Not changed

* `Int4ProtectedAttentionImpl` — never touched by this work
  (orthogonality contract held throughout Phase 4).
* Forked vllm-flash-attn kernel — never touched.
* `INT4_PROTECTED_VC_BRIEF.md` — extended pinning was never in the
  brief; no edit.

## Revisit conditions

This work could be revisited if any of the following hold:

1. **Workload with less prefix sharing.** Synthetic 4-cohort
   shared-prefix workload is too well-served by vLLM's existing
   content-hash dedupe. A real chat replay with long-tail system
   prompts (many distinct prefixes, less overlap across requests)
   might produce cache pressure that pinning could mitigate. Partner-
   provided workload, not lab-synthesized.

2. **Sustained throughput exceeding cache capacity.** Even with
   prefix sharing, a workload that sustains arrival rates well
   above the cache turnover rate could fill the cache. Our
   Run 3 (500 reqs / arrival_rate=20 / max_decode_tokens=256)
   did not reach this regime — vLLM's prefix caching held.
   Higher rates or longer decode budgets might.

3. **Burst-cold-cohort patterns.** A workload where a cohort
   goes quiet for long enough that vLLM's LRU evicts its prefix
   from the cache, then suddenly resumes. Pinning would prevent
   the eviction and the cold-start recomputation. Requires a
   real chat workload pattern; not synthesized in Phase 4.

4. **Different `preemption_mode`.** Run 3 confirmed recompute
   mode works (cell A produced 96 preemption events). But the
   prefix-caching cells never triggered preemption at all. If a
   future vLLM version makes `LRUEvictor.evict()` reachable via
   a different code path (e.g., explicit eviction API instead of
   preemption-coupled eviction), pinning's wrap point would
   naturally start firing.

5. **Multi-tenant pinning (priority classes).** The Phase 4F
   design proposed priority-LRU pinning with operator-declared
   priority tiers. Phase 4F never ran because Phase 4C closed
   without ship signal; the design doc is archaeology. If a
   future revisit re-enters this space, priority classes would
   be the natural elaboration after binary pinning is shown to
   matter on at least one workload.

6. **Audit-fix prerequisite.** Before any revisit, fix the
   stale-pinning bug (no `unmark_pinned` on free) — ~30 lines +
   3-4 CPU tests. Otherwise reported numbers under real
   production pressure would be contaminated by stale-block
   accumulation.

None of these are committed work. They are notes for the next
maintainer who asks "why doesn't pinning ship?" or "is this
worth re-attempting?"

## Artifact pointers

| Doc / data | What it captures |
|---|---|
| `PHASE3_CACHE_AWARE_FINDINGS.md` | Precedent: predictive-eviction retirement |
| `PHASE4_VLLM_EVICTOR_HOOK_RESEARCH.md` | V1/V2 evictor paths + recovery options |
| `PHASE4C_GPU_RUNBOOK.md` | The operational runbook for the Phase 4C measurement |
| `PHASE4F_PRIORITY_LRU_DESIGN.md` | v2.1 priority-LRU design (archaeology; gating condition didn't materialize) |
| `Bench/bench_out/PHASE4C_SEED42/` | Loose-memory run (gpu_mem=0.5) — three-cell streaming summaries + comparison.json |
| `Bench/bench_out/PHASE4C_SEED42_TIGHT/` | Tight-memory run (gpu_mem=0.25, max_model_len=4096) |
| `Bench/bench_out/PHASE4C_SEED42_RECOMPUTE/` | Recompute+pressure run (gpu_mem=0.27, n=500, rate=20, decode=256) |
| `KVPolicy/kv_policy/extended_pinning.py` | Install + manager (retained) |
| `Bench/ctm_bench/scripts/bench_phase4_extended_pinning.py` | Three-cell bench harness (retained) |

## Closing

Phase 4 produced honest, durable engineering work and an honest
measured finding. The Extended Pinning Policy is mechanically
correct — the install resolves the right vLLM 0.7.3 path, the
manager marks the expected blocks, the evictor wrap composes
cleanly with the cache-aware install layer. But on the workload
shape we measured, pinning has no opportunity to act because
vLLM's stock LRU + prefix caching already handles cohort-shared
prefix protection natively.

This is the cleanest possible negative finding — distinct from
Phase 3's inconclusive realized-hit signal + tail-latency regression.
Phase 3 found a predictive mechanism that **didn't help reliably**.
Phase 4 found a deterministic mechanism that **wasn't needed at this
workload's scale**. Both honest; both close the chapter for v2 with
code retained for any future workload where the picture changes.

Same disposition as Phase 3 + Phase 4 trig + TurboQuant:
**code preserved, finding documented, brief unchanged, revisit
conditions named.**
