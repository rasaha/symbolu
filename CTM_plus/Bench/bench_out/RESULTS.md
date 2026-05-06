# CTM+ Tier-Aware Benchmark — Round 5 (HBF stress, canonical)

**Run date:** 2026-05-06
**Mode:** A (synthetic, no GPU). Mode B GPU script available at
`Bench/scripts/run_mode_b.sh` for real-model validation.
**Seeds validated:** Round 4 covered {42, 137, 271}. Round 5 is
single-seed (deterministic tier-config differentiation).
**Commit:** see `git log` at the same SHA as this file.

> ## ⚠ Mode A vs Mode B status (post-GPU-run, May 2026)
>
> **Every number in this document comes from Mode A — a tier-
> aware cache simulator.** Mode B GPU validation was attempted
> on a RunPod A100 (~15 min wall, ~$0.30 spend) and produced a
> conservative six-bullet finding:
>
> 1. **Mode A synthetic validation shows strong CTM+ gains.**
>    5 rounds + an independent audit pass + multi-seed
>    confirmation across {42, 137, 271}. Numbers in this
>    document are reproducible from `runner_sim.py` and the
>    pinned tier-cost model.
> 2. **Mode B real-vLLM run validated harness execution and
>    timing only.** The harness loads Qwen2.5-7B-Instruct on
>    an A100, runs vLLM, and produces honest wall-clock
>    measurements per decode token. That part of the path is
>    proven.
> 3. **CTM+ was not installed into vLLM** because vLLM 0.5+
>    no longer exposes the needed eviction-policy integration
>    point. The original `BlockSpaceManagerV1.evictor` hook was
>    replaced by a private `CpuGpuBlockAllocator._allocators`
>    dict in 0.5+; the existing CTM+ patch raises
>    `NotImplementedError` and there is no public abstraction
>    to register a custom policy against.
> 4. **vLLM batch-mode FCFS execution did not trigger
>    swap/preemption.** `engine.generate(prompts=[...])` with
>    the default scheduler either admits a prompt or queues
>    it; it never preempts running sequences. `swap_space`
>    is engaged only on preemption events. Counter extraction
>    reached the right API; the API honestly returned zero.
> 5. **Therefore, Mode B does not validate or invalidate
>    CTM+.** It does not produce real-model CTM+ vs LRU
>    head-to-head numbers. It does not exercise the swap path
>    that the simulator's tier model is designed to predict.
>    It validates the runner harness, not the policy.
> 6. **Real-model CTM+ vs LRU validation is deferred** pending
>    either (a) a vLLM integration rewrite (~2–3 days against
>    the post-0.5 allocator architecture) or (b) a
>    partner-specific serving harness with a public
>    eviction-policy hook. Both paths are documented in
>    `Bench/scripts/MODE_B_RUNBOOK.md` §9.6 + §10; **neither
>    is justified by current partner conversations** — they
>    should be triggered by a specific partner request.
>
> | | Mode A | Mode B today | Mode B (future, gated) |
> |---|---|---|---|
> | Where | `runner_sim.py` | `runner_vllm.py` (LRU-only smoke) | streaming/async runner OR partner serving stack (~2-3 days) |
> | Status | ✅ 5 rounds + audit pass | ✅ harness + timing valid; ❌ CTM+ not exercised | ❌ not started |
> | Validates | Tier-cost model + policy logic in simulation | Harness execution + per-token wall-clock timing | Real-model CTM+ vs LRU head-to-head |
> | Does **not** validate | Real-silicon behaviour | CTM+ policy on a real model — at all | (TBD by partner-specific requirements) |
>
> The latency cross-check tool
> (`ctm_bench.scripts.latency_cross_check`) reports per-token
> wall-clock and tokens/sec from the existing Mode B runs as
> **harness/timing evidence only — not CTM+ performance
> evidence**. The two Mode B sweeps were both LRU-only because
> CTM+ couldn't be installed into vLLM 0.5+, so no real-model
> CTM+ vs LRU comparison exists today.
>
> **For partner conversations:** the honest framing is "Mode A
> predicts X with full reproducibility across 5 rounds + audit
> pass; Mode B confirmed the harness runs end-to-end on a real
> model and produces honest timing data, but did not exercise
> CTM+ — that integration is gated on either a vLLM rewrite
> or a partner-specific serving stack." See the partner
> validation note at `bench_out/PARTNER_VALIDATION_NOTE.md`
> for the version that's safe to share.

> **Round 5 is the canonical headline.** Round 4 retained below
> as §10 for the multi-seed audit-validation history. Round 1-3
> directories preserved on disk; **absolute numbers in Round 1-3
> reports are biased by 2× on RAG and agentic workloads** due
> to the decode-count bug fixed in Round 4. Relative comparisons
> within each round remain valid.

## §1 Headline findings (Mode A simulated, all rounds)

The harness produced three distinct findings across five
rounds. Each lives on a different workload; partner
conversations should pick the cell that matches the partner's
workload mix.

### §1.1 Chat under heavy KV pressure — the 52% latency cell (Round 5)

**The cell that matters most for a NAND-vendor conversation.**
At oversubscription 0.025, chat_32k spills heavily (HBM hit
rate drops to 10.4-45.7%). Combining CTM+ with an HBF overflow
tier reduces average KV access latency by **52%** vs DDR + LRU.

| Tier config | Policy | HBM hit | slow-tier B/tok | avg access latency |
|---|---|---:|---:|---:|
| hbm_ddr_nvme | lru | 10.4% | 1.08 GB | **56,913 ns** (baseline) |
| hbm_ddr_nvme | ctm_plus | 45.7% | 0.66 GB | 35,337 ns (−38%) |
| hbm_hbf_nvme | lru | 10.4% | 1.08 GB | 43,485 ns (−24%) |
| **hbm_hbf_nvme** | **ctm_plus** | 45.7% | 0.66 GB | **27,203 ns (−52%)** |

The two effects stack roughly multiplicatively: CTM+ alone
captures ~38%, HBF alone captures ~24%, together ~52%. See
§2 for the stacked breakdown and §3 for the bandwidth-
dominance mechanism that makes HBF win despite higher access
latency than DDR.

### §1.2 Retrieval-augmented (RAG) — the 100% elimination cell

CTM+'s S3-FIFO admission keeps one-shot prefill chunks out of
the working set entirely. Slow-tier reads collapse to zero at
every oversubscription tested:

| Oversub | LRU slow-tier B/tok | CTM+ slow-tier B/tok | CTM+ vs LRU |
|---:|---:|---:|---:|
| 0.10 | 2,048 | 0 | **−100%** |
| 0.05 | 2,048 | 0 | **−100%** |
| 0.025 | 2,048 | 0 | **−100%** |

This is a workload-property advantage (one-shot reads can be
identified by frequency); it doesn't scale with tier-0 capacity.
The cleanest single-number win, but **does not directly engage
the flash tier** — RAG simply doesn't spill.

### §1.3 Agentic — the honest regression cell

CTM+ is **worse** than LRU on agentic workloads, and the gap
amplifies under heavier KV pressure:

| Workload + Oversub | LRU B/tok | CTM+ B/tok | Δ vs LRU |
|---|---:|---:|---:|
| agentic_clustered @ 0.10 | 6,144 | 6,912 - 7,936 | +12.5% to +29% |
| agentic_clustered @ 0.05 | 8,192 | 9,216 | +12.5% |
| **agentic_clustered @ 0.025** | 9,216 | **26,880** | **+192%** |
| agentic_64k uniform-random (any oversub) | ~388,000 | ~466,000 | ~+18% |

The α=0.20 production default (Round 4) helps in moderate-
pressure regimes but doesn't scale to extreme pressure. Round 6
candidate fix: explicit recency floor that never evicts a block
touched in the last K decode steps regardless of attention
score.

### §1.4 Putting them together — the honest pitch line

> "CTM+ does three different things on three different workload
> classes: full elimination on retrieval (RAG), 52% combined
> latency reduction when stacked with HBF on chat-under-pressure,
> and a known regression on agentic that we're investigating in
> Round 6. Every number is reproducible from a Mode A simulator
> with an audit-passed cost model. Real-model CTM+ vs LRU
> validation on vLLM is gated — vLLM 0.5+ removed the public
> eviction-policy hook — so that step is deferred until a
> partner serving stack provides the integration point or
> explicitly funds the vLLM rewrite."

Don't lead with RAG alone — that omits the flash-tier story.
Don't lead with chat alone — that omits the most decisive
single-number win. Don't omit agentic — that's the honesty bit
that lets the rest of the pitch land.

## §2 The 52% cell — chat_32k @ oversubscription 0.025

The chat_32k workload at oversubscription 0.025 broke into
heavy spillover (HBM hit rate dropped from 100% to 10.4% LRU /
45.7% CTM+). This is the regime where HBF differentiates.

| Tier config | Policy | HBM hit | slow-tier B/tok | avg access latency |
|---|---|---:|---:|---:|
| hbm_ddr_nvme | lru | 10.4% | 1.08 GB | **56,913 ns** |
| hbm_ddr_nvme | ctm_plus | 45.7% | 0.66 GB | 35,337 ns |
| **hbm_hbf_nvme** | lru | 10.4% | 1.08 GB | 43,485 ns |
| **hbm_hbf_nvme** | **ctm_plus** | 45.7% | 0.66 GB | **27,203 ns** |

Stacked breakdown:

| Configuration | avg access latency | Δ vs DDR + LRU |
|---|---:|---:|
| DDR + LRU (baseline) | 56,913 ns | — |
| DDR + CTM+ | 35,337 ns | **−38%** (eviction-policy effect) |
| HBF + LRU | 43,485 ns | **−24%** (HBF-tier-only effect) |
| HBF + CTM+ | 27,203 ns | **−52%** (combined) |

### §2.1 Partner-conversation pitch

> "On chat workloads under heavy KV-cache pressure, CTM+ alone
> reduces average access latency by ~38%. Replacing the DDR
> overflow tier with HBF alone reduces it by ~24%. Together
> they reduce average latency by 52% — a workload that would
> not be servable on commodity hardware becomes servable, and
> the additional flash-tier capacity is what makes that
> possible."

This is the multi-axis story: the policy and the flash tier
each provide a meaningful fraction; together they cross the
threshold from "infeasible" to "viable."

## §3 Why HBF wins despite higher access latency than DDR

The mechanism is non-obvious and worth stating explicitly.

| Tier | Access latency | Bandwidth | Per-2 MiB-block total |
|---|---:|---:|---:|
| HBM | 200 ns | 1.15 TB/s | ~1.9 µs |
| HBF | 2,000 ns | 200 GB/s | ~12 µs |
| DDR | 80 ns | 64 GB/s | ~31 µs |
| NVMe | 50,000 ns | 5 GB/s | ~450 µs |

HBF has **higher** access latency than DDR (2,000 ns vs 80 ns)
but **2.6× faster** per 2 MiB block because bandwidth
dominates the total at this transfer size. KV blocks are large
enough that bandwidth, not access latency, governs per-block
cost. This is the architectural justification for HBF as an
inference-tier offering: not "DDR but faster per byte" (it's
not), but "bandwidth at scale, where KV-cache spillover
actually needs it."

## §4 Other workloads at heavier spillover

### §4.1 RAG_128K — CTM+ wins 100% at every oversubscription

Scan-resistance is a workload-property advantage independent
of tier-0 capacity:

| Oversub | LRU slow-tier B/tok | CTM+ slow-tier B/tok | CTM+ vs LRU |
|---:|---:|---:|---:|
| 0.05 | 2,048 | 0 | **−100%** |
| 0.025 | 2,048 | 0 | **−100%** |

### §4.2 agentic_clustered_64k — CTM+ regression amplifies under heavy spillover

| Oversub | LRU slow-tier B/tok | CTM+ slow-tier B/tok | CTM+ vs LRU |
|---:|---:|---:|---:|
| 0.10 (Round 4) | 6,144 | 6,912-7,936 | +12.5% to +29% |
| 0.05 | 8,192 | 9,216 | +12.5% |
| **0.025** | 9,216 | **26,880** | **+192%** |

At oversub 0.025, CTM+ is ~3× worse than LRU on
agentic_clustered. The mechanism: under tight tier-0 capacity,
CTM+'s scoring is too aggressive about evicting blocks with
short attention bursts; the Markov-dwell hot blocks lose the
race vs LRU's cheap recency. The α=0.20 fix from Round 4 helps
in moderate-pressure regimes but doesn't scale to extreme
pressure.

**Recommendation:** for deployments with HBM oversubscription
< 0.05 on agentic-style workloads, the production default
α=0.20 may not be enough. A possible Round 6 fix is an
explicit recency floor in addition to the EMA — i.e., never
evict a block touched within the last K decode steps,
regardless of attention score.

### §4.3 agentic_64k uniform-random — adversarial baseline

CTM+ 18-19% worse than LRU at every oversubscription.
Consistent with Round 4. Known not to favour any
attention-aware policy.

## §5 Full 48-cell table

```
Workload               Policy     Tier         Oversub  slow_B/tok    avg_lat   hbm_hit
─────────────────────────────────────────────────────────────────────────────────────────
rag_128k               lru        hbm_ddr_nvme  0.050     2,048 B    3,764 ns  100.0%
rag_128k               fifo       hbm_ddr_nvme  0.050     2,048 B    3,764 ns  100.0%
rag_128k               ctm_plus   hbm_ddr_nvme  0.050         0 B    3,763 ns  100.0%
rag_128k               lru        hbm_ddr_nvme  0.025     2,048 B    3,811 ns  100.0%
rag_128k               fifo       hbm_ddr_nvme  0.025     2,048 B    3,811 ns  100.0%
rag_128k               ctm_plus   hbm_ddr_nvme  0.025         0 B    3,810 ns  100.0%
rag_128k               lru        hbm_hbf_nvme  0.050     2,048 B    3,987 ns  100.0%
rag_128k               fifo       hbm_hbf_nvme  0.050     2,048 B    3,987 ns  100.0%
rag_128k               ctm_plus   hbm_hbf_nvme  0.050         0 B    3,986 ns  100.0%
rag_128k               lru        hbm_hbf_nvme  0.025     2,048 B    4,040 ns  100.0%
rag_128k               fifo       hbm_hbf_nvme  0.025     2,048 B    4,040 ns  100.0%
rag_128k               ctm_plus   hbm_hbf_nvme  0.025         0 B    4,039 ns  100.0%
agentic_clustered_64k  lru        hbm_ddr_nvme  0.050     8,192 B    3,223 ns  100.0%
agentic_clustered_64k  fifo       hbm_ddr_nvme  0.050     8,192 B    3,223 ns  100.0%
agentic_clustered_64k  ctm_plus   hbm_ddr_nvme  0.050     9,216 B    3,223 ns  100.0%
agentic_clustered_64k  lru        hbm_ddr_nvme  0.025     9,216 B    3,257 ns  100.0%
agentic_clustered_64k  fifo       hbm_ddr_nvme  0.025     9,216 B    3,257 ns  100.0%
agentic_clustered_64k  ctm_plus   hbm_ddr_nvme  0.025    26,880 B    3,268 ns  100.0%
agentic_clustered_64k  lru        hbm_hbf_nvme  0.050     8,192 B    3,381 ns  100.0%
agentic_clustered_64k  fifo       hbm_hbf_nvme  0.050     8,192 B    3,381 ns  100.0%
agentic_clustered_64k  ctm_plus   hbm_hbf_nvme  0.050     9,216 B    3,381 ns  100.0%
agentic_clustered_64k  lru        hbm_hbf_nvme  0.025     9,216 B    3,419 ns  100.0%
agentic_clustered_64k  fifo       hbm_hbf_nvme  0.025     9,216 B    3,419 ns  100.0%
agentic_clustered_64k  ctm_plus   hbm_hbf_nvme  0.025    26,880 B    3,427 ns  100.0%
chat_32k               lru        hbm_ddr_nvme  0.050    16,384 B    2,077 ns  100.0%
chat_32k               fifo       hbm_ddr_nvme  0.050    16,384 B    2,077 ns  100.0%
chat_32k               ctm_plus   hbm_ddr_nvme  0.050    33,280 B    2,078 ns  100.0%
chat_32k               lru        hbm_ddr_nvme  0.025  1.08 GB     56,913 ns   10.4%   ← spillover
chat_32k               fifo       hbm_ddr_nvme  0.025  1.08 GB     56,913 ns   10.4%   ← spillover
chat_32k               ctm_plus   hbm_ddr_nvme  0.025  657 MB      35,337 ns   45.7%   ← CTM+ contains it
chat_32k               lru        hbm_hbf_nvme  0.050    16,384 B    2,102 ns  100.0%
chat_32k               fifo       hbm_hbf_nvme  0.050    16,384 B    2,102 ns  100.0%
chat_32k               ctm_plus   hbm_hbf_nvme  0.050    33,280 B    2,103 ns  100.0%
chat_32k               lru        hbm_hbf_nvme  0.025  1.08 GB     43,485 ns   10.4%   ← spillover
chat_32k               fifo       hbm_hbf_nvme  0.025  1.08 GB     43,485 ns   10.4%   ← spillover
chat_32k               ctm_plus   hbm_hbf_nvme  0.025  657 MB      27,203 ns   45.7%   ← HBF + CTM+ wins
agentic_64k            lru        hbm_ddr_nvme  0.050   344,320 B   3,459 ns   99.6%
agentic_64k            fifo       hbm_ddr_nvme  0.050   344,064 B   3,459 ns   99.6%
agentic_64k            ctm_plus   hbm_ddr_nvme  0.050   409,088 B   3,500 ns   99.6%
agentic_64k            lru        hbm_ddr_nvme  0.025   388,608 B   3,521 ns   99.6%
agentic_64k            fifo       hbm_ddr_nvme  0.025   388,608 B   3,521 ns   99.6%
agentic_64k            ctm_plus   hbm_ddr_nvme  0.025   465,664 B   3,570 ns   99.5%
agentic_64k            lru        hbm_hbf_nvme  0.050   344,320 B   3,568 ns   99.6%
agentic_64k            fifo       hbm_hbf_nvme  0.050   344,064 B   3,567 ns   99.6%
agentic_64k            ctm_plus   hbm_hbf_nvme  0.050   409,088 B   3,599 ns   99.6%
agentic_64k            lru        hbm_hbf_nvme  0.025   388,608 B   3,627 ns   99.6%
agentic_64k            fifo       hbm_hbf_nvme  0.025   388,608 B   3,627 ns   99.6%
agentic_64k            ctm_plus   hbm_hbf_nvme  0.025   465,664 B   3,664 ns   99.5%
```

Machine-readable summary in `bench_out/round5_hbf_stress/multi_config_summary.json`.

## §6 What this is and isn't

**It is** a measurement of eviction-policy + tier-config
effects on per-block average access latency, isolated from
real-model serving overheads. Reproducible (seed + tier specs +
workload specs are pinned by the test suite). Round 4 already
established α=0.20 isn't seed-locked; tier differentiation is
deterministic.

**It isn't** a real-model CTM+ benchmark. The Mode B GPU run
attempted in May 2026 validated the harness end-to-end but
did **not** exercise CTM+ on a real model: vLLM 0.5+ no
longer exposes the eviction-policy hook the original CTM+
patch targeted, and batch-mode FCFS scheduling never triggered
the swap path the tier model predicts. Real-model CTM+ vs LRU
validation requires either a vLLM integration rewrite or a
partner-specific serving harness — see the §0 banner and
`Bench/scripts/MODE_B_RUNBOOK.md` §9.

**It isn't** a complete tour of the workload space. Production
deployments have idiosyncratic patterns (mixed agentic + chat,
batched concurrent requests, prefix-cache interactions) that
this synthetic harness deliberately doesn't model. Mode B
captures some of that; real-trace replay would capture more.

## §7 Open issues + Round 6 candidates

1. **agentic_clustered regression amplifies at oversub ≤ 0.05.**
   The α=0.20 fix from Round 4 doesn't scale to extreme
   pressure. Candidate fix: explicit recency floor (never
   evict a block touched in the last K decode steps).
2. **HBF cost model is forward-looking.** The numbers are
   based on public SanDisk announcements; real silicon may
   differ. Worth re-running once HBF parts are sampling.
3. **Block size is fixed at 2 MiB.** Some serving stacks use
   16-token KV blocks at smaller per-block sizes. A block-size
   sweep would round out the cost-model coverage.

## §8 Files in this directory

```
bench_out/
├── RESULTS.md                          # this file (Round 5 canonical)
├── hbm_ddr_nvme/                       # Round 1, oversub 0.4 (no spillover)
├── hbm_ddr_nvme_0p1/                   # Round 1, oversub 0.1
├── hbm_hbf_nvme_0p1/                   # Round 1, HBF tier
├── round2_hbm_ddr_nvme/                # Round 2, agentic_clustered_64k added
├── round3_alpha_0p05/                  # Round 3, α = 0.05
├── round3_alpha_0p10/                  # Round 3, α = 0.10 (control)
├── round3_alpha_0p20/                  # Round 3, α = 0.20 (sweet spot)
├── round3_alpha_0p30/                  # Round 3, α = 0.30 (saturation)
├── round4_multi_seed/                  # Round 4, post-audit, 3 seeds
│   ├── multi_seed_summary.json
│   ├── alpha_0p10_seed42/
│   └── alpha_0p20_seed42/
└── round5_hbf_stress/                  # Round 5 (this round)
    └── multi_config_summary.json       # 48 cells (4 workloads × 3 policies × 2 tiers × 2 oversubs)
```

---

## §9 What to do next

In priority order, all gated on partner request — there is no
internal trigger for any of these today:

1. **Real-model CTM+ vs LRU validation (deferred).** Requires
   either (a) a vLLM 0.5+ integration rewrite — 2–3 days
   against the post-0.5 `CpuGpuBlockAllocator` architecture,
   plus per-vLLM-minor-version regression maintenance — or
   (b) a partner-specific serving harness with a public
   eviction-policy hook. Both paths sketched in
   `MODE_B_RUNBOOK.md` §9.6 / §10. **Do not start without an
   explicit partner trigger.** The May 2026 GPU run validated
   the harness; it did not validate CTM+.
2. **Round 6: explicit recency floor.** Add a
   `protect_recent_blocks` parameter to `KVCachePolicy` that
   never evicts a block touched in the last K decode steps.
   Sweep K ∈ {0, 4, 8, 16}; expected to close the
   agentic_clustered regression at heavy spillover. Mode A only;
   doesn't depend on item 1.
3. **Block-size sweep.** Currently fixed at 2 MiB. Some
   serving stacks use 16-token blocks at smaller sizes. Worth
   a Round 7 to round out the cost-model coverage.

---

## §10 Round 4 — post-audit, multi-seed (retained for reference)

Round 4 established that the production default change
(α 0.10 → 0.20, applied in commit `2c64b89`) was robust
under both the audit-fix corrections and across three seeds.
Retained here in full.

### §10.1 What changed since Round 3 (audit fixes)

An independent critical-audit pass on `Bench/` surfaced 13
findings (3 HIGH, 4 MEDIUM, 3 LOW, 3 DOC). The two that
affected published numbers:

* **HIGH #3 (decode-token count off-by-2x).** Replaced the
  `position == seq_len - 1` heuristic with explicit
  `is_decode_step_marker` flag.
* **HIGH #1 (seed not propagated).** `KVCachePolicy` was
  hardcoded to `random.Random(42)`; adapter now overrides
  with `cfg.seed`.

### §10.2 Round 4 multi-seed validation (oversub 0.10)

| Workload | Seed | α=0.10 | α=0.20 | α=0.10 vs LRU | α=0.20 vs LRU |
|---|---:|---:|---:|---:|---:|
| rag_128k | 42 | 0 | 0 | **−100%** | **−100%** |
| rag_128k | 137 | 0 | 0 | **−100%** | **−100%** |
| rag_128k | 271 | 0 | 0 | **−100%** | **−100%** |
| agentic_clustered_64k | 42 | 9,472 | 6,912 | +54.2% | +12.5% |
| agentic_clustered_64k | 137 | 10,496 | 7,936 | +70.8% | +29.2% |
| agentic_clustered_64k | 271 | 9,984 | 7,680 | +62.5% | +25.0% |
| chat_32k | 42 | 16,896 (+3.1%) | 16,384 (parity) | +3.1% | 0% |
| chat_32k | 137 | 16,896 (+3.1%) | 16,384 (parity) | +3.1% | 0% |
| chat_32k | 271 | 16,896 (+3.1%) | 16,384 (parity) | +3.1% | 0% |

α=0.20 reduces the agentic_clustered regression from a mean
+62.5% (range 54-71%) to a mean +22.2% (range 12.5-29%) —
consistent across seeds — and eliminates the small chat
overhead. The Round 3 recommendation is robust.

Production default change applied in commit `2c64b89`.

### §10.3 What the harness now provides for a partner conversation

> "We have a reproducible benchmark harness that surfaces and
> quantifies policy gaps. Audit-pass discipline: every
> non-trivial change goes through an independent critical
> audit before publication. The harness has paid for itself
> three times — once finding a 4× improvement we missed
> (Round 3), once finding a 2× metric-bias bug + a
> seed-propagation bug that would have invalidated the
> headline numbers (Round 4), and once surfacing the HBF
> bandwidth-dominance mechanism that turns the SanDisk pitch
> into a 52% latency story (Round 5). We're not selling you
> on results; we're selling you on a method that will keep
> finding things like this."

That's a rare positioning for an inference-optimization team.
Most teams' benchmarks show the wins; few teams' benchmarks
show their methodology surfacing and correcting their own
errors mid-flight.

---

## §11 Independent Simulator Cross-Confirmation

A separate simulator (`CTM_plus/KVSimulator/`, different
codebase from Bench/Mode A — different scenarios, different
metrics, written before Bench existed) reproduces the same
qualitative shape Mode A surfaces. **The headline is not
"CTM+ beats LRU"; it's that two independent simulators
converge on the same nuanced finding: CTM+ shows small
recompute-cost wins in moderate / high / bimodal regimes,
but regresses under extreme pressure.**

The full stress-test log is at
`bench_out/independent_simulator_stress_test.txt` (5 seeds ×
4 policies × 7 scenarios; see `KVSimulator/stress_test.py`
for the runner).

### §11.1 The recompute-cost table (primary metric)

`recompute_cost` counts decode steps that hit an evicted
block and force re-computation. It is the most independent
metric: it depends on the eviction *outcome* (did the policy
keep the right block?), not on attention or position signals
that the policy itself uses.

| Workload | CTM+ recompute_cost | LRU recompute_cost | Direction |
|---|---:|---:|---|
| 4a Moderate | 211k | 215k | CTM+ ~2% better |
| 4b High | 147k | 152k | CTM+ ~3% better |
| 4c Extreme | 213k | 174k | **CTM+ ~22% worse** |
| 5a Bimodal | 113k | 117k | CTM+ ~3% better |

The 4c "Extreme" cell (64-block cache, 16 max concurrent,
arrival rate 0.20, completion rate 0.05) also shows an
**accuracy regression: CTM+ 57.0% vs LRU 62.7% — a 5.7
percentage-point drop.** Under extreme pressure the policy is
both slower (more recomputes) and produces lower accuracy.

This is the **same shape Mode A produces.** Mode A's
agentic_clustered cell at oversub 0.025 shows CTM+ +192%
slow-tier-bytes-per-token vs LRU (§4.2). KVSimulator's 4c
cell shows CTM+ +22% recompute-cost and −5.7pp accuracy vs
LRU. Two independent simulators, same direction, same
regression at extreme pressure.

### §11.2 Why we are NOT leading with `important_evictions`

The KVSimulator stress-test report includes a column called
`ImpEv` that counts evictions of blocks classified as
`SINK` or `ENTITY`. The headline-friendly version of that
column is "CTM+ has 0, LRU has 16–75 per scenario." We are
**not** using that as a headline because the metric is
partially policy-coupled:

* **SINK blocks are structurally pinned for all policies.**
  `kv_simulator/buffer_pool.py` adds SINK blocks to a
  framework-level `pinned` set during prefill (line 658) and
  passes that same set to every policy's `select_victim`
  (line 783). LRU, FIFO, Random, and CTM+ all see SINK as
  off-limits. SINK eviction is not a differentiator.
* **ENTITY classification overlaps with CTM+'s scoring
  inputs.** A block is classified ENTITY when its
  `avg_attention` exceeds a threshold
  (`buffer_pool.py:_classify_block` line 811). CTM+'s
  scoring formula directly weights `cumulative_attention`
  and ENTITY position class (`AttentionAwarePolicy._score`
  line 460: `0.35 * attn + 0.30 * position + ...`). LRU has
  no attention signal at all. So "CTM+ avoids ENTITY
  evictions, LRU doesn't" largely measures "the policy that
  uses attention as a signal vs the policy that doesn't" —
  not an independent oracle of which evictions hurt.
* **`recompute_cost` is the more independent metric** because
  it observes the actual operational consequence (a block
  was evicted and then needed) rather than predicting
  importance from the same signals the policy uses.

Reporting `important_evictions` as the headline would have
given a misleading "CTM+ has 0, LRU has 16-75" story that
does not survive technical diligence. The metric is retained
in the captured log as a secondary signal for completeness,
but it should always be cited with the policy-coupling
caveat.

### §11.3 What this section does and does not claim

**Does claim:**

* Two independent simulators (Bench/Mode A and KVSimulator)
  agree on the qualitative shape of the workload-policy
  matrix: CTM+ small wins on moderate workloads, regression
  at extreme pressure.
* The audit-pass discipline applied to Bench was applied to
  this cross-confirmation: the obvious "0 important
  evictions" headline was rejected because the metric is
  policy-coupled. Mode A's tier-cost predictions are the
  canonical numbers; KVSimulator is corroboration of shape,
  not magnitude.
* Same as Mode A's existing finding: a recency-floor
  extension (Round 6) is the candidate fix for the
  extreme-pressure regression.

**Does not claim:**

* That CTM+ beat LRU in all regimes. It does not.
* That CTM+ is generally superior to LRU. It is not — under
  extreme pressure it regresses on both recompute and
  accuracy.
* That this is real-model evidence. KVSimulator is a
  simulator; Mode A is a simulator. Real-model CTM+ vs LRU
  validation remains gated (see the §0 banner).

### §11.4 The conclusion that survives technical diligence

> "CTM+ is promising in moderate-pressure regimes — two
> independent simulators show small recompute-cost wins on
> moderate, high, and bimodal workloads. CTM+ is **not**
> robust under extreme pressure — both simulators show a
> regression (Bench's `agentic_clustered_64k` at oversub
> 0.025: +192% slow-tier-bytes-per-token; KVSimulator's
> 4c Extreme: +22% recompute-cost, −5.7pp accuracy).
> Therefore the correct framing is not 'CTM+ beats LRU,'
> but 'CTM+ needs a pressure-aware fallback or adaptive
> gating before being claimed as generally superior.' Round
> 6 (explicit recency floor) is the named candidate fix."

This is the conservative claim that holds. Stronger framings
would not survive a partner's technical review.

---

## §12 Production-Shape Workload Replay

A **third** independent evidence path: parametric production-
shape replay with multi-seed averaging across three workload
shapes. The replay tool ships at
`ctm_bench/scripts/production_shape_replay.py` and runs in
~66s on this machine (no GPU). Canonical artifact:
`bench_out/production_shape_replay/` (results.json + report.md).

**Honest scope.** This is **workload-shape replay, not real-
attention replay.** The length distributions and arrival
patterns are parametric models tunable to whatever production
data a partner has; the attention itself still comes from
KVSimulator's synthetic generators. True real-attention
replay requires GPU-extracted attention from a real model on
real prompts (#1b in the validation roadmap; not implemented).
The presets are **parametric models, not validated against
specific public datasets** — they are named for the *shape*
they capture, not for any dataset they reproduce.

### §12.1 Multi-seed results (recompute_cost, lead metric)

Three presets × five policies × three seeds (42, 137, 271)
through KVSimulator continuous batching. Means across seeds:

| Preset | CTM+ recompute | LRU recompute | CTM+ vs LRU | Accuracy delta |
|---|---:|---:|---:|---:|
| chat_short_long_mix | 38,320 | 41,509 | **−7.7% (CTM+ better)** | +0.78pp |
| rag_bursty (Pareto α=1.5) | 324,389 | 328,816 | −1.3% (CTM+ marginally better) | +0.66pp |
| agentic_sustained_long | 393,349 | 386,533 | **+1.8% (CTM+ worse)** | **−0.48pp** |

The shapes converge with §11 KVSimulator stress-test and
Mode A: CTM+ wins on bimodal-chat workloads, marginal on
bursty RAG, and underperforms on sustained-long-context
agentic — the same regression direction Mode A shows on
`agentic_clustered_64k` and §11 shows on the 4c Extreme
cell, at smaller magnitude here because the
`agentic_sustained_long` preset is *moderately* pressured
(96 max_blocks, 12 concurrent, 0.20/0.04 arrival/completion),
not *extreme*.

### §12.2 What this third path adds beyond §11 / Mode A

* **Parametric tuning.** A partner can replace the preset
  parameters with empirical measurements from their own
  production trace and re-run the comparison in ~1 minute,
  without GPU. This converts the replay tool into a
  partner-specific measurement vehicle — they don't need to
  trust our synthetic generators on faith.
* **Pareto-bursty arrival modeling.** The `rag_bursty`
  preset uses a Pareto-gap arrival schedule (α=1.5; mean
  inter-arrival 3.5 steps, max gap 47 steps for the first
  seed) — a closer approximation to production heavy-tailed
  arrival patterns than the uniform Bernoulli the existing
  KVSimulator/Mode A use. The replay tool's
  `build_arrival_schedule` is unit-tested for determinism +
  burstiness > uniform.
* **Multi-shape coverage.** Three different shapes in one
  artifact — bimodal-length, bursty-arrival, sustained-
  long-context — each with the §11 audit-passed framing
  (recompute_cost as lead, important_evictions caveated).

### §12.3 What this third path does NOT add

* **Not real-attention.** The attention generators are still
  synthetic; KVSimulator's `ATTENTION_PATTERNS` randomly
  assigns one of {sink+recent, entity-focused, distributed,
  mixed} per sequence. Real-attention replay (#1b) requires
  GPU-extracted attention scores from a real model.
* **Not a real-model run.** This remains simulation-only
  evidence. Real-model CTM+ vs LRU validation is gated on
  Path A (vLLM 0.5+ rewrite) or Path B (partner serving
  stack) — see `PARTNER_VALIDATION_NOTE.md` §4.
* **Presets are parametric, not dataset-derived.** Citing
  these results as "LMSYS" or "BurstGPT" numbers would not
  survive technical diligence and is explicitly flagged in
  the report header. The `shape_caveat` field on every
  preset is rendered into the report verbatim so readers
  cannot misread the framing.

### §12.4 Updated validation evidence chain

The simulation evidence now spans three independent
substrates — same direction, all three:

| Evidence | Substrate | CTM+ on moderate workloads | CTM+ on heavy/sustained pressure |
|---|---|---:|---:|
| Mode A (Bench) | tier-cost simulator | small wins (chat / RAG) | regression (agentic_clustered +192%) |
| KVSimulator §11 | continuous-batching simulator | small recompute wins | regression (4c Extreme +22% recompute, −5.7pp accuracy) |
| Replay §12 | parametric workload shapes | chat_short_long_mix −7.7% recompute | agentic_sustained_long +1.8% recompute, −0.48pp accuracy |

**The conclusion that survives technical diligence is
unchanged from §11.4:** CTM+ is a workload-conditional
optimization; it is not a drop-in eviction-policy upgrade;
it needs a pressure-aware fallback or adaptive gating
(Round 6 candidate: explicit recency floor) before being
claimed as generally superior. **The third path strengthens
the conclusion's robustness — three different simulators
agree — but does not change its content.**
