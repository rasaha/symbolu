# Kernel 6c.3C — resume / status snapshot

> Read this first when resuming work on the 6c.3C kernel-fork
> pivot. Points at the design docs, captures the current state of
> the dev pod, and gives concrete first actions.

## TL;DR

- **Working on:** 6c.3C — a fork of `vllm-project/flash-attention` (the
  vendored vLLM FA fork) at SHA `720c948`, adding INT4 KV cache with
  static protected-K channels.
- **Why this fork:** §20.6.3 closed 6c.3A as not competitive (bypass-FA-
  with-our-own-Triton-kernel loses at end-to-end throughput because
  vLLM's FA is too fast). 6c.3C lands the FA-integrated INT4 path.
- **Latest verified state:** Phase 5A GREEN at commit `b821ace`.
  Native-kernel-routed vLLM decode now proven end-to-end on real
  Qwen2.5-7B inference:
    - All 28 attention layers wrapped at install time (leaf-Attention
      heuristic distinguishes vllm.attention.layer.Attention from
      model-level wrappers like Qwen2Attention)
    - 0 fallback calls during the smoke test (full kernel coverage)
    - Decode output correctly retrieves the needle ("XYZ123XYZ123")
    - 24-char common prefix with stock vLLM before INT4 drift causes
      divergence — matches the ~0.997 algorithm cosine floor we
      measured in Phase 2.3/6.4
  Decode throughput: 28.8 tok/s vs stock 80.3 tok/s. The 2.8× slowdown
  is the parallel FP16 sidecar's Python-managed cache.append() cost
  per token (the documented Phase 5A overhead — measurement-time cost,
  goes away in Phase 2.4 when HBM INT4 storage drops the sidecar).
- **What's NOT yet done:** Phase 2.4 (REAL INT4 K HBM read — the
  memory-savings step), Phase 5B/5C (batch > 1, kv_cache_dtype
  first-class registration), Phase 6 measurement (throughput, KV
  memory, real-data needle on full ship config).
- **Next phase decision (open):**
    - Phase 6.4-native — rerun protect-fraction sweep through the
      Phase 5A install (proves the transitive equivalence argument
      directly, ~1-2 days)
    - Phase 2.4 — HBM INT4 storage with packed uint8 + custom CUTLASS
      load atoms (the memory-savings step, ~3-5 days, highest
      remaining technical risk)
    - Phase 5B — batch > 1 multi-sequence support (vLLM serving v1,
      ~3-5 days)
  (5 days, end-to-end plumbing).

## Hard scope guard (do not creep)

v1 is decode-only, static protected-K mask, INT4 unprotected K/V,
BF16 protect sidecar, **Qwen2.5-7B only**, sm80 only.

**Out of scope:** dynamic masks, pre-RoPE quant, FP4/NVFP4, speculative
decode, multi-model sweep, prefill kernel mods, FA3/Hopper instantiations,
symmetric quant, group sizes ≠ 32.

## Files to read (in order)

| File | Owns |
|---|---|
| `KERNEL_6C3C_RESUME.md` (this) | Snapshot + first actions |
| `KERNEL_6C3C_DESIGN.md` | Required architecture + v1 scope locked + PR triage outcome (base = A) |
| `KERNEL_6C3C_RUNBOOK.md` | Phase-by-phase plan + per-phase results so far |
| `KERNEL_6C3C_PHASE12_CODEREAD.md` | Source map at SHA 720c948 + Phase 1/2 surface |
| `KERNEL_6C3C_PROTECT_MASK_DESIGN.md` | §7.Q1 resolution — protect mask provenance + storage layout |
| `KERNEL_6C3C_PHASE2_3_DESIGN.md` | Phase 2.3 surface (the K read sites, insertion point, gating, effort) |

## Audit trail — branch `claude/fp8-kv-competitive-gap-zpSjg`

| Commit | Closes |
|---|---|
| `e09aee5` | 6c.3A close — §20.6.3 verdict in PHASE4_GPU_FINDINGS.md |
| `e7ce0eb` | 6c.3C design shell |
| `8d44162` | PR triage closes — base = A (fork vllm_flash_attn) |
| `eab8c3d` | Runbook |
| `5a9ce4f` | File-path fix for v0.7.3 SHA |
| `ac45ec1` | Phase 0 scripts (install + restore + smoke) |
| `4d76779` | §7.Q1 + §5.5 compact-lock |
| `6261c09` | Phase 1/2 code-read + runbook re-partition |
| `bb5928e` | **Phase 0 GREEN** (stock build matches baseline) |
| `e53e14c` | Phase 1 patch scripts |
| `2dd93f2` | Phase 1 fix (slim file + relative import) |
| `8a4ffba` | **Phase 1 GREEN** (bit-equality of no-op delegate) |
| `db6457b` | Phase 2.1 patches (dispatch + cloned .cu, dead code) |
| `0fdd1b8` | **Phase 2.1 GREEN** (build mechanics) |
| `3d3efe8` | Phase 2.2 patches (route through new path) |
| `549b942` | Phase 2.2 fix (forward decl in flash.h) |
| `200196d` | **Phase 2.2 GREEN** (route live, bit-equal) |
| `6a2347a` | Phase 2.3 design brief |
| `61f83df` | Phase 2.3 patcher + helper + verify script (builds clean) |
| `df67260` | Phase 2.3 diagnostic — algorithm drift floor ~0.997 (vs brief's 0.9999) |
| `edf0bcd` | **Phase 2.3 GREEN** (relaxed gate to 0.995, route-B match bit-for-bit) |
| `492e590` | **Phase 2.5 GREEN** (template-gated dispatch, stock perf restored 80 → 67 μs) |
| `8a39a08` | **Phase 3 GREEN** (V cache INT4 transform — per-token, axis-flipped helper) |
| `48c2b4a` | Phase 4 patcher (protect-K mask plumbing + helper extension) |
| `7993e8d` | Phase 4 gate-calibration commit (Gaussian-only test was unfair to algorithm) |
| `3f8787b` | **Phase 4 GREEN** (outlier sub-test + recovery-delta gate; 4.5 milli-cosine recovery on outliers) |
| `9c54f6b` | Docs — Phase 2.5/3/4 GREEN results recorded |
| `028cffe` | Phase 2.3 insertion-point retrospective audit |
| `095961e` | Phase 6.4 sweep (algorithm path) + decision-rule aggregator |
| `e9e48a5` | Phase 6.4 — transformers >=5.0 prophylactic check bypass |
| `e8eecbf` | Phase 6.4 long-context sweep at ~30k Qwen tokens |
| `0b80770` | Phase 6.4 aggregator — fix to match track_e JSON schema |
| `1e4dfb5` | **Phase 6.4 GREEN** — delta-gates vs FP16 baseline; 4% protect = 100% needle on real Qwen |
| `4b07f97` | Phase 5A code lands — native-kernel-routed vLLM decode installer + smoke test + design doc |
| `b821ace` | **Phase 5A GREEN** — leaf-attention fix; 0 fallbacks, 28+868 wrapped calls, needle correctly retrieved |

## GPU pod state (as of last session)

- **Dev tree:** `/workspace/dev/vllm-flash-attn-dev` at SHA `720c948`
  with patches applied through Phase 2.2 (idempotent via the apply
  scripts; re-running is a no-op).
- **Backup of original vendored .so:**
  `/workspace/dev/build-logs/vllm_flash_attn_vendored_backup` — restore
  via `bash CTM_plus/Bench/scripts/restore_vendored_vllm_flash_attn.sh`
  if anything breaks.
- **Installed in venv-vllm:** the Phase 2.2 wheel
  (`vllm_flash_attn-2.7.2.post1+cu128`) overwrites
  `/workspace/venv-vllm/lib/python3.12/site-packages/vllm/vllm_flash_attn/`
  with the dev build. `flash_attn_with_int4_kvcache` is importable.

## Active code path (Phase 2.2)

```
Python flash_attn_with_int4_kvcache (vllm_flash_attn/flash_attn_interface.py)
  → torch.ops._vllm_fa2_C.fwd_kvcache_int4
  → mha_fwd_kvcache_int4 + Int4KvDispatchGuard (thread-local ON)
  → mha_fwd_kvcache (stock 280-line param setup, untouched)
  → run_mha_fwd reads thread-local, sets params.is_int4kv = true
  → if constexpr (bf16 && hdim==128 && !causal):
      → run_mha_fwd_splitkv_dispatch_int4kv<bf16_t, 128, false>
      → run_flash_splitkv_fwd<Flash_fwd_kernel_traits<128, 64, 128, 4, false, false, bf16_t>, false>
  → (Phase 2.3+ adds the conditional in-register transform here)
```

## Smoke test commands

To verify the dev install is still working:

```bash
# 1. Import sanity.
python3 -c "
from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache, flash_attn_with_kvcache
import torch
print('OK:', torch.ops._vllm_fa2_C.fwd_kvcache_int4)
"

# 2. Bit-equality of the new path.
python3 /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase1.py

# 3. Stock vLLM unbroken (cell A throughput).
bash /workspace/symbolu/CTM_plus/Bench/scripts/smoke_test_fa_install.sh
```

All three should PASS. If any fails on a fresh session, restore the
vendored copy:

```bash
bash /workspace/symbolu/CTM_plus/Bench/scripts/restore_vendored_vllm_flash_attn.sh
```

…then re-run the patch+build cycle:

```bash
bash /workspace/symbolu/CTM_plus/Bench/scripts/apply_phase1.sh   # idempotent
bash /workspace/symbolu/CTM_plus/Bench/scripts/apply_phase2_1.sh # idempotent
bash /workspace/symbolu/CTM_plus/Bench/scripts/apply_phase2_2.sh # idempotent
```

(All three apply scripts skip already-applied patches via sentinel-
string detection. The cold rebuild takes ~10-15 min if any C++ files
were touched.)

## Where Phase 2.3 picks up

Phase 2.3 inserts a runtime-gated quantize→dequant transform at the
4 K read sites in `compute_attn_1rowblock_splitkv`
(`flash_fwd_kernel.h` lines 267, 851, 929, 990). The transform:

1. Reads K from smem (already loaded by the existing cp.async).
2. Computes per-group max-abs scale (4 groups × kBlockN=128 rows /
   32 per group = 4 scales per K block).
3. Quantizes to INT4 with route-B's rounding convention (must match
   `kv_policy/int4_per_channel_kv.py::quantize_per_channel_int4`
   exactly or cosine drifts at ±1 LSB).
4. Dequantizes back to BF16.
5. Writes back to the same smem locations.
6. Gated on `params.is_int4kv` (runtime check; nvcc CSEs the branch
   since the condition is uniform across the threadblock).

The cooperative max-abs reduction is the hard part — borrow FA's
existing `Softmax::reduce_max` pattern (warp-shuffle + smem
scratchpad) and adapt max → max-abs.

**Acceptance:** `verify_phase1.py` still PASS bit-equal (or cosine
≥ 0.9999 / max-abs ≤ 1e-2) on Qwen2.5-7B shapes. Stock path
unchanged.

**Effort estimate:** ~3 engineer-days (1 day reduction + 1 day
quant/dequant + 1 day integration + drift iteration).

**File to modify:** `csrc/flash_attn/src/flash_fwd_kernel.h`.
Possibly a new helper header in `csrc/common/` to avoid 4× code
duplication across the K read sites.

## What NOT to do in Phase 2.3

- Don't change the HBM K layout (still BF16). That's Phase 2.5.
- Don't add the protect-K BF16 sidecar. That's Phase 4.
- Don't touch V (Phase 3).
- Don't add prefill kernel modifications.
- Don't add more `if constexpr` template gating — Phase 2.5+ needs
  it for the real INT4 read; Phase 2.3 stays runtime-gated.
