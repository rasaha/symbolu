# Phase 8 — KV Eviction Revival Audit

> **Status: audit complete (this doc), engineering NOT YET started.**
> Captured the strategic findings from the Phase 8a audit so the next
> session can pick up cleanly without re-deriving everything.

## TL;DR

Reviving Phase 4 KV eviction is the right move strategically (compounds
with int4_protected, unblocks PCAM's value prop), **but the original
"measure first" plan is the wrong kickoff order.** Audit recommends
pivoting to Route-A Days 4-5 (GPU verification) FIRST, because that's
the integration shape that compounds for both layers and is already
half-landed on CPU.

## What we knew going in

- Phase 4 eviction algorithm GREEN at -11.1% swap_out/decode_token vs LRU
- Cost -20% tokens/sec end-to-end (vLLM 0.7.3 Evictor-ABC tax)
- 7 audit findings fixed; Cython port (v9) recovered 0pp; cost is structural
- Route-A `cache_kv` hook plan has Days 1-3 LANDED on CPU (12 tests),
  Days 4-5 (GPU verification) PENDING
- Route-A is "two work-tracks, one hook surface" — same hook unblocks
  Phase 4 integration AND int4_protected paged-buffer tier

## What the audit found

### 1. The -20% throughput tax is NOT in the policy code

py-spy profile (`PHASE4_GPU_FINDINGS.md` §11):
- CTM+ scoring code = **1.1% of wall time** (0.9% protocol + 0.2% hooks)
- Other 18.9% = Python-call dispatch overhead from vLLM's scheduler
  hitting our Python evictor methods in hot paths that expect C-level
  speed
- Cython port (v9, §12.6) recovered 0pp

**Implication:** algorithmic optimization will not fix this. Only
integration-shape work (route-A) will.

### 2. Route-A as-shipped is dequant-only — it does NOT wire eviction-attention through

What `int4_cache_kv_route_a.py` does today (CPU days 1-3):
- Hooks `Attention.forward`
- Round-trips K/V through int4 quantize+dequantize
- Handles 2-D and 3-D layouts
- 12 CPU regression tests pass

What it does NOT do:
- Call `evictor.forward_block_attention(block_id, attention_sum)`
- Pass attention values to the Phase 4 evictor's scoring

**Implication:** there's a ~1-day "Route-A bridge" task between
"Route-A lands on GPU" and "Phase 4 evictor sees real attention via
Route-A's hook." This bridging was NOT scoped in the original
ROUTE_A_VLLM_CACHE_KV_PLAN.md.

### 3. The v5 measurement used method-limited calibration

- v5 used pooled-layer calibration (MRL=0.221, below the
  methodology's ≥0.3 bar)
- Per-layer recalibration landed POST-findings

**Implication:** the -11% swap_out number may itself be artificially
low. Proper per-layer calibration could improve algorithm quality,
separately from the integration tax fix.

## Strategic recommendation (revised plan)

**Skip Phase 8a's "measure first" original plan. Re-running the v5
workload today most likely re-confirms -20% and teaches us nothing
new about the path forward.**

**Pivot to Route-A Days 4-5 first.** Reasoning:
- Same hook surface unblocks BOTH product lines (int4_protected
  paged-buffer tier + Phase 4 eviction)
- Route-A is half-done on CPU; the remaining work is concrete
  (GPU verification + chat_32k validation)
- After Route-A lands on GPU, Phase 4 remeasurement becomes a
  **policy-tuning task**, not an architecture-risk task

## Revised Phase 8 sequence

| Phase | Work | Duration | Risk |
|-------|------|----------|------|
| **8b** (was 8a) | Route-A Days 4-5 GPU verification | 2-3 days | Medium — vLLM-version gotchas |
| **8b-bridge** | Wire forward_block_attention from Route-A hook to Phase 4 evictor (the gap audit surfaced) | 1 day | Low |
| **8a** (now downstream) | Phase 4 remeasurement under int4_protected + Route-A combined; per-layer recalibration; prefix-caching disabled OR matched-budget metric | 2 days | Low (post-integration) |
| **8c** | Combined-stack measurement on 4-model portfolio; update INT4_PROTECTED_VC_BRIEF.md + PCAM positioning | 2-3 days | Low |
| **Total** | | **~8-10 days** | Concentrated in 8b |

Original plan was ~14 days. The audit shaves 3-4 days off by skipping
the redundant pre-measurement.

## Three risks for any remeasurement (when 8a happens)

1. **Prefix-caching disruption.** v5 had CTM+ at 99% peak KV vs LRU at
   57% — not apples-to-apples (cache regime difference). Phase 8a must
   either disable prefix caching OR use **quality-at-matched-budget**
   instead of raw swap_out counts.
2. **Per-layer recalibration.** Must run BEFORE the remeasurement.
   v5 used pooled-layer (method-limited).
3. **Window-pruning interval starvation.** Log + verify the trig
   signal fires ~3000× / 60s (post-v6 fix) rather than the v5 bug's
   ~45× / 60s in window_pruning_pass only.

## Workload to reproduce (when 8a runs)

From `PHASE4_GPU_FINDINGS.md` §3 run v5:
- Model: Qwen2.5-7B
- Hardware: A100 (we'd run on H100 — note the difference)
- vLLM: 0.7.3 with `enforce_eager=True`, `enable_prefix_caching=True`
  (or False per risk #1), `gpu_memory_utilization=0.26`,
  `swap_space=16GB`
- Workload: chat_32k arrival pattern, 30 concurrent requests, prompts
  8000-30000 tokens uniform, up to 2048 decode tokens, 60s wall
- Cache regime: 99% peak KV utilization to force sustained eviction
  pressure

LRU baseline expected ~85 tok/s; v5 CTM+ Phase 4 was 68 tok/s
(-20%). Phase 8a target: Route-A integration restores parity or
close to it.

## Pointers for the next pickup

| File | Purpose |
|------|---------|
| `CTM_plus/KVPolicy/kv_policy/attention_evictor.py` | The 4-signal scoring policy (505 lines) |
| `CTM_plus/KVPolicy/kv_policy/vllm_evictor.py` | vLLM integration; the layer with the structural tax (2133 lines) |
| `CTM_plus/KVPolicy/kv_policy/int4_cache_kv_route_a.py` | Route-A CPU implementation (1060 lines) |
| `CTM_plus/Bench/scripts/ROUTE_A_VLLM_CACHE_KV_PLAN.md` | Engineering plan (141 lines); Days 1-3 LANDED, Days 4-5 PENDING |
| `CTM_plus/Bench/bench_out/PHASE4_GPU_FINDINGS.md` | The 3500-line audit + measurement history; §1-3, §6-8, §10-11 are the key sections |

Specific code anchors from the audit:
- Scoring formula: `attention_evictor.py` lines 394-411 (score_block)
- Evictor-ABC patching: `vllm_evictor.py` lines 199-267
- Integration tax py-spy diagnosis: `PHASE4_GPU_FINDINGS.md` §11
- Route-A interception: `int4_cache_kv_route_a.py` lines 527-590
  (_wrap_attention_forward_with_kv_rewrite)
- The v5 workload: `PHASE4_GPU_FINDINGS.md` §3 table, run v5, line 114
- Per-layer calibration risk: `PHASE4_GPU_FINDINGS.md` §9.3a.i

## Decision pending

User paused for reflection after the audit reframed the plan. When
work resumes, the kickoff choice is:
- Pivot to Route-A Days 4-5 first (audit-recommended)
- Stick with original 8a remeasurement first
- Run both in parallel and pick after seeing scripts for each
