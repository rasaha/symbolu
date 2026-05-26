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

**In progress:** v2 cache-reuse layer (cache-aware admission
scheduling, RadixAttention-style):
* Phase 0 (CPU prototype + tests): ✅ commit `3168e94`
* Phase 1 PR-1 (vLLM install + CPU smoke): ✅ commit `34763c8`
* Phase 1 PR-2 CPU plumbing (driver arg + install hook +
  CLI flag + stats field + 8 CPU tests): ✅ commit `d14383f`
* Phase 1 PR-2 V2 block-manager BlockTable shape fix (CPU
  mock-vs-real-vLLM drift): ✅ commit `d812324`
* Phase 1 PR-2 GPU smoke (Qwen-7B H100): ✅ **GREEN** —
  gates B1/B2/B3/B5/B7 + flag-OFF regression + Tier A needle
  15/15 all verified. Workload-shape-dependent gates B4 and B6
  (`reordered_count > 0`, `prediction_accuracy >= 0.85`) deferred
  per PR-2 scope ("no hit-rate-improvement claim in PR-2").
* **PR-2 acceptance set CLOSED.**
* Phase 1 PR-2 follow-up (shared-prefix workload + B4/B6
  smoke): pending
* Phase 3 (GPU validation on chat_32k): pending

## Five pending v2 items (the brief's Tier 1 list)

Each has effort + cost from `INT4_PROTECTED_VC_BRIEF.md` page 5
"Tier 1 — production blockers" table.

| # | Item | Effort | GPU $ | Status | Key reference |
|---|---|---:|---:|---|---|
| 1 | **Cache reuse** (v2 cache-aware scheduling) | PR-2 done; ~1 day shared-prefix workload + ~2-3 days Phase 3 GPU | ~$0.20 | PR-2 acceptance set CLOSED (gates B1/B2/B3/B5/B7 + flag-OFF + Tier A 15/15 all GREEN); shared-prefix workload + Phase 3 next | `V2_CACHE_REUSE_DESIGN.md`, `V2_CACHE_REUSE_PHASE1_INTEGRATION_NOTE.md` (§"PR-2 status" + acceptance-gate table) |
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

### 1. Cache reuse PR-2

**STATUS: PR-2 acceptance set CLOSED.** See
`V2_CACHE_REUSE_PHASE1_INTEGRATION_NOTE.md` §"PR-2 status" for
the full acceptance-gate table and committed evidence.

What landed:

- ✅ `AsyncEngineDriver(cache_aware_scheduling: bool = False,
  cache_aware_max_starvation_seconds: float = 30.0)` arg
- ✅ Hook `install_cache_aware_scheduler()` into engine init
  (same pattern as `int4_route_a` install in
  `runner_vllm_streaming.py`)
- ✅ New `cache_aware_scheduler_stats` field on
  `StreamingRunCellResult`
- ✅ CLI flag `--cache-aware-scheduling` on `run_streaming.py`
- ✅ V2 block-manager BlockTable shape fix (commit `d812324`)
  to handle real vLLM 0.7.3 V0+V2 path
- ✅ 12 CPU plumbing/regression tests (8 in
  `Bench/tests/test_cache_aware_runner_plumbing.py` + 4 V2-shape
  tests in `test_cache_aware_install.py`)
- ✅ Qwen-7B GPU smoke GREEN (admitted=20, completed=20,
  decode_tokens=640, `tree_inserts=20`, `tree_evictions=632`,
  all 9 stats keys populated with `enabled=True`)
- ✅ int4_protected Tier A regression GREEN (Qwen-7B seed=44:
  **15/15 == stock bf16**, 0 fallbacks)

Pending (not in PR-2 scope per the original approval — "no
hit-rate-improvement claim in PR-2"):

- Shared-prefix workload to exercise gates 4 (`reordered_count >
  0`) and 6 (`prediction_accuracy >= 0.85`); ~1 day code + CPU
  test + a short GPU smoke (~$0.05). Could land as PR-2.5 or
  fold into Phase 3.
- Phase 3 GPU validation on chat_32k (the real
  measurement-of-effect run). ~2-3 days + ~$0.30.

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

## PROMPT (copy-paste into the next session)

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

End of file.
