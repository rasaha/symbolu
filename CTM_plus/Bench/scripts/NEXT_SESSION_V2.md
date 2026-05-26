# Next session — v2 production-hardening pickup

> Drop this file into your next Claude Code session, or copy the
> "PROMPT" block at the bottom. It gives a fresh session enough
> context to continue v2 work without re-litigating decisions.

## Where things stand (post-current-session)

**Branch:** `claude/dazzling-maxwell-xzQYx`

**Shipped headline:** INT4 protected (4-bit KV cache with 4%
K-channel protection). Tier A replication landed in the VC brief
at commit `419f975`. Three of four models replicated 15/15 needle;
Qwen-7B is at-the-margin under 4% mask. Brief is partner-safe.

**Retired (do NOT restart):**
* Phase 4 KV eviction (CTM+ trig scoring) — `PHASE8_RETIREMENT.md`
* Local TurboQuant / QJL KV-cache path — `TURBOQUANT_RETIREMENT.md`

**CLOSED:** v2 cache-reuse layer (cache-aware admission
scheduling, RadixAttention-style). See
`PHASE3_CACHE_AWARE_FINDINGS.md` for the measured finding.

History:
* Phase 0 (CPU prototype + tests): ✅ commit `3168e94`
* Phase 1 PR-1 (vLLM install + CPU smoke): ✅ commit `34763c8`
* Phase 1 PR-2 CPU plumbing: ✅ commit `d14383f`
* Phase 1 PR-2 V2 block-manager shape fix: ✅ commit `d812324`
* Phase 1 PR-2 GPU smoke (Qwen-7B H100): ✅ GREEN
* Phase 3A (shared-prefix workload + latency + probe): ✅ commit `fef82cc`
* Phase 3B (three-cell bench + dry-run): ✅ commit `5a85be8`
* Phase 3C measurement-path fix (cache-aware tree as instrument): ✅ commit `a873757`
* Phase 3C 2-seed Tier-A GPU runs: ✅ GREEN measurement,
  **inconclusive realized-hit signal + mild E2E p99 regression**
* Phase 3D measured finding: ✅ `PHASE3_CACHE_AWARE_FINDINGS.md`
* **Phase 3 CLOSED.** Cache-aware reorder is **not productionized**.
  Code stays in-tree per the Phase 4 + TurboQuant precedent. CLI
  flag retained as experimental. The measurement-only install +
  three-cell bench harness retained as v2 measurement utilities.

VC brief: unchanged. Cache-aware was never in the brief.

**CLOSED:** v2 Extended Pinning Policy. See
`PHASE4_EXTENDED_PINNING_FINDINGS.md` for the measured finding.

History:
* Phase 4A (CPU prototype + 32 tests): ✅ commit `2590505`
* Phase 4B (driver wiring + CLI + 3-cell bench): ✅ commit `451d307`
* Phase 4F design (v2.1 priority-LRU; gated on 4C ship signal): ✅ commit `ab66df1` — ARCHAEOLOGY (gating condition not met)
* Phase 4C runbook: ✅ commit `2aa5d36`
* Phase 4C operational fixes (`--max-model-len`, `--preemption-mode`): commits `14a4ba0`, `14cac6a`
* Phase 4C three GPU runs at seed=42 (A100):
  - Loose memory (gpu_mem=0.5): zero preemption, zero pinned_evictions_avoided
  - Tight memory (gpu_mem=0.25, max_model_len=4096): zero preemption, zero pinned_evictions_avoided
  - Recompute + cranked-up pressure (n=500, rate=20, decode=256, recompute mode): cell A produced 96 preemption events (confirming workload size is sufficient), but cells B and C with prefix caching ON still produced ZERO preemption — vLLM's content-hash dedupe absorbs the demand
* Phase 4D measured finding: ✅ `PHASE4_EXTENDED_PINNING_FINDINGS.md`
* **Phase 4 CLOSED.** Extended pinning is **not productionized**.
  Mechanism mechanically correct (all install/manager/wrap gates
  pass); had no opportunity to act because vLLM's stock LRU +
  prefix caching already handles cohort-shared workloads natively.
  Code stays in-tree per the Phase 3 + TurboQuant precedent.
  CLI flags retained as experimental. The three-cell bench
  harness retained as a v2 measurement utility.

VC brief: unchanged. Extended pinning was never in the brief.

## Five pending v2 items (the brief's Tier 1 list)

Each has effort + cost from `INT4_PROTECTED_VC_BRIEF.md` page 5
"Tier 1 — production blockers" table.

| # | Item | Effort | GPU $ | Status | Key reference |
|---|---|---:|---:|---|---|
| 1 | **Cache reuse** (v2 cache-aware scheduling) | CLOSED at Phase 3D | ~$0.50 spent | **Inconclusive measured finding** — not productionized. CLI flag retained as experimental. See `PHASE3_CACHE_AWARE_FINDINGS.md`. | `PHASE3_CACHE_AWARE_FINDINGS.md`, `V2_CACHE_REUSE_DESIGN.md`, `V2_CACHE_REUSE_PHASE1_INTEGRATION_NOTE.md` |
| 2 | **CUDA Graphs** for the model forward path | 4-7 days | ~$0.20 | Read-path preflight done (B-pre-1..4); write-path preflight is the gating item | `OPTION_B_PREFLIGHT.md`, `PHASE6_PERF_REPORT.md` |
| 3 | **Tensor parallelism** for 70B-class | 3-5 days | ~$0.50 (multi-GPU pod) | Untouched; code "expected to Just Work" per brief, unverified | brief page 5; INT4_PROTECTED_README.md |
| 4 | **Quality benchmark harness** (MMLU + HumanEval + LongBench) | 2-3 days | ~$0.30 | Untouched; current quality bar is needle-only | brief page 5 "Broader quality bench" row |
| 5 | **Broader INT4 protected model validation** | 1-2 days per model | ~$0.05-0.20 per model | 4 models done; Phi/Qwen-72B/etc pending; D=96 head dim needs kernel work | brief page 4 "cross-family transfer" + page 5 Tier 2 "Kernel support for D=64/D=96" |

**Total if all five land cleanly: ~3-4 engineer-weeks + ~$1.5-2.0
GPU.** That matches the brief's "focused 6-8 week effort can land
Tier 1 cleanly" framing with margin for findings.

## Discipline rules (durable)

1. **Do NOT restart Phase 4 KV eviction.** Retired after failing
   180s-wall measurement on chat_32k. Don't add an algorithm in
   that family.
2. **Do NOT restart local TurboQuant KV-path.** Retired after
   3052× perplexity ratio on Qwen-7B. Don't restore the
   `--turboquant-kv` flag.
3. **Do NOT edit `INT4_PROTECTED_VC_BRIEF.md` without explicit
   user approval.** Tier A replication is the current state;
   any edit must be backed by replicated measurement.
4. **CPU-first verification.** Every new code path lands with
   CPU tests before any GPU spend. See the v2 cache-reuse PR-1
   pattern: 22 CPU tests gate the vLLM integration.
5. **Orthogonality contract.** v2 work does NOT touch
   `Int4ProtectedAttentionImpl`, the forked vllm-flash-attn
   kernel, or the protected-channel splice logic. v2 is
   serving-layer + benchmark-layer work.
6. **No claim about combined-stack X× savings without measurement.**
   The previous "stacks multiplicatively for 3-4× savings"
   projection was retired; the measured combined cell was WORSE
   than either component alone.
7. **Phase-gated execution.** Don't skip phases. For each new
   item: design doc → CPU prototype + tests → vLLM integration
   → GPU smoke → GPU full validation → brief revision (gated on
   approval).
8. **Honest scope.** Mark provisional / pending / replicated
   explicitly. The Tier C audit pattern (`VC_BRIEF_REPLICATION_AUDIT.md`)
   is the template.

## Recommended priority order

If forced to rank by partner-safety × cost-effectiveness:

1. **Cache reuse PR-2** (finish in-flight work; ~$0.10 + 1-2 days).
   Closes a started workstream cleanly. Doesn't add new
   product surface.
2. **Broader model validation** (~$0.05-0.20 per model; quick).
   Each new replicated model strengthens the "cross-family
   transfer" claim. Low risk, partner-credible. Start with one
   adjacent model (e.g., Llama-3.1-70B if TP is available, or
   Qwen-2.5-32B).
3. **Quality benchmark harness** (~$0.30; 2-3 days). Moves the
   brief from "needle-only" to "needle + MMLU + HumanEval." Big
   partner-credibility win for moderate effort.
4. **CUDA Graphs** (~$0.20; 4-7 days). Biggest single-axis
   throughput improvement (projected 2-3× aggregate). Has the
   write-path preflight as a known blocker.
5. **Tensor parallelism** (~$0.50 + multi-GPU pod; 3-5 days).
   Highest risk because untested, but unlocks the largest model
   tier (70B+). Best if scheduled when a multi-GPU pod is
   already available.

User chooses; this is a recommendation, not a directive.

## Per-item entry hooks

### 1. Cache reuse — CLOSED at Phase 3D

**STATUS: Phase 3 CLOSED.** Measured finding documented at
`Bench/scripts/PHASE3_CACHE_AWARE_FINDINGS.md`. Two-seed
Tier-A measurement on Qwen-7B H100 returned an inconclusive
realized-hit signal (C/B = 0.903 and 1.115, opposite signs)
with a consistent mild E2E p99 regression (1.4-1.6×). Cache-
aware reorder is **not productionized**.

What stays in-tree (per Phase 4 + TurboQuant precedent — keep
code, document the finding, no destructive removals):

- `KVPolicy/kv_policy/cache_aware_scheduler.py` (Phase 0)
- `KVPolicy/kv_policy/cache_aware_install.py` (full +
  measurement-only modes)
- `KVPolicy/kv_policy/prefix_hit_probe.py` (Phase 3A probe)
- `Bench/ctm_bench/runner_vllm_streaming.py` (driver wiring +
  shared-prefix builder + latency telemetry)
- `Bench/ctm_bench/scripts/bench_phase3_cache_aware.py` (the
  three-cell bench harness — partner-credible measurement
  utility, retained as a v2 tool)
- CLI flags `--cache-aware-scheduling` (experimental warning in
  --help; do not enable in production) and
  `--cache-aware-measurement-only` (retained as a measurement
  utility independent of reorder)
- 119 CPU tests

What VC brief says: unchanged. Cache-aware was never in the brief.

Revisit conditions (per `PHASE3_CACHE_AWARE_FINDINGS.md`):
1. Better-calibrated predictor (the 3.1× under-prediction is the
   load-bearing mechanism behind the inconclusive signal)
2. Real chat workload replay (synthetic Pareto may not represent
   production)
3. Tier-A 5-seed replication (~$0.50; would tighten confidence
   interval on the 10-15% effect)
4. Partner-driven workload where FCFS produces less natural
   concurrent overlap

### 2. CUDA Graphs

Read `OPTION_B_PREFLIGHT.md` first. The read-path preflight
(B-pre-1 through B-pre-4) is complete. The blocker is the
write-path preflight — `enforce_eager=False` crashes at
`_seq_id_from_block_table_row().item()` in the write path.

Phase order:
1. Write-path preflight (small fixes to the writer to remove
   `.item()` calls that block CUDA graph capture)
2. Capture enable smoke (single-prompt with graphs enabled)
3. Aggregate throughput re-measurement (target: 2-3× the current
   ~42 tok/s @ B=8)

### 3. Tensor parallelism

Untouched; code "expected to Just Work given our read/write path
structure" per the brief. Needs a multi-GPU pod (2-rank smoke at
minimum; 4-rank for 70B-class).

Phase order:
1. CPU sanity: verify the int4_protected backend's TP-relevant
   code paths handle `tensor_parallel_size > 1` cleanly
   (probably needs new tests)
2. 2-rank smoke on Qwen-7B (force TP=2; verify outputs match
   TP=1)
3. 4-rank smoke on Llama-70B or Qwen-72B (the actual unlock)

### 4. Quality benchmark harness

Untouched. Likely implementation: `lm-eval-harness` integration
that takes a model + KV-backend (bf16 / fp8 / int4_protected) and
runs MMLU + HumanEval + LongBench, reports scores side-by-side.

Phase order:
1. CPU prototype: harness adapter that runs a tiny eval (e.g.,
   MMLU 50q) on a fake model — verify the plumbing works
2. GPU smoke on Qwen-7B: MMLU 200q for bf16 vs int4_protected
   (the brief currently claims -0.9pt MMLU @ 1000q at v1; that
   number from `PHASE4_GPU_FINDINGS.md` §19.4 should be replicable)
3. Full quality matrix: 4 models × 3 benchmarks × 2 backends
   (bf16 + int4_protected; fp8 optional)

### 5. Broader model validation

Iterative. Each new model:
1. Verify the calibration script (`calibrate_phase5b_protect_mask.py`)
   produces a mask for the new model
2. Run `verify_phase5b_5_needle.py` with 2 seeds (Tier A replication
   discipline)
3. Run `bench_phase5c_v1.py` three-way (cuda blocks + per-seq
   latency)
4. Update the brief's portfolio table if 2-of-2 replicated

D=96 head-dim models (e.g., Phi-3.5) need a kernel recompile
first per brief Tier 2 — that's not pure validation, it's a
kernel extension. Start with D=128 models that the existing
kernel supports.

## Durable artifacts to read first

```
/home/user/symbolu/
├── INT4_PROTECTED_VC_BRIEF.md                                            ← headline (do not edit)
└── CTM_plus/
    ├── INVESTOR_PITCH.md                                                  ← post-retirement state
    ├── TURBOQUANT_RETIREMENT.md
    ├── KVPolicy/
    │   ├── INT4_PROTECTED_README.md
    │   └── kv_policy/
    │       ├── cache_aware_scheduler.py           ← Phase 0 prototype
    │       ├── cache_aware_install.py             ← PR-1 vLLM install
    │       └── int4_protected.py                  ← shipped backend (do not touch)
    └── Bench/
        ├── tests/
        │   ├── test_cache_aware_scheduler.py      ← Phase 0 tests (24)
        │   ├── test_cache_aware_install.py        ← PR-1 tests (22)
        │   └── test_int4_cache_kv_route_a.py      ← int4_protected tests
        ├── scripts/
        │   ├── V2_CACHE_REUSE_DESIGN.md           ← v2 cache-reuse design
        │   ├── V2_CACHE_REUSE_PHASE1_INTEGRATION_NOTE.md   ← Phase 1 plan
        │   ├── OPTION_B_PREFLIGHT.md              ← CUDA Graphs preflight
        │   ├── PHASE6_PERF_REPORT.md              ← throughput history
        │   ├── PHASE5C_USAGE.md                   ← INT4 protected end-user recipe
        │   ├── PHASE8_RETIREMENT.md               ← Phase 4 retirement record
        │   ├── PHASE8_EVICTION_AUDIT.md           ← pre-Phase-8 audit
        │   ├── VC_BRIEF_REPLICATION_AUDIT.md      ← Tier A audit pattern
        │   ├── NEXT_SESSION_V2.md                 ← THIS FILE
        │   └── (the verify_* / bench_* scripts)
        └── bench_out/
            ├── VC_BRIEF_TIER_A/                   ← Tier A replication artifacts
            └── (historical runs)
```

## PROMPT — original v2 production-hardening (historical, pre-Phase-3/4 closure)

```
Continuing v2 production-hardening on branch claude/dazzling-maxwell-xzQYx.
Latest commit is 34763c8 (v2 cache-reuse Phase 1 PR-1 — CPU green).

Before doing any work, read these four files in order:
1. INT4_PROTECTED_VC_BRIEF.md (root) — current partner-safe state
2. CTM_plus/Bench/scripts/NEXT_SESSION_V2.md — this is your briefing
3. CTM_plus/Bench/scripts/PHASE8_RETIREMENT.md — what's retired (don't
   restart)
4. CTM_plus/TURBOQUANT_RETIREMENT.md — what else is retired

Five v2 items are pending; pick one and propose a plan before
writing code:

1. Cache reuse PR-2 — vLLM streaming-runner plumbing + GPU smoke
   (~1-2 days + ~$0.10 GPU). Finishes work already started.
2. CUDA Graphs — write-path preflight + capture enable + throughput
   re-measurement (~4-7 days + ~$0.20 GPU). Read OPTION_B_PREFLIGHT.md
   first.
3. Tensor parallelism — 2-rank smoke + 4-rank for 70B-class
   (~3-5 days + ~$0.50 GPU + multi-GPU pod).
4. Quality benchmark harness — lm-eval-harness integration for MMLU
   / HumanEval / LongBench (~2-3 days + ~$0.30 GPU).
5. Broader INT4 protected validation — one new model at a time
   (~$0.05-0.20 per model).

Discipline rules:
* Do NOT restart Phase 4 KV eviction. Retired.
* Do NOT restart local TurboQuant KV-path. Retired.
* Do NOT edit INT4_PROTECTED_VC_BRIEF.md without explicit approval.
* CPU-first verification: design → CPU prototype → CPU tests → GPU.
* Orthogonality: v2 work does not touch Int4ProtectedAttentionImpl,
  the forked vllm-flash-attn kernel, or the protected-channel splice.
* No combined-stack X× projections without measurement.
* Phase-gated execution; honest scope (mark provisional vs replicated).

For your first response: tell me which of the five items you'd
work on first and why, then propose a phased plan with explicit
acceptance gates for the first phase. Do NOT write code until I
approve.
```

## PROMPT — Tiered KV storage Phase 5A (copy-paste into the next session)

Use this for the **next focus**: extending the int4_protected
shipped backend with verified warm-tier (CPU RAM) support
and — if warm tier checks out — designing the cold-tier
(NAND/disk) snapshot/restore path.

```
Continuing v2 production-hardening on branch claude/magical-cannon-zDMkY.
Latest commit is 3cbc01d (v2 Extended Pinning Phase 4 CLOSED — measured
finding + experimental disposition).

Phase 3 (cache-aware admission scheduling) and Phase 4 (extended
pinning) both closed as inconclusive measured findings. v1 INT4
protected remains the shipped headline. Code from both phases stays
in-tree as experimental measurement utilities. VC brief unchanged.

Before doing any work, read these files in order:
1. INT4_PROTECTED_VC_BRIEF.md (root) — current partner-safe state
2. CTM_plus/Bench/scripts/NEXT_SESSION_V2.md — this is your briefing
3. CTM_plus/Bench/scripts/PHASE3_CACHE_AWARE_FINDINGS.md — Phase 3 closure
4. CTM_plus/Bench/scripts/PHASE4_EXTENDED_PINNING_FINDINGS.md — Phase 4 closure
5. CTM_plus/Bench/scripts/PHASE8_RETIREMENT.md — Phase 4 trig retirement
6. CTM_plus/TURBOQUANT_RETIREMENT.md — TurboQuant retirement

Today's focus is Phase 5A — verify that the int4_protected
shipped backend's packed KV layout survives vLLM 0.7.3's built-in
CPU swap path (preemption_mode='swap' + swap_space=N).
This is the lowest-cost way to determine whether a "warm tier in
CPU RAM" exists today (free from vLLM) or requires custom work.

Phase 5A scope (the only phase greenlit so far):
* CPU work + ONE GPU smoke (~2-3 days + ~$0.10).
* Verify int4_protected output is bit-identical before vs after
  a forced preemption-swap-restore cycle.
* Add telemetry for cpu_swap_pool usage + swap-in latency.
* Sweep gpu_memory_utilization to find where CPU swap kicks in.
* Confirm composition with extended_pinning / cache_aware_install /
  prefix_hit_probe (or document which combinations are incompatible).

Phase 5A acceptance gates (the load-bearing ones):
* G1: int4_protected output bit-identical pre vs post swap-restore
* G2: swap_out_blocks > 0 under engineered pressure
* G3: telemetry: cpu_swap_pool_bytes_in_use + swap_in_latency_ms
      surfaced in the streaming summary
* G4: extended_pinning + cache_aware_install + prefix_hit_probe
      composition smoke — all three install paths coexist with
      preemption_mode='swap' without crashing
* G5: no Int4ProtectedAttentionImpl modification (AST gate)
* G6: no vllm-flash-attn kernel modification

Conditional Phase 5B+ — gated on Phase 5A green:
* 5B (cold tier prototype): per-session snapshot/restore via
  safetensors. 1 week CPU. Bit-equivalence round-trip.
* 5C (allocator integration): demand-paging restore from cold
  back to warm/hot. 1-2 weeks. THIS is the hard part.
* 5D (3-tier bench): hot-only / +warm / +warm+cold cells. ~$0.50.
* 5E (decision + finding doc).

If 5A is red (vLLM's swap doesn't preserve int4_protected layout),
warm tier requires custom work — another 1-2 weeks before 5B can
even start. Phase 5A is the cheapest way to learn this.

Discipline rules (durable):
* Do NOT restart Phase 4 KV eviction (trig). Retired.
* Do NOT restart local TurboQuant KV-path. Retired.
* Do NOT restart Phase 3 cache-aware reorder. Closed inconclusive.
* Do NOT restart Phase 4 extended pinning reorder. Closed inconclusive.
* Do NOT edit INT4_PROTECTED_VC_BRIEF.md without explicit approval.
* CPU-first verification: design → CPU prototype → CPU tests → GPU.
* Orthogonality: v2 work does not touch Int4ProtectedAttentionImpl,
  the forked vllm-flash-attn kernel, or the protected-channel splice.
  (Phase 5A's verification of swap-restore is observation-only; it
  may need to READ but not WRITE int4_protected backend state.)
* No combined-stack X× projections without measurement.
* Phase-gated execution; honest scope (mark provisional vs replicated).

For your first response: read the briefing docs, then propose a
phased plan for Phase 5A with explicit acceptance gates. Do NOT
write code until I approve.

If Phase 5A is approved AND green, also draft Phase 5B (cold tier
CPU prototype) as a separate plan-of-record before implementing.
The cold tier is genuinely new product surface — 4-6 weeks of
engineering + measurement at minimum — so its scope must be
explicitly approved phase-by-phase, NOT folded into 5A.
```

End of file.
